"""
LIVE NIFTY straddle trader on Fyers — implements the final validated config
from this session's backtesting:
  - Entry: NIFTY realized vol (annualized, 5-min log returns, 1-day rolling
    window) below its 50th percentile over the trailing 20 trading days.
  - Strike: ATM (nearest 50-point strike to spot).
  - Expiry: nearest weekly (Tuesday, per NSE's Sep-2025 schedule change).
  - Default profit exit: Supertrend (7,3), armed after +10 combined-premium points.
  - Hard stop: 15 points on combined CE+PE premium in every exit mode.
  - Optional fixed-target exit: 30 points.
  - Exit: forced square-off by 15:20 IST same day (5 min buffer before the
    15:25 cutoff used in backtesting, for order-placement latency).
  - Re-entry: allowed same day once flat, but only after the next completed
    five-minute candle close; one position at a time.

===========================================================================
READ THIS BEFORE RUNNING
===========================================================================
- DRY_RUN = True by default. In this mode NOTHING is sent to Fyers for
  order placement — every entry/exit is only logged and simulated using
  live LTP. You must deliberately set DRY_RUN = True to place real orders.
- Every number in the backtest that produced this config used SIMULATED
  Black-Scholes premiums (realized vol as an IV proxy), not real historical
  option fills. Real slippage, spreads, and actual traded IV WILL differ
  from what the backtest showed. Run this in DRY_RUN for a meaningful
  stretch and compare simulated fills to what you'd have actually gotten
  before trusting it with capital.
- This script polls once every POLL_SECONDS. It is not a low-latency or
  production-grade execution system: network hiccups, partial fills, and
  Fyers API errors are logged but not exhaustively handled. Review the
  logs regularly if you run this unattended.
- Requires: pip install fyers-apiv3 pandas numpy
===========================================================================
"""

import os
import json
import time
import argparse
import datetime as dt
import csv
import io
import ssl
from urllib.request import urlopen
import numpy as np
import pandas as pd
import certifi
from fyers_apiv3 import fyersModel

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

DRY_RUN = True   # default: forward-test (paper) mode. Overridden by -live flag at runtime.

FYERS_APP_ID = os.environ.get("FYERS_APP_ID", "")          # e.g. "XXXXXX-100"
FYERS_ACCESS_TOKEN = os.environ.get("FYERS_ACCESS_TOKEN", "")

NUM_LOTS = 1

VOL_PERCENTILE = 50
VOL_LOOKBACK_DAYS = 20
REALIZED_VOL_WINDOW_BARS = 78    # ~1 trading day of 5-min bars

STOPLOSS_POINTS = 15.0
TARGET_POINTS = 30.0
SUPER_TREND_TRAIL = True
SUPER_TREND_PERIOD = 7
SUPER_TREND_MULTIPLIER = 3.0
SUPER_TREND_ACTIVATION_POINTS = 10.0
EOD_SQUARE_OFF_TIME = dt.time(15, 20)   # 5-min buffer before the 15:25 backtest cutoff
ENTRY_WINDOW_START_TIME = dt.time(9, 15)
ENTRY_WINDOW_END_TIME = dt.time(11, 30)
MAX_REENTRIES_PER_DAY = 1
REENTRY_CANDLE_MINUTES = 5

MARKET_OPEN_TIME = dt.time(9, 15)
MARKET_CLOSE_TIME = dt.time(15, 30)
CLOSED_MARKET_POLL_SECONDS = 300   # check less frequently while market is shut

POLL_SECONDS = 30
RUNTIME_DIR = os.path.abspath(os.path.expanduser(os.environ.get('NIFTY_STRADDLE_RUNTIME_DIR', os.path.dirname(os.path.abspath(__file__)))))
LOG_FILE = os.path.join(RUNTIME_DIR, "live_trade_log.csv")
STATE_FILE = os.path.join(RUNTIME_DIR, "live_position_state.json")
CHART_FILE = os.path.join(RUNTIME_DIR, "live_premium_chart.json")
ENTRY_GUARD_FILE = os.path.join(RUNTIME_DIR, "long_straddle_entry_guard.json")
REENTRY_GUARD_FILE = os.path.join(RUNTIME_DIR, "long_straddle_reentry_guard.json")


