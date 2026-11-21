#!/usr/bin/env python3
"""Read-only schema probe for one saved FYERS workspace. Never places orders."""
import argparse
from datetime import datetime,timedelta
import hashlib,json,re,sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo
from sector_heatmap.fyers_transport import client as fyers_client

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workspace",required=True)
    args=parser.parse_args()
    if not re.fullmatch("[a-f0-9]{32}",args.workspace):raise ValueError("Exact workspace required.")
    root=Path(__file__).resolve().parents[1]
    registry=root/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        row=db.execute("SELECT broker,account_ref,credential_identity FROM accounts WHERE id=?",(args.workspace,)).fetchone()
    if not row or row[0]!="FYERS":raise ValueError("A registered FYERS workspace is required.")
    folder=registry.parent/"accounts"/args.workspace
    credentials=json.loads((folder/"credentials.json").read_text())
    saved=json.loads((folder/"home/.fyers/token.json").read_text())
    if (not saved.get("app_id") or saved["app_id"]!=credentials.get("FYERS_APP_ID")
            or hashlib.sha256(("FYERS|"+saved["app_id"]).encode()).hexdigest()!=row[2]):
        raise ValueError("Saved session app differs from selected workspace.")
    client=fyers_client(client_id=saved["app_id"],token=saved["access_token"])
    profile=client.get_profile()
    if not isinstance(profile,dict) or profile.get("s")!="ok":
        print(json.dumps(dict(read_only=True,status="SESSION_UNAVAILABLE",broker_requests=1)));return
    identity=(profile.get("data") or {}).get("fy_id")
    # FYERS account_ref is a user-entered reference and may be an app ID.
    # Its enforced registry binding is credential_identity (app hash), unlike Dhan/Motilal.
    if not identity:
        print(json.dumps(dict(read_only=True,status="NATIVE_IDENTITY_UNAVAILABLE",broker_requests=1)));return
    today=datetime.now(ZoneInfo("Asia/Kolkata")).date()
    result=dict(read_only=True,status="ACCOUNT_VERIFIED",broker_orders_submitted=0,reports={})
    book=client.orderbook()
    book_rows=book.get("orderBook") if isinstance(book,dict) and book.get("s")=="ok" else None
    if not isinstance(book_rows,list):
        result["current_order_schema"]=dict(status="UNAVAILABLE")
    else:
        result["current_order_schema"]=dict(status="SCHEMA_SAMPLED" if book_rows else "EMPTY",
            rows=len(book_rows),
            required_entry_fields_present=all(all(k in r for k in ("type","limitPrice","stopPrice","id","symbol")) for r in book_rows),
            linked_parent_rows=sum(bool(r.get("parentId")) for r in book_rows),
            fields=sorted({k for r in book_rows for k in r}))
    selected_symbol=None
    for name in ("order-history","trade-history"):
        response=client._sector_pulse_ipv4_session.get(
            "https://api-t1.fyers.in/api/v3/"+name,headers={"Authorization":client.header},
            params=dict(from_date=(today-timedelta(days=1)).isoformat(),to_date=today.isoformat(),
                        page_size="2",page_no="1",segment_type="0",exchange_type="0"),timeout=15)
        if response.status_code in {401,403}:
            result["reports"][name]=dict(status="ACCESS_UNAVAILABLE",http_status=response.status_code);break
        response.raise_for_status()
        reply=response.json()
        rows=reply.get("data") if isinstance(reply,dict) and reply.get("s")=="ok" else None
        if not isinstance(rows,list):
            result["reports"][name]=dict(status="REPORT_UNAVAILABLE",code=reply.get("code") if isinstance(reply,dict) else None);break
        if any(str(r.get("clientId") or "").upper()!=str(identity).upper() for r in rows):
            result["reports"][name]=dict(status="REPORT_ACCOUNT_MISMATCH");break
        if rows and selected_symbol is None:selected_symbol=rows[0]["symbol"]
        result["reports"][name]=dict(status="SCHEMA_SAMPLED" if rows else "EMPTY_WINDOW",
            sample_count=len(rows),fields=sorted({k for r in rows for k in r}),
            field_types={k:sorted({type(r[k]).__name__ for r in rows if k in r}) for k in sorted({k for r in rows for k in r})},
            all_rows_account_match=True)
    if selected_symbol and all(value["status"] in {"SCHEMA_SAMPLED","EMPTY_WINDOW"} for value in result["reports"].values()):
        from sector_heatmap.chart_trade_fyers_history import read_reports
        import time
        def reader(name,params):
            response=client._sector_pulse_ipv4_session.get(
                "https://api-t1.fyers.in/api/v3/"+name,headers={"Authorization":client.header},
                params=params,timeout=15)
            response.raise_for_status()
            return response.json()
        now=time.time()
        # Narrow exact native symbol, bounded pagination, no raw financial rows in output.
        try:
            evidence=read_reports(reader,symbol=selected_symbol,
                identity_hash=hashlib.sha256(str(identity).encode()).hexdigest(),
                started_at=datetime.combine(today-timedelta(days=1),datetime.min.time(),
                                            ZoneInfo("Asia/Kolkata")).timestamp(),now=now,
                page_size=100,max_pages=5)
            final=client.get_profile()
            if final.get("s")!="ok" or (final.get("data") or {}).get("fy_id")!=identity:
                raise PermissionError("Identity changed.")
            result["reader_validation"]=dict(status="COMPLETE_SELECTED_SYMBOL",
                rows={name:len(rows) for name,rows in evidence.items()},identity_rechecked=True)
        except Exception as error:
            result["reader_validation"]=dict(status="UNVERIFIED",error_type=type(error).__name__)
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
