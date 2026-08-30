"""Dependency-free technical indicators used by the sector domain engine."""
from datetime import datetime
from math import isfinite
from statistics import fmean
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def ema(values, length):
    if not values:
        return []
    alpha = 2.0 / (length + 1)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1 - alpha) * result[-1])
    return result


def true_ranges(candles):
    if not candles:
        return []
    result = [float(candles[0]["high"]) - float(candles[0]["low"])]
    for previous, current in zip(candles, candles[1:]):
        high, low, previous_close = float(current["high"]), float(current["low"]), float(previous["close"])
        result.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return result


def wilder_series(values, length):
    result = [None] * len(values)
    if len(values) < length:
        return result
    average = fmean(float(value) for value in values[:length])
    result[length - 1] = average
    for index in range(length, len(values)):
        average = ((average * (length - 1)) + float(values[index])) / length
        result[index] = average
    return result


def atr(candles, length=14):
    values = wilder_series(true_ranges(candles), length)
    return values[-1] if values else None


def rsi(values, length=14):
    if len(values) <= length:
        return None
    changes = [float(current) - float(previous) for previous, current in zip(values, values[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain, average_loss = fmean(gains[:length]), fmean(losses[:length])
    for gain, loss in zip(gains[length:], losses[length:]):
        average_gain = ((average_gain * (length - 1)) + gain) / length
        average_loss = ((average_loss * (length - 1)) + loss) / length
    if average_loss == 0:
        return 100.0 if average_gain else 50.0
    return 100.0 - (100.0 / (1.0 + average_gain / average_loss))


def roc(values, length=10):
    if len(values) <= length or not values[-1 - length]:
        return None
    return (float(values[-1]) / float(values[-1 - length]) - 1.0) * 100.0


def normalized_slope(series, atr_value, lookback=5):
    if len(series) <= lookback or not atr_value:
        return None
    return (float(series[-1]) - float(series[-1 - lookback])) / (lookback * float(atr_value))


def adx_dmi(candles, length=14):
    if len(candles) < length * 2 + 1:
        return None, None, None
    true_range, plus_dm, minus_dm = [], [], []
    for previous, current in zip(candles, candles[1:]):
        high, low = float(current["high"]), float(current["low"])
        previous_high, previous_low, previous_close = float(previous["high"]), float(previous["low"]), float(previous["close"])
        true_range.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        up_move, down_move = high - previous_high, previous_low - low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
    smoothed_tr = sum(true_range[:length])
    smoothed_plus, smoothed_minus = sum(plus_dm[:length]), sum(minus_dm[:length])
    dx_values, plus_di, minus_di = [], 0.0, 0.0
    for index in range(length - 1, len(true_range)):
        if index >= length:
            smoothed_tr = smoothed_tr - smoothed_tr / length + true_range[index]
            smoothed_plus = smoothed_plus - smoothed_plus / length + plus_dm[index]
            smoothed_minus = smoothed_minus - smoothed_minus / length + minus_dm[index]
        if not smoothed_tr:
            continue
        plus_di, minus_di = 100 * smoothed_plus / smoothed_tr, 100 * smoothed_minus / smoothed_tr
        denominator = plus_di + minus_di
        dx_values.append(100 * abs(plus_di - minus_di) / denominator if denominator else 0.0)
    if len(dx_values) < length:
        return None, plus_di, minus_di
    adx_value = fmean(dx_values[:length])
    for value in dx_values[length:]:
        adx_value = ((adx_value * (length - 1)) + value) / length
    return adx_value, plus_di, minus_di


def resample_weekly(candles):
    groups = []
    for candle in candles:
        moment = datetime.fromtimestamp(int(candle["timestamp"]), IST)
        key = moment.isocalendar()[:2]
        if not groups or groups[-1][0] != key:
            groups.append((key, dict(candle)))
            continue
        aggregate = groups[-1][1]
        aggregate["high"] = max(float(aggregate["high"]), float(candle["high"]))
        aggregate["low"] = min(float(aggregate["low"]), float(candle["low"]))
        aggregate["close"] = float(candle["close"])
        aggregate["volume"] = float(aggregate.get("volume", 0) or 0) + float(candle.get("volume", 0) or 0)
        aggregate["timestamp"] = int(candle["timestamp"])
    return [candle for _, candle in groups]


def align_closes(sector_candles, benchmark_candles):
    benchmark = {int(candle["timestamp"]): float(candle["close"]) for candle in benchmark_candles}
    pairs = [(float(candle["close"]), benchmark[int(candle["timestamp"])]) for candle in sector_candles if int(candle["timestamp"]) in benchmark and benchmark[int(candle["timestamp"])] != 0]
    return pairs


def breadth_score(constituents):
    usable = [item for item in constituents if item.get("close") is not None]
    if not usable:
        return None, {"status": "UNAVAILABLE", "reason": "Constituent candle data is unavailable"}
    metrics = {}
    predicates = {
        "above_ema20_pct": lambda item: item.get("ema20") is not None and item["close"] > item["ema20"],
        "above_ema50_pct": lambda item: item.get("ema50") is not None and item["close"] > item["ema50"],
        "above_ema200_pct": lambda item: item.get("ema200") is not None and item["close"] > item["ema200"],
        "advancing_pct": lambda item: item.get("change", 0) > 0,
        "outperforming_pct": lambda item: item.get("relative_strength_score", 50) > 50,
    }
    available_scores = []
    for key, predicate in predicates.items():
        relevant = [item for item in usable if key not in {"above_ema20_pct", "above_ema50_pct", "above_ema200_pct"} or item.get(key.replace("above_", "").replace("_pct", "")) is not None]
        if relevant:
            metrics[key] = 100.0 * sum(bool(predicate(item)) for item in relevant) / len(relevant)
            available_scores.append(metrics[key])
    score = fmean(available_scores) if available_scores else None
    return (round(score, 2) if score is not None else None), {"status": "DELAYED" if score is not None else "UNAVAILABLE", **metrics}


def volume_participation_score(constituents):
    usable = [item for item in constituents if item.get("volume") is not None and item.get("average_volume20")]
    if not usable:
        return None, {"status": "UNAVAILABLE", "reason": "Reliable constituent volume history is unavailable"}
    relative_volumes = [float(item["volume"]) / float(item["average_volume20"]) for item in usable]
    above_average = 100.0 * sum(value > 1 for value in relative_volumes) / len(relative_volumes)
    expansion = 100.0 * sum(value >= 1.5 for value in relative_volumes) / len(relative_volumes)
    normalized_relative = clamp(fmean(relative_volumes) * 50.0)
    score = 0.4 * above_average + 0.35 * normalized_relative + 0.25 * expansion
    return round(score, 2), {"status": "DELAYED", "above_average_pct": round(above_average, 2), "average_relative_volume": round(fmean(relative_volumes), 2), "expansion_pct": round(expansion, 2)}


def finite_or_none(value):
    return float(value) if value is not None and isfinite(float(value)) else None
