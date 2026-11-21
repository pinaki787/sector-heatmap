import threading
from pathlib import Path
import struct
from sector_heatmap.chart_trade_dhan_conditions import DhanChartConditions
from contextlib import nullcontext
from unittest import TestCase
from tests import test_chart_trade_dhan as fixtures
from sector_heatmap.chart_trade_dhan import DhanChartAdapter
from sector_heatmap.chart_trade_previews import ChartTradePreviews
from sector_heatmap.chart_trade_admission import ChartOrderNotSent, entry_revision
from sector_heatmap.dhan_execution import DhanAPIError


class DhanChartSubmitTests(TestCase):
    def setUp(self):
        fixtures.DhanChartPreviewTests.setUp(self)
        self.execution.lock=threading.RLock()
        self.execution._submission_lock=nullcontext
        self.execution.execution_allowed=lambda:True
        self.posts=[];self.reply={"orderId":"native-owned","orderStatus":"PENDING"}
        original=self.client.request
        def request(method,path,payload=None):
            if method=="POST" and path=="/super/orders":
                self.posts.append(dict(payload))
                if isinstance(self.reply,Exception):raise self.reply
                return self.reply
            return original(method,path,payload)
        self.client.request=request
        self.adapter=DhanChartAdapter(self.account,self.execution,clock=lambda:1794978000,
                                      session_validator=lambda *args:None,submission_enabled=True)
        self.store=ChartTradePreviews(Path(self.execution.folder)/"chart-trading.sqlite3",clock=lambda:1794978000)

    def preview(self):
        return self.store.prepare("owner",self.adapter.prepare(self.payload))

    def arm(self,review):
        return self.store.arm("owner",review["preview_id"],"CONFIRM "+review["preview_id"],
                              mode="LIVE",adapter=self.adapter,enabled=True)

    def test_exact_native_super_once_from_durable_intent(self):
        review=self.preview()
        result=self.arm(review)
        self.assertEqual(result["status"],"BROKER_ACCEPTED")
        self.assertFalse(result["protection_confirmed"])
        body=self.posts[0]
        self.assertEqual((body["price"],body["stopLossPrice"],body["targetPrice"]),(24.5,22,30))
        self.assertEqual((body["dhanClientId"],body["securityId"],body["exchangeSegment"]),("client","123","NSE_FNO"))
        self.assertEqual(body["orderType"],"LIMIT")
        self.assertEqual(body["trailingJump"],0)
        self.assertEqual(self.arm(review),result)
        self.assertEqual(len(self.posts),1)
        self.assertEqual(entry_revision("DHAN",folder=self.execution.folder),"1")

    def test_transport_failure_stays_uncertain_and_is_not_retried(self):
        self.reply=TimeoutError("simulated lost response")
        review=self.preview()
        self.assertEqual(self.arm(review)["status"],"SUBMISSION_UNCERTAIN")
        self.assertEqual(self.arm(review)["status"],"SUBMISSION_UNCERTAIN")
        self.assertEqual(len(self.posts),1)

    def test_native_socket_error_after_invocation_is_not_no_send(self):
        self.reply=BlockingIOError("simulated native transport error")
        review=self.preview()
        result=self.arm(review)
        self.assertEqual(result["status"],"SUBMISSION_UNCERTAIN")
        self.assertNotIn("order_submitted",result)
        self.assertEqual(len(self.posts),1)

    def test_explicit_native_rejection_is_terminal_without_retry(self):
        self.reply=DhanAPIError("simulated rejection",definitive_rejection=True)
        review=self.preview()
        self.assertEqual(self.arm(review)["status"],"REJECTED")
        self.assertEqual(self.arm(review)["status"],"REJECTED")
        self.assertEqual(len(self.posts),1)

    def test_disabled_gate_rejects_before_native_invocation(self):
        review=self.preview();self.adapter._submission_enabled=False
        result=self.arm(review)
        self.assertEqual(result["status"],"REJECTED")
        self.assertFalse(result["order_submitted"])
        self.assertEqual(self.posts,[])
        self.assertEqual(entry_revision("DHAN",folder=self.execution.folder),"0")

    def test_direct_submission_without_durable_review_cannot_invoke_native(self):
        plan=self.adapter.prepare(self.payload)
        with self.assertRaises(ChartOrderNotSent):
            self.adapter.submit_bracket(plan,idempotency_key="not-a-preview")
        self.assertEqual(self.posts,[])

    def conditional(self,*,claim=True):
        self.now=100.3
        self.adapter.clock=lambda:self.now
        self.store.clock=lambda:self.now
        self.payload.update(entry_type="STOP_LIMIT",entry="25.50",limit_price="25.55")
        plan=self.adapter.prepare(self.payload)
        review=self.store.prepare("owner",plan)
        def tick(price,stamp,received,seq):
            return dict(account_id="account",broker="DHAN",symbol=plan.symbol,
                native_account_hash=plan.native_account_hash,source="BROKER_WEBSOCKET",
                stream_id="a"*32,connection_revision=1,sequence=seq,provider_at=stamp,
                received_at=received,price=str(struct.unpack("<f",struct.pack("<f",price))[0]))
        conditions=DhanChartConditions(self.store.path,clock=lambda:self.now)
        conditions.arm("owner",review["preview_id"],"CONFIRM "+review["preview_id"],
            tick=tick(25,100,100.2,1),expires_at=200,mode="LIVE",enabled=True)
        self.now=101.2
        self.client.quote.update(last_price=25.5,depth={"buy":[{"price":25.45}],"sell":[{"price":25.5}]})
        self.current_tick=tick(25.5,101,101.1,2)
        self.adapter.tick_reader=lambda symbol:self.current_tick
        conditions.observe("owner",review["preview_id"],self.current_tick)
        if claim:conditions.claim("owner",review["preview_id"],tick=self.current_tick)
        return plan,review,conditions

    def test_claimed_stop_limit_uses_original_trigger_and_cap_in_one_simulated_super(self):
        plan,review,_=self.conditional()
        refreshed=self.adapter.refresh_triggered(plan,preview_id=review["preview_id"])
        self.assertEqual(refreshed.fingerprint(),plan.fingerprint())
        result=self.adapter.submit_bracket(refreshed,idempotency_key=review["preview_id"])
        self.assertEqual(result["entry_order_id"],"native-owned")
        self.assertEqual(len(self.posts),1)
        self.assertEqual(self.posts[0]["price"],25.55)
        self.assertEqual((self.posts[0]["stopLossPrice"],self.posts[0]["targetPrice"]),(22,30))
        self.assertEqual(plan.entry,"25.50")
        self.assertEqual(plan.entry_type,"STOP_LIMIT")
        with self.assertRaises(ChartOrderNotSent):
            self.adapter.submit_bracket(refreshed,idempotency_key=review["preview_id"])
        self.assertEqual(len(self.posts),1)

    def test_reconnected_or_reversed_claim_cannot_reach_native_send(self):
        plan,review,_=self.conditional()
        self.current_tick=dict(self.current_tick,stream_id="b"*32)
        with self.assertRaisesRegex(ValueError,"stream changed"):
            self.adapter.refresh_triggered(plan,preview_id=review["preview_id"])
        self.assertEqual(self.posts,[])

    def test_final_price_reversal_after_claim_refresh_is_known_no_send(self):
        plan,review,_=self.conditional()
        refreshed=self.adapter.refresh_triggered(plan,preview_id=review["preview_id"])
        self.client.quote["last_price"]=25.45
        with self.assertRaises(ChartOrderNotSent):
            self.adapter.submit_bracket(refreshed,idempotency_key=review["preview_id"])
        self.assertEqual(self.posts,[])

    def test_intervening_entry_revision_invalidates_old_review(self):
        from sector_heatmap.chart_trade_admission import mark_entry_attempt
        review=self.preview()
        mark_entry_attempt("DHAN",folder=self.execution.folder)
        with self.assertRaisesRegex(ValueError,"changed"):
            self.arm(review)
        self.assertEqual(self.posts,[])
