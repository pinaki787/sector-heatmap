"""Independent Decimal50 native-range averages for standard ADR."""
from pathlib import Path
from decimal import Decimal,localcontext
import subprocess,json,math
out=Path(".private/chart-order-rollouts/adr-study-20261119")
m=json.loads((out/"manifest.json").read_text())
sets={
 "mixed":[dict(high=round(100+i*.03+math.sin(i*.2)+i%7*.1,4),low=round(99+i*.03+math.sin(i*.2),4))for i in range(600)],
 "gapped_sessions":[dict(high=10000*(i%2)+5,low=10000*(i%2)+3,close=10000*(i%2)+4)for i in range(100)],
 "flat":[dict(high=100,low=100)for i in range(100)],
 "outlier_then_small_ranges":[dict(high=100000 if i==0 else 1.001,low=1)for i in range(500)]}
cases=[dict(name=name,bars=bars,length=length)for name,bars in sets.items()for length in [1,14,50]]
runner="""const fs=require('node:fs');require(process.argv[1]);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(c=>SectorPulseChartStudies.indicators.ADR.run(c.bars,[],c.length)[0])));"""
reports=[]
for e in m["entries"]:
 p=str(Path(e["candidate"]).resolve())
 subprocess.run(["node","--check",p],check=True,capture_output=True)
 values=json.loads(subprocess.run(["node","-e",runner,p],input=json.dumps(cases),text=True,capture_output=True,check=True).stdout)
 count=0;nulls=0;maximum=0
 with localcontext()as ctx:
  ctx.prec=50
  for c,actual in zip(cases,values):
   bars=c["bars"];n=c["length"];assert len(actual)==len(bars)
   for i,value in enumerate(actual):
    if i<n-1:assert value is None;nulls+=1;continue
    window=bars[i-n+1:i+1]
    expected=(sum(Decimal(str(b["high"]))for b in window)-sum(Decimal(str(b["low"]))for b in window))/Decimal(n)
    assert isinstance(value,(float,int))and math.isfinite(value)
    error=abs(Decimal(str(value))-expected);maximum=max(maximum,float(error));count+=1
    assert error<Decimal("0.00000001"),(c["name"],n,i,value,str(expected))
 reports.append(dict(source=e["path"],cases=len(cases),numeric=count,warmup_nulls=nulls,max_absolute_error=maximum,passed=True))
report=dict(status="PASS",reference="Decimal50 independent average(high)-average(low), including session gaps, zero-range and expiring outlier",sources=reports,limits=["Synthetic calculation audit; native TradingView export, hosted selected-source export and full timeframe matrix remain unverified."])
(out/"decimal-audit.json").write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(report))
