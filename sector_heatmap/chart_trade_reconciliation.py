"""Read-only FYERS order-book reconciliation for one owned chart order."""
from decimal import Decimal, InvalidOperation
import hashlib


def _number(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("The native order quantity or price is unavailable.") from None
    if not result.is_finite():
        raise ValueError("The native order quantity or price is invalid.")
    return result


def reconcile_fyers(plan, rows, preview_id, entry_order_id=None):
    """Never submit, cancel or infer fills from a position or chart price."""
    token = "CH" + hashlib.sha256(str(preview_id).encode()).hexdigest()[:24]
    parents = [row for row in rows if not row.get("parentId") and (
        str(row.get("id") or "") == str(entry_order_id) if entry_order_id
        else row.get("orderTag") in {token, "1:" + token})]
    base = {"account_id": plan.account_id, "broker": plan.broker, "symbol": plan.symbol,
            "retry_allowed": False, "protection_confirmed": False}
    def state(status, message, **fields):
        return dict(base, status=status, message=message, **fields)
    if len(parents) != 1:
        return state("BROKER_STATUS_UNAVAILABLE", "The owned entry is not uniquely present in the current broker order book. Do not resubmit.")
    parent = parents[0]
    side = 1 if plan.side == "BUY" else -1
    if (parent.get("symbol") != plan.symbol or parent.get("side") != side
            or parent.get("productType") != plan.product or _number(parent.get("qty")) != plan.quantity):
        raise ValueError("The native parent differs from the owned chart order.")
    parent_id = str(parent["id"])
    filled, remaining = _number(parent.get("filledQty")), _number(parent.get("remainingQuantity"))
    if min(filled, remaining) < 0 or filled+remaining > plan.quantity:
        raise ValueError("The native parent quantities cannot be reconciled.")
    if filled != int(filled) or remaining != int(remaining):
        raise ValueError("The native parent quantities are not whole units.")
    base.update(entry_order_id=parent_id, filled_quantity=int(filled), pending_quantity=int(remaining))
    expected_type = 4 if plan.entry_type == "STOP_LIMIT" else 1
    expected_stop = _number(plan.entry) if plan.entry_type == "STOP_LIMIT" else Decimal(0)
    if (parent.get("type") != expected_type
            or _number(parent.get("limitPrice")) != _number(plan.limit_price)
            or _number(parent.get("stopPrice")) != expected_stop):
        return state("BROKER_STATUS_UNAVAILABLE",
                     "The broker entry type or price differs from the reviewed chart level. Review the owned order; do not resubmit.")
    status = parent.get("status")
    base["unfilled_quantity"] = int(remaining)
    if status in {1,2,5,7}:
        base["pending_quantity"] = 0
    if (status not in {1,2,4,5,6,7}
            or (status == 2 and (filled != plan.quantity or remaining != 0))
            or (status in {4,6} and filled+remaining != plan.quantity)):
        return state("BROKER_STATUS_UNAVAILABLE", "The broker parent status and filled quantity cannot be reconciled.")
    if filled == 0:
        if status in {1,5,7}:
            return state({1:"CANCELLED",5:"REJECTED",7:"EXPIRED"}[status],
                         "The broker reports a terminal entry with no filled quantity.")
        if status not in {4,6}:
            return state("BROKER_STATUS_UNAVAILABLE", "The broker entry status and quantity disagree.")
        return state("ENTRY_PENDING", "Entry is pending at the broker; no entry fill is confirmed.",
                     linked_prices_match=(_number(parent.get("stopLoss",0)) == _number(plan.stop_loss)
                                          and _number(parent.get("takeProfit",0)) == _number(plan.target)))
    children = [row for row in rows if str(row.get("parentId") or "") == parent_id]
    exits = {"stop_loss": [], "target": []}
    for row in children:
        if row.get("symbol") != plan.symbol or row.get("side") != -side or row.get("productType") != plan.product:
            continue
        if row.get("type") in {3,4} and _number(row.get("stopPrice",0)) == _number(plan.stop_loss):
            exits["stop_loss"].append(row)
        elif row.get("type") == 1 and _number(row.get("limitPrice",0)) == _number(plan.target):
            exits["target"].append(row)
    if any(len(value) != 1 for value in exits.values()):
        return state("ENTRY_FILLED_EXITS_UNVERIFIED" if remaining == 0 else "ENTRY_PARTIALLY_FILLED_EXITS_UNVERIFIED",
                     "Entry fills are confirmed. Both marked, broker-linked exit orders are not yet verified.")
    stop, target = exits["stop_loss"][0], exits["target"][0]
    if any(not leg.get("id") for leg in (stop,target)) or len({parent_id, str(stop["id"]), str(target["id"])}) != 3:
        return state("ENTRY_FILLED_EXITS_UNVERIFIED", "The linked exit identities are missing or conflict.")
    quantities = []
    for leg in (stop,target):
        done, pending, total = (_number(leg.get(key)) for key in ("filledQty","remainingQuantity","qty"))
        if min(done,pending,total) < 0 or done+pending > total or any(v != int(v) for v in (done,pending,total)):
            raise ValueError("Linked exit quantities cannot be reconciled.")
        leg_status = leg.get("status")
        if (total > filled or (leg_status in {4,6} and done+pending != total)
                or (leg_status == 2 and (done != total or pending != 0))):
            return state("ENTRY_FILLED_EXITS_UNVERIFIED", "A linked exit status or quantity disagrees with the confirmed entry fills.")
        quantities.append((done,pending))
    exited = sum(value[0] for value in quantities)
    base.update(stop_order_id=str(stop["id"]), target_order_id=str(target["id"]), exited_quantity=int(exited))
    if exited > filled:
        return state("EXIT_QUANTITY_MISMATCH", "Linked exit fills exceed the confirmed entry fills. Broker review is required.")
    residual = filled-exited
    base["open_quantity"] = int(residual)
    if any(leg.get("status") not in {1,2,4,5,6,7} for leg in (stop,target)):
        return state("ENTRY_FILLED_EXITS_UNVERIFIED", "A linked exit has an unknown broker status.")
    if residual == 0:
        if remaining > 0 and status in {4,6}:
            return state("ENTRY_REMAINDER_PENDING", "Filled units exited, but the original entry still has pending quantity.")
        if any(leg.get("status") in {4,6} and qty[1] > 0 for leg,qty in zip((stop,target),quantities)):
            return state("EXIT_CANCELLATION_PENDING", "Exit fills cover the entry, but a linked sibling order remains active.")
        return state("CLOSED", "Broker-linked exit fills cover the entry; no linked order remains active.")
    protected = all(leg.get("status") in {4,6} and qty[1] == residual for leg,qty in zip((stop,target),quantities))
    return state("POSITION_PROTECTED" if protected else "ENTRY_FILLED_EXITS_UNVERIFIED",
                 "Both marked linked exits cover the currently open filled quantity." if protected else
                 "Entry fills are confirmed, but both linked exits do not cover the open quantity.",
                 protection_confirmed=protected)
