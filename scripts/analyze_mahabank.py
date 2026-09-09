#!/usr/bin/env python3
"""Read-only FYERS evidence snapshot for NSE:MAHABANK-EQ.

Fetches a quote, market depth, and completed 60-minute/daily candles without
printing credentials or submitting orders.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import math
import sys

from fyers_apiv3 import fyersModel

from sector_heatmap.config import load_config
from sector_heatmap.market_calendar import IST


SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "NSE:MAHABANK-EQ"


def ema(values, period):
    multiplier = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = value * multiplier + result * (1 - multiplier)
    return result


def rsi(values, period=14):
    if len(values) < period + 1:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0:
        return 100.0
    return 100 - 100 / (1 + average_gain / average_loss)


def adx(rows, period=14):
    if len(rows) < period * 2 + 1:
        return None
    tr, plus_dm, minus_dm = [], [], []
    for previous, current in zip(rows, rows[1:]):
        up = current[2] - previous[2]
        down = previous[3] - current[3]
        tr.append(max(current[2] - current[3], abs(current[2] - previous[4]), abs(current[3] - previous[4])))
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    smooth_tr, smooth_plus, smooth_minus = sum(tr[:period]), sum(plus_dm[:period]), sum(minus_dm[:period])
    dx_values = []
    for index in range(period, len(tr)):
        if index > period:
            smooth_tr = smooth_tr - smooth_tr / period + tr[index]
            smooth_plus = smooth_plus - smooth_plus / period + plus_dm[index]
            smooth_minus = smooth_minus - smooth_minus / period + minus_dm[index]
        plus_di = 100 * smooth_plus / smooth_tr if smooth_tr else 0
        minus_di = 100 * smooth_minus / smooth_tr if smooth_tr else 0
        denominator = plus_di + minus_di
        dx_values.append(100 * abs(plus_di - minus_di) / denominator if denominator else 0)
    if len(dx_values) < period:
        return None
    value = sum(dx_values[:period]) / period
    for dx in dx_values[period:]:
        value = (value * (period - 1) + dx) / period
    return value


def completed(rows, resolution):
    now = datetime.now(IST)
    minutes = int(resolution) if resolution.isdigit() else None
    result = []
    for row in rows:
        candle_time = datetime.fromtimestamp(row[0], IST)
        if minutes is None:
            if candle_time.date() < now.date() or now.hour > 15 or (now.hour == 15 and now.minute >= 30):
                result.append(row)
        elif candle_time + timedelta(minutes=minutes) <= now:
            result.append(row)
    return result


def history(client, resolution, days):
    today = datetime.now(IST).date()
    response = client.history({"symbol": SYMBOL, "resolution": resolution, "date_format": "1", "range_from": (today - timedelta(days=days)).isoformat(), "range_to": today.isoformat(), "cont_flag": "1"})
    if response.get("s") != "ok" or not response.get("candles"):
        raise RuntimeError(response.get("message") or f"FYERS history failed for {resolution}")
    return completed(response["candles"], resolution)


def summarize(rows):
    closes = [row[4] for row in rows]
    last = rows[-1]
    average_volume = sum(row[5] for row in rows[-21:-1]) / min(20, len(rows) - 1)
    return {
        "completed_at": datetime.fromtimestamp(last[0], IST).isoformat(),
        "ohlcv": {"open": last[1], "high": last[2], "low": last[3], "close": last[4], "volume": last[5]},
        "ema_21": round(ema(closes[-80:], 21), 2),
        "ema_50": round(ema(closes[-100:], 50), 2),
        "rsi_14": round(rsi(closes[-100:]), 2),
        "adx_14": round(adx(rows[-100:]), 2),
        "volume_vs_20_bar_average": round(last[5] / average_volume, 2) if average_volume else None,
        "prior_20_bar_high": max(row[2] for row in rows[-21:-1]),
        "prior_20_bar_low": min(row[3] for row in rows[-21:-1]),
    }


def main():
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("No reusable FYERS token is configured.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    quote = client.quotes({"symbols": SYMBOL})
    depth = client.depth({"symbol": SYMBOL, "ohlcv_flag": "1"})
    hourly, daily = history(client, "60", 90), history(client, "D", 180)
    if quote.get("s") != "ok" or depth.get("s") != "ok":
        raise RuntimeError((quote if quote.get("s") != "ok" else depth).get("message") or "FYERS quote/depth unavailable")
    values = quote["d"][0]["v"]
    book = depth["d"][SYMBOL]
    print(json.dumps({
        "symbol": SYMBOL,
        "fetched_at": datetime.now(IST).isoformat(),
        "quote": {key: values.get(key) for key in ("lp", "ch", "chp", "open_price", "high_price", "low_price", "prev_close_price", "volume", "bid", "ask", "tt")},
        "depth": {"ltp": book.get("ltp"), "totalbuyqty": book.get("totalbuyqty"), "totalsellqty": book.get("totalsellqty"), "top_bid": (book.get("bids") or [{}])[0], "top_ask": (book.get("ask") or [{}])[0]},
        "hourly": summarize(hourly),
        "daily": summarize(daily),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
