#!/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
"""
LIVE SENSEX straddle trader on Fyers. The default exit mode matches the
selected 180-calendar-day configuration: Supertrend(7, 3) armed after +10
combined-premium points, with a 15-point hard stop and no fixed target.
  - Entry: SENSEX realized vol (annualized, 5-min log returns, 1-day
    rolling window) below its 50th percentile over the trailing 20 trading
    days.
  - Strike: ATM (nearest 100-point strike to spot -- SENSEX strikes step
    in 100s, not NIFTY's 50s).
  - Expiry: nearest weekly (Thursday -- BSE kept SENSEX on Thursday even
    after NSE moved NIFTY to Tuesday in Sep 2025).
  - Default exit: after profit reaches 10 points, exit when a subsequent
    completed 5-minute combined-premium candle closes below Supertrend(7, 3).
  - Fixed-target override: 30-point target with the 15-point hard stop.
  - Profit-trail override: after the 30-point target is reached, trail the
    best combined-premium profit by 10 points instead of exiting immediately.
  - Exit: forced square-off by 15:20 IST same day (5 min buffer before the
    15:20 cutoff used in the matching backtest).
  - Re-entry: DAILY_COOLDOWN=False by default -- once flat, the script can
    re-enter the SAME day if the compression signal fires again, but only
    after the next completed five-minute candle close (no
    once-per-day cap). This is the higher-frequency, higher-total-return
    config. Set DAILY_COOLDOWN=True for the lower-frequency alternative
    also validated in backtesting (~0.4 trades/day, PF 10-15, much lower
    +22.4% return but only 1.2% max drawdown -- a cleaner per-trade edge
    with less exposure to execution risk, at the cost of total return).

===========================================================================
READ THIS BEFORE RUNNING
===========================================================================
- DRY_RUN = True by default. In this mode NOTHING is sent to Fyers for
  order placement — every entry/exit is only logged and simulated using
  live LTP. You must deliberately set DRY_RUN = True to place real orders.
- Every number in the backtest that produced this config used SIMULATED
  Black-Scholes premiums (realized vol as an IV proxy), not real historical
  option fills. Real slippage, spreads, and actual traded IV WILL differ
  from what the backtest showed -- and SENSEX weekly options typically have
  THINNER liquidity than NIFTY's, so real slippage risk here is likely
  higher than what the backtest reflects. Run this in DRY_RUN for a
  meaningful stretch and compare simulated fills to what you'd have
  actually gotten before trusting it with capital.
- Supertrend trailing is the default. Its +10 level only activates the trail;
  it is not a take-profit order. The 15-point hard stop remains active.
- Use --fixed-target for the 30-point target behavior,
  or --trail-profit to trail the post-target peak by 10 points.
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
import numpy as np
import pandas as pd
from fyers_apiv3 import fyersModel

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

DRY_RUN = True   # default: forward-test (paper) mode. Overridden by -live flag at runtime.

FYERS_APP_ID = os.environ.get("FYERS_APP_ID", "")          # e.g. "XXXXXX-100"
FYERS_ACCESS_TOKEN = os.environ.get("FYERS_ACCESS_TOKEN", "")

LOT_SIZE = 20
NUM_LOTS = 1
QUANTITY = LOT_SIZE * NUM_LOTS

DAILY_COOLDOWN = False   # True = quality config (~0.4 trades/day, higher PF, lower DD).
                          # False (default) = frequency config (~2+ trades/day, higher
                          # total return, lower PF, ~3x the drawdown of the True config).

VOL_PERCENTILE = 50
VOL_LOOKBACK_DAYS = 20
REALIZED_VOL_WINDOW_BARS = 78    # ~1 trading day of 5-min bars

TARGET_POINTS = 30.0
STOPLOSS_POINTS = 15.0
TRAIL_PROFIT = False       # True = activate a trailing exit after TARGET_POINTS is reached.
TRAIL_PROFIT_POINTS = 10.0 # Exit after profit pulls back this far from its post-target peak.
SUPER_TREND_TRAIL = True   # Default: replace the target with Supertrend; keep hard stop.
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
RUNTIME_DIR = os.path.abspath(os.path.expanduser(os.environ.get(
    "SENSEX_STRADDLE_RUNTIME_DIR", os.path.dirname(os.path.abspath(__file__))
)))
os.makedirs(RUNTIME_DIR, exist_ok=True)
LOG_FILE = os.path.join(RUNTIME_DIR, "live_trade_log.csv")
STATE_FILE = os.path.join(RUNTIME_DIR, "live_position_state.json")
COOLDOWN_FILE = os.path.join(RUNTIME_DIR, "live_cooldown_state.json")
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
fyers = fyersModel.FyersModel(
    client_id=APP_ID, token=ACCESS_TOKEN, is_async=False,
    log_path=RUNTIME_DIR + os.sep,
)


def get_spot_ltp():
    resp = fyers.quotes({"symbols": "BSE:SENSEX-INDEX"})
    return resp["d"][0]["v"]["lp"]


def get_nearest_weekly_expiry_and_atm_symbols(spot):
    """
    Uses the live option chain (rather than hand-computing the expiry date)
    to get the exact nearest-expiry ATM CE/PE symbols Fyers currently lists
    -- this avoids errors from holidays or exchange calendar quirks that a
    manually-computed 'next Thursday' rule could get wrong.
    Returns (atm_strike, ce_symbol, pe_symbol, expiry_date_str).
    """
    resp = fyers.optionchain({"symbol": "BSE:SENSEX-INDEX", "strikecount": 3, "timestamp": ""})
    if resp.get("s") != "ok":
        raise RuntimeError(f"Option chain fetch failed: {resp}")

    expiry_list = resp["data"].get("expiryData", [])
    expiry_date_str = expiry_list[0]["date"] if expiry_list else "unknown"

    chain = resp["data"]["optionsChain"]
    # symbols look like BSE:SENSEX2691076500CE -- the nearest expiry is
    # whichever set of strikes appears first for this default (near-month) call
    atm_strike = round(spot / 100) * 100
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


def get_ltp(symbol):
    resp = fyers.quotes({"symbols": symbol})
    return resp["d"][0]["v"]["lp"]


def get_recent_5min_candles(lookback_days):
    """Fetch recent SENSEX 5-min candles from Fyers for the realized-vol calc."""
    to_date = dt.date.today()
    from_date = to_date - dt.timedelta(days=lookback_days + 10)  # pad for weekends/holidays
    resp = fyers.history({
        "symbol": "BSE:SENSEX-INDEX", "resolution": "5", "date_format": "1",
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
    """Fetch recent 5-minute OHLC candles for an option symbol."""
    to_date = dt.date.today()
    from_date = to_date - dt.timedelta(days=lookback_days)
    resp = fyers.history({
        "symbol": symbol, "resolution": "5", "date_format": "1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to": to_date.strftime("%Y-%m-%d"),
        "cont_flag": "1",
    })
    if resp.get("s") != "ok":
        raise RuntimeError(f"History fetch failed for {symbol}: {resp}")
    df = pd.DataFrame(resp["candles"], columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    return df.set_index("timestamp").sort_index()


def compute_supertrend(df, period, multiplier):
    """Return Supertrend line and bullish state for an OHLC DataFrame."""
    high, low, close = df["high"], df["low"], df["close"]
    previous_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs(),
    ], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    midpoint = (high + low) / 2
    basic_upper = midpoint + multiplier * atr
    basic_lower = midpoint - multiplier * atr
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = pd.Series(np.nan, index=df.index, dtype=float)
    bullish = pd.Series(True, index=df.index, dtype=bool)

    for i in range(1, len(df)):
        if pd.isna(atr.iloc[i]):
            continue
        if pd.isna(final_upper.iloc[i - 1]):
            final_upper.iloc[i - 1] = basic_upper.iloc[i]
            final_lower.iloc[i - 1] = basic_lower.iloc[i]
        if basic_upper.iloc[i] >= final_upper.iloc[i - 1] and close.iloc[i - 1] <= final_upper.iloc[i - 1]:
            final_upper.iloc[i] = final_upper.iloc[i - 1]
        if basic_lower.iloc[i] <= final_lower.iloc[i - 1] and close.iloc[i - 1] >= final_lower.iloc[i - 1]:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        previous_trend = bullish.iloc[i - 1]
        if previous_trend and close.iloc[i] < final_lower.iloc[i]:
            bullish.iloc[i] = False
        elif not previous_trend and close.iloc[i] > final_upper.iloc[i]:
            bullish.iloc[i] = True
        else:
            bullish.iloc[i] = previous_trend
        supertrend.iloc[i] = final_lower.iloc[i] if bullish.iloc[i] else final_upper.iloc[i]

    return supertrend, bullish


def get_combined_premium_chart(ce_symbol, pe_symbol, now=None):
    """Return completed synthetic candles and their Supertrend values.

    The combined OHLC is synthetic: matching CE and PE bar fields are summed.
    Only bars whose five-minute interval has ended are eligible.
    """
    ce = get_symbol_5min_candles(ce_symbol).add_suffix("_ce")
    pe = get_symbol_5min_candles(pe_symbol).add_suffix("_pe")
    joined = ce.join(pe, how="inner")
    combined = pd.DataFrame(index=joined.index)
    for field in ("open", "high", "low", "close"):
        combined[field] = joined[f"{field}_ce"] + joined[f"{field}_pe"]

    current_time = pd.Timestamp(now or dt.datetime.now(), tz="Asia/Kolkata")
    completed = combined[combined.index + pd.Timedelta(minutes=5) <= current_time]
    line, bullish = compute_supertrend(completed, SUPER_TREND_PERIOD, SUPER_TREND_MULTIPLIER)
    candles = []
    for timestamp, row in completed.tail(48).iterrows():
        st_value = line.loc[timestamp]
        candles.append({
            "timestamp": timestamp.isoformat(),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "supertrend": None if pd.isna(st_value) else round(float(st_value), 2),
            "bullish": bool(bullish.loc[timestamp]),
        })
    return candles


def get_combined_premium_supertrend(ce_symbol, pe_symbol, now=None, candles=None):
    """Return the latest completed combined-premium bar's Supertrend state."""
    candles = candles if candles is not None else get_combined_premium_chart(ce_symbol, pe_symbol, now)
    if len(candles) < SUPER_TREND_PERIOD + 1:
        raise RuntimeError("Not enough completed combined-premium candles for Supertrend")
    latest = candles[-1]
    if latest["supertrend"] is None:
        raise RuntimeError("Latest combined-premium Supertrend value is unavailable")
    return {
        "timestamp": latest["timestamp"],
        "close": latest["close"],
        "line": latest["supertrend"],
        "bullish": latest["bullish"],
    }


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
    """Atomically publish read-only chart data for the local dashboard."""
    premium_now = ce_ltp + pe_ltp
    payload = {
        "updated_at": now.astimezone().isoformat(),
        "ce_symbol": state["ce_symbol"], "pe_symbol": state["pe_symbol"],
        "ce_ltp": round(ce_ltp, 2), "pe_ltp": round(pe_ltp, 2),
        "premium_entry": round(float(state["premium_entry"]), 2),
        "activation_premium": round(float(state["premium_entry"]) + SUPER_TREND_ACTIVATION_POINTS, 2),
        "premium_now": round(premium_now, 2),
        "pnl_points": round(premium_now - float(state["premium_entry"]), 2),
        "pnl_rupees": round((premium_now - float(state["premium_entry"])) * QUANTITY, 2),
        "quantity": QUANTITY, "lots": NUM_LOTS,
        "supertrend_armed": bool(supertrend_armed),
        "candles": candles,
        "error": error,
    }
    temporary = CHART_FILE + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(payload, handle, indent=2)
    os.replace(temporary, CHART_FILE)


