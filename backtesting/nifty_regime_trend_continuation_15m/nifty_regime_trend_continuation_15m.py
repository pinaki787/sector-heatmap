"""Read-only NIFTY 15-minute regime-filtered trend-day continuation research."""
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
MIN_OPENING_RANGE, ATR_PERIOD, STOP_ATR_MULTIPLE, MIN_STOP, REWARD_RISK = 0.0025, 14, 0.75, 0.0025, 2.0
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
    frame = frame[frame["epoch"] + 900 <= now.timestamp()].copy()
    frame["session"] = frame["timestamp"].dt.date
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    frame["vwap"] = (typical * frame["volume"]).groupby(frame["session"]).cumsum() / frame["volume"].groupby(frame["session"]).cumsum()
    daily = frame.groupby("session").agg(close=("close", "last"))
    daily["ema20"] = daily["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    daily["bias"] = 0
    daily.loc[daily["close"].shift(1) > daily["ema20"].shift(1), "bias"] = 1
    daily.loc[daily["close"].shift(1) < daily["ema20"].shift(1), "bias"] = -1
    frame["bias"] = frame["session"].map(daily["bias"])
    previous_close = frame.groupby("session")["close"].shift(1)
    tr = pd.concat([frame["high"] - frame["low"], (frame["high"] - previous_close).abs(), (frame["low"] - previous_close).abs()], axis=1).max(axis=1)
    frame["atr"] = tr.groupby(frame["session"]).transform(lambda value: value.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean())
    return frame


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    returns, exits, sides = [], [], []
    for _, bars in frame[frame["session"] >= cutoff].groupby("session", sort=True):
        bars = bars.reset_index(drop=True)
        if len(bars) < 5 or bars.loc[0, "bias"] == 0:
            continue
        opening = bars.iloc[:2]  # 09:15-09:45, a 30-minute range.
        high, low = opening["high"].max(), opening["low"].min()
        if (high - low) / opening.iloc[0]["open"] < MIN_OPENING_RANGE:
            continue
        bias, broke, side, entry = int(bars.loc[0, "bias"]), False, None, None
        for index in range(2, len(bars) - 1):
            bar, next_open = bars.iloc[index], bars.iloc[index + 1]["open"]
            hour, minute = bar["timestamp"].hour, bar["timestamp"].minute
            if side is None:
                if not broke:
                    broke = (bias == 1 and bar["close"] > high) or (bias == -1 and bar["close"] < low)
                    continue
                reclaim = (bias == 1 and bar["low"] <= bar["vwap"] and bar["close"] > bar["vwap"]) or (bias == -1 and bar["high"] >= bar["vwap"] and bar["close"] < bar["vwap"])
                if reclaim:
                    side, entry = ("long" if bias == 1 else "short"), next_open
                continue
            risk = max(MIN_STOP * entry, STOP_ATR_MULTIPLE * bar["atr"])
            stop = entry - risk if side == "long" else entry + risk
            target = entry + REWARD_RISK * risk if side == "long" else entry - REWARD_RISK * risk
            hit_stop = bar["low"] <= stop if side == "long" else bar["high"] >= stop
            hit_target = bar["high"] >= target if side == "long" else bar["low"] <= target
            session_end = (hour, minute) >= (15, 15)
            if hit_stop or hit_target or session_end:
                exit_price = stop if hit_stop else target if hit_target else next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - COST_RATE - FIXED_COST / entry)
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
            "long_trades": sides.count("long"), "short_trades": sides.count("short"), "exits": {key: exits.count(key) for key in sorted(set(exits))}}


def main() -> None:
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    frame = fetch_history(fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(IST))
    result = {"strategy": "15-minute regime-filtered NIFTY trend-day continuation", "rules": "same rule set as the 5-minute study, except entries and exits use 15-minute completed candles; prior daily EMA20 bias; 30-minute opening range; breakout then VWAP pullback/reclaim; next-bar entry; 0.75 ATR or 0.25% minimum stop; 2R target; 15:20 exit", "data_source": "FYERS completed NIFTY 50 index 15-minute candles", "results": [evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps(result, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
