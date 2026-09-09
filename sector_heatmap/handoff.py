"""Local analysis handoff and read-only FYERS option-spread construction."""

from __future__ import annotations

import csv
from datetime import datetime
import io
import math
from pathlib import Path
import time
from typing import Any

import requests

from .config import _atomic_private_write


HANDOFF_RECIPIENTS = {"chatgpt", "codex"}
HANDOFF_ACTIONS = {"preview", "export"}
FULL_ALIGNMENTS = {"FULL BULLISH ALIGNMENT", "FULL BEARISH ALIGNMENT"}
FYERS_FO_MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"
FYERS_FO_MASTER_CACHE = Path.home() / ".fyers" / "sym_master" / "NSE_FO.csv"
FYERS_CM_MASTER_URL = "https://public.fyers.in/sym_details/NSE_CM.csv"
FYERS_CM_MASTER_CACHE = Path.home() / ".fyers" / "sym_master" / "NSE_CM.csv"
MAX_SELECTED_CANDIDATES = 6
MAX_SPREAD_PCT = 12.0
MIN_OPEN_INTEREST = 100
MIN_VOLUME = 1
MIN_REWARD_TO_RISK = 1.0
MAX_INITIAL_GROSS_EXPOSURE_PCT = 60.0
MAX_SIMULTANEOUS_IDEAS = 3
MAX_DAILY_LOSS = 5000.0
MAX_CONFIGURED_POSITIONS = 20


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def risk_budget(planning_capital, max_loss_value, max_loss_unit):
    """Return a rupee risk budget only from explicit user-supplied risk inputs."""
    maximum = _positive_number(max_loss_value)
    if maximum is None:
        return None, "Set an explicit maximum loss per idea."
    if max_loss_unit == "rupees":
        return round(maximum, 2), None
    if max_loss_unit == "percent":
        capital = _positive_number(planning_capital)
        if capital is None:
            return None, "Set planning capital before using a percentage maximum loss."
        if maximum > 100:
            return None, "Maximum loss percentage must be 100 or less."
        return round(capital * maximum / 100, 2), None
    return None, "Choose whether maximum loss is entered in rupees or percent."


def validate_risk_policy(policy):
    """Validate user-editable planning controls without weakening hard safety caps."""
    policy = policy if isinstance(policy, dict) else {}
    planning_capital = _positive_number(policy.get("planning_capital"))
    daily_loss_limit = _positive_number(policy.get("daily_loss_limit"))
    idea_risk_limit = _positive_number(policy.get("idea_risk_limit"))
    reserve = float(policy.get("risk_reserve", -1)) if str(policy.get("risk_reserve", "")).strip() else -1
    max_positions_value = _positive_number(policy.get("max_simultaneous_positions"))
    minimum_rr = _positive_number(policy.get("minimum_reward_to_risk"))
    max_positions = int(max_positions_value or 0)
    if planning_capital is None:
        raise ValueError("Planning capital must be positive.")
    if daily_loss_limit is None or daily_loss_limit > MAX_DAILY_LOSS:
        raise ValueError(f"Daily loss must be positive and no greater than ₹{MAX_DAILY_LOSS:.0f}.")
    if idea_risk_limit is None or not math.isfinite(reserve) or reserve < 0 or idea_risk_limit + reserve > daily_loss_limit:
        raise ValueError("Per-idea risk and a nonnegative reserve must fit inside the daily loss limit.")
    if max_positions_value != max_positions or not 1 <= max_positions <= MAX_CONFIGURED_POSITIONS:
        raise ValueError(f"Maximum simultaneous positions must be a whole number from 1 to {MAX_CONFIGURED_POSITIONS}.")
    if minimum_rr is None or not 1 <= minimum_rr <= 10:
        raise ValueError("Minimum reward-to-risk must be from 1:1 to 1:10.")
    stop_basis = str(policy.get("stop_basis") or "").lower()
    if stop_basis not in {"price", "percent"}:
        raise ValueError("Stop basis must be exact price or percent from entry/spot.")
    order_type = str(policy.get("order_type") or "").upper()
    if order_type not in {"LIMIT", "MARKET"}:
        raise ValueError("Order-type preference must be LIMIT or MARKET.")
    return {
        "planning_capital": planning_capital, "daily_loss_limit": daily_loss_limit,
        "idea_risk_limit": idea_risk_limit, "risk_reserve": reserve,
        "max_simultaneous_positions": max_positions, "minimum_reward_to_risk": minimum_rr,
        "stop_basis": stop_basis, "order_type": order_type,
    }


