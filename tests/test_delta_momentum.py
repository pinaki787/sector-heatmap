import unittest
from unittest.mock import patch
from sector_heatmap.delta_signals import momentum_evidence,momentum_allows,momentum_settings
from tests import test_delta_atm_runner as fixture

class MomentumMath(unittest.TestCase):
 def test_strict_completed_close_and_slope_both_directions(self):
  prior=dict(high=110,low=90,rsi_ma=50)
  for close,ma,bull,bear in [(111,51,True,False),(110,51,False,False),(111,50,False,False),(89,49,False,True),(90,49,False,False),(89,51,False,False)]:
   e=momentum_evidence(dict(close=close,rsi_ma=ma),prior)
   self.assertEqual((e['bullish'],e['bearish']),(bull,bear))
 def test_missing_warmup_default_off_and_validation(self):
  self.assertIsNone(momentum_evidence(dict(close=111,rsi_ma=None),dict(high=110,low=90,rsi_ma=50)))
  self.assertFalse(momentum_settings({})['momentum_enabled'])
  with self.assertRaises(ValueError):momentum_settings(dict(momentum_enabled='true'))
  self.assertFalse(momentum_allows(dict(momentum_enabled=True),{},'BULLISH'))
  self.assertTrue(momentum_allows({}, {},'BULLISH'))

class MomentumRunner(unittest.TestCase):
 setUp=fixture.AtmOptionRunner.setUp
 signal=fixture.AtmOptionRunner.signal
 config=fixture.AtmOptionRunner.config
 def test_block_then_entry_and_exit_bypasses_momentum(self):
  with patch('sector_heatmap.delta_india.threading.Thread'):
   self.b.start_runner(self.config()|dict(momentum_enabled=True,adx_enabled=True,adx_threshold=31))
  for direction in ['BULLISH','BEARISH']:
   self.req.now+=300;self.signal(direction);base=self.b.chart()
   self.b.chart=lambda *a,base=base,**k:dict(last_completed=base['last_completed']|dict(adx=40,momentum=None))
   self.b.runner_tick();self.assertIsNone(self.b.paper['position'])
  self.req.now+=300;self.signal('BULLISH');base=self.b.chart()
  self.b.chart=lambda *a,**k:dict(last_completed=base['last_completed']|dict(adx=40,momentum=dict(bullish=True,bearish=False)))
  self.b.runner_tick();self.assertIsNotNone(self.b.paper['position'])
  # Journal settings must retain the actual runner flags and threshold.
  self.b.chart=lambda *a,**k:dict(symbol='BTCUSD',candles=[dict(timestamp=300*(i+1),open=100+i,high=102+i,low=99+i,close=101+i,volume=7,is_forming=False) for i in range(35)])
  context=self.b._journal_context({},'CROSSOVER')
  self.assertTrue(context['adx']['filter_enabled']);self.assertEqual(context['adx']['threshold'],31);self.assertTrue(context['momentum']['enabled'])
  self.req.now+=300;self.signal('BEARISH');base=self.b.chart()
  self.b.chart=lambda *a,**k:dict(last_completed=base['last_completed']|dict(adx=0,momentum=None))
  self.b.runner_tick();self.assertIsNone(self.b.paper['position'])
