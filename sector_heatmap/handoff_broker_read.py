"""Isolated read-only account evidence for Handoff automation.

Invoked in the selected account's isolated environment. No order mutations exist.
"""
import json
import math
import os
from pathlib import Path
from .exposure_guard import symbol_key, open_exposures

def finite(v,label,nonnegative=False):
    if isinstance(v,bool):raise ValueError(label+" is invalid.")
    try:value=float(v)
    except (TypeError,ValueError):raise ValueError(label+" unavailable.") from None
    if not math.isfinite(value) or nonnegative and value<0:raise ValueError(label+" invalid.")
    return value

def canonical(symbol):
    key=symbol_key(symbol)
    if not key or not key[0]:raise ValueError("Exact broker underlying unavailable.")
    return key[0]+":"+key[1]+"-EQ"

def fyers_fills(book):
    result=[]
    for row in book:
        if row.get("status") not in {2,4,6}:continue
        qty=finite(row.get("filledQty",0),"Filled quantity",True)
        if not qty:continue
        price=finite(row.get("tradedPrice"),"Average fill price",True)
        if price<=0:continue
        parents={str(row[k]) for k in ("parentId","id_parent") if row.get(k)}
        result.append(dict(id=str(row["id"]),symbol=row["symbol"],
            parent_id=next(iter(parents)) if len(parents)==1 else None,
            side="BUY" if row["side"]==1 else "SELL" if row["side"]==-1 else "UNKNOWN",
            filled=qty,requested=finite(row["qty"],"Requested quantity",True),price=price))
    return result

def fyers_state(positions,orders,funds,holdings):
    from .fyers_execution import available_funds
    if any(not isinstance(r,dict) or r.get("s")!="ok" for r in (positions,orders,funds,holdings)):
        raise ValueError("Fresh FYERS positions, orders, funds and holdings required.")
    pos=positions.get("netPositions")
    book=orders.get("orderBook")
    held=holdings.get("holdings")
    if not all(isinstance(r,list) for r in (pos,book,held)):
        raise ValueError("Complete FYERS exposure lists required.")
    exposures=open_exposures(pos,book)
    used={};daily=0.0;clean=[]
    for row in pos:
        qty=finite(row.get("netQty"),"Position quantity")
        # FYERS pl is total current-day realized plus unrealized P&L.
        daily+=finite(row.get("pl"),"Daily position P&L")
        if not qty:continue
        symbol=row.get("symbol");key=canonical(symbol)
        avg=next((row[k] for k in ("netAvg","avgPrice","buyAvg" if qty>0 else "sellAvg","ltp") if row.get(k) is not None and finite(row[k],"Position basis")>0),None)
        price=finite(avg,"Position valuation")
        if price<=0:raise ValueError("Positive position valuation required.")
        multiplier=finite(row.get("qtyMulti_com"),"Commodity contract multiplier",True) if str(symbol).startswith("MCX:") else 1
        if multiplier<=0:raise ValueError("Positive commodity multiplier required.")
        if row.get("crossCurrency")=="Y":
            multiplier*=finite(row.get("rbiRefRate"),"Cross currency reference rate",True)
        used[key]=used.get(key,0)+abs(qty)*price*multiplier
        clean.append(dict(symbol=symbol,netQty=qty,price=price,pnl=finite(row.get("pl"),"P&L")))
    for row in held:
        qty=finite(row.get("quantity"),"Holding quantity",True)
        if not qty:continue
        symbol=row.get("symbol");key=canonical(symbol)
        price=finite(row.get("costPrice",row.get("ltp")),"Holding valuation",True)
        used[key]=used.get(key,0)+qty*price
        exposures.append(dict(symbol=symbol,netQty=qty))
    for row in book:
        if str(row.get("status")) not in {"3","4","6"}:continue
        qty=finite(row.get("remainingQuantity"),"Pending quantity",True)
        price=finite(row.get("limitPrice") or row.get("stopPrice") or row.get("lp"),"Pending order valuation",True)
        key=canonical(row.get("symbol"))
        # Reserve each outstanding order, including multiple contracts of one
        # underlying. An unverified closing-order relationship cannot free capital.
        multiplier=finite(row.get("qtyMulti_com"),"Pending commodity multiplier",True) if str(row.get("symbol")).startswith("MCX:") else 1
        if multiplier<=0:raise ValueError("Positive pending contract multiplier required.")
        used[key]=used.get(key,0)+qty*price*multiplier
    return dict(positions_verified=True,orders_verified=True,holdings_verified=True,
                available_funds=available_funds(funds),used_capital=round(sum(used.values()),2),
                daily_loss=round(max(0,-daily),2),daily_pnl=round(daily,2),filled_orders=fyers_fills(book),exposed_underlyings=sorted({canonical(r["symbol"]) for r in exposures}),
                positions=clean)


