#!/usr/bin/env python3
"""Read-only live FYERS NIFTY iron-condor quote and payoff snapshot.

Never sends orders.  It deliberately prices short legs at bid and protective
legs at ask, so reported credit is conservative.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sector_heatmap.config import load_config
from sector_heatmap.handoff import FyersFoMaster
from sector_heatmap.market_calendar import IST

UNDERLYING = "NSE:NIFTY50-INDEX"
LEGS = ((23500, "PE", -1), (23400, "PE", 1), (23600, "CE", -1), (23700, "CE", 1))


def quote(row: dict, side: int) -> float:
    # Conservative executable estimate: sell at bid, buy at ask.
    key = "bid" if side < 0 else "ask"
    value = float(row.get(key) or 0)
    if value <= 0:
        raise RuntimeError(f"Missing {key} for {row.get('symbol')}")
    return value


def main() -> None:
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("A current FYERS token is required.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    discovery = client.optionchain({"symbol": UNDERLYING, "strikecount": 1, "timestamp": ""})
    expiry = (discovery.get("data", {}).get("expiryData") or [None])[0]
    if not expiry:
        raise RuntimeError("FYERS returned no NIFTY expiry.")
    response = client.optionchain({"symbol": UNDERLYING, "strikecount": 15, "timestamp": str(expiry["expiry"]), "greeks": "1"})
    if response.get("s") != "ok":
        raise RuntimeError(response.get("message") or "FYERS option chain unavailable")
    rows = response["data"]["optionsChain"]
    spot = float(next(row for row in rows if row.get("option_type") == "")["ltp"])
    lookup = {(int(row["strike_price"]), row.get("option_type")): row for row in rows if row.get("option_type") in {"CE", "PE"}}
    chosen = []
    symbols = []
    net_credit = 0.0
    for strike, option_type, side in LEGS:
        row = lookup.get((strike, option_type))
        if not row:
            raise RuntimeError(f"Missing {strike} {option_type} in FYERS chain")
        price = quote(row, side)
        net_credit += -side * price
        symbols.append(row["symbol"])
        chosen.append({"action": "SELL" if side < 0 else "BUY", "strike": strike, "type": option_type, "symbol": row["symbol"], "price": price, "bid": row.get("bid"), "ask": row.get("ask"), "oi": row.get("oi"), "volume": row.get("volume"), "iv": (row.get("greeks") or {}).get("iv")})
    master = FyersFoMaster().lookup(symbols)
    lot_size = int(next(iter(master.values())).get("lot_size") or 0)
    if lot_size <= 0:
        raise RuntimeError("The contracts are absent from today's FYERS master.")
    width = 100.0
    max_loss = (width - net_credit) * lot_size
    breakevens = (23500 - net_credit, 23600 + net_credit)
    output = {
        "as_of": datetime.now(IST).isoformat(), "expiry": expiry, "spot": spot,
        "lot_size": lot_size, "legs": chosen,
        "net_credit_points": round(net_credit, 2),
        "max_profit_per_lot": round(net_credit * lot_size, 2),
        "max_loss_per_lot": round(max_loss, 2),
        "breakevens": [round(value, 2) for value in breakevens],
        "valid": net_credit > 0 and max_loss > 0,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
