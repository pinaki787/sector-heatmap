"""Disabled-by-default FYERS unattended-policy authoring and audit support.

This module never discovers signals or places orders.  It validates and persists
the bounded policy that a separate future runner would have to satisfy.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
from threading import Lock

from .config import _atomic_private_write


PROFILE_PATH = Path.home() / ".fyers" / "sector-heatmap" / "automation-profile.json"
AUDIT_PATH = Path.home() / ".fyers" / "sector-heatmap" / "automation-audit.jsonl"
ALLOWED_SEGMENTS = {"NSE_CM", "NSE_FO"}
ALLOWED_STRATEGIES = {"EQUITY_LONG", "EQUITY_SHORT", "BULL_CALL_DEBIT", "BEAR_PUT_DEBIT", "BULL_PUT_CREDIT", "BEAR_CALL_CREDIT"}
ALLOWED_UNIVERSE_MODES = {"ALIGNED_EQUITIES", "ALIGNED_OPTIONS", "ALIGNED_EQUITIES_AND_OPTIONS"}


def _policy_digest(policy):
    unsigned = {key: value for key, value in policy.items() if key not in {"saved_at", "policy_digest"}}
    return hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _finite(value, label, minimum=None, maximum=None, integer=False):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be numeric.") from error
    if not math.isfinite(number) or minimum is not None and number < minimum or maximum is not None and number > maximum:
        raise ValueError(f"{label} must be from {minimum} to {maximum}.")
    if integer and number != int(number):
        raise ValueError(f"{label} must be a whole number.")
    return int(number) if integer else number


def _clock(value, label):
    try:
        return datetime.strptime(str(value), "%H:%M").strftime("%H:%M")
    except ValueError as error:
        raise ValueError(f"{label} must use HH:MM.") from error


def validate_automation_policy(raw):
    """Return a canonical policy or reject any missing/unbounded control."""
    raw = raw if isinstance(raw, dict) else {}
    symbols = sorted({str(item).strip().upper() for item in raw.get("allowed_symbols", []) if str(item).strip()})
    segments = sorted({str(item).strip().upper() for item in raw.get("allowed_segments", []) if str(item).strip()})
    strategies = sorted({str(item).strip().upper() for item in raw.get("allowed_strategies", []) if str(item).strip()})
    conditions = [str(item).strip() for item in raw.get("completed_candle_conditions", []) if str(item).strip()]
    if not symbols or len(symbols) > 250 or any(not symbol.startswith("NSE:") or not symbol.endswith(("-EQ", "-INDEX")) for symbol in symbols):
        raise ValueError("Allow 1 to 250 exact FYERS NSE cash-equity or index-underlying symbols.")
    if not segments or not set(segments) <= ALLOWED_SEGMENTS:
        raise ValueError("Allowed segments must be a nonempty subset of NSE_CM and NSE_FO.")
    if not strategies or not set(strategies) <= ALLOWED_STRATEGIES:
        raise ValueError("Choose at least one supported strategy type.")
    if not conditions or len(conditions) > 12:
        raise ValueError("Provide 1 to 12 explicit completed-candle signal conditions.")
    daily_loss = _finite(raw.get("max_daily_loss"), "Maximum daily loss", 1, 5000)
    idea_risk = _finite(raw.get("per_idea_risk"), "Per-idea risk", 1, daily_loss)
    planning_capital = _finite(raw.get("planning_capital"), "Planning capital", 1, 1_000_000_000)
    risk_reserve = _finite(raw.get("risk_reserve"), "Risk reserve", 0, daily_loss)
    if idea_risk + risk_reserve > daily_loss:
        raise ValueError("Per-idea risk plus reserve must fit inside the maximum daily loss.")
    max_positions = _finite(raw.get("max_concurrent_positions"), "Maximum concurrent positions", 1, 20, True)
    max_orders = _finite(raw.get("max_concurrent_orders"), "Maximum concurrent orders", 1, 20, True)
    cooldown = _finite(raw.get("cooldown_minutes"), "Cooldown minutes", 1, 1440, True)
    stale_seconds = _finite(raw.get("stale_data_seconds"), "Stale-data threshold", 1, 300, True)
    min_dte = _finite(raw.get("min_dte"), "Minimum DTE", 0, 365, True)
    max_dte = _finite(raw.get("max_dte"), "Maximum DTE", min_dte, 365, True)
    min_rr = _finite(raw.get("minimum_reward_to_risk"), "Minimum reward-to-risk", 1, 10)
    max_spread = _finite(raw.get("max_bid_ask_spread_pct"), "Maximum bid/ask spread", 0.1, 20)
    price_buffer = _finite(raw.get("max_limit_buffer_pct"), "Maximum limit-price buffer", 0, 5)
    start, end = _clock(raw.get("trading_start"), "Trading start"), _clock(raw.get("trading_end"), "Trading end")
    if start >= end:
        raise ValueError("Trading start must be before trading end.")
    order_type = str(raw.get("order_type") or "").upper()
    if order_type != "LIMIT":
        raise ValueError("Unattended policy supports bounded LIMIT orders only.")
    if raw.get("require_completed_candle") is not True:
        raise ValueError("Completed-candle confirmation is mandatory.")
    if raw.get("require_stop_or_defined_risk") is not True or raw.get("require_target") is not True:
        raise ValueError("A stop or defined-risk spread and an explicit target are mandatory.")
    if raw.get("halt_on_uncertain_status") is not True:
        raise ValueError("Stop-on-uncertain-order-status is mandatory.")
    execution_mode = str(raw.get("execution_mode") or "PAPER").upper()
    if execution_mode not in {"PAPER", "LIVE"}:
        raise ValueError("Execution mode must be PAPER or LIVE.")
    universe_mode = str(raw.get("universe_mode") or "").upper()
    if universe_mode not in ALLOWED_UNIVERSE_MODES:
        raise ValueError("Choose aligned equities, aligned index options, or both as the policy universe.")
    index_underlyings = sorted({str(item).strip().upper() for item in raw.get("supported_index_underlyings", []) if str(item).strip()})
    if universe_mode in {"ALIGNED_OPTIONS", "ALIGNED_EQUITIES_AND_OPTIONS"} and (not index_underlyings or not set(index_underlyings) <= set(symbols)):
        raise ValueError("Index-option policies require exact supported index underlyings inside the symbol allowlist.")
    if universe_mode == "ALIGNED_EQUITIES_AND_OPTIONS" and not any(symbol.endswith("-EQ") for symbol in symbols):
        raise ValueError("The combined universe requires at least one exact NSE cash-equity symbol.")
    option_universe = str(raw.get("option_universe") or "").upper()
    if universe_mode in {"ALIGNED_OPTIONS", "ALIGNED_EQUITIES_AND_OPTIONS"} and option_universe != "INDEX_AND_STOCK_OPTIONS":
        raise ValueError("The options universe must explicitly select supported index and stock options.")
    if universe_mode in {"ALIGNED_OPTIONS", "ALIGNED_EQUITIES_AND_OPTIONS"} and raw.get("allow_stock_options_for_aligned_equities") is not True:
        raise ValueError("Stock options must remain limited to freshly aligned, exact cash-equity underlyings.")
    required_alignments = sorted({str(item).strip().upper() for item in raw.get("required_alignment_values", []) if str(item).strip()})
    if required_alignments != ["FULL BEARISH ALIGNMENT", "FULL BULLISH ALIGNMENT"]:
        raise ValueError("The policy must require exact full bullish or full bearish alignment.")
    if raw.get("require_validated_contract") is not True:
        raise ValueError("Fresh FYERS master and contract validation is mandatory for index options.")
    if raw.get("require_active_expiry") is not True or raw.get("require_two_sided_liquidity") is not True:
        raise ValueError("Active expiry and adequate two-sided bid/ask liquidity are mandatory for options.")
    if raw.get("require_complete_greeks_oi_volume") is not True or raw.get("require_valid_lot_tick") is not True:
        raise ValueError("Complete Greeks/OI/volume and valid lot/tick metadata are mandatory for options.")
    if raw.get("require_defined_maximum_loss") is not True:
        raise ValueError("Every option structure must have a defined maximum loss.")
    return {
        "schema": "sector-pulse-fyers-automation-policy/v1",
        "approval_mode": "UNATTENDED_POLICY_APPROVED",
        "enabled": bool(raw.get("enabled")),
        "execution_mode": execution_mode,
        "universe_mode": universe_mode,
        "option_universe": option_universe,
        "allow_stock_options_for_aligned_equities": bool(raw.get("allow_stock_options_for_aligned_equities")),
        "allowed_symbols": symbols,
        "supported_index_underlyings": index_underlyings,
        "allowed_segments": segments,
        "allowed_strategies": strategies,
        "completed_candle_conditions": conditions,
        "require_completed_candle": True,
        "required_alignment_values": required_alignments,
        "require_validated_contract": True,
        "require_active_expiry": True,
        "require_two_sided_liquidity": True,
        "require_complete_greeks_oi_volume": True,
        "require_valid_lot_tick": True,
        "require_defined_maximum_loss": True,
        "planning_capital": planning_capital,
        "max_daily_loss": daily_loss,
        "per_idea_risk": idea_risk,
        "risk_reserve": risk_reserve,
        "max_concurrent_positions": max_positions,
        "max_concurrent_orders": max_orders,
        "minimum_reward_to_risk": min_rr,
        "order_type": "LIMIT",
        "max_limit_buffer_pct": price_buffer,
        "trading_start": start,
        "trading_end": end,
        "min_dte": min_dte,
        "max_dte": max_dte,
        "max_bid_ask_spread_pct": max_spread,
        "require_stop_or_defined_risk": True,
        "require_target": True,
        "cooldown_minutes": cooldown,
        "stale_data_seconds": stale_seconds,
        "kill_switch_engaged": bool(raw.get("kill_switch_engaged", True)),
        "halt_on_uncertain_status": True,
        "automatic_retry": False,
    }


def policy_summary(policy):
    equity_count = sum(symbol.endswith("-EQ") for symbol in policy.get("allowed_symbols", []))
    return [
        f"Mode: {policy['execution_mode']} ({'enabled' if policy['enabled'] else 'disabled'}); kill switch: {'ENGAGED' if policy['kill_switch_engaged'] else 'released'}.",
        f"Universe: aligned cash equities plus supported index and stock options; {equity_count} exact NSE cash underlyings and {len(policy.get('supported_index_underlyings', []))} supported index underlyings. Stock options are permitted only for a currently aligned allowlisted equity.",
        f"Signals: completed 15m, 1h, Daily and Weekly candles must resolve to exact FULL BULLISH ALIGNMENT or FULL BEARISH ALIGNMENT; stale data is vetoed.",
        f"Risk: ₹{policy['planning_capital']:.2f} planning capital, ₹{policy['max_daily_loss']:.2f}/day, ₹{policy['per_idea_risk']:.2f}/idea, ₹{policy['risk_reserve']:.2f} reserve, {policy['max_concurrent_positions']} positions, {policy['max_concurrent_orders']} orders, minimum R:R 1:{policy['minimum_reward_to_risk']}.",
        f"Orders: LIMIT only, max buffer {policy['max_limit_buffer_pct']}%, max spread {policy['max_bid_ask_spread_pct']}%, mandatory stop/defined risk and target. Every option requires active expiry, exact chain/master contract, two-sided liquidity, complete Greeks/OI/volume, valid lot/tick and defined maximum loss.",
        f"Time/contracts: {policy['trading_start']}–{policy['trading_end']} IST, DTE {policy['min_dte']}–{policy['max_dte']}, cooldown {policy['cooldown_minutes']}m, stale veto {policy['stale_data_seconds']}s.",
        "Uncertain order status halts the policy; automatic retry is prohibited; every future order still needs fresh FYERS preflight.",
    ]


class HashChainAuditLog:
    def __init__(self, path=AUDIT_PATH, now=None):
        self.path = Path(path)
        self.now = now or datetime.now
        self.lock = Lock()

    def _rows(self):
        try:
            return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except FileNotFoundError:
            return []

    def append(self, event, detail):
        with self.lock:
            rows = self._rows()
            previous = rows[-1]["event_hash"] if rows else "GENESIS"
            body = {"timestamp": self.now().astimezone().isoformat(), "event": event, "detail": detail, "previous_hash": previous}
            body["event_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            rows.append(body)
            _atomic_private_write(self.path, "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
            return body

    def verify(self):
        previous = "GENESIS"
        try:
            rows = self._rows()
        except (OSError, ValueError, TypeError, KeyError):
            return False
        for row in rows:
            expected = dict(row); actual = expected.pop("event_hash", None)
            if expected.get("previous_hash") != previous or hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != actual:
                return False
            previous = actual
        return True


class AutomationPolicyService:
    """Authors policies only; it has no broker order-submission dependency."""

    def __init__(self, profile_path=PROFILE_PATH, audit=None, now=None):
        self.profile_path = Path(profile_path)
        self.now = now or datetime.now
        self.audit = audit or HashChainAuditLog(now=self.now)
        self.previews = {}

    def current(self):
        try:
            profile = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            profile = None
        profile_digest_valid = True
        if profile is not None and isinstance(profile, dict):
            profile_digest_valid = _policy_digest(profile) == profile.get("policy_digest")
        elif profile is not None:
            profile_digest_valid = False
            profile = {}
        return {"configured": profile is not None, "profile": profile, "human_readable_policy": policy_summary(profile) if profile else [], "profile_digest_valid": profile_digest_valid, "audit_chain_valid": self.audit.verify(), "live_runtime_enabled": os.getenv("SECTOR_PULSE_ENABLE_FYERS_UNATTENDED") == "1"}

    def preview(self, raw):
        policy = validate_automation_policy(raw)
        digest = _policy_digest(policy)
        preview_id = f"POLICY-{digest[:10].upper()}-{secrets.token_hex(2).upper()}"
        phrase = f"ACKNOWLEDGE {preview_id}"
        summary = policy_summary(policy)
        result = {"preview_id": preview_id, "policy_digest": digest, "policy": policy, "human_readable_policy": summary, "acknowledgement_phrase": phrase, "transmitted": False}
        self.previews[preview_id] = result
        return result

    def save(self, preview_id, acknowledgement):
        preview = self.previews.get(preview_id)
        if not preview or acknowledgement != preview["acknowledgement_phrase"]:
            raise ValueError("Type the exact acknowledgement phrase from the current policy preview.")
        policy = dict(preview["policy"])
        if policy["enabled"] and policy["execution_mode"] == "LIVE" and os.getenv("SECTOR_PULSE_ENABLE_FYERS_UNATTENDED") != "1":
            raise PermissionError("Live unattended activation is runtime-disabled. PAPER profiles may still be saved and enabled.")
        policy["saved_at"] = self.now().astimezone().isoformat()
        policy["policy_digest"] = preview["policy_digest"]
        _atomic_private_write(self.profile_path, json.dumps(policy, indent=2) + "\n")
        self.audit.append("POLICY_SAVED", {"policy_digest": policy["policy_digest"], "enabled": policy["enabled"], "execution_mode": policy["execution_mode"], "kill_switch_engaged": policy["kill_switch_engaged"]})
        self.previews.pop(preview_id, None)
        return {"saved": True, "profile": policy, "profile_digest_valid": self.current()["profile_digest_valid"], "audit_chain_valid": self.audit.verify()}

    def save_draft(self, raw):
        """Persist a disabled PAPER draft; activation still requires preview acknowledgement."""
        draft = dict(raw or {})
        draft.update({"enabled": False, "execution_mode": "PAPER", "kill_switch_engaged": True})
        policy = validate_automation_policy(draft)
        policy["approval_mode"] = "PAPER_DRAFT"
        policy["saved_at"] = self.now().astimezone().isoformat()
        policy["policy_digest"] = _policy_digest(policy)
        _atomic_private_write(self.profile_path, json.dumps(policy, indent=2) + "\n")
        self.audit.append("POLICY_DRAFT_SAVED", {"policy_digest": policy["policy_digest"], "enabled": False, "execution_mode": "PAPER", "kill_switch_engaged": True})
        return {"saved": True, "draft": True, "profile": policy, "human_readable_policy": policy_summary(policy), "profile_digest_valid": self.current()["profile_digest_valid"], "audit_chain_valid": self.audit.verify()}

    def evaluate_order(self, context):
        """Fail closed for every order a future unattended runner proposes."""
        current = self.current()
        policy = current.get("profile") or {}
        reasons = []
        if not current["audit_chain_valid"]:
            reasons.append("audit chain validation failed")
        if not current["profile_digest_valid"]:
            reasons.append("profile digest validation failed")
        if not policy.get("enabled"):
            reasons.append("automation profile is disabled")
        if policy.get("kill_switch_engaged"):
            reasons.append("kill switch is engaged")
        if context.get("fresh_fyers_preflight") is not True:
            reasons.append("fresh FYERS preflight is missing")
        if context.get("execution_status_uncertain"):
            self.halt_uncertain(context.get("reference", "unknown"))
            return {"allowed": False, "halted": True, "reasons": ["execution status is uncertain"]}
        policy_symbol = str(context.get("underlying_symbol") or context.get("symbol", "")).upper()
        if policy_symbol not in policy.get("allowed_symbols", []):
            reasons.append("symbol is outside the allowlist")
        if str(context.get("segment", "")).upper() not in policy.get("allowed_segments", []):
            reasons.append("segment is outside the allowlist")
        if str(context.get("strategy", "")).upper() not in policy.get("allowed_strategies", []):
            reasons.append("strategy is outside the allowlist")
        if context.get("completed_candle_conditions_met") is not True:
            reasons.append("completed-candle conditions are not met")
        if str(context.get("full_alignment", "")).upper() not in policy.get("required_alignment_values", []):
            reasons.append("exact full bullish/bearish alignment is not met")
        if str(context.get("segment", "")).upper() == "NSE_FO" and context.get("contract_validated") is not True:
            reasons.append("fresh FYERS derivative contract validation is missing")
        if str(context.get("segment", "")).upper() == "NSE_FO":
            option_checks = {
                "active option expiry is missing": context.get("active_expiry") is True,
                "adequate two-sided option liquidity is missing": context.get("two_sided_liquidity_valid") is True,
                "complete option Greeks/OI/volume are missing": context.get("complete_greeks_oi_volume") is True,
                "valid option lot/tick metadata is missing": context.get("lot_tick_valid") is True,
                "defined option maximum loss is missing": context.get("defined_maximum_loss") is True,
            }
            reasons.extend(message for message, passed in option_checks.items() if not passed)
        if float(context.get("data_age_seconds", math.inf)) > policy.get("stale_data_seconds", 0):
            reasons.append("market data is stale")
        if float(context.get("worst_case_risk", math.inf)) > policy.get("per_idea_risk", 0):
            reasons.append("per-idea risk is exceeded")
        if float(context.get("daily_realized_plus_open_risk", math.inf)) + float(context.get("worst_case_risk", math.inf)) + policy.get("risk_reserve", math.inf) > policy.get("max_daily_loss", 0):
            reasons.append("daily loss budget is exceeded")
        if int(context.get("open_positions", 10**9)) >= policy.get("max_concurrent_positions", 0):
            reasons.append("maximum concurrent positions is reached")
        if int(context.get("open_orders", 10**9)) >= policy.get("max_concurrent_orders", 0):
            reasons.append("maximum concurrent orders is reached")
        if str(context.get("order_type", "")).upper() != "LIMIT":
            reasons.append("order is not a bounded LIMIT")
        if float(context.get("limit_buffer_pct", math.inf)) > policy.get("max_limit_buffer_pct", 0):
            reasons.append("limit-price buffer is exceeded")
        if float(context.get("bid_ask_spread_pct", math.inf)) > policy.get("max_bid_ask_spread_pct", 0):
            reasons.append("bid/ask spread is exceeded")
        if float(context.get("reward_to_risk", 0)) < policy.get("minimum_reward_to_risk", math.inf):
            reasons.append("minimum reward-to-risk is not met")
        if context.get("has_stop_or_defined_risk") is not True or context.get("has_target") is not True:
            reasons.append("mandatory stop/defined risk or target is missing")
        if str(context.get("segment", "")).upper() == "NSE_FO":
            dte = int(context.get("dte", -1))
            if not policy.get("min_dte", 0) <= dte <= policy.get("max_dte", -1):
                reasons.append("contract expiry is outside the DTE filter")
        now = self.now().astimezone()
        if not policy.get("trading_start", "99:99") <= now.strftime("%H:%M") <= policy.get("trading_end", "00:00"):
            reasons.append("current time is outside trading hours")
        if float(context.get("minutes_since_last_order", 0)) < policy.get("cooldown_minutes", math.inf):
            reasons.append("cooldown has not elapsed")
        result = {"allowed": not reasons, "halted": False, "reasons": reasons, "policy_digest": policy.get("policy_digest")}
        self.audit.append("ORDER_POLICY_EVALUATED", {"reference": str(context.get("reference", "")), **result})
        return result

    def halt(self, reference, reason):
        current = self.current().get("profile")
        if current:
            current["enabled"] = False
            current["kill_switch_engaged"] = True
            current["halt_reason"] = str(reason)
            current["saved_at"] = self.now().astimezone().isoformat()
            current["policy_digest"] = _policy_digest(current)
            _atomic_private_write(self.profile_path, json.dumps(current, indent=2) + "\n")
        self.audit.append("POLICY_HALTED", {"reference": str(reference), "reason": str(reason), "automatic_retry": False})
        return {"halted": True, "reason": str(reason), "kill_switch_engaged": True, "automatic_retry": False}

    def halt_uncertain(self, reference):
        return self.halt(reference, "EXECUTION_STATUS_UNCERTAIN")
