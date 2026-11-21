import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from candidate import assess
BASE=int(datetime(2026,10,23,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows(sign=1):
 return [dict(timestamp=BASE+i*300,close=1000+sign*i,host_atr=2) for i in range(70)]
class Tests(unittest.TestCase):
 def check(self,r,direction='BULLISH'):return assess(r,direction,r[-1]['timestamp']+300)
 def test_bullish(self):self.assertTrue(self.check(rows())['allowed'])
 def test_bearish(self):self.assertTrue(self.check(rows(-1),'BEARISH')['allowed'])
 def test_flat(self):
  r=rows()
  for x in r:x['close']=1000
  self.assertEqual(self.check(r)['reason'],'INSUFFICIENT_DIRECTIONAL_PROGRESS')
 def test_quiet(self):
  r=rows();r[-1]['host_atr']=1.99
  self.assertEqual(self.check(r)['reason'],'VOLATILITY_BELOW_REFERENCE')
 def test_future_bar_not_used(self):
  r=rows();expected=assess(r,'BULLISH',r[-1]['timestamp']+300)
  future=dict(r[-1],timestamp=r[-1]['timestamp']+300,close=1)
  self.assertEqual(assess(r+[future],'BULLISH',r[-1]['timestamp']+300),expected)
 def test_gap_blocks(self):
  r=rows();r[-1]['timestamp']+=300
  self.assertEqual(self.check(r)['reason'],'MISSING_HOST_BAR')
 def test_unknown_direction_rejected(self):
  with self.assertRaises(ValueError):self.check(rows(),'NEUTRAL')
 def test_warmup(self):self.assertEqual(self.check(rows()[:10])['reason'],'WARMUP')
 def test_duplicate_timestamp_rejected(self):
  r=rows();r[-1]['timestamp']=r[-2]['timestamp']
  with self.assertRaises(ValueError):self.check(r)
if __name__=='__main__':unittest.main()
