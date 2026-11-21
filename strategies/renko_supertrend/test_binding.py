import unittest,tempfile,json,threading
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from .binding import normalize_settings,validate_request
from . import preferences
from .delta_runner import DeltaRunner

class ScopeTests(unittest.TestCase):
 def test_delta_ignores_hidden_mcx_and_cash_fields(self):
  x=normalize_settings({'symbol':'BTCUSD','commodity-holding':'','cash-product':None},'DELTA_INDIA','BTCUSD')
  self.assertNotIn('commodity-holding',x);self.assertNotIn('cash-product',x)
 def test_saved_crypto_preferences_do_not_require_mcx_policy(self):
  with tempfile.TemporaryDirectory() as t:
   d=preferences.write(Path(t)/'settings.json',{'settings':{'symbol':'BTCUSD','commodity-holding':None,'cash-product':''}},10,scope={'broker':'DELTA_INDIA','instrument':'BTCUSD'})
   self.assertEqual(d['settings']['symbol'],'BTCUSD');self.assertNotIn('commodity-holding',d['settings'])
 def test_invalid_mcx_policy_still_fails(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'MCX holding'):preferences.write(Path(t)/'s.json',{'settings':{'symbol':'MCX:GOLDM26NOVFUT','commodity-holding':'BOGUS'}},10,scope={'broker':'FYERS','instrument':'MCX:GOLDM26NOVFUT'})
 def test_cross_symbol_settings_rejected_before_write(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'s.json'
   with self.assertRaisesRegex(ValueError,'instrument'):preferences.write(p,{'settings':{'symbol':'ETHUSD'}},10,scope={'broker':'DELTA_INDIA','instrument':'BTCUSD'})
   self.assertFalse(p.exists())
 def test_broker_account_and_payload_symbol_checked(self):
  for p in [{'broker':'FYERS'},{'account_id':'other'},{'underlying':'ETHUSD'},{'settings':{'symbol':'ETHUSD'}}]:
   with self.assertRaises(ValueError):validate_request(p,'DELTA_INDIA','BTCUSD','delta-account')
  validate_request({'broker':'DELTA_INDIA','account_id':'delta-account','underlying':'BTCUSD'},'DELTA_INDIA','BTCUSD','delta-account')
 def test_broker_segment_mismatch_rejected(self):
  for b,s in [('DELTA_INDIA','MCX:GOLDM26NOVFUT'),('FYERS','BTCUSD'),('DHAN','BTCUSD'),('MOTILAL_OSWAL','ETHUSD')]:
   with self.assertRaises(ValueError):normalize_settings({'symbol':s},b,s)
 def test_indian_preferences_do_not_keep_crypto_policy(self):
  x=normalize_settings({'symbol':'MCX:GOLDM26NOVFUT','commodity-holding':'CARRY_FORWARD','carry-policy':'CONTINUOUS','delta-execution-route':'DELTA_PERPETUAL'},'FYERS','MCX:GOLDM26NOVFUT')
  self.assertEqual(x['commodity-holding'],'CARRY_FORWARD');self.assertNotIn('carry-policy',x);self.assertNotIn('delta-execution-route',x)

class DeltaPreferenceOwnershipTests(unittest.TestCase):
 def test_both_flags_write_only_bound_delta_preferences(self):
  with tempfile.TemporaryDirectory() as t:
   r=object.__new__(DeltaRunner);r.path=Path(t)/'renko-delta-state.json';r.clock=lambda:100
   r.lock=threading.RLock();r.adapter=SimpleNamespace();r.bound_instrument='BTCUSD'
   r.state={'config':{'broker':'DELTA_INDIA','underlying':'BTCUSD','mode':'PAPER'},'run_id':'owned','trades_used':2}
   r.save=lambda:None;r.snapshot=lambda:deepcopy(r.state)
   r.set_trend_reentry({'enabled':False});r.set_spread_filter({'enabled':True})
   p=Path(t)/'renko-delta-settings.json'
   self.assertTrue(p.exists());self.assertFalse((Path(t)/'renko-supertrend-settings.json').exists())
   d=r.read_preferences();self.assertEqual(d['binding'],{'broker':'DELTA_INDIA','instrument':'BTCUSD'})
   self.assertEqual(d['settings']['symbol'],'BTCUSD');self.assertFalse(d['settings']['trend-reentry-enabled']);self.assertTrue(d['settings']['spread-filter-enabled'])
   self.assertEqual(r.state['run_id'],'owned');self.assertEqual(r.state['trades_used'],2)
 def test_orphan_state_does_not_accept_an_action(self):
  r=object.__new__(DeltaRunner);r.bound_instrument='BTCUSD';r.state={'config':{'underlying':'ETHUSD','broker':'DELTA_INDIA'}}
  with self.assertRaisesRegex(ValueError,'Saved task instrument'):r.validate_binding({})

