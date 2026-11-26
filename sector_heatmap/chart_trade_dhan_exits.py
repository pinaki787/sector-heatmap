"""Pure Dhan chart exit-fill proof from complete native day snapshots.

Never infer closure from CLOSED Super state, a triggered leg, or flat position.
The caller must first verify the exact Super parent and current account identity.
"""
from datetime import datetime
from .dhan_protection import number
from .dhan_execution import IST


def reconcile_dhan_exits(plan, contract, parent, *, client_id, preview_id, orders, trades, positions):
    base = dict(account_id=plan.account_id, broker=plan.broker, symbol=plan.symbol,
                retry_allowed=False, protection_confirmed=False)
    def result(status, message, **fields):
        return dict(base, status=status, message=message, **fields)
    def stamp(value):
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
        except (ValueError, TypeError):
            raise ValueError("Native Dhan order/trade time is unavailable.") from None
    try:
        if plan.broker != "DHAN" or not isinstance(parent,dict) or not parent.get("orderId"):
            raise ValueError("An exact owned Dhan Super parent is required.")
        if any(not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows)
               for rows in (orders,trades,positions)):
            raise ValueError("Complete native Dhan day snapshots are required.")
        from .chart_trade_dhan_reconciliation import reconcile_dhan_super
        proof = reconcile_dhan_super(plan,contract,preview_id=preview_id,
            broker_client_id=client_id,rows=[parent],entry_order_id=parent["orderId"])
        if proof["status"] == "BROKER_STATUS_UNAVAILABLE":
            return proof
        started = stamp(parent.get("createTime"))
        owned_id = str(parent["orderId"])
        security = str(contract["security_id"])
        segment = contract["exchange_segment"]
        def same(row):
            if str(row.get("dhanClientId") or "") != str(client_id):
                raise ValueError("Dhan snapshots contain unverified account identity.")
            if not row.get("securityId") or not row.get("exchangeSegment") or not row.get("productType"):
                raise ValueError("Dhan native instrument identity is incomplete.")
            return (str(row["securityId"]) == security and row["exchangeSegment"] == segment
                    and row["productType"] == plan.product)
        for key, expected in (("dhanClientId",client_id),("securityId",security),
                              ("exchangeSegment",segment),("productType",plan.product),
                              ("transactionType",plan.side)):
            if str(parent.get(key)) != str(expected):
                raise ValueError("The native Dhan Super parent ownership differs.")
        if number(parent.get("quantity")) != plan.quantity or parent.get("legName") != "ENTRY_LEG":
            raise ValueError("The native Dhan Super parent role or quantity differs.")
        filled = number(parent.get("filledQty"))
        if filled <= 0 or filled != int(filled) or filled > plan.quantity:
            raise ValueError("Native Dhan entry fills are unavailable.")
        base.update(entry_order_id=owned_id,filled_quantity=int(filled))
        terminal={"TRADED","CANCELLED","REJECTED","EXPIRED"}
        active={"TRANSIT","PENDING","PART_TRADED"}
        roles={"ENTRY_LEG":[],"STOP_LOSS_LEG":[],"TARGET_LEG":[]}
        for row in orders:
            if not same(row):continue
            state=row.get("orderStatus")
            if state not in terminal|active:
                raise ValueError("Unknown native Dhan exchange-order status.")
            if str(row.get("orderId")) != owned_id:
                if state in active:
                    return result("POSITION_OWNERSHIP_CONFLICT","An unrelated active Dhan contract order prevents chart ownership verification.")
                continue
            role=row.get("legName")
            if role not in roles:
                raise ValueError("An owned Dhan exchange order has no verified leg role.")
            roles[role].append(row)
        if any(len(rows)!=1 for rows in roles.values()):
            return result("ENTRY_FILLED_EXITS_UNVERIFIED","All three owned Dhan exchange-order roles are not uniquely available.")
        exchange_ids={}
        quantities={}
        opposite="SELL" if plan.side=="BUY" else "BUY"
        for role,rows in roles.items():
            row=rows[0]
            if row.get("transactionType") != (plan.side if role=="ENTRY_LEG" else opposite):
                raise ValueError("A Dhan exchange leg has the wrong side.")
            total,done,pending=(number(row.get(key)) for key in ("quantity","filledQty","remainingQuantity"))
            if min(total,done,pending)<0 or done+pending>total or any(v!=int(v) for v in (total,done,pending)):
                raise ValueError("Dhan exchange-leg quantities do not reconcile.")
            if role=="ENTRY_LEG" and (total!=plan.quantity or done!=filled):
                raise ValueError("Dhan exchange and Super entry fills disagree.")
            if row["orderStatus"]=="TRADED" and done!=total or row["orderStatus"]=="REJECTED" and done:
                raise ValueError("Dhan exchange-leg status and fill quantities disagree.")
            exchange_id=str(row.get("exchangeOrderId") or "")
            if exchange_id:
                if exchange_id in exchange_ids:raise ValueError("Dhan leg exchange-order identity is ambiguous.")
                exchange_ids[exchange_id]=role
            elif done>0 or row.get("orderStatus") in {"TRADED","PART_TRADED"}:
                raise ValueError("A filled Dhan exchange leg has no native exchange-order ID.")
            quantities[role]=(done,pending)
        sums={role:number(0) for role in roles}
        seen={}
        for trade in trades:
            if not same(trade):continue
            trade_time=stamp(trade.get("exchangeTime"))
            if trade_time<started:continue
            if str(trade.get("orderId")) != owned_id:
                return result("POSITION_OWNERSHIP_CONFLICT","Unrelated Dhan fills changed this contract after the chart entry.")
            role=exchange_ids.get(str(trade.get("exchangeOrderId") or ""))
            if not role:raise ValueError("A Dhan fill cannot be mapped to an owned exchange leg.")
            if trade.get("transactionType") != (plan.side if role=="ENTRY_LEG" else opposite):
                raise ValueError("An owned Dhan fill has the wrong side.")
            trade_id=str(trade.get("exchangeTradeId") or "")
            qty=number(trade.get("tradedQuantity"));price=number(trade.get("tradedPrice"))
            if not trade_id or qty<=0 or qty!=int(qty) or price<=0:
                raise ValueError("Native Dhan trade identity, quantity or price is invalid.")
            evidence=(role,str(qty),str(price),trade_time)
            if trade_id in seen:
                if seen[trade_id]!=evidence:raise ValueError("Conflicting duplicate Dhan trade identity.")
                continue
            seen[trade_id]=evidence;sums[role]+=qty
        if any(sums[role]!=quantities[role][0] for role in roles):
            return result("BROKER_STATUS_UNAVAILABLE","Dhan exchange order fills and actual trade-book fills do not yet agree.")
        exited=sums["STOP_LOSS_LEG"]+sums["TARGET_LEG"]
        if exited>filled:raise ValueError("Dhan exit fills exceed owned entry fills.")
        residual=filled-exited
        net=number(0);matched_positions=0
        for row in positions:
            if same(row):
                matched_positions+=1
                if matched_positions>1:raise ValueError("Duplicate native Dhan contract position evidence.")
                value=number(row.get("netQty"))
                if value!=int(value):raise ValueError("Dhan position quantity is invalid.")
                net+=value
        if net != (residual if plan.side=="BUY" else -residual):
            return result("POSITION_OWNERSHIP_CONFLICT","The native Dhan position differs from the chart-owned executed quantity.")
        base.update(exited_quantity=int(exited),open_quantity=int(residual))
        if residual:
            return result("ENTRY_FILLED_EXITS_UNVERIFIED","Native Dhan fills leave an open quantity; current protection registration must be checked separately.")
        entry=roles["ENTRY_LEG"][0]
        if entry["orderStatus"] in active:
            return result("ENTRY_REMAINDER_PENDING","Filled units exited, but the original Dhan entry remains active.")
        if any(rows[0]["orderStatus"] in active for role,rows in roles.items() if role!="ENTRY_LEG"):
            return result("EXIT_CANCELLATION_PENDING","Exit fills cover the entry, but a Dhan linked sibling remains active.")
        return result("CLOSED","Actual owned Dhan exit trades cover entry fills, the position is flat, and all owned exchange legs are terminal.")
    except (ValueError,KeyError,TypeError) as error:
        return result("BROKER_STATUS_UNAVAILABLE",str(error) or "Native Dhan exit evidence is unverified.")
