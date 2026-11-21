import tempfile
import unittest
from pathlib import Path
from sector_heatmap.chart_trading import ChartTradingService
from sector_heatmap.chart_trade_plan import ChartTradePlan

class Adapter:
    account_id="account-a"
    broker="FYERS"
    last_preflight={"available_funds":100000,"required_margin":1000}
    calls=0
    def prepare(self,payload):
        self.calls+=1
        return ChartTradePlan("account-a","FYERS","NSE:TEST","BUY",65,"25","22","30",
                              "LIMIT","25","INTRADAY","0.05",65,"AT_OR_BELOW")
    def live_enabled(self):return True
    def refresh(self,plan):return plan
    def submit_bracket(self,plan,*,idempotency_key):
        raise AssertionError("This controller test must never submit an order.")

class ChartTradingControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Adapter()
        self.account={"id":"account-a","broker":"FYERS","user_id":"user-a","live_enabled":True}
        self.service=ChartTradingService(self.account,Path(self.temp.name)/"orders.sqlite3",
                                        lambda account:self.adapter,clock=lambda:100)
        self.user={"id":"user-a","features":["broker","chart-workspace"]}
        self.payload={"account_id":"account-a","broker":"FYERS","symbol":"NSE:TEST"}

    def test_prepare_and_inspect_preserve_selected_account_and_owner(self):
        preview=self.service.prepare(self.user,self.payload)
        self.assertEqual(preview["plan"]["account_id"],"account-a")
        self.assertEqual(preview["status"],"PREVIEW_ONLY")
        record=self.service.status(self.user,dict(self.payload,preview_id=preview["preview_id"]))
        self.assertEqual(record["status"],"PREVIEW")

    def test_analysis_permission_does_not_grant_execution_permission(self):
        for features in (["chart-workspace"],["broker"],[]):
            with self.assertRaises(PermissionError):
                self.service.prepare(dict(self.user,features=features),self.payload)
        self.assertEqual(self.adapter.calls,0)

    def test_changed_account_or_broker_cannot_redirect_a_chart_order(self):
        for payload in (dict(self.payload,account_id="account-b"),dict(self.payload,broker="DHAN")):
            with self.assertRaises(PermissionError):self.service.prepare(self.user,payload)
        self.assertEqual(self.adapter.calls,0)

    def test_another_user_cannot_inspect_or_arm_a_known_preview(self):
        preview=self.service.prepare(self.user,self.payload)
        other={"id":"user-b","features":["broker","chart-workspace"]}
        with self.assertRaises(PermissionError):
            self.service.status(other,dict(self.payload,preview_id=preview["preview_id"]))
        with self.assertRaises(PermissionError):
            self.service.arm(other,dict(self.payload,preview_id=preview["preview_id"],
                                       confirmation=preview["confirmation_phrase"],mode="LIVE"))

    def test_permission_revoked_after_preview_blocks_arming(self):
        preview=self.service.prepare(self.user,self.payload)
        with self.assertRaises(PermissionError):
            self.service.arm(dict(self.user,features=["chart-workspace"]),
                             dict(self.payload,preview_id=preview["preview_id"],
                                  confirmation=preview["confirmation_phrase"],mode="LIVE"))


class ChartTradingRouteBindingTests(unittest.TestCase):
    def test_generic_route_requires_exact_private_account_and_supported_broker(self):
        from sector_heatmap.workspace_guard import WorkspaceGuard
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            guard=WorkspaceGuard(SimpleNamespace(folder=lambda account:Path(folder)),"a",9000,8000)
            account=dict(id="a",broker="DELTA_INDIA")
            path="/api/chart-workspace/trading/prepare"
            guard.validate_action(account,path,dict(account_id="a",broker="DELTA_INDIA"))
            for payload in (dict(account_id="b",broker="DELTA_INDIA"),dict(account_id="a",broker="FYERS"),{}):
                with self.assertRaises(PermissionError):guard.validate_action(account,path,payload)
            for broker in ("DHAN","MOTILAL_OSWAL"):
                with self.assertRaises(PermissionError):
                    guard.validate_action(dict(account,broker=broker),path,dict(account_id="a",broker=broker))
            with self.assertRaises(PermissionError):
                guard.validate_action(account,"/api/chart-workspace/trading/cancel-all",dict(account_id="a",broker="DELTA_INDIA"))



if __name__=="__main__":unittest.main()

