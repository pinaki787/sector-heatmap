"""Read-only Renko timeframe diagnostic from previously captured Delta OHLC.
No broker calls, live state, runner changes, or orders. This is a comparison
candidate, not evidence of native TradingView equivalence.
"""
from pathlib import Path
from datetime import datetime,timezone
import csv,json,subprocess,hashlib,argparse,math

def read_lower(path):
    rows=[]
    for row in csv.DictReader(path.open()):
        if row["provisional"]!="0":continue
        t=int(datetime.fromisoformat(row["source_time_utc"].replace("Z","+00:00")).timestamp())
        rows.append(dict(time=t,**{k:float(row[k])for k in ["open","high","low","close","volume"]}))
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lower",type=Path,required=True);parser.add_argument("--higher",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();lower=read_lower(args.lower)
    higher=json.loads(args.higher.read_text());assert "delta"in higher["provider"].lower()
    hours=[dict(zip(["time","open","high","low","close","volume"],b[:6]))for b in higher["rows"]]
    assert lower and hours
    for data in [lower,hours]:
        assert all(a["time"]<b["time"]for a,b in zip(data,data[1:]))
        assert all(all(math.isfinite(b[k])for k in ["time","open","high","low","close"])for b in data)
    start=math.ceil(lower[0]["time"]/3600)*3600
    end=math.floor(min(lower[-1]["time"]+1800,hours[-1]["time"]+3600)/3600)*3600
    selected_lower=[b for b in lower if start<=b["time"]<end]
    selected_upper=[b for b in hours if start<=b["time"]<end]
    prefix=[b for b in hours if b["time"]<start]
    assert len(selected_lower)==len(selected_upper)*2
    assert all(b["time"]==start+i*1800 for i,b in enumerate(selected_lower))
    assert all(b["time"]==start+i*3600 for i,b in enumerate(selected_upper))
    payload=dict(lower=selected_lower,higher=selected_upper,prefix=prefix)
    runner=r"""
const fs=require('node:fs');require('./chart-workspace-studies.js');
const {renko,indicators}=globalThis.SectorPulseChartStudies;
const data=JSON.parse(fs.readFileSync(0,'utf8')),results=[];
for(const size of [5,10])for(const source of ['close','ohlc']){
 const previous=renko(data.prefix,size,undefined,source).at(-1);
 if(!previous)throw Error('No preceding confirmed brick');
 const streams=[];
 for(const [name,minutes,bars]of [['30m',30,data.lower],['1h',60,data.higher]]){
  const bricks=renko(bars,size,previous,source,false);
  const values=indicators.SMA.run(bricks,bricks.map(b=>b.close),5,undefined,{})[0];
  const sourceTimes=new Set(bars.map(b=>b.time)),counts=new Map();
  bricks.forEach((b,i)=>{
   if(b.time!==i+1||!sourceTimes.has(b.sourceTime)||b.provisional||Math.abs(Math.abs(b.close-b.open)-size)>1e-8)throw Error('Invalid diagnostic brick');
   counts.set(b.sourceTime,(counts.get(b.sourceTime)||0)+1);
  });
  streams.push({name,minutes,bricks:bricks.map((b,i)=>({...b,sourceEnd:b.sourceTime+minutes*60,sma5:values[i]})),
   summary:{sourceCandles:bars.length,brickCount:bricks.length,multiBrickCandles:[...counts.values()].filter(n=>n>1).length,maxBricksPerCandle:Math.max(0,...counts.values()),lastClose:bricks.at(-1)?.close,lastSma5:values.at(-1)}});
 }
 const snapshots=[];let li=-1,hi=-1;
 for(const hour of data.higher){
  const ended=hour.time+3600;
  while(li+1<streams[0].bricks.length&&streams[0].bricks[li+1].sourceEnd<=ended)li++;
  while(hi+1<streams[1].bricks.length&&streams[1].bricks[hi+1].sourceEnd<=ended)hi++;
  const lower=streams[0].bricks[li]?.sma5,higher=streams[1].bricks[hi]?.sma5;
  if(Number.isFinite(lower)&&Number.isFinite(higher))snapshots.push({sourceEnd:ended,lowerSma5:lower,higherSma5:higher,absoluteDifference:Math.abs(lower-higher)});
 }
 const differences=snapshots.map(s=>s.absoluteDifference);
 const availabilityComparison={alignment:'Candidate source-candle availability bounds; not native brick closing times',snapshots:snapshots.length,differingSnapshots:differences.filter(v=>v>1e-8).length,maxAbsoluteDifference:Math.max(0,...differences),meanAbsoluteDifference:differences.length?differences.reduce((a,b)=>a+b,0)/differences.length:null};
 results.push({method:'Traditional',size,source,commonSeed:{open:previous.open,close:previous.close,sourceTime:previous.sourceTime},streams,availabilityComparison,snapshots});
}
console.log(JSON.stringify(results));
"""
    computed=json.loads(subprocess.run(["node","-e",runner],input=json.dumps(payload),capture_output=True,text=True,check=True).stdout)
    args.output.mkdir(parents=True,exist_ok=True);summaries=[]
    for case in computed:
        name=str(case["size"])+"-"+case["source"]
        (args.output/(name+".json")).write_text(json.dumps(case,indent=2)+"\n")
        summaries.append({k:case[k]for k in ["method","size","source","commonSeed","availabilityComparison"]}|dict(streams=[s["summary"]|{"name":s["name"]}for s in case["streams"]]))
    report=dict(status="DIAGNOSTIC_READY_NOT_NATIVE_PARITY",common_window=dict(start=start,end=end,lower_bars=len(selected_lower),higher_bars=len(selected_upper)),
        scenarios=summaries,input_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [args.lower,args.higher]},
        findings=["The chart-library time field is a synthetic brick ordinal; sourceTime is the actual market-candle opening timestamp.",
        "Multiple bricks share a source candle. A join on sourceTime alone discards intermediate indicator states.",
        "The same Traditional size and preceding confirmed seed produce different brick histories when source resolution changes."],
        limits=["No native TradingView Renko export/settings comparison yet.","The common seed comes from the current application's higher-timeframe candidate history; it is not a native TradingView seed.",
        "OHLC reconstruction uses an assumed intrabar path, not tick-exact reconstruction. No Renko timeframe control was enabled."])
    (args.output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":main()
