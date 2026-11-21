"""Independent Decimal50 anchored source averages, calendar boundaries and absent anchors."""
from pathlib import Path
from decimal import Decimal,localcontext
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import json,subprocess,math
out=Path(".private/chart-order-rollouts/twap-study-20261119")
m=json.loads((out/"manifest.json").read_text())
cases=[]
start=datetime(2025,11,1,tzinfo=timezone.utc)
for zone in ["UTC","Asia/Kolkata","America/New_York"]:
 bars=[];keys={}
 for i in range(600):
  t=int((start+timedelta(hours=i*4)).timestamp());base=100+i%31
  bars.append(dict(time=t,open=base,high=base+4,low=base-2,close=base+1,volume=None))
  local=datetime.fromtimestamp(t,ZoneInfo(zone)).date()
  keys[str(t)]=(local-datetime(1970,1,1).date()).days
 for anchor in ["1D","1W","1M","3M","12M"]:
  for source in ["close","open","high","low","hl2","hlc3","ohlc4"]:
   cases.append(dict(bars=bars,anchor=anchor,source=source,exchangeDays=keys,zone=zone))
runner="""const fs=require('fs');require(process.argv[1]);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(c=>SectorPulseChartStudies.indicators.TWAP.run(c.bars,[],0,0,{anchor:c.anchor,source:c.source},{exchangeDay:t=>c.exchangeDays[t]})[0])));"""
reports=[]
for entry in [e for e in m["entries"]if e["kind"]=="library"]:
 candidate=str(Path(entry["candidate"]).resolve())
 subprocess.run(["node","--check",candidate],check=True,capture_output=True)
 actual=json.loads(subprocess.run(["node","-e",runner,candidate],input=json.dumps(cases),text=True,capture_output=True,check=True).stdout)
 numeric=0;maximum=0
 with localcontext()as ctx:
  ctx.prec=50
  for case,series in zip(cases,actual):
   previous=None;total=Decimal(0);count=0
   for bar,got in zip(case["bars"],series):
    day=case["exchangeDays"][str(bar["time"])]
    dt=datetime(1970,1,1).date()+timedelta(days=day)
    period=case["anchor"]
    key=(dt.year,dt.month,dt.day)if period=="1D"else(dt.isocalendar().year,dt.isocalendar().week)if period=="1W"else(dt.year,dt.month)if period=="1M"else(dt.year,(dt.month-1)//3)if period=="3M"else dt.year
    if key!=previous:total=Decimal(0);count=0;previous=key
    fields={k:Decimal(str(bar[k]))for k in ["open","high","low","close"]}
    src=case["source"];value=fields[src]if src in fields else (fields["high"]+fields["low"])/2 if src=="hl2"else(fields["high"]+fields["low"]+fields["close"])/3 if src=="hlc3"else sum(fields.values())/4
    total+=value;count+=1;want=total/Decimal(count);error=abs(Decimal(str(got))-want)
    maximum=max(maximum,float(error));numeric+=1
    assert error<Decimal("0.000000001"),(case["zone"],period,src,got,str(want))
 # Explicit external anchor keys must govern resets; no volume is required.
 edge="""require(process.argv[1]);const i=SectorPulseChartStudies.indicators.TWAP;const bars=[1,2,3,4].map((n)=>({time:n,sourceTime:n+100,open:n,high:n,low:n,close:n}));const p=i.run(bars,[],0,0,{anchor:'840'},{twapAnchorKey:b=>b.sourceTime<103?'a':'b'})[0];if(JSON.stringify(p)!=='[1,1.5,3,3.5]')throw Error(JSON.stringify(p));if(i.run(bars,[],0,0,{anchor:'840'},{}).some(s=>s.some(x=>x!==null)))throw Error('Fabricated anchor');"""
 subprocess.run(["node","-e",edge,candidate],check=True,capture_output=True)
 reports.append(dict(source=entry["path"],cases=len(cases),numeric_values=numeric,max_absolute_error=maximum,passed=True))
report=dict(status="PASS",reference="Decimal50 independently grouped UTC/IST/NewYork with DST, day/week/month/quarter/year and7OHLCsources; custom callback reset and unavailable anchor checks",sources=reports,limits=["Native custom-hour boundary callback and hosted controls require separate verification.","No native TradingView export parity claim."])
(out/"decimal-audit.json").write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(report))
