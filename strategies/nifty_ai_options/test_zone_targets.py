import unittest, tempfile, json, random
from pathlib import Path
from types import SimpleNamespace
from .zone_targets import ZoneBook,ZonePolicy,ReferenceGrid,TargetLadder,validate
from .trend_filter import current_trend_confirmation

class Engine(SimpleNamespace):
 def exit(self,at,reason):
  p=self.position;self.position=None;self.entry_reset_at=at
  return [dict(action='CLOSE_'+p['side'],timestamp=at,reason=reason,position=p)]

def engine(**updates):
 c=dict(account='owner',runtime_session='run',underlying='TEST',reference_value=12,market='NSE',timeframe=5,zone_targets_enabled=True,grid_trailing_enabled=False,display_mode='RENKO',supertrend_basis='COMPLETED_RENKO',execution_route='DIRECT',supertrend_enabled=True)
 c.update(updates)
 e=Engine(config=c,position=None,under_result=dict(direction=1,bar_close=110,st=120),spot_size=1,entry_observation_at=1010,entry_reset_at=0,zone_execution_clear=True)
 e.zone_policy=ZonePolicy(e);e.zone_policy.book.last_available=1000
 return e

def zone(side='DEMAND',low=98,high=100,id='z',**kw):
 z=dict(id=id,side=side,low=low,high=high,origin_at=500,born_at=600,available_at=700,invalidated_at=None,strong=True);z.update(kw);return z
def tick(price,at=1010,**kw):
 d=dict(kind='price',series='underlying',source_basis='BROKER_LIVE_PRICE',close=price,timestamp=at,available_at=at);d.update(kw);return d
def opened(e,direction='SHORT'):
 e.position=dict(side=direction,entry_timestamp=1000,entry_confirmed_at=1001,fill_price=110,order_id='entry',symbol='TEST')
 a=dict(action='OPEN_'+direction,timestamp=1000,position=e.position)
 e.zone_policy.capture(e,a)
 return a

