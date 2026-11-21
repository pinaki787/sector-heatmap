"""Independent Decimal50 HA, Open-SMA5 and ATR14 audit of hosted study exports."""
from pathlib import Path
from decimal import Decimal,localcontext
from datetime import datetime
from bisect import bisect_right
import argparse,csv,json,hashlib

def transform(rows):
    result=[]
    for row in rows:
        t,o,h,l,c,v=row[:6];o,h,l,c=map(lambda x:Decimal(str(x)),[o,h,l,c])
        previous=result[-1]if result else None
        opened=(previous[1]+previous[4])/2 if previous else(o+c)/2
        closed=(o+h+l+c)/4
        result.append([t,opened,max(h,opened,closed),min(l,opened,closed),closed,v])
    return result

def plots(rows):
    averages=[];ranges=[];prior=None
    for i,row in enumerate(rows):
        high,low,close=map(lambda x:Decimal(str(x)),[row[2],row[3],row[4]])
        values=[Decimal(str(b[1]))for b in rows[max(0,i-4):i+1]]
        averages.append(sum(values)/5 if len(values)==5 else None)
        tr=max(high-low,abs(high-prior),abs(low-prior))if prior is not None else high-low
        ranges.append(tr)
        prior=close
    # ATR needs a separate output sequence so every source bar retains its state.
    atr=[];running=None
    for i,value in enumerate(ranges):
        if i==13:running=sum(ranges[:14])/14
        elif i>13:running=(running*13+value)/14
        atr.append(running)
    return [averages,atr]

def audit(history_path,export_path,frames_path=None):
    payload=json.loads(history_path.read_text());assert "delta"in payload["provider"].lower()
    source=payload["rows"];assert source and all(a[0]<b[0]for a,b in zip(source,source[1:]))
    exported=list(csv.DictReader(export_path.open()));ends=[b[0]+3600 for b in source]
    keys=["SMA (5) · 1h","ATR (14) · 1h"]
    with localcontext()as ctx:
        ctx.prec=50
        expected=plots(transform(source));native=plots(source);counts=[0,0];different=[0,0];maximum=Decimal(0)
        for row in exported:
            if frames_path and row["provisional"]=="1":continue
            t=int(datetime.fromisoformat(row["source_time_utc"].replace("Z","+00:00")).timestamp())
            end=t if row["provisional"]=="1"else t+1800
            index=bisect_right(ends,end)-1;assert index>=0
            for i,key in enumerate(keys):
                want=expected[i][index];got=Decimal(row[key]);assert want is not None
                error=abs(got-want);maximum=max(maximum,error)
                assert error<Decimal("0.00000001"),(key,row["source_time_utc"],str(error),str(want),str(got))
                counts[i]+=1
                if abs(want-native[i][index])>Decimal("0.00000001"):different[i]+=1
        result=dict(status="PASS",native_reference_bars=len(source),export_rows=len(exported),plots=[dict(plot=key,numeric_values=n,different_from_native_basis=d)for key,n,d in zip(keys,counts,different)],max_absolute_error=str(maximum))
        if frames_path:
            frames=json.loads(frames_path.read_text());last=exported[-1];assert last["provisional"]=="1";matches=[]
            for frame in frames:
                data=frame["data"]
                if not data.get("connected")or len(data.get("rows",[]))!=1:continue
                live=data["rows"][0]
                if live[0]!=source[-1][0]+3600:continue
                values=[p[-1]for p in plots(transform(source+[live]))]
                error=max(abs(Decimal(last[key])-value)for key,value in zip(keys,values))
                if error<Decimal("0.00000001"):matches.append(dict(request_id=frame["request_id"],live_row=live,numeric_values=2,max_absolute_error=str(error)))
            assert matches,"No observed live frame matches both exported HA calculations"
            result["matched_forming_frames"]=matches
        result.update(reference="Independent Decimal50 recursive HA at requested broker1h timeframe, SMA5 of HA Open and Wilder ATR14, aligned by source closes to30m host bars.",limits=["Selected Delta capture only; native TradingView exported indicator parity and full broker/type matrix remain unverified."],input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [history_path,export_path]})
        return result

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history",type=Path,required=True);parser.add_argument("--export",type=Path,required=True)
    parser.add_argument("--frames",type=Path);parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args();result=audit(args.history,args.export,args.frames)
    args.report.write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
