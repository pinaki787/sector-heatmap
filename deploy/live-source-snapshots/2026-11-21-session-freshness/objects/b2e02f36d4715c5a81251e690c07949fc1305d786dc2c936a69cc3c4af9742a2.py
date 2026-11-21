import unittest
from copy import deepcopy
from .trend_reentry import apply
from .price_basis import observe
from .test_price_basis import PriceBasisTests

class TrendReentryTests(unittest.TestCase):
 def setUp(self):
  self.state=dict(config=dict(strategy_basis='RENKO'),run_id='r',rearm_after_exit=True,
                  last_exit_bar=100,trend_reentry_after=101,trend_reentry_run_id='r',position=None,pending=None)
  self.sig=dict(timestamp=102,market_event_at=102,has_completed_brick=True,direction='BULLISH',
                brick_direction='BULLISH',trend_reentry_direction='BULLISH',entry_qualified=False)
 def test_new_favorable_brick(self):
  result=apply(self.state,self.sig)
  self.assertEqual(result['cross_direction'],'BULLISH');self.assertTrue(result['trend_reentry'])
  self.assertFalse(self.sig['entry_qualified'])
 def test_previous_run_exit_does_not_enable_initial_entry(self):
  state={**self.state,'run_id':'new'};self.assertEqual(apply(state,self.sig),self.sig)
 def test_off_blocks_fresh_favorable_brick(self):
  state={**self.state,'config':{'strategy_basis':'RENKO','trend_reentry_enabled':False}}
  self.assertEqual(apply(state,self.sig),self.sig)
 def test_new_start_without_exit_allows_only_later_brick(self):
  state={**self.state,'rearm_after_exit':False,'trend_reentry_after':0,'trend_reentry_run_id':None,'started_at':101,'eligible_since':101}
  self.assertTrue(apply(state,self.sig)['trend_reentry'])
  self.assertEqual(apply(state,{**self.sig,'market_event_at':101}),{**self.sig,'market_event_at':101})
 def test_bearish_symmetry(self):
  self.sig.update(direction='BEARISH',brick_direction='BEARISH',trend_reentry_direction='BEARISH')
  self.assertEqual(apply(self.state,self.sig)['cross_direction'],'BEARISH')
 def test_held_and_pending_do_not_promote(self):
  for key,value in [('position',{'quantity':1}),('pending',{'tag':'x'})]:
   state={**self.state,key:value};self.assertEqual(apply(state,self.sig),self.sig)
 def test_same_observation_old_queued_and_forming_do_not_promote(self):
  for change in [dict(timestamp=100),dict(market_event_at=101),dict(market_event_at=100),
                 dict(provisional=True),dict(has_completed_brick=False),
                 dict(brick_direction='BEARISH'),dict(trend_reentry_direction=None)]:
   sig={**self.sig,**change};self.assertEqual(apply(self.state,sig),sig)
 def test_unknown_exit_chronology_fails_closed(self):
  state={**self.state,'trend_reentry_after':0};self.assertEqual(apply(state,self.sig),self.sig)
 def test_saved_current_run_fill_establishes_boundary(self):
  state={**self.state,'trend_reentry_after':0,'order_history':[dict(run_id='r',side='SELL',status='FILLED',filled_at=101,is_entry=False)]}
  self.assertTrue(apply(state,self.sig)['trend_reentry'])
  state['order_history'][0]['run_id']='other';self.assertEqual(apply(state,self.sig),self.sig)
 def test_selected_indicator_failure_still_blocks(self):
  sig={**self.sig,'trend_reentry_direction':None,'entry_diagnostic':'WAITING_ADX'}
  self.assertEqual(apply(self.state,sig),sig)

class ReentryCandidateTests(PriceBasisTests):
 def setUp(self):
  super().setUp()
  self.config['supertrend_slope_enabled']=False
 def test_continuation_publishes_candidate_without_changing_initial_entry(self):
  self.price(310)
  rows=self.price(345)
  continued=[r for r in rows if not r.get('raw_supertrend_cross_direction')]
  self.assertTrue(continued)
  self.assertTrue(any(r.get('trend_reentry_direction')=='BULLISH' for r in continued))
  self.assertTrue(all(not r['entry_qualified'] for r in continued))
 def test_opposite_brick_has_no_continuation_candidate(self):
  self.price(310);self.price(345)
  rows=self.price(320)
  for row in rows:
   if row['brick_direction']!=row['direction']:self.assertIsNone(row.get('trend_reentry_direction'))