def _invalidation_price(entry, direction, risk):
    value = _positive_number(risk.get("invalidation"))
    basis = str(risk.get("stop_basis") or "price").lower()
    if value is None:
        return None, "Set an explicit stop/invalidation for this idea."
    if basis == "percent":
        if value > 50:
            return None, "Percent stop distance must be no greater than 50%."
        return round(entry * (1 - value / 100 if direction == "BULLISH" else 1 + value / 100), 6), None
    if basis != "price":
        return None, "Choose exact price or percent stop basis."
    return value, None


def size_equity_candidate(candidate, risk, available_funds=None):
    """Calculate shares from explicit max loss and directional invalidation only."""
    entry = _positive_number(candidate.get("price"))
    invalidation, invalidation_error = _invalidation_price(entry, candidate.get("direction"), risk) if entry is not None else (None, None)
    budget, error = risk_budget(
        risk.get("planning_capital"), risk.get("max_loss_value"), risk.get("max_loss_unit")
    )
    reasons = []
    if error:
        reasons.append(error)
    if entry is None:
        reasons.append("A current positive equity price is required.")
    if invalidation_error:
        reasons.append(invalidation_error)
    direction = candidate.get("direction")
    if entry is not None and invalidation is not None:
        if direction == "BULLISH" and invalidation >= entry:
            reasons.append("Bullish invalidation must be below the current price.")
        if direction == "BEARISH" and invalidation <= entry:
            reasons.append("Bearish invalidation must be above the current price.")
    if reasons:
        return {"status": "REQUIRES_RISK_INPUTS", "quantity": None, "reasons": reasons}

    per_share_risk = abs(entry - invalidation)
    risk_quantity = math.floor(budget / per_share_risk)
    planning_capital = _positive_number(risk.get("planning_capital"))
    capital_base = planning_capital
    funds = _positive_number(available_funds)
    if funds is not None:
        capital_base = min(capital_base, funds) if capital_base is not None else funds
    max_positions = int(_positive_number(risk.get("max_simultaneous_positions")) or MAX_SIMULTANEOUS_IDEAS)
    minimum_rr = _positive_number(risk.get("minimum_reward_to_risk")) or MIN_REWARD_TO_RISK
    per_idea_capital = (
        capital_base * MAX_INITIAL_GROSS_EXPOSURE_PCT / 100 / max_positions
        if capital_base is not None
        else None
    )
    capital_quantity = math.floor(per_idea_capital / entry) if per_idea_capital is not None else risk_quantity
    quantity = min(risk_quantity, capital_quantity)
    limited_by = "maximum loss"
    if capital_quantity < risk_quantity:
        limited_by = "conservative simultaneous-exposure cap"
    if quantity < 1:
        return {
            "status": "NO_SIZE_AVAILABLE",
            "quantity": 0,
            "risk_budget": budget,
            "per_share_risk": round(per_share_risk, 4),
            "reasons": ["The explicit loss budget does not support one share at this invalidation."],
        }
    target = entry + minimum_rr * per_share_risk if direction == "BULLISH" else entry - minimum_rr * per_share_risk
    return {
        "status": "SIZED",
        "quantity": quantity,
        "entry_reference": entry,
        "invalidation": invalidation,
        "risk_budget": budget,
        "per_share_risk": round(per_share_risk, 4),
        "estimated_max_loss": round(quantity * per_share_risk, 2),
        "estimated_notional": round(quantity * entry, 2),
        "limited_by": limited_by,
        "minimum_reward_to_risk": minimum_rr,
        "minimum_target": round(target, 4),
        "capital_assumption": {
            "max_initial_gross_exposure_pct": MAX_INITIAL_GROSS_EXPOSURE_PCT,
            "max_simultaneous_ideas": max_positions,
            "per_idea_capital_cap": round(per_idea_capital, 2) if per_idea_capital is not None else None,
        },
    }


