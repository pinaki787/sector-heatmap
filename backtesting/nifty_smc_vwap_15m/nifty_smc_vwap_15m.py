"""Read-only NIFTY 15-minute SMC plus session VWAP research."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_smc_only_15m" / "nifty_smc_only_15m.py"
spec = importlib.util.spec_from_file_location("smc_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    data = frame[frame["timestamp"].dt.date >= cutoff].copy()
    data["session"] = data["timestamp"].dt.date
    typical = (data["high"] + data["low"] + data["close"]) / 3
    data["vwap"] = (typical * data["volume"]).groupby(data["session"]).cumsum() / data["volume"].groupby(data["session"]).cumsum()
    returns, exits, sides = [], [], []
    for _, bars in data.groupby("session", sort=True):
        bars = bars.reset_index(drop=True)
        last_high = last_low = None
        side = entry = None
        for index in range(2, len(bars) - 1):
            prior, previous, bar, next_open = bars.iloc[index - 2], bars.iloc[index - 1], bars.iloc[index], bars.iloc[index + 1]["open"]
            if previous["high"] > prior["high"] and previous["high"] > bar["high"]:
                last_high = previous["high"]
            if previous["low"] < prior["low"] and previous["low"] < bar["low"]:
                last_low = previous["low"]
            break_up = last_high is not None and bar["close"] > last_high and bar["close"] > bar["vwap"]
            break_down = last_low is not None and bar["close"] < last_low and bar["close"] < bar["vwap"]
            session_end = (bar["timestamp"].hour, bar["timestamp"].minute) >= (15, 15)
            if side is None:
                if break_up:
                    side, entry, last_high = "long", next_open, None
                elif break_down:
                    side, entry, last_low = "short", next_open, None
                continue
            opposite = (side == "long" and break_down) or (side == "short" and break_up)
            if opposite or session_end:
                gross = next_open / entry - 1 if side == "long" else entry / next_open - 1
                returns.append(gross - base.COST_RATE - base.FIXED_COST / entry)
                exits.append("opposite_structure" if opposite else "session")
                sides.append(side)
                side = entry = None
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
    frame = base.fetch_history(fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(base.IST))
    result = {"strategy": "15-minute SMC confirmed structure breaks plus session VWAP", "rules": "same SMC-only market-structure entries, but long breaks require close above VWAP and short breaks require close below VWAP; no other filter; next-candle entry; opposite structure or session exit; costs 0.06% plus Rs 40 per completed trade", "data_source": "FYERS completed NIFTY 50 index 15-minute candles", "results": [evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps(result, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
