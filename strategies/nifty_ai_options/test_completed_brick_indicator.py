import unittest,copy
from indicator import AIRenko,Traditional
class CompletedBrickIndicatorTests(unittest.TestCase):
 def test_consumes_the_exact_completed_brick_without_second_grid(self):
  grid=Traditional(7.14);grid.update(7800)
  ai=AIRenko(manual_brick=7.14,completed_bricks=True,pine_series_precision=True)
  for price in (7825,7840,7810,7780,7820):
   for brick in grid.update(price):
    result=ai.update(brick)
    self.assertAlmostEqual(result['synthetic_open'],brick['open'],8)
    self.assertAlmostEqual(result['synthetic_close'],brick['close'],8)
    self.assertEqual(result['steps'],1)
 def test_rejects_partial_bricks_and_time_candles(self):
  ai=AIRenko(manual_brick=1,completed_bricks=True)
  for bar in (dict(open=100,high=100.5,low=100,close=100.5),dict(open=100,high=103,low=99,close=101)):
   with self.assertRaises(ValueError):ai.update(bar)
 def test_identical_bricks_ignore_time_candle_partition(self):
  bricks=[dict(open=x,close=x+1,high=x+1,low=x) for x in range(100,120)]
  left=AIRenko(manual_brick=1,completed_bricks=True)
  right=AIRenko(manual_brick=1,completed_bricks=True)
  a=[left.update(b) for b in bricks]
  b=[]
  for group in (bricks[:3],bricks[3:15],bricks[15:]):b.extend(right.update(x) for x in group)
  self.assertEqual(a,b)
if __name__=='__main__':unittest.main()
