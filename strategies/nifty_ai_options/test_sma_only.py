import unittest
from unittest.mock import patch
from core import Strategy
from direct import DirectStrategy
from manual_entry import clear_entry_signal
def candle(at,close,kind='underlying',**extra):
 return dict(kind=kind,timestamp=at,open=extra.pop('open',close),high=extra.pop('high',close+1),low=extra.pop('low',close-1),close=close,closed=True,body_available=True,source_basis='PROVIDER_CONFIRMED_CLOSE',closed_at=at+60,available_at=at+60,**extra)
def config(**extra):
 return dict(reference_value=120,market='NSE',underlying='NSE:T-EQ',timeframe=1,product='MARGIN',calculation_mode='CANDLES',supertrend_enabled=False,sma_band_entry=True,sma_band_exit=True,sma_band_period=2,signal_source='UNDERLYING',band_price_basis='underlying',entry_gate='underlying_flip',**extra)
def warm(e,kind='underlying',**kw):
 for t in (100,160):e.update_hybrid(candle(t,10,kind,**kw))
def retest(e,kind='underlying',**kw):
 return e.update_hybrid(candle(220,10,kind,open=12,high=13,low=9,**kw))
def follow(e,kind='underlying',**kw):
 return e.update_hybrid(candle(280,16,kind,open=10,high=16,low=10,**kw))
class SmaOnlyTests(unittest.TestCase):
 def test_direct_requires_retest_then_followup_and_exits_without_supertrend(self):
  e=DirectStrategy(config())
  with patch.object(e.under_ai,'update',side_effect=AssertionError('Supertrend evaluated')):
   warm(e);self.assertEqual(retest(e),[])
   self.assertEqual(follow(e)[0]['action'],'OPEN_LONG')
   self.assertEqual(e.update_hybrid(candle(340,6))[0]['action'],'CLOSE_LONG')
 def test_far_away_initial_entry_and_reentry_are_blocked(self):
  e=DirectStrategy(config());warm(e)
  for t in (220,280,340):self.assertEqual(e.update_hybrid(candle(t,30)),[])
  self.assertIsNone(e.position)
  e=DirectStrategy(config());warm(e);retest(e);follow(e);e.update_hybrid(candle(340,6))
  self.assertEqual(e.update_hybrid(candle(400,30)),[]);self.assertIsNone(e.position)
 def test_short_retest_mirrors_bullish_rule(self):
  e=DirectStrategy(config());warm(e)
  self.assertEqual(e.update_hybrid(candle(220,10,open=8,high=11,low=7)),[])
  self.assertEqual(e.update_hybrid(candle(280,4,open=10,high=10,low=4))[0]['action'],'OPEN_SHORT')
  self.assertEqual(e.update_hybrid(candle(340,16))[0]['action'],'CLOSE_SHORT')
 def test_incomplete_wrong_color_missing_next_and_duplicate_cannot_enter(self):
  for invalid in ('forming','wrong_color','gap'):
   e=DirectStrategy(config());warm(e);retest(e)
   x=candle(340 if invalid=='gap' else 280,16,open=10,high=16,low=10)
   if invalid=='forming':x['closed']=False
   if invalid=='wrong_color':x.update(open=17,high=17)
   self.assertEqual(e.update_hybrid(x),[]);self.assertIsNone(e.position)
  e=DirectStrategy(config());warm(e);retest(e)
  with self.assertRaises(ValueError):retest(e)
 def test_options_choose_call_from_sma_retest_without_supertrend(self):
  e=Strategy(config());e.reset_contract(dict(symbol='PUT',option_type='PE'),.2)
  with patch.object(e.under_ai,'update',side_effect=AssertionError('Supertrend evaluated')):
   warm(e);retest(e);a=follow(e);self.assertEqual(a[0]['action'],'SELECT');self.assertEqual(a[0]['side'],'CE')
   e.reset_contract(dict(symbol='CALL',option_type='CE'),.2)
   self.assertEqual(e.selected_gate_entry()['action'],'BUY')
   self.assertEqual(e.update_hybrid(candle(340,6))[0]['action'],'SELL')
 def test_premium_put_uses_its_own_retest_without_supertrend(self):
  e=Strategy(config());e.config.update(signal_source='PREMIUM',band_price_basis='premium');e.reset_contract(dict(symbol='PUT',option_type='PE'),.2)
  with patch.object(e.option_ai,'update',side_effect=AssertionError('Supertrend evaluated')):
   warm(e,'premium',symbol='PUT');retest(e,'premium',symbol='PUT')
   self.assertEqual(follow(e,'premium',symbol='PUT')[0]['action'],'BUY')
   self.assertEqual(e.update_hybrid(candle(340,6,'premium',symbol='PUT'))[0]['action'],'SELL')
 def test_stale_confirmation_and_consumed_setup_are_blocked(self):
  e=Strategy(config());e.reset_contract(dict(symbol='PUT',option_type='PE'),.2);warm(e);retest(e);follow(e)
  e.reset_contract(dict(symbol='CALL',option_type='CE'),.2);e.entry_observation_at=401
  self.assertIsNone(e.selected_gate_entry())
  clear_entry_signal(e);self.assertIsNone(e.band.entry_retest)
 def test_other_indicators_cannot_be_enabled_in_sma_only(self):
  with self.assertRaises(ValueError):DirectStrategy(config(ema_band_exit=True))


class EverySmaEntryRetestTests(unittest.TestCase):
 def engine(self,options=False,exit_enabled=True):
  c=config();c['supertrend_enabled']=True;c['sma_band_exit']=exit_enabled
  e=Strategy(c) if options else DirectStrategy(c)
  if options:e.reset_contract(dict(symbol='CALL',option_type='CE'),.2)
  e.under_ai.update=lambda bar:dict(direction=-1,st=1,flip=True)
  return e
 def test_fresh_supertrend_flip_far_above_band_cannot_enter(self):
  for options in (False,True):
   e=self.engine(options);warm(e)
   self.assertEqual(e.update_hybrid(candle(220,30)),[])
   self.assertIsNone(e.position)
 def test_entry_only_sma_filter_also_requires_valid_retest(self):
  e=self.engine(exit_enabled=False);warm(e)
  self.assertEqual(retest(e),[])
  self.assertEqual(follow(e)[0]['action'],'OPEN_LONG')
 def test_legacy_update_path_uses_same_retest_gate(self):
  for options in (False,True):
   e=self.engine(options)
   for t in (100,160):e.update(candle(t,10))
   self.assertEqual(e.update(candle(220,30)),[])
   # Reinitialize so the reference band reflects the intended retest, not the far-away bar.
   e=self.engine(options)
   for t in (100,160):e.update(candle(t,10))
   self.assertEqual(e.update(candle(220,10,open=12,high=13,low=9)),[])
   a=e.update(candle(280,16,open=10,high=16,low=10))
   self.assertEqual(a[0]['action'],'BUY' if options else 'OPEN_LONG')
   self.assertIsNone(e.band.entry_retest)
