import unittest
from copy import deepcopy
from .price_basis import observe
from .runner import analysis,ema_adverse
from .test_brick_basis import BASE,candles

class PriceBasisTests(unittest.TestCase):
 def setUp(self):
  self.config={**BASE,'manual_brick':10,'_run_id':'test','timeframe':'5 minutes',
               'supertrend_slope_enabled':True,'ema_fast_enabled':False,'ema_exit_enabled':False}
  self.export=analysis(candles([100,135,165,195,225,255,285,315]),self.config,.05)
  self.at=self.export['last']['timestamp']+1
 def price(self,value,delta=1,generation=1):
  self.at+=delta
  return observe(self.export,self.config,.05,dict(ltp=value,exch_feed_time=self.at),self.at+.01,generation)
 def test_multiple_full_bricks_before_host_close_and_remainder(self):
  self.assertEqual(self.price(310),[])
  rows=self.price(345)
  self.assertEqual([r['close'] for r in rows],[320,330,340])
  self.assertTrue(all(r['market_event_at']==self.at for r in rows))
  self.assertTrue(all(r['confirmation_basis']=='ORDERED_LIVE_PRICE' for r in rows))
  self.assertTrue(all(r['supertrend'] is not None for r in rows))
  self.assertLess(self.at,self.export['rows'][-4]['timestamp']+300)
  self.assertEqual(self.export['state']['price_renko']['level'],34)
  before=deepcopy(self.export['rows'])
  self.assertEqual(self.price(349),[])
  self.assertEqual(before,self.export['rows'])
 def test_two_box_reversal_and_opposite_brick_exit(self):
  self.price(310);self.price(345)
  self.assertEqual(self.price(325),[])
  rows=self.price(320)
  self.assertEqual([(r['open'],r['close']) for r in rows],[(330,320)])
  self.assertEqual(rows[0]['brick_direction'],'BEARISH')
  from .exit_indicators import reason
  self.assertEqual(reason(self.config,rows[0],'BULLISH'),'OPPOSITE_RENKO_BRICK_CLOSE')
  self.assertEqual(self.price(335),[])
  self.assertEqual([(r['open'],r['close']) for r in self.price(340)],[(330,340)])
 def test_duplicate_out_of_order_and_stale_prices_are_inert(self):
  self.price(310);before=deepcopy(self.export)
  for stamp,received in [(self.at,self.at+.1),(self.at-1,self.at+.1),(self.at+1,self.at+20)]:
   self.assertEqual(observe(self.export,self.config,.05,dict(ltp=400,exch_feed_time=stamp),received,1),[])
   self.assertEqual(before,self.export)
 def test_reconnect_and_long_gap_rebase_without_gap_bricks(self):
  self.price(310);self.price(345);before=deepcopy(self.export['rows'])
  self.assertEqual(self.price(500,generation=2),[])
  self.assertEqual(before,self.export['rows'])
  self.assertEqual([r['close'] for r in self.price(510,generation=2)],[510])
  self.assertEqual(self.price(1000,delta=20,generation=2),[])
 def test_new_run_baselines_without_replaying_price_gap(self):
  self.price(310);self.price(345)
  self.config['_run_id']='new-run'
  self.assertEqual(self.price(600),[])
  self.assertEqual([r['close'] for r in self.price(610)],[610])
 def test_resume_preserves_confirmed_rows_and_indicator_values(self):
  self.price(310);self.price(345)
  saved=deepcopy(self.export);stamp=self.at+1
  tick=dict(ltp=370,exch_feed_time=stamp)
  a=observe(self.export,self.config,.05,tick,stamp+.01,1)
  b=observe(saved,self.config,.05,tick,stamp+.01,1)
  self.assertEqual(a,b);self.assertEqual(saved,self.export)
 def test_projected_history_does_not_veto_executable_qualification(self):
  self.price(310);self.price(345)
  saved=deepcopy(self.export)
  saved['state']['brick_indicator_state']['projected_position']=None
  tick=dict(ltp=245,exch_feed_time=self.at+1)
  a=observe(self.export,self.config,.05,tick,self.at+1.01,1)
  b=observe(saved,self.config,.05,tick,self.at+1.01,1)
  keys=('entry_qualified','entry_direction','entry_diagnostic','supertrend_slope_filter')
  self.assertEqual([{k:r[k] for k in keys} for r in a],[{k:r[k] for k in keys} for r in b])
  self.assertTrue(any(r['entry_qualified'] for r in a))
 def test_same_timestamp_ordered_feed_observations_are_not_lost(self):
  self.price(310)
  stamp=self.at+1
  rows=observe(self.export,self.config,.05,dict(ltp=345,exch_feed_time=stamp,observation_sequence=1),stamp+.01,1)
  self.assertEqual(len(rows),3)
  rows=observe(self.export,self.config,.05,dict(ltp=320,exch_feed_time=stamp,observation_sequence=2),stamp+.02,1)
  self.assertEqual([(r['open'],r['close']) for r in rows],[(330,320)])
  self.assertEqual(observe(self.export,self.config,.05,dict(ltp=345,exch_feed_time=stamp,observation_sequence=1),stamp+.03,1),[])
 def test_process_restart_with_same_run_and_generation_rebases(self):
  self.config['_stream_session']='process-one'
  self.price(310);self.price(345)
  self.config['_stream_session']='process-two'
  self.assertEqual(self.price(600),[])
 def test_core_has_no_broker_symbol_or_segment_specific_confirmation(self):
  for symbol in ('NSE:TEST-INDEX','BSE:TEST-INDEX','MCX:TESTFUT','TESTUSD','NSE_FNO:123'):
   c={**self.config,'underlying':symbol}
   saved=deepcopy(self.export)
   observe(saved,c,.05,dict(ltp=310,exch_feed_time=self.at+1),self.at+1.01,1)
   rows=observe(saved,c,.05,dict(ltp=345,exch_feed_time=self.at+2),self.at+2.01,1)
   self.assertEqual([r['close'] for r in rows],[320,330,340])

 def test_fixed_auto_box_not_resized_by_live_prices(self):
  self.config['brick_mode']='Auto'
  self.price(310);rows=self.price(345)
  self.assertTrue(all(r['box']==10 for r in rows))
