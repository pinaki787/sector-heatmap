#!/usr/bin/env python3
"""Save the requested disabled FYERS PAPER policy draft.

The command performs read-only index-option support checks and never enables a
LIVE runtime flag or calls an order API.
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
from sector_heatmap.handoff import FyersFoMaster, fetch_fyers_chain
from sector_heatmap.sectors import BENCHMARK_SYMBOL, SECTOR_DEFINITIONS, equity_symbol


INDEX_UNDERLYINGS = [BENCHMARK_SYMBOL, "NSE:NIFTYBANK-INDEX", "NSE:FINNIFTY-INDEX"]


def exact_equity_universe():
    return sorted({equity_symbol(item.ticker) for sector in SECTOR_DEFINITIONS for item in sector.constituents})


def validate_index_option_support(client):
    master = FyersFoMaster()
    validation = {}
    for underlying in INDEX_UNDERLYINGS:
        chain, expiry = fetch_fyers_chain(client, underlying)
        option_rows = [row for row in chain.get("data", {}).get("optionsChain", []) if row.get("option_type") in {"CE", "PE"} and row.get("symbol")]
        records = master.lookup([row["symbol"] for row in option_rows])
        valid = [row for row in option_rows if row["symbol"] in records and str(records[row["symbol"]].get("expiry_epoch")) == str(expiry.get("expiry"))]
        if not valid:
            raise RuntimeError(f"No exact current FYERS option contract passed chain/master validation for {underlying}.")
        validation[underlying] = {"expiry": expiry.get("date"), "validated_contracts": len(valid)}
    return validation


def main():
    if os.getenv("SECTOR_PULSE_ENABLE_FYERS_UNATTENDED") == "1" or os.getenv("SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS") == "1":
        raise RuntimeError("Refusing to save a PAPER draft while a LIVE runtime gate is enabled.")
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if not token or ":" not in token:
        raise RuntimeError("A valid private FYERS token is required for read-only index-option validation.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    profile = client.get_profile()
    if not isinstance(profile, dict) or profile.get("s") != "ok":
        raise RuntimeError(profile.get("message", "FYERS profile validation failed.") if isinstance(profile, dict) else "FYERS profile validation failed.")
    option_validation = validate_index_option_support(client)
    equities = exact_equity_universe()
    policy = {
        "enabled": False,
        "execution_mode": "PAPER",
        "universe_mode": "ALIGNED_EQUITIES_AND_OPTIONS",
        "option_universe": "INDEX_AND_STOCK_OPTIONS",
        "allow_stock_options_for_aligned_equities": True,
        "allowed_symbols": equities + INDEX_UNDERLYINGS,
        "supported_index_underlyings": INDEX_UNDERLYINGS,
        "allowed_segments": ["NSE_CM", "NSE_FO"],
        "allowed_strategies": ["EQUITY_LONG", "EQUITY_SHORT", "BULL_CALL_DEBIT", "BEAR_PUT_DEBIT"],
        "completed_candle_conditions": [
            "15m, 1h, Daily and Weekly completed candles must all be available and fresh for the candidate.",
            "Every timeframe must agree as exact FULL BULLISH ALIGNMENT or exact FULL BEARISH ALIGNMENT.",
            "Equities and stock-option underlyings must come from the direction-matching official-weight contributor scan; index options use only a supported validated index underlying.",
        ],
        "require_completed_candle": True,
        "required_alignment_values": ["FULL BULLISH ALIGNMENT", "FULL BEARISH ALIGNMENT"],
        "require_validated_contract": True,
        "require_active_expiry": True,
        "require_two_sided_liquidity": True,
        "require_complete_greeks_oi_volume": True,
        "require_valid_lot_tick": True,
        "require_defined_maximum_loss": True,
        "planning_capital": 100000,
        "max_daily_loss": 5000,
        "per_idea_risk": 2000,
        "risk_reserve": 1000,
        "max_concurrent_positions": 3,
        "max_concurrent_orders": 2,
        "minimum_reward_to_risk": 1.0,
        "order_type": "LIMIT",
        "max_limit_buffer_pct": 0.5,
        "trading_start": "09:30",
        "trading_end": "15:00",
        "min_dte": 1,
        "max_dte": 14,
        "max_bid_ask_spread_pct": 8,
        "require_stop_or_defined_risk": True,
        "require_target": True,
        "cooldown_minutes": 30,
        "stale_data_seconds": 15,
        "kill_switch_engaged": True,
        "halt_on_uncertain_status": True,
    }
    result = AutomationPolicyService().save_draft(policy)
    print(json.dumps({
        "saved": result["saved"], "draft": result["draft"],
        "enabled": result["profile"]["enabled"], "execution_mode": result["profile"]["execution_mode"],
        "kill_switch_engaged": result["profile"]["kill_switch_engaged"],
        "equity_symbols": len(equities), "index_option_validation": option_validation,
        "policy_digest": result["profile"]["policy_digest"],
        "profile_digest_valid": result["profile_digest_valid"], "audit_chain_valid": result["audit_chain_valid"],
        "order_submitted": False, "live_flags_changed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
