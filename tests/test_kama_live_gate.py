import os
import unittest
from pathlib import Path
from unittest.mock import patch

from sector_heatmap.fyers_execution import FyersExecutionService
from sector_heatmap.kama_strategy import kama_exit_state_machine, kama_entry_policy_decision


class KamaLiveGateTests(unittest.TestCase):
    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    @patch.dict(os.environ, {"SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS": "0", "SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS": "1"}, clear=False)
    def test_kama_gate_is_independent_from_dashboard_wide_gate(self, _):
        service = FyersExecutionService(client_factory=lambda *_: object(), live_gate_name="SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS")
        capability = service.capabilities()
        self.assertTrue(capability["live_submission_enabled"])
        self.assertEqual(capability["live_gate_name"], "SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS")

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    @patch.dict(os.environ, {"SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS": "0", "SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS": "0"}, clear=False)
    def test_kama_gate_remains_off_without_its_exact_opt_in(self, _):
        self.assertFalse(FyersExecutionService(client_factory=lambda *_: object(), live_gate_name="SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS").capabilities()["live_submission_enabled"])

    def test_kama_runner_reuses_ema_master_eligibility(self):
        backend = Path("sector_heatmap/web.py").read_text(encoding="utf-8")
        self.assertIn("search_kama_underlyings(symbol, execution_mode)", backend)
        self.assertIn("same exchange and segment filters as EMA Band", backend)

    def test_kama_ui_uses_master_backed_search_and_picker(self):
        dashboard = Path("dashboard-enhancements.js").read_text(encoding="utf-8")
        backend = Path("sector_heatmap/web.py").read_text(encoding="utf-8")
        self.assertIn('id="kama-underlying-search"', dashboard)
        self.assertIn('id="kama-underlying" disabled', dashboard)
        self.assertIn('id="kama-execution-mode"', dashboard)
        self.assertIn('Options — automatic ATM Call / Put', dashboard)
        self.assertIn('/api/kama/underlying-search', dashboard)
        self.assertIn('path == "/api/kama/underlying-search"', backend)
        self.assertIn('CURRENT_FYERS_MASTER_UNDERLYINGS_ONLY', backend)
        self.assertIn('"MCX_COM"', backend)
        self.assertIn('select_ema_atm_option(rows, config["master_underlying"]', backend)

    def test_kama_exit_requires_completed_signal_and_confirmed_broker_state(self):
        self.assertFalse(kama_exit_state_machine({"action": "WAIT"}, True)["exit"])
        self.assertEqual(kama_exit_state_machine({"action": "EXIT_LONG"}, True, "ABSENT")["lifecycle"], "RECONCILIATION_BLOCKED")
        ready = kama_exit_state_machine({"action": "SQUARE_OFF"}, True, "CONFIRMED")
        self.assertTrue(ready["exit"])
        self.assertEqual(ready["reason"], "SESSION_SQUARE_OFF")

    def test_kama_entry_policy_is_fail_closed(self):
        self.assertEqual(kama_entry_policy_decision({"action": "ENTER_LONG"}, {})["reason"], "POLICY_INCOMPLETE")
        self.assertFalse(kama_entry_policy_decision({"action": "ENTER_LONG"}, {"quantity": 1, "max_risk": 100, "stop_price": 90}, True)["allowed"])
        self.assertTrue(kama_entry_policy_decision({"action": "ENTER_LONG"}, {"quantity": 1, "max_risk": 100, "stop_price": 90})["allowed"])


if __name__ == "__main__":
    unittest.main()
