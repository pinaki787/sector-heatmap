#!/usr/bin/env python3
"""Read-only FYERS ATM option statistics for selected NSE stock-option underlyings."""
from __future__ import annotations

from datetime import datetime
import json
from zoneinfo import ZoneInfo

from sector_heatmap.fyers_execution import _current_client
from sector_heatmap.handoff import fetch_fyers_chain

SYMBOLS = ("NSE:NTPC-EQ", "NSE:LT-EQ", "NSE:POWERGRID-EQ", "NSE:NIFTY50-INDEX")


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    client = _current_client()
    report = {"timestamp_ist": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"), "underlyings": {}}
    for symbol in SYMBOLS:
        chain, expiry = fetch_fyers_chain(client, symbol, strike_count=15)
        rows = (chain.get("data") or {}).get("optionsChain") or []
        base = next((row for row in rows if number(row.get("strike_price")) == -1), {})
        spot = number(base.get("ltp"))
        options = [row for row in rows if str(row.get("option_type") or "").upper() in {"CE", "PE"}]
        strikes = sorted({number(row.get("strike_price")) for row in options if number(row.get("strike_price")) is not None})
        atm = min(strikes, key=lambda value: abs(value - spot)) if spot and strikes else None
        legs = [row for row in options if number(row.get("strike_price")) == atm]
        def compact(row):
            greek = row.get("greeks") or {}
            return {key: row.get(key) for key in ("symbol", "option_type", "strike_price", "bid", "ask", "ltp", "oi", "oich", "volume")} | {"iv": greek.get("iv"), "delta": greek.get("delta"), "theta": greek.get("theta")}
        call_oi = sum(number(row.get("oi")) or 0 for row in options if row.get("option_type") == "CE")
        put_oi = sum(number(row.get("oi")) or 0 for row in options if row.get("option_type") == "PE")
        report["underlyings"][symbol] = {"expiry": expiry, "spot": spot, "atm_strike": atm,
            "atm_legs": [compact(row) for row in legs], "total_call_oi": call_oi, "total_put_oi": put_oi,
            "pcr_oi": round(put_oi / call_oi, 2) if call_oi else None,
            "near_atm": [compact(row) for row in options if atm is not None and abs(number(row.get("strike_price")) - atm) <= (strikes[1]-strikes[0] if len(strikes)>1 else 0)],
            "chain_compact": [compact(row) for row in options]}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