def log(msg):
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def is_market_open(now=None):
    """
    NSE trading hours check: Mon-Fri, 09:15-15:30 IST. Does NOT account for
    exchange holidays (no holiday calendar wired in) -- on a market holiday
    that falls on a weekday, this will incorrectly report the market as
    open. Cross-check against the actual NSE holiday calendar if running
    unattended around holidays.
    """
    now = now or dt.datetime.now()
    if now.weekday() >= 5:   # Saturday=5, Sunday=6
        return False
    return MARKET_OPEN_TIME <= now.time() <= MARKET_CLOSE_TIME


def _entry_count_today():
    try:
        with open(ENTRY_GUARD_FILE) as handle:
            state = json.load(handle)
        return int(state.get("entries", 0)) if state.get("date") == dt.date.today().isoformat() else 0
    except (OSError, ValueError, TypeError):
        return 0


def _record_entry():
    temporary = ENTRY_GUARD_FILE + ".tmp"
    with open(temporary, "w") as handle:
        json.dump({"date": dt.date.today().isoformat(), "entries": _entry_count_today() + 1}, handle)
    os.replace(temporary, ENTRY_GUARD_FILE)


def _next_five_minute_close(after):
    """Return the next five-minute candle close strictly after ``after``."""
    rounded = after.replace(second=0, microsecond=0)
    return rounded + dt.timedelta(minutes=REENTRY_CANDLE_MINUTES - rounded.minute % REENTRY_CANDLE_MINUTES)


def record_reentry_wait(exited_at):
    """Persist the re-entry gate so a restart cannot bypass the candle check."""
    temporary = REENTRY_GUARD_FILE + ".tmp"
    with open(temporary, "w") as handle:
        json.dump({
            "date": exited_at.date().isoformat(),
            "exit_time": exited_at.isoformat(),
            "eligible_after": _next_five_minute_close(exited_at).isoformat(),
        }, handle)
    os.replace(temporary, REENTRY_GUARD_FILE)


def reentry_allowed(now):
    """Require a fresh completed five-minute candle before a same-day retry."""
    if _entry_count_today() == 0:
        return True, ""
    try:
        with open(REENTRY_GUARD_FILE) as handle:
            state = json.load(handle)
        if state.get("date") != now.date().isoformat():
            return False, "missing same-day five-minute re-entry checkpoint"
        eligible_after = dt.datetime.fromisoformat(state["eligible_after"])
        if now < eligible_after:
            return False, (
                "waiting for completed five-minute candle close "
                f"at {eligible_after:%H:%M} IST before re-entry"
            )
        return True, ""
    except (OSError, ValueError, TypeError, KeyError):
        return False, "missing valid five-minute re-entry checkpoint"


def entry_allowed(now):
    if not ENTRY_WINDOW_START_TIME <= now.time() <= ENTRY_WINDOW_END_TIME:
        return False, f"outside entry window {ENTRY_WINDOW_START_TIME:%H:%M}-{ENTRY_WINDOW_END_TIME:%H:%M} IST"
    if _entry_count_today() >= MAX_REENTRIES_PER_DAY + 1:
        return False, f"daily re-entry cap reached ({MAX_REENTRIES_PER_DAY} re-entry)"
    allowed, reason = reentry_allowed(now)
    if not allowed:
        return False, reason
    return True, ""


def _load_fyers_credentials():
    """Load app_id/access_token from env vars, falling back to
    ~/.fyers/token.json (the saved Fyers login token for this account)."""
    app_id = FYERS_APP_ID
    token = FYERS_ACCESS_TOKEN
    if app_id and token:
        return app_id, token
    token_path = os.path.expanduser("~/.fyers/token.json")
    if os.path.exists(token_path):
        with open(token_path) as f:
            data = json.load(f)
        return data.get("app_id", app_id), data.get("access_token", token)
    raise RuntimeError(
        "No Fyers credentials found. Set FYERS_APP_ID / FYERS_ACCESS_TOKEN "
        "env vars, or ensure ~/.fyers/token.json exists with "
        "{'app_id':..., 'access_token':...}"
    )


APP_ID, ACCESS_TOKEN = _load_fyers_credentials()
fyers = fyersModel.FyersModel(client_id=APP_ID, token=ACCESS_TOKEN, is_async=False, log_path="")


