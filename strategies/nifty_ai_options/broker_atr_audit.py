"""Read-only FYERS parent-candle ATR audit; never a native Renko sizing provider.

Run with the strategy venv. Outputs are research evidence only. No runner,
reference cache, applied chart, service or order API is changed.
"""
import argparse, hashlib, json, math, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT))
IST=ZoneInfo("Asia/Kolkata")


def validate(rows, step):
    unique={}
    duplicates=0
    for row in rows:
        if not isinstance(row,(list,tuple)) or len(row)<5:
            raise ValueError("Missing source OHLC")
        t,*prices=row[:5]
        if isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) or int(t)!=t:
            raise ValueError("Invalid source timestamp")
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in prices):
            raise ValueError("Invalid source price")
        o,h,l,c=prices
        if not l<=min(o,c)<=max(o,c)<=h:
            raise ValueError("Invalid source OHLC ordering")
        if t in unique:
            if unique[t][:5]!=list(row[:5]):
                raise ValueError("Conflicting source OHLC timestamp")
            duplicates+=1
        unique[t]=list(row[:5])
    return sorted(unique.values()),duplicates


def aggregate(rows,step,now):
    rows,dupes=validate(rows,step)
    groups={}
    offhours=0
    for r in rows:
        dt=datetime.fromtimestamp(r[0],IST)
        minute=dt.hour*60+dt.minute
        if not 555<=minute<930:
            offhours+=1
            continue
        start=dt.replace(hour=9,minute=15,second=0,microsecond=0).timestamp()
        key=(dt.date().isoformat(),0 if minute<915 else 1)
        groups.setdefault(key,dict(start=int(start)+(0 if key[1]==0 else 21600),rows=[]))["rows"].append(r)
    bars=[]; rejected=[]
    for (session,bucket),g in sorted(groups.items()):
        start=g["start"];end=start+(21600 if bucket==0 else 900)
        if end>now:
            rejected.append(dict(session=session,bucket=bucket,reason="FORMING_PARENT"))
            continue
        expected=list(range(start,end,step*60))
        if [r[0] for r in g["rows"]]!=expected:
            rejected.append(dict(session=session,bucket=bucket,reason="INCOMPLETE_PARENT",
                                 missing=len(set(expected)-set(r[0] for r in g["rows"]))))
            continue
        rr=g["rows"]
        bars.append(dict(session=session,bucket=bucket,time=start,end=end,
                         open=rr[0][1],high=max(r[2] for r in rr),
                         low=min(r[3] for r in rr),close=rr[-1][4]))
    return bars,dict(duplicates=dupes,excluded_offhours_rows=offhours,rejected=rejected)


def atr(bars,length=5):
    previous=None;seed=[];value=None;timeline=[]
    for b in bars:
        tr=b["high"]-b["low"] if previous is None else max(b["high"]-b["low"],abs(b["high"]-previous),abs(b["low"]-previous))
        previous=b["close"]
        if value is None:
            seed.append(tr)
            if len(seed)==length:value=sum(seed)/length
        else:value+=(tr-value)/length
        timeline.append(dict(time=b["time"],true_range=tr,atr=value))
    if value is None:raise ValueError("Insufficient completed parents for ATR")
    return value,timeline


