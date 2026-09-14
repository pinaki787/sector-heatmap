"""Independent completed-candle KAMA V6 signal engine.

This module deliberately has no EMA dependency and no broker side effects.  A
caller supplies completed candles and owns any paper/live lifecycle state.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def kama_exit_state_machine(signal, completed_candle, broker_state="UNKNOWN"):
    """Turn a completed KAMA exit signal into a fail-closed lifecycle decision."""
    action = str((signal or {}).get("action") or "WAIT").upper()
    if action not in {"EXIT_LONG", "EXIT_SHORT", "SQUARE_OFF"}:
        return {"exit": False, "lifecycle": "HOLD", "reason": "NO_EXIT_SIGNAL"}
    if not completed_candle:
        return {"exit": False, "lifecycle": "CANDLE_INCOMPLETE", "reason": "CANDLE_INCOMPLETE"}
    if str(broker_state).upper() != "CONFIRMED":
        return {"exit": False, "lifecycle": "RECONCILIATION_BLOCKED", "reason": "BROKER_POSITION_UNCONFIRMED"}
    return {
        "exit": True,
        "lifecycle": "EXIT_READY",
        "reason": "SESSION_SQUARE_OFF" if action == "SQUARE_OFF" else "KAMA_EXIT_SIGNAL",
    }


def kama_entry_policy_decision(signal, policy, account_position_exists=False):
    """Validate the minimum KAMA entry policy before any broker submission."""
    action = str((signal or {}).get("action") or "WAIT").upper()
    if action not in {"ENTER_LONG", "ENTER_SHORT"}:
        return {"allowed": False, "reason": "NO_ENTRY_SIGNAL"}
    required = ("quantity", "max_risk", "stop_price")
    if not isinstance(policy, dict) or any(key not in policy for key in required):
        return {"allowed": False, "reason": "POLICY_INCOMPLETE"}
    try:
        valid = int(policy["quantity"]) > 0 and float(policy["max_risk"]) > 0 and float(policy["stop_price"]) > 0
    except (TypeError, ValueError):
        valid = False
    if not valid:
        return {"allowed": False, "reason": "POLICY_INCOMPLETE"}
    if account_position_exists:
        return {"allowed": False, "reason": "ACCOUNT_POSITION_EXISTS"}
    return {"allowed": True, "reason": "POLICY_READY"}


def _in_session(timestamp, session):
    start, end = session.split("-")
    moment = datetime.fromtimestamp(float(timestamp), tz=IST)
    minute = moment.hour * 60 + moment.minute
    return int(start[:2]) * 60 + int(start[2:]) <= minute <= int(end[:2]) * 60 + int(end[2:])


def kama_v6_signal(candles, position=0, last_long_exit_bar=None, last_short_exit_bar=None,
                   kama_length=10, fast_length=2, slow_length=30, minimum_efficiency=.35,
                   breakout_bars=5, cooldown_bars=2, allow_reclaims=True,
                   entry_session="0915-1510", squareoff_session="1515-1530"):
    """Return a KAMA-only decision for the newest completed candle.

    ``position`` is -1, 0, or 1.  Entry, hold, and exit decisions are derived
    exclusively from these candles; eligibility/master checks belong outside
    this function and must never turn a WAIT into an entry.
    """
    if kama_length < 1 or fast_length < 1 or slow_length <= fast_length or breakout_bars < 2:
        raise ValueError("KAMA settings are outside the supported safe range.")
    if len(candles) < max(kama_length + 2, breakout_bars + 1):
        return {"status": "INSUFFICIENT_HISTORY", "action": "WAIT", "message": "KAMA V6 needs more completed candles."}
    closes = [float(item["close"]) for item in candles]
    line = []
    fast_sc, slow_sc = 2 / (fast_length + 1), 2 / (slow_length + 1)
    for index, close in enumerate(closes):
        if index < kama_length:
            line.append(None)
            continue
        change = abs(close - closes[index - kama_length])
        noise = sum(abs(closes[offset] - closes[offset - 1]) for offset in range(index - kama_length + 1, index + 1))
        efficiency = change / noise if noise else 0.0
        smoothing = (efficiency * (fast_sc - slow_sc) + slow_sc) ** 2
        prior = line[-1]
        line.append(close if prior is None else prior + smoothing * (close - prior))
    current, value, previous = candles[-1], line[-1], line[-2]
    change = abs(closes[-1] - closes[-1 - kama_length])
    noise = sum(abs(closes[offset] - closes[offset - 1]) for offset in range(len(closes) - kama_length, len(closes)))
    efficiency = change / noise if noise else 0.0
    rising, falling = value > previous, value < previous
    prior_high = max(float(item["high"]) for item in candles[-breakout_bars - 1:-1])
    prior_low = min(float(item["low"]) for item in candles[-breakout_bars - 1:-1])
    long_ok = efficiency >= minimum_efficiency and rising and (float(current["close"]) > prior_high or (allow_reclaims and float(current["low"]) <= value < float(current["close"])))
    short_ok = efficiency >= minimum_efficiency and falling and (float(current["close"]) < prior_low or (allow_reclaims and float(current["high"]) >= value > float(current["close"])))
    bar_index = len(candles) - 1
    if position and _in_session(current["timestamp"], squareoff_session):
        action = "SQUARE_OFF"
    elif position > 0 and float(current["close"]) < value and falling:
        action = "EXIT_LONG"
    elif position < 0 and float(current["close"]) > value and rising:
        action = "EXIT_SHORT"
    elif position == 0 and _in_session(current["timestamp"], entry_session) and long_ok and (last_long_exit_bar is None or bar_index - last_long_exit_bar > cooldown_bars):
        action = "ENTER_LONG"
    elif position == 0 and _in_session(current["timestamp"], entry_session) and short_ok and (last_short_exit_bar is None or bar_index - last_short_exit_bar > cooldown_bars):
        action = "ENTER_SHORT"
    else:
        action = "WAIT"
    return {"status": "READY", "action": action, "kama": round(value, 4), "efficiency": round(efficiency, 4),
            "kama_rising": rising, "kama_falling": falling, "prior_high": round(prior_high, 4),
            "prior_low": round(prior_low, 4), "message": f"KAMA V6: {action}."}
