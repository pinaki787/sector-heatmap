"""Resumable read-only option history. Never imports trading/order clients."""
import argparse,concurrent.futures,datetime,json,threading,time,hashlib,sys
from pathlib import Path
import requests

def fetch_history(credentials_path,underlying_path,destination,workers=3,offsets=range(-3,4)):
 credentials=json.loads(Path(credentials_path).read_text());headers={'access-token':credentials['DHAN_ACCESS_TOKEN'],'client-id':credentials['DHAN_CLIENT_ID'],'Content-Type':'application/json'}
 raw=json.loads(Path(underlying_path).read_text());from zoneinfo import ZoneInfo
 zone=ZoneInfo('Asia/Kolkata');days=sorted({datetime.datetime.fromtimestamp(r[0],zone).date() for r in raw['rows'] if datetime.datetime.fromtimestamp(r[0],zone).date()>=datetime.date(2026,4,13)})
 directory=Path(destination);directory.mkdir(parents=True,exist_ok=True);chunks=[];i=0
 while i<len(days):
  start=days[i];end=start+datetime.timedelta(days=1);i+=1
  chunks.append((str(start),str(end)))
 tasks=[(start,end,side,offset) for start,end in chunks for side in ('CALL','PUT') for offset in offsets]
 lock=threading.Lock();rate_lock=threading.Lock();next_request=[0.];status={'planned':len(tasks),'completed':0,'cached':0,'failures':[],'responses':[],'underlying_sha256':hashlib.sha256(Path(underlying_path).read_bytes()).hexdigest(),'offsets':list(offsets),'scope':'Rolling nearest-week series; fixed-strike replay required. Missing or empty responses are not fabricated.'}
 def save_status():
  temp=directory/'manifest.tmp';temp.write_text(json.dumps(status,indent=2));temp.replace(directory/'manifest.json')
 def work(task):
  start,end,side,offset=task;name=f'{start}_{end}_{side}_{offset:+d}.json';path=directory/name
  if path.exists():
   try:
    obj=json.loads(path.read_text());d=obj['data'];assert len(d['timestamp'])>0
    return {'file':name,'cached':True,'bars':len(d['timestamp'])}
   except (ValueError,KeyError,AssertionError):pass
  payload=dict(exchangeSegment='NSE_FNO',interval='5',securityId='13',instrument='OPTIDX',expiryFlag='WEEK',expiryCode=1,strike='ATM' if not offset else f'ATM{offset:+d}',drvOptionType=side,requiredData=['open','high','low','close','volume','strike','spot','oi'],fromDate=start,toDate=end)
  error='unknown'
  for attempt in range(3):
   with rate_lock:
    pause=next_request[0]-time.monotonic()
    if pause>0:time.sleep(pause)
    next_request[0]=time.monotonic()+.3
   try:
    r=requests.post('https://api.dhan.co/v2/charts/rollingoption',headers=headers,json=payload,timeout=(5,15))
    if r.status_code in (401,403):return {'file':name,'error':f'authentication HTTP {r.status_code}'}
    if r.status_code!=200:error=f'HTTP {r.status_code}'
    else:
     body=r.json();d=(body.get('data') or {}).get('ce' if side=='CALL' else 'pe')
     if d and d.get('timestamp'):
      obj=dict(request=payload,data=d,received_at=datetime.datetime.now(datetime.timezone.utc).isoformat());temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj));temp.replace(path)
      return {'file':name,'bars':len(d['timestamp']),'cached':False}
     error='empty historical response'
   except (requests.RequestException,ValueError) as exc:error=type(exc).__name__
   time.sleep(1+attempt*2)
  return {'file':name,'error':error}
 save_status()
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
  futures={pool.submit(work,task):task for task in tasks}
  for future in concurrent.futures.as_completed(futures):
   item=future.result()
   with lock:
    status['completed']+=1
    if item.get('error'):status['failures'].append(item)
    else:status['responses'].append(item);status['cached']+=int(item.get('cached',False))
    save_status()
   if status['completed']%20==0 or status['completed']==status['planned']:print(json.dumps({k:status[k] for k in ('planned','completed','cached')}|{'failures':len(status['failures'])}),flush=True)
 return status

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--credentials',required=True);parser.add_argument('--underlying',required=True);parser.add_argument('--destination',required=True);parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
 # Project network policy applies only to this research process.
 from sector_heatmap.network_policy import install_ipv4_only
 install_ipv4_only()
 result=fetch_history(args.credentials,args.underlying,args.destination,args.workers);print('History retrieval complete; failures:',len(result['failures']))
