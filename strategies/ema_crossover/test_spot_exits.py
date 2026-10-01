import sys,unittest
sys.path.insert(0,'/Users/pinaki/trading/sector-heatmap/strategies')
from ema_crossover.runner import spot_exit,validate_spot_levels
class SpotTests(unittest.TestCase):
 def test_override_and_boundaries(self):
  for direction,target,stop,hit,loss in [('BULLISH',120,90,120,90),('BEARISH',80,110,80,110)]:
   config=dict(spot_target=target,spot_stop=stop)
   c=dict(close=100,fast=105 if direction=='BULLISH' else 95)
   self.assertIsNone(spot_exit(c,direction,config))
   self.assertEqual(spot_exit(dict(c,close=hit),direction,config),'SPOT_TARGET_EXIT')
   self.assertEqual(spot_exit(dict(c,close=loss),direction,config),'SPOT_STOP_EXIT')
   self.assertIsNone(spot_exit(dict(c,close=loss,is_forming=True),direction,config))
   validate_spot_levels(100,direction,config)
 def test_single_field_and_fallback(self):
  c=dict(close=95,fast=100,high=150,low=70)
  self.assertIsNone(spot_exit(c,'BULLISH',dict(spot_target=120)))
  self.assertIsNone(spot_exit(c,'BULLISH',dict(spot_stop=90)))
  self.assertEqual(spot_exit(c,'BULLISH',{}),'EMA_CLOSE_EXIT')
 def test_reject_wrong_side(self):
  for d,c in [('BULLISH',dict(spot_target=90)),('BULLISH',dict(spot_stop=110)),('BEARISH',dict(spot_target=110)),('BEARISH',dict(spot_stop=90))]:
   with self.assertRaises(ValueError):validate_spot_levels(100,d,c)
if __name__=='__main__':unittest.main()