def build_equity_opportunity(candidate, policy):
    """Create a completed-candle equity decision-support plan without order authority."""
    states = candidate.get("timeframe_states") if isinstance(candidate.get("timeframe_states"), dict) else {}
    daily, intraday = states.get("daily") or {}, states.get("15m") or {}
    direction = candidate.get("direction")
    live_price = _positive_number(candidate.get("price"))
    trigger = _positive_number(intraday.get("close")) or live_price
    daily_close = _positive_number(daily.get("close")) or live_price
    atr_value = _positive_number(daily.get("atr"))
    ema20_value = _positive_number(daily.get("ema20"))
    if not trigger or not daily_close or not atr_value:
        return {"status": "EXCLUDED", "kind": "EQUITY", "reason": "Fresh price plus completed 15m trigger and Daily ATR evidence are required."}
    if direction == "BULLISH":
        stop_candidates = [value for value in (ema20_value, daily_close - atr_value) if value and value < trigger]
        structure_invalidation = max(stop_candidates, default=None)
        crossed = live_price is not None and live_price > trigger * 1.005
        trigger_text = f"Buy only at/above the completed 15m close ₹{trigger:.2f}; do not chase beyond 0.5%."
    else:
        stop_candidates = [value for value in (ema20_value, daily_close + atr_value) if value and value > trigger]
        structure_invalidation = min(stop_candidates, default=None)
        crossed = live_price is not None and live_price < trigger * 0.995
        trigger_text = f"Sell only at/below the completed 15m close ₹{trigger:.2f}; do not chase beyond 0.5%."
    if structure_invalidation is None:
        return {"status": "EXCLUDED", "kind": "EQUITY", "reason": "Completed Daily EMA20/ATR did not produce a valid directional invalidation."}
    evidence = {
        timeframe: {
            "label": state.get("label"), "close": state.get("close"), "ema20": state.get("ema20"),
            "rsi": state.get("rsi"), "adx": state.get("adx"), "quality": state.get("data_quality"),
            "reasons": (state.get("reasons") or [])[:2],
        }
        for timeframe, state in states.items()
    }
    return {
        "status": "REQUIRES_INVALIDATION", "market_status": "WATCHLIST" if crossed else "READY", "kind": "EQUITY", "symbol": candidate.get("symbol"),
        "name": candidate.get("name"), "direction": direction,
        "thesis": f"{candidate.get('mtf_alignment')} across completed 15m, 1h, Daily and Weekly bars with {daily.get('relative_strength_state', 'available relative-strength')} evidence.",
        "entry": round(trigger, 2), "entry_trigger": trigger_text, "current_price": live_price,
        "stop_invalidation": None, "target": None, "reward_to_risk": float(policy["minimum_reward_to_risk"]),
        "quantity": None, "estimated_max_loss": None, "estimated_notional": None,
        "invalidation_choices": {
            "structure": {"label": "Completed-candle structure", "suggested_price": round(structure_invalidation, 2), "basis": "Daily EMA20 or 1×ATR alignment-break level"},
            "percent": {"label": "Fixed percentage", "default_value": 1.0, "computed_price": round(trigger * (0.99 if direction == "BULLISH" else 1.01), 2)},
            "atr": {"label": "ATR multiple", "default_value": 1.0, "atr": round(atr_value, 2), "computed_price": round(trigger - atr_value if direction == "BULLISH" else trigger + atr_value, 2)},
            "custom": {"label": "Custom exact price", "computed_price": None},
        },
        "recommended_invalidation": {
            "method": "structure",
            "price": round(structure_invalidation, 2),
            "rationale": "Completed Daily EMA20 / 1x ATR structure is the evidence-backed alignment break; it is proposed, not accepted.",
        },
        "active_invalidation": None,
        "exit_conditions": ["Choose an invalidation method before sizing or approval.", "Exit/stand aside if full alignment breaks on a newly completed candle or FYERS evidence becomes stale."],
        "evidence": evidence, "data_quality": candidate.get("data_quality"),
        "decision_support_only": True,
    }