class ZoneTests(unittest.TestCase):
 def test_disabled_defaults_and_incompatible_configuration(self):
  validate(dict())
  for change in [dict(timeframe=30),dict(signal_source='PREMIUM'),dict(swing_targets_enabled=True),dict(supertrend_basis='BROKER_CANDLES'),dict(grid_trailing_enabled=True,execution_route='OPTIONS')]:
   with self.assertRaises(ValueError):engine(**change)
 def test_nearest_eligible_strong_opposing_zone_and_provenance(self):
  e=engine();b=e.zone_policy.book
  b.records=[zone(low=90,high=92,id='far'),zone(),zone(low=103,high=104,id='weak',strong=False),zone(low=105,high=106,id='future',available_at=1100),zone(low=107,high=108,id='broken',invalidated_at=950),zone('SUPPLY',120,122,id='wrong')]
  opened(e)
  self.assertEqual(e.position['zone_target']['id'],'z')
  b.records[1]['high']=99
  self.assertEqual(e.position['zone_target']['high'],100)
 def test_touch_exits_without_brick_then_break_needs_later_complete_red_brick_and_confirmed_flat(self):
  e=engine();e.zone_policy.book.records=[zone(),zone(low=90,high=92,id='next')];opened(e)
  p=e.zone_policy
  self.assertEqual(p.after(e,tick(101),[]),[])
  a=p.after(e,tick(100),[])
  self.assertEqual(a[0]['reason'],'STRONG_OPPOSING_ZONE_TOUCH');self.assertIsNone(e.position)
  unit=dict(kind='brick',closed=True,open=98,close=97,available_at=1011,closed_at=1011)
  e.entry_observation_at=1011;e.under_result=dict(direction=1,bar_close=97,st=105)
  e.zone_execution_clear=False
  self.assertIsNone(current_trend_confirmation(e,unit,e.under_result))
  e.zone_execution_clear=True
  for update in [dict(provisional=True),dict(closed=False),dict(kind='candle'),dict(available_at=1010,closed_at=1010),dict(open=96,close=97)]:
   self.assertIsNone(current_trend_confirmation(e,dict(unit,**update),e.under_result))
  self.assertIsNotNone(current_trend_confirmation(e,unit,e.under_result))
  self.assertFalse(p.admission(e,'SHORT',dict(direction=1,bar_close=98)))
  self.assertTrue(p.admission(e,'SHORT',dict(direction=1,bar_close=97)))
  e.position=dict(side='SHORT',entry_timestamp=1011);e.under_result['bar_close']=97
  p.capture(e,dict(timestamp=1011,action='OPEN_SHORT',position=e.position))
  self.assertEqual(e.position['zone_target']['id'],'next')
 def test_long_mirror_and_opposite_trend_cancels_episode(self):
  e=engine();e.under_result=dict(direction=-1,bar_close=110,st=100);e.zone_policy.book.records=[zone('SUPPLY',120,122)]
  opened(e,'LONG');p=e.zone_policy
  self.assertEqual(p.after(e,tick(120),[])[0]['reason'],'STRONG_OPPOSING_ZONE_TOUCH')
  self.assertFalse(p.admission(e,'LONG',dict(direction=-1,bar_close=122)))
  self.assertFalse(p.admission(e,'LONG',dict(direction=-1,bar_close=123)))
  e.entry_observation_at=1011;e.under_result=dict(direction=-1,bar_close=123,st=110)
  self.assertIsNotNone(current_trend_confirmation(e,dict(kind='brick',closed=True,open=122,close=123,available_at=1011,closed_at=1011),e.under_result))
  self.assertTrue(p.admission(e,'LONG',e.under_result))
  self.assertTrue(p.admission(e,'SHORT',dict(direction=1,bar_close=121)));self.assertIsNone(p.wait)
 def test_stale_source_price_and_existing_protective_exit_priority(self):
  e=engine();e.zone_policy.book.records=[zone()];opened(e);p=e.zone_policy
  self.assertEqual(p.after(e,tick(99,at=2000),[]),[])
  self.assertEqual(p.after(e,tick(99,timestamp=990),[]),[])
  existing=[dict(action='CLOSE_SHORT',reason='AI_RENKO_SUPERTREND_UNDERLYING')]
  self.assertEqual(p.after(e,tick(99),existing),existing)
 def test_unknown_exit_never_submits_again_and_wait_survives_exact_scope_recovery(self):
  with tempfile.TemporaryDirectory() as d:
   e=engine();p=ZonePolicy(e,Path(d)/'state.json');e.zone_policy=p;p.book.last_available=1000;p.book.records=[zone()];opened(e)
   action=p.after(e,tick(99),[])[0]
   e.position=action['position'] # unresolved or partial broker ownership retained
   self.assertEqual(p.after(e,tick(98,1011),[]),[])
   restored=ZonePolicy(e,p.path);self.assertEqual(restored.wait['id'],'z')
   e.config['account']='other';self.assertIsNone(ZonePolicy(e,p.path).wait)
 def test_real_completed_source_aggregation_no_missing_or_forming_substitution(self):
  e=engine(timeframe=1);p=e.zone_policy;p.book.last_available=None
  for i in [0,1,3,4]:
   p.observe(e,dict(kind='underlying',timestamp=900+i*60,open=100,high=102,low=99,close=101),warm=True)
  self.assertIsNone(p.book.last_available)
  with self.assertRaises(ValueError):p.observe(e,dict(kind='underlying',timestamp=900+4*60,open=100,high=999,low=99,close=101),warm=True)
 def test_major_shift_and_causal_born_from_real_detector(self):
  b=ZoneBook({'account':'a','symbol':'TEST'});rng=random.Random(6);price=100
  for i in range(600):
   o=price;price=max(10,price+rng.uniform(-4,4));r=dict(time=300*(i+1),closed_at=300*(i+2),available_at=300*(i+2)+1,open=o,close=price,high=max(o,price)+rng.random(),low=min(o,price)-rng.random())
   b.observe(r)
   self.assertTrue(all(z['born_at']<z['available_at']<=r['available_at'] for z in b.records))
  self.assertTrue(any(z['strong'] for z in b.records))
  self.assertTrue(all(z['body_atr']>=.8 and z['pivot_strength']==5 for z in b.records))
 def test_warm_replay_cannot_invalidate_retained_continuation(self):
  e=engine();e.zone_policy.wait=dict(zone(),direction='SHORT');e.zone_replaying=True
  self.assertTrue(e.zone_policy.admission(e,'LONG',dict(direction=-1,bar_close=101)))
  self.assertIsNotNone(e.zone_policy.wait)

