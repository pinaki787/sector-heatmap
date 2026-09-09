#!/usr/bin/env python3
"""SENSEX EMA-band midpoint signal runner.

Default mode is *dry-run*: it polls FYERS's SENSEX index candles and
prints/journals completed-bar BUY, SELL and matching EXIT signals without
submitting orders. ``--mode live`` additionally requires an explicit command
confirmation before any FYERS order can be submitted. ``--mode forward-test``
replays a CSV locally without broker calls.

The entry/exit rules intentionally mirror ema_band_midpoint_alerts.pine:
previous candle body-crosses the EMA edge; the following completed candle
confirms direction and opens beyond the prior full-range midpoint; an open
position exits on a completed close inside the EMA band.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
SENSEX_SYMBOL = "BSE:SENSEX-INDEX"
SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass
class Signal:
    timestamp: str
    event: str
    close: float
    ema_high: float
    ema_low: float
    position_after: int
    mode: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "live", "forward-test"), default="dry-run")
    parser.add_argument("--interval", choices=("1", "5", "15", "25", "60"), default="5")
    parser.add_argument("--ema-length", type=int, default=21)
    parser.add_argument("--session", default="0915-1515", help="Set empty value to disable")
    parser.add_argument("--cooldown-bars", type=int, default=0)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--once", action="store_true", help="Evaluate available completed bars once")
    parser.add_argument("--csv", type=Path, help="OHLCV CSV required for --mode forward-test")
    parser.add_argument("--state-file", type=Path, default=SCRIPT_DIR / ".private" / "sensex_ema_live_state.json")
    parser.add_argument("--journal", type=Path, default=SCRIPT_DIR / ".private" / "sensex_ema_live_journal.csv")
    parser.add_argument("--lots", type=int, default=1, help="FYERS option lots per signal")
    parser.add_argument("--product-type", choices=("INTRADAY", "MARGIN"), default="INTRADAY")
    parser.add_argument("--confirm-live", default="DISABLE_FYERS_LIVE_ORDERS", help="Required exact value ENABLE_FYERS_LIVE_ORDERS with --mode live")
    args = parser.parse_args()
    if args.ema_length < 1 or args.cooldown_bars < 0 or args.poll_seconds < 1:
        parser.error("EMA length must be >=1; cooldown >=0; poll seconds >=1")
    if args.mode == "forward-test" and not args.csv:
        parser.error("--csv is required with --mode forward-test")
    if args.lots < 1:
        parser.error("--lots must be positive")
    if args.mode == "live" and args.confirm_live != "ENABLE_FYERS_LIVE_ORDERS":
        parser.error("Live orders require --confirm-live ENABLE_FYERS_LIVE_ORDERS")
    return args


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    time_column = next((name for name in ("timestamp", "datetime", "date", "time") if name in frame.columns), None)
    if not time_column:
        raise ValueError("OHLCV data needs timestamp/datetime/date/time column")
    frame[time_column] = pd.to_datetime(frame[time_column], errors="coerce")
    frame = frame.set_index(time_column)
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize(IST)
    else:
        frame.index = frame.index.tz_convert(IST)
    needed = ["open", "high", "low", "close"]
    missing = [name for name in needed if name not in frame.columns]
    if missing:
        raise ValueError(f"Missing OHLC columns: {missing}")
    return frame[needed].apply(pd.to_numeric, errors="coerce").dropna().sort_index().loc[lambda x: ~x.index.duplicated(keep="last")]


def fetch_live_bars(interval: str) -> pd.DataFrame:
    """Fetch SENSEX index candles from FYERS; credentials are environment-only."""
    client = fyers_client()
    today = date.today()
    payload = {
        "symbol": SENSEX_SYMBOL,
        "resolution": interval,
        "date_format": "1",
        "range_from": str(today - timedelta(days=7)),
        "range_to": str(today),
        "cont_flag": "1",
    }
    response = None
    for attempt in range(3):
        response = client.history(payload)
        if isinstance(response, dict) and response.get("s") == "ok":
            break
        # FYERS intermittently returns an otherwise unexplained HTTP 400 for
        # BSE index history. Retry only this idempotent read with short backoff.
        if attempt < 2:
            time.sleep(attempt + 1)
    if not isinstance(response, dict) or response.get("s") != "ok":
        message = response.get("message") if isinstance(response, dict) else repr(response)
        raise RuntimeError(f"FYERS candle request failed after 3 read-only attempts for {SENSEX_SYMBOL} ({interval}-minute): {message or 'unknown response'}")
    rows = response.get("candles") or []
    if not rows:
        raise RuntimeError("FYERS returned no SENSEX candles")
    frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True).dt.tz_convert(IST)
    return normalize_ohlcv(frame)


def fyers_client():
    """Use Sector Heatmap's cached OAuth token, with environment overrides."""
    try:
        from sector_heatmap.config import load_config
        shared = load_config()
    except (ImportError, OSError, ValueError):
        shared = {}
    token = os.getenv("FYERS_ACCESS_TOKEN") or shared.get("FYERS_ACCESS_TOKEN", "")
    app_id = os.getenv("FYERS_APP_ID") or shared.get("FYERS_APP_ID", "")
    if ":" in token:
        token_app_id, token = token.split(":", 1)
        app_id = app_id or token_app_id
    if not app_id or not token:
        raise RuntimeError("No reusable Sector Heatmap FYERS token was found. Sign in through the dashboard or set FYERS_APP_ID and FYERS_ACCESS_TOKEN.")
    try:
        from fyers_apiv3 import fyersModel
    except ImportError as exc:
        raise RuntimeError("Install FYERS SDK first: python -m pip install fyers-apiv3") from exc
    return fyersModel.FyersModel(client_id=app_id, token=token)


