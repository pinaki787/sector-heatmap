import unittest,tempfile,json
from types import SimpleNamespace
from pathlib import Path
from copy import deepcopy
from .support_retest import install,Policy
from .swing_targets import SwingBook
from .zone_targets import ZonePolicy,TargetLadder,record_exit_unit
class TrailingPullbackTests(unittest.TestCase):
 def engine(self,d='SHORT'):
  from .test_current_trend_midline import CurrentTrendTests
  e=CurrentTrendTests().engine(enabled=False)
  e.config.update(grid_trailing_enabled=True,trailing_reentry_enabled=True,display_mode='RENKO',execution_route='DIRECT',swing_targets_enabled=False,swing_retest_required=False,exit_confirmation_mode='RENKO_BRICKS_ONLY')
  e.support_execution_clear=True;e.swing_book=SwingBook();e.swing_book.rows=[dict(price=90 if d=='SHORT' else 110,time=11)]
  install(e);return e
 def arm(self,e,d='SHORT'):
  prior=dict(e.contract,side=d,entry_timestamp=10,fill_price=100,order_id='owned')
  action=dict(action='CLOSE_'+d,timestamp=12,reason='TARGET_GRID_TRAILING_STOP',position=prior)
  e.position=None;e.support_retest.after(e,dict(kind='price',timestamp=12,available_at=12,close=95),[action],prior)
  return e.support_retest
 def price(self,e,price,at,clear=True):
  e.support_retest.before(e,dict(kind='price',series='underlying',symbol=e.config['underlying'],source_basis='BROKER_LIVE_PRICE',close=price,timestamp=at,available_at=at),clear=clear)
 def unit(self,close,at,up=False,**extra):return dict(kind='brick',closed=True,open=close-1 if up else close+1,close=close,closed_at=at,available_at=at,**extra)
 def result(self,close,d='SHORT',flip=False):return dict(direction=1 if d=='SHORT' else -1,flip=flip,bar_close=close,st=120 if d=='SHORT' else 80)
 def test_trailing_exit_freezes_prior_low_without_touch_reentry(self):
  e=self.engine();p=self.arm(e);self.assertEqual(p.wait['price'],90)
  self.price(e,89,13);self.assertEqual(p.wait['phase'],'WAITING_FOR_COUNTER_BRICK')
  self.price(e,95,14);self.assertEqual(p.wait['phase'],'WAITING_FOR_COUNTER_BRICK')
  self.assertFalse(p.admission(e,'SHORT',self.result(89)))
 def test_post_flat_counter_brick_then_later_break_without_new_flip(self):
  from .test_current_trend_midline import CurrentTrendTests
  e=self.engine();p=self.arm(e);helper=CurrentTrendTests()
  self.price(e,95,13)
  self.assertEqual(helper.tick(e,1,95,100,at=14,opening=94),[])
  self.assertEqual(p.wait['phase'],'WAITING_FOR_COMPLETED_PULLBACK_BREAK')
  self.assertEqual(p.wait['price'],90)
  self.price(e,94,15);self.assertEqual(helper.tick(e,1,94,100,at=15,opening=95),[])
  self.price(e,89,16);actions=helper.tick(e,1,89,100,at=16,opening=90)
  self.assertEqual(actions[0]['action'],'OPEN_SHORT')
 def test_long_mirror_uses_frozen_high(self):
  from .test_current_trend_midline import CurrentTrendTests
  e=self.engine('LONG');p=self.arm(e,'LONG');helper=CurrentTrendTests();self.price(e,105,13)
  self.assertEqual(helper.tick(e,-1,105,100,at=14,opening=106),[])
  self.price(e,111,15);actions=helper.tick(e,-1,111,100,at=15,opening=110)
  self.assertEqual(actions[0]['action'],'OPEN_LONG');self.assertEqual(p.wait['price'],110)
 def test_partial_pending_or_unknown_exposure_cannot_record_pullback(self):
  e=self.engine();p=self.arm(e);self.price(e,95,13,clear=False)
  p.observe_unit(e,self.unit(95,14,up=True),self.result(95))
  self.assertIsNone(p.wait['flat_confirmed_at']);self.assertEqual(p.wait['phase'],'WAITING_FOR_COUNTER_BRICK')
 def test_counter_unit_must_be_completed_and_post_flat_not_replayed(self):
  for extra in [dict(provisional=True),dict(historyOnly=True),dict(closed=False),dict(kind='candle')]:
   e=self.engine();p=self.arm(e);self.price(e,95,13)
   u=self.unit(95,14,up=True);u.update(extra);p.observe_unit(e,u,self.result(95))
   self.assertEqual(p.wait['phase'],'WAITING_FOR_COUNTER_BRICK')
  e=self.engine();p=self.arm(e);self.price(e,95,13);e.zone_replaying=True
  p.observe_unit(e,self.unit(95,14,up=True),self.result(95));self.assertEqual(p.wait['phase'],'WAITING_FOR_COUNTER_BRICK')
 def test_reference_never_chases_current_confirming_red_low(self):
  e=self.engine();p=self.arm(e);self.price(e,95,13)
  p.observe_unit(e,self.unit(95,14,up=True),self.result(95));e.entry_observation_at=15
  self.assertTrue(p.confirmation(e,self.unit(89,15),self.result(89)))
  self.assertEqual(p.wait['price'],90)
 def test_opposite_regime_flip_invalidates_old_episode(self):
  e=self.engine();p=self.arm(e);self.price(e,95,13)
  p.observe_unit(e,self.unit(95,14,up=True),self.result(95,'LONG',True))
  self.assertIsNone(p.wait)
 def test_unrelated_stop_or_supertrend_exit_does_not_arm_continuation(self):
  for reason in ['USER_STOP_SQUARE_OFF','AI_RENKO_SUPERTREND_UNDERLYING','OPTIONAL_UNDERLYING_1M_SMA30']:
   e=self.engine();prior=dict(side='SHORT',entry_timestamp=10)
   e.support_retest.after(e,{},[dict(action='CLOSE_SHORT',reason=reason,position=prior)],prior)
   self.assertIsNone(e.support_retest.wait)
 def test_legacy_trailing_without_new_flag_does_not_change(self):
  e=self.engine();e.config['trailing_reentry_enabled']=False
  prior=dict(side='SHORT',entry_timestamp=10);e.support_retest.after(e,{},[dict(action='CLOSE_SHORT',reason='TARGET_GRID_TRAILING_STOP',position=prior)],prior)
  self.assertIsNone(e.support_retest.wait)
 def test_repeated_exit_receipt_does_not_reset_reference_or_episode(self):
  e=self.engine();p=self.arm(e);first=deepcopy(p.wait);e.swing_book.rows=[dict(price=80,time=15)]
  prior=dict(side='SHORT',entry_timestamp=10,order_id='owned');p.arm_trailing(e,dict(timestamp=16,position=prior),prior)
  self.assertEqual(p.wait,first)
 def test_persistence_restores_frozen_reference_and_pullback_phase(self):
  with tempfile.TemporaryDirectory() as d:
   e=self.engine();e.support_retest=Policy(e,Path(d)/'policy.json');p=self.arm(e);self.price(e,95,13)
   p.observe_unit(e,self.unit(95,14,up=True),self.result(95))
   q=Policy(e,Path(d)/'policy.json');self.assertEqual(q.wait,p.wait);self.assertIsNone(q.proof)
 def test_no_confirmation_from_same_time_as_pullback_or_equal_threshold(self):
  e=self.engine();p=self.arm(e);self.price(e,95,13);p.observe_unit(e,self.unit(95,14,up=True),self.result(95))
  self.assertFalse(p.confirmation(e,self.unit(89,14),self.result(89)))
  self.assertFalse(p.confirmation(e,self.unit(90,15),self.result(90)))
 def test_directional_extreme_is_completed_only_and_position_scoped(self):
  e=self.engine();e.position=dict(symbol=e.config['underlying'],side='SHORT',entry_timestamp=10)
  p=e.support_retest;p.observe_unit(e,self.unit(90,11),self.result(90));p.observe_unit(e,self.unit(95,12,up=True),self.result(95))
  self.assertEqual(p.extreme['price'],90)
  p.observe_unit(e,self.unit(89,13,provisional=True),self.result(89));self.assertEqual(p.extreme['price'],90)
 def test_capture_preserves_completed_preentry_low_before_first_counter_brick(self):
  e=self.engine();e.swing_book.rows=[dict(price=90,time=9)]
  p=e.support_retest;position=dict(e.contract,side='SHORT',entry_timestamp=10,fill_price=100,order_id='entry')
  e.position=position;p.capture(e,dict(action='OPEN_SHORT',timestamp=10,position=position))
  p.observe_unit(e,self.unit(95,11,up=True),self.result(95))
  self.assertEqual(p.extreme['price'],90)
  e.position=None;p.arm_trailing(e,dict(action='CLOSE_SHORT',timestamp=12,position=position),position)
  self.assertEqual(p.wait['price'],90)