if __name__=='__main__':unittest.main()

class PriceExecutionTests(unittest.TestCase):
 def test_shared_runner_paper_entry_and_exit_follow_price_bricks_before_host_close(self):
  import tempfile
  from pathlib import Path
  from .test_delta_integration import NativeFake,config
  from .delta_runner import DeltaRunner
  b=NativeFake();b.stream_status=lambda:dict(connected=True,generation=1)
  b.forming=lambda *args:None  # Exercise the real adapter's submission preflight branch.
  with tempfile.TemporaryDirectory() as tmp:
   r=DeltaRunner(b,Path(tmp)/'state.json',lambda:b.now)
   self.addCleanup(r.release)
   c={**config(), 'strategy_basis':'RENKO','renko_confirmation':'PRICE',
      'carry_policy':'CONTINUOUS','supertrend_slope_enabled':True,'supertrend_slope_min_atr':0,
      'ema_fast_enabled':False,'ema_slow_enabled':False,'ema_third_enabled':False,
      'ema_widening_enabled':False,'rsi_level_enabled':False,'ema_exit_enabled':False,
      'renko_brick_exit_enabled':True}
   r.activate({**c,'configuration_revision':r.runtime_revision},background=False)
   from .price_basis import produce
   r._price_test_producer=True
   r.state['renko_engine']=analysis(b.rows,r.state['config'],.05)
   produce(r,dict(ltp=120,exch_feed_time=b.now-.01),b.now,1)
   r.step()  # Fresh baseline only.
   self.assertEqual(r.state['trades_used'],0)
   start=b.now
   b.now+=1
   produce(r,dict(ltp=155,exch_feed_time=b.now-.01),b.now,1)
   r.step()
   self.assertEqual(r.state['trades_used'],1)
   self.assertIsNotNone(r.state['position'])
   self.assertEqual(r.state['position']['direction'],'BULLISH')
   self.assertLess(r.state['position']['entry_event_at']-start,2)
   self.assertEqual(r.state['last_signal']['confirmation_basis'],'ORDERED_LIVE_PRICE')
   b.now+=1
   produce(r,dict(ltp=120,exch_feed_time=b.now-.01),b.now,1)
   r.step()
   self.assertIsNone(r.state['position'])
   self.assertLess(b.now-start,60)
   self.assertEqual(b.sent,[])