def dhan_state(client_id,positions,orders,funds,holdings,resolve):
    """Native Dhan evidence; master resolution is supplied by the same account."""
    if not all(isinstance(rows,list) for rows in (positions,orders,holdings)) or not isinstance(funds,dict):
        raise ValueError("Complete native Dhan account reports required.")
    if str(funds.get("dhanClientId"))!=str(client_id) or any(str(r.get("dhanClientId",client_id))!=str(client_id) for r in positions+orders):
        raise PermissionError("Native Dhan account identity mismatch.")
    exposed=set();used={};daily=0.0;clean=[]
    for row in positions:
        qty=finite(row.get("netQty"),"Dhan net quantity")
        daily+=finite(row.get("realizedProfit"),"Dhan realized P&L")+finite(row.get("unrealizedProfit"),"Dhan unrealized P&L")
        if not qty:continue
        key=resolve(row,False)
        price=finite(row.get("buyAvg") if qty>0 else row.get("sellAvg"),"Dhan position basis",True)
        if price<=0:raise ValueError("Dhan position basis unavailable.")
        exposed.add(key);used[key]=used.get(key,0)+abs(qty)*price
        clean.append(dict(symbol=key,netQty=qty,price=price,pnl=finite(row["realizedProfit"],"Realized")+finite(row["unrealizedProfit"],"Unrealized")))
    for row in holdings:
        qty=finite(row.get("totalQty"),"Dhan holding quantity",True)
        if not qty:continue
        key=resolve(row,True);price=finite(row.get("avgCostPrice"),"Dhan holding cost",True)
        if price<=0:raise ValueError("Dhan holding basis unavailable.")
        exposed.add(key);used[key]=used.get(key,0)+qty*price
    for row in orders:
        status=row.get("orderStatus")
        if status in {"TRADED","CANCELLED","REJECTED","EXPIRED","CLOSED"}:continue
        if status not in {"TRANSIT","PENDING","PART_TRADED"}:raise ValueError("Unknown native Dhan order state.")
        key=resolve(row,False);exposed.add(key)
        remaining=finite(row.get("pendingQuantity"),"Dhan pending quantity",True)
        price=finite(row.get("price") or row.get("triggerPrice"),"Dhan pending valuation",True)
        if remaining and price<=0:raise ValueError("Dhan pending notional unavailable.")
        used[key]=used.get(key,0)+remaining*price
    cash=finite(funds.get("availabelBalance",funds.get("availableBalance")),"Dhan available funds",True)
    return dict(positions_verified=True,orders_verified=True,holdings_verified=True,
        available_funds=cash,used_capital=round(sum(used.values()),2),daily_loss=round(max(0,-daily),2),
        exposed_underlyings=sorted(exposed),positions=clean,daily_pnl=round(daily,2),
        filled_orders=[dict(id=str(r["orderId"]),symbol=r.get("tradingSymbol"),security_id=str(r.get("securityId")),
            correlation_id=r.get("correlationId"),leg_name=r.get("legName"),side=r.get("transactionType"),exchange_segment=r.get("exchangeSegment"),
            filled=finite(r.get("filledQty",0),"Dhan filled quantity",True),
            requested=finite(r.get("quantity"),"Dhan order quantity",True),
            price=finite(r.get("averageTradedPrice",0),"Dhan average fill",True))
            for r in orders if finite(r.get("filledQty",0),"Dhan filled quantity",True)>0])