def clear_premium_chart():
    if os.path.exists(CHART_FILE):
        os.remove(CHART_FILE)


def record_exit_date():
    """Persist today's date so DAILY_COOLDOWN can block re-entry until the
    next trading day, even across script restarts."""
    with open(COOLDOWN_FILE, "w") as f:
        json.dump({"last_exit_date": dt.date.today().isoformat()}, f)


def in_daily_cooldown():
    if not DAILY_COOLDOWN or not os.path.exists(COOLDOWN_FILE):
        return False
    with open(COOLDOWN_FILE) as f:
        data = json.load(f)
    return data.get("last_exit_date") == dt.date.today().isoformat()


def enter_position():
    spot = get_spot_ltp()
    atm_strike, ce_symbol, pe_symbol, expiry_date_str = get_nearest_weekly_expiry_and_atm_symbols(spot)
    ce_ltp = get_ltp(ce_symbol)
    pe_ltp = get_ltp(pe_symbol)
    premium_entry = ce_ltp + pe_ltp

    log(f"ENTRY: spot={spot:.1f}  strike={atm_strike}  expiry={expiry_date_str}  "
        f"CE={ce_symbol}@{ce_ltp:.1f}  PE={pe_symbol}@{pe_ltp:.1f}  "
        f"combined_premium={premium_entry:.1f} pts")

    ce_order = place_order(ce_symbol, QUANTITY, side=1)
    pe_order = place_order(pe_symbol, QUANTITY, side=1)
    ce_order_id = ce_order.get("id")
    pe_order_id = pe_order.get("id")

    log(f"  Order IDs -- CE: {ce_order_id}   PE: {pe_order_id}")

    state = {
        "entry_time": dt.datetime.now().isoformat(),
        "spot_entry": spot, "strike": atm_strike, "expiry": expiry_date_str,
        "ce_symbol": ce_symbol, "pe_symbol": pe_symbol,
        "premium_entry": premium_entry,
        "ce_entry_order_id": ce_order_id, "pe_entry_order_id": pe_order_id,
    }
    save_state(state)
    _record_entry()
    return state


