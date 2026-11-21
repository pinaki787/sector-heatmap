"""Audit NVI/PVI higher-timeframe chart exports against captured broker OHLCV.
Read-only inputs; writes only the requested report. No broker calls or orders.
"""
from pathlib import Path
from decimal import Decimal, localcontext
from datetime import datetime
from bisect import bisect_right
import argparse,csv,json,hashlib

def audit(history_path,export_path):
    history=json.loads(history_path.read_text())
    bars=history["rows"]
    assert "delta" in history["provider"].lower()
    assert bars and all(len(b)>=6 for b in bars)
    assert all(a[0]<b[0] for a,b in zip(bars,bars[1:]))
    rows=list(csv.DictReader(export_path.open()))
    ends=[b[0]+3600 for b in bars]
    cases=[]
    with localcontext() as context:
        context.prec=50
        alpha=Decimal(2)/256
        for kind,positive in [("NVI",False),("PVI",True)]:
            value=Decimal(1000);ema=None;previous=None;plots=[]
            for b in bars:
                close=Decimal(str(b[4]));volume=Decimal(str(b[5]))
                assert close>0 and volume>=0
                if previous and (volume>previous[1] if positive else volume<previous[1]):
                    value*=close/previous[0]
                ema=value if ema is None else alpha*value+(1-alpha)*ema
                plots.append((value,ema));previous=(close,volume)
            maximum=Decimal(0);count=0
            for row in rows:
                time=int(datetime.fromisoformat(row["source_time_utc"].replace("Z","+00:00")).timestamp())
                end=time if row["provisional"]=="1" else time+1800
                i=bisect_right(ends,end)-1
                assert i>=0,"Export precedes captured reference history"
                for name,want in zip([f"{kind} (255) · 1h",f"{kind} EMA (255) · 1h"],plots[i]):
                    error=abs(Decimal(row[name])-want)
                    assert error<Decimal("0.00000001"),(name,row["source_time_utc"],str(error))
                    maximum=max(maximum,error);count+=1
            cases.append(dict(kind=kind,numeric_values=count,max_absolute_error=str(maximum)))
    return dict(status="PASS",reference_bars=len(bars),export_rows=len(rows),cases=cases,
        input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [history_path,export_path]},
        reference="Decimal50 compounding/EMA from captured selected-broker hourly OHLCV, aligned by completed hour to30m host closes.",
        limits=["Closed-hour calculation only. Selected Delta sample, not native TradingView or all broker/chart-type parity."])

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history",type=Path,required=True)
    parser.add_argument("--export",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.history,args.export)
    args.report.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
