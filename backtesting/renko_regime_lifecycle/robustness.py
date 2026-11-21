"""Frozen candidate checks: daily trade-limit and completed-OHLC recovery-lock sensitivity."""
import json,csv,os,time
from pathlib import Path
from datetime import datetime
from review import OUT,ROOT,ARCHIVE,IST,simulate,stats
base=json.loads((OUT/'specification.json').read_text());config=base['base_config']
raw=[]
with (ARCHIVE/'nifty50_5m.csv').open() as f:
 for x in csv.DictReader(f):
  t=datetime.fromtimestamp(int(x['epoch']),IST)
  if t.weekday()>4 or not 555<=t.hour*60+t.minute<930:continue
  raw.append(dict(timestamp=int(x['epoch']),**{k:float(x[k]) for k in ('open','high','low','close','volume')}))
results={}
for cap in (2,10000):
 for recovery in (False,True):
  for brick in base['brick_sizes']:
   for rule in ('Baseline','Efficiency_ATR'):
    name=f'{brick}_{rule}_cap{cap}_lock{recovery}'
    (OUT/'job.json').write_text(json.dumps(dict(status='RUNNING',phase='ROBUSTNESS',scenario=name,pid=os.getpid(),completed=len(results),total=24,heartbeat=time.time())))
    replay=simulate(raw,dict(config,manual_brick=brick),rule,cap=cap,recovery=recovery)
    result={}
    for label,predicate in [('earlier',lambda t:t['entry_day']<'2025-10-25'),('latest',lambda t:t['entry_day']>='2025-10-25')]:
     trades=[t for t in replay['trades'] if predicate(t)]
     result[label]={str(d):stats(trades,d) for d in (0,2,4)}
    results[name]=result
    (OUT/'robustness.json').write_text(json.dumps(dict(completed=False,results=results),indent=2))
(OUT/'robustness.json').write_text(json.dumps(dict(completed=True,results=results),indent=2))
(OUT/'job.json').write_text(json.dumps(dict(status='COMPLETED',phase='ROBUSTNESS',completed=len(results),heartbeat=time.time())))
for name,result in results.items():
 if name.startswith('27.71'):print(name,{p:{k:round(v,2) if isinstance(v,float) else v for k,v in x['2'].items()} for p,x in result.items()})
