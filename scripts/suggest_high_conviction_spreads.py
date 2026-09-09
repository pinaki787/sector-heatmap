#!/usr/bin/env python3
"""Read-only FYERS defined-risk spread proposals for current bullish candidates."""
from __future__ import annotations

from datetime import datetime
import json
import sys

from fyers_apiv3 import fyersModel

from sector_heatmap.config import load_config
from sector_heatmap.handoff import FyersFoMaster, build_defined_risk_spreads, fetch_fyers_chain
from sector_heatmap.market_calendar import IST


# Underlying invalidations come from the completed-candle analyses, never from
# option premium alone. No quantity is calculated without a user risk budget.
CANDIDATES = {
    "NSE:IDFCFIRSTB-EQ": 86.50,
    "NSE:SAGILITY-EQ": 46.55,
    "NSE:BPCL-EQ": 316.50,
    "NSE:SOLARINDS-EQ": 21280.00,
}


def requested_candidates(argv):
    """Optional read-only candidates in SYMBOL=UNDERLYING_INVALIDATION form."""
    candidates = dict(CANDIDATES)
    for index, argument in enumerate(argv):
        if argument != "--candidate":
            continue
        if index + 1 >= len(argv) or "=" not in argv[index + 1]:
            raise ValueError("--candidate requires SYMBOL=INVALIDATION, for example NSE:GRASIM-EQ=3290")
        symbol, invalidation = argv[index + 1].rsplit("=", 1)
        candidates[symbol] = float(invalidation)
    return candidates


def main():
    ignore_reward_to_risk = "--ignore-reward-to-risk" in sys.argv[1:]
    summary_only = "--summary" in sys.argv[1:]
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("No reusable FYERS token is configured.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    master = FyersFoMaster()
    results = {}
    for underlying, invalidation in requested_candidates(sys.argv[1:]).items():
        try:
            chain, expiry = fetch_fyers_chain(client, underlying, strike_count=10)
            option_symbols = [row.get("symbol") for row in chain.get("data", {}).get("optionsChain", []) if row.get("option_type") in {"CE", "PE"}]
            result = build_defined_risk_spreads(
                chain, expiry, master.lookup(option_symbols), "BULLISH",
                {
                    "invalidation": invalidation,
                    "stop_basis": "price",
                    # Comparison-only mode retains all contract-liquidity checks.
                    "minimum_reward_to_risk": 0.01 if ignore_reward_to_risk else 1.0,
                },
            )
            results[underlying] = result
        except Exception as error:
            results[underlying] = {"status": "UNAVAILABLE", "reason": str(error), "proposals": []}
    if summary_only:
        results = {
            symbol: {
                key: result.get(key)
                for key in ("status", "spot", "expiry", "reason", "proposals")
            }
            for symbol, result in results.items()
        }
    print(json.dumps({"fetched_at": datetime.now(IST).isoformat(), "reward_to_risk_filter": not ignore_reward_to_risk, "results": results}, indent=2))


if __name__ == "__main__":
    main()
