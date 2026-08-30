"""Explainable multi-timeframe sector scoring, ranking, and rotation logic."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import tanh
from statistics import fmean
from typing import Optional
from zoneinfo import ZoneInfo

from .analysis_config import (
    ADX_LENGTH, ADX_THRESHOLDS, ATR_LENGTH, EMA_LENGTHS, MINIMUM_CANDLES,
    MOMENTUM_WEIGHTS, MTF_MODES, ROC_LENGTH, ROTATION, RSI_LENGTH,
    RSI_THRESHOLDS, RS_EMA_LENGTH, SECTOR_SCORE_WEIGHTS, SLOPE_LOOKBACK,
    TREND_WEIGHTS,
)
from .indicators import (
    adx_dmi, align_closes, atr, breadth_score, clamp, ema, normalized_slope,
    roc, rsi, volume_participation_score,
)


STATE_LABELS = {2: "Strong Bullish", 1: "Bullish", 0: "Neutral", -1: "Bearish", -2: "Strong Bearish"}
IST = ZoneInfo("Asia/Kolkata")


@dataclass
class TimeframeTrendState:
    timeframe: str
    state: Optional[int] = None
    score: Optional[float] = None
    label: str = "Unavailable"
    close: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None
    ema20_slope: Optional[float] = None
    ema50_slope: Optional[float] = None
    rsi: Optional[float] = None
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None
    momentum_score: Optional[float] = None
    relative_strength_score: Optional[float] = None
    relative_strength_state: str = "Unavailable"
    relative_strength_slope: Optional[float] = None
    relative_strength_roc: Optional[float] = None
    reasons: list[str] = field(default_factory=list)
    data_quality: str = "UNAVAILABLE"
    missing_components: list[str] = field(default_factory=list)
    last_updated: Optional[str] = None
    series: list[dict] = field(default_factory=list)


@dataclass
class SectorAnalysis:
    sector_id: str
    symbol: str
    name: str
    mode: str
    timeframe_states: dict[str, dict]
    trend_score: Optional[float]
    relative_strength_score: Optional[float]
    relative_strength_state: str
    momentum_score: Optional[float]
    breadth_score: Optional[float]
    volume_score: Optional[float]
    overall_score: Optional[float]
    rank: Optional[int] = None
    previous_rank: Optional[int] = None
    rank_change: Optional[int] = None
    rotation_state: str = "NEUTRAL"
    acceleration_state: str = "STABLE"
    mtf_alignment: str = "MIXED"
    adx: Optional[float] = None
    last_updated: Optional[str] = None
    data_quality: str = "UNAVAILABLE"
    missing_components: list[str] = field(default_factory=list)
    component_weights: dict[str, float] = field(default_factory=dict)
    explanations: list[str] = field(default_factory=list)


def _round(value, digits=2):
    return round(float(value), digits) if value is not None else None


def state_from_score(score):
    if score is None:
        return None
    if score >= 80:
        return 2
    if score >= 60:
        return 1
    if score <= 20:
        return -2
    if score <= 40:
        return -1
    return 0


def rsi_state(value):
    if value is None:
        return 0, "RSI unavailable"
    if value >= RSI_THRESHOLDS["strong_bullish"]:
        return 2, "Strong bullish momentum"
    if value >= RSI_THRESHOLDS["bullish"]:
        return 1, "Bullish momentum"
    if value <= RSI_THRESHOLDS["strong_bearish"]:
        return -2, "Strong bearish momentum"
    if value <= RSI_THRESHOLDS["bearish"]:
        return -1, "Bearish momentum"
    return 0, "Neutral momentum"


def _structure_score(close, ema20, ema50, ema200):
    comparisons = (close > ema20, close > ema50, close > ema200, ema20 > ema50, ema50 > ema200)
    return 100.0 * sum(comparisons) / len(comparisons)


def _relative_strength(pairs):
    if len(pairs) <= max(RS_EMA_LENGTH, ROC_LENGTH, SLOPE_LOOKBACK):
        return None, "Unavailable", None, None, []
    ratios = [sector / benchmark for sector, benchmark in pairs]
    average = ema(ratios, RS_EMA_LENGTH)
    slope = (ratios[-1] / ratios[-1 - SLOPE_LOOKBACK] - 1.0) * 100.0
    change = roc(ratios, ROC_LENGTH)
    position = 1 if ratios[-1] > average[-1] else -1
    score = clamp(50 + position * 15 + 20 * tanh(slope / 1.5) + 15 * tanh((change or 0) / 3.0))
    if score >= 70:
        label = "Strong Outperformer"
    elif score >= 58:
        label = "Outperformer"
    elif score <= 30:
        label = "Strong Underperformer"
    elif score <= 42:
        label = "Underperformer"
    else:
        label = "Neutral"
    reasons = [f"RS is {'above' if position > 0 else 'below'} its EMA{RS_EMA_LENGTH}", f"RS slope {slope:+.2f}% over {SLOPE_LOOKBACK} bars", f"RS ROC{ROC_LENGTH} {(change or 0):+.2f}%"]
    return score, label, slope, change, reasons


def calculate_timeframe_state(timeframe, candles, benchmark_candles, data_quality="DELAYED"):
    state = TimeframeTrendState(timeframe=timeframe, data_quality=data_quality)
    if not candles:
        state.reasons.append("Sector candle history is unavailable")
        return asdict(state)
    state.last_updated = datetime.fromtimestamp(int(candles[-1]["timestamp"]), timezone.utc).astimezone(IST).isoformat()
    if len(candles) < MINIMUM_CANDLES:
        state.data_quality = "INSUFFICIENT DATA"
        state.missing_components.append(f"minimum {MINIMUM_CANDLES} completed candles")
        state.reasons.append(f"Only {len(candles)} completed candles are available")
        return asdict(state)

    closes = [float(candle["close"]) for candle in candles]
    ema20_series, ema50_series, ema200_series = (ema(closes, length) for length in EMA_LENGTHS)
    atr_value = atr(candles, ATR_LENGTH)
    ema20_slope = normalized_slope(ema20_series, atr_value, SLOPE_LOOKBACK)
    ema50_slope = normalized_slope(ema50_series, atr_value, SLOPE_LOOKBACK)
    rsi_value = rsi(closes, RSI_LENGTH)
    adx_value, plus_di, minus_di = adx_dmi(candles, ADX_LENGTH)
    close, ema20_value, ema50_value, ema200_value = closes[-1], ema20_series[-1], ema50_series[-1], ema200_series[-1]

    structure = _structure_score(close, ema20_value, ema50_value, ema200_value)
    slope_score = clamp(50 + 25 * tanh((ema20_slope or 0) * 3) + 25 * tanh((ema50_slope or 0) * 3))
    rsi_score_value = clamp(rsi_value if rsi_value is not None else 50)
    direction = 1 if plus_di is not None and minus_di is not None and plus_di > minus_di else -1
    dmi_strength = clamp((adx_value or 0) / 40.0, 0, 1)
    dmi_score = clamp(50 + direction * 50 * dmi_strength)
    trend_score = sum({"structure": structure, "slope": slope_score, "rsi": rsi_score_value, "dmi": dmi_score}[key] * weight for key, weight in TREND_WEIGHTS.items())
    trend_state = state_from_score(trend_score)

    price_roc = roc(closes, ROC_LENGTH)
    momentum_parts = {
        "rsi": rsi_score_value,
        "roc": clamp(50 + 50 * tanh((price_roc or 0) / 5.0)),
        "ema_slope": clamp(50 + 50 * tanh((ema20_slope or 0) * 3.0)),
    }
    momentum_score = sum(momentum_parts[key] * weight for key, weight in MOMENTUM_WEIGHTS.items())
    rs_score, rs_label, rs_slope, rs_roc, rs_reasons = _relative_strength(align_closes(candles, benchmark_candles))

    if close > ema20_value > ema50_value > ema200_value:
        state.reasons.append("Close > EMA20 > EMA50 > EMA200")
    elif close < ema20_value < ema50_value < ema200_value:
        state.reasons.append("Close < EMA20 < EMA50 < EMA200")
    else:
        state.reasons.append("EMA structure is mixed")
    state.reasons.extend([
        f"EMA20 slope {'rising' if (ema20_slope or 0) > 0.02 else 'falling' if (ema20_slope or 0) < -0.02 else 'flat'} ({(ema20_slope or 0):+.3f} ATR/bar)",
        f"EMA50 slope {'rising' if (ema50_slope or 0) > 0.02 else 'falling' if (ema50_slope or 0) < -0.02 else 'flat'} ({(ema50_slope or 0):+.3f} ATR/bar)",
        f"RSI{RSI_LENGTH} {rsi_value:.1f}: {rsi_state(rsi_value)[1]}",
        f"ADX{ADX_LENGTH} {adx_value:.1f}: {'strong' if adx_value >= ADX_THRESHOLDS['strong'] else 'developing' if adx_value >= ADX_THRESHOLDS['developing'] else 'weak'} trend, {'+DI > -DI' if direction > 0 else '-DI > +DI'}",
        *rs_reasons,
    ])
    if rs_score is None:
        state.missing_components.append("relative strength benchmark alignment")

    state.state, state.score, state.label = trend_state, _round(trend_score), STATE_LABELS[trend_state]
    state.close, state.ema20, state.ema50, state.ema200 = map(_round, (close, ema20_value, ema50_value, ema200_value))
    state.ema20_slope, state.ema50_slope = _round(ema20_slope, 4), _round(ema50_slope, 4)
    state.rsi, state.adx, state.plus_di, state.minus_di = map(_round, (rsi_value, adx_value, plus_di, minus_di))
    state.momentum_score = _round(momentum_score)
    state.relative_strength_score, state.relative_strength_state = _round(rs_score), rs_label
    state.relative_strength_slope, state.relative_strength_roc = _round(rs_slope), _round(rs_roc)
    start = max(0, len(candles) - 60)
    state.series = [{"timestamp": int(candles[index]["timestamp"]), "close": _round(closes[index]), "ema20": _round(ema20_series[index]), "ema50": _round(ema50_series[index]), "ema200": _round(ema200_series[index])} for index in range(start, len(candles))]
    return asdict(state)


def weighted_available(values, weights):
    available = {key: float(value) for key, value in values.items() if value is not None and weights.get(key, 0) > 0}
    total_weight = sum(weights[key] for key in available)
    if not available or total_weight <= 0:
        return None, {}
    effective = {key: weights[key] / total_weight for key in available}
    return sum(available[key] * effective[key] for key in available), effective


def mtf_alignment(timeframe_states):
    values = {key: value.get("state") for key, value in timeframe_states.items() if value.get("state") is not None}
    if not values:
        return "UNAVAILABLE"
    states = list(values.values())
    if len(states) == 4 and all(value >= 1 for value in states):
        return "FULL BULLISH ALIGNMENT"
    if len(states) == 4 and all(value <= -1 for value in states):
        return "FULL BEARISH ALIGNMENT"
    daily_weekly = [values.get("daily"), values.get("weekly")]
    if all(value is not None and value >= 1 for value in daily_weekly):
        return "BULLISH ALIGNMENT"
    if all(value is not None and value <= -1 for value in daily_weekly):
        return "BEARISH ALIGNMENT"
    return "MIXED"


def calculate_sector(sector, timeframe_states, mode="intraday", constituent_metrics=None):
    mode_weights = MTF_MODES.get(mode, MTF_MODES["intraday"])
    trend, _ = weighted_available({key: value.get("score") for key, value in timeframe_states.items()}, mode_weights)
    relative_strength, _ = weighted_available({key: value.get("relative_strength_score") for key, value in timeframe_states.items()}, mode_weights)
    momentum, _ = weighted_available({key: value.get("momentum_score") for key, value in timeframe_states.items()}, mode_weights)
    adx_value, _ = weighted_available({key: value.get("adx") for key, value in timeframe_states.items()}, mode_weights)
    breadth, breadth_details = breadth_score((constituent_metrics or {}).get("breadth", []))
    volume, volume_details = volume_participation_score((constituent_metrics or {}).get("volume", []))
    components = {"trend": trend, "relative_strength": relative_strength, "breadth": breadth, "volume": volume, "momentum": momentum}
    overall, effective_weights = weighted_available(components, SECTOR_SCORE_WEIGHTS)
    missing = [key for key, value in components.items() if value is None]
    quality_values = [value.get("data_quality") for value in timeframe_states.values()]
    quality = "UNAVAILABLE" if all(value == "UNAVAILABLE" for value in quality_values) else "INSUFFICIENT DATA" if all(value in {"UNAVAILABLE", "INSUFFICIENT DATA"} for value in quality_values) else "STALE" if "STALE" in quality_values else "DELAYED"
    latest = max((value.get("last_updated") for value in timeframe_states.values() if value.get("last_updated")), default=None)
    rs_label = "Unavailable"
    if relative_strength is not None:
        rs_label = "Strong Outperformer" if relative_strength >= 70 else "Outperformer" if relative_strength >= 58 else "Strong Underperformer" if relative_strength <= 30 else "Underperformer" if relative_strength <= 42 else "Neutral"
    explanations = [f"{key.replace('_', ' ').title()} contributes {effective_weights[key] * 100:.1f}% after missing-metric redistribution" for key in effective_weights]
    if breadth is None:
        explanations.append(breadth_details["reason"])
    if volume is None:
        explanations.append(volume_details["reason"])
    result = SectorAnalysis(
        sector_id=sector.sector_id, symbol=sector.symbol, name=sector.name, mode=mode,
        timeframe_states=timeframe_states, trend_score=_round(trend), relative_strength_score=_round(relative_strength), relative_strength_state=rs_label,
        momentum_score=_round(momentum), breadth_score=_round(breadth), volume_score=_round(volume), overall_score=_round(overall),
        mtf_alignment=mtf_alignment(timeframe_states), adx=_round(adx_value), last_updated=latest,
        data_quality=quality, missing_components=missing, component_weights={key: _round(value * 100) for key, value in effective_weights.items()}, explanations=explanations,
    )
    return asdict(result)


def rank_sectors(sectors, previous_ranks=None):
    ordered = sorted(sectors, key=lambda item: (item.get("overall_score") is None, -(item.get("overall_score") or 0), item["name"]))
    previous_ranks = previous_ranks or {}
    for index, sector in enumerate(ordered, 1):
        if sector.get("overall_score") is None:
            sector["rank"] = None
        else:
            sector["rank"] = index
        previous = previous_ranks.get(sector["sector_id"])
        sector["previous_rank"] = previous
        sector["rank_change"] = previous - sector["rank"] if previous is not None and sector["rank"] is not None else None
    return ordered


def classify_rotation(current, history):
    usable = [point for point in history if point.get("overall_score") is not None and point.get("rank") is not None]
    if current.get("overall_score") is None or current.get("rank") is None or len(usable) < ROTATION["minimum_snapshots"]:
        return "NEUTRAL", "STABLE", 0.0
    previous = usable[-1]
    score_velocity = current["overall_score"] - previous["overall_score"]
    rank_velocity = previous["rank"] - current["rank"]
    if current["overall_score"] >= ROTATION["leading_score"] and score_velocity >= 0 and rank_velocity >= 0:
        state = "LEADING"
    elif current["overall_score"] <= ROTATION["lagging_score"] and score_velocity <= 0:
        state = "LAGGING"
    elif score_velocity > ROTATION["velocity_threshold"] or rank_velocity > 0:
        state = "IMPROVING"
    elif score_velocity < -ROTATION["velocity_threshold"] or rank_velocity < 0:
        state = "WEAKENING"
    else:
        state = "NEUTRAL"
    acceleration = "STABLE"
    if len(usable) >= 2:
        prior_velocity = previous["overall_score"] - usable[-2]["overall_score"]
        change = score_velocity - prior_velocity
        if change > ROTATION["acceleration_threshold"]:
            acceleration = "ACCELERATING"
        elif change < -ROTATION["acceleration_threshold"]:
            acceleration = "DECELERATING"
    return state, acceleration, _round(score_velocity)


def detect_events(previous, current):
    if not previous:
        return []
    events = []
    previous_top, current_top = (previous.get("rank") or 999) <= 3, (current.get("rank") or 999) <= 3
    if previous_top != current_top:
        events.append({"type": "TOP_3_ENTERED" if current_top else "TOP_3_EXITED", "sector_id": current["sector_id"]})
    for key, event_type in (("rotation_state", "ROTATION_CHANGED"), ("mtf_alignment", "MTF_ALIGNMENT_CHANGED"), ("relative_strength_state", "RELATIVE_STRENGTH_CHANGED")):
        if previous.get(key) != current.get(key):
            events.append({"type": event_type, "sector_id": current["sector_id"], "from": previous.get(key), "to": current.get(key)})
    return events


def market_overview(sectors, benchmark_states):
    available = [sector for sector in sectors if sector.get("overall_score") is not None]
    daily_weekly_bullish = sum(sector["mtf_alignment"] in {"FULL BULLISH ALIGNMENT", "BULLISH ALIGNMENT"} for sector in available)
    bullish = sum((sector.get("timeframe_states", {}).get("daily", {}).get("state") or 0) > 0 for sector in available)
    benchmark_daily = benchmark_states.get("daily", {}).get("state")
    benchmark_weekly = benchmark_states.get("weekly", {}).get("state")
    alignment_ratio = daily_weekly_bullish / len(available) if available else 0
    regime_score = (benchmark_daily or 0) + (benchmark_weekly or 0) + (1 if alignment_ratio >= 0.6 else -1 if alignment_ratio <= 0.3 else 0)
    regime = "STRONGLY BULLISH" if regime_score >= 4 else "BULLISH" if regime_score >= 2 else "STRONGLY BEARISH" if regime_score <= -4 else "BEARISH" if regime_score <= -2 else "NEUTRAL"
    by_rotation = {state: [sector["name"] for sector in available if sector["rotation_state"] == state][:4] for state in ("LEADING", "IMPROVING", "NEUTRAL", "WEAKENING", "LAGGING")}
    return {
        "market_regime": regime,
        "sector_breadth": {"bullish": bullish, "total": len(available)},
        "daily_weekly_bullish_alignment": {"count": daily_weekly_bullish, "total": len(available)},
        "strong_outperformers": sum(sector.get("relative_strength_state") == "Strong Outperformer" for sector in available),
        "strong_underperformers": sum(sector.get("relative_strength_state") == "Strong Underperformer" for sector in available),
        **{key.lower(): value for key, value in by_rotation.items()},
    }
