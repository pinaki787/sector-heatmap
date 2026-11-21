from unittest import TestCase
from tests import test_chart_trade_dhan_submit as fixtures
from sector_heatmap.chart_trading import ChartTradingService
from sector_heatmap.chart_trade_dhan_controller import DhanConditionalController


class Worker:
    def __init__(self,*args,**kwargs):self.starts=0;self.stops=0
    def start(self):self.starts+=1
    def close(self):self.stops+=1


class DhanConditionalControllerTests(TestCase):
    def setUp(self):
        fixtures.DhanChartSubmitTests.setUp(self)
        self.now=100.3
        self.adapter.clock=lambda:self.now
        self.account["user_id"]="owner"
        self.enabled=True
        self.payload.update(entry_type="STOP_LIMIT",entry="25.50",limit_price="25.55")
        import hashlib
        self.current_tick=dict(account_id="account",broker="DHAN",symbol=self.payload["symbol"],
            native_account_hash=hashlib.sha256(b"client").hexdigest(),source="BROKER_WEBSOCKET",
            stream_id="a"*32,connection_revision=1,sequence=1,provider_at=100,received_at=100.2,price="25.0")
        self.adapter.tick_reader=lambda symbol:self.current_tick
        self.service=ChartTradingService(self.account,self.store.path,lambda account:self.adapter,
            clock=lambda:self.now,conditional_factory=lambda service:DhanConditionalController(service,
                tick_reader=lambda symbol:self.current_tick,expiry_resolver=lambda *args:200,
                enabled=lambda:self.enabled,worker_factory=Worker))
        self.addCleanup(self.service.close)
        self.user=dict(id="owner",features=["chart-workspace","broker"])

    def preview(self):
        return self.service.prepare(self.user,self.payload)

    def arm(self,review,**changes):
        payload=dict(account_id="account",broker="DHAN",preview_id=review["preview_id"],
                     confirmation="CONFIRM "+review["preview_id"],mode="LIVE",expires_at=999999)
        payload.update(changes)
        return self.service.arm(self.user,payload)

    def test_explicit_arm_waits_and_starts_worker_only_after_confirmation(self):
        self.assertEqual(self.service.conditional.worker.starts,0)
        review=self.preview()
        self.assertEqual(self.service.conditional.worker.starts,0)
        result=self.arm(review)
        self.assertEqual(result["status"],"WAITING_FOR_TRIGGER")
        self.assertFalse(result["protection_confirmed"])
        self.assertEqual(self.posts,[])
        self.assertEqual(self.service.conditional.worker.starts,1)
        state=self.service.conditional.conditions.inspect("owner",review["preview_id"])["state"]
        self.assertEqual(state["expires_at"],200)
        self.assertEqual(self.arm(review),result)
        self.assertEqual(self.service.conditional.worker.starts,1)

    def test_status_is_local_and_cancel_cannot_cancel_a_native_claim(self):
        review=self.preview();self.arm(review)
        payload=dict(account_id="account",broker="DHAN",preview_id=review["preview_id"])
        self.client.calls.clear()
        self.assertEqual(self.service.status(self.user,payload)["status"],"WAITING_FOR_TRIGGER")
        self.assertEqual(self.client.calls,[])
        self.now=101.2
        self.current_tick=dict(self.current_tick,price="25.5",provider_at=101,received_at=101.1,sequence=2)
        conditions=self.service.conditional.conditions
        conditions.observe("owner",review["preview_id"],self.current_tick)
        conditions.claim("owner",review["preview_id"],tick=self.current_tick)
        with self.assertRaises(ValueError):self.service.cancel_condition(self.user,payload)
        self.assertEqual(self.posts,[])

    def test_unclaimed_cancel_is_owner_scoped_and_local_only(self):
        review=self.preview();self.arm(review)
        result=self.service.cancel_condition(self.user,dict(account_id="account",broker="DHAN",preview_id=review["preview_id"]))
        self.assertEqual(result["status"],"CANCELLED")
        self.assertFalse(result["order_submitted"])
        self.assertEqual(self.posts,[])

    def test_owner_permissions_gate_and_confirmation_before_arm(self):
        review=self.preview()
        for changes in ({"mode":"PAPER"},{"confirmation":"wrong"}):
            with self.assertRaises(PermissionError):self.arm(review,**changes)
        for user in (dict(id="foreign",admin=True),dict(id="owner",features=["chart-workspace"]),
                     dict(id="owner",features=["broker"])):
            with self.assertRaises(PermissionError):
                self.service.arm(user,dict(account_id="account",broker="DHAN",preview_id=review["preview_id"],
                    confirmation="CONFIRM "+review["preview_id"],mode="LIVE"))
        self.enabled=False
        with self.assertRaises(PermissionError):self.arm(review)
        self.assertEqual(self.service.conditional.worker.starts,0)
        self.assertEqual(self.posts,[])

    def test_worker_start_failure_does_not_leave_a_silent_waiting_condition(self):
        review=self.preview()
        def failed():raise RuntimeError("simulated thread start failure")
        self.service.conditional.worker.start=failed
        with self.assertRaisesRegex(ValueError,"could not start"):self.arm(review)
        self.assertEqual(self.service.previews.inspect("owner",review["preview_id"])["status"],"REVIEW_REQUIRED")
        self.assertEqual(self.posts,[])

    def test_changed_tick_at_confirmation_does_not_arm_an_old_trigger(self):
        review=self.preview()
        self.current_tick=dict(self.current_tick,price="25.5")
        with self.assertRaisesRegex(ValueError,"Review a new"):
            self.arm(review)
        self.assertEqual(self.service.conditional.worker.starts,0)
        self.assertEqual(self.posts,[])
