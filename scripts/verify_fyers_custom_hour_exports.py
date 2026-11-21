"""Compare exported custom-hour bars with separate completed 30m chart exports."""
import argparse,csv,json,hashlib
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal
from collections import defaultdict
p=argparse.ArgumentParser();p.add_argument('folder',type=Path);a=p.parse_args();root=a.folder
def read(f):return [r for r in csv.DictReader(f.open()) if r.get('provisional','0') not in ['1','true']]
def dt(r):return datetime.fromisoformat(r['source_time_utc'].replace('Z','+00:00'))
source=root/'nse-nifty50-index-fyers-30m-candles (1).csv';groups=defaultdict(list)
for r in read(source):groups[(dt(r)+timedelta(hours=5,minutes=30)).date()].append(r)
eligible={};excluded=[]
for day,rows in groups.items():
 local=[(dt(r)+timedelta(hours=5,minutes=30)).hour*60+(dt(r)+timedelta(hours=5,minutes=30)).minute for r in rows]
 if local==list(range(555,916,30)):eligible[day]=rows
 else:excluded.append({'date':str(day),'source_bars':len(rows),'local_minutes':local})
results=[]
for hours in [6,14,22,23]:
 f=root/f'nse-nifty50-index-fyers-{hours}h-candles.csv';actual={dt(r):r for r in read(f)}
 checked=0;errors=[];bars=0
 for day,rows in eligible.items():
  buckets=[rows[:12],rows[12:]] if hours==6 else [rows]
  for b in buckets:
   key=dt(b[0]);r=actual.get(key);bars+=1
   if r is None:errors.append({'time':key.isoformat(),'reason':'missing custom bar'});continue
   want={'open':Decimal(b[0]['open']),'high':max(Decimal(x['high']) for x in b),'low':min(Decimal(x['low']) for x in b),'close':Decimal(b[-1]['close']),'volume':sum(Decimal(x['volume']) for x in b)}
   for field,v in want.items():
    checked+=1
    if Decimal(r[field])!=v:errors.append({'time':key.isoformat(),'field':field,'expected':str(v),'actual':r[field]})
  # Only matching completed session buckets are compared; all other custom history is out of scope.
 results.append({'hours':hours,'session_days':len(eligible),'bars_checked':bars,'fields_checked':checked,'mismatches':errors,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
report={'status':'FAIL' if any(x['mismatches'] for x in results) else 'PASS','results':results,'excluded_incomplete_or_special_sessions':excluded,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'Separate hosted FYERS adapter exports. Regular sessions with all13 half-hour source openings only; special/partial sessions excluded and listed. Excludes forming bars. Not an independent native TradingView or raw broker resolution comparison.'}
(root/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(report['status']!='PASS')
