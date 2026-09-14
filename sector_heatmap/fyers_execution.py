"""FYERS-only, confirmation-gated ticket preparation and reconciliation."""

from __future__ import annotations

from datetime import date, datetime, time as clock_time, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
from threading import Lock
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel

from .config import _atomic_private_write, load_config
from .equity_exit_plan import build_equity_exit_plan
from .handoff import FyersCmMaster, FyersFoMaster, MIN_REWARD_TO_RISK, fetch_fyers_chain


HARD_MAX_DAILY_LOSS = 5000.0
DEFAULT_IDEA_RISK = 2000.0
DEFAULT_RISK_RESERVE = 1000.0
PREVIEW_TTL_SECONDS = 120
RISK_LEDGER_PATH = Path.home() / ".fyers" / "sector-heatmap" / "risk-ledger.json"


class FyersExecutionUnavailable(RuntimeError):
    pass


class PreviewChanged(RuntimeError):
    def __init__(self, preview):
        super().__init__("Fresh FYERS state changed the exact ticket; review and confirm the replacement preview.")
        self.preview = preview


def _require_cash_session(now):
    local = now.astimezone(ZoneInfo("Asia/Kolkata"))
    if local.weekday() >= 5 or not (clock_time(9, 15) <= local.time().replace(tzinfo=None) <= clock_time(15, 30)):
        raise FyersExecutionUnavailable("FYERS market state is closed; a live Screener order preview is unavailable outside the cash session.")


def _fresh_market_state(now, instrument):
    _require_cash_session(now)
    raw = instrument.get("contracts", [{}])[0].get("quote", {}).get("provider_timestamp")
    try:
        timestamp = float(raw)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
    except (TypeError, ValueError):
        raise FyersExecutionUnavailable("FYERS did not provide a timestamp for the live market quote.")
    age = abs(now.timestamp() - timestamp)
    if age > 60:
        raise FyersExecutionUnavailable(f"FYERS quote is stale ({age:.0f}s old); refresh during the live cash session.")


def _number(value, default=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _ok(response):
    return isinstance(response, dict) and response.get("s") == "ok"


def _message(response, fallback):
    return response.get("message") if isinstance(response, dict) and response.get("message") else fallback


def _current_client(client_factory=None):
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if not token or ":" not in token:
        raise FyersExecutionUnavailable("A current private FYERS access token is required.")
    app_id, access_token = token.split(":", 1)
    return (client_factory or (lambda client_id, value: fyersModel.FyersModel(client_id=client_id, token=value)))(app_id, access_token)


class DailyRiskLedger:
    def __init__(self, path=RISK_LEDGER_PATH):
        self.path = Path(path)

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {"version": 1, "days": {}}
        return data if data.get("version") == 1 and isinstance(data.get("days"), dict) else {"version": 1, "days": {}}

    def entries(self, day=None):
        return list(self._load()["days"].get((day or date.today()).isoformat(), []))

    def append(self, entry, day=None):
        data = self._load()
        key = (day or date.today()).isoformat()
        data["days"].setdefault(key, []).append(entry)
        for old_day in sorted(data["days"])[:-10]:
            data["days"].pop(old_day, None)
        _atomic_private_write(self.path, json.dumps(data, indent=2) + "\n")

    def open_risk(self, day=None):
        return round(sum(
            _number(item.get("worst_case_risk"), 0) or 0 for item in self.entries(day)
            if item.get("status") in {"OPEN", "PENDING", "EXECUTION_STATUS_UNCERTAIN"}
        ), 2)


def available_funds(response):
    """Return FYERS' available balance row without adding non-additive limits."""
    if not _ok(response):
        raise FyersExecutionUnavailable(_message(response, "FYERS funds are unavailable."))
    limits = response.get("fund_limit") or response.get("data", {}).get("fund_limit") or []
    available = next((item for item in limits if item.get("id") == 10), None)
    if available is None:
        available = next((item for item in limits if str(item.get("title") or "").strip().casefold() == "available balance"), None)
    if available is None:
        raise FyersExecutionUnavailable("FYERS did not return its Available Balance limit row.")
    return round((_number(available.get("equityAmount"), 0) or 0) + (_number(available.get("commodityAmount"), 0) or 0), 2)


def _positions(response):
    if not _ok(response):
        raise FyersExecutionUnavailable(_message(response, "FYERS positions are unavailable."))
    return response.get("netPositions") or response.get("data", {}).get("netPositions") or []


def _orders(response):
    if not _ok(response):
        raise FyersExecutionUnavailable(_message(response, "FYERS order state is unavailable."))
    return response.get("orderBook") or response.get("data", {}).get("orderBook") or []


def _quotes(response):
    if not _ok(response):
        raise FyersExecutionUnavailable(_message(response, "FYERS quotes are unavailable."))
    result = {}
    for row in response.get("d") or []:
        values = row.get("v") or {}
        symbol = row.get("n") or values.get("symbol")
        bid, ask = _number(values.get("bid")), _number(values.get("ask"))
        if symbol and bid and ask and ask >= bid:
            result[symbol] = {"ltp": _number(values.get("lp")), "bid": bid, "ask": ask, "provider_timestamp": values.get("tt")}
    return result


def _round_tick(price, tick):
    return round(math.floor(float(price) / float(tick) + 1e-9) * float(tick), 6)


def _realized_loss(positions):
    realized = sum(_number(item.get("realized_profit", item.get("realizedProfit", 0)), 0) or 0 for item in positions)
    return round(max(0.0, -realized), 2)


def option_order_policy(expiry_iso, trading_day):
    """Map FYERS UI terminology to API fields for a standard option order."""
    try:
        expiry_day = date.fromisoformat(str(expiry_iso))
    except ValueError as error:
        raise FyersExecutionUnavailable("The option expiry date is invalid.") from error
    return {
        "execution_mode": "NORMAL",
        "holding_product": "OVERNIGHT",
        "product_type": "MARGIN",
        "is_expiry_day": expiry_day == trading_day,
        "mapping_note": "FYERS Normal is a standard order without BO/CO exits; FYERS API MARGIN maps to Overnight for F&O.",
    }


def _order_ids(response):
    ids = []
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"id", "orderId", "order_id"} and child:
                    ids.append(str(child))
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(response)
    return list(dict.fromkeys(ids))


