"""Read-only NIFTY 15-minute SMC-only market-structure-break research."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

IST = ZoneInfo("Asia/Kolkata")
SYMBOL = "NSE:NIFTY50-INDEX"
COST_RATE, FIXED_COST = 0.0006, 40


def fetch_history(client: fyersModel.FyersModel, now: datetime) -> pd.DataFrame:
    rows, cursor, end = [], now.date() - timedelta(days=365), now.date()
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=99), end)
        response = client.history({"symbol": SYMBOL, "resolution": "15", "date_format": 1,
                                   "range_from": cursor.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": 1})
        if response.get("s") != "ok":
            raise RuntimeError(response.get("message") or "history unavailable")
        rows.extend(response["candles"])
        cursor = chunk_end + timedelta(days=1)
    frame = pd.DataFrame(rows, columns=["epoch", "open", "high", "low", "close", "volume"]).drop_duplicates("epoch").sort_values("epoch")
    frame["timestamp"] = pd.to_datetime(frame["epoch"], unit="s", utc=True).dt.tz_convert(IST)
    return frame[frame["epoch"] + 900 <= now.timestamp()].copy()


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    data = frame[frame["timestamp"].dt.date >= cutoff]
    returns, exits, sides = [], [], []
    for _, bars in data.groupby(data["timestamp"].dt.date, sort=True):
        bars = bars.reset_index(drop=True)
        last_high = last_low = None
        side = entry = None
        for index in range(2, len(bars) - 1):
            previous, bar, next_open = bars.iloc[index - 1], bars.iloc[index], bars.iloc[index + 1]["open"]
            prior = bars.iloc[index - 2]
            if previous["high"] > prior["high"] and previous["high"] > bar["high"]:
                last_high = previous["high"]
            if previous["low"] < prior["low"] and previous["low"] < bar["low"]:
                last_low = previous["low"]
            break_up = last_high is not None and bar["close"] > last_high
            break_down = last_low is not None and bar["close"] < last_low
            session_end = (bar["timestamp"].hour, bar["timestamp"].minute) >= (15, 15)
            if side is None:
                if break_up:
                    side, entry = "long", next_open
                    last_high = None
                elif break_down:
                    side, entry = "short", next_open
                    last_low = None
                continue
            opposite_break = (side == "long" and break_down) or (side == "short" and break_up)
            if opposite_break or session_end:
                exit_price = next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - COST_RATE - FIXED_COST / entry)
                exits.append("opposite_structure" if opposite_break else "session")
                sides.append(side)
                side = entry = None
        if side is not None:
            bar = bars.iloc[-1]
            gross = bar["close"] / entry - 1 if side == "long" else entry / bar["close"] - 1
            returns.append(gross - COST_RATE - FIXED_COST / entry)
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
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    frame = fetch_history(fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(IST))
    result = {"strategy": "15-minute SMC-only confirmed swing structure breaks", "rules": "a swing high/low is confirmed only after its right-hand 15-minute candle closes; enter next candle open when price closes beyond latest confirmed swing high/low; exit on an opposite confirmed structure break or session close; no other indicator/filter; costs 0.06% plus Rs 40 per completed trade", "data_source": "FYERS completed NIFTY 50 index 15-minute candles", "results": [evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps(result, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
