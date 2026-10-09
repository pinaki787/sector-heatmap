import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from .runner import Runner
from .test_runner import FakeBroker


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.r=Runner(FakeBroker(),Path(self.tmp.name)/'state.json')
        self.r.state.update(running=True,config={'mode':'PAPER'},account_identity='TEST',accepting_entries=False,
                            position={'symbol':'owned'},pending={'order':{'id':'existing'}},seen=['consumed'])
        self.r.file_lock=Mock()

    def test_stopped_never_rearmed(self):
        self.r.state['running']=False
        with patch('strategies.renko_supertrend.recovery.threading.Thread') as t:
            self.r.recovery.check();t.assert_not_called()
        self.assertEqual(self.r.recovery.status,'STOPPED')

    def test_living_stale_worker_not_duplicated(self):
        self.r.thread=Mock();self.r.thread.is_alive.return_value=True
        self.r.recovery.heartbeat-=100
        with patch('strategies.renko_supertrend.recovery.threading.Thread') as t:
            self.r.recovery.check();t.assert_not_called()
        self.assertEqual(self.r.recovery.status,'WAITING_FOR_INFLIGHT_WORK')

    def test_dead_worker_preserves_order_intent_and_monitor_only(self):
        self.r.thread=Mock();self.r.thread.is_alive.return_value=False
        with patch('strategies.renko_supertrend.recovery.threading.Thread') as t:
            self.r.recovery.check();t.return_value.start.assert_called_once()
        self.assertFalse(self.r.state['accepting_entries'])
        self.assertEqual(self.r.state['pending']['order']['id'],'existing')
        self.assertEqual(self.r.state['seen'],['consumed'])
        self.assertEqual(self.r.state['position']['symbol'],'owned')
        self.assertEqual(self.r.adapter.sent,[])

    def test_account_mismatch_and_backoff_block_recovery(self):
        self.r.state['account_identity']='OTHER'
        with patch('strategies.renko_supertrend.recovery.threading.Thread') as t:
            self.r.recovery.check();self.r.recovery.check();t.assert_not_called()
        self.assertEqual(self.r.recovery.status,'RECOVERY_BLOCKED')
        self.assertGreater(self.r.recovery.next_attempt,self.r.recovery.clock())

    def test_disabled_live_gate_never_restarts(self):
        self.r.state['config']['mode']='LIVE';self.r.adapter.live_enabled=lambda:False
        with patch('strategies.renko_supertrend.recovery.threading.Thread') as t:
            self.r.recovery.check();t.assert_not_called()
        self.assertEqual(self.r.recovery.status,'RECOVERY_BLOCKED')
