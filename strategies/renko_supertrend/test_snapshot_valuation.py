"""Read-only valuation under real execution-lock contention; no network or orders."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch

from .delta_broker import Broker
from .delta_runner import DeltaRunner
from .runner import Runner
from .test_delta_integration import NativeFake, config


class SnapshotValuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.b=NativeFake()
        self.r=DeltaRunner(self.b,self.root/'renko-delta-state.json',lambda:self.b.now)
        self.addCleanup(self.r.release)
        with patch.object(Runner,'supertrend_agreement',return_value=dict(allowed=True,reason='fixture')):
            cfg=dict(config(),lots=100)
            self.r.activate(dict(cfg,configuration_revision=self.r.runtime_revision),background=False)
            self.r.state['eligible_since']=self.b.now-10
            self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        self.chart=Broker(SimpleNamespace(clock=lambda:self.b.now),self.root/'history')
        self.chart.connected=True;self.chart.start=lambda:None  # Public stream never started in tests.
        self.r.valuation_adapter=self.chart
        self.symbol=self.r.state['position']['symbol']
        self.chart.symbols.add(self.symbol)
        self.feed()
        self.baseline=deepcopy(self.r.state)

    def feed(self,age=0,bid=30,ask=31):
        stamp=self.b.now-age
        self.chart.ingest(dict(type='ob_l1',symbol=self.symbol,ts=stamp*1e6,bp=bid,ap=ask),stamp)

    def hold_execution_lock(self):
        entered=threading.Event();release=threading.Event()
        def busy():
            with self.r.lock:entered.set();release.wait(5)
        thread=threading.Thread(target=busy);thread.start()
        self.addCleanup(lambda:(release.set(),thread.join(2)))
        self.assertTrue(entered.wait(1))
        return release,thread

    def test_fresh_delta_bid_survives_execution_lock_timeout(self):
        self.hold_execution_lock()
        result=self.r.snapshot()
        self.assertTrue(result['status_read_delayed'],'real base snapshot contention path exercised')
        self.assertTrue(result['pnl']['available'])
        self.assertAlmostEqual(result['pnl']['unrealized'],2)  # (30-10)*100*.001
        trade=next(t for t in result['trade_history'] if t['remaining_quantity'])
        self.assertEqual(trade['valuation']['price'],30)
        self.assertEqual(trade['valuation']['exchange_at'],self.b.now)
        self.assertEqual(result['pnl']['updated_at'],self.b.now)
        self.assertEqual(self.r.state,self.baseline)
        self.assertEqual(self.b.sent,[])

    def test_genuine_stale_delta_quote_remains_unavailable(self):
        self.b.now+=16;self.hold_execution_lock()
        result=self.r.snapshot()
        self.assertFalse(result['pnl']['available']);self.assertIsNone(result['pnl']['unrealized'])
        self.assertIn('Fresh executable Delta backend quote required',result['pnl']['quote_error'])
        trade=next(t for t in result['trade_history'] if t['remaining_quantity'])
        self.assertIsNone(trade['valuation'])
        self.assertEqual(self.b.sent,[])

    def test_disconnected_quote_adapter_is_not_marked_fresh(self):
        self.chart.connected=False;self.hold_execution_lock()
        result=self.r.snapshot()
        self.assertFalse(result['pnl']['available']);self.assertIn('quote_error',result['pnl'])

    def test_old_persisted_position_is_rejected_before_quote_read(self):
        self.hold_execution_lock()
        self.r.state['position']['quantity']-=1  # Mimic a newer in-memory partial fill before save.
        with patch.object(self.chart,'quote',side_effect=AssertionError('wrong position queried')) as quote:
            result=self.r.snapshot()
        quote.assert_not_called()
        self.assertFalse(result['pnl']['available']);self.assertIn('Position changed',result['pnl']['quote_error'])

    def test_position_changes_during_quote_read_do_not_publish_mark(self):
        self.hold_execution_lock()
        original=self.chart.quote
        for change in ('quantity','entry_price','lifecycle_id','run_id','close'):
            with self.subTest(change=change):
                self.r.state=deepcopy(self.baseline)
                def changed(symbol):
                    quote=original(symbol)
                    if change=='close':self.r.state['position']=None
                    elif change=='run_id':self.r.state['run_id']='different-run'
                    elif change=='lifecycle_id':self.r.state['position']['lifecycle_id']='new-lifecycle'
                    else:self.r.state['position'][change]+=1
                    return quote
                with patch.object(self.chart,'quote',side_effect=changed):result=self.r.snapshot()
                self.assertFalse(result['pnl']['available']);self.assertIsNone(result['pnl']['unrealized'])
                self.assertIn('Position changed during valuation',result['pnl']['quote_error'])
                old_trade=next(t for t in result['trade_history'] if t['remaining_quantity'])
                self.assertIsNone(old_trade['valuation'])
                self.assertEqual(old_trade['remaining_quantity'],100,'journal uses copied exposure, not the newer state')

    def test_short_position_uses_executable_ask(self):
        result=deepcopy(self.baseline)
        result['position']['entry_side']=-1;self.r.state['position']['entry_side']=-1
        result['pnl']={'available':False,'unrealized':None,'quote_error':'old error'}
        valuation=self.r.snapshot_valuation(result)
        self.assertEqual(valuation['price'],31)
        self.assertAlmostEqual(result['pnl']['unrealized'],-2.1)
        self.assertNotIn('quote_error',result['pnl'])

    def test_quote_that_ages_during_read_is_rejected(self):
        result=deepcopy(self.baseline);result['pnl']={'available':True,'unrealized':5,'updated_at':self.b.now}
        original=self.chart.quote
        def aged(symbol):
            quote=original(symbol);self.b.now+=16;return quote
        with patch.object(self.chart,'quote',side_effect=aged):valuation=self.r.snapshot_valuation(result)
        self.assertIsNone(valuation);self.assertFalse(result['pnl']['available'])
        self.assertIn('stale',result['pnl']['quote_error']);self.assertNotIn('updated_at',result['pnl'])