def main():
    from run import client,ok,atomic
    from sector_heatmap.fyers_history import history,account_read
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--account",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--cached-source",help="Explicit dated FYERS 15-minute raw response; never reported as fresh")
    args=p.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    now=datetime.now(IST)
    archive=ROOT/"data/backtesting/nifty50-fyers-2024-10-25_2026-10-24"
    manifest=json.loads((archive/"manifest.json").read_text())
    saved=json.loads((archive/"nifty50_1m.json").read_text())
    if saved["symbol"]!="NSE:NIFTY50-INDEX" or saved["resolution_minutes"]!=1:
        raise ValueError("Archive instrument/timeframe mismatch")
    rows=saved["rows"]
    cut=max(r[0] for r in rows)
    start=datetime.fromtimestamp(cut,IST).date()+timedelta(days=1)
    authentication="NOT_CHECKED_CACHED_EVIDENCE_ONLY"
    if args.cached_source:
        response=json.loads(Path(args.cached_source).read_text())
        step=15
    else:
        api=client(args.account)
        try:
            transport=api._sector_pulse_ipv4_session
            from fyers_apiv3 import fyersModel
            profile_response=transport.get(fyersModel.Config.API+fyersModel.Config.get_profile,
                headers={"Authorization":api.header,"Content-Type":"application/json","version":"3"},
                timeout=(3,10))
            payload=profile_response.json()
            if profile_response.status_code!=200 or payload.get("s")!="ok":
                failure=dict(status="FYERS_AUTHENTICATION_OR_PROFILE_UNAVAILABLE",
                    checked_at=now.isoformat(),http_status=profile_response.status_code,
                    broker_code=payload.get("code"),orders_submitted=0,service_reloads=0)
                atomic(out/"fetch-failure.json",failure)
                print(json.dumps(failure,indent=2))
                return
            profile=ok(payload)
            if not (profile.get("data") or {}).get("fy_id"):
                raise ValueError("FYERS account identity unavailable")
            authentication="PASS"
            response=ok(history(api,dict(symbol=saved["symbol"],resolution="1",date_format=1,
                                         range_from=start.isoformat(),range_to=now.date().isoformat(),cont_flag=0)))
            atomic(out/"fyers-1m-raw.json",response)
            step=1
        finally:
            api._sector_pulse_ipv4_session.close()
    recent=response.get("candles")
    if not isinstance(recent,list) or not recent:raise ValueError("FYERS history unavailable")
    recent=[r for r in recent if r[0]>cut]
    if not recent:raise ValueError("No FYERS evidence after archive end")
    old_bars,old_audit=aggregate(rows,1,now.timestamp())
    new_bars,new_audit=aggregate(recent,step,now.timestamp())
    bars=old_bars+new_bars
    if any(bars[i]["time"]>=bars[i+1]["time"] for i in range(len(bars)-1)):
        raise ValueError("Conflicting or overlapping parent sources")
    audit=dict(archive=old_audit,recent=new_audit)
    cases={}
    for name,parents in (("full_6h_only",[b for b in bars if b["bucket"]==0]),
                         ("session_6h_with_15m_tail",bars)):
        value,timeline=atr(parents)
        last=parents[-1]
        cases[name]=dict(parent_count=len(parents),last_parent=last,atr5=value,
                         thirty_minute_candle_estimate=value/12)
        atomic(out/(name+"-timeline.json"),timeline)
    report=dict(status="BROKER_CANDLE_ATR_RESEARCH_ONLY_NOT_VERIFIED_RENKO_SIZE",
                checked_at=now.isoformat(),broker="FYERS",symbol=saved["symbol"],
                account_sha256=hashlib.sha256(args.account.encode()).hexdigest(),
                authentication=authentication,cached_evidence_only=bool(args.cached_source),atr_period=5,parent_minutes=360,baseline_minutes=30,divisor=12,
                session_anchor="09:15 Asia/Kolkata",first_source=rows[0][0],
                last_source=max(r[0] for r in recent),recent_source_rows=len(recent),recent_step_minutes=step,
                recent_source_sha256=hashlib.sha256(json.dumps(response,sort_keys=True).encode()).hexdigest(),
                archive_sha256=hashlib.sha256((archive/"nifty50_1m.json").read_bytes()).hexdigest(),
                archive_calendar_complete=False,source_revision_parity_verified=False,
                archive_manifest_status=manifest.get("status"),audit=audit,cases=cases,
                native_renko_parity_verified=False,eligible_for_strategy=False,
                production_reference_writes=0,orders_submitted=0,service_reloads=0)
    atomic(out/"report.json",report)
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
