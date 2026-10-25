import unittest
from datetime import datetime
from unittest.mock import Mock
from sector_heatmap.market_calendar import IST
from sector_heatmap.motilal_analysis import Provider

def bar(day,hour=9,minute=15,volume=True):
 return dict(timestamp=int(datetime(2026,10,day,hour,minute,tzinfo=IST).timestamp()),open=100,high=102,low=99,close=101,volume=1,volume_available=volume)

class CompletedNativeHistoryTests(unittest.TestCase):
 def provider(self):
  p=object.__new__(Provider);p.execution=Mock();p.adapter=Mock()
  p.prepare=Mock();p.resolve=Mock(return_value={"symbol":"MO:NSE:1"})
  p.now=lambda:datetime(2026,10,21,12,0,tzinfo=IST)
  return p
 def test_forming_week_is_excluded_from_native_captured_analysis(self):
  p=self.provider();p.execution.history.session_candles.return_value=[bar(16),bar(19),bar(21)]
  rows=p.get("NSE:TEST-EQ","weekly")
  self.assertEqual(len(rows),1)
  self.assertLess(datetime.fromtimestamp(rows[0]["timestamp"],IST).date(),datetime(2026,10,19).date())
 def test_native_hourly_requires_completed_bar_and_real_volume(self):
  p=self.provider();p.execution.history.candles.return_value=[bar(21,10),bar(21,11,30),bar(21,9,15,False)]
  rows=p.get("NSE:TEST-EQ","1h")
  self.assertEqual([r["timestamp"] for r in rows],[bar(21,10)["timestamp"]])
 def test_daily_excludes_current_open_session_and_future(self):
  p=self.provider();p.execution.history.session_candles.return_value=[bar(19),bar(21),bar(22)]
  self.assertEqual([r["timestamp"] for r in p.get("NSE:TEST-EQ","daily")],[bar(19)["timestamp"]])
