"""Isolated activation/clock regressions; fake broker, no background runner."""
import tempfile
import unittest
from pathlib import Path
from .delta_runner import DeltaRunner
from .test_delta_integration import NativeFake, config

class ContinuousActivationTests(unittest.TestCase):
    def run_case(self,policy,deadline):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        broker=NativeFake();runner=DeltaRunner(broker,Path(temp.name)/'state.json',lambda:broker.now)
        self.addCleanup(runner.release)
        payload=dict(config(),carry_policy=policy,session_deadline=deadline,configuration_revision=runner.runtime_revision)
        state=runner.activate(payload,background=False)
        self.assertTrue(state['running']);self.assertEqual(broker.sent,[])
        self.assertEqual(state['activation_message_revision'],'continuous-cutoff-status-v2')
        return broker,runner,state

    def test_continuous_none_deadline_activation_and_midnight_keep_running(self):
        broker,runner,state=self.run_case('CONTINUOUS',None)
        self.assertIsNone(state['config']['session_deadline']);self.assertIn('continuous crypto',state['message'])
        # Existing exposure across midnight must not fall into the daily suffix path.
        runner.state['position']={'opened_at':broker.now-86400,'expiry_epoch':broker.now+86400}
        runner.deadline();self.assertTrue(runner.state['accepting_entries'])
        self.assertFalse(runner.state['position'].get('exit_requested',False));self.assertEqual(broker.sent,[])

    def test_continuous_still_protects_exact_held_expiry(self):
        broker,runner,_=self.run_case('CONTINUOUS',None)
        runner.state['position']={'opened_at':broker.now-10,'expiry_epoch':broker.now+30}
        runner.deadline();self.assertTrue(runner.state['position']['exit_requested'])
        self.assertEqual(runner.state['position']['exit_reason'],'CONTRACT_EXPIRY');self.assertEqual(broker.sent,[])

    def test_daily_cutoff_message_and_policy_preserved(self):
        _,_,state=self.run_case('DAILY_SQUARE_OFF','23:30')
        self.assertEqual(state['config']['session_deadline'],'23:30');self.assertIn('segment cutoff 23:30 IST',state['message'])
