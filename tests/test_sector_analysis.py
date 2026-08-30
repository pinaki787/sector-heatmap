from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sector_heatmap.analysis import (
    calculate_sector, calculate_timeframe_state, classify_rotation, detect_events,
    mtf_alignment, rank_sectors, rsi_state, weighted_available,
)
from sector_heatmap.analysis_config import MTF_MODES, SECTOR_SCORE_WEIGHTS
from sector_heatmap.indicators import (
    adx_dmi, breadth_score, ema, normalized_slope, rsi,
    volume_participation_score,
)
from sector_heatmap.sector_service import SectorAnalysisService
from sector_heatmap.sectors import SECTOR_DEFINITIONS


def candles(count=260, start=100.0, step=0.5, timestamp=None):
    first = timestamp or int((datetime.now() - timedelta(days=count)).timestamp())
    rows = []
    for index in range(count):
        close = start + index * step
        rows.append({"timestamp": first + index * 86400, "open": close - step / 2, "high": close + 1, "low": close - 1, "close": close, "volume": 1000 + index})
    return rows


def timeframe(score=70, state=1, rs=65, momentum=60, adx=25, quality="DELAYED"):
    return {"score": score, "state": state, "relative_strength_score": rs, "momentum_score": momentum, "adx": adx, "data_quality": quality, "last_updated": "2026-08-29T15:30:00+05:30", "series": []}


