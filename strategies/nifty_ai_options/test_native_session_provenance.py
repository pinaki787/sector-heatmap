import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from test_native_sizing import reply,DELTA
import native_sizing as n
class SessionProvenanceTests(unittest.TestCase):
 def fixture(self):
  now=datetime(2026,11,26,12,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  end=datetime(2026,11,25,15,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  r=reply(now);r['structuredContent']['symbol']='BSE:SENSEX'
  r['structuredContent']['last_values']['plots'].update({'0':1500,'1':(end-21600)*1000,'2':end*1000,'3':(end-17*86400)*1000})
  return now,r,dict(DELTA,broker='FYERS',underlying='BSE:SENSEX-INDEX',market='BSE')
 def test_old_native_brick_is_explicitly_carried_not_relabelled(self):
  now,r,c=self.fixture()
  with patch('sector_heatmap.market_calendar.market_session',return_value={'status':'OPEN','last_completed_session':'2026-11-25','next_open':'2026-11-26T09:15:00+05:30'}):
   ref=n.parse_result(r,c,now=now)
  self.assertTrue(ref['native_observation_carried'])
  self.assertEqual(ref['native_observation_role'],'LAST_NATIVE_BRICK_TIME')
  self.assertEqual(ref['native_observation_at'],r['structuredContent']['last_values']['plots']['3']/1000)
 def test_previous_session_host_is_valid_without_current_day_quote_data(self):
  now,r,c=self.fixture()
  r['structuredContent']['last_values']['plots']['6']=r['structuredContent']['last_values']['plots']['2']
  with patch('sector_heatmap.market_calendar.market_session',return_value={'status':'OPEN','last_completed_session':'2026-11-25','last_completed_session_close':'2026-11-25T15:30:00+05:30','next_open':'2026-11-26T09:15:00+05:30'}):
   ref=n.parse_result(r,c,now=now)
  self.assertEqual(ref['native_box'],1500)
  self.assertLess(ref['host_end'],now-12*3600)
 def test_same_date_but_incomplete_session_is_rejected(self):
  now,r,c=self.fixture()
  r['structuredContent']['last_values']['plots']['2']-=3600*1000
  with patch('sector_heatmap.market_calendar.market_session',return_value={'status':'OPEN','last_completed_session':'2026-11-25','last_completed_session_close':'2026-11-25T15:30:00+05:30','next_open':'2026-11-26T09:15:00+05:30'}):
   with self.assertRaisesRegex(ValueError,'regular-session close'):n.parse_result(r,c,now=now)
 def test_fresh_calculation_does_not_mask_stale_host_data(self):
  now,r,c=self.fixture();r['structuredContent']['last_values']['plots']['6']=(now-86400)*1000
  with patch('sector_heatmap.market_calendar.market_session',return_value={'status':'OPEN','last_completed_session':'2026-11-25'}):
   with self.assertRaisesRegex(ValueError,'host data does not cover'):n.parse_result(r,c,now=now)
 def test_closed_session_requires_recent_completed_host(self):
  now,r,c=self.fixture();r['structuredContent']['last_values']['plots']['6']=(now-86400)*1000
  with patch('sector_heatmap.market_calendar.market_session',return_value={'status':'CLOSED','last_completed_session':'2026-11-25','last_completed_session_close':'2026-11-25T15:30:00+05:30'}):
   with self.assertRaisesRegex(ValueError,'host data does not cover'):n.parse_result(r,c,now=now)