def apply_invalidation_choice(candidate, opportunity, policy, selection, tick_size=0.05, option_proposal=None):
    """Apply one explicit stop choice and recompute all dependent risk values."""
    method = str((selection or {}).get("method") or "").lower()
    if method not in {"structure", "percent", "atr", "custom"}:
        raise ValueError("Choose structure, percent, ATR multiple, or custom invalidation.")
    entry = _positive_number(opportunity.get("entry") or (option_proposal or {}).get("spot"))
    if entry is None:
        raise ValueError("A fresh positive entry/spot is required before selecting invalidation.")
    direction = candidate.get("direction")
    choices = opportunity.get("invalidation_choices") or {}
    if method == "structure":
        raw_price = _positive_number((choices.get("structure") or {}).get("suggested_price"))
        input_value = raw_price
    elif method == "percent":
        input_value = _positive_number((selection or {}).get("value"))
        if input_value is None or input_value > 50:
            raise ValueError("Percentage invalidation must be greater than 0 and no greater than 50%.")
        raw_price = entry * (1 - input_value / 100 if direction == "BULLISH" else 1 + input_value / 100)
    elif method == "atr":
        input_value = _positive_number((selection or {}).get("value"))
        atr_value = _positive_number((choices.get("atr") or {}).get("atr"))
        if input_value is None or input_value > 10 or atr_value is None:
            raise ValueError("ATR multiple must be greater than 0 and no greater than 10 with fresh Daily ATR evidence.")
        raw_price = entry - input_value * atr_value if direction == "BULLISH" else entry + input_value * atr_value
    else:
        input_value = _positive_number((selection or {}).get("value"))
        raw_price = input_value
        if input_value is None:
            raise ValueError("Enter a positive custom invalidation price.")
    tick = _positive_number(tick_size)
    if tick is None:
        raise ValueError("A valid fresh tick size is required.")
    invalidation = math.floor(raw_price / tick + 1e-9) * tick if direction == "BULLISH" else math.ceil(raw_price / tick - 1e-9) * tick
    invalidation = round(invalidation, 6)
    if direction == "BULLISH" and invalidation >= entry or direction == "BEARISH" and invalidation <= entry:
        raise ValueError("The selected invalidation is on the wrong side of the current entry/spot.")
    risk_points = abs(entry - invalidation)
    minimum_rr = float(policy["minimum_reward_to_risk"])
    target = entry + minimum_rr * risk_points if direction == "BULLISH" else entry - minimum_rr * risk_points
    if target <= 0:
        raise ValueError("The selected invalidation produces a nonpositive target.")
    result = {
        "method": method, "input_value": input_value, "price": invalidation, "tick_size": tick,
        "risk_points": round(risk_points, 4), "target": round(target, 6), "reward_to_risk": minimum_rr,
    }
    if option_proposal:
        lots = math.floor(float(policy["idea_risk_limit"]) / float(option_proposal["max_loss_per_lot"]))
        if lots < 1:
            raise ValueError("Configured per-idea risk does not support one validated spread lot.")
        result.update({
            "lots": lots, "quantity": lots * int(option_proposal["lot_size"]),
            "estimated_max_loss": round(lots * float(option_proposal["max_loss_per_lot"]), 2),
            "target_exit_points": option_proposal.get("target_exit_points"),
        })
    else:
        sizing = size_equity_candidate({**candidate, "price": entry}, {
            "planning_capital": policy["planning_capital"], "max_loss_value": policy["idea_risk_limit"],
            "max_loss_unit": "rupees", "invalidation": invalidation, "stop_basis": "price",
            "max_simultaneous_positions": policy["max_simultaneous_positions"], "minimum_reward_to_risk": minimum_rr,
        })
        if sizing.get("status") != "SIZED":
            raise ValueError("; ".join(sizing.get("reasons") or ["Configured risk does not support one share."]))
        result.update({"quantity": sizing["quantity"], "estimated_max_loss": sizing["estimated_max_loss"], "estimated_notional": sizing["estimated_notional"]})
    return result