class IndicatorTests(unittest.TestCase):
    def test_ema_alignment_is_strong_bullish_for_ordered_uptrend(self):
        result = calculate_timeframe_state("daily", candles(), candles(step=0.2))
        self.assertEqual(result["state"], 2)
        self.assertIn("Close > EMA20 > EMA50 > EMA200", result["reasons"])

    def test_normalized_ema_slope_uses_atr_and_lookback(self):
        series = ema([100 + index for index in range(30)], 5)
        self.assertAlmostEqual(normalized_slope(series, 2.0, 5), (series[-1] - series[-6]) / 10)

    def test_rsi_state_thresholds(self):
        self.assertEqual(rsi_state(60)[0], 2)
        self.assertEqual(rsi_state(57)[0], 1)
        self.assertEqual(rsi_state(50)[0], 0)
        self.assertEqual(rsi_state(42)[0], -1)
        self.assertEqual(rsi_state(39)[0], -2)

    def test_rsi_uptrend_is_bounded(self):
        value = rsi([100 + index for index in range(30)])
        self.assertGreaterEqual(value, 0)
        self.assertLessEqual(value, 100)

    def test_adx_direction_comes_from_dmi(self):
        adx, plus_di, minus_di = adx_dmi(candles(80), 14)
        self.assertGreater(adx, 25)
        self.assertGreater(plus_di, minus_di)

    def test_momentum_normalization_is_bounded(self):
        result = calculate_timeframe_state("daily", candles(), candles(step=0.2))
        self.assertGreaterEqual(result["momentum_score"], 0)
        self.assertLessEqual(result["momentum_score"], 100)

    def test_relative_strength_calculation_detects_outperformance(self):
        result = calculate_timeframe_state("daily", candles(step=1.0), candles(step=0.1))
        self.assertGreater(result["relative_strength_score"], 50)

    def test_relative_strength_state_is_explainable(self):
        result = calculate_timeframe_state("daily", candles(step=1.0), candles(step=0.1))
        self.assertIn(result["relative_strength_state"], {"Outperformer", "Strong Outperformer"})
        self.assertTrue(any("RS slope" in reason for reason in result["reasons"]))

    def test_breadth_calculation(self):
        score, details = breadth_score([
            {"close": 110, "ema20": 100, "ema50": 95, "ema200": 90, "change": 1, "relative_strength_score": 60},
            {"close": 90, "ema20": 100, "ema50": 95, "ema200": 85, "change": -1, "relative_strength_score": 40},
        ])
        self.assertEqual(details["above_ema20_pct"], 50)
        self.assertGreater(score, 0)

    def test_volume_participation_calculation(self):
        score, details = volume_participation_score([{"volume": 200, "average_volume20": 100}, {"volume": 80, "average_volume20": 100}])
        self.assertEqual(details["above_average_pct"], 50)
        self.assertGreater(score, 0)


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.sector = SECTOR_DEFINITIONS[0]
        self.states = {key: timeframe() for key in MTF_MODES["intraday"]}

    def test_sector_score_uses_configured_components(self):
        result = calculate_sector(self.sector, self.states, "intraday", {"breadth": [{"close": 110, "ema20": 100, "ema50": 95, "ema200": 90, "change": 1, "relative_strength_score": 60}], "volume": [{"volume": 150, "average_volume20": 100}]})
        self.assertEqual(set(result["component_weights"]), set(SECTOR_SCORE_WEIGHTS))
        self.assertGreater(result["overall_score"], 0)

    def test_missing_metric_weights_are_redistributed(self):
        result = calculate_sector(self.sector, self.states, "intraday")
        self.assertAlmostEqual(sum(result["component_weights"].values()), 100, places=1)
        self.assertNotIn("breadth", result["component_weights"])
        self.assertIn("breadth", result["missing_components"])

    def test_intraday_mtf_weighting(self):
        values = {"15m": 20, "1h": 40, "daily": 80, "weekly": 100}
        score, _ = weighted_available(values, MTF_MODES["intraday"])
        self.assertAlmostEqual(score, 47)

    def test_swing_mtf_weighting_excludes_15m(self):
        values = {"15m": 0, "1h": 50, "daily": 80, "weekly": 100}
        score, _ = weighted_available(values, MTF_MODES["swing"])
        self.assertAlmostEqual(score, 85)

    def test_rank_generation(self):
        ranked = rank_sectors([{"sector_id": "a", "name": "A", "overall_score": 60}, {"sector_id": "b", "name": "B", "overall_score": 80}])
        self.assertEqual((ranked[0]["sector_id"], ranked[0]["rank"]), ("b", 1))

    def test_rank_change_positive_means_improving(self):
        ranked = rank_sectors([{"sector_id": "a", "name": "A", "overall_score": 80}], {"a": 3})
        self.assertEqual(ranked[0]["rank_change"], 2)

    def test_rotation_classification_uses_score_and_rank_direction(self):
        current = {"overall_score": 72, "rank": 1}
        history = [{"overall_score": 60, "rank": 4}, {"overall_score": 68, "rank": 2}]
        self.assertEqual(classify_rotation(current, history)[0], "LEADING")

    def test_rotation_acceleration_compares_velocities(self):
        current = {"overall_score": 75, "rank": 1}
        history = [{"overall_score": 60, "rank": 4}, {"overall_score": 64, "rank": 3}]
        self.assertEqual(classify_rotation(current, history)[1], "ACCELERATING")

    def test_full_mtf_alignment(self):
        states = {key: timeframe(state=1) for key in ("15m", "1h", "daily", "weekly")}
        self.assertEqual(mtf_alignment(states), "FULL BULLISH ALIGNMENT")

    def test_missing_timeframe_redistributes_mode_weight(self):
        score, weights = weighted_available({"15m": None, "1h": 50, "daily": 100, "weekly": 0}, MTF_MODES["intraday"])
        self.assertIsNotNone(score)
        self.assertAlmostEqual(sum(weights.values()), 1)

    def test_missing_weekly_cannot_claim_full_alignment(self):
        states = {"15m": timeframe(state=1), "1h": timeframe(state=1), "daily": timeframe(state=1), "weekly": {"state": None}}
        self.assertEqual(mtf_alignment(states), "MIXED")

    def test_stale_data_handling(self):
        old = [{"timestamp": int((datetime.now() - timedelta(days=20)).timestamp())}]
        self.assertEqual(SectorAnalysisService._quality("daily", old), "STALE")

    def test_insufficient_candles_are_explicit(self):
        result = calculate_timeframe_state("daily", candles(20), candles(20))
        self.assertEqual(result["data_quality"], "INSUFFICIENT DATA")
        self.assertIsNone(result["score"])

    def test_benchmark_failure_retains_absolute_trend(self):
        result = calculate_timeframe_state("daily", candles(), [])
        self.assertIsNotNone(result["score"])
        self.assertIsNone(result["relative_strength_score"])
        self.assertIn("relative strength benchmark alignment", result["missing_components"])

    def test_constituent_failure_does_not_fabricate_breadth(self):
        result = calculate_sector(self.sector, self.states, "intraday", {"breadth": [], "volume": []})
        self.assertIsNone(result["breadth_score"])
        self.assertIsNone(result["volume_score"])

    def test_alert_ready_transition_event(self):
        previous = {"rank": 5, "rotation_state": "IMPROVING", "mtf_alignment": "MIXED", "relative_strength_state": "Neutral"}
        current = {"sector_id": "auto", "rank": 2, "rotation_state": "LEADING", "mtf_alignment": "BULLISH ALIGNMENT", "relative_strength_state": "Strong Outperformer"}
        types = {event["type"] for event in detect_events(previous, current)}
        self.assertIn("TOP_3_ENTERED", types)
        self.assertIn("ROTATION_CHANGED", types)


