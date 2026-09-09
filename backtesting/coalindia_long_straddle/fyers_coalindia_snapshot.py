#!/usr/bin/env python3
"""Read-only FYERS COALINDIA chart and ATM straddle evidence snapshot."""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sector_heatmap.fyers_execution import _current_client
from sector_heatmap.handoff import fetch_fyers_chain

SYMBOL = "NSE:COALINDIA-EQ"


def candle_summary(client, resolution: str, days: int):
    end = int(datetime.now(ZoneInfo("Asia/Kolkata")).timestamp())
    start = end - days * 86400
    response = client.history({"symbol": SYMBOL, "resolution": resolution,
        "date_format": "0", "range_from": str(start), "range_to": str(end), "cont_flag": "1"})
    rows = response.get("candles") or []
    closes = [float(row[4]) for row in rows]
    return {"status": response.get("s"), "bars": len(rows),
            "last_close": closes[-1] if closes else None,
            "change_pct": round((closes[-1] / closes[0] - 1) * 100, 2) if len(closes) > 1 else None}


def main():
    client = _current_client()
    quote = client.quotes({"symbols": SYMBOL})
    chain, expiry = fetch_fyers_chain(client, SYMBOL, strike_count=12)
    data = chain.get("data") or {}
    raw_rows = data.get("optionsChain") or data.get("optionschain") or []
    underlying_row = next((row for row in raw_rows if float(row.get("strike_price", -1)) < 0), {})
    spot = data.get("ltp") or data.get("underlyingValue") or data.get("underlying_value") or underlying_row.get("ltp")
    options = [row for row in raw_rows if str(row.get("option_type") or "").upper() in {"CE", "PE"}]
    strikes = []
    for row in options:
        strike = row.get("strike_price")
        if strike is not None:
            strikes.append(float(strike))
    atm = min(set(strikes), key=lambda strike: abs(strike - float(spot))) if spot and strikes else None
    legs = [row for row in options if atm is not None and float(row.get("strike_price", -1)) == atm]
    report = {
        "timestamp_ist": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"),
        "quote": quote,
        "expiry": expiry,
        "spot": spot,
        "atm_strike": atm,
        "atm_legs": legs,
        "chain_compact": [{key: row.get(key) for key in ("symbol", "strike_price", "option_type", "bid", "ask", "ltp", "oi", "oich", "volume", "greeks")} for row in options],
        "chain_rows": len(options),
        "chain_data_keys": list(data),
        "chain_first_row": options[0] if options else None,
        "chart": {"daily": candle_summary(client, "D", 70), "15m": candle_summary(client, "15", 10), "5m": candle_summary(client, "5", 5)},
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
