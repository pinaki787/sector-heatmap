from copy import deepcopy
from types import SimpleNamespace
import threading
import unittest
from .confirmed_feed import SharedCandleFeed,CandlePending,SharedQuoteHub,confirmed_export,bind_confirmed
from .runner import analysis,provisional
from .test_signals import candle


class SharedFeedTests(unittest.TestCase):
    def test_concurrent_consumers_share_one_nonblocking_request(self):
        now=[600.];feed=SharedCandleFeed(lambda:now[0]);entered=threading.Event();release=threading.Event();calls=[]
        rows=[{**candle(i,100+i),'timestamp':i*60} for i in range(10)]
        def slow():
            calls.append(1);entered.set();release.wait(2);return rows
        for _ in range(5):
            with self.assertRaises(CandlePending):feed.read(('X','1 minute'),60,slow)
        self.assertTrue(entered.wait(1));self.assertEqual(len(calls),1)
        release.set();feed.entries[('X','1 minute')]['worker'].join(2)
        got=feed.read(('X','1 minute'),60,slow);got[0]['close']=999
        self.assertNotEqual(feed.read(('X','1 minute'),60,slow)[0]['close'],999)
        now[0]=661;release.clear()
        self.assertEqual(feed.read(('X','1 minute'),60,slow)[0]['close'],100)
        self.assertTrue(feed.health(('X','1 minute'))['busy'])
        release.set();feed.entries[('X','1 minute')]['worker'].join(2)

    def test_late_completed_candle_retries_without_promoting_cached_forming_bar(self):
        now=[600.];feed=SharedCandleFeed(lambda:now[0]);key=('X','1 minute')
        rows=[{**candle(0,100),'timestamp':480},{**candle(1,101),'timestamp':540,'is_forming':True}]
        def load():return rows
        with self.assertRaises(CandlePending):feed.read(key,60,load)
        feed.entries[key]['worker'].join(2)
        cached=feed.read(key,60,load)
        self.assertTrue(cached[-1]['is_forming'])
        self.assertEqual(feed.health(key)['next_at'],601)
        now[0]=601;rows[-1]['is_forming']=False
        feed.read(key,60,load);feed.entries[key]['worker'].join(2)
        self.assertFalse(feed.read(key,60,load)[-1]['is_forming'])
        self.assertEqual(feed.health(key)['latest_completed'],540)

    def test_failure_retains_last_snapshot_and_single_retry_budget(self):
        now=[600.];feed=SharedCandleFeed(lambda:now[0]);key=('X','1 minute')
        def good():return [{**candle(0,100),'timestamp':540}]
        with self.assertRaises(CandlePending):feed.read(key,60,good)
        feed.entries[key]['worker'].join(2);before=feed.read(key,60,good)
        now[0]=661
        def fail():raise RuntimeError('secret provider text')
        feed.read(key,60,fail);feed.entries[key]['worker'].join(2)
        self.assertEqual(feed.read(key,60,fail),before)
        self.assertNotIn('secret',str(feed.health(key)))
        self.assertEqual(feed.health(key)['next_at'],662)

    def test_accounts_get_distinct_pools(self):
        from .confirmed_feed import feed_for
        def account_a():pass
        def account_b():pass
        self.assertIs(feed_for(account_a),feed_for(account_a))
        self.assertIsNot(feed_for(account_a),feed_for(account_b))

    def test_hub_stop_detaches_only_one_consumer(self):
        class Transport:
            def __init__(self):self.socket=None;self.connected=True;self.stream_error=None;self.starts=0
            def start(self):
                if self.socket is None:self.socket=object();self.starts+=1
            def tick(self,symbol):return {'symbol':symbol,'ltp':100}
        class Owner:
            def __init__(self):self.lock=threading.Lock();self.symbols={'X'};self.ticks={};self.seen=[];self.on_tick=self.seen.append
        transport=Transport();hub=SharedQuoteHub(transport);one=Owner();two=Owner()
        hub.join(one);hub.join(two);self.assertEqual(transport.starts,1)
        hub.publish({'symbol':'X','ltp':100});self.assertEqual(len(one.seen),1);self.assertEqual(len(two.seen),1)
        hub.leave(one);hub.publish({'symbol':'X','ltp':101})
        self.assertEqual(len(one.seen),1);self.assertEqual(len(two.seen),2);self.assertTrue(transport.connected)
        hub.join(one);self.assertEqual(transport.starts,1)

    def test_confirmed_export_is_atomic_owned_and_independent_of_provisional_signal(self):
        c=dict(underlying='NSE:TEST',timeframe='1 minute',brick_mode='Manual',manual_brick=1)
        rows=[{**candle(i,100+i),'timestamp':i*60} for i in range(40)]
        engine=analysis(rows,c,.05);state=dict(run_id='one',config=c,renko_engine=engine,last_signal={'supertrend':999})
        before=deepcopy(state);export=confirmed_export(state,True)
        self.assertEqual(export['latest'],engine['last']);self.assertNotEqual(export['latest'].get('supertrend'),999)
        export['rows'][0]['close']=888;self.assertEqual(state,before)
        runner=SimpleNamespace(state=state,lock=threading.Lock())
        self.assertEqual(bind_confirmed(runner,'one','NSE:TEST','1 minute')['revision'],confirmed_export(state)['revision'])
        for run,symbol,frame in [('other','NSE:TEST','1 minute'),('one','NSE:OTHER','1 minute'),('one','NSE:TEST','5 minutes')]:
            with self.assertRaises(ValueError):bind_confirmed(runner,run,symbol,frame)
        # Repeated previews clone the same confirmed recurrence.
        forming={**candle(40,141),'timestamp':2400,'is_forming':True,'stream_exchange_at':2401}
        provisional(engine,forming,c,.05,2401);provisional(engine,{**forming,'close':142,'high':145},c,.05,2401)
        self.assertEqual(state,before)


