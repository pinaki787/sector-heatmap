"""One-year, completed-candle research for the original Pinaki Das Supertrend.

This is a research-only NIFTY 15-minute simulation. It uses next-bar-open
fills, exits before the close, and a conservative cost proxy. It is not an
options-premium test and does not place orders.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

IST = ZoneInfo("Asia/Kolkata")
SYMBOL = "NSE:NIFTY50-INDEX"
RESOLUTION = "15"
ATR_LENGTH = 14
FACTOR = 3.0
EMA_LENGTH = 21
SLOPE_BARS = 8
MIN_SLOPE_ATR = 0.10
COST_RATE = 0.0006
FIXED_COST = 40.0


def fetch_history(client: fyersModel.FyersModel, now: datetime) -> pd.DataFrame:
    rows, cursor, end = [], now.date() - timedelta(days=365), now.date()
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=90), end)
        response = client.history({"symbol": SYMBOL, "resolution": RESOLUTION, "date_format": 1,
                                   "range_from": cursor.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": 1})
        if response.get("s") != "ok":
            raise RuntimeError(response.get("message", "FYERS history unavailable"))
        rows.extend(response["candles"])
        cursor = chunk_end + timedelta(days=1)
    df = pd.DataFrame(rows, columns=["epoch", "open", "high", "low", "close", "volume"]).drop_duplicates("epoch").sort_values("epoch")
    df["timestamp"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert(IST)
    # Only closed candles, NSE session, and no use of the still-forming bar.
    df = df[(df["epoch"] + int(RESOLUTION) * 60 <= now.timestamp()) &
            (df["timestamp"].dt.time >= datetime.strptime("09:15", "%H:%M").time()) &
            (df["timestamp"].dt.time <= datetime.strptime("15:15", "%H:%M").time())].copy()
    return df.reset_index(drop=True)


def wilder_atr(df: pd.DataFrame, length: int) -> pd.Series:
    previous_close = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]), (df["high"] - previous_close).abs(), (df["low"] - previous_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def add_indicator(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["atr"] = wilder_atr(data, ATR_LENGTH)
    midpoint = (data["high"] + data["low"]) / 2
    upper = midpoint + FACTOR * data["atr"]
    lower = midpoint - FACTOR * data["atr"]
    final_upper, final_lower, trend = np.full(len(data), np.nan), np.full(len(data), np.nan), np.ones(len(data), dtype=int)
    for i in range(1, len(data)):
        if np.isnan(data.at[i, "atr"]):
            continue
        final_upper[i] = upper.iat[i] if np.isnan(final_upper[i - 1]) or upper.iat[i] < final_upper[i - 1] or data["close"].iat[i - 1] > final_upper[i - 1] else final_upper[i - 1]
        final_lower[i] = lower.iat[i] if np.isnan(final_lower[i - 1]) or lower.iat[i] > final_lower[i - 1] or data["close"].iat[i - 1] < final_lower[i - 1] else final_lower[i - 1]
        if data["close"].iat[i] > final_upper[i - 1]:
            trend[i] = 1
        elif data["close"].iat[i] < final_lower[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]
    data["trend"] = trend
    data["ema"] = data["close"].ewm(span=EMA_LENGTH, adjust=False, min_periods=EMA_LENGTH).mean()
    data["slope_atr"] = (data["ema"] - data["ema"].shift(SLOPE_BARS)) / data["atr"].shift(SLOPE_BARS)
    data["long_signal"] = (data["trend"].eq(1) & data["trend"].shift(1).eq(-1) & data["close"].gt(data["ema"]) & data["slope_atr"].ge(MIN_SLOPE_ATR))
    data["short_signal"] = (data["trend"].eq(-1) & data["trend"].shift(1).eq(1) & data["close"].lt(data["ema"]) & data["slope_atr"].le(-MIN_SLOPE_ATR))
    return data


def simulate(data: pd.DataFrame) -> tuple[list[dict], dict]:
    trades, side, entry = [], None, None
    for i in range(1, len(data) - 1):
        row, next_open = data.iloc[i], data.iloc[i + 1]["open"]
        session_end = row["timestamp"].time() >= datetime.strptime("15:00", "%H:%M").time()
        opposite = side == "long" and row["short_signal"] or side == "short" and row["long_signal"]
        if side and (opposite or session_end):
            exit_price = next_open
            gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
            trades.append({"entry": entry, "exit": exit_price, "side": side, "return": gross - COST_RATE - FIXED_COST / entry})
            side = entry = None
        if side is None and not session_end:
            if row["long_signal"]:
                side, entry = "long", next_open
            elif row["short_signal"]:
                side, entry = "short", next_open
    if side:
        row = data.iloc[-1]
        gross = row["close"] / entry - 1 if side == "long" else entry / row["close"] - 1
        trades.append({"entry": entry, "exit": row["close"], "side": side, "return": gross - COST_RATE - FIXED_COST / entry})
    equity = peak = 1.0
    max_dd = 0.0
    for trade in trades:
        equity *= 1 + trade["return"]
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    return trades, {"trades": len(trades), "win_rate_pct": round(100 * sum(t["return"] > 0 for t in trades) / len(trades), 2) if trades else None,
                    "net_return_pct": round(100 * (equity - 1), 2), "max_drawdown_pct": round(100 * max_dd, 2),
                    "profit_factor": round(sum(t["return"] for t in trades if t["return"] > 0) / abs(sum(t["return"] for t in trades if t["return"] <= 0)), 2) if any(t["return"] <= 0 for t in trades) else None}


def main() -> None:
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=token)
    data = add_indicator(fetch_history(client, datetime.now(IST)))
    split = data["timestamp"].min() + (data["timestamp"].max() - data["timestamp"].min()) / 2
    _, in_sample = simulate(data[data["timestamp"] < split].reset_index(drop=True))
    _, out_sample = simulate(data[data["timestamp"] >= split].reset_index(drop=True))
    print(json.dumps({"indicator": "Pinaki Das Supertrend", "symbol": SYMBOL, "resolution": "15m", "bars": len(data),
                      "rules": "Supertrend flip plus EMA-21 slope normalized by ATR; next-bar-open entry; opposite confirmed flip or 15:00 exit; cost proxy included",
                      "first_half": in_sample, "final_half_out_of_sample": out_sample}, indent=2))


if __name__ == "__main__":
    main()
