import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from adx_candidate import assess
BASE=int(datetime(2026,10,23,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows():
 return [dict(timestamp=BASE+i*300,host_atr=2,adx=15+i*.1) for i in range(70)]
class Tests(unittest.TestCase):
 def check(self,r):return assess(r,'BULLISH',r[-1]['timestamp']+300)
 def test_strength_rising(self):self.assertTrue(self.check(rows())['allowed'])
 def test_bearish_symmetric(self):
  r=rows();self.assertTrue(assess(r,'BEARISH',r[-1]['timestamp']+300)['allowed'])
 def test_exact_strength_threshold(self):
  r=rows();r[-4]['adx']=14;r[-1]['adx']=15
  self.assertTrue(self.check(r)['allowed'])
 def test_exact_volatility_threshold(self):
  r=rows();r[-1]['host_atr']=1.6
  self.assertTrue(self.check(r)['allowed'])
 def test_quiet_blocks(self):
  r=rows();r[-1]['host_atr']=1.59
  self.assertEqual(self.check(r)['reason'],'VOLATILITY_BELOW_REFERENCE')
 def test_falling_strength_blocks(self):
  r=rows();r[-1]['adx']=r[-4]['adx']-.1
  self.assertEqual(self.check(r)['reason'],'TREND_STRENGTH_NOT_RISING')
 def test_weak_strength_blocks(self):
  r=rows();r[-1]['adx']=14.9
  self.assertEqual(self.check(r)['reason'],'WEAK_TREND_STRENGTH')
 def test_future_not_used(self):
  r=rows();expected=self.check(r);future=dict(r[-1],timestamp=r[-1]['timestamp']+300,adx=0)
  self.assertEqual(assess(r+[future],'BULLISH',r[-1]['timestamp']+300),expected)
 def test_unknown_and_warmup(self):
  self.assertEqual(self.check(rows()[:10])['reason'],'WARMUP')
  with self.assertRaises(ValueError):assess(rows(),'UNKNOWN',BASE+100000)
 def test_missing_bar(self):
  r=rows();r[-1]['timestamp']+=300
  self.assertEqual(self.check(r)['reason'],'MISSING_HOST_BAR')
if __name__=='__main__':unittest.main()
