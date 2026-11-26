import unittest
from unittest.mock import patch
from core import Strategy
from sma_band import BandPolicy
from ui_bridge import configuration
class SignalSourceExitTests(unittest.TestCase):
 def config(self,source='UNDERLYING',**extra):
  return dict(account='a'*32,reference_value=120,market='NSE',underlying='NSE:TEST-EQ',execution_route='OPTIONS',timeframe=1,signal_source=source,entry_gate='underlying_flip' if source=='UNDERLYING' else 'underlying_trend_premium_flip',exit_supertrend='underlying' if source=='UNDERLYING' else 'premium',band_price_basis='underlying' if source=='UNDERLYING' else 'premium',**extra)
 def event(self,series,i,opening,high,low,close,symbol=None):
  return dict(kind=series,timestamp=1000+i*60,closed_at=1060+i*60,available_at=1061+i*60,open=opening,high=high,low=low,close=close,symbol=symbol,closed=True,body_available=True,source_basis='PROVIDER_CONFIRMED_CLOSE')
 def engine(self,source='UNDERLYING',side='CE',**extra):
  e=Strategy(self.config(source,**extra));e.reset_contract(dict(symbol=side,option_type=side),.2);return e
 def test_bridge_selects_both_decisions_and_band_source(self):
  p=dict(account_id='a'*32,broker='FYERS',underlying='NSE:TEST-EQ',timeframe='1 minute')
  with patch('ui_bridge.owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',return_value=None):
   for source,series in [('UNDERLYING','underlying'),('PREMIUM','premium')]:
    c=configuration(dict(p,ai_signal_source=source),'a'*32)
    self.assertEqual(c['signal_source'],source);self.assertEqual(c['exit_supertrend'],series);self.assertEqual(c['band_price_basis'],series)
 def test_underlying_mode_does_not_calculate_premium_indicator(self):
  e=self.engine()
  e.option_ai.update=lambda *_:self.fail('Premium indicator must not run')
  self.assertEqual(e.update_hybrid(dict(kind='price',series='premium',symbol='CE',timestamp=2000,close=20)),[])
  self.assertIsNone(e.premium_result)
 def test_underlying_supertrend_exit_needs_no_sma_or_premium(self):
  for side,direction,st,opening,close in [('CE',1,110,100,99),('PE',-1,90,99,100)]:
   e=self.engine(side=side);e.under_result=dict(direction=direction,st=st);e.manual_entry(side,900)
   actions=e.update_hybrid(self.event('underlying',1,opening,101,98,close))
   self.assertEqual(actions[0]['action'],'SELL');self.assertEqual(actions[0]['reason'],'AI_RENKO_SUPERTREND_UNDERLYING')
   self.assertIsNone(e.pending_underlying_flip)
 def test_underlying_band_can_exit_while_supertrend_still_favorable(self):
  e=self.engine(sma_band_period=2,sma_band_entry=True,sma_band_exit=True)
  for i in range(2):e.band.observe(self.event('underlying',i,100,110,90,100),e.config)
  e.under_result=dict(direction=-1,st=10);e.manual_entry('CE',1100)
  actions=e.update_hybrid(self.event('underlying',2,55,60,49,50))
  self.assertEqual(actions[0]['reason'],'OPTIONAL_UNDERLYING_SMA_BAND')
 def test_premium_band_treats_bought_put_as_long_premium(self):
  c=self.config('PREMIUM',sma_band_period=2,sma_band_entry=True,sma_band_exit=True,band_symbol='PE');b=BandPolicy(c)
  for i in range(2):b.observe(self.event('premium',i,20,21,19,20,'PE'),c)
  b.observe(dict(kind='price',series='premium',timestamp=1200,close=22,symbol='PE'),c)
  self.assertFalse(b.allows('PE',c)) # Price above the band is not a completed retest.
  b.observe(self.event('premium',2,18,19,17,17.5,'PE'),c)
  self.assertEqual(b.exit_reason(dict(side='PE')),'OPTIONAL_PREMIUM_SMA_BAND')
 def test_premium_band_exit_independent_of_bullish_premium_supertrend(self):
  e=self.engine('PREMIUM','PE',sma_band_period=2,sma_band_entry=True,sma_band_exit=True)
  for i in range(2):e.band.observe(self.event('premium',i,20,21,19,20,'PE'),e.config)
  e.under_result=dict(direction=1,st=200);e.premium_result=dict(direction=-1,st=5);e.manual_entry('PE',1100)
  actions=e.update_hybrid(self.event('premium',2,18,19,17,17.5,'PE'))
  self.assertEqual(actions[0]['reason'],'OPTIONAL_PREMIUM_SMA_BAND')
 def test_premium_supertrend_exit_ignores_underlying_and_disabled_bands(self):
  e=self.engine('PREMIUM');e.under_result=dict(direction=-1,st=1);e.premium_result=dict(direction=1,st=30);e.manual_entry('CE',900)
  actions=e.update_hybrid(self.event('premium',1,20,21,19,19.5,'CE'))
  self.assertEqual(actions[0]['reason'],'AI_RENKO_SUPERTREND_PREMIUM')
 def test_premium_band_does_not_consume_underlying_candles(self):
  e=self.engine('PREMIUM',sma_band_period=2,sma_band_entry=True)
  for i in range(2):e.band.observe(self.event('underlying',i,100,110,90,100),e.config)
  self.assertFalse(e.band.allows('CE',e.config));self.assertEqual(e.band.history['SMA'],[])
 def test_premium_retest_followup_can_reenter_a_bought_put(self):
  e=self.engine('PREMIUM','PE',sma_band_period=2,sma_band_entry=True,sma_band_exit=True)
  for i in range(2):e.band.observe(self.event('premium',i,20,21,19,20,'PE'),e.config)
  e.under_result=dict(direction=1,st=200);e.premium_result=dict(direction=-1,st=5)
  self.assertEqual(e.update_hybrid(self.event('premium',2,22,22,20.5,21,'PE')),[])
  actions=e.update_hybrid(self.event('premium',3,21.2,23,21,22.8,'PE'))
  self.assertEqual(actions[0]['action'],'BUY');self.assertEqual(actions[0]['position']['side'],'PE')
 def test_contract_change_clears_previous_premium_band(self):
  e=self.engine('PREMIUM',sma_band_period=2,sma_band_entry=True)
  for i in range(2):e.band.observe(self.event('premium',i,20,21,19,20,'CE'),e.config)
  e.reset_contract(dict(symbol='NEWPE',option_type='PE'),-.2)
  self.assertFalse(e.band.allows('PE',e.config));self.assertEqual(e.band.snapshot(e.config)['underlying'],'NEWPE')
if __name__=='__main__':unittest.main()
