import unittest,copy
from . import rsi_slope,signals
class RSI(unittest.TestCase):
 def test_warmup(self):
  s={}
  for n in range(15):
   v=rsi_slope.observe(s,100+(n%3))
   if n<14:self.assertIsNone(v['rsi14'])
  self.assertIsNone(v['rsi14_slope']);self.assertIsNotNone(rsi_slope.observe(s,103)['rsi14_slope'])
 def test_flat(self):
  s={}
  for _ in range(16):v=rsi_slope.observe(s,100)
  self.assertEqual(v['rsi14'],50);self.assertEqual(v['rsi14_slope'],0)
 def test_entry_paths(self):
  for retest in [False,True]:
   for direction in ['BULLISH','BEARISH']:
    for slope in [None,0,1,-1]:
     for enabled in [False,True]:
      e=dict(entry_qualified=True,entry_direction=direction,entry_buy_signal=direction=='BULLISH',entry_sell_signal=direction=='BEARISH',retest_signal=retest);s={'ema_qualified':direction}
      rsi_slope.apply(e,s,dict(rsi14=55,rsi14_previous=54,rsi14_slope=slope),direction,enabled)
      expected=not enabled or slope is not None and (slope>0 if direction=='BULLISH' else slope<0)
      self.assertEqual(e['entry_qualified'],expected)
      if retest:self.assertEqual(e['retest_signal'],expected)
 def test_clone(self):
  s={}
  for n in range(18):rsi_slope.observe(s,100+(n%5))
  old=copy.deepcopy(s);rsi_slope.observe(copy.deepcopy(s),120);self.assertEqual(s,old)
 def test_wilder(self):
  s={};closes=[100,101,99,103,102,104,100,105,103,104,102,106,105,107,104,108]
  for c in closes:v=rsi_slope.observe(s,c)
  gains=sum(max(closes[i]-closes[i-1],0) for i in range(1,15))/14
  losses=sum(max(closes[i-1]-closes[i],0) for i in range(1,15))/14
  gains=(gains*13+4)/14;losses=losses*13/14
  self.assertAlmostEqual(v['rsi14'],100-100/(1+gains/losses))

class Defaults(unittest.TestCase):
 def test_new_default_and_explicit_off(self):
  self.assertTrue(signals.settings({})["rsi_slope_enabled"])
  self.assertFalse(signals.settings({"rsi_slope_enabled":False})["rsi_slope_enabled"])
