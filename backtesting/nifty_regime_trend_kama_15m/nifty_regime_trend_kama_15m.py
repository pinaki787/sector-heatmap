"""Read-only 15-minute NIFTY continuation research with a KAMA trend filter."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_regime_trend_continuation_15m" / "nifty_regime_trend_continuation_15m.py"
spec = importlib.util.spec_from_file_location("base_15m", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ER_PERIOD, FAST_PERIOD, SLOW_PERIOD = 10, 2, 30


def kama(close: pd.Series) -> pd.Series:
    change = (close - close.shift(ER_PERIOD)).abs()
    volatility = close.diff().abs().rolling(ER_PERIOD).sum()
    efficiency = (change / volatility.replace(0, float("nan"))).fillna(0)
    fast = 2 / (FAST_PERIOD + 1)
    slow = 2 / (SLOW_PERIOD + 1)
    smoothing = (efficiency * (fast - slow) + slow) ** 2
    values = pd.Series(index=close.index, dtype=float)
    values.iloc[ER_PERIOD] = close.iloc[ER_PERIOD]
    for index in range(ER_PERIOD + 1, len(close)):
        values.iloc[index] = values.iloc[index - 1] + smoothing.iloc[index] * (close.iloc[index] - values.iloc[index - 1])
    return values


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    returns, exits, sides = [], [], []
    for _, bars in frame[frame["session"] >= cutoff].groupby("session", sort=True):
        bars = bars.reset_index(drop=True)
        if len(bars) < 5 or bars.loc[0, "bias"] == 0:
            continue
        opening = bars.iloc[:2]
        high, low = opening["high"].max(), opening["low"].min()
        if (high - low) / opening.iloc[0]["open"] < base.MIN_OPENING_RANGE:
            continue
        bias, broke, side, entry = int(bars.loc[0, "bias"]), False, None, None
        for index in range(2, len(bars) - 1):
            bar, next_open = bars.iloc[index], bars.iloc[index + 1]["open"]
            hour, minute = bar["timestamp"].hour, bar["timestamp"].minute
            kama_long = pd.notna(bar["kama"]) and bar["close"] > bar["kama"] and bar["kama"] > bars.iloc[index - 1]["kama"]
            kama_short = pd.notna(bar["kama"]) and bar["close"] < bar["kama"] and bar["kama"] < bars.iloc[index - 1]["kama"]
            if side is None:
                if not broke:
                    broke = (bias == 1 and bar["close"] > high and kama_long) or (bias == -1 and bar["close"] < low and kama_short)
                    continue
                reclaim = (bias == 1 and bar["low"] <= bar["vwap"] and bar["close"] > bar["vwap"] and kama_long) or (bias == -1 and bar["high"] >= bar["vwap"] and bar["close"] < bar["vwap"] and kama_short)
                if reclaim:
                    side, entry = ("long" if bias == 1 else "short"), next_open
                continue
            risk = max(base.MIN_STOP * entry, base.STOP_ATR_MULTIPLE * bar["atr"])
            stop = entry - risk if side == "long" else entry + risk
            target = entry + base.REWARD_RISK * risk if side == "long" else entry - base.REWARD_RISK * risk
            hit_stop = bar["low"] <= stop if side == "long" else bar["high"] >= stop
            hit_target = bar["high"] >= target if side == "long" else bar["low"] <= target
            session_end = (hour, minute) >= (15, 15)
            if hit_stop or hit_target or session_end:
                exit_price = stop if hit_stop else target if hit_target else next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - base.COST_RATE - base.FIXED_COST / entry)
                exits.append("stop" if hit_stop else "target" if hit_target else "session")
                sides.append(side)
                break
    equity = peak = 1.0
    drawdown = 0.0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    return {"calendar_lookback_days": days, "closed_trades": len(returns), "wins": sum(value > 0 for value in returns),
            "win_rate_pct": round(100 * sum(value > 0 for value in returns) / len(returns), 2) if returns else None,
            "net_return_pct": round(100 * (equity - 1), 3), "max_drawdown_pct": round(100 * drawdown, 3),
            "long_trades": sides.count("long"), "short_trades": sides.count("short"), "exits": {kind: exits.count(kind) for kind in sorted(set(exits))}}


def main() -> None:
    app_id, token = base.load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    frame = base.fetch_history(fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(base.IST))
    frame["kama"] = kama(frame["close"])
    result = {"strategy": "15-minute regime-filtered trend-day continuation with KAMA", "rules": "same 15-minute baseline, plus close above/below KAMA(ER10, fast2, slow30) and KAMA slope in the trade direction at breakout and pullback entry", "data_source": "FYERS completed NIFTY 50 index 15-minute candles", "results": [evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps(result, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
