from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from sector_heatmap.chart_trade_previews import ChartTradePreviews
from sector_heatmap.chart_trade_dhan_conditions import DhanChartConditions
from sector_heatmap.chart_trade_ownership import assert_no_chart_entry_conflict
from tests import test_chart_trade_dhan_trigger as fixtures


class DhanConditionsTests(unittest.TestCase):
    def setUp(self):
        fixtures.DhanTriggerTests.setUp(self)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=100.3
        self.path=Path(self.tmp.name)/"chart-trading.sqlite3"
        self.previews=ChartTradePreviews(self.path,clock=lambda:self.now)
        self.conditions=DhanChartConditions(self.path,clock=lambda:self.now)
        self.review=self.previews.prepare("owner",self.plan)
        self.key=self.review["preview_id"]

    event=fixtures.DhanTriggerTests.event

    def arm(self,**values):
        args=dict(tick=self.tick,expires_at=200,mode="LIVE",enabled=True);args.update(values)
        return self.conditions.arm("owner",self.key,"CONFIRM "+self.key,**args)

    def triggered(self):
        self.arm();self.now=101.2
        result=self.conditions.observe("owner",self.key,self.event())
        self.assertEqual(result["state"]["status"],"TRIGGERED")
        return result

    def test_waiting_state_is_durable_owns_account_and_does_not_place(self):
        result=self.arm()
        self.assertEqual(result["state"]["status"],"WAITING_FOR_TRIGGER")
        restored=DhanChartConditions(self.path,clock=lambda:self.now)
        self.assertEqual(restored.inspect("owner",self.key),result)
        with self.assertRaises(ValueError):
            assert_no_chart_entry_conflict(self.path,"account","DHAN")
        self.assertIsNone(self.conditions.claim("owner",self.key,tick=self.tick))

    def test_two_competing_workers_get_one_durable_claim(self):
        self.triggered()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.conditions.claim("owner",self.key,tick=self.event()),range(2)))
        self.assertEqual(sum(value is not None for value in results),1)
        record=self.previews.inspect("owner",self.key)
        self.assertEqual(record["status"],"SUBMISSION_UNCERTAIN")
        self.assertFalse(record["result"]["protection_confirmed"])
        restored=DhanChartConditions(self.path,clock=lambda:self.now)
        self.assertIsNone(restored.claim("owner",self.key,tick=self.event()))
        with self.assertRaises(ValueError):restored.cancel_unclaimed("owner",self.key)

    def test_unclaimed_conditions_do_not_query_native_order_reconciliation(self):
        self.arm()
        self.assertEqual(self.previews.pending("account","DHAN"),[])
        class Native:
            def reconcile(self,*args,**kwargs):raise AssertionError("Unclaimed entry has no native order to query")
        record=self.previews.reconcile("owner",self.key,Native())
        self.assertEqual(record["status"],"WAITING_FOR_TRIGGER")
        record=self.previews.record_read_failure("owner",self.key)
        self.assertEqual(record["status"],"WAITING_FOR_TRIGGER")
        self.now=101.2
        self.conditions.observe("owner",self.key,self.event())
        self.assertEqual(self.previews.pending("account","DHAN"),[])
        self.conditions.claim("owner",self.key,tick=self.event())
        self.assertEqual(self.previews.pending("account","DHAN"),[("owner",self.key)])

    def test_repeated_arm_does_not_reset_or_reenable_trigger(self):
        original=self.arm()
        self.now=101
        repeated=self.arm(tick=self.event(),expires_at=300)
        self.assertEqual(repeated,original)

    def test_wrong_owner_and_missing_explicit_live_confirmation_are_rejected(self):
        for values in ({"enabled":False},{"mode":"PAPER"}):
            with self.assertRaises(PermissionError):self.arm(**values)
        with self.assertRaises(PermissionError):
            self.conditions.arm("foreign",self.key,"CONFIRM "+self.key,tick=self.tick,
                                expires_at=200,mode="LIVE",enabled=True)
        self.arm()
        with self.assertRaises(PermissionError):self.conditions.inspect("foreign",self.key)

    def test_local_cancel_only_before_claim_and_expiry_release_ownership(self):
        self.arm()
        result=self.conditions.cancel_unclaimed("owner",self.key)
        self.assertEqual(result["state"]["status"],"CANCELLED")
        self.assertIsNone(self.conditions.claim("owner",self.key,tick=self.tick))
        assert_no_chart_entry_conflict(self.path,"account","DHAN")
        self.assertFalse(self.previews.inspect("owner",self.key)["result"]["order_submitted"])

    def test_reconnect_or_stale_trigger_cannot_be_claimed(self):
        self.triggered()
        with self.assertRaises(ValueError):
            self.conditions.claim("owner",self.key,tick=self.event(stream_id="b"*32))
        self.assertEqual(self.conditions.inspect("owner",self.key)["state"]["status"],"REVIEW_REQUIRED")
        self.assertIsNone(self.conditions.claim("owner",self.key,tick=self.event()))

    def test_stale_claim_persists_review_required(self):
        self.triggered();self.now=104
        with self.assertRaises(ValueError):
            self.conditions.claim("owner",self.key,tick=self.event(provider_at=104,received_at=104,sequence=5))
        self.assertFalse(self.conditions.inspect("owner",self.key)["claimed"])

    def test_expired_condition_is_not_a_native_submission(self):
        self.arm();self.now=200
        result=self.conditions.observe("owner",self.key,None)
        self.assertEqual(result["state"]["status"],"EXPIRED")
        self.assertIsNone(self.conditions.claim("owner",self.key,tick=None))
        assert_no_chart_entry_conflict(self.path,"account","DHAN")