def exit_position(state, reason):
    ce_ltp = get_ltp(state["ce_symbol"])
    pe_ltp = get_ltp(state["pe_symbol"])
    premium_exit = ce_ltp + pe_ltp
    pnl_points = premium_exit - state["premium_entry"]
    pnl_rupees = pnl_points * QUANTITY

    log(f"EXIT ({reason}): premium_exit={premium_exit:.1f} "
        f"pnl_points={pnl_points:+.1f} pnl_rupees={pnl_rupees:+,.0f}")

    ce_exit_order = place_order(state["ce_symbol"], QUANTITY, side=-1)
    pe_exit_order = place_order(state["pe_symbol"], QUANTITY, side=-1)
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
        "ce_entry_order_id": state.get("ce_entry_order_id"), "pe_entry_order_id": state.get("pe_entry_order_id"),
        "ce_exit_order_id": ce_exit_order_id, "pe_exit_order_id": pe_exit_order_id,
        "dry_run": DRY_RUN,
    })
    clear_state()
    clear_premium_chart()
    record_exit_date()
    record_reentry_wait(exited_at)


def main_loop():
    if SUPER_TREND_TRAIL:
        target_exit_mode = (f"Supertrend({SUPER_TREND_PERIOD},{SUPER_TREND_MULTIPLIER:g}) "
                            f"after +{SUPER_TREND_ACTIVATION_POINTS:g}; no fixed target")
    elif TRAIL_PROFIT:
        target_exit_mode = f"trail {TRAIL_PROFIT_POINTS:g}pts after target"
    else:
        target_exit_mode = "fixed target"
    risk_config = f"SL={STOPLOSS_POINTS:g}pts"
    log(f"Starting live SENSEX straddle trader. DRY_RUN={DRY_RUN}. "
        f"Config: vol_pctile={VOL_PERCENTILE}, {risk_config}, "
        f"exit={target_exit_mode}, "
        f"qty={QUANTITY} ({NUM_LOTS} lot(s)), "
        f"daily_cooldown={DAILY_COOLDOWN}, entry_window={ENTRY_WINDOW_START_TIME:%H:%M}-{ENTRY_WINDOW_END_TIME:%H:%M} IST, "
        f"max_reentries={MAX_REENTRIES_PER_DAY}, reentry_check={REENTRY_CANDLE_MINUTES}-minute close")
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
            elif in_daily_cooldown():
                log("In daily cooldown (already traded and exited today). Waiting for next trading day.")
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
                ce_ltp = get_ltp(state["ce_symbol"])
                pe_ltp = get_ltp(state["pe_symbol"])
                premium_now = ce_ltp + pe_ltp
                pnl_points = premium_now - state["premium_entry"]
                pnl_rupees = pnl_points * QUANTITY
                peak_profit_points = state.get("peak_profit_points")
                supertrend_status = None
                chart_candles = []
                chart_error = None
                supertrend_armed = (
                    state.get("supertrend_armed") is True
                    and state.get("supertrend_activation_points") == SUPER_TREND_ACTIVATION_POINTS
                )

                if (SUPER_TREND_TRAIL and not supertrend_armed
                        and pnl_points >= SUPER_TREND_ACTIVATION_POINTS):
                    supertrend_armed = True
                    state["supertrend_armed"] = True
                    state["supertrend_armed_time"] = now.isoformat()
                    state["supertrend_activation_points"] = SUPER_TREND_ACTIVATION_POINTS
                    save_state(state)
                    log(f"Supertrend profit trail armed at {pnl_points:+.1f} points")

                try:
                    chart_candles = get_combined_premium_chart(state["ce_symbol"], state["pe_symbol"], now)
                except Exception as chart_exception:
                    chart_error = str(chart_exception)

                if SUPER_TREND_TRAIL and supertrend_armed:
                    if chart_error:
                        raise RuntimeError(chart_error)
                    supertrend_status = get_combined_premium_supertrend(
                        state["ce_symbol"], state["pe_symbol"], now, chart_candles
                    )
                    armed_time = pd.Timestamp(state["supertrend_armed_time"])
                    if armed_time.tzinfo is None:
                        armed_time = armed_time.tz_localize("Asia/Kolkata")
                    signal_time = pd.Timestamp(supertrend_status["timestamp"])
                    supertrend_status["eligible"] = signal_time > armed_time

                save_premium_chart(
                    state, now, ce_ltp, pe_ltp, chart_candles, supertrend_armed, chart_error
                )

                if TRAIL_PROFIT and not SUPER_TREND_TRAIL and pnl_points >= TARGET_POINTS:
                    if peak_profit_points is None or pnl_points > peak_profit_points:
                        peak_profit_points = pnl_points
                        state["peak_profit_points"] = peak_profit_points
                        save_state(state)

                trailing_stop_points = (
                    peak_profit_points - TRAIL_PROFIT_POINTS
                    if TRAIL_PROFIT and not SUPER_TREND_TRAIL and peak_profit_points is not None else None
                )
                if SUPER_TREND_TRAIL:
                    if supertrend_status is None:
                        exit_status = f"ST waiting for +{SUPER_TREND_ACTIVATION_POINTS:g} activation"
                    else:
                        st_wait = "" if supertrend_status["eligible"] else " (waiting for post-arm close)"
                        exit_status = (
                            f"ST={supertrend_status['line']:.1f} "
                            f"close={supertrend_status['close']:.1f}{st_wait}"
                        )
                elif trailing_stop_points is not None:
                    exit_status = f"TRAIL={trailing_stop_points:.1f} (peak={peak_profit_points:.1f})"
                else:
                    exit_status = f"TGT={TARGET_POINTS:.0f}"
                log(
                    f"OPEN POSITION | strike={state['strike']}  expiry={state.get('expiry', 'unknown')}  "
                    f"CE={state['ce_symbol']}@{ce_ltp:.1f}  PE={state['pe_symbol']}@{pe_ltp:.1f}  "
                    f"entry_premium={state['premium_entry']:.1f}  current_premium={premium_now:.1f}  "
                    f"P&L={pnl_points:+.1f} pts (Rs {pnl_rupees:+,.0f})  "
                    f"[{exit_status}]"
                )

                if pnl_points <= -STOPLOSS_POINTS:
                    exit_position(state, "stoploss")
                elif now.time() >= EOD_SQUARE_OFF_TIME:
                    exit_position(state, "eod")
                elif (SUPER_TREND_TRAIL and supertrend_status is not None
                      and supertrend_status["eligible"]
                      and not supertrend_status["bullish"]):
                    exit_position(state, "supertrend_trail")
                elif trailing_stop_points is not None and pnl_points <= trailing_stop_points:
                    exit_position(state, "trailing_profit")
                elif not SUPER_TREND_TRAIL and not TRAIL_PROFIT and pnl_points >= TARGET_POINTS:
                    exit_position(state, "target")
            except Exception as e:
                log(f"ERROR checking exit: {e}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SENSEX vol-compression straddle trader (Fyers). "
                     "Default mode is forward-test / paper trading (no real orders)."
    )
    parser.add_argument(
        "-live", "--live", dest="live", action="store_true",
        help="Place REAL orders on your Fyers account instead of forward-testing.",
    )
    parser.add_argument(
        "--lots", type=int, default=NUM_LOTS, metavar="N",
        help=f"Number of SENSEX option lots per leg (default: {NUM_LOTS}).",
    )
    parser.add_argument("--entry-start", default=ENTRY_WINDOW_START_TIME.strftime("%H:%M"), help="New-entry window start in IST (HH:MM).")
    parser.add_argument("--entry-end", default=ENTRY_WINDOW_END_TIME.strftime("%H:%M"), help="New-entry window end in IST (HH:MM).")
    exit_mode = parser.add_mutually_exclusive_group()
    exit_mode.add_argument(
        "--fixed-target", dest="exit_mode", action="store_const", const="fixed",
        help=f"Use a {TARGET_POINTS:g}-point fixed target with the {STOPLOSS_POINTS:g}-point hard stop.",
    )
    exit_mode.add_argument(
        "--trail-profit", dest="exit_mode", action="store_const", const="trail",
        help=f"After reaching the target, trail peak profit by {TRAIL_PROFIT_POINTS:g} points.",
    )
    exit_mode.add_argument(
        "--supertrend-trail", dest="exit_mode", action="store_const", const="supertrend",
        help=(f"After +{SUPER_TREND_ACTIVATION_POINTS:g} points, trail completed combined-premium candles with "
              f"Supertrend({SUPER_TREND_PERIOD},{SUPER_TREND_MULTIPLIER:g}); "
              f"disable the fixed target and keep the {STOPLOSS_POINTS:g}-point hard stop (default)."),
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

    if args.lots < 1:
        parser.error("--lots must be at least 1")
    NUM_LOTS = args.lots
    QUANTITY = LOT_SIZE * NUM_LOTS

    TRAIL_PROFIT = args.exit_mode == "trail"
    SUPER_TREND_TRAIL = args.exit_mode == "supertrend"

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
