#!/usr/bin/env python3
"""Read-only selected-workspace Delta schema probe; never submits or alters orders."""
import argparse,hashlib,json,re,sqlite3,time
from pathlib import Path
from sector_heatmap.delta_india import DeltaIndia,delta_request_session,BASE


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workspace",required=True)
    parser.add_argument("--symbol",default="BTCUSD")
    args=parser.parse_args()
    if not re.fullmatch("[a-f0-9]{32}",args.workspace) or not re.fullmatch("[A-Z0-9][A-Z0-9_-]{0,79}",args.symbol):
        raise ValueError("Choose an exact private workspace and listed symbol.")
    root=Path(__file__).resolve().parents[1]
    registry=root/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute("SELECT broker,credential_identity FROM accounts WHERE id=?",(args.workspace,)).fetchone()
    if not row or row["broker"]!="DELTA_INDIA":raise ValueError("A Delta India workspace is required.")
    credentials=json.loads((registry.parent/"accounts"/args.workspace/"credentials.json").read_text())
    key,secret=(credentials.get(name) for name in ("DELTA_INDIA_API_KEY","DELTA_INDIA_API_SECRET"))
    if not key or not secret or hashlib.sha256(("DELTA_INDIA|"+key).encode()).hexdigest()!=row["credential_identity"]:
        raise ValueError("The saved credentials do not match this registered workspace.")
    # No DeltaIndia constructor: no ledger/archive initialization or recovery writes.
    client=object.__new__(DeltaIndia)
    client.clock=time.time;client.requester=delta_request_session()
    client._credentials=lambda:credentials
    product=client.requester.get(BASE+"/v2/products/"+args.symbol,timeout=15).json()["result"]
    if product.get("symbol")!=args.symbol:raise ValueError("Exact native product mismatch.")
    pid=product["id"];end=int(time.time()*1e6);start=end-30*86400*1000000
    output={"symbol":args.symbol,"read_only":True,"broker_orders_submitted":0}
    for name,path,params in [
        ("active","/v2/orders",dict(product_ids=pid,states="open,pending",page_size=100)),
        ("history","/v2/orders/history",dict(product_ids=pid,start_time=start,end_time=end,page_size=100)),
        ("fills","/v2/fills",dict(product_ids=pid,start_time=start,end_time=end,page_size=100))]:
        reply=client._private("GET",path,params=params)
        rows=reply.get("result")
        if not isinstance(rows,list):raise ValueError("Native read response is unavailable.")
        brackets=[item for item in rows if item.get("bracket_order") is True]
        from collections import Counter
        output[name+"_bracket_semantics"]={
            field:dict(Counter(str(item.get(field)) for item in brackets))
            for field in ("order_type","stop_order_type","stop_trigger_method","reduce_only","state")}
        ids={str(item.get("id")) for item in rows}
        output[name+"_bracket_parent_evidence"]={
            "metadata_fields":sorted({field for item in brackets for field in (item.get("meta_data") or {})}),
            "parent_types":dict(Counter(str((item.get("meta_data") or {}).get("parent_type")) for item in brackets)),
            "parent_present":sum((item.get("meta_data") or {}).get("parent_id") is not None for item in brackets),
            "parent_in_order_sample":sum(str((item.get("meta_data") or {}).get("parent_id")) in ids for item in brackets)}
        output[name+"_metadata_fields"]=sorted({field for item in rows for field in (item.get("meta_data") or {})})
        output[name+"_fill_position_fields"]=sorted({field for item in rows for field in ((item.get("meta_data") or {}).get("new_position") or {})})
        output[name+"_timestamps"]={"iso":sum("T" in str(item.get("created_at")) for item in rows),
                                    "digits":sum(str(item.get("created_at","")).isdigit() for item in rows)}
        output[name]=dict(sample_count=len(rows),has_more=bool((reply.get("meta") or {}).get("after")),
                          fields=sorted({field for item in rows for field in item}),
                          bracket_sample_count=len(brackets),
                          bracket_shapes=[{field:type(item.get(field)).__name__ for field in (
                              "id","product_id","bracket_order","reduce_only","order_type","stop_order_type",
                              "stop_trigger_method","stop_price","size","unfilled_size","state","created_at")} for item in brackets[:2]])
    print(json.dumps(output,indent=2))
if __name__=="__main__":main()
