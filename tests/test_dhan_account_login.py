from pathlib import Path
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
import tempfile
from sector_heatmap.dhan_account_login import login

class DhanAccountLoginTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);folder=Path(tmp.name)
        account={"id":"a","broker":"DHAN","account_ref":"123","live_enabled":False}
        (folder/"credentials.json").write_text(json.dumps({"DHAN_API_KEY":"key","DHAN_API_SECRET":"secret"}))
        store=SimpleNamespace(account=Mock(return_value=account),folder=Mock(return_value=folder),configure=Mock())
        runtime=SimpleNamespace(lock=threading.RLock(),running=Mock(return_value=False))
        self.setup=store,runtime,{"csrf":"owner-session"},folder

    def test_consent_and_completion(self):
        store,runtime,user,folder=self.setup
        with patch("sector_heatmap.dhan_account_login.request_json",side_effect=[{"status":"success","consentAppId":"consent"},{"dhanClientId":"123","accessToken":"token","expiryTime":"tomorrow"}]):
            assert "consentAppId=consent" in login(store,runtime,user,"a")["url"]
            assert login(store,runtime,user,"a","callback")["connected"]
        store.configure.assert_called_once_with(user,"a",{"DHAN_ACCESS_TOKEN":"token"},False)
        assert not (folder/"dhan-consent.json").exists()

    def test_wrong_account_rejected(self):
        store,runtime,user,_=self.setup
        with patch("sector_heatmap.dhan_account_login.request_json",side_effect=[{"status":"success","consentAppId":"consent"},{"dhanClientId":"456","accessToken":"token"}]):
            login(store,runtime,user,"a")
            with self.assertRaisesRegex(ValueError,"different account"):login(store,runtime,user,"a","callback")
        store.configure.assert_not_called()

    def test_other_session_rejected(self):
        store,runtime,user,_=self.setup
        with patch("sector_heatmap.dhan_account_login.request_json",return_value={"status":"success","consentAppId":"consent"}):
            login(store,runtime,user,"a")
            with self.assertRaisesRegex(ValueError,"another session"):login(store,runtime,{"csrf":"other"},"a","callback")
        store.configure.assert_not_called()

    def test_active_worker_allows_same_account_renewal(self):
        store,runtime,user,_=self.setup
        runtime.running.return_value=True
        with patch("sector_heatmap.dhan_account_login.request_json",side_effect=[{"status":"success","consentAppId":"consent"},{"dhanClientId":"123","accessToken":"new-token"}]):
            login(store,runtime,user,"a")
            self.assertTrue(login(store,runtime,user,"a","callback")["connected"])
        store.configure.assert_called_once_with(user,"a",{"DHAN_ACCESS_TOKEN":"new-token"},False)

    def test_owner_check_precedes_broker_call(self):
        store,runtime,user,_=self.setup
        store.account.side_effect=PermissionError("not yours")
        with patch("sector_heatmap.dhan_account_login.request_json") as req:
            with self.assertRaises(PermissionError):login(store,runtime,user,"other")
            req.assert_not_called()

    def test_expired_consent_rejected(self):
        store,runtime,user,folder=self.setup
        (folder/"dhan-consent.json").write_text(json.dumps({"binding":__import__("hashlib").sha256(user["csrf"].encode()).hexdigest(),"created":0}))
        with self.assertRaisesRegex(ValueError,"expired"):login(store,runtime,user,"a","callback")
        store.configure.assert_not_called()

    def test_api_key_pair_can_be_saved_without_token(self):
        from sector_heatmap.workspaces import WorkspaceStore
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        store=WorkspaceStore(Path(tmp.name)/"registry.sqlite3")
        user=store.create_user("admin","administrator-password",bootstrap=True)
        account=store.create_account(user,"DHAN","My Dhan","123")
        store.configure(user,account["id"],{"DHAN_CLIENT_ID":"123","DHAN_API_KEY":"key","DHAN_API_SECRET":"secret"})
        saved=json.loads((store.folder(account)/"credentials.json").read_text())
        self.assertEqual(saved["DHAN_API_KEY"],"key")
        self.assertNotIn("DHAN_ACCESS_TOKEN",saved)
