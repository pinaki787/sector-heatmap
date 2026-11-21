import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from model import target_fill,simulate
BASE=int(datetime(2026,10,23,10,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
class FakeEngine:
 def __init__(self,*a):self.state={}
 def update(self,r):return dict(r,entry_direction='BULLISH',ema10=100,ema30=100,host_atr=2,raw_supertrend_cross_direction=None)
class Tests(unittest.TestCase):
 def test_long_target(self):self.assertEqual(target_fill(dict(direction='BULLISH',target=102),dict(high=103,low=99)),(102,'TARGET_TOUCHED'))
 def test_short_target(self):self.assertEqual(target_fill(dict(direction='BEARISH',target=98),dict(high=101,low=97)),(98,'TARGET_TOUCHED'))
 def simulate_bar(self,low):
  hosts=[dict(timestamp=BASE,open=100,high=101,low=99,close=100,volume=0)]
  minutes=[dict(timestamp=BASE+i*60,open=100,high=103 if i==5 else 100,low=low if i==5 else 100,close=100,volume=0) for i in range(11)]
  with patch('model.Engine',FakeEngine),patch('model.ema_proximity.check'),patch('model.exit_indicators.reason',return_value=None),patch.dict('model.EXITS',{'test':dict(hard=1,target=.5)}):
   return simulate(hosts,minutes,dict(ema_exit_enabled=False),'Baseline','test','2026-10-23')
 def test_same_minute_stop_and_target_uses_adverse_order(self):
  r=self.simulate_bar(97);self.assertEqual(r['trades'][0]['reason'],'STOP_TOUCHED');self.assertEqual(r['trades'][0]['exit_price'],98)
 def test_small_target_can_still_lose_after_costs(self):
  r=self.simulate_bar(99);self.assertEqual(r['trades'][0]['reason'],'TARGET_TOUCHED');self.assertLess(r['splits']['all']['2']['net_points'],0)
if __name__=='__main__':unittest.main()