class IndependentPricePublicationTests(unittest.TestCase):
 def test_confirmation_and_durable_publication_do_not_wait_for_execution_lock(self):
  import tempfile,threading
  from types import SimpleNamespace
  from pathlib import Path
  from queue import SimpleQueue
  from .price_basis import produce
  config={**BASE,'_run_id':'run','renko_confirmation':'PRICE'}
  export=analysis(candles([100,135,165,195]),config,.05)
  stamp=export['last']['timestamp']+1
  with tempfile.TemporaryDirectory() as tmp:
   runner=SimpleNamespace(state=dict(config=config,run_id='run',renko_engine=export),
      path=Path(tmp)/'state.json',adapter=SimpleNamespace(host_tick_size=lambda s:.05),
      confirmed_price_events=SimpleQueue(),_price_stream_session='process',lock=threading.Lock())
   produce(runner,dict(ltp=190,exch_feed_time=stamp),stamp+.01,1)
   runner.lock.acquire()
   try:
    rows=produce(runner,dict(ltp=225,exch_feed_time=stamp+1),stamp+1.01,1)
   finally:runner.lock.release()
   self.assertEqual([r['close'] for r in rows],[200,210,220])
   self.assertEqual(runner._confirmed_publication['latest']['close'],220)
   self.assertEqual(runner.confirmed_price_events.qsize(),3)
   self.assertTrue((Path(tmp)/'price-confirmed-history.json').exists())

class StopDrainTests(unittest.TestCase):
 def runner(self,*,pending=False,squareoff=False):
  import threading
  from types import SimpleNamespace
  calls=[]
  r=SimpleNamespace(lock=threading.RLock(),stop_requested=threading.Event(),state=dict(running=True,position=None if pending else {'quantity':1},pending={'tag':'owned'} if pending else None,squareoff_requested=squareoff,accepting_entries=False),recovery=SimpleNamespace(beat=lambda:None))
  def stop():
   calls.append('stop');r.state['squareoff_requested']=True
   if not r.state['position'] and not r.state['pending']:r.state['running']=False
  def manage():calls.append('manage');return 'drain'
  r.stop=stop;r._candle_step=manage;r.stop_requested.set()
  return r,calls
 def test_stop_request_reaches_owned_position_management_without_new_price(self):
  from .price_basis import run_step
  r,calls=self.runner()
  self.assertEqual(run_step(r),'drain');self.assertEqual(calls,['stop','manage'])
  self.assertFalse(r.state['accepting_entries'])
 def test_existing_drain_does_not_reissue_stop_or_starve_pending_reconciliation(self):
  from .price_basis import run_step
  r,calls=self.runner(pending=True,squareoff=True)
  self.assertEqual(run_step(r),'drain');self.assertEqual(calls,['manage'])
 def test_flat_stop_finishes_without_entry_or_management(self):
  from .price_basis import run_step
  r,calls=self.runner();r.state['position']=None
  run_step(r);self.assertFalse(r.state['running']);self.assertEqual(calls,['stop'])
 def test_persisted_squareoff_is_honoured_even_after_in_memory_event_is_lost(self):
  from .price_basis import run_step
  r,calls=self.runner(squareoff=True);r.stop_requested.clear()
  self.assertEqual(run_step(r),'drain');self.assertEqual(calls,['manage'])

class ActualPaperStopTests(unittest.TestCase):
 def test_normal_stop_drains_existing_paper_position_without_new_prices_or_broker_orders(self):
  import tempfile
  from pathlib import Path
  from .runner import Runner
  from .test_runner import FakeBroker
  with tempfile.TemporaryDirectory() as directory:
   broker=FakeBroker();runner=Runner(broker,Path(directory)/'state.json',lambda:broker.now)
   try:
    config=dict(strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',lots=1,mode='PAPER',ema_momentum_enabled=False,atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,exit_policy='OPPOSITE_CONFIRMED_SIGNAL',rsi_slope_enabled=False,ema_exit_enabled=True)
    preview=runner.preview(config);runner.start(dict(preview_id=preview['id'],confirmation=preview['confirmation']),background=False)
    runner.state['eligible_since']=broker.now-10;runner.step()
    self.assertIsNotNone(runner.state['position'])
    runner.state['config'].update(strategy_basis='RENKO',renko_confirmation='PRICE')
    runner.request_stop()
    # Both synchronous and asynchronous request paths lead to the same durable drain.
    if not runner.state.get('squareoff_requested'):runner.stop()
    for _ in range(5):
     if not runner.state['running']:break
     runner.step()
    self.assertFalse(runner.state['running']);self.assertIsNone(runner.state['position']);self.assertIsNone(runner.state['pending'])
    self.assertFalse(runner.state['accepting_entries']);self.assertEqual(broker.sent,[])
    self.assertEqual(runner.state['order_history'][-1]['reason'],'MANUAL_SQUARE_OFF')
    self.assertEqual(runner.state['order_history'][-1]['mode'],'PAPER')
   finally:runner.release()
