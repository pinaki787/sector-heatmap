import unittest,tempfile
from types import SimpleNamespace
from pathlib import Path
from copy import deepcopy
from .support_retest import Policy,install
from .swing_targets import SwingBook
class SupportRetestTests(unittest.TestCase):
 def engine(self,d='SHORT'):
  e=SimpleNamespace(config=dict(swing_targets_enabled=True,swing_retest_required=True,display_mode='RENKO',supertrend_basis='COMPLETED_RENKO',account='owner',underlying='BTCUSD',runtime_session='session',reference_value=46),spot_size=1,contract=dict(tick_size=.5),position=None,entry_reset_at=0,entry_observation_at=0,under_result=dict(bar_close=100,direction=1,st=103),entry_confirmation=SimpleNamespace(clear=lambda:None))
  e.swing_book=SwingBook();e.swing_book.lows=[dict(id='low1',price=95,origin_at=1,confirmed_at=5),dict(id='low2',price=90,origin_at=2,confirmed_at=6)];e.swing_book.highs=[dict(id='high1',price=105,origin_at=1,confirmed_at=5),dict(id='high2',price=110,origin_at=2,confirmed_at=6)]
  e.exit=lambda at,reason:[dict(action='CLOSE_'+e.position['side'],position=deepcopy(e.position),timestamp=at,reason=reason)]
  install(e);return e
 def event(self,p,at):return dict(kind='price',series='underlying',symbol='BTCUSD',source_basis='BROKER_LIVE_PRICE',close=p,timestamp=at,available_at=at)
 def wait(self,e,d='SHORT'):
  e.support_retest.wait=dict(id='low1' if d=='SHORT' else 'high1',price=95 if d=='SHORT' else 105,direction=d,exit_requested_at=10,phase='WAITING_FOR_DEPARTURE')
 def brick(self,e,close,at,d='SHORT',**kw):
  e.entry_observation_at=at
  u=dict(kind='brick',closed=True,open=close+(1 if d=='SHORT' else -1),close=close,available_at=at,closed_at=at);u.update(kw)
  r=dict(direction=1 if d=='SHORT' else -1,st=100,bar_close=close,flip=False)
  return e.support_retest.confirmation(e,u,r),r
 def test_book_retains_more_than_latest_pivot(self):
  b=SwingBook()
  for i,p in enumerate([100,102,105,103,101,99,97,99,101,103,106,104,102,99,95,98,100]):b.observe(dict(close=p,closed=True),i)
  self.assertGreaterEqual(len(b.lows),2);self.assertEqual(b.low['price'],95);self.assertEqual(b.lows[0]['price'],97)
 def test_capture_nearest_and_next_retained_support(self):
  e=self.engine();p=e.support_retest
  a=dict(action='OPEN_SHORT',timestamp=10,position=dict(side='SHORT',entry_timestamp=10))
  p.capture(e,a);self.assertEqual(a['position']['retained_swing_target']['price'],95)
  p.used=['low1'];e.under_result['bar_close']=94
  p.capture(e,a);self.assertEqual(a['position']['retained_swing_target']['price'],90)
 def test_broken_historical_support_archived_but_not_selected(self):
  e=self.engine();e.swing_book.lows.insert(0,dict(id='broken',price=99,confirmed_at=5,broken_at=8))
  a=dict(action='OPEN_SHORT',timestamp=10,position=dict(side='SHORT',entry_timestamp=10))
  e.support_retest.capture(e,a);self.assertEqual(a['position']['retained_swing_target']['price'],95)
 def test_book_break_invalidation_is_causal_and_preserves_history(self):
  b=SwingBook()
  for i,p in enumerate([100,99,97,99,100,96]):b.observe(dict(close=p,closed=True),i+1)
  self.assertEqual(b.lows[0]['price'],97);self.assertEqual(b.lows[0]['broken_at'],6)
 def test_future_unconfirmed_level_not_target(self):
  e=self.engine();e.swing_book.lows.append(dict(id='future',price=99,origin_at=1,confirmed_at=11))
  a=dict(action='OPEN_SHORT',timestamp=10,position=dict(side='SHORT',entry_timestamp=10))
  e.support_retest.capture(e,a);self.assertEqual(a['position']['retained_swing_target']['price'],95)
 def test_short_requires_departure_then_retest_then_later_red_brick(self):
  e=self.engine();p=e.support_retest;self.wait(e)
  p.before(e,self.event(94,11),clear=True);self.assertEqual(p.wait['phase'],'WAITING_FOR_RETEST')
  self.assertFalse(self.brick(e,94,12)[0])
  p.before(e,self.event(95,13),clear=True);self.assertEqual(p.wait['phase'],'WAITING_FOR_FAILED_RETEST_BRICK')
  self.assertFalse(self.brick(e,94,13)[0])
  p.before(e,self.event(94,14),clear=True);ok,r=self.brick(e,94,14);self.assertTrue(ok);self.assertTrue(p.admission(e,'SHORT',r))
 def test_long_mirror(self):
  e=self.engine();p=e.support_retest;self.wait(e,'LONG')
  p.before(e,self.event(106,11),clear=True);p.before(e,self.event(105,12),clear=True);p.before(e,self.event(106,13),clear=True)
  ok,r=self.brick(e,106,13,'LONG');self.assertTrue(ok);self.assertTrue(p.admission(e,'LONG',r))
 def test_pending_exposure_does_not_advance_retest(self):
  e=self.engine();p=e.support_retest;self.wait(e)
  p.before(e,self.event(94,11),clear=False);self.assertEqual(p.wait['phase'],'WAITING_FOR_DEPARTURE');self.assertFalse(self.brick(e,94,12)[0])
 def test_stale_wrong_symbol_and_replayed_prices_ignored(self):
  for changes in [dict(timestamp=1),dict(symbol='PAXGUSD'),dict(source_basis='HISTORY'),dict(kind='underlying')]:
   e=self.engine();p=e.support_retest;self.wait(e);p.before(e,dict(self.event(94,20),**changes),clear=True);self.assertEqual(p.wait['phase'],'WAITING_FOR_DEPARTURE')
  e=self.engine();p=e.support_retest;self.wait(e);p.before(e,self.event(94,11),clear=True,warm=True);self.assertEqual(p.wait['phase'],'WAITING_FOR_DEPARTURE')
 def test_provisional_candle_wrong_color_and_exact_level_do_not_confirm(self):
  for changes in [dict(provisional=True),dict(closed=False),dict(historyOnly=True),dict(kind='candle'),dict(open=93),dict(closed_at=20)]:
   e=self.engine();self.wait(e);e.support_retest.wait.update(phase='WAITING_FOR_FAILED_RETEST_BRICK',retested_at=12);e.support_execution_clear=True
   self.assertFalse(self.brick(e,94,13,**changes)[0])
 def test_candle_and_sma_admission_without_brick_proof_blocked(self):
  e=self.engine();self.wait(e);e.support_execution_clear=True
  self.assertFalse(e.support_retest.admission(e,'SHORT',dict(direction=1,bar_close=94,flip=False)))
 def test_opposite_new_flip_invalidates_episode(self):
  e=self.engine();self.wait(e)
  self.assertTrue(e.support_retest.admission(e,'LONG',dict(direction=-1,bar_close=96,flip=True)));self.assertIsNone(e.support_retest.wait)
 def test_touch_exit_is_profit_only_and_idempotent(self):
  e=self.engine();p=e.support_retest
  e.position=dict(side='SHORT',entry_timestamp=10,fill_price=100,retained_swing_target=dict(id='low1',price=95,direction='SHORT',entry_underlying_close=100))
  prior=deepcopy(e.position)
  a=p.after(e,self.event(95,11),[],prior);self.assertEqual(a[0]['reason'],'RETAINED_SWING_PROFIT_TOUCH');self.assertEqual(p.wait['price'],95)
  self.assertEqual(p.after(e,self.event(94,12),[],prior),[])
 def test_old_existing_position_not_retroactively_targeted(self):
  e=self.engine();e.position=dict(side='SHORT',entry_timestamp=10,fill_price=100)
  self.assertEqual(e.support_retest.after(e,self.event(90,11),[],deepcopy(e.position)),[])
 def test_rejected_entry_keeps_wait_until_actual_new_fill(self):
  e=self.engine();self.wait(e);p=e.support_retest
  p.filled(e,dict(side='SHORT',entry_timestamp=9));self.assertIsNotNone(p.wait)
  p.filled(e,dict(side='SHORT',entry_timestamp=14,fill_price=94));self.assertIsNone(p.wait)
 def test_protective_exit_takes_priority(self):
  e=self.engine();self.wait(e);a=[dict(action='CLOSE_SHORT',reason='PROTECTIVE')]
  self.assertEqual(e.support_retest.after(e,self.event(94,15),a,None),a);self.assertIsNone(e.support_retest.wait)
 def test_durable_exact_scope_restores_wait_but_not_old_quote_proof(self):
  with tempfile.TemporaryDirectory() as d:
   e=self.engine();p=Policy(e,Path(d)/'policy.json');e.support_retest=p;self.wait(e);p.save()
   q=Policy(e,Path(d)/'policy.json');self.assertEqual(q.wait,p.wait);self.assertIsNone(q.proof)
   e.config['underlying']='OTHER';self.assertIsNone(Policy(e,Path(d)/'policy.json').wait)
 def test_real_direct_engine_reenters_after_retest_without_flip(self):
  from .test_current_trend_midline import CurrentTrendTests
  helper=CurrentTrendTests();e=helper.engine(enabled=False)
  e.config.update(swing_targets_enabled=True,swing_retest_required=True,display_mode='RENKO')
  install(e);self.wait(e);e.support_retest.wait.update(phase='WAITING_FOR_FAILED_RETEST_BRICK',retested_at=12)
  e.support_execution_clear=True;e.under_result=dict(direction=1,flip=False,bar_close=96,st=102)
  actions=helper.tick(e,1,94,100,at=13,opening=95)
  self.assertEqual(actions[0]['action'],'OPEN_SHORT')
 def test_actual_fill_skips_target_already_passed_before_entry(self):
  e=self.engine();e.config['execution_route']='DIRECT'
  a=dict(action='OPEN_SHORT',timestamp=10,position=dict(side='SHORT',entry_timestamp=10,fill_price=94))
  e.support_retest.capture(e,a);self.assertEqual(a['position']['retained_swing_target']['price'],90)
 def test_activation_beyond_target_waits_return_then_fresh_touch(self):
  e=self.engine();p=e.support_retest
  e.position=dict(side='SHORT',order_id='123',entry_timestamp=10,fill_price=100,retained_swing_target=dict(id='low1',price=95,direction='SHORT',entry_underlying_close=100,fresh_touch_after=20,fresh_touch_armed=False))
  prior=deepcopy(e.position)
  self.assertEqual(p.after(e,self.event(94,21),[],prior),[])
  self.assertEqual(p.after(e,self.event(96,22),[],prior),[])
  a=p.after(e,self.event(95,23),[],prior);self.assertEqual(a[0]['reason'],'RETAINED_SWING_PROFIT_TOUCH')
 def test_activation_outside_target_still_needs_post_activation_quote(self):
  e=self.engine();p=e.support_retest
  e.position=dict(side='SHORT',order_id='123',entry_timestamp=10,fill_price=100,retained_swing_target=dict(id='low1',price=95,direction='SHORT',entry_underlying_close=100,fresh_touch_after=20,fresh_touch_armed=True))
  prior=deepcopy(e.position)
  self.assertEqual(p.after(e,self.event(94,20),[],prior),[])
  self.assertEqual(p.after(e,self.event(95,21),[],prior)[0]['reason'],'RETAINED_SWING_PROFIT_TOUCH')
 def test_pending_fill_reconciliation_does_not_clear_until_owned_fill(self):
  from .support_retest import reconciled
  e=self.engine();self.wait(e)
  owned=dict(order_id='123',side='SHORT',quantity=20,fill_price=94,entry_timestamp=14)
  executor=SimpleNamespace(state=dict(pending=dict(id='pending'),position=owned))
  reconciled(e,executor);self.assertIsNotNone(e.support_retest.wait)
  executor.state['pending']=None;reconciled(e,executor);self.assertIsNone(e.support_retest.wait)
 def test_disabled_legacy_stays_unchanged(self):
  e=self.engine();e.config['swing_retest_required']=False;del e.support_retest;install(e);self.assertFalse(hasattr(e,'support_retest'))
if __name__=='__main__':unittest.main()
