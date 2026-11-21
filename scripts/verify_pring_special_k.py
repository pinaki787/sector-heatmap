"""Independent Decimal audit of Pring Special K's documented12 cycles."""
from pathlib import Path
from decimal import Decimal,localcontext
from collections import deque
import json,math,subprocess
out=Path(".private/chart-order-rollouts/pring-special-k-20261119")
manifest=json.loads((out/"manifest.json").read_text())
cycles=[(10,10,1),(15,10,2),(20,10,3),(30,15,4),(40,50,1),(65,65,2),(75,75,3),(100,100,4),(195,130,1),(265,130,2),(390,130,3),(530,195,4)]
def mean_finite(values,n):
    window=deque();total=Decimal(0);result=[]
    for value in values:
        if value is None:result.append(None);continue
        window.append(value);total+=value
        if len(window)>n:total-=window.popleft()
        result.append(total/n if len(window)==n else None)
    return result
def price(bar,source):
    selected={"close":["close"],"open":["open"],"high":["high"],"low":["low"],"hl2":["high","low"],"hlc3":["high","low","close"],"ohlc4":["open","high","low","close"]}.get(source,["close"])
    values=[bar[k]for k in selected]
    return None if any(v is None for v in values)else sum(Decimal(str(v))for v in values)/len(values)
def reference(case):
    prices=[price(b,case["inputs"]["source"])for b in case["bars"]];averages=[]
    for roc,smooth,weight in cycles:
        rates=[100*(p-prices[i-roc])/prices[i-roc]if i>=roc and p is not None and prices[i-roc] not in (None,0)else None for i,p in enumerate(prices)]
        averages.append((mean_finite(rates,smooth),weight))
    special=[sum(series[i]*weight for series,weight in averages)if all(series[i]is not None for series,weight in averages)else None for i in range(len(prices))]
    signal=mean_finite(mean_finite(special,case["inputs"]["signalLength1"]),case["inputs"]["signalLength2"])
    return special,signal
datasets={}
for name in ["trend","oscillation"]:
    bars=[]
    for i in range(1200):
        base=100+i*.03 if name=="trend"else 100+15*math.sin(i*.047)+3*math.cos(i*.13)
        o=round(base+.3*math.sin(i),4);c=round(base+.4*math.cos(i),4)
        bars.append(dict(time=1700000000+i*60,open=o,high=max(o,c)+1.2,low=min(o,c)-.8,close=c,volume=100+i%7))
    datasets[name]=bars
cases=[]
for name,bars in datasets.items():
    for source in ["close","open","high","low","hl2","hlc3","ohlc4"]:
        for a,b in [(100,100),(1,14),(2000,2000)]:
            cases.append(dict(name=name,bars=bars,inputs=dict(source=source,signalLength1=a,signalLength2=b)))
for count in [724,725,922,923]:
    cases.append(dict(name="flat-boundary",bars=[dict(open=100,high=100,low=100,close=100)for _ in range(count)],inputs=dict(source="close",signalLength1=100,signalLength2=100)))
runner="""const fs=require('node:fs');require(process.argv[1]);const i=globalThis.SectorPulseChartStudies.indicators.SpecialK;let c=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(c.map(x=>i.run(x.bars,[],undefined,undefined,x.inputs))));"""
with localcontext()as context:
    context.prec=50
    expected=[reference(c)for c in cases]
    reports=[]
    for e in manifest["entries"]:
        if e["kind"]!="library":continue
        actual=json.loads(subprocess.run(["node","-e",runner,str(Path(e["candidate"]).resolve())],input=json.dumps(cases),capture_output=True,text=True,check=True).stdout)
        numeric=0;nulls=0;maximum=Decimal(0)
        for case,wants,plots in zip(cases,expected,actual):
            for want,got in zip(wants,plots):
                assert len(want)==len(got)
                for i,(w,g)in enumerate(zip(want,got)):
                    if w is None:assert g is None,(case["name"],i,g);nulls+=1
                    else:
                        assert isinstance(g,(int,float))and math.isfinite(g)
                        error=abs(Decimal(str(g))-w);maximum=max(maximum,error);numeric+=1
                        assert error<Decimal("0.00000001"),(case["name"],case["inputs"],i,str(w),g)
        reports.append(dict(source=e["path"],cases=len(cases),numeric_values=numeric,warmup_nulls=nulls,max_absolute_error=str(maximum),passed=True))
result=dict(status="PASS",reference="Independent Decimal50 twelve fixed weighted ROC/SMA cycles and double finite-observation SMA; all7OHLCsources, three signal-length pairs,724/725/922/923 boundaries.",sources=reports,limits=["Native TradingView export and hosted rendering remain separate checks."])
(out/"decimal-audit.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
