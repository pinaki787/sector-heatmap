from copy import deepcopy
import json
import unittest
from . import test_runner as fixtures
from .runner import Runner

class JournalTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    start=fixtures.RenkoLifecycleTests.start
    append=fixtures.RenkoLifecycleTests.append
    def test_frozen_entry_exit_snapshots_and_durable_roundtrip(self):
        self.start();self.r.step()
        entry=deepcopy(self.r.state['order_history'][0]['indicator_snapshot'])
        self.assertIsNotNone(entry['indicators']['ema10'])
        self.r.state['config']['factor']=2
        self.assertEqual(self.r.state['order_history'][0]['indicator_snapshot'],entry)
        self.r.state['config']['factor']=.1
        self.append(80);self.r.step()
        snap=self.r.snapshot()['trade_history'][0]
        self.assertEqual(snap['entry_indicator_snapshot'],entry)
        self.assertIsNotNone(snap['exit_indicator_snapshots'][0]['indicators']['ema10'])
        self.assertEqual(snap['remaining_quantity'],0)
        self.assertTrue(snap['reconciliation_events'])
        restored=Runner(self.b,self.path,lambda:self.b.now)
        self.assertEqual(restored.snapshot()['trade_history'],self.r.snapshot()['trade_history'])
        self.assertFalse(restored.state['running'])
        json.dumps(snap,allow_nan=False)
    def test_live_fixture_partial_reconciliation_retains_snapshot_and_ids(self):
        self.c['mode']='LIVE';self.start();self.r.step()
        pending=self.r.state['pending'];original=deepcopy(pending['position']['entry_indicator_snapshot'])
        self.r.record_order(pending,'PARTIAL',7,10)
        self.r.state['last_signal']['ema10']=999
        self.r.record_order(pending,'PARTIAL',13,11)
        row=self.r.state['order_history'][0]
        self.assertEqual(row['indicator_snapshot'],original)
        self.assertEqual(row['order_id'],'O1');self.assertEqual(row['remaining'],7)
        self.assertEqual([e['filled'] for e in row['reconciliation_events']], [0,0,7,13])
        self.r.save();restored=Runner(self.b,self.path,lambda:self.b.now)
        trade=restored.snapshot()['trade_history'][0]
        self.assertEqual(trade['entry_filled'],13);self.assertEqual(trade['entry_order_ids'],['O1'])
        self.assertEqual(trade['entry_indicator_snapshot'],original)
        self.assertIsNone(trade['end_time']);self.assertFalse(restored.state['running'])

    def test_paper_register_preserves_controls_lots_and_quote_provenance(self):
        self.b.quote=lambda symbol:dict(bid=11,ask=11.2,exchange_at=self.b.now-1,received_at=self.b.now)
        self.start();self.r.step()
        t=self.r.snapshot()['trade_history'][0]
        self.assertEqual(t['entry_side'],'BUY')
        self.assertEqual(t['lots'],1)
        self.assertEqual(t['valuation']['exchange_at'],self.b.now-1)
        self.assertEqual(t['valuation']['bid'],11)
        self.assertEqual(t['configured_lots'],1)
        self.assertIsNone(t['spot_target'])
        self.assertFalse(t['trailing_enabled'])
        self.assertTrue(t['entry_order_ids'][0].startswith('PAPER-ORDER-'))
        self.assertTrue(t['entry_reasons'])