def read_dhan():
    from datetime import datetime
    from .market_calendar import IST
    from .workspaces import WorkspaceStore
    from .dhan_execution import DhanExecutionService,contract_underlying
    store=WorkspaceStore(os.environ["SECTOR_PULSE_WORKSPACE_REGISTRY"])
    with store.db() as db:
        account=dict(db.execute("SELECT * FROM accounts WHERE id=?",(os.environ["SECTOR_PULSE_WORKSPACE_ID"],)).fetchone())
    if account["broker"]!="DHAN":raise PermissionError("Native Dhan account required.")
    execution=DhanExecutionService(account,store.folder(account));client=execution._client()
    positions=client.request("GET","/positions");orders=client.request("GET","/orders")
    funds=client.request("GET","/fundlimit");holdings=client.request("GET","/holdings")
    masters=execution.master.load(datetime.now(IST))
    def resolve(row,holding):
        security=str(row.get("securityId"))
        if holding:
            exchange=str(row.get("exchange") or "").upper()
            symbol=str(row.get("tradingSymbol") or "").removesuffix("-EQ")
            matches=[r for r in masters if str(r["SEM_SMST_SECURITY_ID"])==security and r["SEM_SEGMENT"]=="E"
                and (exchange=="ALL" or r["SEM_EXM_EXCH_ID"]==exchange) and str(r["SEM_TRADING_SYMBOL"]).removesuffix("-EQ")==symbol]
        else:
            segment=row.get("exchangeSegment")
            matches=[r for r in masters if str(r["SEM_SMST_SECURITY_ID"])==security and
                r["SEM_EXM_EXCH_ID"]+{"E":"_EQ","D":"_FNO","M":"_COMM","I":""}.get(r["SEM_SEGMENT"],"")==segment]
        keys={r["SEM_EXM_EXCH_ID"]+":"+contract_underlying(r)+"-EQ" for r in matches}
        if len(keys)!=1:raise ValueError("Native Dhan exposure has no unique owned master mapping.")
        return next(iter(keys))
    return dhan_state(client.client_id,positions,orders,funds,holdings,resolve)


def motilal_state(positions,orders,holdings,margin,resolve):
    """Native report quantities/amounts; margin rows are non-additive."""
    if not all(isinstance(rows,list) for rows in (positions,orders,holdings,margin)):
        raise ValueError("Complete owned Motilal reports are required.")
    from .motilal_strategy_broker import STATES
    values={}
    for code in (102,103,600,700):
        matches=[r for r in margin if str(r.get("srno"))==str(code)]
        if len(matches)!=1:raise ValueError("Exact native cash/F&O funds and daily P&L rows required.")
        values[code]=finite(matches[0].get("amount"),"Native margin/P&L")
    if min(values[102],values[103])<0:raise ValueError("Native available margin is negative.")
    used={};exposed=set();clean=[]
    for row in positions:
        bought=finite(row.get("buyquantity"),"Native bought quantity",True)
        sold=finite(row.get("sellquantity"),"Native sold quantity",True)
        net=bought-sold
        if not net:continue
        meta=resolve(row,False);key=meta["underlying"]
        base_qty=bought if net>0 else sold
        total=finite(row.get("buyamount") if net>0 else row.get("sellamount"),"Native position amount",True)
        if not base_qty or total<=0:raise ValueError("Native full position valuation unavailable.")
        basis=total/base_qty;used[key]=used.get(key,0)+abs(net)*basis;exposed.add(key)
        pnl=finite(row.get("bookedprofitloss"),"Native realized P&L")+finite(row.get("marktomarket"),"Native unrealized P&L")
        clean.append(dict(symbol=meta["symbol"],netQty=net,price=basis,pnl=pnl))
    for row in holdings:
        qty=finite(row.get("dpquantity"),"Native holding quantity",True)
        if not qty:continue
        meta=resolve(row,True);key=meta["underlying"]
        price=finite(row.get("buyavgprice"),"Native holding basis",True)
        if price<=0:raise ValueError("Native holding valuation unavailable.")
        used[key]=used.get(key,0)+qty*price;exposed.add(key)
    for row in orders:
        status=STATES.get(str(row.get("orderstatus") or "").strip().upper())
        if status is None:raise ValueError("Unknown native order status.")
        if status not in {3,4,6}:continue
        meta=resolve(row,False);key=meta["underlying"]
        qty=finite(row.get("totalqtyremaining"),"Native pending quantity",True)
        price=finite(row.get("price") or row.get("triggerprice"),"Native pending valuation",True)
        if qty and price<=0:raise ValueError("Native pending full notional unavailable.")
        used[key]=used.get(key,0)+qty*price;exposed.add(key)
    pnl=values[600]+values[700]
    return dict(positions_verified=True,orders_verified=True,holdings_verified=True,
        available_funds=min(values[102],values[103]),used_capital=round(sum(used.values()),2),
        daily_loss=round(max(0,-pnl),2),daily_pnl=round(pnl,2),positions=clean,
        exposed_underlyings=sorted(exposed),filled_orders=[])

