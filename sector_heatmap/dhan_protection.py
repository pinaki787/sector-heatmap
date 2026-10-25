"""Read-only native Dhan Super Order registration reconciliation.

Reference: https://dhanhq.co/docs/v2/super-order/
Server-held exit registration is distinct from an exchange exit fill.
"""
from decimal import Decimal,InvalidOperation

def number(value):
    if isinstance(value,bool):raise ValueError("Invalid numeric broker evidence.")
    try:value=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError):raise ValueError("Missing broker numeric evidence.") from None
    if not value.is_finite():raise ValueError("Nonfinite broker evidence.")
    return value

def reconcile(ticket,protection,order_id,correlation,rows,tick):
    base=dict(protection_requested=bool(protection),protection_confirmed=False,
        protection_state="UNVERIFIED",protected_quantity=0,no_order_action=True)
    try:
        if not isinstance(rows,list) or not order_id or not correlation:raise ValueError()
        matches=[r for r in rows if str(r.get("orderId"))==str(order_id)]
        if len(matches)!=1:raise ValueError()
        parent=matches[0]
        if str(parent.get("correlationId"))!=str(correlation) or str(parent.get("dhanClientId"))!=str(ticket["dhanClientId"]):
            raise ValueError()
        for key in ("transactionType","exchangeSegment","productType","securityId"):
            if str(parent.get(key))!=str(ticket[key]):raise ValueError()
        quantity=number(ticket["quantity"]);step=number(tick)
        if quantity<=0 or quantity!=int(quantity) or step<=0 or number(parent.get("quantity"))!=quantity:raise ValueError()
        if ticket["transactionType"] not in {"BUY","SELL"} or parent.get("afterMarketOrder") is True:raise ValueError()
        stop,target=number(protection["stop_loss_price"]),number(protection["target_price"])
        if stop<=0 or target<=0:raise ValueError()
        if parent.get("legName")!="ENTRY_LEG":raise ValueError()
        filled=number(parent.get("filledQty"));remaining=number(parent.get("remainingQuantity"))
        if filled<0 or remaining<0 or filled+remaining!=quantity:raise ValueError()
        if parent.get("orderStatus")!="TRADED" or filled!=quantity:
            return dict(base,protection_state="AWAITING_FULL_ENTRY_FILL")
        if number(parent.get("averageTradedPrice"))<=0:raise ValueError()
        children=parent.get("legDetails")
        if not isinstance(children,list):raise ValueError()
        expected_side="SELL" if ticket["transactionType"]=="BUY" else "BUY"
        for name,key in (("STOP_LOSS_LEG","stop_loss_price"),("TARGET_LEG","target_price")):
            legs=[r for r in children if r.get("legName")==name]
            if len(legs)!=1:raise ValueError()
            leg=legs[0]
            if str(leg.get("orderId"))!=str(order_id) or leg.get("transactionType")!=expected_side:
                raise ValueError()
            if leg.get("orderStatus") not in {"PENDING","TRANSIT"}:
                return dict(base,protection_state="EXIT_NOT_REGISTERED_PENDING")
            if abs(number(leg.get("price"))-number(protection[key]))>step/2:
                return dict(base,protection_state="LEVEL_MISMATCH")
            # Super-order children can have zero trigger quantity until activated.
            # The linked full parent quantity owns the server-held exit plan.
            for field in ("totalQuatity","totalQuantity","remainingQuantity"):
                if leg.get(field) is not None and number(leg[field]) not in (0,quantity):raise ValueError()
        return dict(base,protection_confirmed=True,protection_state="BROKER_REGISTERED_FILLED_ENTRY",
            protected_quantity=int(quantity),entry_order_id=str(order_id),entry_fill_price=str(number(parent["averageTradedPrice"])),
            entry_side=ticket["transactionType"],
            reason="Exact fully filled Super parent and both server-held exit roles match the requested contract and prices; this is not an exit fill guarantee.")
    except (ValueError,KeyError,TypeError,InvalidOperation):
        return dict(base,reason="Exact native Super Order ownership, fills and exit registration are unverified.")
