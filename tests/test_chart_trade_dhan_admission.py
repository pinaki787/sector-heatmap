import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from sector_heatmap.chart_trade_admission import (
    entry_lock,entry_revision,mark_entry_attempt,assert_dhan_chart_entry_allowed,
    mark_dhan_entry_attempt,serialized_dhan_entry,serialized_dhan_strategy_entry,
    serialized_runner_entry)
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_previews import ChartTradePreviews


class DhanAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/"account";self.folder.mkdir()
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();self.addCleanup(self.env.stop)
        self.service=SimpleNamespace(account={"id":"account","broker":"DHAN"},folder=self.folder,
                                     lock=threading.RLock(),_submission_lock=lambda:None)
        self.store=ChartTradePreviews(self.folder/"chart-trading.sqlite3",clock=lambda:100)
        self.plan=ChartTradePlan("account","DHAN","NSE_FNO:123","BUY",65,"25","22","30",
                                "LIMIT","25","MARGIN",".05",65,"AT_OR_BELOW")

    def own(self):
        record=self.store.prepare("owner",self.plan)
        import sqlite3
        with sqlite3.connect(self.store.path) as db:
            db.execute("UPDATE previews SET state='SUBMISSION_UNCERTAIN' WHERE id=?",(record["preview_id"],))
        return record

    def test_explicit_account_folders_coordinate_without_worker_environment(self):
        other=Path(self.tmp.name)/"other";other.mkdir()
        with entry_lock("DHAN",folder=self.folder):
            self.assertEqual(mark_dhan_entry_attempt(self.service),"1")
            self.assertEqual(entry_revision("DHAN",folder=self.folder),"1")
            self.assertEqual(entry_revision("DHAN",folder=other),"0")
        self.own()
        with self.assertRaises(ValueError):assert_dhan_chart_entry_allowed(self.service)
        assert_dhan_chart_entry_allowed(SimpleNamespace(account={"id":"other","broker":"DHAN"},folder=other))

    def test_manual_and_investment_style_workflows_block_before_method(self):
        called=[]
        @serialized_dhan_entry
        def submit(service):called.append(True)
        submit(self.service);self.assertEqual(called,[True])
        self.own()
        with self.assertRaises(ValueError):submit(self.service)
        self.assertEqual(called,[True])

    def test_strategy_rejection_is_known_no_send_and_exit_remains_available(self):
        called=[]
        class Broker:
            service=self.service
            @serialized_dhan_strategy_entry
            def place(self,order):called.append(order["side"]);return {"s":"ok"}
        broker=Broker();self.own()
        reply=broker.place({"side":1})
        self.assertEqual(reply["code"],400);self.assertEqual(called,[])
        self.assertEqual(broker.place({"side":-1})["s"],"ok")
        self.assertEqual(called,[-1])

    def test_runner_admission_occurs_before_pending_intent_and_skips_paper_exits(self):
        called=[]
        class Runner:
            adapter=SimpleNamespace(service=self.service)
            state={"config":{"mode":"LIVE","broker":"DHAN"}}
            def is_entry_order(self,order,position):return order["side"]==1
            @serialized_runner_entry
            def submit(self,order,position,reason):called.append(order["side"])
        runner=Runner();self.own()
        with self.assertRaises(ValueError):runner.submit({"side":1},{},"entry")
        self.assertEqual(called,[])
        runner.submit({"side":-1},{},"exit")
        runner.state={"config":{"mode":"PAPER","broker":"DHAN"}}
        runner.submit({"side":1},{},"paper")
        self.assertEqual(called,[-1,1])

    def test_explicit_folder_cannot_escape_bound_workspace(self):
        account="a"*32;root=Path(self.tmp.name)/"registered";folder=root/"accounts"/account
        folder.mkdir(parents=True)
        with patch.dict(os.environ,{"SECTOR_PULSE_WORKSPACE_ID":account,
                    "SECTOR_PULSE_WORKSPACE_REGISTRY":str(root/"registry.sqlite3"),
                    "SECTOR_PULSE_WORKSPACE_BROKER":"DHAN"}):
            with self.assertRaises(PermissionError):
                with entry_lock("DHAN",folder=self.folder):pass
            with entry_lock("DHAN",folder=folder):
                self.assertEqual(entry_revision("DHAN",folder=folder),"0")


if __name__=="__main__":unittest.main()
