"""Audit captured native TradingView Renko CSVs against the current-library diagnostic.
Read-only offline evidence. Does not establish all-method or indicator alignment parity.
"""
import argparse,csv,json,hashlib
from pathlib import Path
from decimal import Decimal,getcontext
getcontext().prec=50

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diagnostic",type=Path,required=True)
    p.add_argument("--lower",type=Path,required=True)
    p.add_argument("--higher",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    case=json.loads(args.diagnostic.read_text())
    assert case["method"]=="Traditional" and case["size"]==10 and case["source"]=="close"
    start,end=1793304000,1795096800
    results=[]
    for stream,path in zip(case["streams"],[args.lower,args.higher]):
        rows=list(csv.DictReader(path.open()))
        native=[r for r in rows if start<=Decimal(r["time"])<end]
        expected=stream["bricks"]
        assert len(native)==len(expected),(path,len(native),len(expected))
        errors=[];clock_matches=0;synthetic_clock_matches=0;duplicates={}
        for i,(want,got) in enumerate(zip(expected,native)):
            for key in ["open","high","low","close"]:
                error=abs(Decimal(got[key])-Decimal(str(want[key])))
                assert error<Decimal("0.00000001"),(path,i,key,str(error))
                errors.append(error)
            source_open=int(Decimal(got["time"])//(stream["minutes"]*60))*(stream["minutes"]*60)
            assert source_open==want["sourceTime"],(path,i,source_open,want["sourceTime"])
            clock_matches+=1
            count=duplicates.get(source_open,0);duplicates[source_open]=count+1
            candidate_time=Decimal(source_open)+Decimal(count)/1000
            assert Decimal(got["time"])==candidate_time,(path,i,str(candidate_time),got["time"])
            synthetic_clock_matches+=1
        results.append(dict(name=stream["name"],native_export_rows=len(rows),matched_bricks=len(native),
            ohlc_comparisons=len(errors),source_candle_open_matches=clock_matches,synthetic_clock_matches=synthetic_clock_matches,max_absolute_error=str(max(errors,default=Decimal(0))),
            native_ma_present=sum(bool(r["MA"]) for r in native),native_ma_gaps=sum(not r["MA"] for r in native)))
    higher=list(csv.DictReader(args.higher.open()))
    sma_errors=[]
    for i in range(4,len(higher)):
        want=sum(Decimal(r["close"])for r in higher[i-4:i+1])/5
        assert higher[i]["MA"],i
        error=abs(Decimal(higher[i]["MA"])-want)
        assert error<Decimal("0.00000001"),(i,str(error))
        sma_errors.append(error)
    lower=list(csv.DictReader(args.lower.open()))
    merge_checks=[];fixed_duration_mismatches=0
    for i,row in enumerate(lower[:-2]):
        opened,closed=Decimal(row["time"]),Decimal(lower[i+1]["time"])
        if opened<Decimal(higher[0]["time"]) or closed>Decimal(higher[-2]["time"]):continue
        events=[r["MA"]for j,r in enumerate(higher[:-2])if opened<Decimal(higher[j+1]["time"])<=closed]
        expected=events[-1]if events else ""
        assert expected==row["MA"],(i,row["time"],expected,row["MA"])
        merge_checks.append(dict(index=i,time=row["time"],value=expected or None))
        duration_events=[r["MA"]for r in higher[:-2]if opened<Decimal(r["time"])+3600<=closed]
        duration_expected=duration_events[-1]if duration_events else ""
        fixed_duration_mismatches+=duration_expected!=row["MA"]
    assert merge_checks
    merge_audit=dict(status="PASS_CAPTURED_HISTORICAL_ROWS",checks=len(merge_checks),
        values=sum(r["value"] is not None for r in merge_checks),fixed_duration_merge_mismatches=fixed_duration_mismatches,
        gaps=sum(r["value"] is None for r in merge_checks),
        rule="Each source brick closes at next source synthetic timestamp. Emit last source value with close in (host open, next host synthetic timestamp]; no event means gap.",
        excluded_tail="Last two host and last two source rows excluded: captured live/projection finality is not established.",
        limits="Historical export replay only. Finality, live projections, dynamic ATR/percentage construction and generalized source-seed behavior remain unproven.")
    result=dict(status="PASS_SELECTED_NATIVE_BRICKS_AND_HOURLY_SMA",window=dict(start=start,end=end),
        construction=dict(method="Traditional",size=10,source="Close",wicks=False),
        streams=results,historical_merge=merge_audit,hourly_chart_sma5=dict(comparisons=len(sma_errors),max_absolute_error=str(max(sma_errors))),
        last_native_values=dict(lower_hourly_sma=lower[-1]["MA"],higher_chart_sma=higher[-1]["MA"],lower_time=lower[-1]["time"],higher_time=higher[-1]["time"]),
        input_sha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest()for f in [args.diagnostic,args.lower,args.higher]},
        limits=["Selected Delta ETHUSD native exports and captured broker source window only; no all-broker, ATR, percentage or OHLC-source parity claim.",
        "Common candidate seed selected before window; starting-state and arbitrary history-window behavior remain unverified.",
        "Selected fractional synthetic timestamps exactly match source-open plus one millisecond per additional same-candle brick. General live/projection clocks remain unverified.",
        "Hourly SMA arithmetic and historical next-brick-close merge are verified on captured exports. Lower-chart live/projection alignment remains unverified; final-value difference is preserved.",
        "No production calculation controls enabled and no trading actions."])
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":main()