def evidence_conviction(candidate, opportunity, option_proposal=None):
    """Return an auditable evidence grade, never a probability or guarantee."""
    states = candidate.get("timeframe_states") if isinstance(candidate.get("timeframe_states"), dict) else {}
    completed = [states.get(name) or {} for name in ("15m", "1h", "daily", "weekly")]
    reasons, score = [], 0
    if len(completed) == 4 and all(state.get("label") and "UNAVAILABLE" not in str(state.get("label")) for state in completed):
        score += 2; reasons.append("four completed timeframes agree")
    else:
        reasons.append("timeframe evidence is incomplete")
    daily = states.get("daily") or {}
    adx = _positive_number(daily.get("adx"))
    if adx is not None and adx >= 25:
        score += 1; reasons.append(f"Daily ADX {adx:.1f} confirms trend strength")
    else:
        reasons.append("Daily ADX is below 25 or unavailable")
    rs = str(daily.get("relative_strength_state") or candidate.get("relative_strength_state") or "").upper()
    direction = str(candidate.get("direction") or "").upper()
    if (direction == "BULLISH" and "OUTPERFORM" in rs) or (direction == "BEARISH" and "UNDERPERFORM" in rs):
        score += 1; reasons.append("relative strength agrees with direction")
    else:
        reasons.append("relative strength is neutral, unavailable, or not directionally aligned")
    quality = str(candidate.get("data_quality") or "").upper()
    if quality in {"FRESH", "COMPLETE", "READY"} or all(str(state.get("data_quality") or "").upper() not in {"STALE", "INCOMPLETE", "UNAVAILABLE"} for state in completed):
        score += 1; reasons.append("data-quality gates pass")
    else:
        reasons.append("freshness or completeness is degraded")
    rr = _positive_number((option_proposal or {}).get("reward_to_risk") or opportunity.get("reward_to_risk"))
    if rr is not None and rr >= MIN_REWARD_TO_RISK:
        score += 1; reasons.append(f"planned reward:risk is 1:{rr:g}")
    if option_proposal:
        legs = option_proposal.get("legs") or []
        if len(legs) == 2 and all(leg.get("validated") for leg in legs):
            score += 1; reasons.append("both option legs pass quote, spread, Greeks, OI and volume gates")
        else:
            reasons.append("option evidence is incomplete or illiquid")
    rating = "High" if score >= (6 if option_proposal else 5) else "Moderate" if score >= 3 else "Low"
    return {"rating": rating, "score": score, "maximum_score": 7 if option_proposal else 6, "rationale": "; ".join(reasons), "advisory": "Evidence grade only; it is not a probability or guarantee."}


class FyersFoMaster:
    """Daily cached, streaming lookup for exact FYERS derivative metadata."""

    def __init__(self, cache_path=FYERS_FO_MASTER_CACHE, requester=None, now=None, master_url=FYERS_FO_MASTER_URL):
        self.cache_path = Path(cache_path)
        self.requester = requester or requests.get
        self.now = now or time.time
        self.master_url = master_url

    def _content(self):
        current_day = datetime.fromtimestamp(self.now()).date()
        if self.cache_path.exists() and datetime.fromtimestamp(self.cache_path.stat().st_mtime).date() >= current_day:
            return self.cache_path.read_text(encoding="utf-8")
        response = self.requester(self.master_url, timeout=60)
        response.raise_for_status()
        content = response.text
        try:
            _atomic_private_write(self.cache_path, content)
        except OSError:
            # Read-only/sandboxed dashboard sessions may refresh safely without
            # persisting the daily optimization cache.
            pass
        return content

    def lookup(self, symbols):
        wanted = {str(symbol) for symbol in symbols if symbol}
        found = {}
        if not wanted:
            return found
        for row in csv.reader(io.StringIO(self._content())):
            if len(row) < 18 or row[9] not in wanted:
                continue
            found[row[9]] = {
                "fy_token": row[0],
                "description": row[1],
                "instrument_type": row[2],
                "lot_size": int(float(row[3])),
                "tick_size": float(row[4]),
                "expiry_epoch": str(row[8]),
                "symbol": row[9],
                "exchange": int(row[10]),
                "segment": int(row[11]),
                "exchange_token": str(row[12]),
                "underlying": row[13],
                "strike": float(row[15]),
                "option_type": row[16],
            }
            if len(found) == len(wanted):
                break
        return found


class FyersCmMaster(FyersFoMaster):
    def __init__(self, cache_path=FYERS_CM_MASTER_CACHE, requester=None, now=None):
        super().__init__(cache_path=cache_path, requester=requester, now=now, master_url=FYERS_CM_MASTER_URL)


def fetch_fyers_chain(client, underlying_symbol, strike_count=8):
    """Fetch a fresh nearest-expiry FYERS chain with Greeks; never submits an order."""
    discovery = client.optionchain({"symbol": underlying_symbol, "strikecount": 1, "timestamp": ""})
    if not isinstance(discovery, dict) or discovery.get("s") != "ok":
        message = discovery.get("message") if isinstance(discovery, dict) else "invalid response"
        raise RuntimeError(f"FYERS option chain unavailable for {underlying_symbol}: {message}")
    expiries = discovery.get("data", {}).get("expiryData") or []
    if not expiries:
        raise RuntimeError(f"No listed FYERS option expiry is available for {underlying_symbol}.")
    expiry = expiries[0]
    chain = client.optionchain({
        "symbol": underlying_symbol,
        "strikecount": min(50, max(2, int(strike_count))),
        "timestamp": str(expiry.get("expiry", "")),
        "greeks": "1",
    })
    if not isinstance(chain, dict) or chain.get("s") != "ok":
        message = chain.get("message") if isinstance(chain, dict) else "invalid response"
        raise RuntimeError(f"FYERS option chain unavailable for {underlying_symbol}: {message}")
    return chain, expiry


