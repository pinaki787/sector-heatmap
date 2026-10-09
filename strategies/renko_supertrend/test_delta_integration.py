"""Isolated broker/market concurrency tests; no production network or order calls."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from .batch import Batch
from .delta_broker import Broker
from .delta_runner import DeltaRunner, DeltaAdoptedRunner
from .runner import Runner, analysis
from .test_runner import FakeBroker
from .test_delta_contracts import product, NOW
from .adoption import identity


class NativeFake(FakeBroker):
    def __init__(self):
        super().__init__()
        self.delta=SimpleNamespace(live={'orders':{}},product=lambda symbol:product(),_inr_conversion=lambda:dict(rate=85))
        self.resolved_contracts={}
    def resolve(self,config,direction):
        meta=self.contract('C-BTC-90000-071026' if direction=='BULLISH' else 'P-BTC-90000-071026')
        self.resolved_contracts[meta['symbol']]=meta;return meta
    def contract(self,symbol):
        return dict(symbol=symbol,product_id=123,lot_size=1,tick_size=.1,quantity_multiplier=.001,
                    quote_currency='USD',settlement_currency='USD',product='DELTA_LONG_OPTION',
                    option_type='CE' if symbol.startswith('C-') else 'PE',strike=90000,expiry_epoch=self.now+86400)
    def order(self,symbol,qty,side,quote):return dict(symbol=symbol,qty=qty,side=side,type=1,productType='DELTA_LONG_OPTION')


def config(symbol='BTCUSD'):
    return dict(strategy='RENKO_SUPERTREND_V1',rsi_slope_enabled=False,underlying=symbol,timeframe='1 minute',mode='PAPER',lots=1,max_trades=2,
                atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,exit_policy='OPPOSITE_CONFIRMED_SIGNAL',
                broker='DELTA_INDIA',price_source='PERPETUAL_LAST_TRADE',order_terms='MARKETABLE_LIMIT_IOC',
                carry_policy='DAILY_SQUARE_OFF',session_deadline='23:30')


class ConcurrentRulesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        mtf_patch=patch.object(Runner,'supertrend_agreement',return_value=dict(allowed=True,reason='MTF fixture agrees'))
        mtf_patch.start();self.addCleanup(mtf_patch.stop)
    def arm(self,runner,cfg):
        runner.activate(dict(cfg,configuration_revision=runner.runtime_revision),background=False)
        runner.state['eligible_since']=runner.clock()-10
        runner.step()
        self.addCleanup(runner.release)
    def test_fyers_nifty_open_then_delta_btc_start_does_not_replace_exposure(self):
        fb=FakeBroker();fy=Runner(fb,self.root/'fyers.json',lambda:fb.now)
        self.arm(fy,dict(config('NSE:NIFTY50-INDEX'),broker='FYERS'))
        self.assertIsNotNone(fy.state['position']);before=deepcopy(fy.state)
        db=NativeFake();delta=DeltaRunner(db,self.root/'delta.json',lambda:db.now)
        self.arm(delta,config())
        self.assertEqual(fy.state,before)
        self.assertEqual(delta.state['position']['symbol'],'C-BTC-90000-071026')
        self.assertEqual(delta.state['position']['quantity'],1)
        self.assertEqual(delta.state['position']['quantity_multiplier'],.001)
        self.assertEqual(fb.sent,[]);self.assertEqual(db.sent,[])
        delta.stop()
        self.assertEqual(fy.state,before)
        self.assertTrue(fy.state['running'])
    def test_same_broker_multiple_markets_have_independent_quota_settings_and_stop(self):
        runners=[]
        for symbol in ('NSE:NIFTY50-INDEX','BSE:SENSEX-INDEX','MCX:CRUDEOIL26OCTFUT'):
            broker=FakeBroker();runner=Runner(broker,self.root/(symbol.split(':')[0]+'.json'),lambda b=broker:b.now)
            self.arm(runner,dict(config(symbol),broker='FYERS'));runners.append(runner)
        states=[deepcopy(r.state) for r in runners]
        runners[1].stop()
        self.assertEqual(runners[0].state,states[0]);self.assertEqual(runners[2].state,states[2])
        self.assertEqual([r.state['trades_used'] for r in runners],[1,1,1])
    def test_delta_restart_keeps_exposure_but_never_autostarts(self):
        broker=NativeFake();runner=DeltaRunner(broker,self.root/'delta.json',lambda:broker.now)
        self.arm(runner,config());held=deepcopy(runner.state['position']);runner.release()
        restored=DeltaRunner(NativeFake(),self.root/'delta.json',lambda:broker.now)
        self.assertFalse(restored.state['running']);self.assertEqual(restored.state['position'],held)
    def test_exact_signal_formula_is_shared(self):
        broker=FakeBroker();a=config('BTCUSD');b={**a,'underlying':'NSE:NIFTY50-INDEX'}
        self.assertEqual(analysis(broker.rows,a,.05)['rows'],analysis(broker.rows,b,.05)['rows'])
        self.assertIs(DeltaRunner.signal,Runner.signal)
        self.assertEqual(DeltaAdoptedRunner.configure(config())['broker'],'DELTA_INDIA')
    def test_native_adoption_identity_cannot_be_spoofed_by_product_label(self):
        row=dict(symbol='C-BTC-90000-071026',netQty=4,netAvg=20,productType='DELTA_LONG_OPTION')
        with self.assertRaises(ValueError):identity(row)
        self.assertEqual(identity(dict(row,broker='DELTA_INDIA',product_id=123,quote_currency='USD'))['product'],'DELTA_LONG_OPTION')


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.b=Broker(SimpleNamespace(clock=lambda:NOW),Path(self.temp.name));self.b.subscribe('BTCUSD',60);self.b.connected=True
    def test_public_stream_uses_trusted_ca_bundle_without_disabling_tls(self):
        import certifi
        with patch('websocket.WebSocketApp') as socket:
            socket.return_value.run_forever.side_effect=lambda **kw:self.b.stopping.set()
            self.b.start();self.b.thread.join(2)
            self.assertFalse(self.b.thread.is_alive())
            ssl=socket.return_value.run_forever.call_args.kwargs['sslopt']
            self.assertEqual(ssl,{'ca_certs':certifi.where()})
    def message(self,**change):
        return dict(type='candlestick_1m',sy='BTCUSD',ts=NOW*1000000,cst=(NOW//60*60)*1000000,res='1m',o=100,h=102,l=99,c=101,v=0,**change)
    def test_backend_candle_is_fresh_and_zero_volume_is_preserved(self):
        self.b.ingest(self.message());self.assertEqual(self.b.tick('BTCUSD')['ltp'],101)
        row=self.b.forming(dict(underlying='BTCUSD',timeframe='1 minute'),[],NOW)
        self.assertEqual(row['volume'],0)
    def test_missing_volume_is_a_gap_and_stale_prices_are_rejected(self):
        msg=self.message();msg.pop('v');self.b.ingest(msg)
        self.assertIsNone(self.b.forming_bars[('BTCUSD',60,NOW//60*60)]['volume'])
        self.b.delta.clock=lambda:NOW+16
        with self.assertRaises(ValueError):self.b.tick('BTCUSD')
    def test_out_of_order_candle_does_not_revise_newer_tick(self):
        self.b.ingest(self.message());msg=self.message();msg.update(ts=(NOW-1)*1000000,c=100)
        self.b.ingest(msg);self.assertEqual(self.b.tick('BTCUSD')['ltp'],101)
    def test_option_quote_is_executable_and_never_uses_mark(self):
        self.b.ingest(dict(type='ob_l1',sy='BTCUSD',ts=NOW*1000000,bp=10,ap=11,mark_price=999))
        self.assertEqual(self.b.quote('BTCUSD')['bid'],10)
        self.b.connected=False
        with self.assertRaises(ValueError):self.b.quote('BTCUSD')
    def test_documented_compact_feed_without_cst_uses_exchange_time_bucket(self):
        message=self.message();message.pop('cst');self.b.ingest(message)
        self.assertEqual(self.b.tick('BTCUSD')['ltp'],101)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.runners={};self.calls=[]
        outer=self
        class Fake:
            runtime_revision='revision'
            def __init__(self):self.state=dict(running=False,position=None,pending=None)
            def configure(self,c):return {k:v for k,v in c.items() if k!='configuration_revision'}
            def preview(self,c):
                if c['underlying']=='BLOCKED':raise ValueError('Unavailable contract')
            def activate(self,c,background=True):
                outer.calls.append(c['underlying']);self.state.update(running=True,config=c);return self.state
        def create(broker,symbol):
            key=broker+':'+symbol
            if key not in self.runners:self.runners[key]=Fake()
            return key
        self.batch=Batch(Path(self.temp.name),create,lambda broker,key:self.runners[key])
        self.payload=dict(request_id='batch-test-123',broker='FYERS',instruments=['NIFTY','BLOCKED','CRUDE'],settings=dict(mode='PAPER',configuration_revision='revision'))
    def test_partial_batch_reports_exact_successes_and_blocker(self):
        result=self.batch.start(self.payload,False)
        self.assertEqual([r['status'] for r in result['results']],['STARTED','BLOCKED','STARTED'])
        self.assertEqual(self.calls,['NIFTY','CRUDE']);self.assertFalse(result['all_selected_active'])
    def test_same_batch_is_idempotent_and_changed_terms_rejected(self):
        first=self.batch.start(self.payload,False);second=self.batch.start(self.payload,False)
        self.assertEqual(first,second);self.assertEqual(len(self.calls),2)
        with self.assertRaises(ValueError):self.batch.start({**self.payload,'instruments':['BTCUSD']},False)
    def test_duplicate_symbol_selection_rejected_before_any_start(self):
        with self.assertRaises(ValueError):self.batch.start({**self.payload,'instruments':['NIFTY','NIFTY']},False)
        self.assertFalse(self.calls)
    def test_existing_active_instance_is_not_overwritten(self):
        self.batch.start(self.payload,False)
        result=self.batch.start({**self.payload,'request_id':'another-test-123'},False)
        self.assertEqual(result['results'][0]['status'],'ALREADY_RUNNING');self.assertEqual(len(self.calls),2)
