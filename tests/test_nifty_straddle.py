import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from sector_heatmap.nifty_straddle import NiftyStraddleService


SCRIPT = """
NUM_LOTS = 1
VOL_PERCENTILE = 50
VOL_LOOKBACK_DAYS = 20
REALIZED_VOL_WINDOW_BARS = 78
STOPLOSS_POINTS = 15.0
TARGET_POINTS = 30.0
import datetime as dt
EOD_SQUARE_OFF_TIME = dt.time(15, 20)
"""


class NiftyStraddleServiceTests(unittest.TestCase):
    def test_snapshot_reads_nifty_strategy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nifty_straddle.py"
            path.write_text(SCRIPT)
            result = NiftyStraddleService(path).snapshot()
            self.assertTrue(result["available"])
            self.assertEqual(result["name"], "NIFTY Long Straddle")
            self.assertEqual(result["strategy"]["hard_stop"], "-15 combined-premium points")
            self.assertIn("Supertrend(7, 3) after +10 points", result["strategy"]["exit"])
            self.assertEqual(result["strategy"]["entry_window_start"], "09:15")
            self.assertEqual(result["strategy"]["entry_window_end"], "11:30")
            self.assertEqual(result["strategy"]["daily_reentry_limit"], 1)

    def test_live_start_requires_confirmation_and_passes_every_cli_option(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nifty_straddle.py"
            path.write_text(f"#!{Path(__import__('sys').executable)}\n{SCRIPT}")
            process = Mock(pid=321, stdout=[])
            process.poll.return_value = None
            process.stdin = StringIO()
            process.stdin.close = Mock()
            factory = Mock(return_value=process)
            service = NiftyStraddleService(path, process_factory=factory)
            with self.assertRaises(PermissionError):
                service.start("live", lots=2, stoploss=12, target=35)
            service.start("live", lots=2, stoploss=12, target=35, confirmation="YES")
            command = factory.call_args.args[0]
            self.assertIn("--live", command)
            self.assertEqual(command[command.index("--lots") + 1], "2")
            self.assertEqual(command[command.index("--stoploss") + 1], "12.0")
            self.assertEqual(command[command.index("--target") + 1], "35.0")
            self.assertEqual(command[command.index("--entry-start") + 1], "09:15")
            self.assertEqual(command[command.index("--entry-end") + 1], "11:30")
            self.assertIn("--supertrend-trail", command)
            self.assertEqual(process.stdin.getvalue(), "YES\n")

    def test_paper_start_omits_live_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nifty_straddle.py"
            path.write_text(SCRIPT)
            process = Mock(pid=456, stdout=[])
            process.poll.return_value = None
            factory = Mock(return_value=process)
            NiftyStraddleService(path, process_factory=factory).start("paper", lots=1, stoploss=15, target=30)
            self.assertNotIn("--live", factory.call_args.args[0])

    def test_entry_window_is_validated_and_passed_to_the_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nifty_straddle.py"
            path.write_text(SCRIPT)
            process = Mock(pid=456, stdout=[])
            process.poll.return_value = None
            factory = Mock(return_value=process)
            service = NiftyStraddleService(path, process_factory=factory)
            with self.assertRaises(ValueError):
                service.start("paper", entry_start="11:31", entry_end="11:30")
            service.start("paper", entry_start="09:30", entry_end="11:00")
            command = factory.call_args.args[0]
            self.assertEqual(command[command.index("--entry-start") + 1], "09:30")
            self.assertEqual(command[command.index("--entry-end") + 1], "11:00")


if __name__ == "__main__":
    unittest.main()
