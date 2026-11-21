import unittest,runpy
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
module=runpy.run_path(str(Path(__file__).with_name('review.py')),run_name='research_module')
assess=module['assess'];rule=('test',6,.5,2,3)
BASE=int(datetime(2026,10,23,10,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows(values,directions=None):
 return [dict(timestamp=BASE+300*i,supertrend=v,pine_direction=(directions or [-1]*len(values))[i],box=10) for i,v in enumerate(values)]
class Tests(unittest.TestCase):
 def test_advancing_bullish_line(self):self.assertTrue(assess(rows([100,101,102,103,104,105,106]),rule)['allowed'])
 def test_flat_line_is_blocked(self):self.assertFalse(assess(rows([100]*7),rule)['allowed'])
 def test_one_large_jump_is_not_persistence(self):self.assertFalse(assess(rows([100,100,100,100,100,100,110]),rule)['allowed'])
 def test_direction_flip_is_blocked(self):self.assertFalse(assess(rows([100,101,102,103,104,105,106],[-1,-1,1,-1,-1,-1,-1]),rule)['allowed'])
 def test_bearish_line_is_symmetric(self):self.assertTrue(assess(rows([106,105,104,103,102,101,100],[1]*7),rule)['allowed'])
 def test_warmup_fails_closed(self):self.assertFalse(assess(rows([100,101]),rule)['allowed'])
 def test_four_flat_bars_are_blocked(self):self.assertFalse(assess(rows([100,103,106,106,106,106,106]),rule)['allowed'])
 def test_future_is_not_an_input_to_prefix(self):
  prefix=rows([100,101,102,103,104,105,106]);expected=assess(prefix,rule)
  extended=prefix+rows([50,20])
  self.assertEqual(assess(extended[:len(prefix)],rule),expected)
if __name__=='__main__':unittest.main()
