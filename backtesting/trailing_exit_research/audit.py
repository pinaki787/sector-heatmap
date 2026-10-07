import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
coverage=[]
for p in (ROOT/'.private/renko-chart-history').glob('*.json'):
 d=json.loads(p.read_text()); rows=d.get('rows',d.get('candles',[]))
 coverage.append(dict(path=str(p),keys=list(d),metadata={k:v for k,v in d.items() if k not in ('rows','candles')},count=len(rows),first=rows[0] if rows else None,last=rows[-1] if rows else None))
(OUT/'coverage.json').write_text(json.dumps(coverage,indent=2))
for d in coverage:
 print(json.dumps({k:v for k,v in d.items() if k!='metadata'}))
s=json.loads((ROOT/'.private/renko-supertrend-state.json').read_text())
(OUT/'config.json').write_text(json.dumps(s.get('config',{}),indent=2))
print('config',json.dumps(s.get('config',{})))
print('state keys',list(s))
for k in ('journal','trades','closed_trades','orders'):
 v=s.get(k,[]);print(k,len(v))
 if v: print('sample keys',list(v[-1]))