def get_spot_ltp():
    resp = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX"})
    return resp["d"][0]["v"]["lp"]


def get_nearest_weekly_expiry_and_atm_symbols(spot):
    """
    Uses the live option chain (rather than hand-computing the expiry date)
    to get the exact nearest-expiry ATM CE/PE symbols Fyers currently lists
    -- this avoids errors from holidays or exchange calendar quirks that a
    manually-computed 'next Tuesday' rule could get wrong.
    Returns (atm_strike, ce_symbol, pe_symbol, expiry_date_str).
    """
    resp = fyers.optionchain({"symbol": "NSE:NIFTY50-INDEX", "strikecount": 3, "timestamp": ""})
    if resp.get("s") != "ok":
        raise RuntimeError(f"Option chain fetch failed: {resp}")

    expiry_list = resp["data"].get("expiryData", [])
    expiry_date_str = expiry_list[0]["date"] if expiry_list else "unknown"

    chain = resp["data"]["optionsChain"]
    # symbols look like NSE:NIFTY2690823700CE -- the nearest expiry is
    # whichever set of strikes appears first for this default (near-month) call
    atm_strike = round(spot / 50) * 50
    ce_symbol = pe_symbol = None
    for row in chain:
        if row.get("strike_price") == atm_strike:
            if row.get("option_type") == "CE":
                ce_symbol = row["symbol"]
            elif row.get("option_type") == "PE":
                pe_symbol = row["symbol"]
    if not ce_symbol or not pe_symbol:
        raise RuntimeError(f"Could not find ATM {atm_strike} CE/PE in option chain response")
    return atm_strike, ce_symbol, pe_symbol, expiry_date_str


def resolve_fyers_lot_size(symbol):
    """Read the current NSE F&O master; never trust a hard-coded lot size."""
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(
            "https://public.fyers.in/sym_details/NSE_FO.csv", timeout=30, context=ssl_context
        ) as response:
            rows = csv.reader(io.TextIOWrapper(response, encoding="utf-8"))
            record = next((row for row in rows if len(row) >= 18 and row[9] == symbol), None)
    except OSError as exc:
        raise RuntimeError("Could not fetch the current FYERS NSE F&O master; no order submitted.") from exc
    if not record:
        raise RuntimeError(f"{symbol} is absent from today's FYERS NSE F&O master; no order submitted.")
    lot_size = int(float(record[3]))
    if lot_size < 1:
        raise RuntimeError(f"FYERS reported an invalid lot size for {symbol}; no order submitted.")
    return lot_size


def resolve_pair_quantity(ce_symbol, pe_symbol):
    """Resolve one current whole lot for both legs before placing either order."""
    ce_lot_size = resolve_fyers_lot_size(ce_symbol)
    pe_lot_size = resolve_fyers_lot_size(pe_symbol)
    if ce_lot_size != pe_lot_size:
        raise RuntimeError(
            f"ATM leg lot-size mismatch: CE={ce_lot_size}, PE={pe_lot_size}; no order submitted."
        )
    return ce_lot_size * NUM_LOTS, ce_lot_size


def get_ltp(symbol):
    resp = fyers.quotes({"symbols": symbol})
    return resp["d"][0]["v"]["lp"]


