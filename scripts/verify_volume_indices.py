"""Independent Decimal reference for the staged NVI/PVI and EMA plots."""
from pathlib import Path
from decimal import Decimal,localcontext
import json,subprocess,math
out=Path(".private/chart-order-rollouts/volume-index-studies-20261119")
manifest=json.loads((out/"manifest.json").read_text())
cases=[]
datasets={
 "mixed":[{"close":round(100+math.sin(i*.31)*8+i*.03,2),"volume":[100,80,120,120,0,60,140][i%7]}for i in range(500)],
 "equal_volume":[{"close":100+i,"volume":10}for i in range(50)],
 "zero_volume":[{"close":100+i,"volume":0}for i in range(50)],
 "large_prices":[{"close":round(10000000+math.sin(i)*1000,2),"volume":i%9}for i in range(300)]}
for name,bars in datasets.items():
 for kind in ["NVI","PVI"]:
  for length in [1,14,255]:cases.append(dict(name=name,bars=bars,kind=kind,length=length))
runner="""const fs=require('node:fs');require(process.argv[1]);const cases=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(cases.map(c=>globalThis.SectorPulseChartStudies.indicators[c.kind].run(c.bars,[],c.length))));"""
reports=[]
for entry in manifest["entries"]:
 candidate=Path(entry["candidate"]).resolve()
 subprocess.run(["node","--check",str(candidate)],check=True,capture_output=True)
 actual=json.loads(subprocess.run(["node","-e",runner,str(candidate)],input=json.dumps(cases),text=True,capture_output=True,check=True).stdout)
 numeric=0;maximum=0
 with localcontext()as ctx:
  ctx.prec=50
  for case,plots in zip(cases,actual):
   index=Decimal(1000);average=None;expected=[[],[]];prior=None
   a=Decimal(2)/Decimal(case["length"]+1)
   for bar in case["bars"]:
    close=Decimal(str(bar["close"]));vol=bar["volume"]
    if prior:
     selected=vol>prior["volume"]if case["kind"]=="PVI"else vol<prior["volume"]
     if selected:index=index*(Decimal(1)+(close-Decimal(str(prior["close"])))/Decimal(str(prior["close"])))
    average=index if average is None else a*index+(1-a)*average
    expected[0].append(index);expected[1].append(average);prior=bar
   for got,want in zip(plots,expected):
    assert len(got)==len(want)
    for g,w in zip(got,want):
     assert isinstance(g,(float,int))and math.isfinite(g)
     error=abs(Decimal(str(g))-w);maximum=max(maximum,float(error));numeric+=1
     assert error<Decimal("0.00000001"),(entry["path"],case["kind"],case["name"],g,str(w))
 # Explicitly check no-data and missing-volume handling without claiming external parity.
 edge="""require(process.argv[1]);let i=globalThis.SectorPulseChartStudies.indicators;for(let k of ['NVI','PVI']){for(let b of [[],[{close:100,volume:null}],[{close:0,volume:10}]]){let p=i[k].run(b,[],255);if(p.some(x=>x.some(v=>v!==null)))process.exit(1)}}"""
 subprocess.run(["node","-e",edge,str(candidate)],check=True,capture_output=True)
 reports.append({"source":entry["path"],"cases":len(cases),"numeric_values":numeric,"max_absolute_error":maximum,"pass":True})
report={"status":"PASS","reference":"Independent Decimal50 compounding and EMA; four synthetic datasets; lengths1/14/255","sources":reports,"limitations":["Native TradingView export parity and missing-data behavior remain unverified.","Hosted rendering, plot styles and source-data correctness are separate acceptance checks."]}
(out/"decimal-audit.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report))
