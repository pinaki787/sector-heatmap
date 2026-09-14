"""Read-only FYERS comparison: baseline EMA Band versus its slope-filtered variant.

This is an underlying-futures proxy, not an options-premium backtest.  It uses
completed five-minute fixed-contract candles, next-bar-open fills, an EMA-band
exit, and a conservative round-trip price cost proxy.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fyers_apiv3 import fyersModel

from sector_heatmap.config import load_config
from sector_heatmap.web import ema_band_resistance_volume_exit, ema_band_slope_regime


SYMBOL = "MCX:CRUDEOIL26SEPFUT"
RESOLUTION = "5"
EMA_LENGTH = 21
SLOPE_LOOKBACK = 8
MINIMUM_SLOPE_ATR = 0.10
ROUND_TRIP_COST_RATE = 0.0004
IST = ZoneInfo("Asia/Kolkata")


def completed_candles():
    config = load_config()
    token = config.get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("FYERS authentication is required for this read-only comparison.")
    app_id, access_token = token.split(":", 1)
    now = datetime.now(IST)
    response = fyersModel.FyersModel(client_id=app_id, token=access_token).history({
        "symbol": SYMBOL, "resolution": RESOLUTION, "date_format": 1,
        "range_from": (now - timedelta(days=45)).date().isoformat(),
        "range_to": now.date().isoformat(), "cont_flag": 0, "oi_flag": 1,
    })
    if response.get("s") != "ok":
        raise RuntimeError(f"FYERS history unavailable: {response.get('message') or 'unknown error'}")
    interval = int(RESOLUTION) * 60
    return [
        {"timestamp": int(row[0]), "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]) if len(row) > 5 else 0.0}
        for row in response.get("candles", []) if len(row) >= 5 and int(row[0]) + interval <= now.timestamp()
    ]


def ema(values, length):
    alpha, output = 2 / (length + 1), []
    for value in values:
        output.append(value if not output else alpha * value + (1 - alpha) * output[-1])
    return output


def run(candles, slope_filter, resistance_volume_exit=False):
    highs = ema([bar["high"] for bar in candles], EMA_LENGTH)
    lows = ema([bar["low"] for bar in candles], EMA_LENGTH)
    position = 0
    entry = None
    trades = []
    for index in range(max(EMA_LENGTH + 1, SLOPE_LOOKBACK + 2), len(candles) - 1):
        prior, current, fill = candles[index - 1], candles[index], candles[index + 1]
        weak_resistance = resistance_volume_exit and position > 0 and current["close"] > entry and ema_band_resistance_volume_exit(candles[:index + 1], 20, 1.5)["exit"]
        if position and (lows[index] <= current["close"] <= highs[index] or weak_resistance):
            exit_price = fill["open"]
            gross = (exit_price - entry) * position
            cost = ROUND_TRIP_COST_RATE * (entry + exit_price)
            trades.append({"entry": entry, "exit": exit_price, "side": position, "net": gross - cost})
            position = 0
            entry = None
            continue
        if position:
            continue
        midpoint = (prior["high"] + prior["low"]) / 2
        bullish = prior["open"] <= highs[index - 1] and prior["close"] > highs[index - 1] and current["close"] > current["open"] and current["open"] > midpoint
        bearish = prior["open"] >= lows[index - 1] and prior["close"] < lows[index - 1] and current["close"] < current["open"] and current["open"] < midpoint
        if not (bullish or bearish):
            continue
        if slope_filter and not ema_band_slope_regime(candles[:index + 1], EMA_LENGTH, SLOPE_LOOKBACK, MINIMUM_SLOPE_ATR)["pass"]:
            continue
        position = 1 if bullish else -1
        entry = fill["open"]
    return trades


def metrics(trades):
    net = sum(trade["net"] for trade in trades)
    wins = sum(trade["net"] > 0 for trade in trades)
    equity = peak = drawdown = 0.0
    for trade in trades:
        equity += trade["net"]
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)
    return {"trades": len(trades), "win_rate": 100 * wins / len(trades) if trades else 0.0, "net_points": net, "max_drawdown_points": drawdown}


def print_comparison(candles, days):
    cutoff = datetime.now(IST).timestamp() - days * 86400
    sample = [bar for bar in candles if bar["timestamp"] >= cutoff]
    baseline = metrics(run(sample, slope_filter=False))
    filtered = metrics(run(sample, slope_filter=True))
    protected = metrics(run(sample, slope_filter=True, resistance_volume_exit=True))
    print(f"{days}D | baseline {baseline} | slope-filtered {filtered} | slope-plus-resistance-exit {protected}")


if __name__ == "__main__":
    candles = completed_candles()
    print(f"{SYMBOL} | completed {RESOLUTION}-minute candles: {len(candles)} | proxy cost: {ROUND_TRIP_COST_RATE:.04%} round trip")
    for horizon in (7, 30, 45):
        print_comparison(candles, horizon)