def get_recent_5min_candles(lookback_days):
    """Fetch recent NIFTY 5-min candles from Fyers for the realized-vol calc."""
    to_date = dt.date.today()
    from_date = to_date - dt.timedelta(days=lookback_days + 10)  # pad for weekends/holidays
    resp = fyers.history({
        "symbol": "NSE:NIFTY50-INDEX", "resolution": "5", "date_format": "1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to": to_date.strftime("%Y-%m-%d"),
        "cont_flag": "1",
    })
    if resp.get("s") != "ok":
        raise RuntimeError(f"History fetch failed: {resp}")
    df = pd.DataFrame(resp["candles"], columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    return df.set_index("timestamp").sort_index()


def get_symbol_5min_candles(symbol, lookback_days=10):
    """Fetch recent five-minute option candles."""
    to_date = dt.date.today()
    from_date = to_date - dt.timedelta(days=lookback_days)
    resp = fyers.history({
        "symbol": symbol, "resolution": "5", "date_format": "1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to": to_date.strftime("%Y-%m-%d"), "cont_flag": "1",
    })
    if resp.get("s") != "ok":
        raise RuntimeError(f"History fetch failed for {symbol}: {resp}")
    df = pd.DataFrame(resp["candles"], columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    return df.set_index("timestamp").sort_index()


def compute_supertrend(df, period, multiplier):
    """Return a Wilder-ATR Supertrend line and bullish state."""
    high, low, close = df["high"], df["low"], df["close"]
    previous_close = close.shift(1)
    true_range = pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    midpoint = (high + low) / 2
    basic_upper, basic_lower = midpoint + multiplier * atr, midpoint - multiplier * atr
    final_upper, final_lower = basic_upper.copy(), basic_lower.copy()
    supertrend = pd.Series(np.nan, index=df.index, dtype=float)
    bullish = pd.Series(True, index=df.index, dtype=bool)
    for i in range(1, len(df)):
        if pd.isna(atr.iloc[i]):
            continue
        if pd.isna(final_upper.iloc[i - 1]):
            final_upper.iloc[i - 1], final_lower.iloc[i - 1] = basic_upper.iloc[i], basic_lower.iloc[i]
        if basic_upper.iloc[i] >= final_upper.iloc[i - 1] and close.iloc[i - 1] <= final_upper.iloc[i - 1]:
            final_upper.iloc[i] = final_upper.iloc[i - 1]
        if basic_lower.iloc[i] <= final_lower.iloc[i - 1] and close.iloc[i - 1] >= final_lower.iloc[i - 1]:
            final_lower.iloc[i] = final_lower.iloc[i - 1]
        previous_trend = bullish.iloc[i - 1]
        bullish.iloc[i] = False if previous_trend and close.iloc[i] < final_lower.iloc[i] else True if not previous_trend and close.iloc[i] > final_upper.iloc[i] else previous_trend
        supertrend.iloc[i] = final_lower.iloc[i] if bullish.iloc[i] else final_upper.iloc[i]
    return supertrend, bullish


def get_combined_premium_chart(ce_symbol, pe_symbol, now=None):
    """Build synthetic CE+PE OHLC candles using completed five-minute bars only."""
    ce = get_symbol_5min_candles(ce_symbol).add_suffix("_ce")
    pe = get_symbol_5min_candles(pe_symbol).add_suffix("_pe")
    joined = ce.join(pe, how="inner")
    combined = pd.DataFrame(index=joined.index)
    for field in ("open", "high", "low", "close"):
        combined[field] = joined[f"{field}_ce"] + joined[f"{field}_pe"]
    current_time = pd.Timestamp(now or dt.datetime.now(), tz="Asia/Kolkata")
    completed = combined[combined.index + pd.Timedelta(minutes=5) <= current_time]
    line, bullish = compute_supertrend(completed, SUPER_TREND_PERIOD, SUPER_TREND_MULTIPLIER)
    return [{
        "timestamp": timestamp.isoformat(),
        "open": round(float(row["open"]), 2), "high": round(float(row["high"]), 2),
        "low": round(float(row["low"]), 2), "close": round(float(row["close"]), 2),
        "supertrend": None if pd.isna(line.loc[timestamp]) else round(float(line.loc[timestamp]), 2),
        "bullish": bool(bullish.loc[timestamp]),
    } for timestamp, row in completed.tail(48).iterrows()]


def get_combined_premium_supertrend(ce_symbol, pe_symbol, now=None, candles=None):
    candles = candles if candles is not None else get_combined_premium_chart(ce_symbol, pe_symbol, now)
    if len(candles) < SUPER_TREND_PERIOD + 1 or candles[-1]["supertrend"] is None:
        raise RuntimeError("Completed combined-premium Supertrend is unavailable")
    latest = candles[-1]
    return {"timestamp": latest["timestamp"], "close": latest["close"], "line": latest["supertrend"], "bullish": latest["bullish"]}


def compute_current_vol_signal(now=None):
    """
    Same realized-vol + percentile-rank logic as the backtest: today's
    rolling realized vol vs its trailing 20-trading-day distribution.
    Returns (signal_is_compressed: bool, current_vol: float).
    """
    df = get_recent_5min_candles(VOL_LOOKBACK_DAYS)
    current_time = pd.Timestamp(now or dt.datetime.now(), tz="Asia/Kolkata")
    df = df[df.index + pd.Timedelta(minutes=REENTRY_CANDLE_MINUTES) <= current_time]
    log_ret = np.log(df["close"] / df["close"].shift(1))
    bars_per_year = 252 * 78
    rv = log_ret.rolling(REALIZED_VOL_WINDOW_BARS).std() * np.sqrt(bars_per_year)
    rv = rv.dropna()
    if len(rv) < REALIZED_VOL_WINDOW_BARS:
        return False, np.nan
    threshold = np.percentile(rv.iloc[-VOL_LOOKBACK_DAYS * 78:], VOL_PERCENTILE)
    current_vol = rv.iloc[-1]
    return bool(current_vol < threshold), current_vol


def place_order(symbol, qty, side):
    """side: 1 = buy, -1 = sell. Market order. Respects DRY_RUN."""
    if DRY_RUN:
        log(f"  [DRY RUN] Would place {'BUY' if side==1 else 'SELL'} order: "
            f"{symbol} qty={qty} (market)")
        return {"s": "ok", "id": "DRYRUN", "dry_run": True}

    order = {
        "symbol": symbol, "qty": qty, "type": 2,   # 2 = market order
        "side": side, "productType": "INTRADAY", "limitPrice": 0, "stopPrice": 0,
        "validity": "DAY", "disclosedQty": 0, "offlineOrder": False,
    }
    resp = fyers.place_order(order)
    log(f"  Order response for {symbol} ({'BUY' if side==1 else 'SELL'} {qty}): {resp}")
    if resp.get("s") != "ok":
        raise RuntimeError(f"Order placement FAILED for {symbol}: {resp}")
    return resp


def log_trade(row):
    df_row = pd.DataFrame([row])
    header = not os.path.exists(LOG_FILE)
    df_row.to_csv(LOG_FILE, mode="a", header=header, index=False)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, default=str, indent=2)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return None


def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def save_premium_chart(state, now, ce_ltp, pe_ltp, candles, supertrend_armed, error=None):
    premium_now = ce_ltp + pe_ltp
    quantity = int(state["quantity"])
    payload = {
        "updated_at": now.astimezone().isoformat(),
        "ce_symbol": state["ce_symbol"], "pe_symbol": state["pe_symbol"],
        "ce_ltp": round(ce_ltp, 2), "pe_ltp": round(pe_ltp, 2),
        "premium_entry": round(float(state["premium_entry"]), 2),
        "activation_premium": round(float(state["premium_entry"]) + SUPER_TREND_ACTIVATION_POINTS, 2),
        "premium_now": round(premium_now, 2),
        "pnl_points": round(premium_now - float(state["premium_entry"]), 2),
        "pnl_rupees": round((premium_now - float(state["premium_entry"])) * quantity, 2),
        "quantity": quantity, "lots": NUM_LOTS, "supertrend_armed": bool(supertrend_armed),
        "candles": candles, "error": error,
    }
    temporary = CHART_FILE + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(payload, handle, indent=2)
    os.replace(temporary, CHART_FILE)


def clear_premium_chart():
    if os.path.exists(CHART_FILE):
        os.remove(CHART_FILE)


def enter_position():
    spot = get_spot_ltp()
    atm_strike, ce_symbol, pe_symbol, expiry_date_str = get_nearest_weekly_expiry_and_atm_symbols(spot)
    quantity, lot_size = resolve_pair_quantity(ce_symbol, pe_symbol)
    ce_ltp = get_ltp(ce_symbol)
    pe_ltp = get_ltp(pe_symbol)
    premium_entry = ce_ltp + pe_ltp

    log(f"ENTRY: spot={spot:.1f}  strike={atm_strike}  expiry={expiry_date_str}  "
        f"CE={ce_symbol}@{ce_ltp:.1f}  PE={pe_symbol}@{pe_ltp:.1f}  "
        f"combined_premium={premium_entry:.1f} pts  "
        f"qty={quantity} ({NUM_LOTS} x lot_size={lot_size})")

    ce_order = place_order(ce_symbol, quantity, side=1)
    pe_order = place_order(pe_symbol, quantity, side=1)
    ce_order_id = ce_order.get("id")
    pe_order_id = pe_order.get("id")

    log(f"  Order IDs -- CE: {ce_order_id}   PE: {pe_order_id}")

    state = {
        "entry_time": dt.datetime.now().isoformat(),
        "spot_entry": spot, "strike": atm_strike, "expiry": expiry_date_str,
        "ce_symbol": ce_symbol, "pe_symbol": pe_symbol,
        "quantity": quantity, "lot_size": lot_size,
        "premium_entry": premium_entry,
        "ce_entry_order_id": ce_order_id, "pe_entry_order_id": pe_order_id,
    }
    save_state(state)
    _record_entry()
    return state


def exit_position(state, reason):
    quantity = state.get("quantity")
    if not isinstance(quantity, int) or quantity < 1:
        raise RuntimeError(
            "Position state has no recorded quantity. Refusing an automated exit; "
            "reconcile the broker position manually."
        )
    ce_ltp = get_ltp(state["ce_symbol"])
    pe_ltp = get_ltp(state["pe_symbol"])
    premium_exit = ce_ltp + pe_ltp
    pnl_points = premium_exit - state["premium_entry"]
    pnl_rupees = pnl_points * quantity

    log(f"EXIT ({reason}): premium_exit={premium_exit:.1f} "
        f"pnl_points={pnl_points:+.1f} pnl_rupees={pnl_rupees:+,.0f}")

    ce_exit_order = place_order(state["ce_symbol"], quantity, side=-1)
    pe_exit_order = place_order(state["pe_symbol"], quantity, side=-1)
    ce_exit_order_id = ce_exit_order.get("id")
    pe_exit_order_id = pe_exit_order.get("id")

    log(f"  Exit order IDs -- CE: {ce_exit_order_id}   PE: {pe_exit_order_id}")

    exited_at = dt.datetime.now()
    log_trade({
        "entry_time": state["entry_time"], "exit_time": exited_at.isoformat(),
        "strike": state["strike"], "expiry": state.get("expiry"),
        "ce_symbol": state["ce_symbol"], "pe_symbol": state["pe_symbol"],
        "premium_entry": state["premium_entry"], "premium_exit": premium_exit,
        "pnl_points": pnl_points, "pnl_rupees": pnl_rupees, "exit_reason": reason,
        "quantity": quantity,
        "ce_entry_order_id": state.get("ce_entry_order_id"), "pe_entry_order_id": state.get("pe_entry_order_id"),
        "ce_exit_order_id": ce_exit_order_id, "pe_exit_order_id": pe_exit_order_id,
        "dry_run": DRY_RUN,
    })
    clear_state()
    clear_premium_chart()
    record_reentry_wait(exited_at)


def main_loop():
    exit_mode = (f"Supertrend({SUPER_TREND_PERIOD},{SUPER_TREND_MULTIPLIER:g}) after "
                 f"+{SUPER_TREND_ACTIVATION_POINTS:g}; no fixed target") if SUPER_TREND_TRAIL else f"fixed target +{TARGET_POINTS:g}"
    log(f"Starting live straddle trader. DRY_RUN={DRY_RUN}. "
        f"Config: vol_pctile={VOL_PERCENTILE}, SL={STOPLOSS_POINTS}pts, "
        f"exit={exit_mode}, lots={NUM_LOTS}, entry_window={ENTRY_WINDOW_START_TIME:%H:%M}-{ENTRY_WINDOW_END_TIME:%H:%M} IST, "
        f"max_reentries={MAX_REENTRIES_PER_DAY}, reentry_check={REENTRY_CANDLE_MINUTES}-minute close "
        "(quantity is resolved from the FYERS master before entry)")
    if not DRY_RUN:
        log("*** LIVE MODE: REAL ORDERS WILL BE PLACED. ***")

    while True:
        now = dt.datetime.now()

        if not is_market_open(now):
            log(f"Market closed (now={now.strftime('%a %H:%M')}). Waiting... "
                f"(no entries/exits evaluated while closed)")
            time.sleep(CLOSED_MARKET_POLL_SECONDS)
            continue

        state = load_state()

        if state is None:
            # not in a position -- check entry conditions
            if now.time() >= EOD_SQUARE_OFF_TIME:
                pass  # too late in the day to open a new position
            else:
                allowed, reason = entry_allowed(now)
                if not allowed:
                    log(f"ENTRY BLOCKED: {reason}. Existing-position management remains active.")
                else:
                    try:
                        is_compressed, current_vol = compute_current_vol_signal(now)
                        log(f"Vol check: compressed={is_compressed} current_vol={current_vol:.1%}")
                        if is_compressed:
                            enter_position()
                    except Exception as e:
                        log(f"ERROR checking entry / entering: {e}")
        else:
            # in a position -- check exit conditions
            try:
                quantity = state.get("quantity")
                if not isinstance(quantity, int) or quantity < 1:
                    raise RuntimeError(
                        "Position state has no recorded quantity. Refusing automated exit; "
                        "reconcile the broker position manually."
                    )
                ce_ltp = get_ltp(state["ce_symbol"])
                pe_ltp = get_ltp(state["pe_symbol"])
                premium_now = ce_ltp + pe_ltp
                pnl_points = premium_now - state["premium_entry"]
                pnl_rupees = pnl_points * quantity
                supertrend_armed = (
                    state.get("supertrend_armed") is True
                    and state.get("supertrend_activation_points") == SUPER_TREND_ACTIVATION_POINTS
                )
                if SUPER_TREND_TRAIL and not supertrend_armed and pnl_points >= SUPER_TREND_ACTIVATION_POINTS:
                    supertrend_armed = True
                    state["supertrend_armed"] = True
                    state["supertrend_armed_time"] = now.isoformat()
                    state["supertrend_activation_points"] = SUPER_TREND_ACTIVATION_POINTS
                    save_state(state)
                    log(f"Supertrend profit trail armed at {pnl_points:+.1f} points")
                chart_candles, chart_error, supertrend_status = [], None, None
                try:
                    chart_candles = get_combined_premium_chart(state["ce_symbol"], state["pe_symbol"], now)
                    if SUPER_TREND_TRAIL and supertrend_armed:
                        supertrend_status = get_combined_premium_supertrend(state["ce_symbol"], state["pe_symbol"], now, chart_candles)
                        armed_time = pd.Timestamp(state["supertrend_armed_time"])
                        if armed_time.tzinfo is None:
                            armed_time = armed_time.tz_localize("Asia/Kolkata")
                        supertrend_status["eligible"] = pd.Timestamp(supertrend_status["timestamp"]) > armed_time
                except Exception as chart_exception:
                    chart_error = str(chart_exception)
                save_premium_chart(state, now, ce_ltp, pe_ltp, chart_candles, supertrend_armed, chart_error)
                log(
                    f"OPEN POSITION | strike={state['strike']}  expiry={state.get('expiry', 'unknown')}  "
                    f"CE={state['ce_symbol']}@{ce_ltp:.1f}  PE={state['pe_symbol']}@{pe_ltp:.1f}  "
                    f"entry_premium={state['premium_entry']:.1f}  current_premium={premium_now:.1f}  "
                    f"P&L={pnl_points:+.1f} pts (Rs {pnl_rupees:+,.0f})  "
                    f"[SL={-STOPLOSS_POINTS:.0f} {'ST 7,3' if SUPER_TREND_TRAIL else f'TGT={TARGET_POINTS:.0f}'}]"
                )

                if pnl_points <= -STOPLOSS_POINTS:
                    exit_position(state, "stoploss")
                elif (SUPER_TREND_TRAIL and supertrend_status is not None
                      and supertrend_status.get("eligible") and not supertrend_status["bullish"]):
                    exit_position(state, "supertrend_trail")
                elif not SUPER_TREND_TRAIL and pnl_points >= TARGET_POINTS:
                    exit_position(state, "target")
                elif now.time() >= EOD_SQUARE_OFF_TIME:
                    exit_position(state, "eod")
            except Exception as e:
                log(f"ERROR checking exit: {e}")

        time.sleep(POLL_SECONDS)


def validate_current_contracts():
    """Read-only preflight for the exact ATM contracts selected right now."""
    spot = get_spot_ltp()
    atm_strike, ce_symbol, pe_symbol, expiry_date_str = get_nearest_weekly_expiry_and_atm_symbols(spot)
    quantity, lot_size = resolve_pair_quantity(ce_symbol, pe_symbol)
    ce_ltp = get_ltp(ce_symbol)
    pe_ltp = get_ltp(pe_symbol)
    print(json.dumps({
        "validation": "ok",
        "spot": spot,
        "strike": atm_strike,
        "expiry": expiry_date_str,
        "ce_symbol": ce_symbol,
        "pe_symbol": pe_symbol,
        "ce_ltp": ce_ltp,
        "pe_ltp": pe_ltp,
        "lot_size": lot_size,
        "lots": NUM_LOTS,
        "quantity": quantity,
        "stoploss_points": STOPLOSS_POINTS,
        "target_points": TARGET_POINTS,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NIFTY vol-compression straddle trader (Fyers). "
                     "Default mode is forward-test / paper trading (no real orders)."
    )
    parser.add_argument(
        "-live", "--live", dest="live", action="store_true",
        help="Place REAL orders on your Fyers account instead of forward-testing.",
    )
    parser.add_argument(
        "--validate-contracts", action="store_true",
        help="Read-only check of the currently selected ATM contract lot size and quotes.",
    )
    parser.add_argument(
        "--lots", type=int, default=None,
        help=f"Number of lots per option leg (default: {NUM_LOTS}).",
    )
    parser.add_argument(
        "--stoploss", type=float, default=None,
        help=f"Combined-premium stop loss in points (default: {STOPLOSS_POINTS:g}).",
    )
    parser.add_argument(
        "--target", type=float, default=None,
        help=f"Combined-premium target in points (default: {TARGET_POINTS:g}).",
    )
    parser.add_argument("--entry-start", default=ENTRY_WINDOW_START_TIME.strftime("%H:%M"), help="New-entry window start in IST (HH:MM).")
    parser.add_argument("--entry-end", default=ENTRY_WINDOW_END_TIME.strftime("%H:%M"), help="New-entry window end in IST (HH:MM).")
    parser.add_argument(
        "--supertrend-trail", dest="exit_mode", action="store_const", const="supertrend",
        help=(f"After +{SUPER_TREND_ACTIVATION_POINTS:g} points, trail completed combined-premium candles "
              f"with Supertrend({SUPER_TREND_PERIOD},{SUPER_TREND_MULTIPLIER:g}); no fixed target; "
              "the configured hard stop remains active."),
    )
    parser.add_argument(
        "--fixed-target", dest="exit_mode", action="store_const", const="fixed",
        help=f"Use the {TARGET_POINTS:g}-point target and {STOPLOSS_POINTS:g}-point hard stop.",
    )
    parser.set_defaults(exit_mode="supertrend")
    args = parser.parse_args()

    def parse_entry_time(value, flag):
        try:
            return dt.datetime.strptime(value, "%H:%M").time()
        except ValueError:
            parser.error(f"{flag} must use HH:MM IST")

    ENTRY_WINDOW_START_TIME = parse_entry_time(args.entry_start, "--entry-start")
    ENTRY_WINDOW_END_TIME = parse_entry_time(args.entry_end, "--entry-end")
    if ENTRY_WINDOW_START_TIME > ENTRY_WINDOW_END_TIME:
        parser.error("--entry-start must be no later than --entry-end")

    if args.live and args.validate_contracts:
        parser.error("--live and --validate-contracts cannot be used together")

    if args.lots is not None:
        if args.lots < 1:
            parser.error("--lots must be a positive whole number")
        NUM_LOTS = args.lots
    if args.stoploss is not None:
        if args.stoploss <= 0:
            parser.error("--stoploss must be greater than zero")
        STOPLOSS_POINTS = args.stoploss
    if args.target is not None:
        if args.target <= 0:
            parser.error("--target must be greater than zero")
        TARGET_POINTS = args.target
    SUPER_TREND_TRAIL = args.exit_mode == "supertrend"

    if args.validate_contracts:
        DRY_RUN = True
        validate_current_contracts()
        raise SystemExit(0)

    if args.live:
        DRY_RUN = True
        print("=" * 70)
        print("LIVE MODE REQUESTED: this will place REAL orders with REAL money.")
        print("=" * 70)
        confirm = input("Type 'YES' (all caps) to proceed live, anything else to abort: ")
        if confirm != "YES":
            print("Aborted. No orders will be placed.")
            raise SystemExit(0)
    else:
        DRY_RUN = True
        print("Running in forward-test (paper) mode. Use -live to place real orders.")

    main_loop()
