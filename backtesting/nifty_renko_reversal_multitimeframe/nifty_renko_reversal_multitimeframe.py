"""Read-only NIFTY intraday fixed-brick Renko reversal research across timeframes."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_vwap_pullback_multitimeframe" / "nifty_vwap_pullback_multitimeframe.py"
spec = importlib.util.spec_from_file_location("data_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

BRICK_SIZE, INITIAL_STOP_POINTS, TRAIL_ACTIVATION_POINTS, TRAIL_POINTS = 30.0, 60.0, 60.0, 30.0


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    returns, exits, sides = [], [], []
    for _, bars in frame[frame["session"] >= cutoff].groupby("session", sort=True):
        bars = bars.reset_index(drop=True)
        anchor = bars.iloc[0]["open"]
        directions = []
        side = entry = None
        highwater = lowwater = None
        trail_active = False
        for index in range(1, len(bars) - 1):
            bar, next_open = bars.iloc[index], bars.iloc[index + 1]["open"]
            move = bar["close"] - anchor
            new_directions = []
            while move >= BRICK_SIZE:
                anchor += BRICK_SIZE
                move -= BRICK_SIZE
                new_directions.append(1)
            while move <= -BRICK_SIZE:
                anchor -= BRICK_SIZE
                move += BRICK_SIZE
                new_directions.append(-1)
            directions.extend(new_directions)
            directions = directions[-2:]
            hour, minute = bar["timestamp"].hour, bar["timestamp"].minute
            signal = directions[0] if len(directions) == 2 and directions[0] == directions[1] else 0
            session_end = (hour, minute) >= (15, 15)
            if side is None:
                if new_directions and signal and (hour, minute) >= (9, 30) and (hour, minute) < (14, 45):
                    side, entry = ("long" if signal == 1 else "short"), next_open
                    highwater, lowwater = entry, entry
                continue
            hard_stop = entry - INITIAL_STOP_POINTS if side == "long" else entry + INITIAL_STOP_POINTS
            trail = highwater - TRAIL_POINTS if side == "long" else lowwater + TRAIL_POINTS
            hit_hard_stop = bar["low"] <= hard_stop if side == "long" else bar["high"] >= hard_stop
            hit_trail = trail_active and (bar["low"] <= trail if side == "long" else bar["high"] >= trail)
            opposite = (side == "long" and signal == -1) or (side == "short" and signal == 1)
            if hit_hard_stop or hit_trail or opposite or session_end:
                exit_price = hard_stop if hit_hard_stop else trail if hit_trail else next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - base.COST_RATE - base.FIXED_COST / entry)
                exits.append("hard_stop" if hit_hard_stop else "trailing_stop" if hit_trail else "opposite_renko" if opposite else "session")
                sides.append(side)
                side = entry = None
                trail_active = False
                continue
            highwater, lowwater = max(highwater, bar["high"]), min(lowwater, bar["low"])
            trail_active = trail_active or (highwater - entry >= TRAIL_ACTIVATION_POINTS if side == "long" else entry - lowwater >= TRAIL_ACTIVATION_POINTS)
        if side is not None:
            bar = bars.iloc[-1]
            gross = bar["close"] / entry - 1 if side == "long" else entry / bar["close"] - 1
            returns.append(gross - base.COST_RATE - base.FIXED_COST / entry)
            exits.append("session")
            sides.append(side)
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
    client, now = fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(base.IST)
    results = {}
    for timeframe in base.TIMEFRAMES:
        frame = base.fetch_history(client, now, timeframe)
        results[f"{timeframe}m"] = {"completed_bars": len(frame), "windows": [evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps({"strategy": "Fixed 30-point Renko two-brick reversal with delayed one-brick trailing stop", "rules": "build intraday fixed 30-point Renko bricks from completed raw-candle closes; enter next candle open after two same-direction bricks; use a two-brick 60-point initial stop; after a two-brick favorable move, trail by one 30-point brick; exit on an opposite two-brick reversal or 15:20 session exit; costs 0.06% plus Rs 40 per completed trade", "data_source": "FYERS completed NIFTY 50 index candles", "results": results}, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
