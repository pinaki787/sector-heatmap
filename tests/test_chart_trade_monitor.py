import json
from pathlib import Path
import tempfile
import unittest
from sector_heatmap.chart_trading import ChartTradingService
from sector_heatmap.chart_trade_monitor import ChartTradeMonitor
from sector_heatmap.chart_trade_plan import ChartTradePlan


class ReadAdapter:
    account_id="account-a";broker="FYERS"
    def __init__(self):self.reads=0;self.batches=0;self.fail=False;self.status="ENTRY_PENDING"
    def begin_reconciliation_batch(self):
        self.batches+=1
        if self.fail:raise TimeoutError("Read unavailable")
    def reconcile(self,plan,**kwargs):
        self.reads+=1
        return dict(account_id=plan.account_id,broker=plan.broker,symbol=plan.symbol,status=self.status,
                    checked_at=100,protection_confirmed=self.status=="POSITION_PROTECTED",
                    retry_allowed=False,message="Native read evidence.")
    def prepare(self,*args,**kwargs):raise AssertionError("Monitor cannot prepare an order")
    def refresh(self,*args,**kwargs):raise AssertionError("Monitor cannot arm an order")
    def submit_bracket(self,*args,**kwargs):raise AssertionError("Monitor cannot submit an order")


class ChartMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"chart.sqlite3";self.clock=0;self.adapter=ReadAdapter()
        self.account=dict(id="account-a",broker="FYERS",user_id="owner",live_enabled=False)
        self.service=ChartTradingService(self.account,self.path,lambda account:self.adapter,clock=lambda:100)
        self.monitor=ChartTradeMonitor(self.service,clock=lambda:self.clock)
        self.plan=ChartTradePlan("account-a","FYERS","NSE:TEST","BUY",65,"25","22","30",
                                "LIMIT","25","INTRADAY",".05",65,"AT_OR_BELOW")
    def intent(self):
        preview=self.service.previews.prepare("owner",self.plan)
        result=dict(account_id="account-a",broker="FYERS",symbol="NSE:TEST",status="SUBMISSION_UNCERTAIN",
                    protection_confirmed=False,retry_allowed=False)
        with self.service.previews.connection() as db:
            db.execute("UPDATE previews SET state=?,result=? WHERE id=?",
                       ("SUBMISSION_UNCERTAIN",json.dumps(result),preview["preview_id"]))
        return preview["preview_id"]
    def test_durable_uncertain_entry_is_read_without_live_gate_or_order_resubmission(self):
        key=self.intent()
        self.assertEqual(self.monitor.run_once(),1)
        self.assertEqual(self.service.previews.inspect("owner",key)["status"],"ENTRY_PENDING")
        self.assertEqual(self.adapter.reads,1)
    def test_unsubmitted_preview_never_causes_broker_reads(self):
        self.service.previews.prepare("owner",self.plan)
        self.assertEqual(self.monitor.run_once(),0);self.assertEqual(self.adapter.batches,0)
    def test_restart_resumes_only_reads_of_existing_intent(self):
        key=self.intent();self.monitor.run_once()
        restarted=ChartTradingService(self.account,self.path,lambda account:self.adapter,clock=lambda:100)
        monitor=ChartTradeMonitor(restarted,clock=lambda:self.clock)
        self.adapter.status="CLOSED"
        self.assertEqual(monitor.run_once(),1)
        self.assertEqual(restarted.previews.inspect("owner",key)["status"],"CLOSED")
        self.assertEqual(monitor.run_once(),0)
    def test_one_native_account_batch_serves_multiple_pending_records(self):
        self.intent();self.intent();self.assertEqual(self.monitor.run_once(),2)
        self.assertEqual(self.adapter.batches,1);self.assertEqual(self.adapter.reads,2)
        self.assertEqual(self.monitor.run_once(),0)
    def test_read_failure_clears_protection_and_backs_off_without_repeating_order(self):
        key=self.intent();self.adapter.status="POSITION_PROTECTED";self.monitor.run_once()
        self.adapter.fail=True;self.clock=16;self.monitor.run_once()
        record=self.service.previews.inspect("owner",key)
        self.assertEqual(record["status"],"BROKER_STATUS_UNAVAILABLE")
        self.assertFalse(record["result"]["protection_confirmed"])
        batches=self.adapter.batches;self.clock=31;self.monitor.run_once()
        self.assertEqual(self.adapter.batches,batches)
        self.adapter.fail=False;self.clock=47;self.monitor.run_once()
        self.assertEqual(self.service.previews.inspect("owner",key)["status"],"POSITION_PROTECTED")
    def test_stop_and_busy_status_reader_do_not_create_parallel_reads(self):
        self.intent()
        with self.service.reconciliation_lock:self.assertEqual(self.monitor.run_once(),0)
        self.monitor.close();self.assertEqual(self.monitor.run_once(),0)
        self.assertEqual(self.adapter.reads,0)

    def test_background_thread_updates_durable_state_without_any_browser_request(self):
        import threading
        key=self.intent();observed=threading.Event()
        original=self.adapter.reconcile
        def reconcile(*args,**kwargs):
            value=original(*args,**kwargs);observed.set();return value
        self.adapter.reconcile=reconcile
        self.service.start_monitor()
        try:self.assertTrue(observed.wait(1))
        finally:self.service.close()
        self.assertEqual(self.service.previews.inspect("owner",key)["status"],"ENTRY_PENDING")

    def test_service_registration_starts_one_monitor_and_never_falls_through_unknown_broker(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from sector_heatmap.chart_trading import get_service
        server=SimpleNamespace();guard=SimpleNamespace(store=SimpleNamespace(folder=lambda account:Path(self.temp.name)))
        with patch.object(ChartTradingService,"start_monitor") as start:
            first=get_service(server,guard,self.account,object())
            second=get_service(server,guard,self.account,object())
            self.assertIs(first,second);self.assertEqual(start.call_count,1)
            with self.assertRaises(ValueError):
                get_service(server,guard,dict(self.account,broker="UNKNOWN"),object())

    def test_server_restart_hook_resumes_only_when_a_private_ledger_exists(self):
        import sqlite3
        from types import SimpleNamespace
        from unittest.mock import patch
        from sector_heatmap.chart_trading import resume_existing
        registry=Path(self.temp.name)/"registry.sqlite3"
        with sqlite3.connect(registry) as db:
            db.execute("CREATE TABLE accounts(id TEXT,broker TEXT)")
            db.execute("INSERT INTO accounts VALUES(?,?)",("account-a","FYERS"))
        def connection():
            db=sqlite3.connect(registry);db.row_factory=sqlite3.Row;return db
        guard=SimpleNamespace(account_id="account-a",store=SimpleNamespace(db=connection,folder=lambda account:Path(self.temp.name)))
        with patch("sector_heatmap.chart_trading.get_service") as get:
            resume_existing(object(),guard,object())
            get.assert_not_called()
            (Path(self.temp.name)/"chart-trading.sqlite3").touch()
            resume_existing(object(),guard,object())
            self.assertEqual(get.call_count,1)

if __name__=="__main__":unittest.main()
