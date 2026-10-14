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
