import json
import tempfile
import threading
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from sector_heatmap.runner_job_history import record, read
from strategies.ema_crossover.runner import Runner
from strategies.renko_supertrend.delta_broker import history_file_lock

class JobControlTests(TestCase):
    def test_history_keeps_each_submission_and_updates_only_its_record(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"state.json"
            state=dict(run_id="first",started_at=1,config={"mode":"PAPER"},running=True,updated_at=2)
            record(path,state)
            record(path,{**state,"run_id":"second","started_at":3})
            record(path,{**state,"running":False,"updated_at":4})
            rows=read(path)
            self.assertEqual([r["job_id"] for r in rows],["second","first"])
            self.assertFalse(rows[1]["running"])
            self.assertTrue(rows[0]["running"])
    def test_stop_ack_does_not_wait_for_trading_lock_and_rejects_wrong_run(self):
        with tempfile.TemporaryDirectory() as d:
            runner=Runner(Mock(),Path(d)/"state.json")
            runner.state.update(run_id="one",running=True,started_at=1,config={"mode":"PAPER"})
            runner.save()
            held=threading.Event();release=threading.Event();finished=threading.Event()
            def hold():
                with runner.lock:
                    held.set();release.wait(3)
            t=threading.Thread(target=hold);t.start();self.assertTrue(held.wait(1))
            runner.stop=lambda: (runner.lock.acquire(),runner.lock.release(),finished.set())
            try:
                with self.assertRaises(ValueError):runner.request_stop({"run_id":"other"})
                before=time.monotonic();result=runner.request_stop({"run_id":"one"})
                self.assertLess(time.monotonic()-before,.25)
                self.assertTrue(result["shutdown_pending"])
                self.assertTrue(runner.stop_requested.is_set())
                self.assertFalse(finished.is_set())
            finally:
                release.set();t.join();runner.stop_thread.join(2)
            self.assertTrue(finished.is_set())
    def test_independent_history_archives_do_not_share_network_lock(self):
        self.assertIs(history_file_lock("/tmp/a","BTCUSD","1m"),history_file_lock("/tmp/a","BTCUSD","1m"))
        self.assertIsNot(history_file_lock("/tmp/a","BTCUSD","1m"),history_file_lock("/tmp/b","BTCUSD","1m"))
        self.assertIsNot(history_file_lock("/tmp/a","BTCUSD","1m"),history_file_lock("/tmp/a","ETHUSD","1m"))

    def test_busy_snapshot_returns_saved_position_without_claiming_fresh_pnl(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=Mock();adapter.live_enabled.return_value=False
            runner=Runner(adapter,Path(d)/"state.json")
            runner.state.update(run_id="held",running=True,position={"symbol":"ABC","quantity":1})
            runner.save()
            ready=threading.Event();release=threading.Event()
            def hold():
                with runner.lock:
                    ready.set();release.wait(2)
            worker=threading.Thread(target=hold);worker.start()
            self.assertTrue(ready.wait(1))
            try:
                before=time.monotonic();snapshot=runner.snapshot()
                self.assertLess(time.monotonic()-before,.5)
                self.assertTrue(snapshot["status_read_delayed"])
                self.assertEqual(snapshot["position"]["symbol"],"ABC")
                self.assertFalse(snapshot["pnl"]["available"])
                self.assertIsNone(snapshot["pnl"]["unrealized"])
                adapter.quote.assert_not_called()
            finally:
                release.set();worker.join()

    def test_fyers_chart_history_locks_are_per_range_and_rate_slots_are_shared(self):
        from strategies.renko_supertrend.chart_history import ChartHistory
        from unittest.mock import patch
        history=ChartHistory("/tmp/test-history",min_interval=.5)
        self.assertIs(history.history_lock("a"),history.history_lock("a"))
        self.assertIsNot(history.history_lock("a"),history.history_lock("b"))
        with patch("strategies.renko_supertrend.chart_history.time.monotonic",return_value=10), patch("strategies.renko_supertrend.chart_history.time.sleep") as sleep:
            history.wait_request_slot()
            history.wait_request_slot()
        self.assertEqual([call.args[0] for call in sleep.call_args_list],[0,.5])

    def test_legacy_history_retains_iso_timestamp_and_settings_after_stop(self):
        from sector_heatmap.runner_job_history import record_legacy
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"legacy.json"
            state={"run_started_at":"2026-10-14T09:30:00+05:30","running":True,"config":{"symbol":"ABC"}}
            record_legacy(path,state)
            record_legacy(path,{**state,"running":False,"status":"STOPPED"})
            rows=read(path)
            self.assertEqual(len(rows),1)
            self.assertFalse(rows[0]["running"])
            self.assertIsInstance(rows[0]["started_at"],float)
            self.assertEqual(rows[0]["config"]["symbol"],"ABC")


    def test_async_stop_preserves_owned_position_and_pending_until_reconciled(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=Mock()
            runner=Runner(adapter,Path(d)/"state.json")
            runner.state.update(run_id="owned",running=True,started_at=1,
                config={"mode":"LIVE"},position={"symbol":"ABC","quantity":3},
                pending={"order_id":"accepted","quantity":5})
            runner.save()
            runner.snapshot=Mock(return_value={})
            result=runner.request_stop({"run_id":"owned"})
            runner.stop_thread.join(2)
            self.assertTrue(result["shutdown_pending"])
            self.assertFalse(runner.stop_thread.is_alive())
            self.assertTrue(runner.state["running"])
            self.assertFalse(runner.state["accepting_entries"])
            self.assertTrue(runner.state["squareoff_requested"])
            self.assertEqual(runner.state["position"]["quantity"],3)
            self.assertTrue(runner.state["position"]["exit_requested"])
            self.assertEqual(runner.state["pending"]["order_id"],"accepted")
            adapter.stop.assert_not_called()
            adapter.submit.assert_not_called()
            saved=json.loads(runner.path.read_text())
            self.assertEqual(saved["pending"]["order_id"],"accepted")
            self.assertEqual(saved["position"]["quantity"],3)


class StraddleHistoryTests(TestCase):
    def test_both_straddle_services_retain_submissions_after_reload(self):
        from sector_heatmap.sensex_straddle import SensexStraddleService
        from sector_heatmap.nifty_straddle import NiftyStraddleService
        for cls in (SensexStraddleService,NiftyStraddleService):
            with self.subTest(service=cls.__name__), tempfile.TemporaryDirectory() as d:
                service=cls(runtime_dir=d)
                process=Mock();process.poll.return_value=None
                service.process=process
                service.started_at="2026-10-14T09:30:00+05:30"
                service.active_mode="PAPER"
                service.active_lots=2
                first=service.snapshot_unlocked()["job_history"][0]["job_id"]
                process.poll.return_value=0
                stopped=service.snapshot_unlocked()["job_history"][0]
                self.assertFalse(stopped["running"])
                service.started_at="2026-10-14T10:30:00+05:30"
                process.poll.return_value=None
                rows=service.snapshot_unlocked()["job_history"]
                self.assertEqual(len(rows),2)
                self.assertNotEqual(rows[0]["job_id"],first)
                restored=cls(runtime_dir=d)
                retained=restored.snapshot_unlocked()["job_history"]
                self.assertEqual(retained,rows)
                self.assertIsNone(restored.process)
                process.terminate.assert_not_called()
