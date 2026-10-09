import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from .runner import Runner, configuration
from .signals import series
from .test_signals import candle


class FakeBroker:
    def __init__(self):
        self.now=datetime(2026,10,6,10,0,5,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        self.rows=[candle(i,price) for i,price in enumerate([100,110,120])]
        for i,row in enumerate(self.rows):row['timestamp']=self.now-185+i*60
        self.sent=[];self.book=[];self.qty=0;self.fail=False
    def host_tick_size(self,s):return .05
    def candles(self,c):return self.rows
    def live_enabled(self):return True
    def live_price(self,c,now):return (self.rows[-1]['close'] if isinstance(self.rows,list) and self.rows else 100),now
    def validate_config(self,c):return {'broker':'FAKE','account_identity':'TEST'}
    def start(self):pass
    def stop(self):pass
    def quote(self,s):return dict(bid=10,ask=10)
    def resolve(self,c,d):return dict(symbol='NSE:TESTCE' if d=='BULLISH' else 'NSE:TESTPE',lot_size=20,tick_size=.05,quantity_multiplier=1)
    def order(self,s,q,side,quote):return dict(symbol=s,qty=q,side=side,type=2,productType='MARGIN')
    def validate_order(self,o):pass
    def preflight(self,o,c):pass
    def place(self,o):
        self.sent.append(o)
        if self.fail:raise TimeoutError('uncertain')
        return dict(s='ok',id='O'+str(len(self.sent)))
    def orders(self):return self.book
    def reconcile_position(self,s,q):
        if q!=self.qty:raise ValueError('position mismatch')


class RenkoLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.b=FakeBroker();self.path=Path(self.tmp.name)/'renko.json'
        self.r=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(self.r.release)
        # Existing lifecycle scenarios isolate the new mandatory MTF gate.
        # Real direction/source behavior is covered by test_mtf_supertrend.
        mtf_patch=patch.object(Runner,'supertrend_agreement',return_value=dict(allowed=True,reason='MTF fixture agrees'))
        mtf_patch.start();self.addCleanup(mtf_patch.stop)
        self.c=dict(strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',
                    lots=1,mode='PAPER',atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,
                    exit_policy='OPPOSITE_CONFIRMED_SIGNAL',rsi_slope_enabled=False,ema_exit_enabled=True)
    def start(self):
        p=self.r.preview(self.c);self.r.start(dict(preview_id=p['id'],confirmation=p['confirmation']),background=False)
        self.r.state['eligible_since']=self.b.now-10
    def append(self,price):
        self.b.now+=60
        self.b.rows.append({**candle(len(self.b.rows),price),'timestamp':self.b.rows[-1]['timestamp']+60})
    def test_paper_entry_exit_no_same_candle_reentry_and_no_broker_calls(self):
        self.start();self.r.step()
        self.assertEqual(self.r.state['position']['symbol'],'NSE:TESTCE')
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1)
        self.append(80);self.r.step()
        self.assertIsNone(self.r.state['position'])
        self.r.step();self.assertEqual(len(self.r.state['order_history']),2)
        self.assertEqual([r['reason'] for r in self.r.state['order_history']],['RENKO_EMA_ENTRY','EMA10_CONFIRMED_BREACH'])
        self.assertEqual(self.b.sent,[])
    def test_old_reversal_not_replayed_on_activation(self):
        p=self.r.preview(self.c);self.r.start(dict(preview_id=p['id'],confirmation=p['confirmation']),background=False)
        self.r.step();self.assertIsNone(self.r.state['position'])
        self.append(121);self.r.step();self.assertIsNone(self.r.state['position'])
    def test_uncertain_live_ack_blocks_duplicate_order(self):
        self.c['mode']='LIVE';self.b.fail=True;self.start();self.r.step()
        self.assertEqual(self.r.state['status'],'ORDER_STATUS_UNKNOWN')
        self.assertEqual(len(self.b.sent),1)
        with self.assertRaisesRegex(ValueError,'uniquely reconciled'):self.r.step()
        self.assertEqual(len(self.b.sent),1)
    def test_streaming_history_window_does_not_reseed_and_revision_blocks(self):
        self.r.state['config']=configuration(self.c)
        self.r.signal();self.append(121);expected=series(self.b.rows,self.c)[-1];expected={**expected,'supertrend_cross_direction':expected['cross_direction'],'cross_direction':expected['entry_direction'],'ema_exit':expected['ema10'],'ema_exit_length':10,'ema_exit_enabled':True}
        self.b.rows=self.b.rows[1:]
        self.assertEqual(self.r.signal(),expected)
        self.b.rows[-1]['volume']=2
        self.r.signal()  # Volume is not an input to this strategy.
        self.b.rows[-1]['high']+=1
        with self.assertRaisesRegex(ValueError,'full original anchor'):self.r.signal()
    def test_restart_recovers_engine_state_without_starting_runner(self):
        self.r.state['config']=configuration(self.c);self.r.signal()
        other=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(other.release)
        self.assertFalse(other.state['running'])
        self.assertEqual(other.signal(),self.r.state['last_signal'])
    def test_configuration_requires_correct_strategy_and_exit_policy(self):
        for change in (dict(strategy='RSI_BASED_EMA_V1'),dict(exit_policy=None),dict(trailing_enabled=True,trailing_distance=0),dict(spot_stop=-100)):
            with self.assertRaises(ValueError):configuration({**self.c,**change})
        self.assertEqual(self.r.snapshot()['strategy'],'RENKO_SUPERTREND_V1')
        self.assertNotIn('rsi_length',configuration(self.c))
