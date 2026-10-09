import unittest
from copy import deepcopy
from . import test_runner as fixtures
from .runner import Runner

class PositionRecoveryTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    def stopped_position(self):
        fixtures.RenkoLifecycleTests.start(self);self.r.step()
        self.r.state['run_id']='RECOVERY-TEST';self.r.state['running']=False;self.r.state['accepting_entries']=False;self.r.save();self.r.release()
        self.old=deepcopy(self.r.state)
        self.r=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(self.r.release)
        return dict(run_id=self.r.state.get('run_id'),mode='PAPER')
    def test_resume_keeps_position_and_journal_without_entry_authority(self):
        payload=self.stopped_position();s=self.r.resume_position(payload,False)
        self.assertTrue(s['running']);self.assertFalse(s['accepting_entries']);self.assertTrue(s['management_only'])
        for key in ('position','order_history','trades_used','realized_pnl'):
            self.assertEqual(s[key],self.old[key])
        self.assertFalse(self.b.sent)
        self.r.step();self.assertEqual(len(self.r.state['order_history']),len(self.old['order_history']))
    def test_wrong_context_and_pending_order_cannot_resume(self):
        payload=self.stopped_position()
        for wrong in ({**payload,'mode':'LIVE'},{**payload,'run_id':'wrong'}):
            with self.assertRaises(ValueError):self.r.resume_position(wrong,False)
        self.r.state['pending']={'id':'unresolved'}
        with self.assertRaises(ValueError):self.r.resume_position(payload,False)
        self.assertFalse(self.r.state['running']);self.assertFalse(self.b.sent)
    def test_restart_labels_recovery_and_read_only_valuation_does_not_arm(self):
        self.stopped_position();s=self.r.snapshot()
        self.assertEqual(s['status'],'RECOVERY_REQUIRED');self.assertIn('Monitoring stopped',s['message'])
        self.assertTrue(s['pnl']['available']);self.assertFalse(s['running']);self.assertFalse(self.b.sent)

    def test_resumed_monitor_exits_only_and_stops_flat(self):
        payload=self.stopped_position();self.r.resume_position(payload,False)
        fixtures.RenkoLifecycleTests.append(self,80);self.r.step()
        self.assertIsNone(self.r.state['position'])
        count=len(self.r.state['order_history']);self.r.step()
        self.assertFalse(self.r.state['running']);self.assertEqual(len(self.r.state['order_history']),count)
        self.assertFalse(self.b.sent)
