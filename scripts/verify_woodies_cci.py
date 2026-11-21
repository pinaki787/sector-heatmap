"""Independent Decimal50 CCI values and documented Woodies histogram regimes."""
from pathlib import Path
from decimal import Decimal,localcontext
import json,math,subprocess
out=Path(".private/chart-order-rollouts/woodies-cci-20261119")
manifest=json.loads((out/"manifest.json").read_text())
def prices(bars):
 return [None if any(b[k]is None for k in ["high","low","close"])else sum(Decimal(str(b[k]))for k in ["high","low","close"])/3 for b in bars]
def cci(data,n):
 result=[]
 for i,value in enumerate(data):
  window=data[max(0,i-n+1):i+1]
  if len(window)<n or any(v is None for v in window):result.append(None);continue
  offsets=[v-window[0]for v in window];mean=sum(offsets)/n
  deviation=sum(abs(v-mean)for v in offsets)/n
  result.append((offsets[-1]-mean)/(Decimal("0.015")*deviation)if deviation else Decimal(0))
 return result
def colors(values,inputs):
 side=0;count=0;result=[]
 for value in values:
  direction=0 if value is None or value==0 else 1 if value>0 else -1
  count=count+1 if direction and direction==side else 1 if direction else 0;side=direction
  key=("upColor"if direction>0 else"downColor")if count>=6 else"warningColor"if count==5 else"neutralColor"
  result.append(inputs.get(key,{"upColor":"#089981","downColor":"#f23645","warningColor":"#fdd835","neutralColor":"#787b86"}[key]))
 return result
bars=[]
for i in range(600):
 base=100+8*math.sin(i*.113)+2*math.cos(i*.31)+i*.01
 close=round(base,4);bars.append(dict(high=round(base+1.2,4),low=round(base-.8,4),close=close))
datasets={"oscillation":bars,"flat":[dict(high=100,low=100,close=100)for _ in range(100)],"gaps":[dict(b)for b in bars]}
for i in [100,201,299]:datasets["gaps"][i]["high"]=None
cases=[]
for name,data in datasets.items():
 for slow,fast in [(14,6),(20,10),(1,1),(100,40),(2000,2000)]:
  cases.append(dict(name=name,bars=data,inputs=dict(cciPeriod=slow,turboPeriod=fast)))
cases.append(dict(name="custom_palette",bars=bars,inputs=dict(cciPeriod=14,turboPeriod=6,upColor="#112233",downColor="#445566",neutralColor="#778899",warningColor="#aabbcc")))
runner="""const fs=require('node:fs');require(process.argv[1]);const i=globalThis.SectorPulseChartStudies.indicators.WoodiesCCI;let cases=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(cases.map(c=>{let plots=i.run(c.bars,[],undefined,undefined,c.inputs);return {plots,colors:plots[0].colors};})));"""
with localcontext()as context:
 context.prec=50;expected=[]
 for case in cases:
  data=prices(case["bars"]);slow=cci(data,case["inputs"]["cciPeriod"]);fast=cci(data,case["inputs"]["turboPeriod"])
  expected.append(dict(plots=[slow,slow,fast],colors=colors(slow,case["inputs"])))
 reports=[]
 for e in manifest["entries"]:
  if e["kind"]!="library":continue
  actual=json.loads(subprocess.run(["node","-e",runner,str(Path(e["candidate"]).resolve())],input=json.dumps(cases),capture_output=True,text=True,check=True).stdout)
  maximum=Decimal(0);numeric=0;nulls=0;color_count=0
  for case,want,got in zip(cases,expected,actual):
   assert got["colors"]==want["colors"],(case["name"],case["inputs"])
   color_count+=len(got["colors"])
   for ws,gs in zip(want["plots"],got["plots"]):
    assert len(ws)==len(gs)
    for i,(w,g)in enumerate(zip(ws,gs)):
     if w is None:assert g is None,(case["name"],i,g);nulls+=1
     else:
      assert isinstance(g,(int,float))and math.isfinite(g)
      error=abs(Decimal(str(g))-w);maximum=max(maximum,error);numeric+=1
      assert error<Decimal("0.00000001"),(case["name"],case["inputs"],i,str(error),str(w),g)
  reports.append(dict(source=e["path"],cases=len(cases),numeric_values=numeric,warmup_and_missing_nulls=nulls,color_values=color_count,max_absolute_error=str(maximum),passed=True))
result=dict(status="PASS",reference="Independent Decimal50 HLC3 centered mean absolute deviation;14/6,20/10,1/1,100/40,2000/2000 periods; oscillation, flat/gaps and custom palette; color-state counter verified independently.",sources=reports,limits=["Native TradingView export/hex-color parity and hosted rendering remain separate checks."])
(out/"decimal-audit.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
