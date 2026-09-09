#!/usr/bin/env python3
"""Read-only FYERS NIFTY daily swing snapshot; never sends an order."""
from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import sys

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sector_heatmap.config import load_config


def ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    value = values[0]
    for close in values[1:]:
        value = alpha * close + (1 - alpha) * value
    return value


def rsi(values: list[float], period: int = 14) -> float:
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0) for change in changes[-period:]]
    losses = [max(-change, 0) for change in changes[-period:]]
    avg_gain, avg_loss = sum(gains) / period, sum(losses) / period
    return 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)


def main() -> None:
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("A current FYERS token is required.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    today = date.today()
    response = client.history({"symbol": "NSE:NIFTY50-INDEX", "resolution": "D", "date_format": "1", "range_from": (today - timedelta(days=150)).isoformat(), "range_to": today.isoformat(), "cont_flag": "1"})
    if response.get("s") != "ok":
        raise RuntimeError(response.get("message") or "FYERS daily history unavailable")
    candles = response.get("candles") or []
    closes = [float(row[4]) for row in candles]
    latest = candles[-1]
    # Today's daily candle may still be forming; use only the last completed daily close for trend.
    completed = candles[:-1]
    completed_closes = [float(row[4]) for row in completed]
    last = completed[-1]
    last_close = completed_closes[-1]
    ema20, ema50 = ema(completed_closes[-50:], 20), ema(completed_closes[-50:], 50)
    high20 = max(float(row[2]) for row in completed[-20:])
    low20 = min(float(row[3]) for row in completed[-20:])
    output = {
        "completed_daily_close": last_close,
        "today_live_close": float(latest[4]),
        "ema20": round(ema20, 2), "ema50": round(ema50, 2), "rsi14": round(rsi(completed_closes), 2),
        "twenty_day_high": high20, "twenty_day_low": low20,
        "trend": "BULLISH" if last_close > ema20 > ema50 else "BEARISH" if last_close < ema20 < ema50 else "MIXED",
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
