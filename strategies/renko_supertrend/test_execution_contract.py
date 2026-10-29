"""Execution-contract checks with a fake broker; never contact a real account."""
import unittest
from . import test_runner as fixtures

class QualifiedLiveContractTests(unittest.TestCase):
    def fixture(self):
        f=fixtures.RenkoLifecycleTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.c["mode"]="LIVE"
        f.start()
        return f

    def test_qualified_live_signal_submits_once_but_acceptance_is_not_a_fill(self):
        f=self.fixture()
        f.r.step()
        self.assertEqual(len(f.b.sent),1)
        self.assertEqual(f.r.state["status"],"ORDER_PENDING")
        self.assertEqual(f.r.state["pending"]["id"],"O1")
        self.assertIsNone(f.r.state["position"])
        self.assertEqual(f.r.state["order_history"][-1]["status"],"ACCEPTED")

    def test_disabled_live_gate_sends_nothing_even_with_qualified_signal(self):
        f=self.fixture()
        f.b.live_enabled=lambda:False
        f.r.step()
        self.assertEqual(f.b.sent,[])
        self.assertIsNone(f.r.state["position"])
        self.assertIsNone(f.r.state["pending"])
        self.assertEqual(f.r.state["status"],"BLOCKED")

    def test_opposing_brick_exit_is_separate_from_supertrend_reversal(self):
        from .exit_indicators import reason
        c={"strategy_basis":"RENKO","supertrend_exit_enabled":True,"renko_brick_exit_enabled":True}
        sig={"has_completed_brick":True,"brick_exit_events":[{"brick_direction":"BULLISH","raw_supertrend_cross_direction":None}]}
        self.assertEqual(reason(c,sig,"BEARISH"),"OPPOSITE_RENKO_BRICK_CLOSE")
        self.assertIsNone(reason({**c,"renko_brick_exit_enabled":False},sig,"BEARISH"))
        sig["brick_exit_events"][0]["raw_supertrend_cross_direction"]="BULLISH"
        self.assertEqual(reason({**c,"renko_brick_exit_enabled":False},sig,"BEARISH"),"RENKO_ST_EXIT")
