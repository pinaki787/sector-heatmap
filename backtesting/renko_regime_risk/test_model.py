import unittest
from model import stop_fill,update_stop,stats,stop_level
def pos(direction='BULLISH'):
 return dict(direction=direction,entry_price=100.,atr=2.,favorable=0.,stop=95. if direction=='BULLISH' else 105.)
class Tests(unittest.TestCase):
 def test_long_gap_worse_than_stop(self):self.assertEqual(stop_fill(pos(),dict(open=93,low=92,high=96)),(93,'STOP_GAP_OPEN'))
 def test_short_gap_worse_than_stop(self):self.assertEqual(stop_fill(pos('BEARISH'),dict(open=107,low=104,high=109)),(107,'STOP_GAP_OPEN'))
 def test_touched_stop(self):self.assertEqual(stop_fill(pos(),dict(open=100,low=94,high=103)),(95.,'STOP_TOUCHED'))
 def test_trail_never_loosens(self):
  p=pos();rule=dict(trail=1.,activation=1.)
  update_stop(p,dict(high=106,low=100),rule,2);first=p['stop']
  update_stop(p,dict(high=104,low=101),rule,2);self.assertEqual(p['stop'],first)
 def test_new_stop_is_not_applied_to_previous_minute(self):
  p=pos();bar=dict(open=100,high=110,low=96)
  self.assertIsNone(stop_fill(p,bar))
  update_stop(p,bar,dict(trail=1.,activation=1.),2)
  self.assertEqual(p['stop'],108)
  self.assertEqual(stop_fill(p,dict(open=106,high=109,low=105)),(106,'STOP_GAP_OPEN'))
 def test_breakeven_cost_offset(self):
  p=pos();update_stop(p,dict(high=103,low=100),dict(breakeven=1.),2)
  self.assertEqual(p['stop'],102.)
 def test_zero_does_not_hide_nonpositive_streak(self):
  s=stats([dict(gross_points=-1),dict(gross_points=2),dict(gross_points=-2)],2)
  self.assertEqual(s['max_nonpositive_streak'],3)
 def test_selected_exits_without_stops(self):
  p=pos();p['stop']=None
  self.assertIsNone(stop_fill(p,dict(open=90,high=120,low=80)))
 def test_long_stop_rounds_down(self):self.assertEqual(stop_level(97.999,'BULLISH'),97.95)
 def test_short_stop_rounds_up(self):self.assertEqual(stop_level(102.001,'BEARISH'),102.05)
if __name__=='__main__':unittest.main()
