import unittest
from copy import deepcopy
from strategies.ema_crossover.paper_capital import preflight
from strategies.ema_crossover.spread_policy import enabled
from .signals import settings
from .test_trend_reentry import ContinuationSubmissionTests,TogglePersistenceTests

class SpreadPolicyTests(unittest.TestCase):
 def setUp(self):
  self.state={'config':{'strategy':'RENKO_SUPERTREND_V1','mode':'PAPER','paper_capital_inr':100000},'order_history':[],'realized_pnl':0}
 def test_default_off_accepts_wide_executable_quote(self):
  self.assertFalse(settings({})['spread_filter_enabled']);self.assertFalse(enabled(self.state['config']))
  self.assertGreater(preflight(self.state,{'qty':1},{'quantity_multiplier':1},{'bid':80,'ask':100})['available_native'],0)
 def test_opt_in_blocks_wide_quote_and_accepts_boundary(self):
  self.state['config']['spread_filter_enabled']=True
  with self.assertRaisesRegex(ValueError,'3%'):preflight(self.state,{'qty':1},{},{'bid':80,'ask':100})
  preflight(self.state,{'qty':1},{'quantity_multiplier':1},{'bid':97,'ask':100})
 def test_quote_validity_remains_required_with_filter_off(self):
  for quote in [{'bid':0,'ask':100},{'bid':101,'ask':100},{'ask':100},{'bid':float('nan'),'ask':100},{'bid':True,'ask':100}]:
   with self.assertRaisesRegex(ValueError,'quote'):preflight(self.state,{'qty':1},{},quote)
 def test_other_strategies_keep_existing_default(self):
  self.state['config']['strategy']='RSI_BASED_EMA_V1'
  with self.assertRaisesRegex(ValueError,'3%'):preflight(self.state,{'qty':1},{},{'bid':80,'ask':100})
 def test_invalid_flag_fails_closed(self):
  for value in ['false',0,None]:
   with self.assertRaises(ValueError):enabled({'spread_filter_enabled':value})

class SpreadSubmissionTests(ContinuationSubmissionTests):
 def test_off_fills_wide_spread_without_broker_order(self):
  self.scenario();self.r.state['config']['spread_filter_enabled']=False
  self.b.quote=lambda symbol:{'bid':8,'ask':10}
  self.r._candle_step()
  self.assertIsNotNone(self.r.state.get('position'))
  self.assertEqual(self.r.state['position']['entry_price'],10)
  self.assertEqual(self.b.sent,[])
 def test_on_blocks_same_wide_spread(self):
  self.scenario();self.r.state['config']['spread_filter_enabled']=True
  self.b.quote=lambda symbol:{'bid':8,'ask':10}
  with self.assertRaisesRegex(ValueError,'3%'):self.r._candle_step()
  self.assertFalse(self.r.state.get('position'));self.assertFalse(self.r.state.get('order_history'))

class SpreadToggleTests(TogglePersistenceTests):
 def test_save_on_off_preserves_run_and_exposure(self):
  from . import preferences
  self.r.state['position']={'symbol':'TEST','quantity':1}
  for flag in [True,False]:
   self.r.set_spread_filter({'enabled':flag})
   self.assertIs(self.r.state['config']['spread_filter_enabled'],flag)
   self.assertIs(self.r.adapter.entry_spread_filter_enabled,flag)
   saved=preferences.read(self.r.path.with_name('renko-supertrend-settings.json'))
   self.assertIs(saved['settings']['spread-filter-enabled'],flag)
  self.assertEqual(self.r.state['run_id'],'same');self.assertEqual(self.r.state['trades_used'],3)
  self.assertEqual(self.r.state['position'],{'symbol':'TEST','quantity':1});self.assertEqual(self.b.sent,[])