class CompletedTrailingExitTests(unittest.TestCase):
 def engine(self,d='SHORT'):
  from .test_zone_targets import engine
  e=engine(zone_targets_enabled=False,grid_trailing_enabled=True,exit_confirmation_mode='RENKO_BRICKS_ONLY')
  e.position=dict(symbol='TEST',side=d,entry_timestamp=10,entry_confirmed_at=11,order_id='entry',fill_price=100,target_grid=dict(high=105,low=95))
  p=e.zone_policy;p.trailing=TargetLadder(e.position['target_grid'],100,d);p.position_key=['entry',10]
  p.trailing.observe(85 if d=='SHORT' else 115)
  return e,p
 def event(self,price,at=20,**kw):return dict(kind='price',series='underlying',source_basis='BROKER_LIVE_PRICE',symbol='TEST',timestamp=at,available_at=at,close=price,**kw)
 def test_tick_touch_and_provisional_green_do_not_exit_short(self):
  e,p=self.engine();self.assertEqual(p.after(e,self.event(100),[]),[])
  record_exit_unit(e,dict(kind='brick',closed=True,provisional=True,open=99,close=100,closed_at=21,available_at=21),dict(bar_close=100))
  self.assertEqual(p.after(e,self.event(100,21),[]),[])
 def test_completed_green_at_or_beyond_stop_exits_short(self):
  e,p=self.engine();u=dict(kind='brick',closed=True,open=99,close=100,closed_at=20,available_at=20)
  record_exit_unit(e,u,dict(bar_close=100));a=p.after(e,self.event(100),[])
  self.assertEqual(a[0]['reason'],'TARGET_GRID_TRAILING_STOP');self.assertEqual(a[0]['confirmation']['confirmation_basis'],'COMPLETED_ADVERSE_RENKO_TRAILING_STOP')
 def test_completed_red_at_stop_exits_long(self):
  e,p=self.engine('LONG');u=dict(kind='brick',closed=True,open=101,close=100,closed_at=20,available_at=20)
  record_exit_unit(e,u,dict(bar_close=100));self.assertEqual(p.after(e,self.event(100),[])[0]['action'],'CLOSE_LONG')
 def test_stale_preentry_wrong_color_or_partial_unit_cannot_exit(self):
  for changes in [dict(available_at=19),dict(closed_at=10),dict(open=101),dict(open=99.5),dict(historyOnly=True)]:
   e,p=self.engine();u=dict(kind='brick',closed=True,open=99,close=100,closed_at=20,available_at=20);u.update(changes)
   record_exit_unit(e,u,dict(bar_close=100));self.assertEqual(p.after(e,self.event(100),[]),[])
 def test_ratchet_is_separate_from_exit_and_never_loosens(self):
  e,p=self.engine();self.assertEqual(p.after(e,self.event(75),[]),[]);self.assertEqual(p.trailing.stop,85)
  self.assertEqual(p.after(e,self.event(86,21),[]),[]);self.assertEqual(p.trailing.stop,85)
 def test_confirmed_provider_candle_brick_can_exit_with_fresh_completed_close(self):
  e,p=self.engine();u=dict(kind='brick',closed=True,open=99,close=100,closed_at=20,available_at=20);record_exit_unit(e,u,dict(bar_close=100))
  event=dict(kind='underlying',closed=True,body_available=True,source_basis='PROVIDER_CONFIRMED_CLOSE',timestamp=0,closed_at=20,available_at=20,close=100)
  self.assertEqual(p.after(e,event,[])[0]['reason'],'TARGET_GRID_TRAILING_STOP')
