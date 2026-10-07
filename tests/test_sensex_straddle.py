import tempfile
import unittest
import json
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from sector_heatmap.sensex_straddle import SensexStraddleService


SCRIPT = """
LOT_SIZE = 20
NUM_LOTS = 1
DAILY_COOLDOWN = False
VOL_PERCENTILE = 50
SUPER_TREND_PERIOD = 7
SUPER_TREND_MULTIPLIER = 3.0
SUPER_TREND_ACTIVATION_POINTS = 10.0
import datetime as dt
EOD_SQUARE_OFF_TIME = dt.time(15, 20)

import json
DRY_RUN=True
QUANTITY=20

def place_order(symbol,quantity,side):
    return {}

def enter_position():
    premium_entry=100
    ce_symbol='CE'
    pe_symbol='PE'
    ce_order = place_order(ce_symbol, QUANTITY, side=1)
    state={'premium_entry':premium_entry}
    save_state(state)
    return state

def exit_position(state,reason):
    premium_exit=110
    pnl_rupees=(premium_exit-state['premium_entry'])*QUANTITY
    clear_state()

if __name__ == "__main__":
    pass

"""


class SensexStraddleServiceTests(unittest.TestCase):
    def test_snapshot_reads_strategy_and_exposes_guarded_live_control(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensex_straddle.py"
            path.write_text(SCRIPT)
            service = SensexStraddleService(path)
            result = service.snapshot()
            self.assertTrue(result["available"])
            self.assertEqual(result["mode"], "STOPPED")
            self.assertTrue(result["live_control_available"])
            self.assertEqual(result["strategy"]["exit"], "Supertrend(7, 3.0) after +10.0 points")
            self.assertEqual(result["strategy"]["eod"], "15:20")
            self.assertEqual(result["strategy"]["entry_window_start"], "09:15")
            self.assertEqual(result["strategy"]["entry_window_end"], "11:30")
            self.assertEqual(result["strategy"]["daily_reentry_limit"], 1)
            self.assertEqual(result["runtime_dir"], str(path.parent.resolve()))

    def test_snapshot_exposes_premium_chart_only_for_open_position(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensex_straddle.py"
            path.write_text(SCRIPT)
            runtime = Path(directory) / "runtime"
            runtime.mkdir()
            (runtime / "live_premium_chart.json").write_text(json.dumps({"premium_now": 742.5}))
            service = SensexStraddleService(path, runtime_dir=runtime)
            self.assertIsNone(service.snapshot()["premium_chart"])
            (runtime / "live_position_state.json").write_text(json.dumps({"premium_entry": 730}))
            self.assertEqual(service.snapshot()["premium_chart"]["premium_now"], 742.5)

    def test_absolute_executable_shebang_selects_runner_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensex_straddle.py"
            path.write_text(f"#!{Path(__import__('sys').executable)}\n{SCRIPT}")
            service = SensexStraddleService(path)
            self.assertEqual(service.snapshot()["interpreter"], str(Path(__import__('sys').executable)))

    def test_missing_script_is_reported_and_cannot_start(self):
        service = SensexStraddleService("/tmp/not-a-real-sensex-runner.py")
        self.assertFalse(service.snapshot()["available"])
        with self.assertRaises(FileNotFoundError):
            service.start_paper()

    def test_live_start_requires_exact_confirmation_and_passes_selected_options(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensex_straddle.py"
            path.write_text(f"#!{Path(__import__('sys').executable)}\n{SCRIPT}")
            process = Mock()
            process.pid = 123
            process.poll.return_value = None
            process.stdout = []
            process.stdin = StringIO()
            process.stdin.close = Mock()
            factory = Mock(return_value=process)
            service = SensexStraddleService(path, process_factory=factory)

            with self.assertRaises(PermissionError):
                service.start(mode="live", exit_mode="supertrend")
            result = service.start(mode="live", exit_mode="trail", lots=3, confirmation="YES")

            command = factory.call_args.args[0]
            self.assertIn("--live", command)
            self.assertIn("--trail-profit", command)
            self.assertEqual(command[command.index("--lots") + 1], "3")
            self.assertEqual(command[command.index("--entry-start") + 1], "09:15")
            self.assertEqual(command[command.index("--entry-end") + 1], "11:30")
            self.assertEqual(process.stdin.getvalue(), "YES\n")
            self.assertEqual(result["mode"], "LIVE")

    def test_paper_start_supports_each_exit_option_without_live_flag(self):
        for exit_mode, expected_flag in {
            "supertrend": "--supertrend-trail",
            "fixed": "--fixed-target",
            "trail": "--trail-profit",
        }.items():
            with self.subTest(exit_mode=exit_mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "sensex_straddle.py"
                path.write_text(f"#!{Path(__import__('sys').executable)}\n{SCRIPT}")
                process = Mock(pid=456, stdout=[])
                process.poll.return_value = None
                factory = Mock(return_value=process)
                result = SensexStraddleService(path, process_factory=factory).start("paper", exit_mode)
                command = factory.call_args.args[0]
                self.assertIn(expected_flag, command)
                self.assertNotIn("--live", command)
                self.assertEqual(result["mode"], "PAPER")

    def test_lots_must_be_a_whole_number_in_supported_range(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensex_straddle.py"
            path.write_text(SCRIPT)
            service = SensexStraddleService(path)
            for lots in (0, 21, 1.5, "three"):
                with self.subTest(lots=lots), self.assertRaises(ValueError):
                    service.start("paper", "supertrend", lots=lots)

    def test_entry_window_is_validated_and_passed_to_the_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensex_straddle.py"
            path.write_text(SCRIPT)
            process = Mock(pid=456, stdout=[])
            process.poll.return_value = None
            factory = Mock(return_value=process)
            service = SensexStraddleService(path, process_factory=factory)
            with self.assertRaises(ValueError):
                service.start("paper", entry_start="11:31", entry_end="11:30")
            service.start("paper", entry_start="09:30", entry_end="11:00")
            command = factory.call_args.args[0]
            self.assertEqual(command[command.index("--entry-start") + 1], "09:30")
            self.assertEqual(command[command.index("--entry-end") + 1], "11:00")


if __name__ == "__main__":
    unittest.main()
