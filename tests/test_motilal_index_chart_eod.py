"""Regression: listed Motilal indices must use their exact native completed EOD row."""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from sector_heatmap.chart_workspace import motilal_chart
from sector_heatmap.motilal_history import History
from sector_heatmap.motilal_api import MotilalError

IST = ZoneInfo("Asia/Kolkata")
NIFTY_EOD = dict(exchange="NSE", scripcode=26000, open=25323.15, high=25390.8,
                 low=25141.8, close=25227.95, volume=446951226, date="19-11-2026")

class MotilalIndexEodTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 11, 19, 19, tzinfo=IST).timestamp()
        self.history = History(Path(self.temp.name) / "history.sqlite", clock=lambda: self.now)
        self.feed = Mock(connected=False)
        self.feed.price.side_effect = ValueError("No current native tick")
        self.master = Mock()
        self.master.indices.return_value = [dict(token=26000, name="Nifty 50")]
        self.service = SimpleNamespace(ready=Mock(), master=self.master, feed=self.feed,
                                       clock=lambda: self.now, history=self.history,
                                       eod_snapshot=Mock(return_value={"data": [dict(NIFTY_EOD)]}))

    def chart(self, interval="1D", exchange="NSE", token=26000, live=False):
        return motilal_chart(self.service, interval, live=live,
                            symbol=f"MO:INDEX:{exchange}:{token}")

    def test_native_completed_nifty_eod_is_available_without_captured_ticks(self):
        result = self.chart()
        opening = int(datetime(2026, 11, 19, tzinfo=IST).timestamp())
        self.assertEqual(result["rows"], [[opening, 25323.15, 25390.8, 25141.8, 25227.95, 446951226]])
        self.assertEqual(result["provider"], "Motilal Oswal")
        self.assertEqual(result["symbol"], "MO:INDEX:NSE:26000")
        self.feed.subscribe_index.assert_called_once_with("NSE", 26000)
        self.service.eod_snapshot.assert_called_once_with("NSE")

    def test_bse_index_uses_only_its_exact_exchange_and_token(self):
        self.master.indices.return_value = [dict(token=1, name="SENSEX")]
        expected = {**NIFTY_EOD, "exchange": "BSE", "scripcode": 1}
        self.service.eod_snapshot.return_value = {"data": [NIFTY_EOD, expected]}
        rows = self.chart(exchange="BSE", token=1)["rows"]
        self.assertEqual(len(rows), 1)
        self.service.eod_snapshot.assert_called_once_with("BSE")

    def test_no_substitution_when_native_eod_has_only_other_instruments(self):
        self.service.eod_snapshot.return_value = {"data": [{**NIFTY_EOD, "scripcode": 99}]}
        self.assertEqual(self.chart()["rows"], [])

    def test_forming_daily_eod_cannot_be_published_as_completed_history(self):
        self.now = datetime(2026, 11, 19, 14, tzinfo=IST).timestamp()
        self.assertEqual(self.chart()["rows"], [])
        self.assertEqual(self.history.daily_snapshots("MO:INDEX:NSE:26000"), [])

    def test_one_daily_snapshot_does_not_fabricate_a_complete_week(self):
        self.assertEqual(self.chart("1W")["rows"], [])
        self.assertEqual(len(self.history.daily_snapshots("MO:INDEX:NSE:26000")), 1)

    def test_live_stream_does_not_fetch_or_replace_ticks_with_eod(self):
        self.assertEqual(self.chart(live=True)["rows"], [])
        self.service.eod_snapshot.assert_not_called()

    def test_expired_broker_session_still_requires_authentication(self):
        self.service.eod_snapshot.side_effect = MotilalError("expired", auth_required=True)
        with self.assertRaises(MotilalError):
            self.chart()

if __name__ == "__main__":
    unittest.main()