def resolve_atm_option(signal: Signal, lots: int) -> tuple[str, int]:
    """Resolve the nearest-expiry, current ATM CE for BUY or PE for SELL."""
    option_type = "CE" if signal.event == "BUY" else "PE"
    client = fyers_client()
    discovery = client.optionchain({"symbol": SENSEX_SYMBOL, "strikecount": 1, "timestamp": ""})
    expiry = (discovery.get("data", {}).get("expiryData") or [None])[0]
    if discovery.get("s") != "ok" or not expiry:
        raise RuntimeError("FYERS returned no current SENSEX option expiry; no order submitted.")
    chain = client.optionchain({"symbol": SENSEX_SYMBOL, "strikecount": 2, "timestamp": str(expiry["expiry"])})
    rows = chain.get("data", {}).get("optionsChain") or []
    spot_row = next((row for row in rows if row.get("option_type") == ""), None)
    candidates = [row for row in rows if row.get("option_type") == option_type and row.get("symbol")]
    if chain.get("s") != "ok" or not spot_row or not candidates:
        raise RuntimeError("FYERS returned no eligible ATM SENSEX option contract; no order submitted.")
    spot = float(spot_row["ltp"])
    contract = min(candidates, key=lambda row: abs(float(row["strike_price"]) - spot))
    lot_size = validate_fyers_symbol(str(contract["symbol"]), 0)
    return str(contract["symbol"]), lot_size * lots


def submit_fyers_order(signal: Signal, trade_symbol: str, quantity: int, args: argparse.Namespace) -> None:
    """Submit a validated order for a signal from live mode."""
    side = 1 if signal.event in {"BUY", "EXIT SELL"} else -1
    payload = {"symbol": trade_symbol, "qty": quantity, "type": 2, "side": side,
               "productType": args.product_type, "limitPrice": 0, "stopPrice": 0,
               "disclosedQty": 0, "validity": "DAY", "offlineOrder": False,
               "stopLoss": 0, "takeProfit": 0, "orderTag": "emabandsensex", "isSliceOrder": False}
    validate_fyers_symbol(trade_symbol, quantity)
    client = fyers_client()
    quote = client.quotes({"symbols": trade_symbol})
    if quote.get("s") != "ok" or not quote.get("d"):
        raise RuntimeError(f"FYERS did not validate the tradable symbol: {quote.get('message', quote)}")
    response = client.place_order(payload)
    if response.get("s") != "ok":
        raise RuntimeError(f"FYERS order was rejected or uncertain: {response}")
    print(json.dumps({"fyers_order": response, "signal": asdict(signal)}, separators=(",", ":")))


def validate_fyers_symbol(symbol: str, quantity: int) -> int:
    """Fail closed unless the exact daily FYERS derivative master lists the contract."""
    try:
        with urlopen("https://public.fyers.in/sym_details/BSE_FO.csv", timeout=30) as response:
            rows = csv.reader(io.TextIOWrapper(response, encoding="utf-8"))
            record = next((row for row in rows if len(row) >= 18 and row[9] == symbol), None)
    except OSError as exc:
        raise RuntimeError("Could not validate against today's FYERS BFO symbol master; no order submitted.") from exc
    if not record:
        raise RuntimeError("Trade symbol is absent from today's FYERS BFO symbol master; no order submitted.")
    lot_size = int(float(record[3]))
    if lot_size < 1 or (quantity and quantity % lot_size):
        raise RuntimeError(f"Quantity {quantity} is not a whole FYERS lot (lot size {lot_size}); no order submitted.")
    return lot_size


def manage_signal(signal: Signal, state: dict, args: argparse.Namespace) -> dict:
    """Map entries to ATM options and exit the exact contract opened by this runner."""
    active = state.get("active_contract")
    active_valid = isinstance(active, dict) and bool(active.get("symbol")) and int(active.get("quantity") or 0) > 0
    if signal.event in {"BUY", "SELL"}:
        if active_valid:
            raise RuntimeError("A local option contract is already active; no duplicate entry submitted.")
        if active:
            raise RuntimeError("The local active-contract record is incomplete; reconcile FYERS positions before a new entry.")
        symbol, quantity = resolve_atm_option(signal, args.lots)
        submit_fyers_order(signal, symbol, quantity, args)
        return {"active_contract": {"symbol": symbol, "quantity": quantity, "entry": signal.event}}
    if not active_valid:
        print(json.dumps({
            "execution": "EXIT_SKIPPED_NO_TRACKED_CONTRACT",
            "signal": asdict(signal),
            "message": "No FYERS order submitted because this runner has no locally tracked entry contract."
        }, separators=(",", ":")))
        return {"active_contract": None}
    submit_fyers_order(signal, str(active["symbol"]), int(active["quantity"]), args)
    return {"active_contract": None}