class ServiceContractTests(unittest.TestCase):
    def test_refresh_ranks_sectors_persists_history_and_keeps_detail_series(self):
        class Provider:
            def __init__(self):
                self.calls = []

            def get(self, symbol, timeframe):
                self.calls.append((symbol, timeframe))
                offset = sum(ord(character) for character in symbol) % 7
                return candles(260, start=100 + offset, step=0.2 + offset / 100)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "analysis.json"
            provider = Provider()
            service = SectorAnalysisService("", state_file=path, provider=provider)
            service.refresh()
            snapshot = service.snapshot("intraday")
            detail = service.snapshot("intraday", SECTOR_DEFINITIONS[0].sector_id)
            self.assertEqual(snapshot["status"], "DELAYED")
            self.assertEqual(len(snapshot["sectors"]), len(SECTOR_DEFINITIONS))
            self.assertEqual(snapshot["sectors"][0]["rank"], 1)
            self.assertNotIn("series", snapshot["sectors"][0]["timeframe_states"]["daily"])
            self.assertTrue(detail["sector"]["timeframe_states"]["daily"]["series"])
            self.assertTrue(path.exists())
            self.assertEqual(len(provider.calls), (len(SECTOR_DEFINITIONS) + 1) * 3)

    def test_unknown_detail_is_explicitly_unavailable(self):
        with TemporaryDirectory() as directory:
            service = SectorAnalysisService("", state_file=Path(directory) / "analysis.json")
            result = service.snapshot("intraday", "unknown")
            self.assertEqual(result["status"], "UNAVAILABLE")
            self.assertIn("Unknown", result["error"])

    def test_one_timeframe_failure_preserves_other_timeframes(self):
        class PartialProvider:
            def get(self, symbol, timeframe):
                if timeframe == "1h":
                    raise RuntimeError("provider interval unavailable")
                return candles(260)

        with TemporaryDirectory() as directory:
            service = SectorAnalysisService("", state_file=Path(directory) / "analysis.json", provider=PartialProvider())
            service.refresh()
            sector = service.snapshot("intraday", SECTOR_DEFINITIONS[0].sector_id)["sector"]
            self.assertEqual(sector["timeframe_states"]["1h"]["data_quality"], "UNAVAILABLE")
            self.assertIsNotNone(sector["overall_score"])

    def test_missing_authentication_has_actionable_analysis_error(self):
        with TemporaryDirectory() as directory:
            service = SectorAnalysisService("", state_file=Path(directory) / "analysis.json")
            result = service.snapshot("intraday")
            self.assertIn("authentication", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
