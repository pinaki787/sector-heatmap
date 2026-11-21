import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from slope_review import assess
BASE=int(datetime(2026,10,23,10,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows(sign=1):
 return [dict(timestamp=BASE+300*i,supertrend=100+sign*i*2,pine_direction=-sign,box=10) for i in range(7)]
class Tests(unittest.TestCase):
 def test_rising(self):self.assertTrue(assess(rows(),('s',6,.1))['allowed'])
 def test_falling(self):self.assertTrue(assess(rows(-1),('s',6,.1))['allowed'])
 def test_flat(self):
  r=rows()
  for x in r:x['supertrend']=100
  self.assertFalse(assess(r,('s',6,.1))['allowed'])
 def test_band_jump_is_not_slope(self):
  r=rows();r[-1]['pine_direction']=1
  self.assertEqual(assess(r,('s',6,.1))['state'],'BAND_SWITCH')
 def test_exact_threshold(self):self.assertTrue(assess(rows(),('s',6,.2))['allowed'])
 def test_insufficient(self):self.assertFalse(assess(rows()[:2],('s',6,.1))['allowed'])
if __name__=='__main__':unittest.main()
