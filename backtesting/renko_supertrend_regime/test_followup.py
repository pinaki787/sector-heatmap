import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from followup import assess
BASE=int(datetime(2026,10,23,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows(sign=1):
 return [dict(timestamp=BASE+i*300,close=100+sign*i,host_atr=2 if i<21 else 2.2,
  pine_direction=-sign,rsi14=60 if sign>0 else 40,adx=25+i*.1) for i in range(22)]
class Tests(unittest.TestCase):
 def test_combined_bullish(self):self.assertTrue(assess(rows(),('Combined',))['allowed'])
 def test_combined_bearish(self):self.assertTrue(assess(rows(-1),('Combined',))['allowed'])
 def test_atr_expansion_without_direction_is_blocked(self):
  r=rows()
  for i,x in enumerate(r):x['close']=100+(i%2)
  self.assertFalse(assess(r,('Combined',))['allowed'])
 def test_flat_prices_are_blocked(self):
  r=rows()
  for x in r:x['close']=100
  self.assertFalse(assess(r,('Combined',))['allowed'])
 def test_rsi_disagreement_blocks(self):
  r=rows();r[-1]['rsi14']=49
  self.assertFalse(assess(r,('Combined',))['allowed'])
 def test_weak_adx_blocks(self):
  r=rows();r[-1]['adx']=19.9
  self.assertFalse(assess(r,('Combined',))['allowed'])
 def test_no_atr_expansion_blocks(self):
  r=rows();r[-1]['host_atr']=2
  self.assertFalse(assess(r,('Combined',))['allowed'])
 def test_warmup_blocks(self):self.assertFalse(assess(rows()[:10],('Combined',))['allowed'])
if __name__=='__main__':unittest.main()
