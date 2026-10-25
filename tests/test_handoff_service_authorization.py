import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.handoff_bridge import OwnedBridge
from sector_heatmap.handoff_runtime import Runtime
from sector_heatmap.handoff_authorization import save
from sector_heatmap.handoff_schedule import Schedule

class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=WorkspaceStore(self.root/"registry.sqlite3",clock=lambda:100)
        with self.store.db() as db:
            db.execute("INSERT INTO users VALUES(?,?,?,?,?)",("owner","owner","x","x",1))
        self.user=dict(id="owner",admin=1,features=["handoff"])
        self.account=self.store.create_account(self.user,"FYERS","Owned","test")
        self.folder=self.store.folder(self.account)
        Schedule(self.folder/"handoff-schedule.sqlite3",self.account["id"],"FYERS",collect=Mock(),exposure=Mock())
        save(self.store,self.account,self.user,True)
        self.bridge=OwnedBridge(self.root,self.store,self.user,self.account,None)
        self.bridge.background=True
    def tearDown(self):self.tmp.cleanup()
    def test_background_does_not_consult_expired_or_logged_out_browser_session(self):
        with patch.object(self.store,"session",side_effect=PermissionError("expired")) as session:
            self.assertEqual(self.bridge.identity()[0]["id"],"owner")
            session.assert_not_called()
    def test_interactive_bridge_still_requires_dashboard_session(self):
        self.bridge.background=False
        with self.assertRaises(PermissionError):self.bridge.identity()
    def test_explicit_revocation_blocks_background(self):
        save(self.store,self.account,self.user,False)
        with self.assertRaises(PermissionError):self.bridge.identity()
    def test_feature_revocation_blocks_background(self):
        with self.store.db() as db:db.execute("UPDATE users SET admin=0 WHERE id='owner'")
        with self.assertRaises(PermissionError):self.bridge.identity()
    def test_owner_change_blocks_background(self):
        with self.store.db() as db:db.execute("UPDATE accounts SET user_id='different' WHERE id=?",(self.account["id"],))
        with self.assertRaises(PermissionError):self.bridge.identity()
    def test_broker_failure_propagates_without_http_or_order_submission(self):
        self.bridge.tickets=Mock()
        self.bridge.tickets.call.side_effect=ValueError("Broker token expired")
        with self.assertRaisesRegex(ValueError,"expired"):
            self.bridge.analysis("cash_equity",dict(ai_provider="RULES_ONLY",capital=100000))
        self.assertEqual(self.bridge.tickets.call.call_args.args[0],"analysis")
    def test_restart_restores_only_enabled_explicit_grant_without_browser_token(self):
        schedule=Schedule(self.folder/"handoff-schedule.sqlite3",self.account["id"],"FYERS",collect=Mock(),exposure=Mock())
        schedule.configure({"enabled":True,"mode":"MANUAL"})
        runtime=Runtime(self.store,self.root)
        with patch.object(runtime,"start") as start,patch.object(self.store,"session",side_effect=PermissionError()):
            runtime.restore()
            self.assertEqual(start.call_count,1)
            b=runtime.entries[self.account["id"]]["bridge"]
            self.assertTrue(b.background);self.assertIsNone(b.token)
        runtime.close()
    def test_disabled_schedule_is_never_rearmed_on_restart(self):
        runtime=Runtime(self.store,self.root)
        with patch.object(runtime,"start") as start:runtime.restore();start.assert_not_called()
        runtime.close()

class BrokerAttributionTests(unittest.TestCase):
    def test_quote_failure_fails_closed(self):
        from sector_heatmap.handoff_fyers_analysis import Provider
        provider=object.__new__(Provider);provider.client=Mock()
        provider.client.quotes.return_value=dict(s="error",code=-16)
        with self.assertRaisesRegex(ValueError,"authentication"):provider.live_sectors()
    def test_attribution_uses_existing_broker_and_official_constituents(self):
        from sector_heatmap.handoff_fyers_analysis import Provider
        from sector_heatmap.sectors import SECTOR_DEFINITIONS
        provider=object.__new__(Provider);provider.client=Mock()
        provider.client.quotes.side_effect=lambda p:dict(s="ok",d=[
            dict(n=s,s="ok",v=dict(lp=100,chp=2)) for s in p["symbols"].split(",")])
        rows=provider.live_sectors()
        self.assertEqual(len(rows),len(SECTOR_DEFINITIONS))
        first=next(r for r in rows if r["drivers"])["drivers"][0]
        self.assertEqual(first["change"],2)
        self.assertAlmostEqual(first["contribution"],first["weight"]*.02)
        self.assertTrue(all(len(c.args[0]["symbols"].split(","))<=50 for c in provider.client.quotes.call_args_list))

if __name__=="__main__":unittest.main()
