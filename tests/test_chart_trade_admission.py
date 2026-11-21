import json
import multiprocessing
from pathlib import Path
import tempfile
import threading
import unittest
from dataclasses import replace
from unittest.mock import patch
from sector_heatmap.chart_trade_admission import entry_lock,entry_revision,mark_entry_attempt,serialized_fyers_entry,ChartOrderNotSent
from sector_heatmap.chart_trade_ownership import assert_workspace_chart_entry_allowed
from sector_heatmap.chart_trade_previews import ChartTradePreviews
from sector_heatmap.chart_trade_plan import ChartTradePlan


def child_revision(started,acquired,result):
    started.set()
    with entry_lock("FYERS"):
        result.put(entry_revision("FYERS"));acquired.set()


def fork_again_revision(started,acquired,result):
    ctx=multiprocessing.get_context("fork")
    process=ctx.Process(target=child_revision,args=(started,acquired,result))
    process.start();process.join(5)
    if process.is_alive():process.terminate();process.join(1)
    if process.exitcode!=0:raise RuntimeError("Nested admission worker did not finish")


class Adapter:
    broker="FYERS"
    def __init__(self,account):self.account_id=account;self.calls=0
    def refresh(self,plan):return replace(plan,native_entry_revision=entry_revision("FYERS"))
    def submit_bracket(self,plan,**kwargs):
        self.calls+=1
        mark_entry_attempt("FYERS")
        return dict(account_id=plan.account_id,symbol=plan.symbol,entry_order_id="fake-native-id")


class ChartAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.account="a"*32
        self.base=self.folder/"accounts"/self.account;self.base.mkdir(parents=True)
        self.env=patch.dict("os.environ",dict(SECTOR_PULSE_WORKSPACE_ID=self.account,
                            SECTOR_PULSE_WORKSPACE_REGISTRY=str(self.folder/"registry.sqlite3"),
                            SECTOR_PULSE_WORKSPACE_BROKER="FYERS"))
        self.env.start();self.addCleanup(self.env.stop)
        self.store=ChartTradePreviews(self.base/"chart-trading.sqlite3",clock=lambda:100)
        self.plan=ChartTradePlan(self.account,"FYERS","NSE:TEST","BUY",65,"25","22","30",
                                "LIMIT","25","MARGIN",".05",65,"AT_OR_BELOW",native_entry_revision=entry_revision("FYERS"))
        self.preview=self.store.prepare("owner",self.plan);self.adapter=Adapter(self.account)
    def arm(self):
        return self.store.arm("owner",self.preview["preview_id"],self.preview["confirmation_phrase"],
                              mode="LIVE",adapter=self.adapter,enabled=True)
    def test_lock_is_cross_process_and_revision_is_durable(self):
        ctx=multiprocessing.get_context("spawn")
        started,acquired,result=ctx.Event(),ctx.Event(),ctx.Queue()
        process=ctx.Process(target=child_revision,args=(started,acquired,result))
        try:
            with entry_lock("FYERS"):
                process.start();self.assertTrue(started.wait(3))
                self.assertFalse(acquired.wait(.1))
                self.assertEqual(mark_entry_attempt("FYERS"),"1")
            self.assertTrue(acquired.wait(3));self.assertEqual(result.get(timeout=1),"1")
            process.join(3);self.assertEqual(process.exitcode,0)
        finally:
            if process.is_alive():process.terminate();process.join(2)
            result.close()
    def test_nested_admission_is_reentrant_and_counter_survives_unlock(self):
        with entry_lock("FYERS"):
            self.assertEqual(entry_revision("FYERS"),"0")
            with entry_lock("FYERS"):self.assertEqual(mark_entry_attempt("FYERS"),"1")
        self.assertEqual(entry_revision("FYERS"),"1")
    def test_intervening_entry_invalidates_preview_before_any_chart_placement(self):
        mark_entry_attempt("FYERS")
        with self.assertRaisesRegex(ValueError,"changed"):self.arm()
        self.assertEqual(self.adapter.calls,0)
        self.assertEqual(self.store.inspect("owner",self.preview["preview_id"])["status"],"PREVIEW")
    def test_legacy_entry_first_blocks_chart_refresh_until_revision_changed(self):
        entered=threading.Event();release=threading.Event();finished=threading.Event();errors=[]
        def legacy():
            with entry_lock("FYERS"):
                mark_entry_attempt("FYERS");entered.set();release.wait(3)
        def chart():
            try:self.arm()
            except Exception as error:errors.append(error)
            finally:finished.set()
        legacy_thread=threading.Thread(target=legacy);chart_thread=threading.Thread(target=chart)
        legacy_thread.start();self.assertTrue(entered.wait(2));chart_thread.start()
        try:self.assertFalse(finished.wait(.1))
        finally:release.set();legacy_thread.join(3);chart_thread.join(3)
        self.assertTrue(finished.is_set());self.assertEqual(self.adapter.calls,0)
        self.assertIsInstance(errors[0],ValueError)
    def test_chart_first_blocks_late_legacy_entry_before_its_placement(self):
        entered=threading.Event();release=threading.Event();legacy_done=threading.Event();errors=[];legacy_calls=[]
        original=self.adapter.submit_bracket
        def chart_submit(plan,**kwargs):
            entered.set();release.wait(3);return original(plan,**kwargs)
        self.adapter.submit_bracket=chart_submit
        @serialized_fyers_entry
        def legacy():
            assert_workspace_chart_entry_allowed("FYERS")
            legacy_calls.append("would-place")
        def legacy_run():
            try:legacy()
            except Exception as error:errors.append(error)
            finally:legacy_done.set()
        chart_result=[]
        chart_thread=threading.Thread(target=lambda:chart_result.append(self.arm()))
        legacy_thread=threading.Thread(target=legacy_run)
        chart_thread.start();self.assertTrue(entered.wait(2));legacy_thread.start()
        try:self.assertFalse(legacy_done.wait(.1))
        finally:release.set();chart_thread.join(3);legacy_thread.join(3)
        self.assertEqual(chart_result[0]["status"],"BROKER_ACCEPTED")
        self.assertEqual(self.adapter.calls,1);self.assertEqual(legacy_calls,[])
        self.assertIsInstance(errors[0],ValueError)
    def test_verified_no_send_rejection_does_not_leave_an_uncertain_owner(self):
        def reject(*args,**kwargs):raise ChartOrderNotSent("Final local validation failed")
        self.adapter.submit_bracket=reject
        result=self.arm()
        self.assertEqual(result["status"],"REJECTED");self.assertFalse(result["order_submitted"])
        self.assertEqual(self.adapter.calls,0)
        assert_workspace_chart_entry_allowed("FYERS")
        self.assertEqual(entry_revision("FYERS"),"0")
    def test_unknown_transport_outcome_remains_owned_and_is_never_retried(self):
        def send(*args,**kwargs):
            self.adapter.calls+=1;mark_entry_attempt("FYERS");raise TimeoutError("Unknown")
        self.adapter.submit_bracket=send
        self.assertEqual(self.arm()["status"],"SUBMISSION_UNCERTAIN")
        self.assertEqual(self.arm()["status"],"SUBMISSION_UNCERTAIN")
        self.assertEqual(self.adapter.calls,1)
        with self.assertRaises(ValueError):assert_workspace_chart_entry_allowed("FYERS")

    def test_native_socket_error_is_never_misclassified_as_no_send(self):
        from sector_heatmap.chart_trade_admission import place_fyers_entry
        calls=[]
        def sender(payload):
            calls.append(payload);raise BlockingIOError("Native transport outcome unknown")
        with self.assertRaises(BlockingIOError):place_fyers_entry(sender,{"symbol":"NSE:TEST"})
        self.assertEqual(len(calls),1)
        self.assertEqual(entry_revision("FYERS"),"1")

    def test_delta_chart_nested_native_admission_is_reentrant_and_exits_bypass_it(self):
        from types import SimpleNamespace
        from sector_heatmap.chart_trade_admission import serialized_delta_request
        import hashlib
        class Native:
            def __init__(self):self.lock=threading.RLock();self.calls=[]
            @serialized_delta_request
            def send(self,method,path,params=None,body=None,credentials=None):
                self.calls.append(body);return {"id":"delta-native-fake"}
        with patch.dict("os.environ",{"SECTOR_PULSE_WORKSPACE_BROKER":"DELTA_INDIA"}):
            native=Native();plan=replace(self.plan,broker="DELTA_INDIA")
            preview=self.store.prepare("owner",plan)
            adapter=SimpleNamespace(broker="DELTA_INDIA",account_id=self.account,execution=native,
                refresh=lambda plan:replace(plan,native_entry_revision=entry_revision("DELTA_INDIA")))
            def submit(plan,*,idempotency_key):
                token="CH"+hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]
                reply=native.send("POST","/v2/orders",body=dict(client_order_id=token,reduce_only=False))
                return dict(entry_order_id=reply["id"],account_id=self.account,symbol=plan.symbol)
            adapter.submit_bracket=submit
            result=self.store.arm("owner",preview["preview_id"],preview["confirmation_phrase"],mode="LIVE",adapter=adapter,enabled=True)
            self.assertEqual(result["status"],"BROKER_ACCEPTED");self.assertEqual(len(native.calls),1)
            finished=threading.Event()
            with entry_lock("DELTA_INDIA"):
                thread=threading.Thread(target=lambda:(native.send("POST","/v2/orders",body={"reduce_only":True}),finished.set()))
                thread.start();self.assertTrue(finished.wait(1));thread.join(1)
            self.assertEqual(len(native.calls),2)
            self.assertEqual(entry_revision("DELTA_INDIA"),"1")


    def test_parser_and_long_straddle_entry_paths_preserve_exit_and_dry_run_access(self):
        import ast
        from types import SimpleNamespace
        from sector_heatmap.chart_trade_admission import place_fyers_entry
        from sector_heatmap.parser_lifecycle import ParserLifecycle
        with self.store.connection() as db:
            db.execute("UPDATE previews SET state='ENTRY_PENDING' WHERE id=?",(self.preview["preview_id"],))
        lifecycle=ParserLifecycle(self.base/"parser.sqlite3",object(),enabled=lambda:True)
        self.addCleanup(lifecycle.db.close)
        with self.assertRaisesRegex(ValueError,"chart order owns"):
            lifecycle.submit_entry({"preview_id":"parser-ticket"})
        self.assertEqual(lifecycle.rows(),[])
        for name in ("nifty_straddle.py","sensex_straddle.py"):
            path=Path("strategies/long_straddle")/name
            tree=ast.parse(path.read_text())
            function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="place_order")
            calls=[]
            def sender(order):
                calls.append(order);return {"s":"ok","id":"fake-exit"}
            scope=dict(DRY_RUN=False,fyers=SimpleNamespace(place_order=sender),place_fyers_entry=place_fyers_entry,
                       log=lambda *args:None)
            exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),"exec"),scope)
            with self.assertRaises(ChartOrderNotSent):scope["place_order"]("NSE:TEST",65,1)
            self.assertEqual(calls,[])
            scope["place_order"]("NSE:TEST",65,-1)
            self.assertEqual(calls[0]["side"],-1)
            scope["DRY_RUN"]=True
            scope["place_order"]("NSE:TEST",65,1)
            self.assertEqual(len(calls),1)


    @unittest.skipUnless("fork" in multiprocessing.get_all_start_methods(),"OS fork unavailable")
    def test_forked_worker_cannot_inherit_reentrant_lock_ownership(self):
        ctx=multiprocessing.get_context("fork")
        started,acquired,result=ctx.Event(),ctx.Event(),ctx.Queue()
        process=ctx.Process(target=child_revision,args=(started,acquired,result))
        try:
            with entry_lock("FYERS"):
                process.start();self.assertTrue(started.wait(2))
                self.assertFalse(acquired.wait(.1))
                mark_entry_attempt("FYERS")
            self.assertTrue(acquired.wait(2));self.assertEqual(result.get(timeout=1),"1")
            process.join(2);self.assertEqual(process.exitcode,0)
        finally:
            if process.is_alive():process.terminate();process.join(2)
            result.close()


    @unittest.skipUnless("fork" in multiprocessing.get_all_start_methods(),"OS fork unavailable")
    def test_forked_worker_can_safely_fork_another_reader(self):
        ctx=multiprocessing.get_context("fork")
        started,acquired,result=ctx.Event(),ctx.Event(),ctx.Queue()
        process=ctx.Process(target=fork_again_revision,args=(started,acquired,result))
        try:
            with entry_lock("FYERS"):
                process.start();self.assertTrue(started.wait(2))
                self.assertFalse(acquired.wait(.1));mark_entry_attempt("FYERS")
            self.assertTrue(acquired.wait(2));self.assertEqual(result.get(timeout=1),"1")
            process.join(3);self.assertEqual(process.exitcode,0)
        finally:
            if process.is_alive():process.terminate();process.join(2)
            result.close()

if __name__=="__main__":unittest.main()
