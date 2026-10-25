import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from .signals import settings,series
from .indicator_selection import qualify
from . import destinations,preferences
from .retest import evaluate
from .test_signals import candle

class ThirdEmaTests(unittest.TestCase):
 def cfg(self,**kw):return settings(dict(rsi_slope_enabled=False,ema_widening_enabled=False,**kw))
 def test_default_and_strict_validation(self):
  c=self.cfg();self.assertTrue(c['ema_third_enabled']);self.assertEqual(c['ema_third_length'],100)
  for value in [True,0,1001,2.5,'NaN']:
   with self.subTest(value=value),self.assertRaises(ValueError):self.cfg(ema_third_length=value)
  with self.assertRaises(ValueError):self.cfg(ema_third_enabled='false')
 def test_bullish_and_bearish_order_and_price_gate(self):
  c=self.cfg()
  self.assertTrue(qualify(c,110,108,106,-1,True,True,None,None,104)[1])
  self.assertEqual(qualify(c,110,108,106,-1,True,True,None,None,107)[2],'WAITING_EMA_THIRD')
  self.assertEqual(qualify(c,110,108,106,-1,True,True,None,None,110)[2],'WAITING_EMA_THIRD')
  self.assertTrue(qualify(c,90,92,94,1,True,True,None,None,96)[1])
  self.assertFalse(qualify(c,90,92,94,1,True,True,None,None,93)[1])
 def test_third_only_direction_and_disabled_no_gate(self):
  c=self.cfg(supertrend_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False)
  self.assertEqual(qualify(c,110,1,2,0,True,False,None,None,100)[:2],(-1,True))
  self.assertEqual(qualify(c,90,1,2,0,True,False,None,None,100)[:2],(1,True))
  self.assertFalse(qualify(c,100,1,2,0,True,False,None,None,100)[1])
  c=self.cfg(ema_third_enabled=False)
  self.assertTrue(qualify(c,110,108,106,-1,True,True,None,None,None)[1])
 def test_actual_ema_recursion_and_disable_parity(self):
  bars=[candle(i,p) for i,p in enumerate([100,110,90,120,80,130])]
  rows=series(bars,dict(ema_third_length=3,rsi_slope_enabled=False))
  self.assertEqual(rows[0]['ema100'],100);self.assertEqual(rows[1]['ema100'],105);self.assertEqual(rows[2]['ema100'],97.5)
  a=series(bars,dict(ema_third_enabled=False,ema_third_length=2,rsi_slope_enabled=False))
  b=series(bars,dict(ema_third_enabled=False,ema_third_length=500,rsi_slope_enabled=False))
  keys=['entry_direction','entry_qualified','entry_diagnostic','lifecycle_event','ema_gap','ema_widening']
  self.assertEqual([{k:r[k] for k in keys} for r in a],[{k:r[k] for k in keys} for r in b])
 def test_family_and_chart_destinations_are_independent(self):
  c=settings(dict(ema_family_enabled=False,ema_third_enabled=True));self.assertFalse(c['ema_third_enabled'])
  self.assertTrue(c['indicator_family_choices']['ema_third_enabled'])
  self.assertFalse(destinations.chart(dict(ema_third_enabled=True,ema_third_enabled_indicator=False))['ema_third_enabled'])
 def test_preferences_keep_false_custom_period_and_legacy_file(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'settings.json';raw=json.dumps(dict(settings={'ema-fast-enabled':False,'ema-slow-length':45},schema_version=1));p.write_text(raw)
   preferences.read(p);self.assertEqual(p.read_text(),raw)
   fields={'ema-fast-enabled':False,'ema-slow-length':45,'ema-third-enabled':False,'ema-third-enabled-indicator':True,'ema-third-length':77}
   self.assertEqual(preferences.write(p,dict(settings=fields),100)['settings'],fields)
 def test_retest_cannot_bypass_selected_third_ema(self):
  state=dict(retest_direction='BULLISH',retest_ready=True)
  bar=dict(timestamp=600,open=101,high=103,low=99,close=102)
  entry=dict(ema10=101,ema30=95,ema100=110)
  with patch('strategies.renko_supertrend.retest.matches',return_value=['ENGULFING']):
   a=evaluate(dict(state),bar,dict(timestamp=300),[100,94],-1,-1,entry,True,dict(host_seconds=300,ema_third_enabled=True))
   b=evaluate(dict(state),bar,dict(timestamp=300),[100,94],-1,-1,entry,True,dict(host_seconds=300,ema_third_enabled=False))
  self.assertFalse(a['retest_signal']);self.assertTrue(b['retest_signal'])
if __name__=='__main__':unittest.main()