class RecordedIncidentTests(unittest.TestCase):
 def test_recorded_tick_exit_rejected_and_synthetic_completed_green_accepted(self):
  from .test_zone_targets import engine
  fixture=json.loads((Path(__file__).parent/'fixtures/btc-trailing-completed-brick.json').read_text())
  e=engine(zone_targets_enabled=False,grid_trailing_enabled=True,exit_confirmation_mode='RENKO_BRICKS_ONLY')
  e.spot_size=fixture['brick'];e.position=dict(symbol='TEST',side='SHORT',entry_timestamp=1,entry_confirmed_at=2,order_id='fixture',fill_price=fixture['entry'],target_grid=fixture['ladder']['grid'])
  p=e.zone_policy;p.trailing=TargetLadder.restore(fixture['ladder']);p.position_key=['fixture',1]
  last=fixture['latest_confirmed'];old=dict(kind='brick',closed=True,open=last['open'],close=last['close'],closed_at=last['source_time'],available_at=last['available_at'])
  record_exit_unit(e,old,dict(bar_close=old['close']))
  self.assertEqual(p.after(e,fixture['tick'],[]),[]);self.assertIsNotNone(e.position)
  at=fixture['tick']['available_at']+60;close=last['close']+2*fixture['brick']
  control=dict(kind='brick',closed=True,open=close-fixture['brick'],close=close,closed_at=at,available_at=at)
  record_exit_unit(e,control,dict(bar_close=close))
  a=p.after(e,dict(fixture['tick'],timestamp=at,available_at=at,close=close),[])
  self.assertEqual(a[0]['confirmation']['confirmation_basis'],'COMPLETED_ADVERSE_RENKO_TRAILING_STOP')
if __name__=='__main__':unittest.main()