class PipelineIntegrationTests(unittest.TestCase):
    def test_supported_timeframes_refresh_at_their_own_boundary(self):
        for seconds in (60,300,900):
            with self.subTest(seconds=seconds):
                now=[float(seconds*20)]
                feed=SharedCandleFeed(lambda:now[0]);key=('X',seconds);calls=[]
                def loader():
                    calls.append(1)
                    return [{**candle(0,100),'timestamp':int(now[0]//seconds)*seconds-seconds}]
                with self.assertRaises(CandlePending):feed.read(key,seconds,loader)
                feed.entries[key]['worker'].join(2)
                for _ in range(5):feed.read(key,seconds,loader)
                self.assertEqual(len(calls),1)
                now[0]+=seconds+1
                feed.read(key,seconds,loader);feed.entries[key]['worker'].join(2)
                self.assertEqual(len(calls),2)

    def test_runner_reuses_committed_engine_until_source_revision_changes(self):
        from .test_history_recovery import HistoryRecoveryTests
        fixture=HistoryRecoveryTests();fixture.setUp()
        try:
            fixture.r.state['config']=fixture.c
            revision=['one'];fixture.b.candle_revision=lambda c:revision[0]
            from unittest.mock import patch
            with patch.object(fixture.r,'current_analysis',wraps=fixture.r.current_analysis) as calculate:
                fixture.r.signal();fixture.r.signal()
                self.assertEqual(calculate.call_count,1)
                fixture.append(130);revision[0]='two';fixture.r.signal()
                self.assertEqual(calculate.call_count,2)
        finally:
            fixture.doCleanups()

    def test_chart_tail_uses_shared_candles_without_duplicate_provider_request(self):
        import tempfile
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from .chart_history import ChartHistory
        from .test_chart_history import Client
        now=datetime(2026,10,6,10,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        client=Client();shared=[]
        with tempfile.TemporaryDirectory() as folder:
            history=ChartHistory(folder,min_interval=0,tail_provider=lambda symbol,frame:shared)
            config={'underlying':'MCX:TEST','timeframe':'1 minute'}
            history.load(client,'MCX:TEST','1 minute','custom','2026-10-06','2026-10-06',config,.05,now)
            count=len(client.calls)
            shared.append(dict(timestamp=int(now),open=999,high=1001,low=998,close=1000,is_forming=False))
            _,rows,_,_=history.load(client,'MCX:TEST','1 minute','custom','2026-10-06','2026-10-06',config,.05,now+61)
            self.assertEqual(client.calls.__len__(),count)
            self.assertEqual(next(r for r in rows if r['timestamp']==now)['close'],1000)


class PublicationLockTests(unittest.TestCase):
    def test_chart_reads_published_state_while_execution_lock_is_held(self):
        from .confirmed_feed import publish_confirmed
        config=dict(underlying='NSE:TEST',timeframe='1 minute')
        engine=analysis([candle(i,100+i) for i in range(40)],config,.05)
        runner=SimpleNamespace(state=dict(run_id='one',config=config,renko_engine=engine),lock=threading.Lock())
        publish_confirmed(runner)
        with runner.lock:
            exported=bind_confirmed(runner,'one','NSE:TEST','1 minute')
            self.assertEqual(exported['latest'],engine['last'])
            exported['rows'][0]['close']=999
            self.assertNotEqual(bind_confirmed(runner,'one','NSE:TEST','1 minute')['rows'][0]['close'],999)
        runner.state['run_id']='two'
        with self.assertRaises(ValueError):bind_confirmed(runner,'one','NSE:TEST','1 minute')
        with self.assertRaises(CandlePending):bind_confirmed(runner,'two','NSE:TEST','1 minute')


class SharedExecutableQuoteTests(unittest.TestCase):
    def test_shared_quote_preserves_real_bid_provenance(self):
        from .runner import Broker
        from .confirmed_feed import SharedQuoteHub
        import time
        now=time.time();symbol='MCX:TESTCE'
        raw=dict(symbol=symbol,bid_price=100,ask_price=101,exch_feed_time=now,_bid_received_at=now,_bid_exchange_at=now)
        transport=SimpleNamespace(lock=threading.Lock(),ticks={symbol:(raw,now)},connected=True,socket=None,stream_error=None,tick=lambda symbol:raw)
        owner=object.__new__(Broker);owner.lock=threading.Lock();owner.symbols=set();owner.ticks={symbol:(dict(raw),now)};owner._shared_quote_hub=SharedQuoteHub(transport)
        quote=owner.quote(symbol)
        self.assertEqual(quote['received_at'],now)
        self.assertEqual(quote['exchange_at'],now)
        raw['_bid_received_at']=now-30;raw['_bid_exchange_at']=now-30
        with self.assertRaisesRegex(ValueError,'Fresh executable'):owner.quote(symbol)
