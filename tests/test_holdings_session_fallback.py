from datetime import datetime
from zoneinfo import ZoneInfo
import unittest
from sector_heatmap.native_holdings import complete_cash_session
class CompleteSessionTests(unittest.TestCase):
 def bars(self):
  start=int(datetime(2026,10,27,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
  return [dict(timestamp=start+i*60,open=100+i*.01,high=102+i*.01,low=99+i*.01,close=101+i*.01,volume=10) for i in range(375)]
 def test_aggregates_complete_session_without_invented_minutes(self):
  rows=self.bars();r=complete_cash_session(rows,'2026-10-27')
  self.assertEqual(r['open'],rows[0]['open']);self.assertEqual(r['close'],rows[-1]['close']);self.assertEqual(r['high'],max(v['high'] for v in rows));self.assertEqual(r['volume'],3750);self.assertEqual(r['source_minutes'],375)
 def test_missing_open_midday_or_close_and_duplicate_minutes_block(self):
  rows=self.bars()
  for broken in (rows[1:],rows[:-1],rows[:100]+rows[101:],rows[:100]+[rows[99]]+rows[100:]):
   with self.assertRaisesRegex(ValueError,'incomplete'):complete_cash_session(broken,'2026-10-27')
