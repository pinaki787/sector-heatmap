#!/usr/bin/env python3
"""NIFTY conditional bear-call-spread runner.

Default mode is read-only. ``--live`` submits both legs through FYERS' basket
endpoint only after the completed-candle and fresh-market safeguards pass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time as clock_time
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from sector_heatmap.fyers_execution import _current_client, _number, _orders, _positions, available_funds
from sector_heatmap.handoff import FyersFoMaster, fetch_fyers_chain

SYMBOL = "NSE:NIFTY50-INDEX"
BREAKDOWN, INVALIDATION = 23_465.0, 23_525.0
DEFAULT_SHORT_STRIKE, DEFAULT_LONG_STRIKE = 23_600.0, 23_700.0
MAX_RISK_RUPEES = 5_000.0
OUTFILE, IST = Path(__file__).with_name("signal.json"), ZoneInfo("Asia/Kolkata")


def completed_candle(client):
    now = datetime.now(IST)
    end = int(now.timestamp())
    response = client.history({"symbol": SYMBOL, "resolution": "15", "date_format": "0",
                               "range_from": str(end - 3 * 86400), "range_to": str(end), "cont_flag": "1"})
    closed = [row for row in (response.get("candles") or []) if int(row[0]) + 900 <= end]
    if not closed:
        raise RuntimeError("No completed NIFTY 15-minute candle is available from FYERS.")
    row = closed[-1]
    return {"timestamp": int(row[0]), "close": float(row[4])}


def require_market_open():
    now = datetime.now(IST)
    if now.weekday() >= 5 or not (clock_time(9, 15) <= now.time().replace(tzinfo=None) <= clock_time(15, 20)):
        raise RuntimeError("Live basket placement is allowed only during the NSE session before 15:20 IST.")


def exact_call(rows, strike):
    row = next((item for item in rows if item.get("option_type") == "CE" and float(item.get("strike_price", -1)) == strike), None)
    if not row:
        raise RuntimeError(f"FYERS did not return the {strike:.0f} CE in the selected expiry.")
    bid, ask = _number(row.get("bid")), _number(row.get("ask"))
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        raise RuntimeError(f"The {strike:.0f} CE has no valid two-sided market.")
    return row


def build_preview(client, lots, short_strike, long_strike):
    chain, expiry = fetch_fyers_chain(client, SYMBOL, strike_count=30)
    rows = (chain.get("data") or {}).get("optionsChain") or []
    short, long = exact_call(rows, short_strike), exact_call(rows, long_strike)
    master = FyersFoMaster().lookup([short.get("symbol"), long.get("symbol")])
    if len(master) != 2:
        raise RuntimeError("A basket leg is absent from today's FYERS F&O symbol master.")
    if any(str(master[leg["symbol"]]["expiry_epoch"]) != str(expiry.get("expiry")) for leg in (short, long)):
        raise RuntimeError("The basket contracts do not match the fresh FYERS expiry.")
    lot_sizes = {master[short["symbol"]]["lot_size"], master[long["symbol"]]["lot_size"]}
    if len(lot_sizes) != 1:
        raise RuntimeError("FYERS returned inconsistent lot sizes for the two basket legs.")
    lot_size = lot_sizes.pop()
    quantity = lot_size * lots
    credit = round(float(short["bid"]) - float(long["ask"]), 2)
    if credit <= 0 or credit >= long_strike - short_strike:
        raise RuntimeError("Fresh FYERS quotes no longer form a positive, defined-risk credit spread.")
    max_loss = round((long_strike - short_strike - credit) * quantity, 2)
    if max_loss > MAX_RISK_RUPEES:
        raise RuntimeError(f"Maximum basket risk ₹{max_loss:.2f} exceeds the hard ₹{MAX_RISK_RUPEES:.0f} cap.")
    return {"expiry": expiry.get("date"), "lots": lots, "lot_size": lot_size, "quantity": quantity,
            "credit_points": credit, "maximum_profit_rupees": round(credit * quantity, 2),
            "maximum_loss_rupees": max_loss, "breakeven": round(short_strike + credit, 2),
            "order_tag": f"NIFTYBCC{int(short_strike)}", "orders": [
                {"action": "BUY", "symbol": long["symbol"], "strike": long_strike, "limit_price": float(long["ask"])},
                {"action": "SELL", "symbol": short["symbol"], "strike": short_strike, "limit_price": float(short["bid"])}]}


def reject_duplicate_exposure(client, preview):
    symbols = {item["symbol"] for item in preview["orders"]}
    if any(item.get("symbol") in symbols and (_number(item.get("netQty", item.get("net_qty", 0)), 0) or 0) != 0 for item in _positions(client.positions())):
        raise RuntimeError("An existing position already uses a basket leg; reconcile it before another entry.")
    if any(item.get("symbol") in symbols and item.get("status") in {4, 6} for item in _orders(client.orderbook())):
        raise RuntimeError("A pending FYERS order already uses a basket leg; reconcile it before another entry.")


def basket_payload(preview):
    return [{"symbol": leg["symbol"], "qty": preview["quantity"], "type": 1,
             "side": 1 if leg["action"] == "BUY" else -1, "productType": "MARGIN",
             "limitPrice": leg["limit_price"], "stopPrice": 0, "validity": "DAY",
             "disclosedQty": 0, "offlineOrder": False, "orderTag": preview["order_tag"]}
            for leg in preview["orders"]]


def basket_margin(client, orders):
    """Get FYERS' fresh basket-margin result; failure blocks a live order."""
    response = requests.post(
        "https://api-t1.fyers.in/api/v3/multiorder/margin",
        headers={"Authorization": client.header, "Content-Type": "application/json"},
        json={"data": orders}, timeout=15,
    )
    response.raise_for_status()
    body = response.json()
    if not _ok(body):
        raise RuntimeError(f"FYERS basket-margin check failed: {body.get('message', 'unknown error')}")
    data = body.get("data") or body
    required = _number(data.get("margin_total", data.get("margin_new_order")))
    if required is None or required <= 0:
        raise RuntimeError("FYERS did not return a positive required basket margin.")
    return round(required, 2)