def _leg(chain_item, master):
    bid = _positive_number(chain_item.get("bid"))
    ask = _positive_number(chain_item.get("ask"))
    ltp = _positive_number(chain_item.get("ltp"))
    oi = _positive_number(chain_item.get("oi")) or 0
    volume = _positive_number(chain_item.get("volume")) or 0
    greeks = chain_item.get("greeks") if isinstance(chain_item.get("greeks"), dict) else {}
    mid = (bid + ask) / 2 if bid is not None and ask is not None else None
    spread_pct = (ask - bid) / mid * 100 if mid and ask >= bid else None
    reasons = []
    if not master:
        reasons.append("exact contract is absent from today's FYERS symbol master")
    if bid is None or ask is None or ask < bid:
        reasons.append("valid two-sided bid/ask is unavailable")
    if spread_pct is None or spread_pct > MAX_SPREAD_PCT:
        reasons.append(f"bid/ask spread exceeds {MAX_SPREAD_PCT:.0f}% or is unavailable")
    if oi < MIN_OPEN_INTEREST:
        reasons.append(f"open interest is below {MIN_OPEN_INTEREST}")
    if volume < MIN_VOLUME:
        reasons.append("traded volume is unavailable")
    required_greeks = ("delta", "gamma", "theta", "vega", "iv")
    if any(greeks.get(key) is None for key in required_greeks):
        reasons.append("complete Delta/Gamma/Theta/Vega/IV data is unavailable")
    return {
        "symbol": chain_item.get("symbol"),
        "security_token": master.get("exchange_token") if master else None,
        "fy_token": master.get("fy_token") if master else chain_item.get("fyToken"),
        "strike": float(chain_item.get("strike_price")),
        "option_type": chain_item.get("option_type"),
        "ltp": ltp,
        "bid": bid,
        "ask": ask,
        "spread_pct": round(spread_pct, 2) if spread_pct is not None else None,
        "open_interest": int(oi),
        "volume": int(volume),
        "greeks": {key: greeks.get(key) for key in required_greeks},
        "lot_size": master.get("lot_size") if master else None,
        "tick_size": master.get("tick_size") if master else None,
        "expiry_epoch": master.get("expiry_epoch") if master else None,
        "validated": not reasons,
        "validation_reasons": reasons,
    }


def _spread(identifier, label, direction, strategy, long_leg, short_leg, width, scenario):
    if not long_leg["validated"] or not short_leg["validated"]:
        return None
    if long_leg["lot_size"] != short_leg["lot_size"]:
        return None
    lot_size = long_leg["lot_size"]
    if strategy == "DEBIT":
        entry = long_leg["ask"] - short_leg["bid"]
        max_loss_points = entry
        max_profit_points = width - entry
    else:
        entry = short_leg["bid"] - long_leg["ask"]
        max_profit_points = entry
        max_loss_points = width - entry
    if entry <= 0 or max_loss_points <= 0 or max_profit_points <= 0:
        return None
    return {
        "proposal_id": identifier,
        "label": label,
        "direction": direction,
        "structure": strategy,
        "status": "ANALYSIS_ONLY",
        "legs": [
            {"action": "BUY", **long_leg},
            {"action": "SELL", **short_leg},
        ],
        "entry_points": round(entry, 2),
        "width_points": round(width, 2),
        "lot_size": lot_size,
        "max_loss_per_lot": round(max_loss_points * lot_size, 2),
        "max_profit_per_lot": round(max_profit_points * lot_size, 2),
        "reward_to_risk": round(max_profit_points / max_loss_points, 2),
        "scenario": scenario,
        "pricing_note": "Top-of-book estimate from the fresh FYERS chain; prices are not guaranteed fills.",
    }


