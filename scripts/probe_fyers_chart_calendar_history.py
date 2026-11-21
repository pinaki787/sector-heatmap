#!/usr/bin/env python3
"""Selected-worker FYERS calendar history validation; no order endpoints."""
import argparse,hashlib,json,math,sqlite3,sys,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--workspace",required=True);args=parser.parse_args()
    if len(args.workspace)!=32 or any(c not in "0123456789abcdef" for c in args.workspace):raise ValueError("Exact workspace required.")
    root=Path(__file__).resolve().parents[1];registry=root/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        account=db.execute("SELECT broker,credential_identity FROM accounts WHERE id=?",(args.workspace,)).fetchone()
    if not account or account[0]!="FYERS":raise ValueError("Selected FYERS workspace required.")
    folder=registry.parent/"accounts"/args.workspace;source=folder/"source"
    credentials=json.loads((folder/"credentials.json").read_text())
    saved=json.loads((folder/"home/.fyers/token.json").read_text())
    app=credentials.get("FYERS_APP_ID")
    if not app or saved.get("app_id")!=app or hashlib.sha256(("FYERS|"+app).encode()).hexdigest()!=account[1]:
        raise ValueError("Saved app binding differs.")
    sys.path.insert(0,str(source))
    import sector_heatmap
    sector_heatmap.__path__.insert(0,str(source/"sector_heatmap"))
    from sector_heatmap.fyers_transport import client as factory
    from sector_heatmap.fyers_history import history
    from sector_heatmap.chart_workspace import fetch_fyers_history
    client=factory(client_id=app,token=saved["access_token"])
    try:
        profile=client.get_profile()
        if profile.get("s")!="ok" or not (profile.get("data") or {}).get("fy_id"):
            raise ValueError("Selected profile unavailable.")
        cache={};requests_count=0;last_request=0
        class SelectedHistory:
            def history(self,data):
                nonlocal requests_count,last_request
                if data.get("symbol")!="NSE:NIFTY50-INDEX" or data.get("resolution")!="D":
                    raise ValueError("Unexpected historical scope.")
                key=json.dumps(data,sort_keys=True)
                if key not in cache:
                    if requests_count>=30:raise ValueError("History request budget exceeded.")
                    delay=max(0,1.5-(time.monotonic()-last_request))
                    if delay:time.sleep(delay)
                    requests_count+=1;last_request=time.monotonic()
                    cache[key]=history(client,data)
                return cache[key]
        bound=SelectedHistory();now=datetime.now(ZoneInfo("Asia/Kolkata"))
        def summarize(payload):
            rows=payload["rows"];stamps=[r[0] for r in rows]
            if stamps!=sorted(set(stamps)):raise ValueError("Duplicate or unordered candles.")
            for row in rows:
                if len(row)<6 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in row[:5]):
                    raise ValueError("Invalid broker OHLC.")
                if row[2]<max(row[1],row[3],row[4]) or row[3]>min(row[1],row[2],row[4]):raise ValueError("Invalid OHLC range.")
            return dict(count=len(rows),oldest=datetime.fromtimestamp(stamps[0],now.tzinfo).date().isoformat() if rows else None,
                        newest=datetime.fromtimestamp(stamps[-1],now.tzinfo).date().isoformat() if rows else None,
                        forming_period_separate=payload.get("prefix") is not None)
        output=dict(read_only=True,provider="FYERS",symbol="NSE:NIFTY50-INDEX",
                    worker_source=str(source),results={},orders_submitted=0)
        for interval in ("1W","1M","12M"):
            item={};output["results"][interval]=item
            try:
                current=fetch_fyers_history(bound,interval,now,symbol="NSE:NIFTY50-INDEX")
                item["initial"]=summarize(current)
                if current["rows"]:
                    cursor=current["rows"][0][0]
                    older=fetch_fyers_history(bound,interval,now,symbol="NSE:NIFTY50-INDEX",before=cursor)
                    if any(r[0]>=cursor for r in older["rows"]):raise ValueError("Older history crossed its cursor.")
                    item["older"]=summarize(older)
            except Exception as error:
                item["status"]="UNVERIFIED";item["error_type"]=type(error).__name__
                cause=error
                for _ in range(5):
                    response=getattr(cause,"response",None)
                    if response is not None:
                        item["http_status"]=response.status_code
                        try:item["broker_code"]=response.json().get("code")
                        except (ValueError,AttributeError):pass
                        break
                    cause=getattr(cause,"__cause__",None)
                    if cause is None:break
                break  # Never continue broker reads after an auth/limit/history failure.
        output["native_history_requests"]=requests_count
        print(json.dumps(output,indent=2))
    finally:client._sector_pulse_ipv4_session.close()
if __name__=="__main__":main()
