"""Read-only FYERS protection reconciliation; never creates or changes orders."""
from decimal import Decimal, InvalidOperation

def number(value):
    if isinstance(value, bool):
        raise ValueError("Invalid numeric broker evidence.")
    try:
        v = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Missing numeric broker evidence.") from None
    if not v.is_finite():
        raise ValueError("Nonfinite broker evidence.")
    return v


def reconcile(preview, order_ids, book):
    base = dict(protection_requested=bool(preview.get("protection")), protection_confirmed=False,
                protection_state="UNVERIFIED", protected_quantity=0, no_order_action=True)
    try:
        leg = preview["instrument"]["contracts"][0]
        if preview["instrument"]["kind"] not in {"EQUITY", "LONG_OPTION"}:
            return dict(base, protection_state="NOT_APPLICABLE", reason="Defined-risk spreads use their separate leg reconciliation.")
        if len(order_ids) != 1 or not isinstance(book, dict) or book.get("s") != "ok":
            return dict(base, reason="Exact parent order and successful fresh order book required.")
        rows = book.get("orderBook")
        if not isinstance(rows, list):
            return dict(base, reason="Broker order book unavailable.")
        matches = [r for r in rows if str(r.get("id")) == str(order_ids[0])]
        if len(matches) != 1:
            return dict(base, reason="Exact parent order is missing or ambiguous.")
        parent = matches[0]
        side = 1 if leg["action"] == "BUY" else -1
        quantity = number(leg["quantity"])
        if parent.get("symbol") != leg["symbol"] or number(parent.get("side")) != side or number(parent.get("qty")) != quantity:
            return dict(base, reason="Parent contract, direction or quantity differs from the submitted plan.")
        if parent.get("productType") != preview["order_policy"]["product_type"]:
            return dict(base, reason="Parent product differs from the submitted plan.")
        status = parent.get("status")
        if status not in {2, 4, 6}:
            return dict(base, protection_state="TERMINAL_OR_UNKNOWN", reason="Parent is rejected, cancelled, expired or unknown.")
        protection = preview.get("protection") or {}
        stop, target = number(protection.get("stop_loss_price")), number(protection.get("target_price"))
        tick = number(leg.get("tick_size"))
        if tick <= 0:
            raise ValueError("Invalid contract tick.")
        # FYERS fields may be absolute reflected levels or explicit point offsets.
        # Never infer offset semantics when the broker omits legType.
        sl, tp = number(parent.get("stopLoss")), number(parent.get("takeProfit"))
        if sl <= 0 or tp <= 0:
            return dict(base, reason="Broker has not registered both stop-loss and take-profit.")
        if parent.get("legType") == 1:
            reference = number(parent.get("tradedPrice")) if status == 2 else number(parent.get("limitPrice"))
            actual_stop, actual_target = reference - side * sl, reference + side * tp
        elif parent.get("legType") in (None, 0):
            actual_stop, actual_target = sl, tp
        else:
            return dict(base, reason="Broker exit units are unsupported or ambiguous.")
        if abs(actual_stop-stop) > tick / 2 or abs(actual_target-target) > tick / 2:
            return dict(base, protection_state="LEVEL_MISMATCH", reason="Broker exit levels differ from the validated recommendation.",
                        broker_stop=str(actual_stop), broker_target=str(actual_target))
        filled = number(parent.get("filledQty", 0))
        remaining = number(parent.get("remainingQuantity", quantity-filled))
        if filled < 0 or filled > quantity or remaining < 0 or filled + remaining != quantity:
            return dict(base, reason="Broker fill quantities are inconsistent.")
        if status != 2 or filled != quantity:
            return dict(base, protection_state="REGISTERED_AWAITING_FILL", registered_quantity=int(quantity),
                        reason="Broker registered exits; full entry fill is not confirmed.")
        entry_price=number(parent.get("tradedPrice"))
        if entry_price<=0:return dict(base,reason="Positive broker-confirmed entry average required.")
        return dict(base, protection_confirmed=True, protection_state="BROKER_REGISTERED_FILLED_ENTRY",
                    protected_quantity=int(filled), entry_fill_price=str(entry_price), broker_stop=str(actual_stop), broker_target=str(actual_target),
                    reason="Fresh exact filled parent reflects the requested stop-loss and target. This is broker registration evidence, not a guarantee of exit execution.")
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return dict(base, reason="Incomplete or invalid protection evidence; no order was changed.")
