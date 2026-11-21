"""Fetch only missing fixed-strike history using the documented ATM-relative band."""
import argparse,datetime,json,math,time,sys,concurrent.futures,threading
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
Z=ZoneInfo('Asia/Kolkata')
def repair(folder,results_path,credentials_path,workers=6):
 folder=Path(folder);results=json.loads(Path(results_path).read_text());credentials=json.loads(Path(credentials_path).read_text());headers={'access-token':credentials['DHAN_ACCESS_TOKEN'],'client-id':credentials['DHAN_CLIENT_ID'],'Content-Type':'application/json'}
 atm={}
 for path in (folder/'cache').glob('*_+0.json'):
  obj=json.loads(path.read_text());d=obj['data'];side=obj['request']['drvOptionType']
  for ts,strike in zip(d.get('timestamp',[]),d.get('strike',[])):atm[int(ts),side]=float(strike)
 tasks=set();unsupported=[];required={}
 for ts,side,strike in results['missing_contract_keys']:
  current=atm.get((int(ts),side))
  if current is None:unsupported.append(dict(timestamp=ts,side=side,strike=strike,reason='Missing ATM source needed to resolve relative band'));continue
  offset=int(round((strike-current)/50))
  if abs(offset)>10:unsupported.append(dict(timestamp=ts,side=side,strike=strike,offset=offset,reason='Outside documented rolling-option ATM +/-10 history band'));continue
  date=datetime.datetime.fromtimestamp(ts,Z).date();task=(str(date),str(date+datetime.timedelta(days=1)),side,offset);tasks.add(task);required.setdefault(task,set()).add((int(ts),float(strike)))
  # Extend one further strike in the same direction when a held contract approaches a band edge.
  if offset and abs(offset)<10:tasks.add((str(date),str(date+datetime.timedelta(days=1)),side,offset+(1 if offset>0 else -1)))
 rate=threading.Lock();next_request=[0.]
 def work(task):
  start,end,side,offset=task;path=folder/'cache'/f'{start}_{end}_{side}_{offset:+d}.json';payload=dict(exchangeSegment='NSE_FNO',interval='5',securityId='13',instrument='OPTIDX',expiryFlag='WEEK',expiryCode=1,strike='ATM' if not offset else f'ATM{offset:+d}',drvOptionType=side,requiredData=['open','high','low','close','volume','strike','spot','oi'],fromDate=start,toDate=end);error=None
  if path.exists():
   cached=json.loads(path.read_text())['data'];available=set(zip(map(int,cached.get('timestamp',[])),map(float,cached.get('strike',[]))))
   if required.get(task,set())<=available:return dict(file=path.name,bars=len(cached['timestamp']),status='CACHED')
  for attempt in range(3):
   with rate:
    pause=next_request[0]-time.monotonic()
    if pause>0:time.sleep(pause)
    next_request[0]=time.monotonic()+.3
   try:
    response=requests.post('https://api.dhan.co/v2/charts/rollingoption',headers=headers,json=payload,timeout=(5,15))
    if response.status_code!=200:error=f'HTTP {response.status_code}'
    else:
     obj=response.json();d=(obj.get('data') or {}).get('ce' if side=='CALL' else 'pe')
     if d and d.get('timestamp'):
      if path.exists():
       backup=path.parent/'revisions';backup.mkdir(exist_ok=True);old=path.read_bytes();import hashlib
       target=backup/(path.stem+'-'+hashlib.sha256(old).hexdigest()[:12]+'.json')
       if not target.exists():target.write_bytes(old)
      temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(dict(request=payload,data=d,received_at=datetime.datetime.now(datetime.timezone.utc).isoformat())));temporary.replace(path)
      return dict(file=path.name,bars=len(d['timestamp']),status='RECEIVED')
     error='empty history'
   except (requests.RequestException,ValueError) as exc:error=type(exc).__name__
   time.sleep(1+attempt*2)
  return dict(file=path.name,status='FAILED',error=error)
 completed=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
  for item in pool.map(work,sorted(tasks)):
   completed.append(item)
   if len(completed)%10==0:print('Repair requests completed',len(completed),'/',len(tasks),flush=True)
 report=dict(tasks=len(tasks),completed=completed,unsupported=unsupported);out=Path(results_path).parent/'repair-report.json';out.write_text(json.dumps(report,indent=2));print(json.dumps(dict(tasks=len(tasks),failed=sum(x['status']=='FAILED' for x in completed),unsupported=len(unsupported))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--folder',default='backtesting/nifty_atm_options');p.add_argument('--results',required=True);p.add_argument('--credentials',required=True);p.add_argument('--workers',type=int,default=6);a=p.parse_args()
 from sector_heatmap.network_policy import install_ipv4_only
 install_ipv4_only();repair(a.folder,a.results,a.credentials,a.workers)
