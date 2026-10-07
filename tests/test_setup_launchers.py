import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATES = (
    "SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS",
    "SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS",
    "SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS",
)


class SetupLauncherTests(unittest.TestCase):
    def test_runtime_template_is_fail_closed(self):
        template = (ROOT / ".env.example").read_text(encoding="utf-8")
        for gate in GATES:
            self.assertIn(f"{gate}=0", template)

    def test_all_launchers_load_and_validate_the_same_live_gates(self):
        for filename in ("setup_and_run.sh", "run_live_heatmap.sh", "setup_and_run.bat", "run_live_heatmap.bat"):
            source = (ROOT / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertIn(".env", source)
                self.assertIn("Live-order switches must each be 0 or 1.", source)
                for gate in GATES:
                    self.assertIn(gate, source)


if __name__ == "__main__":
    unittest.main()
