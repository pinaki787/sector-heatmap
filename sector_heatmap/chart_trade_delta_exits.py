"""Reconcile a Delta chart position against complete native fills and bracket records."""
from decimal import Decimal, InvalidOperation


def number(value):
    try:
        value=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError("Delta native quantity or price evidence is unavailable.") from None
    if not value.is_finite():
        raise ValueError("Delta native quantity or price evidence is invalid.")
    return value


def verify_delta_exits(plan,parent,orders,fills,position):
    """No mutations. Call only with complete product-filtered snapshots since entry."""
    product_id=str(parent["product_id"])
    entry_id=str(parent["id"])
    filled=number(parent["size"])-number(parent["unfilled_size"])
    side=plan.side.lower()
    opposite="sell" if side=="buy" else "buy"
    def result(status,message,**fields):
        return dict(status=status,message=message,protection_confirmed=False,**fields)
    unique={}
    for row in orders:
        if str(row.get("product_id"))!=product_id:
            raise ValueError("Delta order evidence contains another product.")
        key=str(row.get("id") or "")
        if not key:
            raise ValueError("A Delta bracket order identifier is unavailable.")
        if key in unique and unique[key]!=row:
            raise ValueError("Delta order snapshots changed during reconciliation.")
        if row.get("state") not in {"open","pending","closed","cancelled"}:
            raise ValueError("A Delta native order has an unknown state.")
        unique[key]=row
    brackets={"stop_loss":[],"target":[]}
    active_foreign=False
    for key,row in unique.items():
        if key==entry_id:
            continue
        kind=row.get("stop_order_type")
        level="stop_loss" if kind=="stop_loss_order" else "target" if kind=="take_profit_order" else None
        matches=(level and row.get("bracket_order") is True and row.get("reduce_only") is True
                 and row.get("side")==opposite and row.get("order_type")=="market_order"
                 and row.get("stop_trigger_method")==plan.exit_trigger_method
                 and (row.get("meta_data") or {}).get("parent_type")=="position"
                 and bool((row.get("meta_data") or {}).get("parent_id"))
                 and number(row.get("stop_price"))==number(getattr(plan,level)))
        if matches:
            brackets[level].append(row)
        elif row.get("state") in {"open","pending"}:
            active_foreign=True
    if active_foreign:
        return result("POSITION_OWNERSHIP_CONFLICT","Another active Delta product order prevents verification of this chart setup.")
    exit_ids={str(row["id"]) for rows in brackets.values() for row in rows}
    entry_fills=Decimal(0);exit_fills=Decimal(0);seen={}
    for fill in fills:
        if str(fill.get("product_id") or (fill.get("product") or {}).get("id"))!=product_id:
            raise ValueError("Delta fill evidence contains another product.")
        key=str(fill.get("id") or "")
        if not key:
            raise ValueError("A native Delta fill identifier is unavailable.")
        if key in seen:
            if seen[key]!=fill:raise ValueError("Conflicting Delta fill records.")
            continue
        seen[key]=fill
        qty=number(fill.get("size"))
        if qty<=0 or qty!=int(qty):
            raise ValueError("Invalid Delta executed contract quantity.")
        order_id=str(fill.get("order_id") or "")
        if order_id==entry_id and fill.get("side")==side:
            entry_fills+=qty
        elif order_id in exit_ids and fill.get("side")==opposite:
            exit_fills+=qty
        else:
            return result("POSITION_OWNERSHIP_CONFLICT","Unrelated Delta fills changed this product after the chart entry.")
    if entry_fills!=filled or exit_fills>entry_fills:
        return result("BROKER_STATUS_UNAVAILABLE","Delta entry and exit fills do not yet reconcile with the native order.")
    residual=entry_fills-exit_fills
    expected=residual if side=="buy" else -residual
    if number(position)!=expected:
        return result("POSITION_OWNERSHIP_CONFLICT","The current Delta position differs from the chart-owned executed quantity.")
    common=dict(open_quantity=int(residual),exited_quantity=int(exit_fills),
                bracket_order_ids=sorted(exit_ids))
    active={}
    for level,rows in brackets.items():
        active[level]=[row for row in rows if row.get("state") in {"open","pending"}]
    if residual==0:
        if parent.get("state") in {"open","pending"} and number(parent["unfilled_size"])>0:
            return result("ENTRY_REMAINDER_PENDING","Filled units exited but the Delta entry still has pending quantity.",**common)
        if any(active.values()):
            return result("EXIT_CANCELLATION_PENDING","Exit fills cover the chart entry, but a native bracket sibling is still active.",**common)
        if exit_fills>0:
            return result("CLOSED","Native Delta bracket fills cover the entry, the position is flat and no bracket sibling remains active.",**common)
        return result("BROKER_STATUS_UNAVAILABLE","No chart entry or exit fills are available.",**common)
    if any(len(rows)!=1 for rows in active.values()):
        return result("ENTRY_FILLED_EXITS_UNVERIFIED","Both marked Delta position-bracket exits are not uniquely active.",**common)
    parents={str((rows[0].get("meta_data") or {}).get("parent_id")) for rows in active.values()}
    if len(parents)!=1:
        return result("ENTRY_FILLED_EXITS_UNVERIFIED","The Delta bracket legs belong to different native position groups.",**common)
    for row in [active["stop_loss"][0],active["target"][0]]:
        total,unfilled=(number(row.get(key)) for key in ("size","unfilled_size"))
        if min(total,unfilled)<0 or total!=int(total) or unfilled!=int(unfilled) or unfilled>total or unfilled!=residual:
            return result("ENTRY_FILLED_EXITS_UNVERIFIED","The native Delta bracket quantities do not cover the open chart position.",**common)
    return dict(status="POSITION_PROTECTED",message="Both marked native Delta bracket exits cover the current chart-owned position.",
                protection_confirmed=True,stop_order_id=str(active["stop_loss"][0]["id"]),
                target_order_id=str(active["target"][0]["id"]),**common)
