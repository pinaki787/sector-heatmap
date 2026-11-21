"""Independent two-symbol arithmetic and missing-reference checks."""
import csv,json,subprocess,tempfile,argparse,hashlib
from decimal import Decimal,localcontext
from datetime import datetime
from pathlib import Path

def price(row,field):
 v={k:Decimal(str(row[k])) for k in ("open","high","low","close")}
 return (v["high"]+v["low"])/2 if field=="hl2" else (v["high"]+v["low"]+v["close"])/3 if field=="hlc3" else sum(v.values())/4 if field=="ohlc4" else v[field]

def main():
 p=argparse.ArgumentParser();p.add_argument("primary");p.add_argument("reference");p.add_argument("--output",required=True);args=p.parse_args()
 primary=[dict(time=int(datetime.fromisoformat(r["source_time_utc"].replace("Z","+00:00")).timestamp()),**{k:float(r[k]) for k in ("open","high","low","close","volume")}) for r in csv.DictReader(open(args.primary))]
 reference=[dict(zip(("time","open","high","low","close","volume"),r)) for r in json.load(open(args.reference))];lookup={r["time"]:r for r in reference}
 sources=["close","open","high","low","hl2","hlc3","ohlc4"];root=Path(__file__).resolve().parents[1]
 js="""const fs=require("node:fs");require(process.argv[1]);const d=JSON.parse(fs.readFileSync(process.argv[2],"utf8")),i=globalThis.SectorPulseChartStudies.indicators;const result={};for(const source of d.sources){result[source]={};for(const kind of ["Spread","Ratio","CorrelationCoefficient"])result[source][kind]=i[kind].pairedPlots(d.primary,d.reference,20,{source})[0];}process.stdout.write(JSON.stringify(result));"""
 with tempfile.TemporaryDirectory(prefix="chart-comparison-") as folder:
  f=Path(folder)/"inputs.json";f.write_text(json.dumps(dict(primary=primary,reference=reference,sources=sources)))
  actual=json.loads(subprocess.run(["node","-e",js,str(root/"chart-workspace-studies.js"),str(f)],check=True,capture_output=True,text=True).stdout)
 errors={k:[] for k in ("Spread","Ratio","CorrelationCoefficient")};null_checks=0
 with localcontext() as ctx:
  ctx.prec=50
  for field in sources:
   x=[price(r,field) for r in primary];y=[price(lookup[r["time"]],field) if r["time"] in lookup else None for r in primary]
   expected={"Spread":[None if b is None else a-b for a,b in zip(x,y)],"Ratio":[None if b is None or b==0 else a/b for a,b in zip(x,y)],"CorrelationCoefficient":[]}
   for index in range(len(x)):
    xx=x[max(0,index-19):index+1];yy=y[max(0,index-19):index+1]
    if len(xx)<20 or any(v is None for v in yy):value=None
    else:
     mx=sum(xx)/20;my=sum(yy)/20;cov=sum((a-mx)*(b-my) for a,b in zip(xx,yy));vx=sum((a-mx)**2 for a in xx);vy=sum((b-my)**2 for b in yy);value=cov/(vx*vy).sqrt() if vx and vy else None
    expected["CorrelationCoefficient"].append(value)
   for kind,values in expected.items():
    assert len(actual[field][kind])==len(values)
    for e,a in zip(values,actual[field][kind]):
     if e is None:assert a is None,(kind,field,a);null_checks+=1
     else:assert a is not None,(kind,field);errors[kind].append(abs(float(e)-a))
 maximum={k:max(v) for k,v in errors.items()};assert all(v<1e-8 for v in maximum.values()),maximum
 result=dict(status="PASS",scope="Independent arithmetic on captured Delta BTCUSD/ETHUSD completed weekly bars; not external TradingView parity",primary_rows=len(primary),reference_rows=len(reference),matched_timestamps=sum(r["time"] in lookup for r in primary),price_sources=sources,correlation_length=20,numeric_checks={k:len(v) for k,v in errors.items()},missing_or_warmup_checks=null_checks,max_absolute_error=maximum,primary_sha256=hashlib.sha256(Path(args.primary).read_bytes()).hexdigest(),reference_sha256=hashlib.sha256(Path(args.reference).read_bytes()).hexdigest())
 Path(args.output).write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
