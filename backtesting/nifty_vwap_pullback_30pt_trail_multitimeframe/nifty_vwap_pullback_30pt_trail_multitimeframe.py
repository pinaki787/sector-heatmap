"""Read-only NIFTY VWAP pullback research with a 30-point profit-trailing exit."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_vwap_pullback_multitimeframe" / "nifty_vwap_pullback_multitimeframe.py"
spec = importlib.util.spec_from_file_location("vwap_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ACTIVATION_POINTS, TRAIL_POINTS = 30.0, 15.0


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    returns, exits, sides = [], [], []
    for _, bars in frame[frame["session"] >= cutoff].groupby("session", sort=True):
        bars = bars.reset_index(drop=True)
        side = entry = stop = None
        highwater = lowwater = None
        trail_active = traded = False
        for index in range(1, len(bars) - 1):
            previous, bar, next_open = bars.iloc[index - 1], bars.iloc[index], bars.iloc[index + 1]["open"]
            hour, minute = bar["timestamp"].hour, bar["timestamp"].minute
            if side is None and not traded and (hour, minute) >= (9, 30) and (hour, minute) < (14, 45):
                long_pullback = previous["close"] > previous["vwap"] and bar["low"] <= bar["vwap"] and bar["close"] > bar["vwap"]
                short_pullback = previous["close"] < previous["vwap"] and bar["high"] >= bar["vwap"] and bar["close"] < bar["vwap"]
                if long_pullback:
                    side, entry, stop = "long", next_open, bar["low"]
                elif short_pullback:
                    side, entry, stop = "short", next_open, bar["high"]
                else:
                    continue
                if (entry - stop if side == "long" else stop - entry) <= 0:
                    side = entry = stop = None
                    continue
                highwater, lowwater = entry, entry
                continue
            if side is None:
                continue
            fixed_stop = bar["low"] <= stop if side == "long" else bar["high"] >= stop
            existing_trail = highwater - TRAIL_POINTS if side == "long" else lowwater + TRAIL_POINTS
            trail_stop = trail_active and (bar["low"] <= existing_trail if side == "long" else bar["high"] >= existing_trail)
            session_end = (hour, minute) >= (15, 15)
            if fixed_stop or trail_stop or session_end:
                exit_price = stop if fixed_stop else existing_trail if trail_stop else next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - base.COST_RATE - base.FIXED_COST / entry)
                exits.append("fixed_stop" if fixed_stop else "trailing_stop" if trail_stop else "session")
                sides.append(side)
                side, entry, stop, traded = None, None, None, True
                continue
            highwater, lowwater = max(highwater, bar["high"]), min(lowwater, bar["low"])
            trail_active = trail_active or (highwater - entry >= ACTIVATION_POINTS if side == "long" else entry - lowwater >= ACTIVATION_POINTS)
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
    print(json.dumps({"strategy": "Pure VWAP pullback with 30-point profit-trailing exit", "rules": "same pure VWAP pullback entry; initial stop at pullback extreme; after a 30-point favorable move, activate a 15-point trailing stop; 15:20 session exit; one trade per session; costs 0.06% plus Rs 40 per completed trade", "data_source": "FYERS completed NIFTY 50 index candles", "results": results}, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