def read_motilal():
    from .workspaces import WorkspaceStore
    from .motilal_service import Service
    store=WorkspaceStore(os.environ["SECTOR_PULSE_WORKSPACE_REGISTRY"])
    with store.db() as db:
        account=dict(db.execute("SELECT * FROM accounts WHERE id=?",(os.environ["SECTOR_PULSE_WORKSPACE_ID"],)).fetchone())
    if account["broker"]!="MOTILAL_OSWAL":raise PermissionError("Owned Motilal account required.")
    service=Service(store.folder(account),account)
    reports={name:service.book(name)["data"] for name in ("positions","orders","holdings","margin")}
    def resolve(row,holding):
        if holding:
            if int(row.get("nsesymboltoken") or 0)>0:exchange,token="NSE",row["nsesymboltoken"]
            elif int(row.get("bsescripcode") or 0)>0:exchange,token="BSE",row["bsescripcode"]
            else:raise ValueError("Native holding has no exact security token.")
        else:exchange,token=row["exchange"],row["symboltoken"]
        meta=service.master.exact("MO:"+str(exchange)+":"+str(int(token)))
        underlying=meta["exchange"].removesuffix("FO")+":"+meta["underlying"]+"-EQ"
        return dict(underlying=underlying,symbol=meta["symbol"])
    return motilal_state(reports["positions"],reports["orders"],reports["holdings"],reports["margin"],resolve)

def read():
    broker=os.getenv("SECTOR_PULSE_WORKSPACE_BROKER")
    if broker=="FYERS":
        from .fyers_execution import _current_client
        c=_current_client()
        return fyers_state(c.positions(),c.orderbook(),c.funds(),c.holdings())
    if broker=="DHAN":return read_dhan()
    if broker=="MOTILAL_OSWAL":return read_motilal()
    # Native adapters are selected explicitly; never use FYERS credentials as fallback.
    raise ValueError("Native broker exposure adapter is not integrated yet; no alternate broker is used.")

def public_read_error(error):
    from .motilal_api import MotilalError
    if isinstance(error,MotilalError) and error.auth_required:
        return 'Motilal sign-in is required or expired; reconnect this owned account. No new entry.'
    return str(error) if isinstance(error,ValueError) else 'Owned broker evidence unavailable.'


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",nargs="?",default="state",choices=("state","reconcile"))
    parser.add_argument("preview_id",nargs="?")
    args=parser.parse_args()
    try:
        if args.action=="state":state=read()
        else:
            broker=os.getenv("SECTOR_PULSE_WORKSPACE_BROKER")
            if broker=="FYERS":
                from .fyers_execution import FyersExecutionService
                service=FyersExecutionService()
            elif broker=="DHAN":
                from .workspaces import WorkspaceStore
                from .dhan_execution import DhanExecutionService
                store=WorkspaceStore(os.environ["SECTOR_PULSE_WORKSPACE_REGISTRY"])
                with store.db() as db:account=dict(db.execute("SELECT * FROM accounts WHERE id=?",(os.environ["SECTOR_PULSE_WORKSPACE_ID"],)).fetchone())
                service=DhanExecutionService(account,store.folder(account))
            else:raise ValueError("Native broker protection reconciliation is unavailable.")
            state=service.reconcile_protection(args.preview_id)
        print(json.dumps(dict(ok=True,state=state),allow_nan=False))
    except Exception as e:
        print(json.dumps(dict(ok=False,error=public_read_error(e))))
if __name__=="__main__":main()
