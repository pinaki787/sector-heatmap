"""Independent Decimal checks of six pivot methods and 52-week source selection."""
import argparse,csv,json,subprocess,tempfile,hashlib
from decimal import Decimal,localcontext
from pathlib import Path

def pivot(method,b,opening):
 o,h,l,c=[Decimal(str(b[k])) for k in ("open","high","low","close")];r=h-l;p=(h+l+c)/3
 out={}
 if method=="DM":
  x=h+2*l+c if c<o else 2*h+l+c if c>o else h+l+2*c
  return {"P":x/4,"R1":x/2-l,"S1":x/2-h}
 if method=="Woodie":p=(h+l+2*Decimal(str(opening)))/4
 out["P"]=p
 if method in ("Traditional","Classic","Woodie"):
  out.update(R1=2*p-l,S1=2*p-h,R2=p+r,S2=p-r)
 if method=="Traditional":
  for n in (3,4,5):out[f"R{n}"]=h+(n-1)*(p-l);out[f"S{n}"]=l-(n-1)*(h-p)
 elif method=="Classic":
  for n in (3,4):out[f"R{n}"]=p+(n-1)*r;out[f"S{n}"]=p-(n-1)*r
 elif method=="Woodie":
  out.update(R3=h+2*(p-l),S3=l-2*(h-p));out.update(R4=out["R3"]+r,S4=out["S3"]-r)
 elif method=="Fibonacci":
  for n,k in enumerate((Decimal(".382"),Decimal(".618"),Decimal(1)),1):out[f"R{n}"]=p+k*r;out[f"S{n}"]=p-k*r
 elif method=="Camarilla":
  for n,divisor in enumerate((12,6,4,2),1):out[f"R{n}"]=c+r*Decimal("1.1")/divisor;out[f"S{n}"]=c-r*Decimal("1.1")/divisor
  if l:out.update(R5=h*c/l,S5=2*c-h*c/l)
 return out

def source(b,key):
 v={k:Decimal(str(b[k])) for k in ("open","high","low","close")}
 return (v["high"]+v["low"])/2 if key=="hl2" else (v["high"]+v["low"]+v["close"])/3 if key=="hlc3" else sum(v.values())/4 if key=="ohlc4" else v[key]

def main():
 p=argparse.ArgumentParser();p.add_argument("csv");p.add_argument("--output",required=True);a=p.parse_args()
 bars=[{k:float(r[k]) for k in ("open","high","low","close","volume")} for r in csv.DictReader(open(a.csv))]
 methods=["Traditional","Fibonacci","Woodie","Classic","DM","Camarilla"];sources=["close","open","high","low","hl2","hlc3","ohlc4"]
 cases=[dict(previous=b,opening=bars[i+1]["open"],method=m) for i,b in enumerate(bars[:-1]) for m in methods]
 for opening,close in [(100,99),(100,100),(100,101)]:cases.append(dict(previous=dict(open=opening,high=105,low=95,close=close),opening=102,method="DM"))
 root=Path(__file__).resolve().parents[1]
 js="""const fs=require("node:fs");require(process.argv[1]);const lib=globalThis.SectorPulseChartStudies,d=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));process.stdout.write(JSON.stringify({pivots:d.cases.map(x=>lib.standardPivotLevels(x.method,x.previous,x.opening)),weekly:d.sources.flatMap(highSource=>d.sources.map(lowSource=>({highSource,lowSource,values:lib.indicators.FiftyTwoWeekHighLow.weeklyLevels(d.bars,{highSource,lowSource})}))),warmup:lib.indicators.FiftyTwoWeekHighLow.weeklyLevels(d.bars.slice(0,51))}));"""
 with tempfile.TemporaryDirectory(prefix="chart-reference-levels-") as folder:
  path=Path(folder)/"input.json";path.write_text(json.dumps(dict(bars=bars,cases=cases,sources=sources)))
  result=json.loads(subprocess.run(["node","-e",js,str(root/"chart-workspace-studies.js"),str(path)],capture_output=True,text=True,check=True).stdout)
 errors=[];checks=0
 with localcontext() as ctx:
  ctx.prec=50
  for case,actual in zip(cases,result["pivots"]):
   expected=pivot(case["method"],case["previous"],case["opening"]);assert set(actual)==set(expected)
   for key,value in expected.items():errors.append(abs(float(value)-actual[key]));checks+=1
  for case in result["weekly"]:
   expected=[max(source(b,case["highSource"]) for b in bars[-52:]),min(source(b,case["lowSource"]) for b in bars[-52:])]
   for e,v in zip(expected,case["values"]):errors.append(abs(float(e)-v));checks+=1
 assert result["warmup"]==[None,None];assert max(errors)<1e-8,max(errors)
 output=dict(status="PASS",scope="Independent arithmetic checks on captured Delta weekly OHLC; not hosted rendering or external TradingView comparison",source_sha256=hashlib.sha256(Path(a.csv).read_bytes()).hexdigest(),source_bars=len(bars),pivot_methods=methods,pivot_cases=len(cases),weekly_source_combinations=len(result["weekly"]),numeric_values_checked=checks,max_absolute_error=max(errors),warmup_51_weeks="NULL_LEVELS")
 Path(a.output).write_text(json.dumps(output,indent=2)+"\n");print(json.dumps(output,indent=2))
if __name__=="__main__":main()
