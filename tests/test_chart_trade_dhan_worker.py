import json
from unittest import TestCase
from tests import test_chart_trade_dhan_submit as fixtures
from sector_heatmap.chart_trade_dhan_worker import DhanConditionalWorker


class DhanConditionalWorkerTests(TestCase):
    conditional=fixtures.DhanChartSubmitTests.conditional

    def setUp(self):
        fixtures.DhanChartSubmitTests.setUp(self)
        self.plan,self.review,self.conditions=self.conditional(claim=False)
        self.enabled=True
        self.worker=self.new_worker()
        self.addCleanup(self.worker.close)

    def new_worker(self):
        return DhanConditionalWorker(self.account,self.conditions,adapter_factory=lambda:self.adapter,
            tick_reader=lambda symbol:self.current_tick,enabled=lambda:self.enabled)

    def result(self):
        return self.store.inspect("owner",self.review["preview_id"])

    def test_native_once_and_restart_never_reclaims(self):
        self.assertEqual(self.worker.run_once(),1)
        self.assertEqual(self.result()["status"],"BROKER_ACCEPTED")
        self.assertEqual(len(self.posts),1)
        self.assertFalse(self.result()["result"]["protection_confirmed"])
        self.assertEqual(self.worker.run_once(),0)
        restarted=self.new_worker()
        self.assertEqual(restarted.run_once(),0)
        self.assertEqual(len(self.posts),1)

    def test_lost_native_response_is_uncertain_without_worker_retry(self):
        self.reply=TimeoutError("simulated")
        self.worker.run_once()
        self.assertEqual(self.result()["status"],"SUBMISSION_UNCERTAIN")
        self.assertNotIn("order_submitted",self.result()["result"])
        self.worker.run_once();self.new_worker().run_once()
        self.assertEqual(len(self.posts),1)

    def test_disabled_gate_persists_review_and_does_not_auto_rearm(self):
        self.enabled=False
        self.worker.run_once()
        self.assertEqual(self.result()["status"],"REVIEW_REQUIRED")
        self.enabled=True;self.worker.run_once()
        self.assertEqual(self.posts,[])

    def test_reconnection_prevents_claim_and_native_order(self):
        self.current_tick=dict(self.current_tick,stream_id="b"*32)
        self.worker.run_once()
        self.assertEqual(self.result()["status"],"REVIEW_REQUIRED")
        self.assertEqual(self.posts,[])

    def test_tick_reader_failure_is_persisted_instead_of_silent_waiting(self):
        def failed(symbol):raise PermissionError("simulated expired session")
        self.worker.tick_reader=failed
        self.worker.run_once()
        self.assertEqual(self.result()["status"],"REVIEW_REQUIRED")
        self.assertEqual(self.posts,[])

    def test_tick_reader_failure_after_admission_cannot_claim(self):
        calls=[0]
        def reader(symbol):
            calls[0]+=1
            if calls[0]>1:raise TimeoutError("simulated feed failure")
            return self.current_tick
        self.worker.tick_reader=reader
        self.worker.run_once()
        self.assertEqual(self.result()["status"],"REVIEW_REQUIRED")
        self.assertFalse(self.conditions.inspect("owner",self.review["preview_id"])["claimed"])
        self.assertEqual(self.posts,[])

    def test_failed_read_only_refresh_is_known_no_send(self):
        def failed(*args,**kwargs):raise ValueError("Simulated changed contract")
        self.adapter.refresh_triggered=failed
        self.worker.run_once()
        self.assertEqual(self.result()["status"],"REJECTED")
        self.assertFalse(self.result()["result"]["order_submitted"])
        self.assertEqual(self.posts,[])

    def test_stop_during_refresh_prevents_placement(self):
        original=self.adapter.refresh_triggered
        def stop(*args,**kwargs):
            result=original(*args,**kwargs);self.worker.close();return result
        self.adapter.refresh_triggered=stop
        self.worker.run_once()
        self.assertEqual(self.posts,[])
        self.assertFalse(self.result()["result"]["order_submitted"])

    def test_late_ack_does_not_overwrite_newer_fill_and_protection_evidence(self):
        original=self.adapter.submit_bracket
        def observed(*args,**kwargs):
            receipt=original(*args,**kwargs)
            with self.store.connection() as db:
                result=dict(account_id="account",broker="DHAN",symbol=self.plan.symbol,status="POSITION_PROTECTED",
                    entry_order_id=receipt["entry_order_id"],filled_quantity=65,protection_confirmed=True)
                db.execute("UPDATE previews SET state=?,result=? WHERE id=?",
                    ("POSITION_PROTECTED",json.dumps(result),self.review["preview_id"]))
            return receipt
        self.adapter.submit_bracket=observed
        self.worker.run_once()
        self.assertEqual(self.result()["status"],"POSITION_PROTECTED")
        self.assertTrue(self.result()["result"]["protection_confirmed"])
        self.assertEqual(len(self.posts),1)