class LadderTests(unittest.TestCase):
 def grid(self):return dict(high=105,low=95,origin_at=500,available_at=600)
 def test_long_t1_entry_t2_t1_t3_t2_and_no_loosening(self):
  x=TargetLadder(self.grid(),100,'LONG')
  self.assertFalse(x.observe(114));self.assertIsNone(x.stop)
  self.assertFalse(x.observe(115));self.assertEqual(x.stop,100)
  x.observe(125);self.assertEqual(x.stop,115)
  x.observe(135);self.assertEqual(x.stop,125)
  self.assertFalse(x.observe(130));self.assertEqual(x.stop,125)
  self.assertTrue(x.observe(125))
 def test_short_mirror_and_jump_arbitrarily_many_targets(self):
  x=TargetLadder(self.grid(),100,'SHORT')
  x.observe(85);self.assertEqual(x.stop,100)
  x.observe(75);self.assertEqual(x.stop,85)
  x.observe(-10005);self.assertGreater(x.achieved,1000);self.assertEqual(x.stop,x.target(x.achieved-1))
  self.assertTrue(x.observe(x.stop))
 def test_fill_and_reentry_reset_excludes_preentry_targets(self):
  x=TargetLadder(self.grid(),126,'LONG')
  self.assertEqual(x.target(1),135);self.assertIsNone(x.stop);x.observe(135);self.assertEqual(x.stop,126)
  self.assertEqual(TargetLadder.restore(x.snapshot()).snapshot(),x.snapshot())
 def test_policy_optional_and_actual_fill_required(self):
  e=engine(zone_targets_enabled=False,grid_trailing_enabled=True);p=e.zone_policy
  e.position=dict(side='LONG',symbol='TEST',entry_timestamp=1000,entry_confirmed_at=1001,order_id='a',target_grid=self.grid())
  self.assertEqual(p.after(e,tick(115),[]),[]);self.assertIsNone(p.trailing)
  e.position['fill_price']=100;p.position_key=None
  self.assertEqual(p.after(e,tick(115),[]),[]);self.assertEqual(p.trailing.stop,100)
  self.assertEqual(p.after(e,tick(100,1011),[]),[])
  e.grid_exit_unit=dict(kind='brick',closed=True,open=101,close=100,closed_at=1012,available_at=1012)
  a=p.after(e,tick(100,1012),[]);self.assertEqual(a[0]['reason'],'TARGET_GRID_TRAILING_STOP')
  self.assertEqual(p.after(e,tick(99,1013),[]),[])
 def test_reference_grid_uses_first_red_after_open_and_exact_span(self):
  g=ReferenceGrid(dict(market='NSE'))
  g.observe(dict(time=33300,closed_at=33600,available_at=33600,open=100,close=99,high=102,low=98));self.assertIsNone(g.lock)
  g.observe(dict(time=33600,closed_at=33900,available_at=33900,open=100,close=99,high=101,low=98));self.assertEqual(g.lock['high']-g.lock['low'],3)
  x=TargetLadder(g.lock,100,'LONG');self.assertEqual(x.target(1),104);self.assertEqual(x.target(10001),30104)

if __name__=='__main__':unittest.main()

class RuntimeIntegrationTests(unittest.TestCase):
 def test_real_direct_wrapper_touch_pending_flat_and_no_flip_continuation(self):
  from .automatic_sizing import AutoSizedStrategy
  from .test_current_trend_midline import CurrentTrendTests
  helper=CurrentTrendTests();inner=helper.engine(enabled=False)
  inner.config.update(zone_targets_enabled=True,execution_route='DIRECT',display_mode='RENKO',runtime_session='r',account='a')
  exposure=[False]
  wrapper=AutoSizedStrategy(inner,SimpleNamespace(),exposure=lambda:exposure[0])
  object.__setattr__(wrapper,'_refresh',lambda:True)
  p=inner.zone_policy;p.book.last_available=1000;p.book.records=[zone(),zone(low=90,high=92,id='next')]
  inner.under_result=dict(direction=1,bar_close=110,st=120)
  inner.position=dict(inner.contract,side='SHORT',entry_timestamp=1000,entry_confirmed_at=1001,fill_price=110)
  p.capture(inner,dict(action='OPEN_SHORT',timestamp=1000,position=inner.position))
  # No full brick: zone price touch still exits.
  from unittest.mock import patch
  event=dict(kind='price',series='underlying',source_basis='BROKER_LIVE_PRICE',symbol=inner.config['underlying'],timestamp=1010,available_at=1010,close=100)
  with patch('strategies.nifty_ai_options.hybrid_basis.price',return_value=([],None)):
   actions=wrapper.update_hybrid(event)
  self.assertEqual(actions[0]['reason'],'STRONG_OPPOSING_ZONE_TOUCH')
  exposure[0]=True
  result=dict(direction=1,bar_close=97,st=105,flip=False)
  bar=dict(open=98,close=97,high=98,low=97,_signal_result=result)
  with patch('strategies.nifty_ai_options.hybrid_basis.price',return_value=([bar],result)):
   self.assertEqual(wrapper.update_hybrid(dict(event,timestamp=1011,available_at=1011,close=97)),[])
  exposure[0]=False
  with patch('strategies.nifty_ai_options.hybrid_basis.price',return_value=([bar],result)):
   actions=wrapper.update_hybrid(dict(event,timestamp=1012,available_at=1012,close=97))
  self.assertEqual(actions[0]['action'],'OPEN_SHORT')
  self.assertEqual(actions[0]['position']['zone_target']['id'],'next')
 def test_same_tick_replay_and_actual_fill_guard_do_not_duplicate_orders(self):
  e=engine(grid_trailing_enabled=True);p=e.zone_policy;p.book.records=[zone()]
  opened(e);e.position['target_grid']=dict(high=115,low=105,available_at=800)
  e.position['fill_price']=99 # No profit at a near-edge zone touch above actual short fill.
  self.assertEqual(p.after(e,tick(100),[]),[])
