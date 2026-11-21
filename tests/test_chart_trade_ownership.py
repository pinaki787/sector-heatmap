import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from sector_heatmap.chart_trade_ownership import assert_no_chart_entry_conflict,assert_workspace_chart_entry_allowed
from sector_heatmap.delta_india import DeltaIndia

class ChartOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.account="a"*32
        self.path=self.folder/"accounts"/self.account/"chart-trading.sqlite3"
        self.path.parent.mkdir(parents=True)
        self.plan=json.dumps(dict(account_id=self.account,broker="DELTA_INDIA"))
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE previews(id TEXT,plan TEXT,state TEXT)")
    def record(self,state):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM previews")
            db.execute("INSERT INTO previews VALUES(?,?,?)",("preview",self.plan,state))
    def check(self,**kwargs):
        return assert_no_chart_entry_conflict(self.path,self.account,"DELTA_INDIA",**kwargs)
    def test_previews_and_confirmed_terminal_records_do_not_own_execution(self):
        for state in ("PREVIEW","CLOSED","CANCELLED","REJECTED","EXPIRED"):
            self.record(state);self.check()
    def test_pending_partial_protected_and_unknown_records_block_other_entries(self):
        for state in ("SUBMISSION_UNCERTAIN","BROKER_ACCEPTED","ENTRY_PENDING","POSITION_PROTECTED",
                      "ENTRY_PARTIALLY_FILLED_EXITS_UNVERIFIED","BROKER_STATUS_UNAVAILABLE","EXIT_CANCELLATION_PENDING"):
            self.record(state)
            with self.subTest(state=state),self.assertRaises(ValueError):self.check()
    def test_exact_persisted_chart_intent_can_submit_but_a_different_tag_cannot(self):
        self.record("SUBMISSION_UNCERTAIN")
        token="CH"+hashlib.sha256(b"preview").hexdigest()[:24]
        self.check(client_order_id=token)
        with self.assertRaises(ValueError):self.check(client_order_id="another")
    def test_corrupt_or_wrong_account_evidence_blocks_new_entries(self):
        self.record("ENTRY_PENDING")
        with self.assertRaises(ValueError):
            assert_no_chart_entry_conflict(self.path,"b"*32,"DELTA_INDIA")
        with sqlite3.connect(self.path) as db:db.execute("UPDATE previews SET plan='broken'")
        with self.assertRaises(ValueError):self.check()
    def test_private_workspace_resolves_its_own_registry_folder(self):
        self.record("ENTRY_PENDING")
        with patch.dict("os.environ",{"SECTOR_PULSE_WORKSPACE_ID":self.account,
                                     "SECTOR_PULSE_WORKSPACE_REGISTRY":str(self.folder/"registry.sqlite3")}):
            with self.assertRaises(ValueError):assert_workspace_chart_entry_allowed("DELTA_INDIA")
    def native(self):
        self.calls=[]
        def send(url,**kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(status_code=200,json=lambda:dict(success=True,result={"id":1}))
        delta=object.__new__(DeltaIndia);delta.clock=lambda:100
        delta.requester=SimpleNamespace(post=send,delete=send,get=send)
        delta._credentials=lambda:dict(DELTA_INDIA_API_KEY="test-key",DELTA_INDIA_API_SECRET="test-secret")
        return delta
    def test_native_boundary_blocks_opening_without_touching_exit_or_cancel(self):
        self.record("SUBMISSION_UNCERTAIN");delta=self.native()
        with patch.dict("os.environ",{"SECTOR_PULSE_WORKSPACE_ID":self.account,
                                     "SECTOR_PULSE_WORKSPACE_REGISTRY":str(self.folder/"registry.sqlite3")}):
            with self.assertRaises(ValueError):
                delta._private("POST","/v2/orders",body=dict(product_id=27,reduce_only=False))
            self.assertEqual(self.calls,[])
            delta._private("POST","/v2/orders",body=dict(product_id=27,reduce_only=True))
            delta._private("DELETE","/v2/orders",body=dict(id=123,product_id=27))
        self.assertEqual(len(self.calls),2)

    def test_fyers_ticket_and_batch_entries_respect_existing_chart_intent(self):
        from sector_heatmap.fyers_execution import FyersExecutionService
        self.plan=json.dumps(dict(account_id=self.account,broker="FYERS"));self.record("SUBMISSION_UNCERTAIN")
        service=object.__new__(FyersExecutionService)
        with patch.dict("os.environ",{"SECTOR_PULSE_WORKSPACE_ID":self.account,
                                     "SECTOR_PULSE_WORKSPACE_REGISTRY":str(self.folder/"registry.sqlite3")}):
            for submit in (service.submit,service.submit_batch):
                with self.assertRaisesRegex(ValueError,"chart order owns"):
                    submit("unused","unused")

    def test_live_runner_entries_block_before_intent_but_exit_branch_remains_available(self):
        from strategies.ema_crossover.runner import Runner
        from types import SimpleNamespace
        self.plan=json.dumps(dict(account_id=self.account,broker="FYERS"));self.record("ENTRY_PENDING")
        runner=object.__new__(Runner);runner.state=dict(config=dict(mode="LIVE",broker="FYERS"))
        class ExitBranchReached(Exception):pass
        def quote(symbol):raise ExitBranchReached()
        runner.adapter=SimpleNamespace(validate_order=lambda order:None,quote=quote)
        with patch.dict("os.environ",{"SECTOR_PULSE_WORKSPACE_ID":self.account,
                                     "SECTOR_PULSE_WORKSPACE_REGISTRY":str(self.folder/"registry.sqlite3")}):
            for side in (1,-1):
                with self.assertRaisesRegex(ValueError,"chart order owns"):
                    runner.submit(dict(side=side,symbol="NSE:TEST"),dict(entry_side=side),"ENTRY")
                with self.assertRaises(ExitBranchReached):
                    runner.submit(dict(side=-side,symbol="NSE:TEST"),dict(entry_side=side),"EXIT")
        self.assertNotIn("pending",runner.state)

if __name__=="__main__":unittest.main()
