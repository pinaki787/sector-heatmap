#!/usr/bin/env python3
"""Read-only exposure gate for a selected FYERS/Delta dashboard reload."""
import argparse,hashlib,json,re,sqlite3,time
from decimal import Decimal
from pathlib import Path

def number(value):
    if value is None or isinstance(value,bool):raise ValueError("Missing broker quantity.")
    value=Decimal(str(value))
    if not value.is_finite():raise ValueError("Nonfinite broker quantity.")
    return value

def inspect(workspace):
    root=Path(__file__).resolve().parents[1]
    registry=root/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        row=db.execute("SELECT broker,credential_identity FROM accounts WHERE id=?",(workspace,)).fetchone()
    if not row or row[0] not in {"FYERS","DELTA_INDIA"}:raise ValueError("Select an eligible registered workspace.")
    broker,digest=row;folder=registry.parent/"accounts"/workspace
    credentials=json.loads((folder/"credentials.json").read_text())
    result=dict(broker=broker,read_only=True,orders_submitted=0,checked_at=time.time())
    if broker=="FYERS":
        from sector_heatmap.fyers_transport import client as client_factory
        saved=json.loads((folder/"home/.fyers/token.json").read_text())
        app=credentials.get("FYERS_APP_ID")
        if not app or saved.get("app_id")!=app or hashlib.sha256(("FYERS|"+app).encode()).hexdigest()!=digest:
            raise ValueError("Saved application binding differs.")
        client=client_factory(client_id=app,token=saved["access_token"])
        try:
            profile=client.get_profile()
            identity=(profile.get("data") or {}).get("fy_id") if profile.get("s")=="ok" else None
            if not identity:raise ValueError("Native profile unavailable.")
            positions=client.positions();orders=client.orderbook()
            if positions.get("s")!="ok" or not isinstance(positions.get("netPositions"),list):raise ValueError("Native positions unavailable.")
            if orders.get("s")!="ok" or not isinstance(orders.get("orderBook"),list):raise ValueError("Native orders unavailable.")
            rows=orders["orderBook"]
            if any(r.get("status") not in {1,2,4,5,6,7} or str(r.get("clientId") or "")!=str(identity) for r in rows):
                raise ValueError("Order status or account binding cannot be verified.")
            open_positions=sum(number(r.get("netQty"))!=0 for r in positions["netPositions"])
            open_orders=sum(r["status"] in {4,6} for r in rows)
        finally:client._sector_pulse_ipv4_session.close()
    else:
        from sector_heatmap.delta_india import DeltaIndia,delta_request_session
        key=credentials.get("DELTA_INDIA_API_KEY")
        if not key or hashlib.sha256(("DELTA_INDIA|"+key).encode()).hexdigest()!=digest:
            raise ValueError("Saved application binding differs.")
        client=object.__new__(DeltaIndia)
        client.clock=time.time;client.requester=delta_request_session();client._credentials=lambda:credentials
        try:
            positions=client._private("GET","/v2/positions/margined")
            rows=positions.get("result")
            if not isinstance(rows,list) or (positions.get("meta") or {}).get("after"):raise ValueError("Position coverage unavailable.")
            open_positions=sum(number(r.get("size"))!=0 for r in rows)
            orders=[];seen=set();cursor=None
            for page in range(20):
                params=dict(states="open,pending",page_size=100)
                if cursor:params["after"]=cursor
                reply=client._private("GET","/v2/orders",params=params)
                rows=reply.get("result")
                if not isinstance(rows,list):raise ValueError("Native orders unavailable.")
                if any(r.get("state") not in {"open","pending"} for r in rows):raise ValueError("Unexpected active-order state.")
                orders.extend(rows);cursor=(reply.get("meta") or {}).get("after")
                if not cursor:break
                if cursor in seen:raise ValueError("Repeated order page.")
                seen.add(cursor)
            else:raise ValueError("Order pagination incomplete.")
            open_orders=len(orders)
        finally:client.requester.close()
    result.update(open_positions=int(open_positions),open_orders=int(open_orders),
                  gate="PASS" if open_positions==0 and open_orders==0 else "BLOCKED_EXPOSURE")
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--workspace",required=True);args=parser.parse_args()
    if not re.fullmatch("[a-f0-9]{32}",args.workspace):raise ValueError("Exact workspace required.")
    try:result=inspect(args.workspace)
    except Exception as error:result=dict(read_only=True,orders_submitted=0,gate="UNVERIFIED",error_type=type(error).__name__)
    print(json.dumps(result))
if __name__=="__main__":main()
