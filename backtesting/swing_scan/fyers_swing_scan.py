#!/usr/bin/env python3
"""Read-only completed-candle swing scan for selected NSE equities using FYERS."""
from __future__ import annotations

from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pandas as pd

from sector_heatmap.fyers_execution import _current_client

SYMBOLS = ("NSE:NTPC-EQ", "NSE:LT-EQ", "NSE:POWERGRID-EQ", "NSE:NIFTY50-INDEX")


def candles(client, symbol, resolution, days):
    end = int(datetime.now(ZoneInfo("Asia/Kolkata")).timestamp())
    raw = client.history({"symbol": symbol, "resolution": resolution, "date_format": "0",
                          "range_from": str(end - days * 86400), "range_to": str(end), "cont_flag": "1"})
    frame = pd.DataFrame(raw.get("candles") or [], columns=["ts", "open", "high", "low", "close", "volume"])
    if frame.empty:
        raise RuntimeError(f"No {resolution} candles for {symbol}: {raw}")
    return frame.astype(float)


def metrics(frame):
    close = frame.close
    previous = close.shift(1)
    tr = pd.concat([frame.high-frame.low, (frame.high-previous).abs(), (frame.low-previous).abs()], axis=1).max(axis=1)
    delta = close.diff()
    gains, losses = delta.clip(lower=0), -delta.clip(upper=0)
    rs = gains.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / losses.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    return {"close": round(close.iloc[-1], 2), "ema20": round(close.ewm(span=20, adjust=False).mean().iloc[-1], 2),
            "ema50": round(close.ewm(span=50, adjust=False).mean().iloc[-1], 2),
            "rsi14": round((100 - 100/(1+rs.iloc[-1])), 1),
            "atr14": round(tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean().iloc[-1], 2),
            "recent_high": round(frame.high.tail(20).max(), 2), "recent_low": round(frame.low.tail(20).min(), 2)}


def main():
    client = _current_client()
    report = {}
    for symbol in SYMBOLS:
        report[symbol] = {"daily": metrics(candles(client, symbol, "D", 100)),
                          "60m": metrics(candles(client, symbol, "60", 60)),
                          "15m": metrics(candles(client, symbol, "15", 15))}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
