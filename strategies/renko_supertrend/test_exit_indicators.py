import unittest
from .exit_indicators import settings, reason
class IndependentExitTests(unittest.TestCase):
 def test_disabled_entry_supertrend_does_not_disable_exit(self):
  self.assertEqual(reason({'supertrend_enabled':False},{'supertrend_cross_direction':'BEARISH'},'BULLISH'),'RENKO_ST_EXIT')
 def test_disabled_exit_ignores_reversal(self):
  self.assertIsNone(reason({'supertrend_exit_enabled':False},{'supertrend_cross_direction':'BEARISH'},'BULLISH'))
 def test_selected_rsi_is_independent_of_entry_rsi(self):
  self.assertEqual(reason({'supertrend_exit_enabled':False,'rsi_slope_enabled':False,'rsi_exit_enabled':True},{'rsi14_slope':-1},'BULLISH'),'RSI_OPPOSING_SLOPE')
 def test_forming_candle_never_exits(self):
  self.assertIsNone(reason({'rsi_exit_enabled':True},{'is_forming':True,'rsi14_slope':-1,'supertrend_cross_direction':'BEARISH'},'BULLISH'))
 def test_new_exits_are_opt_in(self):
  self.assertIsNone(reason(settings({}),{'rsi14_slope':-1,'adx':0,'ema_gap':1,'exit_previous_ema_gap':3,'close':1,'ema30':2},'BULLISH'))
 def test_gap_contraction_and_adx_threshold(self):
  self.assertEqual(reason({'ema_widening_exit_enabled':True},{'ema_gap':-2,'exit_previous_ema_gap':-3},'BEARISH'),'EMA_GAP_CONTRACTION')
  self.assertIsNone(reason({'adx_exit_enabled':True},{'adx':25},'BULLISH'))
  self.assertEqual(reason({'adx_exit_enabled':True},{'adx':24},'BULLISH'),'ADX_BELOW_THRESHOLD')
 def test_opposing_swings_and_second_ema(self):
  self.assertEqual(reason({'market_structure_exit_enabled':True},{'exit_market_structure':{'state':'BULLISH_HH_HL'}},'BEARISH'),'OPPOSING_CONFIRMED_SWINGS')
  self.assertEqual(reason({'ema_slow_exit_enabled':True,'ema_slow_length':35},{'close':4,'ema30':3},'BEARISH'),'EMA35_CONFIRMED_BREACH')
 def test_boolean_validation(self):
  with self.assertRaises(ValueError):settings({'supertrend_exit_enabled':'false'})

 def test_historical_exits_follow_explicit_selection(self):
  from .signals import series
  from .test_signals import candle
  base=dict(atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,rsi_slope_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False,ema_widening_enabled=False,ema_exit_enabled=False)
  bars=[candle(i,v) for i,v in enumerate([100,110,120,100,80,90,120])]
  self.assertFalse(any((r.get('lifecycle_event') or '').endswith('EXIT') for r in series(bars,{**base,'supertrend_exit_enabled':False})))
  self.assertTrue(any(r.get('lifecycle_reason')=='RENKO_ST_EXIT' for r in series(bars,{**base,'supertrend_exit_enabled':True})))
