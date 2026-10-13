import unittest
from strategies.renko_supertrend.signals import Engine
class AutoBrickTests(unittest.TestCase):
 def rows(self):
  return [dict(timestamp=1791240000+i*300,open=100,high=112,low=88,close=100,volume=1) for i in range(20)]
 def test_nse_bse_atr5_div12_independent_of_supertrend_atr_period(self):
  for symbol in ['NSE:NIFTY50-INDEX','BSE:SENSEX-INDEX','NSE:RELIANCE-EQ','BSE:RELIANCE-A','NSE:TESTCE']:
   for period in [5,14]:
    engine=Engine(dict(underlying=symbol,atr_length=period),.05)
    rows=[engine.update(c) for c in self.rows()]
    self.assertIsNone(rows[3]['auto_box'])
    self.assertEqual(rows[4]['auto_box'],2)
    self.assertAlmostEqual(rows[-1]['box'],2)
 def test_manual_and_other_exchanges_unchanged(self):
  engine=Engine(dict(underlying='NSE:NIFTY50-INDEX',brick_mode='Manual',manual_brick=7),.05)
  self.assertEqual([engine.update(c) for c in self.rows()][-1]['box'],7)
  for symbol in ['ETHUSD','MCX:GOLD26DECFUT']:
   engine=Engine(dict(underlying=symbol),.05)
   self.assertAlmostEqual([engine.update(c) for c in self.rows()][-1]['box'],24)
 def test_minimum_tick_is_respected(self):
  engine=Engine(dict(underlying='NSE:TEST-EQ'),5)
  self.assertEqual([engine.update(c) for c in self.rows()][-1]['box'],5)
