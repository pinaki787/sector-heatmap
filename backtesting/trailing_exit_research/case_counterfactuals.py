"""Recorded entries and baseline exits retained; close-only counterfactuals."""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent;IST=ZoneInfo('Asia/Kolkata')
quotes={json.loads(p.read_text())['symbol']:json.loads(p.read_text())['response']['candles'] for p in OUT.glob('case_history_*.json')}
results=[]
for t in json.loads((OUT/'journal_cases.json').read_text()):
 if not (100<=t['realized_pnl']<=125 or 2000<=t['realized_pnl']<=2250):continue
 rows=[r for r in quotes[t['symbol']] if r[0]>=t['entry_time'] and r[0]+60<=t['exit_time']]
 for a in (.025,.05,.10,.20,.25,.30):
  for retain in (.4,.6,.8):
   best=t['entry_price'];stop=None;fill=t['exit_price'];trigger=None;armed=False
   for i,r in enumerate(rows):
    best=max(best,r[4])
    if best>=t['entry_price']*(1+a):armed=True;stop=max(stop or 0,t['entry_price']+retain*(best-t['entry_price']))
    nextq=next((x for x in quotes[t['symbol']] if x[0]==r[0]+60 and x[0]<=t['exit_time']),None)
    if stop is not None and r[4]<=stop and nextq is not None:fill=nextq[1];trigger=r[0]+60;break
   unit=t['entry_filled']*t['quantity_multiplier']
   future=[r for r in quotes[t['symbol']] if trigger and trigger<=r[0]<=trigger+1800]
   results.append(dict(symbol=t['symbol'],entry_time=datetime.fromtimestamp(t['entry_time'],IST).isoformat(),activation=a,retain=retain,armed=armed,trigger=trigger,close_only_gross=(fill-t['entry_price'])*unit,recorded_paper_gross=t['realized_pnl'],future_close_above_peak=bool(future) and max(r[4] for r in future)>best,filled_bid_unknown=True))
(OUT/'case_counterfactuals.json').write_text(json.dumps(results,indent=2))
for r in results:
 if r['activation'] in (.025,.05,.20) and r['retain']==.6:print(json.dumps(r))
