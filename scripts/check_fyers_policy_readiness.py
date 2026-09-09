#!/usr/bin/env python3
"""Read-only readiness check for the FYERS unattended policy.

This command never saves a policy, changes a runtime gate, or submits an order.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fyers_apiv3 import fyersModel

from sector_heatmap.automation import AutomationPolicyService
from sector_heatmap.config import load_config


def readiness():
    policy_state = AutomationPolicyService().current()
    profile = policy_state.get("profile") or {}
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    session_valid = False
    session_message = "A private FYERS access token was not found."
    if token and ":" in token:
        app_id, access_token = token.split(":", 1)
        response = fyersModel.FyersModel(client_id=app_id, token=access_token).get_profile()
        session_valid = isinstance(response, dict) and response.get("s") == "ok"
        session_message = "FYERS profile validated." if session_valid else (response.get("message") if isinstance(response, dict) else "Invalid FYERS profile response.")

    required = {
        "saved acknowledged policy": policy_state.get("configured") is True,
        "valid policy digest": policy_state.get("profile_digest_valid") is True and policy_state.get("configured") is True,
        "valid audit hash chain": policy_state.get("audit_chain_valid") is True,
        "profile enabled": profile.get("enabled") is True,
        "LIVE execution mode": profile.get("execution_mode") == "LIVE",
        "released kill switch": profile.get("kill_switch_engaged") is False,
        "combined aligned equities and options universe": profile.get("universe_mode") == "ALIGNED_EQUITIES_AND_OPTIONS" and profile.get("option_universe") == "INDEX_AND_STOCK_OPTIONS",
        "allowed symbols": bool(profile.get("allowed_symbols")),
        "allowed segments": bool(profile.get("allowed_segments")),
        "allowed strategies": bool(profile.get("allowed_strategies")),
        "completed-candle conditions": bool(profile.get("completed_candle_conditions")) and profile.get("require_completed_candle") is True,
        "bounded planning/daily/idea/reserve risk": bool(profile.get("planning_capital")) and bool(profile.get("max_daily_loss")) and bool(profile.get("per_idea_risk")) and profile.get("risk_reserve") is not None,
        "bounded concurrent positions/orders": bool(profile.get("max_concurrent_positions")) and bool(profile.get("max_concurrent_orders")),
        "LIMIT order protections": profile.get("order_type") == "LIMIT" and profile.get("max_limit_buffer_pct") is not None,
        "trading window": bool(profile.get("trading_start")) and bool(profile.get("trading_end")),
        "expiry/contract filters": profile.get("min_dte") is not None and profile.get("max_dte") is not None and profile.get("require_validated_contract") is True,
        "complete option evidence gates": profile.get("require_active_expiry") is True and profile.get("require_two_sided_liquidity") is True and profile.get("require_complete_greeks_oi_volume") is True and profile.get("require_valid_lot_tick") is True and profile.get("require_defined_maximum_loss") is True,
        "mandatory stop/defined risk and target": profile.get("require_stop_or_defined_risk") is True and profile.get("require_target") is True,
        "cooldown and stale-data veto": bool(profile.get("cooldown_minutes")) and bool(profile.get("stale_data_seconds")),
        "halt on uncertain status": profile.get("halt_on_uncertain_status") is True and profile.get("automatic_retry") is False,
        "unattended runtime gate": os.getenv("SECTOR_PULSE_ENABLE_FYERS_UNATTENDED") == "1",
        "live-order runtime gate": os.getenv("SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS") == "1",
        "valid FYERS session/profile": session_valid,
    }
    return {
        "ready_to_activate": all(required.values()),
        "policy_evaluation_only": True,
        "order_submitted": False,
        "session_message": session_message,
        "checks": required,
        "missing_conditions": [name for name, passed in required.items() if not passed],
    }


if __name__ == "__main__":
    result = readiness()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ready_to_activate"] else 2)