def main():
    parser = argparse.ArgumentParser(description="Monitor or submit the conditional NIFTY bear-call basket.")
    parser.add_argument("--live", action="store_true", help="Submit the validated FYERS two-leg basket if entry is ready.")
    parser.add_argument("--lots", type=int, default=1, help="Whole exchange lots; default: 1.")
    parser.add_argument("--short-strike", type=float, default=DEFAULT_SHORT_STRIKE, help="Short-call strike; default: 23600.")
    parser.add_argument("--long-strike", type=float, default=DEFAULT_LONG_STRIKE, help="Protective long-call strike; default: 23700.")
    args = parser.parse_args()
    if args.lots < 1:
        raise SystemExit("--lots must be at least 1.")
    if args.long_strike <= args.short_strike:
        raise SystemExit("--long-strike must be above --short-strike for a defined-risk bear call spread.")
    client, candle = _current_client(), None
    candle = completed_candle(client)
    close = candle["close"]
    report = {"timestamp_ist": datetime.now(IST).isoformat(timespec="seconds"),
              "mode": "LIVE_BASKET_REQUESTED" if args.live else "DRY_RUN_MONITOR",
              "nifty_completed_15m_close": close, "completed_candle_epoch": candle["timestamp"],
              "breakdown": BREAKDOWN, "invalidation": INVALIDATION, "lots": args.lots,
              "short_strike": args.short_strike, "long_strike": args.long_strike,
              "status": "WATCHING", "preview": None, "order_response": None}
    if close >= INVALIDATION:
        report.update(status="INVALIDATED", note="Completed candle is at or above the invalidation level.")
    elif close >= BREAKDOWN:
        report["note"] = "No completed breakdown below the entry trigger yet."
    else:
        preview = build_preview(client, args.lots, args.short_strike, args.long_strike)
        reject_duplicate_exposure(client, preview)
        preview["required_margin_rupees"] = basket_margin(client, basket_payload(preview))
        report.update(status="ENTRY_READY", preview=preview, note="Completed breakdown and fresh validated basket pricing.")
        if args.live:
            require_market_open()
            if available_funds(client.funds()) < preview["required_margin_rupees"]:
                raise RuntimeError("FYERS available funds do not cover the required basket margin.")
            report["order_response"] = client.place_basket_orders(basket_payload(preview))
            report.update(status="BASKET_SUBMITTED_RECONCILE_IN_FYERS",
                          note="FYERS received the basket request. Reconcile both legs in FYERS; no automatic retry occurs.")
    OUTFILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