def report_live_pnl(state: dict) -> None:
    """Print the current FYERS position and broker-reported P&L."""
    active = state.get("active_contract")
    if not active:
        return
    client = fyers_client()
    response = client.positions()
    if response.get("s") != "ok":
        raise RuntimeError(f"FYERS position request failed: {response.get('message', response)}")
    position = next((item for item in response.get("netPositions", []) if item.get("symbol") == active["symbol"]), None)
    if not position:
        print(json.dumps({"fyers_position": {"symbol": active["symbol"], "status": "not found"}}, separators=(",", ":")))
        return
    print(json.dumps({
        "fyers_position": {
            "symbol": position.get("symbol"),
            "quantity": position.get("netQty"),
            "average_price": position.get("netAvg"),
            "ltp": position.get("ltp"),
            "realized_pnl": position.get("realized_profit"),
            "unrealized_pnl": position.get("unrealized_profit"),
            "pnl": position.get("pl"),
        }
    }, separators=(",", ":")))


def session_pass(timestamp: pd.Timestamp, session: str) -> bool:
    if not session:
        return True
    start, end = session.split("-", 1)
    now = timestamp.strftime("%H%M")
    return start <= now <= end


def build_events(frame: pd.DataFrame, ema_length: int, session: str, cooldown: int, mode: str) -> list[Signal]:
    frame = frame.copy()
    frame["ema_high"] = frame.high.ewm(span=ema_length, adjust=False).mean()
    frame["ema_low"] = frame.low.ewm(span=ema_length, adjust=False).mean()
    position, last_long_exit, last_short_exit = 0, None, None
    events: list[Signal] = []
    for i in range(1, len(frame)):
        current, prior = frame.iloc[i], frame.iloc[i - 1]
        timestamp = frame.index[i]
        inside = current.ema_low <= current.close <= current.ema_high
        event = None
        if position == 1 and inside:
            position, last_long_exit, event = 0, i, "EXIT BUY"
        elif position == -1 and inside:
            position, last_short_exit, event = 0, i, "EXIT SELL"
        elif position == 0 and session_pass(timestamp, session):
            midpoint = (prior.high + prior.low) / 2.0
            long_cross = prior.open <= prior.ema_high and prior.close > prior.ema_high
            short_cross = prior.open >= prior.ema_low and prior.close < prior.ema_low
            long_cooldown_ok = last_long_exit is None or i - last_long_exit > cooldown
            short_cooldown_ok = last_short_exit is None or i - last_short_exit > cooldown
            if long_cross and current.close > current.open and current.open > midpoint and long_cooldown_ok:
                position, event = 1, "BUY"
            elif short_cross and current.close < current.open and current.open < midpoint and short_cooldown_ok:
                position, event = -1, "SELL"
        if event:
            events.append(Signal(timestamp.isoformat(), event, float(current.close), float(current.ema_high), float(current.ema_low), position, mode))
    return events


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def record(signals: list[Signal], journal: Path) -> None:
    journal.parent.mkdir(parents=True, exist_ok=True)
    fresh_file = not journal.exists()
    with journal.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(signals[0])))
        if fresh_file:
            writer.writeheader()
        writer.writerows(asdict(signal) for signal in signals)
    for signal in signals:
        print(json.dumps(asdict(signal), separators=(",", ":")))


def main() -> int:
    args = parse_args()
    if args.mode == "forward-test":
        signals = build_events(normalize_ohlcv(pd.read_csv(args.csv)), args.ema_length, args.session, args.cooldown_bars, args.mode)
        if signals:
            record(signals, args.journal)
        print(f"forward-test complete: {len(signals)} signals; no broker calls were made")
        return 0
    while True:
        frame = fetch_live_bars(args.interval)
        signals = build_events(frame.iloc[:-1], args.ema_length, args.session, args.cooldown_bars, args.mode)
        state = load_state(args.state_file)
        last_seen = state.get("last_signal_timestamp")
        if last_seen is None:
            newest = signals[-1].timestamp if signals else frame.index[-2].isoformat()
            args.state_file.parent.mkdir(parents=True, exist_ok=True)
            args.state_file.write_text(json.dumps({"last_signal_timestamp": newest}, indent=2) + "\n")
            print(f"{datetime.now(IST).isoformat()} initialized at {newest}; historical signals were not traded")
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
            continue
        unseen = [signal for signal in signals if signal.timestamp > (last_seen or "")]
        if unseen:
            record(unseen, args.journal)
            if args.mode == "live":
                for signal in unseen:
                    state.update(manage_signal(signal, state, args))
            args.state_file.parent.mkdir(parents=True, exist_ok=True)
            state["last_signal_timestamp"] = unseen[-1].timestamp
            args.state_file.write_text(json.dumps(state, indent=2) + "\n")
        else:
            print(f"{datetime.now(IST).isoformat()} no new completed-bar signal")
        report_live_pnl(state)
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
