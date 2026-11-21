import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from ema_slope_review import assess
BASE=int(datetime(2026,10,23,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows(sign=1):
 return [dict(timestamp=BASE+300*i,close=100+sign*i,ema10=100+sign*i*.2,ema30=100+sign*i*.1,
  host_atr=2,pine_direction=-sign) for i in range(22)]
class Tests(unittest.TestCase):
 def test_bullish(self):self.assertTrue(assess(rows(),('Both_EMAs',))['allowed'])
 def test_bearish(self):self.assertTrue(assess(rows(-1),('Both_EMAs',))['allowed'])
 def test_flat(self):
  r=rows()
  for x in r:x.update(ema10=100,ema30=100)
  self.assertFalse(assess(r,('Both_EMAs',))['allowed'])
 def test_opposite_direction(self):
  r=rows()
  for x in r:x['pine_direction']=1
  self.assertFalse(assess(r,('Both_EMAs',))['allowed'])
 def test_stable_volatility(self):self.assertTrue(assess(rows(),('Both_ATR_stable',))['allowed'])
 def test_extreme_volatility(self):
  r=rows();r[-1]['host_atr']=4
  self.assertFalse(assess(r,('Both_ATR_stable',))['allowed'])
 def test_missing_warmup(self):self.assertFalse(assess(rows()[:2],('Both_EMAs',))['allowed'])
if __name__=='__main__':unittest.main()
