#!/usr/bin/env python3
"""Read-only FYERS NIFTY expiry snapshot. This module never places orders."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sector_heatmap.config import load_config
from sector_heatmap.handoff import FyersFoMaster


IST = ZoneInfo("Asia/Kolkata")
SYMBOL = "NSE:NIFTY50-INDEX"


def _client():
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("A current FYERS token is required.")
    app_id, access_token = token.split(":", 1)
    return fyersModel.FyersModel(client_id=app_id, token=access_token)


def _completed(candles, minutes, now):
    boundary = int(now.timestamp()) // (minutes * 60) * (minutes * 60)
    return [row for row in candles if int(row[0]) < boundary]


def _ema(values, period):
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def _spread(rows, spot, direction, lot_size):
    option_type = "CE" if direction == "BULLISH" else "PE"
    legs = sorted((row for row in rows if row.get("option_type") == option_type), key=lambda row: float(row["strike_price"]))
    strikes = [float(row["strike_price"]) for row in legs]
    atm = min(strikes, key=lambda strike: abs(strike - spot))
    long_leg = next(row for row in legs if float(row["strike_price"]) == atm)
    candidates = [row for row in legs if float(row["strike_price"]) > atm] if direction == "BULLISH" else [row for row in legs if float(row["strike_price"]) < atm]
    if not candidates:
        return None
    short_leg = min(candidates, key=lambda row: abs(float(row["strike_price"]) - atm))
    debit = float(long_leg.get("ask") or 0) - float(short_leg.get("bid") or 0)
    width = abs(float(short_leg["strike_price"]) - atm)
    if debit <= 0 or debit >= width:
        return None
    return {
        "label": "Bull call debit spread" if direction == "BULLISH" else "Bear put debit spread",
        "buy": {"symbol": long_leg["symbol"], "strike": atm, "ask": long_leg.get("ask")},
        "sell": {"symbol": short_leg["symbol"], "strike": float(short_leg["strike_price"]), "bid": short_leg.get("bid")},
        "net_debit_points": round(debit, 2),
        "max_loss_per_lot": round(debit * lot_size, 2),
        "max_profit_per_lot": round((width - debit) * lot_size, 2),
        "reward_to_risk": round((width - debit) / debit, 2),
        "lot_size": lot_size,
    }


def main():
    now = datetime.now(IST)
    client = _client()
    day = now.date().isoformat()
    history = client.history({"symbol": SYMBOL, "resolution": "15", "date_format": "1", "range_from": day, "range_to": day, "cont_flag": "1"})
    if history.get("s") != "ok":
        raise RuntimeError(history.get("message") or "FYERS history unavailable")
    candles = _completed(history.get("candles") or [], 15, now)
    if len(candles) < 2:
        raise RuntimeError("Insufficient completed 15-minute candles.")
    discovery = client.optionchain({"symbol": SYMBOL, "strikecount": 1, "timestamp": ""})
    expiry = (discovery.get("data", {}).get("expiryData") or [None])[0]
    if not expiry:
        raise RuntimeError("FYERS returned no NIFTY expiry.")
    chain = client.optionchain({"symbol": SYMBOL, "strikecount": 15, "timestamp": str(expiry["expiry"]), "greeks": "1"})
    if chain.get("s") != "ok":
        raise RuntimeError(chain.get("message") or "FYERS option chain unavailable")
    rows = chain.get("data", {}).get("optionsChain") or []
    spot_row = next(row for row in rows if row.get("option_type") == "")
    spot = float(spot_row["ltp"])
    closes = [float(row[4]) for row in candles]
    latest = candles[-1]
    opening_high = max(float(row[2]) for row in candles[:2])
    opening_low = min(float(row[3]) for row in candles[:2])
    ema20 = _ema(closes, min(20, len(closes)))
    direction = "BULLISH" if closes[-1] > opening_high and closes[-1] > ema20 else "BEARISH" if closes[-1] < opening_low and closes[-1] < ema20 else "NEUTRAL"
    calls = [row for row in rows if row.get("option_type") == "CE"]
    puts = [row for row in rows if row.get("option_type") == "PE"]
    strikes = sorted({float(row["strike_price"]) for row in calls})
    atm = min(strikes, key=lambda strike: abs(strike - spot))
    atm_call = next(row for row in calls if float(row["strike_price"]) == atm)
    atm_put = next(row for row in puts if float(row["strike_price"]) == atm)
    call_oi = sum(float(row.get("oi") or 0) for row in calls)
    put_oi = sum(float(row.get("oi") or 0) for row in puts)
    option_symbols = [row.get("symbol") for row in calls + puts if row.get("symbol")]
    master = FyersFoMaster().lookup(option_symbols)
    atm_contract = master.get(atm_call.get("symbol"))
    if not atm_contract or not atm_contract.get("lot_size"):
        raise RuntimeError("The exact ATM contract is absent from today's FYERS symbol master.")
    lot_size = int(atm_contract["lot_size"])
    result = {
        "as_of": now.isoformat(),
        "expiry": expiry,
        "is_expiry_day": datetime.strptime(expiry["date"], "%d-%m-%Y").date() == now.date(),
        "spot": spot,
        "completed_15m": {"timestamp": datetime.fromtimestamp(latest[0], IST).isoformat(), "close": closes[-1], "ema20": round(ema20, 2), "opening_range_high": opening_high, "opening_range_low": opening_low},
        "signal": direction,
        "atm": atm,
        "atm_straddle": round(float(atm_call.get("ask") or atm_call.get("ltp") or 0) + float(atm_put.get("ask") or atm_put.get("ltp") or 0), 2),
        "pcr": round(put_oi / call_oi, 2) if call_oi else None,
        "max_call_oi_strike": max(calls, key=lambda row: float(row.get("oi") or 0))["strike_price"],
        "max_put_oi_strike": max(puts, key=lambda row: float(row.get("oi") or 0))["strike_price"],
        "watchlist_spreads": {
            "bullish_breakout": _spread(rows, spot, "BULLISH", lot_size),
            "bearish_breakdown": _spread(rows, spot, "BEARISH", lot_size),
        },
        "defined_risk_candidate": _spread(rows, spot, direction, lot_size) if direction != "NEUTRAL" else None,
        "decision": "WAIT_FOR_COMPLETED_15M_BREAK" if direction == "NEUTRAL" else "CANDIDATE_ONLY_REQUIRES_FRESH_CONFIRMATION",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