def _nearest_pair(legs, spot, long_higher=False):
    ordered = sorted(legs, key=lambda item: item["strike"])
    pairs = []
    for lower, higher in zip(ordered, ordered[1:]):
        long_leg, short_leg = (higher, lower) if long_higher else (lower, higher)
        pairs.append((abs((lower["strike"] + higher["strike"]) / 2 - spot), long_leg, short_leg))
    pairs.sort(key=lambda item: item[0])
    return [(long_leg, short_leg) for _, long_leg, short_leg in pairs]


def build_defined_risk_spreads(chain_payload, expiry, master_records, direction, risk=None):
    """Build at most one debit and one credit spread from exact, liquid chain legs."""
    rows = chain_payload.get("data", {}).get("optionsChain") or []
    spot_row = next((row for row in rows if row.get("option_type") == ""), None)
    spot = _positive_number(spot_row.get("ltp") if spot_row else None)
    if spot is None:
        return {"status": "UNAVAILABLE", "reason": "FYERS chain spot is unavailable.", "proposals": []}
    normalized = [
        _leg(row, master_records.get(row.get("symbol")))
        for row in rows
        if row.get("option_type") in {"CE", "PE"} and row.get("strike_price") is not None
    ]
    expiry_epoch = str(expiry.get("expiry", ""))
    for leg in normalized:
        if leg["expiry_epoch"] and expiry_epoch and leg["expiry_epoch"] != expiry_epoch:
            leg["validated"] = False
            leg["validation_reasons"].append("chain expiry and symbol-master expiry do not match")
    calls = [leg for leg in normalized if leg["option_type"] == "CE"]
    puts = [leg for leg in normalized if leg["option_type"] == "PE"]
    proposals = []
    if direction == "BULLISH":
        debit_pairs = _nearest_pair(calls, spot, long_higher=False)
        credit_pairs = _nearest_pair(puts, spot, long_higher=False)
        definitions = [
            ("bull-call-debit", "Bull call debit spread", "DEBIT", debit_pairs, "Benefits from a rise through the long call while loss is capped at the net debit."),
            ("bull-put-credit", "Bull put credit spread", "CREDIT", credit_pairs, "Benefits if the underlying holds above the short put; downside is capped by the long put."),
        ]
    else:
        debit_pairs = _nearest_pair(puts, spot, long_higher=True)
        credit_pairs = _nearest_pair(calls, spot, long_higher=True)
        definitions = [
            ("bear-put-debit", "Bear put debit spread", "DEBIT", debit_pairs, "Benefits from a decline through the long put while loss is capped at the net debit."),
            ("bear-call-credit", "Bear call credit spread", "CREDIT", credit_pairs, "Benefits if the underlying remains below the short call; upside risk is capped by the long call."),
        ]
    for identifier, label, strategy, pairs, scenario in definitions:
        for long_leg, short_leg in pairs:
            width = abs(long_leg["strike"] - short_leg["strike"])
            proposal = _spread(identifier, label, direction, strategy, long_leg, short_leg, width, scenario)
            if proposal:
                proposals.append(proposal)
                break

    budget, budget_error = risk_budget(
        (risk or {}).get("planning_capital"),
        (risk or {}).get("max_loss_value"),
        (risk or {}).get("max_loss_unit"),
    )
    invalidation, invalidation_error = _invalidation_price(spot, direction, risk or {})
    for proposal in proposals:
        reasons = []
        if budget_error:
            reasons.append(budget_error)
        if invalidation_error:
            reasons.append(invalidation_error)
        if reasons:
            proposal["sizing"] = {"status": "REQUIRES_RISK_INPUTS", "lots": None, "reasons": reasons}
        else:
            lots = math.floor(budget / proposal["max_loss_per_lot"])
            proposal["sizing"] = {
                "status": "SIZED" if lots > 0 else "NO_SIZE_AVAILABLE",
                "lots": lots,
                "quantity": lots * proposal["lot_size"],
                "risk_budget": budget,
                "underlying_invalidation": invalidation,
                "estimated_max_loss": round(lots * proposal["max_loss_per_lot"], 2),
                "funding_validation": "Fresh FYERS funds and margin coverage are still required at trade preview.",
            }
    below_reward_gate = []
    eligible_proposals = []
    minimum_rr = _positive_number((risk or {}).get("minimum_reward_to_risk")) or MIN_REWARD_TO_RISK
    for proposal in proposals:
        if proposal["reward_to_risk"] < minimum_rr:
            below_reward_gate.append({
                "proposal_id": proposal["proposal_id"],
                "label": proposal["label"],
                "reward_to_risk": proposal["reward_to_risk"],
                "hard_gate_reward_to_risk": minimum_rr,
                "reason": f"{proposal['label']}: analyzed R:R 1:{proposal['reward_to_risk']:g} vs hard gate 1:{minimum_rr:g}.",
            })
        else:
            eligible_proposals.append(proposal)
    proposals = eligible_proposals

    capital = _positive_number((risk or {}).get("planning_capital"))
    max_positions = int(_positive_number((risk or {}).get("max_simultaneous_positions")) or MAX_SIMULTANEOUS_IDEAS)
    per_idea_capital = (
        capital * MAX_INITIAL_GROSS_EXPOSURE_PCT / 100 / max_positions
        if capital is not None
        else None
    )
    for proposal in proposals:
        sizing = proposal.get("sizing", {})
        if sizing.get("lots") is None or per_idea_capital is None:
            continue
        planning_requirement = (
            proposal["entry_points"] * proposal["lot_size"]
            if proposal["structure"] == "DEBIT"
            else proposal["max_loss_per_lot"]
        )
        capital_lots = math.floor(per_idea_capital / planning_requirement) if planning_requirement > 0 else 0
        if capital_lots < sizing["lots"]:
            sizing["lots"] = capital_lots
            sizing["quantity"] = capital_lots * proposal["lot_size"]
            sizing["estimated_max_loss"] = round(capital_lots * proposal["max_loss_per_lot"], 2)
            sizing["limited_by"] = "conservative simultaneous-exposure cap"
            sizing["status"] = "SIZED" if capital_lots > 0 else "NO_SIZE_AVAILABLE"
        else:
            sizing["limited_by"] = "maximum loss"
        sizing["capital_assumption"] = {
            "max_initial_gross_exposure_pct": MAX_INITIAL_GROSS_EXPOSURE_PCT,
            "max_simultaneous_ideas": max_positions,
            "per_idea_capital_cap": round(per_idea_capital, 2),
        }

    rejected = [leg for leg in normalized if not leg["validated"]]
    expiry_display = expiry.get("date")
    try:
        expiry_iso = datetime.strptime(expiry_display, "%d-%m-%Y").date().isoformat()
    except (TypeError, ValueError):
        expiry_iso = None
    return {
        "status": "READY" if proposals else "UNAVAILABLE",
        "spot": spot,
        "expiry": expiry_display,
        "expiry_iso": expiry_iso,
        "expiry_epoch": expiry_epoch,
        "liquidity_rules": {
            "max_spread_pct": MAX_SPREAD_PCT,
            "min_open_interest": MIN_OPEN_INTEREST,
            "min_volume": MIN_VOLUME,
            "complete_greeks_required": True,
            "minimum_reward_to_risk": minimum_rr,
        },
        "proposals": proposals,
        "rejected_proposals": below_reward_gate,
        "rejected_contracts": rejected,
        "reason": None if proposals else "No adjacent pair passed exact-contract, Greeks, OI, volume and spread validation.",
    }


