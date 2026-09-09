from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLICY_FILES = [
    ROOT / "README.md",
    ROOT / "BROKER_POLICY.md",
    ROOT / "dashboard-enhancements.js",
    ROOT / "sector_heatmap" / "handoff.py",
    ROOT / "sector_heatmap" / "fyers_execution.py",
    ROOT / "sector_heatmap" / "automation.py",
    ROOT / "sector_heatmap" / "web.py",
]


class FyersOnlyInvariantTests(unittest.TestCase):
    def test_feature_surface_contains_no_competing_broker(self):
        forbidden = re.compile(r"\b(dhan(?:hq)?|zerodha|upstox|angel\s*one)\b", re.IGNORECASE)
        for path in POLICY_FILES:
            self.assertIsNone(forbidden.search(path.read_text(encoding="utf-8")), path.name)

    def test_project_policy_explicitly_declares_single_broker(self):
        policy = (ROOT / "BROKER_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("one broker boundary: FYERS", policy)
        self.assertIn("There is no broker chooser", policy)


if __name__ == "__main__":
    unittest.main()
