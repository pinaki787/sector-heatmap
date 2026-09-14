from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sector_heatmap.handoff import (
    apply_invalidation_choice, build_defined_risk_spreads, build_equity_opportunity, evidence_conviction, risk_budget, size_equity_candidate,
    validate_handoff_request, validate_risk_policy,
)


def chain_leg(symbol, strike, option_type, bid, ask, oi=1000, volume=200):
    return {
        "symbol": symbol,
        "fyToken": f"fy-{symbol}",
        "strike_price": strike,
        "option_type": option_type,
        "ltp": (bid + ask) / 2,
        "bid": bid,
        "ask": ask,
        "oi": oi,
        "volume": volume,
        "greeks": {"delta": 0.5 if option_type == "CE" else -0.5, "gamma": 0.02, "theta": -1.2, "vega": 0.8, "iv": 18.0},
    }


class HandoffRiskTests(unittest.TestCase):
    def test_codex_is_the_default_analysis_handoff_recipient(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('name="recipient" value="codex" checked', dashboard)
        self.assertNotIn('name="recipient" value="chatgpt" checked', dashboard)

    def test_candidate_stop_field_is_auto_populated_and_uses_exact_price_basis(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('value="${escapeHtml(derived.price)}"', dashboard)
        self.assertIn("stop_basis: 'price'", dashboard)
        self.assertIn('Stop / thesis invalidation', dashboard)

    def test_handoff_has_mutually_exclusive_cash_and_stock_option_routes(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('name="instrument-route" value="cash_equity" checked', dashboard)
        self.assertIn('name="instrument-route" value="stock_options"', dashboard)
        self.assertNotIn('id="include-options"', dashboard)
        self.assertIn("instrument_route: instrumentRoute", dashboard)
        self.assertIn("instrument_route: selectedInstrumentRoute()", dashboard)

    def test_reopening_a_recommendation_reuses_its_ticket_entry(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn("const ticketKey = `${ticket.candidate.symbol}|${ticket.proposal.label}|${ticket.options.expiry_iso || ''}`", dashboard)
        self.assertIn("if (index < 0) index = ticketProposals.push(ticket) - 1", dashboard)

    def aligned_candidate(self):
        states = {
            name: {"label": "STRONG BULLISH", "close": 100, "ema20": 95, "atr": 4, "adx": 31,
                   "relative_strength_state": "OUTPERFORMING", "data_quality": "FRESH", "reasons": []}
            for name in ("15m", "1h", "daily", "weekly")
        }
        return {"key": "stock:TEST", "kind": "stock", "symbol": "NSE:TEST-EQ", "name": "Test", "price": 100,
                "direction": "BULLISH", "mtf_alignment": "FULL BULLISH ALIGNMENT", "data_quality": "FRESH", "timeframe_states": states}

    def policy(self):
        return validate_risk_policy({"planning_capital": 100000, "daily_loss_limit": 5000, "idea_risk_limit": 2000,
            "risk_reserve": 1000, "max_simultaneous_positions": 3, "minimum_reward_to_risk": 1.5,
            "enforce_risk_controls": True, "enforce_minimum_reward_to_risk": True,
            "stop_basis": "price", "order_type": "LIMIT"})

    def test_equity_proposal_recommends_structure_but_requires_acceptance(self):
        candidate = self.aligned_candidate()
        opportunity = build_equity_opportunity(candidate, self.policy())
        self.assertEqual(opportunity["status"], "REQUIRES_INVALIDATION")
        self.assertEqual(opportunity["recommended_invalidation"]["method"], "structure")
        self.assertIsNone(opportunity["active_invalidation"])
        self.assertEqual(set(opportunity["invalidation_choices"]), {"structure", "percent", "atr", "custom"})
        accepted = apply_invalidation_choice(candidate, opportunity, self.policy(), {"method": "percent", "value": 2}, tick_size=0.05)
        self.assertEqual(accepted["price"], 98)
        self.assertEqual(accepted["target"], 103)
        self.assertGreater(accepted["quantity"], 0)

    def test_bearish_structure_stop_is_derived_above_completed_trigger(self):
        candidate = self.aligned_candidate()
        candidate["direction"] = "BEARISH"
        candidate["mtf_alignment"] = "FULL BEARISH ALIGNMENT"
        for state in candidate["timeframe_states"].values():
            state.update({"label": "STRONG BEARISH", "close": 100, "ema20": 104, "atr": 5})
        opportunity = build_equity_opportunity(candidate, self.policy())
        self.assertEqual(opportunity["recommended_invalidation"]["price"], 104)
        self.assertGreater(opportunity["recommended_invalidation"]["price"], opportunity["entry"])

    def test_missing_completed_atr_fails_closed_without_structural_stop(self):
        candidate = self.aligned_candidate()
        candidate["timeframe_states"]["daily"]["atr"] = None
        opportunity = build_equity_opportunity(candidate, self.policy())
        self.assertEqual(opportunity["status"], "EXCLUDED")
        self.assertIn("Daily ATR", opportunity["reason"])

    def test_conviction_is_transparent_evidence_grade(self):
        candidate = self.aligned_candidate()
        opportunity = build_equity_opportunity(candidate, self.policy())
        grade = evidence_conviction(candidate, opportunity)
        self.assertEqual(grade["rating"], "High")
        self.assertIn("four completed timeframes agree", grade["rationale"])
        self.assertIn("not a probability", grade["advisory"])

    def test_risk_budget_never_infers_missing_max_loss(self):
        self.assertEqual(risk_budget(100000, None, "rupees"), (None, "Set an explicit maximum loss per idea."))
        self.assertEqual(risk_budget(100000, 2, "percent"), (2000.0, None))

    def test_equity_requires_invalidation_and_shows_one_to_one_target(self):
        candidate = {"price": 100, "direction": "BULLISH"}
        missing = size_equity_candidate(candidate, {"planning_capital": 100000, "max_loss_value": 2000, "max_loss_unit": "rupees"})
        self.assertEqual(missing["status"], "REQUIRES_RISK_INPUTS")
        sized = size_equity_candidate(candidate, {"planning_capital": 100000, "max_loss_value": 2000, "max_loss_unit": "rupees", "invalidation": 95, "enforce_risk_controls": True, "enforce_minimum_reward_to_risk": True, "minimum_reward_to_risk": 1})
        self.assertEqual(sized["status"], "SIZED")
        self.assertEqual(sized["minimum_target"], 105.0)
        self.assertEqual(sized["quantity"], 200)  # 20% per-idea capital cap is tighter than risk quantity.
        self.assertEqual(sized["limited_by"], "conservative simultaneous-exposure cap")

    def test_recipient_action_and_funds_confirmation_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "recipient"):
            validate_handoff_request({"action": "preview", "candidate_keys": ["stock:A"]})
        with self.assertRaisesRegex(ValueError, "Confirm funds"):
            validate_handoff_request({"recipient": "codex", "action": "export", "candidate_keys": ["stock:A"], "include_funds": True})
        self.assertEqual(validate_handoff_request({"recipient": "chatgpt", "action": "preview", "candidate_keys": ["stock:A"]})[:3], ("chatgpt", "preview", ["stock:A"]))

    def test_editable_policy_drives_percent_stop_and_position_cap(self):
        policy = validate_risk_policy({
            "planning_capital": 100000, "daily_loss_limit": 4000, "idea_risk_limit": 1500,
            "risk_reserve": 500, "max_simultaneous_positions": 5,
            "minimum_reward_to_risk": 2, "enforce_risk_controls": True, "enforce_minimum_reward_to_risk": True, "stop_basis": "percent", "order_type": "LIMIT",
        })
        sized = size_equity_candidate(
            {"price": 100, "direction": "BULLISH"},
            {**policy, "max_loss_value": policy["idea_risk_limit"], "max_loss_unit": "rupees", "invalidation": 5},
        )
        self.assertEqual(sized["invalidation"], 95)
        self.assertEqual(sized["quantity"], 120)
        self.assertEqual(sized["minimum_target"], 110)
        self.assertEqual(sized["capital_assumption"]["max_simultaneous_ideas"], 5)


class DefinedRiskSpreadTests(unittest.TestCase):
    def setUp(self):
        self.expiry = {"date": "03-09-2026", "expiry": "1788422400"}
        rows = [{"symbol": "NSE:TEST-EQ", "option_type": "", "strike_price": -1, "ltp": 100}]
        rows += [
            chain_leg("CE95", 95, "CE", 5.5, 6.0),
            chain_leg("CE100", 100, "CE", 4.5, 4.8),
            chain_leg("CE105", 105, "CE", 1.4, 1.6),
            chain_leg("PE95", 95, "PE", 0.8, 1.0),
            chain_leg("PE100", 100, "PE", 4.2, 4.4),
            chain_leg("PE105", 105, "PE", 6.2, 6.5),
        ]
        self.chain = {"s": "ok", "data": {"optionsChain": rows}}
        self.master = {
            row["symbol"]: {
                "exchange_token": row["symbol"], "fy_token": f"fy-{row['symbol']}",
                "lot_size": 50, "tick_size": 0.05, "expiry_epoch": self.expiry["expiry"],
            }
            for row in rows if row.get("option_type")
        }

    def test_spreads_require_exact_contracts_greeks_liquidity_and_reward_gate(self):
        result = build_defined_risk_spreads(
            self.chain, self.expiry, self.master, "BULLISH",
            {"planning_capital": 100000, "max_loss_value": 2000, "max_loss_unit": "rupees", "invalidation": 95, "enforce_risk_controls": True, "enforce_minimum_reward_to_risk": True, "minimum_reward_to_risk": 1},
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["expiry_iso"], "2026-09-03")
        self.assertTrue(result["proposals"])
        self.assertTrue(all(proposal["reward_to_risk"] >= 1.0 for proposal in result["proposals"]))
        self.assertTrue(all(proposal["sizing"]["lots"] is not None for proposal in result["proposals"]))

    def test_missing_master_never_becomes_a_live_proposal(self):
        result = build_defined_risk_spreads(self.chain, self.expiry, {}, "BULLISH", {})
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertTrue(result["rejected_contracts"])

    def test_user_minimum_reward_gate_and_percent_invalidation_are_applied(self):
        result = build_defined_risk_spreads(
            self.chain, self.expiry, self.master, "BULLISH",
            {"planning_capital": 100000, "max_loss_value": 2000, "max_loss_unit": "rupees", "invalidation": 5, "stop_basis": "percent", "minimum_reward_to_risk": 2.5, "enforce_risk_controls": True, "enforce_minimum_reward_to_risk": True},
        )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertTrue(result["rejected_proposals"])
        for rejected in result["rejected_proposals"]:
            self.assertIn("analyzed R:R", rejected["reason"])
            self.assertIn("vs hard gate 1:2.5", rejected["reason"])
            self.assertEqual(rejected["hard_gate_reward_to_risk"], 2.5)


if __name__ == "__main__":
    unittest.main()
