"""Read-only Dhan Super entry/registration evidence for chart-owned levels.

GET /super/orders covers the current day. CLOSED means exit triggered, not
exchange-filled; this module intentionally cannot establish a closed position.
Reference: https://dhanhq.co/docs/v2/super-order/
"""
from .chart_trade_native import native_bracket_order
from dataclasses import replace
from .dhan_protection import number, reconcile


def reconcile_dhan_super(plan, contract, *, preview_id, broker_client_id,
                         rows, entry_order_id=None):
    base = dict(account_id=plan.account_id, broker=plan.broker, symbol=plan.symbol,
                protection_confirmed=False, retry_allowed=False)
    def result(status, message, **fields):
        return dict(base, status=status, message=message, **fields)
    if plan.broker != "DHAN":
        raise ValueError("An account-bound Dhan chart plan is required.")
    # A durably managed stop-limit reaches Dhan as its reviewed LIMIT cap.
    # This is receipt comparison only and cannot submit or arm a trigger.
    native_plan=replace(plan,entry_type="LIMIT",entry=plan.limit_price) if plan.entry_type=="STOP_LIMIT" else plan
    ticket = native_bracket_order(native_plan, contract, client_order_id=preview_id,
                                  broker_client_id=broker_client_id)["body"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return result("BROKER_STATUS_UNAVAILABLE", "The native Dhan Super order book is unavailable. Do not resubmit.")
    matches = [row for row in rows if (
        str(row.get("orderId") or "") == str(entry_order_id) if entry_order_id
        else row.get("correlationId") == ticket["correlationId"])]
    if len(matches) != 1:
        return result("BROKER_STATUS_UNAVAILABLE", "The owned Dhan entry is not uniquely present in the current-day Super order book. Do not resubmit.")
    parent = matches[0]
    try:
        for key in ("dhanClientId", "correlationId", "transactionType",
                    "exchangeSegment", "securityId", "productType", "orderType"):
            if str(parent.get(key)) != str(ticket[key]):
                raise ValueError("Native Dhan entry ownership or contract differs from the reviewed order.")
        if not parent.get("orderId") or parent.get("legName") != "ENTRY_LEG" or parent.get("afterMarketOrder") is True:
            raise ValueError("Native Dhan entry role or session differs from the reviewed order.")
        if number(parent.get("price")) != number(plan.limit_price):
            raise ValueError("Native Dhan entry price differs from the reviewed order.")
        quantity = number(parent.get("quantity"))
        filled = number(parent.get("filledQty"))
        remaining = number(parent.get("remainingQuantity"))
        if quantity != plan.quantity or min(filled, remaining) < 0 or filled + remaining != quantity or any(v != int(v) for v in (filled, remaining)):
            raise ValueError("Native Dhan entry quantities do not reconcile.")
        status = parent.get("orderStatus")
        if status not in {"TRANSIT", "PENDING", "PART_TRADED", "TRADED", "CLOSED", "CANCELLED", "REJECTED", "EXPIRED"}:
            raise ValueError("Unknown native Dhan entry status.")
        base.update(entry_order_id=str(parent["orderId"]), filled_quantity=int(filled),
                    pending_quantity=int(remaining) if status in {"TRANSIT", "PENDING", "PART_TRADED"} else 0,
                    unfilled_quantity=int(remaining))
        if not filled:
            if status in {"CANCELLED", "REJECTED", "EXPIRED"}:
                return result(status, "The broker entry is terminal with no confirmed fills.")
            if status not in {"TRANSIT", "PENDING"}:
                raise ValueError("Native Dhan entry status disagrees with its zero fill quantity.")
            return result("ENTRY_PENDING", "Dhan entry is pending; no entry fill is confirmed.")
        if number(parent.get("averageTradedPrice")) <= 0:
            raise ValueError("Native Dhan entry fill price is unavailable.")
        base["entry_fill_price"] = str(number(parent["averageTradedPrice"]))
        if status == "TRADED" and filled != quantity:
            raise ValueError("Native Dhan traded status disagrees with entry fill quantity.")
        if filled != quantity or status != "TRADED":
            return result("ENTRY_FILLED_EXITS_UNVERIFIED" if filled == quantity else "ENTRY_PARTIALLY_FILLED_EXITS_UNVERIFIED",
                          "Entry fills exist. Triggered exits and CLOSED Super status do not prove exchange exit fills; trade-book reconciliation is required.")
        # Require exact marked prices; the older registration helper allows half-tick
        # comparison for its separate workflow.
        legs = parent.get("legDetails")
        if not isinstance(legs, list) or any(not isinstance(leg, dict) for leg in legs):
            raise ValueError("Native Dhan linked exits are unavailable.")
        for name, price in (("STOP_LOSS_LEG", plan.stop_loss), ("TARGET_LEG", plan.target)):
            matches = [leg for leg in legs if leg.get("legName") == name]
            if len(matches) != 1 or number(matches[0].get("price")) != number(price):
                raise ValueError("Native Dhan linked exits differ from the marked levels.")
        proof = reconcile(ticket, dict(stop_loss_price=plan.stop_loss, target_price=plan.target),
                          parent["orderId"], ticket["correlationId"], rows, plan.tick_size)
        if proof["protection_confirmed"] is not True:
            return result("ENTRY_FILLED_EXITS_UNVERIFIED", "The exact server-held Dhan exit registration is not verified.")
        return result("POSITION_PROTECTED", "Both marked Dhan server-held exits are registered for the full filled entry. This does not guarantee an exit fill.",
                      protection_confirmed=True, protected_quantity=plan.quantity)
    except (ValueError, TypeError, KeyError) as exc:
        return result("BROKER_STATUS_UNAVAILABLE", str(exc) or "Native Dhan order evidence cannot be verified.")