class TogglePersistenceTests(unittest.TestCase):
 def setUp(self):
  import tempfile
  from pathlib import Path
  from .runner import Runner
  from .test_runner import FakeBroker
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.b=FakeBroker();self.r=Runner(self.b,Path(self.tmp.name)/'state.json',lambda:self.b.now)
  self.addCleanup(self.r.release)
  self.r.state.update(config={'mode':'PAPER','strategy_basis':'RENKO'},running=True,run_id='same',trades_used=3)
  self.r.snapshot=lambda:deepcopy(self.r.state)
 def test_default_on_and_persist_off_on_without_orders(self):
  from .signals import settings
  from . import preferences
  self.assertTrue(settings({})['trend_reentry_enabled'])
  self.r.set_trend_reentry({'enabled':False})
  self.assertFalse(self.r.state['config']['trend_reentry_enabled'])
  self.assertFalse(preferences.read(self.r.path.with_name('renko-supertrend-settings.json'))['settings']['trend-reentry-enabled'])
  self.r.set_trend_reentry({'enabled':True})
  self.assertTrue(self.r.state['config']['trend_reentry_enabled'])
  self.assertEqual(self.r.state['eligible_since'],self.b.now)
  self.assertEqual(self.r.state['run_id'],'same');self.assertEqual(self.r.state['trades_used'],3);self.assertEqual(self.b.sent,[])
 def test_invalid_toggle_rejected(self):
  for value in ['false',0,None]:
   with self.assertRaises(ValueError):self.r.set_trend_reentry({'enabled':value})
 def test_off_invalidates_cached_reentry_and_preserves_exposure(self):
  self.r.state['position']={'symbol':'TEST','quantity':1}
  self.r._price_current={'trend_reentry':True,'entry_qualified':True,'cross_direction':'BULLISH'}
  self.r.set_trend_reentry({'enabled':False})
  self.assertIsNone(self.r._price_current['cross_direction'])
  self.assertEqual(self.r.state['position'],{'symbol':'TEST','quantity':1})

class ContinuationSubmissionTests(unittest.TestCase):
 from .test_runner import RenkoLifecycleTests as Fixture
 setUp=Fixture.setUp
 start=Fixture.start
 def scenario(self,enabled=True,changed=False):
  self.c.update(ema_momentum_enabled=False,ema_exit_enabled=False,higher_timeframe_enabled=False)
  self.start();self.r.signal();self.b.now+=2
  self.r.state['config'].update(strategy_basis='RENKO',trend_reentry_enabled=enabled)
  self.b.forming=lambda *args:None
  last=self.r.state['renko_engine']['last'];last={**last,'open':last['close']-10,'high':last['close'],'low':last['close']-10}
  raw={**last,'timestamp':self.b.now-1,'market_event_at':self.b.now-1,
       'has_completed_brick':True,'confirmation_basis':'ORDERED_LIVE_PRICE','entry_qualified':False,
       'entry_diagnostic':'WAITING_SUPERTREND_REVERSAL','direction':'BULLISH','brick_direction':'BULLISH',
       'trend_reentry_direction':'BULLISH','entry_direction':None,'cross_direction':None}
  from .trend_reentry import apply
  sig=apply(self.r.state,raw)
  self.r.state['renko_engine']['last']={**raw,**({'direction':'BEARISH','trend_reentry_direction':None} if changed else {})}
  self.r.state['last_processed_bar']=raw['timestamp']-1
  self.r.state['last_signal']=sig
  self.r.signal=lambda:sig
  return sig
 def test_full_paper_submission_accepts_continuation_without_reversal(self):
  self.scenario();self.r._candle_step()
  self.assertIsNotNone(self.r.state.get('position'))
  self.assertEqual(len(self.r.state['order_history']),1)
  self.assertEqual(self.b.sent,[])
 def test_off_blocks_full_paper_submission(self):
  self.scenario(enabled=False);self.r._candle_step()
  self.assertFalse(self.r.state.get('position'));self.assertFalse(self.r.state.get('order_history'))
 def test_changed_trend_still_blocks_submission(self):
  self.scenario(changed=True)
  with self.assertRaisesRegex(ValueError,'setup changed'):self.r._candle_step()
  self.assertFalse(self.r.state.get('position'))

 def test_same_trend_submission_after_current_run_exit_fill(self):
  self.scenario()
  self.r.state["run_id"]="reentry-test-run"
  boundary=self.b.now-1.5
  self.r.state.update(rearm_after_exit=True,last_exit_bar=self.b.now-2,
                      trend_reentry_after=boundary,trend_reentry_run_id=self.r.state['run_id'])
  self.r.state['order_history']=[dict(tag='previous-exit',run_id=self.r.state['run_id'],side='SELL',status='FILLED',filled_at=boundary,is_entry=False)]
  self.r._candle_step()
  self.assertIsNotNone(self.r.state.get('position'))
  self.assertEqual(self.r.state['position']['direction'],'BULLISH')
  self.assertEqual(self.b.sent,[])
