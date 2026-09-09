"""Read-only NIFTY pure VWAP pullback study across 3-, 5-, and 15-minute candles."""
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
TIMEFRAMES = ("3", "5", "15")
REWARD_RISK, COST_RATE, FIXED_COST = 2.0, 0.0006, 40


def fetch_history(client: fyersModel.FyersModel, now: datetime, resolution: str) -> pd.DataFrame:
    rows, cursor, end = [], now.date() - timedelta(days=365), now.date()
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=99), end)
        response = client.history({"symbol": SYMBOL, "resolution": resolution, "date_format": 1,
                                   "range_from": cursor.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": 1})
        if response.get("s") != "ok":
            raise RuntimeError(response.get("message") or f"history unavailable for {resolution}-minute candles")
        rows.extend(response["candles"])
        cursor = chunk_end + timedelta(days=1)
    frame = pd.DataFrame(rows, columns=["epoch", "open", "high", "low", "close", "volume"]).drop_duplicates("epoch").sort_values("epoch")
    seconds = int(resolution) * 60
    frame["timestamp"] = pd.to_datetime(frame["epoch"], unit="s", utc=True).dt.tz_convert(IST)
    frame = frame[frame["epoch"] + seconds <= now.timestamp()].copy()
    frame["session"] = frame["timestamp"].dt.date
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    frame["vwap"] = (typical * frame["volume"]).groupby(frame["session"]).cumsum() / frame["volume"].groupby(frame["session"]).cumsum()
    return frame


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    returns, exits, sides = [], [], []
    for _, bars in frame[frame["session"] >= cutoff].groupby("session", sort=True):
        bars = bars.reset_index(drop=True)
        side = entry = None
        traded = False
        for index in range(1, len(bars) - 1):
            previous, bar, next_open = bars.iloc[index - 1], bars.iloc[index], bars.iloc[index + 1]["open"]
            hour, minute = bar["timestamp"].hour, bar["timestamp"].minute
            entry_window = (hour, minute) >= (9, 30) and (hour, minute) < (14, 45)
            if side is None and not traded and entry_window:
                long_pullback = previous["close"] > previous["vwap"] and bar["low"] <= bar["vwap"] and bar["close"] > bar["vwap"]
                short_pullback = previous["close"] < previous["vwap"] and bar["high"] >= bar["vwap"] and bar["close"] < bar["vwap"]
                if long_pullback:
                    side, entry, stop = "long", next_open, bar["low"]
                elif short_pullback:
                    side, entry, stop = "short", next_open, bar["high"]
                else:
                    continue
                risk = entry - stop if side == "long" else stop - entry
                if risk <= 0:
                    side = entry = None
                    continue
                target = entry + REWARD_RISK * risk if side == "long" else entry - REWARD_RISK * risk
                continue
            if side is None:
                continue
            hit_stop = bar["low"] <= stop if side == "long" else bar["high"] >= stop
            hit_target = bar["high"] >= target if side == "long" else bar["low"] <= target
            session_end = (hour, minute) >= (15, 15)
            if hit_stop or hit_target or session_end:
                exit_price = stop if hit_stop else target if hit_target else next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - COST_RATE - FIXED_COST / entry)
                exits.append("stop" if hit_stop else "target" if hit_target else "session")
                sides.append(side)
                side, entry, traded = None, None, True
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
    client = fyersModel.FyersModel(client_id=app_id, token=token)
    now = datetime.now(IST)
    results = {}
    for timeframe in TIMEFRAMES:
        frame = fetch_history(client, now, timeframe)
        results[f"{timeframe}m"] = {"completed_bars": len(frame), "windows": [evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps({"strategy": "Pure session VWAP pullback", "rules": "after 09:30, a prior close on one side of VWAP followed by a candle that touches and closes back on that side triggers next-candle entry; stop at pullback candle extreme; 2R target; 15:20 exit; maximum one trade per session; no indicator beyond session VWAP; costs 0.06% plus Rs 40 per completed trade", "data_source": "FYERS completed NIFTY 50 index candles", "results": results}, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
