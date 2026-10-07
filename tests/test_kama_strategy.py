from datetime import datetime
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from sector_heatmap.kama_strategy import kama_series, kama_v6_signal
from sector_heatmap.web import kama_scheduled_squareoff_due


def candle(minute, close, high=None, low=None):
    stamp = datetime(2026, 9, 11, 9 + minute // 60, minute % 60, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()
    return {"timestamp": stamp, "open": close, "high": high if high is not None else close, "low": low if low is not None else close, "close": close}


class KamaSignalTests(unittest.TestCase):
    def test_kama_series_aligns_display_values_to_completed_candles(self):
        bars = [candle(20 + index * 5, 100 + index) for index in range(8)]
        values = kama_series(bars, kama_length=3, fast_length=2, slow_length=10)
        self.assertEqual(len(values), len(bars))
        self.assertEqual(values[:3], [None, None, None])
        self.assertTrue(all(value is not None for value in values[3:]))

    def test_kama_only_signal_enters_and_exits_from_completed_candles(self):
        # A sustained completed-bar advance produces a rising line and a break
        # above the previous two highs.  No EMA input exists in the API.
        bars = [candle(20 + index * 5, 100 + index, 100 + index + .2, 100 + index - .2) for index in range(14)]
        entry = kama_v6_signal(bars, kama_length=3, fast_length=2, slow_length=10, minimum_efficiency=.1, breakout_bars=2)
        self.assertEqual(entry["action"], "ENTER_LONG")
        bars.append(candle(90, 106, 106.2, 105.8))
        exit_signal = kama_v6_signal(bars, position=1, kama_length=3, fast_length=2, slow_length=10, minimum_efficiency=.1, breakout_bars=2)
        self.assertEqual(exit_signal["action"], "EXIT_LONG")

    def test_kama_slope_filter_blocks_only_new_entries(self):
        bars = [candle(20 + index * 5, 100 + index, 100 + index + .2, 100 + index - .2) for index in range(14)]
        blocked = kama_v6_signal(bars, kama_length=3, fast_length=2, slow_length=10,
                                 minimum_efficiency=.1, breakout_bars=2,
                                 slope_lookback=3, minimum_slope_atr=100)
        self.assertEqual(blocked["action"], "WAIT")
        self.assertEqual(blocked["blocked_by"], "KAMA_SLOPE")
        self.assertFalse(blocked["slope_filter_passed"])
        allowed = kama_v6_signal(bars, kama_length=3, fast_length=2, slow_length=10,
                                 minimum_efficiency=.1, breakout_bars=2,
                                 slope_lookback=3, minimum_slope_atr=0)
        self.assertEqual(allowed["action"], "ENTER_LONG")
        self.assertTrue(allowed["slope_filter_passed"])

        exit_signal = kama_v6_signal(bars + [candle(90, 106, 106.2, 105.8)], position=1,
                                     kama_length=3, fast_length=2, slow_length=10,
                                     minimum_efficiency=.1, breakout_bars=2,
                                     slope_lookback=3, minimum_slope_atr=100)
        self.assertEqual(exit_signal["action"], "EXIT_LONG")

    def test_squareoff_has_priority_for_an_open_position(self):
        bars = [candle(20 + index * 5, 100 + index) for index in range(14)]
        stamp = datetime(2026, 9, 11, 15, 16, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp()
        bars[-1] = {"timestamp": stamp, "open": 113, "high": 113, "low": 113, "close": 113}
        result = kama_v6_signal(bars, position=1, kama_length=3, fast_length=2, slow_length=10, breakout_bars=2)
        self.assertEqual(result["action"], "SQUARE_OFF")

    def test_exchange_squareoff_cutoffs_use_ist_wall_clock(self):
        nse = {"symbol": "NSE:NIFTY50-INDEX", "opened_at": "2026-09-16T09:15:00+05:30"}
        mcx = {"symbol": "MCX:CRUDEOIL26SEP2026FUT", "opened_at": "2026-09-16T09:15:00+05:30"}
        self.assertFalse(kama_scheduled_squareoff_due(nse, datetime(2026, 9, 16, 15, 14, tzinfo=ZoneInfo("Asia/Kolkata"))))
        self.assertTrue(kama_scheduled_squareoff_due(nse, datetime(2026, 9, 16, 15, 15, tzinfo=ZoneInfo("Asia/Kolkata"))))
        self.assertFalse(kama_scheduled_squareoff_due(mcx, datetime(2026, 9, 16, 23, 29, tzinfo=ZoneInfo("Asia/Kolkata"))))
        self.assertTrue(kama_scheduled_squareoff_due(mcx, datetime(2026, 9, 16, 23, 30, tzinfo=ZoneInfo("Asia/Kolkata"))))

    def test_dashboard_keeps_kama_runner_separate_from_ema_and_manual_tickets(self):
        root = Path(__file__).resolve().parents[1]
        backend = (root / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (root / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('"/api/kama/runner/start"', backend)
        self.assertIn('"/api/kama/execution-log"', backend)
        self.assertIn('"/api/kama/chart"', backend)
        self.assertIn("KAMA V6 completed candles only", backend)
        self.assertIn("FYERS master screen only; it cannot authorize a trade", backend)
        self.assertNotIn("kama/live-preview", backend)
        self.assertNotIn("kama/live-submit", backend)
        self.assertIn("NO MANUAL TICKETS", dashboard)
        self.assertIn("KAMA Strategy", dashboard)
        self.assertIn("fetchJson(`/api/kama/chart?${params}`)", dashboard)
        self.assertIn("Closed at", dashboard)
        self.assertIn("Scheduled square-off", dashboard)
        self.assertIn("KAMA chart type", dashboard)
        self.assertIn("Candlestick", dashboard)
        self.assertIn("sector-pulse:kama-chart-type", dashboard)
        self.assertIn("FYERS candlestick", dashboard)
        self.assertIn("KAMA chart refresh interval", dashboard)
        self.assertIn("sector-pulse:kama-refresh-ms", dashboard)
        self.assertIn("return allowedKamaRefreshMs.includes(stored) ? stored : 2000", dashboard)
        self.assertIn("<option>1 minute</option>", dashboard)
        self.assertIn('"1 minute": "1"', backend)
        self.assertIn("KAMA slope lookback", dashboard)
        self.assertIn("minimum_slope_atr", backend)

    def test_live_runner_is_explicitly_double_gated_and_broker_reconciled(self):
        root = Path(__file__).resolve().parents[1]
        backend = (root / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (root / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn("SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS", backend)
        self.assertIn("SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS", backend)
        self.assertIn("kama_submit_live_entry", backend)
        self.assertIn("kama_submit_live_exit", backend)
        self.assertIn("kama_position_reconciliation", backend)
        self.assertIn('productType": "INTRADAY"', backend)
        self.assertIn("Invalidation / stop price", dashboard)
        self.assertIn("Maximum idea risk", dashboard)

    def test_fyers_login_is_checked_before_opening_the_browser_flow(self):
        root = Path(__file__).resolve().parents[1]
        backend = (root / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (root / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('path == "/api/auth/status"', backend)
        self.assertIn("def fyers_auth_status", backend)
        self.assertIn("validated_config(expected_port=port)", backend)
        self.assertIn("/api/auth/status", dashboard)
        self.assertLess(dashboard.index("/api/auth/status"), dashboard.index("/api/auth/start"))


if __name__ == "__main__":
    unittest.main()