class FyersExecutionService:
    """Creates exact limit-order tickets and requires a second fresh-state check."""

    def __init__(self, client_factory=None, master=None, cm_master=None, ledger=None, now=None, execution_halt=None,
                 live_gate_name="SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS", live_gate=None):
        self.client_factory = client_factory
        self.master = master or FyersFoMaster()
        self.cm_master = cm_master or FyersCmMaster()
        self.ledger = ledger or DailyRiskLedger()
        self.now = now or datetime.now
        self.execution_halt = execution_halt
        self.live_gate_name = str(live_gate_name)
        self.live_gate = live_gate
        self.lock = Lock()
        self.previews = {}

    def capabilities(self):
        try:
            _current_client(self.client_factory)
            configured = True
            message = "Private FYERS token found."
        except FyersExecutionUnavailable as error:
            configured = False
            message = str(error)
        return {
            "selected_broker": "fyers",
            "fyers_configured": configured,
            "live_submission_enabled": self._live_submission_enabled(),
            "live_gate_name": self.live_gate_name,
            "message": message,
        }

    def _live_submission_enabled(self):
        if self.live_gate is not None:
            return bool(self.live_gate())
        return os.getenv(self.live_gate_name) == "1"

    @staticmethod
    def _risk_settings(payload):
        enforce_risk_controls = payload.get("enforce_risk_controls") is True
        enforce_minimum_rr = payload.get("enforce_minimum_reward_to_risk") is True
        daily_limit = _number(payload.get("daily_loss_limit"), HARD_MAX_DAILY_LOSS)
        idea_limit = _number(payload.get("idea_risk_limit"), DEFAULT_IDEA_RISK)
        reserve = _number(payload.get("risk_reserve"), DEFAULT_RISK_RESERVE)
        external_open_risk = _number(payload.get("external_open_risk"))
        max_positions_value = _number(payload.get("max_simultaneous_positions"), 3)
        minimum_rr = _number(payload.get("minimum_reward_to_risk")) if enforce_minimum_rr else None
        order_type = str(payload.get("order_type") or "LIMIT").upper()
        max_positions = int(max_positions_value or 0)
        if enforce_risk_controls:
            if daily_limit <= 0:
                raise ValueError("Daily loss limit must be positive when capital controls are enabled.")
            if idea_limit <= 0 or reserve < 0 or idea_limit + reserve > daily_limit:
                raise ValueError("Per-idea risk plus the protected reserve must fit inside the daily limit.")
            if max_positions_value != max_positions or not 1 <= max_positions <= 20:
                raise ValueError("Maximum simultaneous positions must be a whole number from 1 to 20 when capital controls are enabled.")
        if enforce_minimum_rr and minimum_rr is None:
            raise ValueError("Minimum reward-to-risk must be positive when enabled.")
        if order_type != "LIMIT":
            raise ValueError("Market-order preference is preview-only; live FYERS tickets require bounded LIMIT prices.")
        return enforce_risk_controls, daily_limit, idea_limit, reserve, external_open_risk, max_positions, minimum_rr, order_type

    def _preflight_option_spread(self, client, payload, proposal, minimum_rr):
        underlying_symbol = str(payload.get("underlying") or "")
        expiry_iso = str(payload.get("expiry") or "")
        requested_legs = proposal.get("legs") or []
        if len(requested_legs) != 2:
            raise ValueError("A defined-risk spread requires exactly two option legs.")
        chain, expiry = fetch_fyers_chain(client, underlying_symbol)
        try:
            chain_expiry_iso = datetime.strptime(expiry.get("date"), "%d-%m-%Y").date().isoformat()
        except (TypeError, ValueError) as error:
            raise FyersExecutionUnavailable("FYERS returned an invalid option expiry.") from error
        if chain_expiry_iso != expiry_iso:
            raise FyersExecutionUnavailable("The selected expiry is no longer the fresh nearest FYERS option-chain expiry.")
        rows = [row for row in chain.get("data", {}).get("optionsChain", []) if row.get("option_type") in {"CE", "PE"}]
        exact_rows = []
        for requested in requested_legs:
            action = str(requested.get("action") or "").upper()
            if action not in {"BUY", "SELL"}:
                raise ValueError("Each option leg action must be BUY or SELL.")
            match = next((row for row in rows if float(row.get("strike_price")) == float(requested.get("strike")) and row.get("option_type") == requested.get("option_type")), None)
            if not match:
                raise FyersExecutionUnavailable("A selected option leg is absent from the fresh FYERS chain.")
            exact_rows.append((action, match))
        symbols = [row["symbol"] for _, row in exact_rows]
        master = self.master.lookup(symbols)
        if any(symbol not in master for symbol in symbols):
            raise FyersExecutionUnavailable("An exact option contract is absent from today's FYERS symbol master.")
        if any(str(master[symbol].get("expiry_epoch")) != str(expiry.get("expiry")) for symbol in symbols):
            raise FyersExecutionUnavailable("A selected contract's master expiry does not match the fresh FYERS option-chain expiry.")
        lot_sizes = {master[symbol]["lot_size"] for symbol in symbols}
        if len(lot_sizes) != 1:
            raise FyersExecutionUnavailable("Fresh option contracts have inconsistent lot sizes.")
        lot_size = lot_sizes.pop()
        lots_value = _number(payload.get("lots"), 0) or 0
        requested_lots = int(lots_value)
        if lots_value != requested_lots:
            raise ValueError("Lots must be a whole number and are never rounded up.")
        if requested_lots < 1:
            raise ValueError("Choose at least one lot.")
        quantity = requested_lots * lot_size
        quote_map = _quotes(client.quotes({"symbols": ",".join(symbols)}))
        contracts = []
        for action, row in exact_rows:
            symbol = row["symbol"]
            if symbol not in quote_map:
                raise FyersExecutionUnavailable(f"FYERS omitted a valid two-sided quote for {symbol}.")
            metadata = master[symbol]
            quote = quote_map[symbol]
            contracts.append({
                "action": action, "symbol": symbol, "quantity": quantity,
                "lot_size": lot_size, "tick_size": metadata["tick_size"],
                "expiry_epoch": metadata["expiry_epoch"], "strike": float(row["strike_price"]),
                "option_type": row["option_type"], "quote": quote,
                "limit_price": _round_tick(quote["ask"] if action == "BUY" else quote["bid"], metadata["tick_size"]),
                "chain": {"oi": row.get("oi"), "volume": row.get("volume"), "greeks": row.get("greeks")},
            })
        long_leg = next((item for item in contracts if item["action"] == "BUY"), None)
        short_leg = next((item for item in contracts if item["action"] == "SELL"), None)
        if not long_leg or not short_leg or long_leg["option_type"] != short_leg["option_type"]:
            raise ValueError("A defined-risk spread requires one protective BUY and one same-type SELL option.")
        structure = str(proposal.get("structure") or "").upper()
        direction = str(proposal.get("direction") or "").upper()
        option_type = long_leg["option_type"]
        valid_orientation = {
            ("DEBIT", "BULLISH", "CE"): long_leg["strike"] < short_leg["strike"],
            ("DEBIT", "BEARISH", "PE"): long_leg["strike"] > short_leg["strike"],
            ("CREDIT", "BULLISH", "PE"): long_leg["strike"] < short_leg["strike"],
            ("CREDIT", "BEARISH", "CE"): long_leg["strike"] > short_leg["strike"],
        }
        if not valid_orientation.get((structure, direction, option_type), False):
            raise ValueError("The option legs do not match the selected direction and defined-risk spread structure.")
        width = abs(long_leg["strike"] - short_leg["strike"])
        if structure == "DEBIT":
            entry_points = long_leg["limit_price"] - short_leg["limit_price"]
            max_loss_points, max_profit_points = entry_points, width - entry_points
        elif structure == "CREDIT":
            entry_points = short_leg["limit_price"] - long_leg["limit_price"]
            max_profit_points, max_loss_points = entry_points, width - entry_points
        else:
            raise ValueError("Only defined-risk debit or credit spreads are supported.")
        if min(entry_points, max_loss_points, max_profit_points) <= 0:
            raise FyersExecutionUnavailable("Fresh FYERS prices no longer form the selected spread.")
        reward_to_risk = max_profit_points / max_loss_points
        if minimum_rr is not None and reward_to_risk < minimum_rr:
            raise FyersExecutionUnavailable(f"Fresh reward-to-risk {reward_to_risk:.2f} is below 1:{minimum_rr}.")
        return {
            "kind": "OPTION_SPREAD", "contracts": sorted(contracts, key=lambda item: 0 if item["action"] == "BUY" else 1),
            "lots": requested_lots, "lot_size": lot_size, "quantity": quantity,
            "entry_points": round(entry_points, 2), "width_points": round(width, 2),
            "max_loss_per_lot": round(max_loss_points * lot_size, 2),
            "worst_case_risk": round(max_loss_points * quantity, 2),
            "max_profit": round(max_profit_points * quantity, 2),
            "reward_to_risk": round(reward_to_risk, 2),
            "minimum_cash_required": round(long_leg["limit_price"] * quantity, 2),
            "margin": {
                "status": "PREMIUM_FUNDED" if structure == "DEBIT" else "UNAVAILABLE",
                "message": "Debit spread is protection-first and requires the full long-leg premium before short-leg proceeds." if structure == "DEBIT" else "Exact FYERS SPAN/basket margin is not exposed by the installed SDK; credit-spread submission is blocked.",
            },
            "submission_eligible": structure == "DEBIT",
            "expiry": chain_expiry_iso,
        }

    def _preflight_equity(self, client, payload, proposal, invalidation, minimum_rr):
        symbol = str(payload.get("underlying") or "")
        metadata = self.cm_master.lookup([symbol]).get(symbol)
        if not metadata:
            raise FyersExecutionUnavailable("The exact equity contract is absent from today's FYERS cash-market master.")
        quantity_value = _number(payload.get("quantity", proposal.get("quantity")), 0) or 0
        quantity = int(quantity_value)
        if quantity_value != quantity or quantity < 1:
            raise ValueError("Equity quantity must be a positive whole number.")
        direction = str(proposal.get("direction") or "").upper()
        action = "BUY" if direction == "BULLISH" else "SELL" if direction == "BEARISH" else ""
        if not action:
            raise ValueError("Equity direction must be BULLISH or BEARISH.")
        product_type = str(payload.get("cash_product") or "INTRADAY").upper()
        if product_type not in {"INTRADAY", "CNC"}:
            raise ValueError("Cash product must be Intraday or Delivery (CNC).")
        if product_type == "CNC" and action != "BUY":
            raise FyersExecutionUnavailable(f"{product_type} is not available for a new short cash-equity position.")
        quotes = _quotes(client.quotes({"symbols": symbol}))
        if symbol not in quotes:
            raise FyersExecutionUnavailable(f"FYERS omitted a valid two-sided quote for {symbol}.")
        quote = quotes[symbol]
        limit_price = _round_tick(quote["ask"] if action == "BUY" else quote["bid"], metadata["tick_size"])
        if direction == "BULLISH" and invalidation >= limit_price or direction == "BEARISH" and invalidation <= limit_price:
            raise FyersExecutionUnavailable("The accepted invalidation is no longer on the safe side of the fresh FYERS entry quote.")
        target = _number(proposal.get("target"))
        if target is None or (direction == "BULLISH" and target <= limit_price) or (direction == "BEARISH" and target >= limit_price):
            raise FyersExecutionUnavailable("The accepted target is no longer valid against the fresh FYERS entry quote.")
        exit_plan = build_equity_exit_plan(
            direction, quantity, limit_price, target,
            str(payload.get("exit_plan_mode") or proposal.get("exit_plan_mode") or "FIXED_TARGET"),
        )
        per_share_risk = abs(limit_price - invalidation)
        per_share_reward = abs(target - limit_price)
        reward_to_risk = per_share_reward / per_share_risk
        if minimum_rr is not None and reward_to_risk < minimum_rr:
            raise FyersExecutionUnavailable(f"Fresh reward-to-risk {reward_to_risk:.2f} is below 1:{minimum_rr}.")
        cash_required = limit_price * quantity if action == "BUY" else 0.0
        funding_label = "DELIVERY_CASH_FUNDED" if product_type == "CNC" else "CASH_FUNDED"
        return {
            "kind": "EQUITY", "contracts": [{"action": action, "symbol": symbol, "quantity": quantity,
                "lot_size": 1, "tick_size": metadata["tick_size"], "quote": quote, "limit_price": limit_price}],
            "quantity": quantity, "entry_price": limit_price, "target": target,
            "worst_case_risk": round(per_share_risk * quantity, 2), "max_profit": round(per_share_reward * quantity, 2),
            "reward_to_risk": round(reward_to_risk, 2), "minimum_cash_required": round(cash_required, 2),
            "cash_product": product_type,
            "exit_plan": exit_plan,
            "margin": {"status": funding_label if action == "BUY" else "UNAVAILABLE",
                "message": f"Long equity requires full cash notional for {product_type}." if action == "BUY" else "Exact FYERS intraday short margin is unavailable; submission is blocked."},
            "submission_eligible": action == "BUY" and exit_plan["mode"] == "FIXED_TARGET",
        }

    def _preflight(self, payload):
        if str(payload.get("broker", "")).lower() != "fyers":
            raise ValueError("FYERS must be explicitly selected for this dashboard's order preview.")
        invalidation = _number(payload.get("invalidation"))
        if invalidation is None or invalidation <= 0:
            raise ValueError("An explicit positive stop/invalidation is required.")
        enforce_risk_controls, daily_limit, idea_limit, reserve, external_open_risk, max_positions, minimum_rr, order_type = self._risk_settings(payload)
        client = _current_client(self.client_factory)
        profile = client.get_profile()
        if not _ok(profile):
            raise FyersExecutionUnavailable(_message(profile, "FYERS profile/token validation failed."))
        if payload.get("require_market_open") is True:
            _require_cash_session(self.now())
        proposal = payload.get("proposal") or {}
        instrument = self._preflight_equity(client, payload, proposal, invalidation, minimum_rr) if str(proposal.get("kind") or "").upper() == "EQUITY" else self._preflight_option_spread(client, payload, proposal, minimum_rr)
        if payload.get("require_market_open") is True:
            _fresh_market_state(self.now(), instrument)
        funds_response, positions_response, orders_response = client.funds(), client.positions(), client.orderbook()
        available_balance = available_funds(funds_response)
        positions, orders = _positions(positions_response), _orders(orders_response)
        open_positions = [item for item in positions if _number(item.get("netQty", item.get("net_qty", 0)), 0) != 0]
        if enforce_risk_controls and len(open_positions) >= max_positions:
            raise FyersExecutionUnavailable(f"Fresh FYERS state has {len(open_positions)} open position rows, meeting the configured maximum of {max_positions}.")
        if enforce_risk_controls and open_positions and external_open_risk is None:
            raise FyersExecutionUnavailable("Open FYERS positions exist. Declare their current worst-case stop risk before preparing a new ticket.")
        external_open_risk = external_open_risk or 0.0
        symbols = {item["symbol"] for item in instrument["contracts"]}
        pending = {4, 6}
        duplicates = [item for item in orders if item.get("symbol") in symbols and item.get("status") in pending]
        if duplicates:
            raise FyersExecutionUnavailable("A pending FYERS order already exists for a selected contract; reconcile it first.")
        realized_loss = _realized_loss(positions)
        app_open_risk = self.ledger.open_risk(self.now().date())
        used = realized_loss + app_open_risk + external_open_risk
        if enforce_risk_controls and used > daily_limit:
            raise FyersExecutionUnavailable("Realized loss plus worst-case open risk already exceeds the configured daily loss limit.")
        remaining_before_reserve = max(0.0, daily_limit - used) if enforce_risk_controls else None
        available_new_risk = min(idea_limit, max(0.0, remaining_before_reserve - reserve)) if enforce_risk_controls else None
        if enforce_risk_controls and instrument["worst_case_risk"] > available_new_risk + 1e-9:
            raise FyersExecutionUnavailable(f"Worst-case risk ₹{instrument['worst_case_risk']:.2f} exceeds available new-idea risk ₹{available_new_risk:.2f}.")
        if instrument["minimum_cash_required"] > available_balance:
            raise FyersExecutionUnavailable("Fresh FYERS funds do not cover the protection-first premium requirement.")
        option_policy = option_order_policy(instrument["expiry"], self.now().date()) if instrument["kind"] == "OPTION_SPREAD" else None
        preview = {
            "broker": "FYERS", "status": "PREVIEW_ONLY",
            "created_at": self.now().astimezone().isoformat(),
            "expires_at": (self.now().astimezone() + timedelta(seconds=PREVIEW_TTL_SECONDS)).isoformat(),
            "profile_validated": True, "underlying": payload.get("underlying"),
            "strategy": proposal.get("label"), "direction": proposal.get("direction"),
            "underlying_invalidation": invalidation, "instrument": instrument,
            "funds_margin": {"available_funds": available_balance, "minimum_cash_required": instrument["minimum_cash_required"], **instrument["margin"]},
            "daily_risk_ledger": {
                "capital_controls_enabled": enforce_risk_controls, "hard_daily_loss_limit": daily_limit if enforce_risk_controls else None, "realized_loss": realized_loss,
                "app_open_worst_case_risk": app_open_risk, "declared_external_open_risk": external_open_risk,
                "protected_reserve": reserve if enforce_risk_controls else None, "remaining_before_reserve": round(remaining_before_reserve, 2) if remaining_before_reserve is not None else None,
                "available_for_new_idea": round(available_new_risk, 2) if available_new_risk is not None else None,
                "remaining_after_proposal": round(remaining_before_reserve - reserve - instrument["worst_case_risk"], 2) if remaining_before_reserve is not None else None,
                "maximum_simultaneous_positions": max_positions if enforce_risk_controls else None,
            },
            "fresh_state": {
                "profile": "validated", "symbol_master": f"FYERS daily {'NSE_CM' if instrument['kind'] == 'EQUITY' else 'NSE_FO'} master",
                "option_chain": "not applicable" if instrument["kind"] == "EQUITY" else "fresh nearest expiry with Greeks", "quotes": "fresh two-sided FYERS snapshot",
                "positions_count": len(open_positions), "orders_count": len(orders), "pending_duplicates": 0,
            },
            "order_policy": {
                "order_type": order_type, "product_type": instrument["cash_product"] if instrument["kind"] == "EQUITY" else option_policy["product_type"], "validity": "DAY",
                "execution_mode": "NORMAL", "holding_product": instrument["cash_product"] if instrument["kind"] == "EQUITY" else option_policy["holding_product"],
                "is_expiry_day": None if instrument["kind"] == "EQUITY" else option_policy["is_expiry_day"],
                "mapping_note": "Standard FYERS order without BO/CO exits." if instrument["kind"] == "EQUITY" else option_policy["mapping_note"],
                "minimum_reward_to_risk": minimum_rr,
                "rounding": "Quantities use whole shares/lots; limit prices round down to the FYERS master tick.",
                "sequence": "Single equity limit order." if instrument["kind"] == "EQUITY" else "BUY protection leg first, then SELL leg in one FYERS basket call.",
                "automatic_retry": False,
            },
            "submission_eligible": instrument["submission_eligible"],
            "live_submission_enabled": self._live_submission_enabled(),
        }
        preview["state_digest"] = hashlib.sha256(json.dumps(preview, sort_keys=True, default=str).encode()).hexdigest()
        return preview

    def prepare(self, payload):
        preview = self._preflight(payload)
        preview_id = f"FYERS-{self.now().strftime('%m%d%H%M%S')}-{secrets.token_hex(3).upper()}"
        preview["preview_id"] = preview_id
        preview["confirmation_phrase"] = f"CONFIRM {preview_id}"
        with self.lock:
            self.previews[preview_id] = {"payload": payload, "preview": preview}
        return preview

    def _batch_preflight(self, payload):
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        if not 1 <= len(items) <= 100:
            raise ValueError("Select between 1 and 100 High-Conviction plans for one FYERS batch preview.")
        symbols = [str(item.get("underlying") or "") for item in items]
        if len(set(symbols)) != len(symbols):
            raise ValueError("A FYERS batch cannot contain the same underlying more than once.")
        preferred = []
        for index, item in enumerate(items, 1):
            try:
                probe_payload = {**item, "quantity": 1, "proposal": {**(item.get("proposal") or {}), "quantity": 1}}
                probe = self._preflight(probe_payload)
            except Exception as error:
                raise FyersExecutionUnavailable(f"Batch item {index} ({symbols[index - 1] or 'unknown'}): {error}") from error
            per_share_risk = probe["instrument"]["worst_case_risk"]
            idea_limit = probe["daily_risk_ledger"]["available_for_new_idea"]
            quantity = math.floor(idea_limit / per_share_risk) if idea_limit is not None and per_share_risk > 0 else 1
            if quantity < 1:
                raise FyersExecutionUnavailable(f"Batch item {index} ({symbols[index - 1]}): risk-based sizing produced zero whole shares.")
            preferred.append(({**item, "quantity": quantity, "proposal": {**(item.get("proposal") or {}), "quantity": quantity}}, quantity, probe))
        ledger = preferred[0][2]["daily_risk_ledger"]
        funds = preferred[0][2]["funds_margin"]["available_funds"]
        open_positions = preferred[0][2]["fresh_state"]["positions_count"]
        if ledger["maximum_simultaneous_positions"] is not None and open_positions + len(preferred) > ledger["maximum_simultaneous_positions"]:
            raise FyersExecutionUnavailable("The selected batch plus current FYERS positions exceeds the maximum simultaneous-position guardrail.")
        buffer = round(max(500.0, funds * 0.05), 2)
        estimated_preferred_notional = sum(item[1] * item[2]["instrument"]["entry_price"] for item in preferred)
        estimated_preferred_costs = estimated_preferred_notional * 0.002 + 20 * len(preferred)
        estimated_preferred_risk = sum(item[1] * item[2]["instrument"]["worst_case_risk"] for item in preferred)
        spendable = max(0.0, funds - buffer)
        cash_scale = spendable / (estimated_preferred_notional * 1.002 + 20 * len(preferred)) if estimated_preferred_notional else 0.0
        risk_scale = ledger["available_for_new_idea"] / estimated_preferred_risk if ledger["available_for_new_idea"] is not None and estimated_preferred_risk else 1.0
        scale = min(1.0, cash_scale, risk_scale)
        adjusted_payloads, excluded = [], []
        for item, preferred_quantity, probe in preferred:
            quantity = math.floor(preferred_quantity * scale)
            if quantity < 1:
                excluded.append({"underlying": item.get("underlying"), "preferred_quantity": preferred_quantity,
                                 "reason": "Proportional full-cash allocation reduced this plan below one whole share."})
                continue
            adjusted_payloads.append({**item, "quantity": quantity, "proposal": {**item["proposal"], "quantity": quantity}})
        if not adjusted_payloads:
            raise FyersExecutionUnavailable("Available FYERS funds after costs and buffer cannot fund one whole share of any selected plan.")
        previews = []
        for index, item in enumerate(adjusted_payloads, 1):
            try:
                previews.append(self._preflight(item))
            except Exception as error:
                raise FyersExecutionUnavailable(f"Allocated batch item {index} ({item.get('underlying') or 'unknown'}): {error}") from error
        total_risk = round(sum(item["instrument"]["worst_case_risk"] for item in previews), 2)
        total_notional = round(sum(item["instrument"]["minimum_cash_required"] for item in previews), 2)
        estimated_costs = round(total_notional * 0.002 + 20 * len(previews), 2)
        cash_reserved = round(total_notional + estimated_costs + buffer, 2)
        if ledger["available_for_new_idea"] is not None and total_risk > ledger["available_for_new_idea"] + 1e-9:
            raise FyersExecutionUnavailable(f"Aggregate batch risk ₹{total_risk:.2f} exceeds available new risk ₹{ledger['available_for_new_idea']:.2f}.")
        if cash_reserved > funds + 1e-9:
            raise FyersExecutionUnavailable(f"Aggregate cash, estimated costs and buffer ₹{cash_reserved:.2f} exceed fresh FYERS funds ₹{funds:.2f}.")
        if not all(item["submission_eligible"] for item in previews):
            raise FyersExecutionUnavailable("Every selected batch item must independently be submission-eligible; partial batches are not prepared.")
        return {
            "broker": "FYERS", "status": "BATCH_PREVIEW_ONLY", "items": previews,
            "excluded": excluded,
            "allocation": {"rule": "Risk-sized independently, then proportionally scaled to whole shares under full-cash funding.",
                           "margin_assumption": "NONE_FULL_CASH", "preferred_notional": round(estimated_preferred_notional, 2), "scaling_factor": round(scale, 6)},
            "aggregate": {"order_count": len(previews), "selected_count": len(items), "total_worst_case_risk": total_risk,
                          "total_minimum_cash_required": total_notional, "estimated_costs": estimated_costs, "cash_buffer": buffer,
                          "cash_reserved": cash_reserved, "available_funds": funds, "available_new_risk": ledger["available_for_new_idea"]},
            "submission_eligible": True, "live_submission_enabled": self._live_submission_enabled(),
        }

    def prepare_batch(self, payload):
        preview = self._batch_preflight(payload)
        preview_id = f"FYERS-BATCH-{self.now().strftime('%m%d%H%M%S')}-{secrets.token_hex(3).upper()}"
        preview.update({"preview_id": preview_id, "confirmation_phrase": f"CONFIRM {preview_id}",
                        "created_at": self.now().astimezone().isoformat(),
                        "expires_at": (self.now().astimezone() + timedelta(seconds=PREVIEW_TTL_SECONDS)).isoformat()})
        with self.lock:
            self.previews[preview_id] = {"payload": payload, "preview": preview, "batch": True}
        return preview

    def submit_batch(self, preview_id, confirmation):
        if not self._live_submission_enabled():
            raise PermissionError(f"Live FYERS submission is disabled. Enable {self.live_gate_name}=1 intentionally before submitting a reviewed batch.")
        with self.lock:
            stored = self.previews.get(preview_id)
        if not stored or not stored.get("batch"):
            raise ValueError("Unknown or expired FYERS batch preview.")
        if confirmation != f"CONFIRM {preview_id}":
            raise ValueError("Type the exact confirmation phrase from the current FYERS batch preview.")
        if self.now().astimezone() >= datetime.fromisoformat(stored["preview"]["expires_at"]):
            raise ValueError("This FYERS batch preview expired. Prepare a fresh preview.")
        refreshed = self._batch_preflight(stored["payload"])
        old_critical = {"items": [{"instrument": item["instrument"], "daily_risk_ledger": item["daily_risk_ledger"], "fresh_state": item["fresh_state"]} for item in stored["preview"]["items"]], "aggregate": stored["preview"]["aggregate"]}
        new_critical = {"items": [{"instrument": item["instrument"], "daily_risk_ledger": item["daily_risk_ledger"], "fresh_state": item["fresh_state"]} for item in refreshed["items"]], "aggregate": refreshed["aggregate"]}
        if old_critical != new_critical:
            raise PreviewChanged(self.prepare_batch(stored["payload"]))
        client = _current_client(self.client_factory)
        orders = []
        for item in refreshed["items"]:
            leg = item["instrument"]["contracts"][0]
            orders.append({"symbol": leg["symbol"], "qty": leg["quantity"], "type": 1, "side": 1 if leg["action"] == "BUY" else -1,
                           "productType": item["order_policy"]["product_type"], "limitPrice": leg["limit_price"], "stopPrice": 0,
                           "validity": "DAY", "disclosedQty": 0, "offlineOrder": False})
        response = client.place_basket_orders(orders)
        order_ids = _order_ids(response)
        status = "PENDING" if len(order_ids) == len(orders) else "EXECUTION_STATUS_UNCERTAIN"
        self.ledger.append({"preview_id": preview_id, "created_at": self.now().astimezone().isoformat(), "status": status,
                            "worst_case_risk": refreshed["aggregate"]["total_worst_case_risk"], "symbols": [item["underlying"] for item in refreshed["items"]], "order_ids": order_ids}, self.now().date())
        with self.lock:
            self.previews.pop(preview_id, None)
        return {"preview_id": preview_id, "status": status, "order_ids": order_ids,
                "message": "FYERS accepted the complete basket; reconcile every order before further action." if status == "PENDING" else "Batch execution status is uncertain; reconcile FYERS and do not retry automatically."}

    def submit(self, preview_id, confirmation):
        if not self._live_submission_enabled():
            raise PermissionError(f"Live FYERS submission is disabled. The account holder must intentionally set {self.live_gate_name}=1 before starting the dashboard.")
        with self.lock:
            stored = self.previews.get(preview_id)
        if not stored:
            raise ValueError("Unknown or expired FYERS preview.")
        if confirmation != f"CONFIRM {preview_id}":
            raise ValueError("Type the exact confirmation phrase from the current FYERS preview.")
        if self.now().astimezone() >= datetime.fromisoformat(stored["preview"]["expires_at"]):
            raise ValueError("This FYERS preview expired. Prepare a fresh ticket.")
        refreshed = self._preflight(stored["payload"])
        old = {key: value for key, value in stored["preview"].items() if key not in {"preview_id", "confirmation_phrase", "state_digest", "created_at", "expires_at"}}
        new = {key: value for key, value in refreshed.items() if key not in {"state_digest", "created_at", "expires_at"}}
        if old != new:
            raise PreviewChanged(self.prepare(stored["payload"]))
        if not refreshed["submission_eligible"]:
            raise PermissionError("This FYERS structure lacks exact margin validation and cannot be submitted.")
        client = _current_client(self.client_factory)
        orders = [{
            "symbol": leg["symbol"], "qty": leg["quantity"], "type": 1,
            "side": 1 if leg["action"] == "BUY" else -1, "productType": refreshed["order_policy"]["product_type"],
            "limitPrice": leg["limit_price"], "stopPrice": 0, "validity": "DAY",
            "disclosedQty": 0, "offlineOrder": False,
        } for leg in refreshed["instrument"]["contracts"]]
        response = client.place_order(orders[0]) if refreshed["instrument"]["kind"] == "EQUITY" else client.place_basket_orders(orders)
        order_ids = _order_ids(response)
        if not order_ids:
            status = "EXECUTION_STATUS_UNCERTAIN"
            reconciled = []
        else:
            book = client.orderbook()
            if not _ok(book):
                status, reconciled = "EXECUTION_STATUS_UNCERTAIN", []
            else:
                by_id = {str(item.get("id")): item for item in _orders(book)}
                reconciled = [by_id.get(order_id, {"id": order_id, "status": "UNKNOWN"}) for order_id in order_ids]
                if len(order_ids) == len(orders) and all(item.get("status") == 2 for item in reconciled):
                    status = "OPEN"
                elif any(item.get("status") in {1, 5, 7} for item in reconciled):
                    status = "REJECTED"
                else:
                    status = "PENDING"
        if status in {"EXECUTION_STATUS_UNCERTAIN", "REJECTED"} and self.execution_halt:
            self.execution_halt(preview_id, status)
        self.ledger.append({
            "preview_id": preview_id, "created_at": self.now().astimezone().isoformat(),
            "status": status, "worst_case_risk": refreshed["instrument"]["worst_case_risk"],
            "symbols": [leg["symbol"] for leg in refreshed["instrument"]["contracts"]], "order_ids": order_ids,
        }, self.now().date())
        with self.lock:
            self.previews.pop(preview_id, None)
        return {
            "preview_id": preview_id, "status": status, "order_ids": order_ids, "orders": reconciled,
            "message": "Order status is uncertain; reconcile FYERS orders and do not retry automatically." if status == "EXECUTION_STATUS_UNCERTAIN" else "FYERS rejected or terminated at least one leg; the policy is halted and no retry will occur." if status == "REJECTED" else "All order legs reconciled as filled." if status == "OPEN" else "Order accepted but not fully filled; monitor FYERS orders before further action.",
        }
