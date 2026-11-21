import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_previews import ChartTradePreviews


class Adapter:
    account_id = "account-a"
    broker = "FYERS"
    def __init__(self):
        self.calls = 0
        self.changed = False
        self.failure = False
        self.rejected = False
    def refresh(self, plan):
        return replace(plan, target="32") if self.changed else plan
    def submit_bracket(self, plan, *, idempotency_key):
        self.calls += 1
        if self.failure:
            raise TimeoutError("Unknown broker response")
        if self.rejected:
            return {"status": "REJECTED"}
        return {"entry_order_id": "broker-entry-1", "account_id": plan.account_id, "symbol": plan.symbol}


class ChartTradePreviewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"chart-orders.sqlite3"
        self.now = 100
        self.service = ChartTradePreviews(self.path, clock=lambda:self.now)
        self.adapter = Adapter()
        self.plan = ChartTradePlan("account-a", "FYERS", "NSE:TEST", "BUY", 65, "25", "22", "30",
                                   "LIMIT", "25", "INTRADAY", "0.05", 65, "AT_OR_BELOW")
        self.preview = self.service.prepare("user-a", self.plan)
    def arm(self, **kwargs):
        return self.service.arm(kwargs.pop("owner","user-a"), self.preview["preview_id"],
                                kwargs.pop("confirmation",self.preview["confirmation_phrase"]),
                                mode=kwargs.pop("mode","LIVE"),adapter=self.adapter,
                                enabled=kwargs.pop("enabled",True),**kwargs)

    def test_prepare_cannot_submit_and_live_submission_is_separately_gated(self):
        self.assertEqual(self.adapter.calls, 0)
        self.assertFalse(self.preview["order_submitted"])
        for args in ({"mode":"PAPER"}, {"enabled":False}, {"confirmation":"yes"}, {"owner":"user-b"}):
            with self.subTest(args=args), self.assertRaises(PermissionError):
                self.arm(**args)
        self.assertEqual(self.adapter.calls, 0)

    def test_changed_drawings_expiry_or_account_fail_before_submission(self):
        self.adapter.changed = True
        with self.assertRaises(ValueError):self.arm()
        self.adapter.changed = False
        self.now = 220
        with self.assertRaises(ValueError):self.arm()
        self.now = 100
        self.adapter.account_id = "account-b"
        with self.assertRaises(PermissionError):self.arm()
        self.assertEqual(self.adapter.calls,0)

    def test_duplicate_confirmation_after_restart_cannot_submit_again(self):
        first = self.arm()
        self.assertEqual(first["status"], "BROKER_ACCEPTED")
        self.assertFalse(first["protection_confirmed"])
        self.service = ChartTradePreviews(self.path, clock=lambda:self.now)
        self.assertEqual(self.arm(), first)
        self.assertEqual(self.adapter.calls,1)

    def test_unknown_network_result_is_durable_and_never_retried(self):
        self.adapter.failure = True
        first = self.arm()
        self.assertEqual(first["status"],"SUBMISSION_UNCERTAIN")
        self.service = ChartTradePreviews(self.path, clock=lambda:self.now)
        self.adapter.failure = False
        self.assertEqual(self.arm(),first)
        self.assertEqual(self.adapter.calls,1)

    def test_rejection_is_not_fill_or_permission_to_retry(self):
        self.adapter.rejected = True
        result = self.arm()
        self.assertEqual(result["status"],"REJECTED")
        self.assertFalse(result["protection_confirmed"])
        self.assertFalse(result["retry_allowed"])
        self.arm()
        self.assertEqual(self.adapter.calls,1)


    def test_reconciliation_is_persisted_and_never_resubmits(self):
        self.arm()
        def reconcile(plan,**kwargs):
            return dict(account_id=plan.account_id,broker=plan.broker,symbol=plan.symbol,
                        status="ENTRY_PENDING",protection_confirmed=False,message="Native pending entry.")
        self.adapter.reconcile=reconcile
        record=self.service.reconcile("user-a",self.preview["preview_id"],self.adapter)
        self.assertEqual(record["status"],"ENTRY_PENDING")
        self.assertEqual(self.adapter.calls,1)
        self.service=ChartTradePreviews(self.path,clock=lambda:self.now)
        self.assertEqual(self.arm()["status"],"ENTRY_PENDING")
        self.assertEqual(self.adapter.calls,1)

    def test_wrong_account_reconciliation_cannot_overwrite_record(self):
        original=self.arm()
        self.adapter.reconcile=lambda plan,**kwargs:dict(account_id="wrong",symbol=plan.symbol,broker=plan.broker,status="CLOSED")
        with self.assertRaises(PermissionError):self.service.reconcile("user-a",self.preview["preview_id"],self.adapter)
        self.assertEqual(self.service.inspect("user-a",self.preview["preview_id"])["result"],original)

    def test_status_network_failure_preserves_durable_intent(self):
        original=self.arm()
        def reconcile(*args,**kwargs):raise TimeoutError("Unavailable")
        self.adapter.reconcile=reconcile
        with self.assertRaises(TimeoutError):self.service.reconcile("user-a",self.preview["preview_id"],self.adapter)
        self.assertEqual(self.service.inspect("user-a",self.preview["preview_id"])["result"],original)
        self.assertEqual(self.adapter.calls,1)


    def test_late_native_acknowledgement_cannot_overwrite_newer_closed_evidence(self):
        def reconcile(plan,**kwargs):
            return dict(account_id=plan.account_id,broker=plan.broker,symbol=plan.symbol,status="CLOSED",
                        entry_order_id="broker-entry-1",protection_confirmed=False,message="Verified exits closed.")
        self.adapter.reconcile=reconcile
        def submit(plan,**kwargs):
            self.adapter.calls+=1
            self.service.reconcile("user-a",self.preview["preview_id"],self.adapter)
            return dict(entry_order_id="broker-entry-1",account_id=plan.account_id,symbol=plan.symbol)
        self.adapter.submit_bracket=submit
        result=self.arm()
        self.assertEqual(result["status"],"CLOSED")
        self.assertEqual(self.service.inspect("user-a",self.preview["preview_id"])["status"],"CLOSED")
        self.assertEqual(self.adapter.calls,1)


if __name__ == "__main__":unittest.main()

