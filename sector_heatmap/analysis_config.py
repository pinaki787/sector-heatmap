"""Central configuration for deterministic multi-timeframe sector analysis."""

TIMEFRAMES = {
    "15m": {"resolution": "15", "lookback_days": 45, "ttl_seconds": 15 * 60, "stale_seconds": 2 * 60 * 60},
    "1h": {"resolution": "60", "lookback_days": 180, "ttl_seconds": 60 * 60, "stale_seconds": 4 * 60 * 60},
    # Daily is retained long enough to derive Weekly EMA200 from the same cache.
    "daily": {"resolution": "D", "lookback_days": 1700, "ttl_seconds": 60 * 60, "stale_seconds": 4 * 24 * 60 * 60},
    "weekly": {"resolution": "D", "lookback_days": 1700, "ttl_seconds": 6 * 60 * 60, "stale_seconds": 11 * 24 * 60 * 60, "derive": "weekly"},
}

EMA_LENGTHS = (20, 50, 200)
RSI_LENGTH = 14
RSI_THRESHOLDS = {"strong_bullish": 60, "bullish": 55, "bearish": 45, "strong_bearish": 40}
ADX_LENGTH = 14
ADX_THRESHOLDS = {"strong": 25, "developing": 20}
ATR_LENGTH = 14
SLOPE_LOOKBACK = 5
ROC_LENGTH = 10
RS_EMA_LENGTH = 20
MINIMUM_CANDLES = 210

TREND_WEIGHTS = {"structure": 0.40, "slope": 0.20, "rsi": 0.20, "dmi": 0.20}
MOMENTUM_WEIGHTS = {"rsi": 0.45, "roc": 0.30, "ema_slope": 0.25}
SECTOR_SCORE_WEIGHTS = {"trend": 0.25, "relative_strength": 0.25, "breadth": 0.20, "volume": 0.15, "momentum": 0.15}
MTF_MODES = {
    "intraday": {"15m": 0.30, "1h": 0.40, "daily": 0.25, "weekly": 0.05},
    "swing": {"15m": 0.0, "1h": 0.10, "daily": 0.50, "weekly": 0.40},
}

ROTATION = {
    "minimum_snapshots": 2,
    "leading_score": 70,
    "improving_score": 55,
    "lagging_score": 35,
    "velocity_threshold": 1.0,
    "acceleration_threshold": 0.75,
    "history_limit": 120,
}

REFRESH_INTERVAL_SECONDS = 5 * 60
SNAPSHOT_INTERVAL_SECONDS = 15 * 60
HISTORY_RANGE_DAYS = {"today": 1, "5sessions": 8, "20sessions": 32}
