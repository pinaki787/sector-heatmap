import threading
import unittest
from unittest.mock import patch
from sector_heatmap.chart_feed_recovery import ChartFeedRecoveryMixin, safe_stream_error

class Immediate:
    def __init__(self, target, **kwargs):self.target=target
    def start(self):self.target()
    def join(self, timeout=None):pass

class Socket:
    def __init__(self):self.closed=0;self.subscribed=[]
    def close_connection(self):self.closed+=1
    def subscribe(self, symbols, **kwargs):
        self.subscribed+=symbols
        if symbols==['BAD']:raise ValueError('private-secret')

class Base:
    def __init__(self):
        self.lock=threading.Lock();self.subscription_lock=threading.Lock()
        self.socket=None;self.connected=False;self.ticks={};self.symbols={'NIFTY'}
        self.stream_generation=0;self.last_subscribe={};self.starts=0
    def start(self):
        if self.socket:return
        self.starts+=1;self.stream_generation+=1;self.socket=Socket();self.connected=True
    def tick(self, symbol):
        if symbol not in self.ticks:raise ValueError('No tick')
        return self.ticks[symbol][0]
    def stream_status(self):return dict(connected=self.connected)

class Chart(ChartFeedRecoveryMixin, Base):
    token=b'first'
    def _chart_token_hash(self):return self.token

class Tests(unittest.TestCase):
    def setUp(self):
        self.now=1000
        self.time=patch('sector_heatmap.chart_feed_recovery.time.time',side_effect=lambda:self.now);self.time.start()
        self.thread=patch('sector_heatmap.chart_feed_recovery.threading.Thread',Immediate);self.thread.start()
        self.b=Chart();self.b.start()
    def tearDown(self):self.thread.stop();self.time.stop()
    def test_missing_ticks_replaces_only_transport_preserving_symbols(self):
        old=self.b.socket;self.now+=46
        with self.assertRaises(ValueError):self.b.tick('NIFTY')
        self.assertEqual(old.closed,1);self.assertEqual(self.b.starts,2)
        self.assertEqual(self.b.symbols,{'NIFTY'});self.assertEqual(self.b.stream_generation,3)
    def test_fresh_ticks_do_not_rotate(self):
        self.now+=60;self.b.ticks['NIFTY']=({'exch_feed_time':self.now},self.now)
        self.b.tick('NIFTY');self.assertEqual(self.b.starts,1)
    def test_recent_receipt_with_stale_exchange_time_recovers(self):
        self.now+=60;self.b.ticks['NIFTY']=({'exch_feed_time':1},self.now)
        with self.assertRaises(ValueError):self.b.tick('NIFTY')
        self.assertEqual(self.b.starts,2)
    def test_refreshed_token_replaces_existing_socket(self):
        self.b.token=b'new';self.now+=11
        with self.assertRaises(ValueError):self.b.tick('NIFTY')
        self.assertEqual(self.b.starts,2);self.assertEqual(self.b._chart_token,b'new')
    def test_backoff_prevents_reconnect_storm(self):
        self.now+=46;self.b._recover_chart('NIFTY',self.now)
        self.now+=46;self.b._recover_chart('NIFTY',self.now)
        self.assertEqual(self.b.starts,2)
        self.now+=15;self.b._recover_chart('NIFTY',self.now)
        self.assertEqual(self.b.starts,3)
    def test_bad_subscription_does_not_block_other_symbol(self):
        self.b.symbols={'BAD','NIFTY'};self.b.subscribe_all()
        self.assertEqual(self.b.socket.subscribed,['BAD','NIFTY'])
        self.assertNotIn('private-secret',self.b.stream_error)
    def test_recovery_does_not_call_any_runner(self):
        self.b.runner=object();self.now+=50;self.b._recover_chart('NIFTY',self.now)
        self.assertEqual(self.b.starts,2)
    def test_single_recovery_owner(self):
        self.b._chart_recovery_lock.acquire();self.now+=50
        self.b._recover_chart('NIFTY',self.now);self.assertEqual(self.b.starts,1)
        self.b._chart_recovery_lock.release()
    def test_diagnostics_keep_category_and_never_raw_broker_text(self):
        d=safe_stream_error({'code':-300,'type':'cn','message':'private-secret'})
        self.assertEqual(d,{'code':-300,'category':'authentication'})
        self.assertNotIn('private-secret',str(d))
        self.assertEqual(safe_stream_error({'type':'sub'})['category'],'subscription')

if __name__=='__main__':unittest.main()
