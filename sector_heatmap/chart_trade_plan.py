"""Exact chart level plans. Pure validation; this module cannot submit orders.

Broker adapters must resolve the selected native contract, obtain a fresh quote,
and confirm native linked-exit capability before a plan can be armed.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math


def positive(value, name):
    if isinstance(value, bool):
        raise ValueError(name + " must be a positive number.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(name + " must be a positive number.") from None
    if not result.is_finite() or result <= 0:
        raise ValueError(name + " must be a positive number.")
    return result


def exact_price(value, tick, name):
    result = positive(value, name)
    if result % tick:
        raise ValueError(name + " must match the selected contract tick " + str(tick) + ".")
    return result


@dataclass(frozen=True)
class ChartTradePlan:
    account_id: str
    broker: str
    symbol: str
    side: str
    quantity: int
    entry: str
    stop_loss: str
    target: str
    entry_type: str
    limit_price: str
    product: str
    tick_size: str
    lot_size: int
    price_trigger: str
    protection: str = "BROKER_LINKED_FULL_QUANTITY"
    revision: str = "chart-level-order-v1"
    native_account_hash: str = ""
    exit_trigger_method: str = "last_traded_price"
    native_entry_revision: str = ""

    def terms(self):
        return asdict(self)

    def fingerprint(self):
        return sha256(json.dumps(self.terms(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_plan(payload, *, account, contract, quote, now, triggered_dhan_entry=False):
    """Validate exact levels and source identity without rounding or side effects."""
    aid = str(account.get("id") or "")
    broker = str(account.get("broker") or "")
    if not aid or broker not in {"FYERS", "DHAN", "MOTILAL_OSWAL", "DELTA_INDIA"}:
        raise ValueError("Choose a connected execution broker account.")
    if payload.get("account_id") != aid or payload.get("broker") != broker:
        raise PermissionError("The chart and execution account must match.")
    symbol = str(contract.get("symbol") or "")
    if not symbol or payload.get("symbol") != symbol:
        raise ValueError("Resolve the exact selected chart contract before reviewing an order.")
    if contract.get("tradable") is not True:
        raise ValueError("The chart symbol is not a tradable broker contract.")
    if quote.get("account_id") != aid or quote.get("symbol") != symbol:
        raise PermissionError("The quote belongs to a different account or symbol.")
    try:
        age = float(now) - float(quote["received_at"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("Fresh broker quote timing is required.") from None
    if not math.isfinite(age) or age < -1 or age > 5:
        raise ValueError("The broker quote is stale. Refresh the preview.")
    try:
        provider_age = float(now) - float(quote["provider_at"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("Broker-provided quote timing is required.") from None
    if not math.isfinite(provider_age) or provider_age < -1 or provider_age > 5:
        raise ValueError("The broker market price is stale. Refresh the preview.")
    exit_trigger = payload.get("exit_trigger_method","last_traded_price")
    if exit_trigger not in ({"last_traded_price","mark_price"} if broker=="DELTA_INDIA" else {"last_traded_price"}):
        raise ValueError("Choose a supported exit trigger price source for this broker.")
    if exit_trigger=="mark_price":
        positive(quote.get("mark_price"),"Native Delta mark price")
    last = positive(quote.get("last_price"), "Broker price")
    tick = positive(contract.get("tick_size"), "Contract tick")
    expiry = contract.get("expires_at")
    if expiry is not None and (not math.isfinite(float(expiry)) or float(expiry) <= float(now)):
        raise ValueError("The selected contract has expired.")
    side = str(payload.get("side") or "")
    if side not in {"BUY", "SELL"}:
        raise ValueError("Choose BUY or SELL explicitly.")
    quantity = positive(payload.get("quantity"), "Quantity")
    lot = positive(contract.get("lot_size"), "Contract lot size")
    if quantity != quantity.to_integral_value() or lot != lot.to_integral_value() or quantity % lot:
        raise ValueError("Quantity must be a whole multiple of the selected contract lot size.")
    entry = exact_price(payload.get("entry"), tick, "Entry")
    stop = exact_price(payload.get("stop_loss"), tick, "Stop loss")
    target = exact_price(payload.get("target"), tick, "Target")
    if not (stop < entry < target if side == "BUY" else target < entry < stop):
        raise ValueError("BUY requires stop < entry < target; SELL requires target < entry < stop.")
    entry_type = str(payload.get("entry_type") or "")
    if entry_type not in {"LIMIT", "STOP_LIMIT"}:
        raise ValueError("Choose a limit or stop-limit entry.")
    limit = exact_price(payload.get("limit_price", entry), tick, "Entry limit")
    if entry_type == "LIMIT":
        if limit != entry:
            raise ValueError("A limit entry must use the marked entry price.")
        if (side == "BUY" and entry > last) or (side == "SELL" and entry < last):
            raise ValueError("This marked entry needs a stop-limit trigger; a marketable limit cannot replace it.")
        trigger = "AT_OR_BELOW" if side == "BUY" else "AT_OR_ABOVE"
    else:
        if triggered_dhan_entry is True:
            if broker!="DHAN" or not (entry<=last and entry<limit<target if side=="BUY" else last<=entry and target<limit<entry):
                raise ValueError("Fresh Dhan price no longer satisfies the reviewed conditional entry.")
        elif not (last < entry < limit < target if side == "BUY" else target < limit < entry < last):
            raise ValueError("Stop-limit entry needs a trigger beyond the current broker price and a bounded limit before the target.")
        trigger = "AT_OR_ABOVE" if side == "BUY" else "AT_OR_BELOW"
    if contract.get("linked_exit_capability") != "NATIVE_OCO":
        raise ValueError("Verified broker-linked stop-loss and target support is required before arming this chart order.")
    product = str(payload.get("product") or "")
    if product not in contract.get("products", []):
        raise ValueError("Choose a supported broker product for this exact contract.")
    if side == "SELL" and product in {"CNC", "DELIVERY", "MTF"}:
        raise ValueError("This is a new position setup. Use the existing-position exit workflow to sell delivery holdings.")
    return ChartTradePlan(aid, broker, symbol, side, int(quantity), str(entry), str(stop), str(target),
                          entry_type, str(limit), product, str(tick), int(lot), trigger,
                          native_account_hash=str(account.get("native_identity") or ""),exit_trigger_method=exit_trigger,
                          native_entry_revision=str(account.get("native_entry_revision") or ""))


def confirm_plan(reviewed, refreshed, confirmation, *, expires_at, now):
    """Refuse changed drawings/account/contract/quantity, stale reviews or implicit consent."""
    if not math.isfinite(float(expires_at)) or float(now) >= float(expires_at):
        raise ValueError("The chart order preview expired. Prepare a fresh preview.")
    if reviewed.fingerprint() != refreshed.fingerprint():
        raise ValueError("The chart order changed. Review the replacement preview before submitting.")
    expected = "CONFIRM " + reviewed.fingerprint()
    if confirmation != expected:
        raise PermissionError("Confirm the exact current chart order preview.")
    return refreshed.terms()

