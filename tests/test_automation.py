from datetime import datetime
from pathlib import Path
import json
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from sector_heatmap.automation import AutomationPolicyService, HashChainAuditLog, validate_automation_policy


def valid_policy():
    return {
        "enabled": True, "execution_mode": "PAPER",
        "universe_mode": "ALIGNED_EQUITIES_AND_OPTIONS", "option_universe": "INDEX_AND_STOCK_OPTIONS",
        "allow_stock_options_for_aligned_equities": True,
        "allowed_symbols": ["NSE:RELIANCE-EQ", "NSE:NIFTY50-INDEX"], "allowed_segments": ["NSE_CM", "NSE_FO"],
        "supported_index_underlyings": ["NSE:NIFTY50-INDEX"],
        "allowed_strategies": ["BULL_CALL_DEBIT"],
        "completed_candle_conditions": ["15m and 1h close above EMA20"], "require_completed_candle": True,
        "required_alignment_values": ["FULL BULLISH ALIGNMENT", "FULL BEARISH ALIGNMENT"], "require_validated_contract": True,
        "require_active_expiry": True, "require_two_sided_liquidity": True,
        "require_complete_greeks_oi_volume": True, "require_valid_lot_tick": True, "require_defined_maximum_loss": True,
        "planning_capital": 100000, "max_daily_loss": 5000, "per_idea_risk": 2000, "risk_reserve": 1000, "max_concurrent_positions": 3,
        "max_concurrent_orders": 2, "minimum_reward_to_risk": 1.5, "order_type": "LIMIT",
        "max_limit_buffer_pct": 0.5, "trading_start": "09:30", "trading_end": "15:00",
        "min_dte": 1, "max_dte": 14, "max_bid_ask_spread_pct": 8,
        "require_stop_or_defined_risk": True, "require_target": True,
        "cooldown_minutes": 30, "stale_data_seconds": 15, "kill_switch_engaged": True,
        "halt_on_uncertain_status": True,
    }


class AutomationPolicyTests(unittest.TestCase):
    def service(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        now = lambda: datetime(2026, 8, 30, 11, 0).astimezone()
        audit = HashChainAuditLog(root / "audit.jsonl", now=now)
        return AutomationPolicyService(root / "profile.json", audit=audit, now=now)

    def test_policy_requires_completed_candles_and_uncertain_halt(self):
        policy = valid_policy(); policy["halt_on_uncertain_status"] = False
        with self.assertRaisesRegex(ValueError, "uncertain"):
            validate_automation_policy(policy)

    def test_paper_profile_needs_exact_ack_and_writes_valid_hash_chain(self):
        service = self.service(); preview = service.preview(valid_policy())
        with self.assertRaisesRegex(ValueError, "exact acknowledgement"):
            service.save(preview["preview_id"], "yes")
        result = service.save(preview["preview_id"], preview["acknowledgement_phrase"])
        self.assertTrue(result["profile"]["enabled"])
        self.assertEqual(result["profile"]["execution_mode"], "PAPER")
        self.assertTrue(result["audit_chain_valid"])

    @patch.dict(os.environ, {"SECTOR_PULSE_ENABLE_FYERS_UNATTENDED": "0"}, clear=False)
    def test_live_profile_cannot_activate_without_runtime_gate(self):
        service = self.service(); policy = valid_policy(); policy["execution_mode"] = "LIVE"
        preview = service.preview(policy)
        with self.assertRaisesRegex(PermissionError, "runtime-disabled"):
            service.save(preview["preview_id"], preview["acknowledgement_phrase"])

    def test_uncertain_status_engages_kill_switch_and_never_retries(self):
        service = self.service(); preview = service.preview(valid_policy())
        service.save(preview["preview_id"], preview["acknowledgement_phrase"])
        result = service.halt_uncertain("order-123")
        self.assertTrue(result["kill_switch_engaged"])
        self.assertFalse(result["automatic_retry"])
        self.assertFalse(service.current()["profile"]["enabled"])

    def test_every_future_order_fails_closed_without_fresh_fyers_preflight(self):
        service = self.service(); policy = valid_policy(); policy["kill_switch_engaged"] = False
        preview = service.preview(policy); service.save(preview["preview_id"], preview["acknowledgement_phrase"])
        result = service.evaluate_order({"symbol": "NSE:NIFTY50-INDEX"})
        self.assertFalse(result["allowed"])
        self.assertIn("fresh FYERS preflight is missing", result["reasons"])

    def test_tampered_profile_digest_fails_closed(self):
        service = self.service(); preview = service.preview(valid_policy())
        service.save(preview["preview_id"], preview["acknowledgement_phrase"])
        data = json.loads(service.profile_path.read_text()); data["max_daily_loss"] = 999999
        service.profile_path.write_text(json.dumps(data))
        self.assertFalse(service.current()["profile_digest_valid"])

    def test_paper_draft_is_forced_disabled_with_kill_switch(self):
        service = self.service(); policy = valid_policy(); policy.update({"enabled": True, "execution_mode": "LIVE", "kill_switch_engaged": False})
        result = service.save_draft(policy)
        self.assertTrue(result["draft"])
        self.assertFalse(result["profile"]["enabled"])
        self.assertEqual(result["profile"]["execution_mode"], "PAPER")
        self.assertTrue(result["profile"]["kill_switch_engaged"])
        self.assertEqual(result["profile"]["approval_mode"], "PAPER_DRAFT")


if __name__ == "__main__":
    unittest.main()
