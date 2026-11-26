import unittest,copy
from direct import DirectStrategy
from core import Strategy
from test_completed_unit_hybrid import config,candle,tick,BASE
from indicator import AIRenko,Traditional
class BrickBasisRuntimeTests(unittest.TestCase):
 def warm(self,cls=DirectStrategy):
  e=cls(config(supertrend_basis='COMPLETED_RENKO'))
  for i,p in enumerate([100,99,98,97,96,95,94,95,96,97,98,99,100]*3):
   e.update(dict(kind='underlying',timestamp=BASE-2340+i*60,open=p,high=p+.1,low=p-.1,close=p));e.position=None
  e.entry_quotes_ready=True;e.entry_reset_at=BASE-1
  return e
 def state(self,e):
  return copy.deepcopy({**e.under_ai.__dict__,'atrs':[a.__dict__ for a in e.under_ai.atrs]})
 def test_partial_price_and_small_candle_do_not_advance_indicator(self):
  e=self.warm();before=self.state(e)
  e.update_hybrid(tick(BASE+1,100.2,1))
  self.assertEqual(self.state(e),before)
  e.update_hybrid(candle(BASE,100.1,100.2))
  self.assertEqual(self.state(e),before)
 def test_completed_price_bricks_update_indicator_once_and_confirm_does_not_repeat(self):
  e=self.warm();expected=copy.deepcopy(e.under_ai);grid=copy.deepcopy(e.under_renko)
  for b in grid.update(103.2):expected.update(b)
  e.update_hybrid(tick(BASE+1,103.2,1))
  self.assertEqual(e.under_ai.st,expected.st);self.assertEqual(e.under_ai.rc,103)
  before=self.state(e);e.update_hybrid(candle(BASE,100,103.2));self.assertEqual(self.state(e),before)
 def test_provider_completed_close_can_supply_missing_completed_bricks(self):
  e=self.warm();e.update_hybrid(candle(BASE,100,103.2))
  self.assertEqual(e.under_ai.rc,103)
  self.assertEqual(e.under_result['decision_basis'],'COMPLETED_RENKO_BRICK')
 def test_option_and_direct_share_identical_brick_indicator(self):
  direct=self.warm();option=self.warm(Strategy)
  option.reset_contract(dict(symbol='CALL',option_type='CE'),.5)
  for n,p in enumerate((100.1,102.2,104.1,101.1,98.8),1):
   direct.update_hybrid(tick(BASE+n,p,n));option.update_hybrid(tick(BASE+n,p,n))
   self.assertEqual(direct.under_result,option.under_result)
 def test_no_time_candle_signal_before_first_completed_brick(self):
  e=DirectStrategy(config(supertrend_basis='COMPLETED_RENKO'))
  e.update(dict(kind='underlying',timestamp=BASE-60,open=100,high=100.1,low=99.9,close=100))
  self.assertIsNone(e.under_result)
  self.assertEqual(e.update_hybrid(candle(BASE,100,100.2)),[])
  self.assertIsNone(e.under_result)
 def test_renko_band_exit_ignores_small_candle_but_accepts_completed_brick(self):
  from unittest.mock import Mock
  e=self.warm();e.config['exit_confirmation_mode']='RENKO_BRICKS_ONLY'
  e.manual_entry('LONG',BASE-1)
  e.band.exit_reason=Mock(return_value='OPTIONAL_UNDERLYING_EMA_BAND')
  self.assertEqual(e.update_hybrid(candle(BASE,100,100.2)),[])
  actions=e.update_hybrid(tick(BASE+61,97.8,1))
  self.assertEqual(actions[0]['action'],'CLOSE_LONG')
  self.assertEqual(actions[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
 def test_sma_only_renko_exit_uses_brick_and_never_evaluates_supertrend(self):
  from unittest.mock import patch,Mock
  e=DirectStrategy(config(supertrend_basis='COMPLETED_RENKO',exit_confirmation_mode='RENKO_BRICKS_ONLY',supertrend_enabled=False,sma_band_entry=True,sma_band_exit=True,sma_band_period=2,sma_retest_required=False))
  with patch.object(AIRenko,'update',side_effect=AssertionError('Supertrend disabled')):
   for i,p in enumerate([100,99,98,97,96,95,94,95,96,97,98,99,100]*3):
    e.update(dict(kind='underlying',timestamp=BASE-2340+i*60,open=p,high=p+.1,low=p-.1,close=p));e.position=None
   e.manual_entry('LONG',BASE-1);e.band.exit_reason=Mock(return_value='OPTIONAL_UNDERLYING_SMA_BAND')
   self.assertEqual(e.update_hybrid(candle(BASE,100,100.2)),[])
   actions=e.update_hybrid(tick(BASE+61,97.8,1))
   self.assertEqual(actions[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
  self.assertTrue(e.completed_signal_queue)
  self.assertTrue(all(p['st'] is None for p in e.completed_signal_queue))

 def test_renko_flat_entry_never_confirms_a_small_time_candle(self):
  from unittest.mock import Mock
  for cls in (DirectStrategy,Strategy):
   e=self.warm(cls);e.config['exit_confirmation_mode']='RENKO_BRICKS_ONLY'
   e.entry_confirmation.confirm=Mock(return_value=None)
   e.update_hybrid(candle(BASE,100,100.2))
   e.entry_confirmation.confirm.assert_not_called()
   e.update_hybrid(tick(BASE+61,103.2,1))
   self.assertTrue(e.entry_confirmation.confirm.called)
   self.assertTrue(all(call.args[0]['kind']=='brick' for call in e.entry_confirmation.confirm.call_args_list))
 def test_sma_only_flat_renko_entry_rejects_small_candle_and_accepts_full_brick(self):
  from unittest.mock import patch,Mock
  from types import SimpleNamespace
  e=DirectStrategy(config(supertrend_basis='COMPLETED_RENKO',exit_confirmation_mode='RENKO_BRICKS_ONLY',supertrend_enabled=False,sma_band_entry=True,sma_band_exit=True,sma_band_period=2,sma_retest_required=False))
  with patch.object(AIRenko,'update',side_effect=AssertionError('Supertrend disabled')):
   for i in range(40):e.update(dict(kind='underlying',timestamp=BASE-2400+i*60,open=100,high=100.1,low=99.9,close=100));e.position=None
   e.entry_reset_at=BASE-1;e.entry_quotes_ready=True
   e.band.observe=Mock();e.band.entry_ready=Mock(return_value=True)
   e.band.states['SMA']=SimpleNamespace(value=dict(upper=99,lower=98,close=100))
   self.assertEqual(e.update_hybrid(candle(BASE,100,100.2)),[])
   self.assertIsNone(e.position)
   actions=e.update_hybrid(tick(BASE+61,102.2,1))
   self.assertEqual(actions[0]['action'],'OPEN_LONG')
   self.assertEqual(actions[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
if __name__=='__main__':unittest.main()
