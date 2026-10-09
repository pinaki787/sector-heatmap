import unittest, tempfile
from pathlib import Path
from .signals import series, settings
from .test_signals import candle
from .preferences import write, read
BASE=dict(atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,rsi_slope_enabled=False)
PURE={**BASE,'ema_fast_enabled':False,'ema_slow_enabled':False,'ema_widening_enabled':False}
class IndependentIndicators(unittest.TestCase):
 def test_supertrend_only_enters_on_reversals_without_ema_delay(self):
  rows=series([candle(i,p) for i,p in enumerate([100,110,120,100,80,90,120])],PURE)
  self.assertTrue(any(r['buy_signal'] for r in rows))
  for r in rows:self.assertEqual(r['entry_direction'],r['cross_direction'])
 def test_disabling_widening_removes_the_delay(self):
  bars=[candle(i,p) for i,p in enumerate([100,110,120,130])]
  self.assertFalse(series(bars,{**BASE,'widening_window':3})[1]['entry_qualified'])
  self.assertTrue(series(bars,{**BASE,'ema_widening_enabled':False})[1]['entry_qualified'])
 def test_ema_only_does_not_wait_for_opposing_supertrend(self):
  rows=series([candle(i,p) for i,p in enumerate([100,101,102,103])],dict(supertrend_enabled=False,ema_fast_enabled=True,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,manual_brick=100,brick_mode='Manual'))
  self.assertEqual(rows[1]['entry_direction'],'BULLISH');self.assertEqual(rows[1]['direction'],'BULLISH');self.assertIsNone(rows[1]['cross_direction'])
 def test_no_indicators_is_candles_only_without_entries(self):
  rows=series([candle(i,p) for i,p in enumerate([100,110,120])],{**PURE,'supertrend_enabled':False})
  self.assertTrue(all(not r['entry_qualified'] for r in rows))
 def test_custom_periods_are_actual_calculations(self):
  rows=series([candle(0,100),candle(1,110)],{**BASE,'ema_fast_length':5,'ema_widening_enabled':False})
  self.assertAlmostEqual(rows[1]['ema10'],100+10/3)
 def test_invalid_hidden_dependency_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'shorter'):settings(dict(ema_fast_length=30,ema_slow_length=10))
 def test_preferences_round_trip_each_checkbox_and_period(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'prefs.json';v={'supertrend-enabled':True,'ema-fast-enabled':False,'ema-slow-enabled':False,'ema-widening-enabled':False,'ema-fast-length':5,'ema-slow-length':30,'rsi-slope-enabled':False}
   write(p,{'settings':v},123);self.assertEqual(read(p)['settings'],v)
 def test_rsi_filter_blocks_supertrend_when_selected(self):
  rows=series([candle(i,p) for i,p in enumerate([100,110,120])],{**PURE,'rsi_slope_enabled':True})
  self.assertTrue(all(r['entry_direction'] is None for r in rows))
 def test_widening_can_run_without_ema_line_selections(self):
  rows=series([candle(i,p) for i,p in enumerate([100,110,120,130])],{**PURE,'supertrend_enabled':False,'ema_widening_enabled':True})
  self.assertTrue(any(r['entry_direction']=='BULLISH' for r in rows))
 def test_custom_rsi_period_matches_wilder_math(self):
  from .rsi_slope import observe
  state={}
  for p in [100,102,101,103]:value=observe(state,p,3)
  self.assertAlmostEqual(value['rsi14'],80)
 def test_new_configuration_defaults_both_timing_options_off(self):
  from .runner import configuration
  cfg=configuration(dict(strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',mode='PAPER',lots=1,max_trades=1))
  self.assertFalse(cfg['intrabar_entries']);self.assertFalse(cfg['ema_exit_enabled'])
 def test_false_is_not_coerced_from_a_string(self):
  with self.assertRaises(ValueError):settings(dict(supertrend_enabled='false'))
