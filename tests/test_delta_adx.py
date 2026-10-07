import unittest, math
from copy import deepcopy
from sector_heatmap import delta_adx
from tests import test_delta_atm_runner as fixture

class AdxMath(unittest.TestCase):
 def candles(self,flat=False):
  return [dict(timestamp=i*300,open=100+i,high=100 if flat else 102+i,low=100 if flat else 99+i,close=100 if flat else 101+i,is_forming=False) for i in range(50)]
 def test_wilder_warmup_trend_flat_and_forming_exclusion(self):
  rows=self.candles();v=delta_adx.series(rows);self.assertIsNone(v[26*300]);self.assertEqual(v[27*300],100);self.assertEqual(v[49*300],100)
  self.assertEqual(delta_adx.series(self.candles(True))[49*300],0)
  rows[-1]['is_forming']=True;self.assertNotIn(49*300,delta_adx.series(rows))
 def test_default_off_strict_threshold_and_unavailable_fail_closed(self):
  self.assertFalse(delta_adx.settings({})['adx_enabled'])
  for value in (None,float('nan'),25,24.9):self.assertFalse(delta_adx.allows(dict(adx_enabled=True,adx_threshold=25),value))
  self.assertTrue(delta_adx.allows(dict(adx_enabled=True,adx_threshold=25),25.1));self.assertTrue(delta_adx.allows({},None))
  for payload in (dict(adx_enabled='true'),dict(adx_threshold=True),dict(adx_threshold=100),dict(adx_threshold=float('nan'))):
   with self.assertRaises(ValueError):delta_adx.settings(payload)

class AdxRunner(unittest.TestCase):
 setUp=fixture.AtmOptionRunner.setUp
 signal=fixture.AtmOptionRunner.signal
 config=fixture.AtmOptionRunner.config
 def test_blocks_entries_but_never_opposite_exit(self):
  from unittest.mock import patch
  with patch('sector_heatmap.delta_india.threading.Thread'):
   self.b.start_runner(self.config()|dict(adx_enabled=True,adx_threshold=25))
  for value in (None,20,25):
   self.req.now+=300;self.signal('BULLISH');base=self.b.chart();self.b.chart=lambda *a,base=base,value=value,**k:dict(last_completed=base['last_completed']|dict(adx=value));self.b.runner_tick();self.assertIsNone(self.b.paper['position'])
  self.req.now+=300;self.signal('BULLISH');base=self.b.chart();self.b.chart=lambda *a,**k:dict(last_completed=base['last_completed']|dict(adx=30));self.b.runner_tick();self.assertIsNotNone(self.b.paper['position'])
  self.req.now+=300;self.signal('BEARISH');base=self.b.chart();self.b.chart=lambda *a,**k:dict(last_completed=base['last_completed']|dict(adx=5));self.b.runner_tick();self.assertIsNone(self.b.paper['position']);self.assertEqual(len(self.b.paper['trades']),1)