def validate_handoff_request(payload):
    recipient = str(payload.get("recipient", "")).lower()
    action = str(payload.get("action", "")).lower()
    if recipient not in HANDOFF_RECIPIENTS:
        raise ValueError("Choose ChatGPT or Codex as the packet recipient.")
    if action not in HANDOFF_ACTIONS:
        raise ValueError("Choose local preview or local export as the packet action.")
    selected = payload.get("candidate_keys") or []
    if not isinstance(selected, list) or not selected:
        raise ValueError("Select at least one fully aligned candidate.")
    if len(selected) > MAX_SELECTED_CANDIDATES:
        raise ValueError(f"Select at most {MAX_SELECTED_CANDIDATES} candidates per packet.")
    include_funds = payload.get("include_funds") is True
    if include_funds and payload.get("funds_confirmed") is not True:
        raise ValueError("Confirm funds inclusion before the server reads current account funds for this packet.")
    return recipient, action, list(dict.fromkeys(map(str, selected))), include_funds


def packet_prompt(recipient):
    audience = "ChatGPT" if recipient == "chatgpt" else "Codex"
    return (
        f"Review this Sector Pulse packet in {audience}. Treat it as analysis-only evidence, not order authority. "
        "Reject stale, missing, or internally inconsistent data. Re-check every option contract and quote before any future trade preview. "
        "Do not place, modify, or cancel an order from this packet."
    )
