import unittest
from copy import deepcopy
from . import test_runner as fixtures
from .runner import Runner

class GuardedPaperRecoveryTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    def start(self):
        self.r.state['run_id']='RENKO-RUN-TEST'
        return fixtures.RenkoLifecycleTests.start(self)
    append=fixtures.RenkoLifecycleTests.append
    def test_identical_flat_paper_resume_preserves_run_quota_journal_and_pnl(self):
        self.start();self.r.step();self.append(80);self.r.step()
        self.r.state['running']=False;self.r.save();self.r.release()
        old=deepcopy(self.r.state);self.b.now+=2
        other=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(other.release)
        payload=dict(old['config'],resume_run_id=old['run_id'],configuration_revision=other.runtime_revision)
        s=other.activate(payload,False)
        for k in ['run_id','trades_used','realized_pnl','started_at','order_history','seen']:
            self.assertEqual(s[k],old[k])
        self.assertGreater(s['eligible_since'],old['started_at'])
        self.assertFalse(other.fresh_cross(old['last_signal']))
    def test_recovery_rejects_changed_settings_and_live(self):
        self.start();self.r.state['running']=False;self.r.save();self.r.release()
        other=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(other.release)
        for change in [dict(lots=2),dict(mode='LIVE'),dict(resume_run_id='wrong')]:
            payload={**self.r.state['config'],'resume_run_id':self.r.state['run_id'],'configuration_revision':other.runtime_revision,**change}
            with self.assertRaises(ValueError):other.activate(payload,False)
            self.assertFalse(other.state['running'])

    def test_v8_saved_paper_resume_adds_off_retest_defaults_without_replay(self):
        self.start();self.r.signal()
        for k in ('retest_enabled','retest_engulfing','retest_harami','retest_star'):
            self.r.state['config'].pop(k,None)
            self.r.state['renko_engine']['identity']['config'].pop(k,None)
        self.r.state['running']=False;self.r.save();self.r.release()
        old=deepcopy(self.r.state);self.b.now+=2
        other=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(other.release)
        s=other.activate(dict(old['config'],resume_run_id=old['run_id'],configuration_revision=other.runtime_revision),False)
        self.assertFalse(s['config']['retest_enabled'])
        other.step();self.assertIsNone(other.state['position'])
        self.assertEqual(other.state['trades_used'],old['trades_used'])
        self.assertEqual(other.state['seen'],old['seen'])
