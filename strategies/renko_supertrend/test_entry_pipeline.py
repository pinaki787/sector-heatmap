import csv
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import entry_pipeline as pipeline

class ParallelPreflightTests(unittest.TestCase):
    def preflight(self,*,positions=None,orders=None,balance=1000,required=100,barrier=None,deadline=None):
        def read(value):
            if barrier:barrier.wait(timeout=2)
            return value
        self.b=SimpleNamespace(
            validate_order=lambda order:None,
            contract=lambda symbol:{'quantity_multiplier':1},
            quote=lambda symbol:{'bid':9.9,'ask':10},
            positions=lambda:read(positions or []),
            orders=lambda:read(orders or []))
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'s':'ok','data':{'margin_total':required}})
        with patch('strategies.ema_crossover.broker._current_client',return_value=object()),              patch('strategies.ema_crossover.broker.account_read',side_effect=lambda *args:read({})),              patch('strategies.ema_crossover.broker.available_funds',return_value=balance),              patch('strategies.ema_crossover.broker.requests.post',side_effect=lambda *args,**kw:read(response)):
            pipeline.broker_preflight(self.b,{'symbol':'TEST','qty':1},{'_entry_deadline':deadline or time.time()+5})
    def test_all_four_independent_reads_are_concurrent(self):
        self.preflight(barrier=threading.Barrier(4))
        self.assertTrue(all(v is not None for v in self.b.last_entry_preflight['stages'].values()))
    def test_existing_exposure_or_pending_order_still_blocks(self):
        with self.assertRaisesRegex(ValueError,'Existing position'):
            self.preflight(positions=[{'symbol':'TEST','netQty':1}])
        with self.assertRaisesRegex(ValueError,'Outstanding order'):
            self.preflight(orders=[{'symbol':'TEST','status':6}])
    def test_funds_reserve_and_margin_still_block(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            self.preflight(balance=10)
        with self.assertRaisesRegex(ValueError,'margin unavailable'):
            self.preflight(required=2000)
    def test_expired_original_signal_never_starts_broker_checks(self):
        with self.assertRaisesRegex(ValueError,'expired'):
            self.preflight(deadline=time.time()-1)
        self.assertIsNone(self.b.last_entry_preflight['stages']['metadata'])
    def test_ownership_timeout_returns_without_waiting_or_submission(self):
        release=threading.Event()
        try:
            begin=time.monotonic()
            with self.assertRaisesRegex(ValueError,'deadline'):
                pipeline.bounded_read(lambda:release.wait(2),time.time()+.03)
            self.assertLess(time.monotonic()-begin,.5)
        finally:release.set()

class MasterCacheTests(unittest.TestCase):
    def test_unchanged_master_is_reused_but_replacement_and_age_are_checked(self):
        from strategies.ema_crossover.broker import FyersBroker
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'NSE_FO.csv';p.write_text('one,two\n')
            b=FyersBroker(folder,lambda *a:[],lambda *a:None)
            rows=b.rows('NSE_FO')
            self.assertIs(b.rows('NSE_FO'),rows)
            replacement=p.with_suffix('.new');replacement.write_text('three,four\n');replacement.replace(p)
            self.assertEqual(b.rows('NSE_FO'),(('three','four'),))
            os.utime(p,(time.time()-90000,time.time()-90000))
            with self.assertRaisesRegex(ValueError,'24 hours'):b.rows('NSE_FO')

class ErrorBoundaryTests(unittest.TestCase):
    def test_price_preflight_error_does_not_rearm_or_consume_intervening_bricks(self):
        from .runner import Runner as RenkoSupertrendRunner
        r=object.__new__(RenkoSupertrendRunner)
        r.state={'eligible_since':100,'config':{'strategy_basis':'RENKO','renko_confirmation':'PRICE'}}
        r.clock=lambda:200;r.event=lambda status,message:None
        try:raise ValueError('preflight expired')
        except ValueError as error:r.handle_step_error(error)
        self.assertEqual(r.state['eligible_since'],100)
        self.assertIn('ValueError',r.state['last_execution_error']['traceback'])
    def test_legacy_error_boundary_is_preserved(self):
        from .runner import Runner as RenkoSupertrendRunner
        r=object.__new__(RenkoSupertrendRunner)
        r.state={'eligible_since':100,'config':{}}
        r.clock=lambda:200;r.event=lambda *args:None
        r.handle_step_error(ValueError('legacy error'))
        self.assertEqual(r.state['eligible_since'],200)
    def test_latest_failed_qualification_blocks_even_if_original_signal_passed(self):
        from .runner import Runner as RenkoSupertrendRunner
        r=object.__new__(RenkoSupertrendRunner)
        r.state={'run_id':'same','config':{'renko_confirmation':'PRICE'},
                 'last_signal':{'market_event_at':100},'eligible_since':90}
        r.clock=lambda:101;r.renko_loss_entry_gate=lambda **kw:True
        r._price_export=('same',{'last':{'entry_qualified':False,'direction':'BEARISH'}})
        with self.assertRaisesRegex(ValueError,'setup changed'):
            r.validate_entry_authorization({'direction':'BEARISH'})

class PublicationIsolationTests(unittest.TestCase):
    def test_producer_does_not_mutate_execution_engine_or_config(self):
        from queue import SimpleQueue
        from .price_basis import produce
        from .runner import analysis
        from .test_brick_basis import BASE,candles
        config={**BASE,'_run_id':'run','renko_confirmation':'PRICE'}
        original=analysis(candles([100,135,165,195]),config,.05)
        stamp=original['last']['timestamp']+1
        with tempfile.TemporaryDirectory() as folder:
            r=SimpleNamespace(state={'config':config,'run_id':'run','renko_engine':original},
                path=Path(folder)/'state.json',confirmed_price_events=SimpleQueue(),_price_stream_session='session')
            before=json.dumps(r.state,sort_keys=True)
            produce(r,{'ltp':190,'exch_feed_time':stamp},stamp+.01,1)
            produce(r,{'ltp':225,'exch_feed_time':stamp+1},stamp+1.01,1,config={**config,'prepared_marker':'kept'})
            self.assertIs(r.state['renko_engine'],original)
            self.assertEqual(json.dumps(r.state,sort_keys=True),before)
            self.assertEqual(r._price_export[1]['last']['close'],220)
            self.assertEqual(r._confirmed_publication['latest']['close'],220)
            self.assertEqual(r._confirmed_publication['_config']['prepared_marker'],'kept')
            self.assertEqual(r.confirmed_price_events.qsize(),3)

class OrderedBatchTests(unittest.TestCase):
    def test_failed_event_does_not_discard_next_fresh_event(self):
        from queue import SimpleQueue
        from .price_basis import run_step
        calls=[];errors=[];q=SimpleQueue()
        for stamp in (999,1000):
            q.put({'market_event_at':stamp,'timestamp':stamp,'source_timestamp':stamp,
                   'direction':'BULLISH','entry_qualified':True})
        r=SimpleNamespace(state={'running':True,'run_id':'run','config':{'timeframe':'1 minute'},
                                'position':None,'pending':None},
            recovery=SimpleNamespace(beat=lambda:None),lock=threading.RLock(),
            stop_requested=threading.Event(),clock=lambda:1000,
            _price_test_producer=True,confirmed_price_events=q,
            observe_renko_loss_range=lambda row:None,save=lambda:None,
            handle_step_error=errors.append)
        def execute():
            calls.append(r._price_current['timestamp'])
            if len(calls)==1:raise ValueError('transient preflight failure')
        r._candle_step=execute
        run_step(r)
        self.assertEqual(calls,[999,1000])
        self.assertEqual(len(errors),1)