class ReconciliationTests(unittest.TestCase):
 def test_pending_partial_and_old_position_do_not_acknowledge_a_continuation_fill(self):
  from .zone_targets import reconciled
  e=engine();p=e.zone_policy;p.wait=dict(zone(),direction='SHORT',exit_requested_at=1000);p.episode=dict(direction='SHORT',started_at=500)
  old=dict(side='SHORT',entry_timestamp=500,zone_episode=p.episode,order_id='old',fill_price=110)
  x=SimpleNamespace(state=dict(position=old,pending=None));reconciled(e,x);self.assertIsNotNone(p.wait)
  x.state.update(position=dict(old,entry_timestamp=1010,order_id='new'),pending=dict(uncertain=True));reconciled(e,x);self.assertIsNotNone(p.wait)
  x.state['pending']=None;reconciled(e,x);self.assertIsNone(p.wait)
class DuplicateFillTests(unittest.TestCase):
 def test_duplicate_old_fill_cannot_clear_wait_and_confirmation_replay_cannot_reset_trailing(self):
  from .zone_targets import filled
  e=engine(grid_trailing_enabled=True);p=e.zone_policy;p.wait=dict(zone(),direction='SHORT',exit_requested_at=1010);p.episode=dict(direction='SHORT',started_at=1000)
  e.position=dict(side='SHORT',entry_timestamp=1000,zone_episode=p.episode);filled(e);self.assertIsNotNone(p.wait)
  p.wait=None;e.config['zone_targets_enabled']=False
  e.position=dict(side='LONG',entry_timestamp=1000,entry_confirmed_at=1001,order_id='a',fill_price=100,target_grid=dict(high=105,low=95))
  p.after(e,tick(135),[]);self.assertEqual(p.trailing.stop,125)
  e.position['entry_confirmed_at']=1005 # repeated confirmation for same order
  p.after(e,tick(130,1011),[]);self.assertEqual(p.trailing.stop,125)
class FrozenExitTests(unittest.TestCase):
 def test_owned_zone_exit_survives_expired_native_sizing(self):
  from .automatic_sizing import AutoSizedStrategy
  from .test_current_trend_midline import CurrentTrendTests
  from unittest.mock import patch
  inner=CurrentTrendTests().engine(enabled=False);inner.config.update(zone_targets_enabled=True,execution_route='DIRECT',display_mode='RENKO',runtime_session='r',account='a')
  wrapper=AutoSizedStrategy(inner,None,exposure=lambda:True);object.__setattr__(wrapper,'_refresh',lambda:False)
  inner.under_result=dict(direction=1,bar_close=110,st=120)
  inner.position=dict(inner.contract,side='SHORT',entry_timestamp=1000,entry_confirmed_at=1001,fill_price=110)
  p=inner.zone_policy;p.book.last_available=1000;p.book.records=[zone()];p.capture(inner,dict(action='OPEN_SHORT',timestamp=1000))
  event=dict(kind='price',series='underlying',symbol=inner.config['underlying'],source_basis='BROKER_LIVE_PRICE',timestamp=1010,available_at=1010,close=100)
  with patch('strategies.nifty_ai_options.hybrid_basis.price',return_value=([],None)):actions=wrapper.update_hybrid(event)
  self.assertEqual(actions[0]['reason'],'STRONG_OPPOSING_ZONE_TOUCH')
class GridFreshnessTests(unittest.TestCase):
 def test_prior_session_anchor_is_not_reused_for_new_entry(self):
  e=engine(zone_targets_enabled=False,grid_trailing_enabled=True);p=e.zone_policy
  p.grid.observe(dict(time=33300,closed_at=33600,available_at=33600,open=100,close=99,high=102,low=98))
  p.grid.observe(dict(time=33600,closed_at=33900,available_at=33900,open=100,close=99,high=101,low=98))
  p.book.last_available=33900;e.entry_observation_at=33960
  self.assertTrue(p.admission(e,'LONG',dict(direction=-1,bar_close=100)))
  e.entry_observation_at=33960+86400;p.book.last_available=e.entry_observation_at
  self.assertFalse(p.admission(e,'LONG',dict(direction=-1,bar_close=100)))
 def test_countertrend_candle_cannot_bypass_wait_for_original_completed_break(self):
  e=engine();p=e.zone_policy;p.wait=dict(zone(),direction='SHORT',exit_requested_at=1000)
  self.assertFalse(p.admission(e,'LONG',dict(direction=1,bar_close=105)))
