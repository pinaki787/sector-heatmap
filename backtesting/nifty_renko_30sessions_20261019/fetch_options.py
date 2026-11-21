"""Resumable historical download only; no execution clients."""
import json,pathlib,requests,time,threading,concurrent.futures,sys
ROOT=pathlib.Path('/home/trading/sector-heatmap');OUT=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from sector_heatmap.network_policy import install_ipv4_only
install_ipv4_only()
c=json.loads((ROOT/'.private/dashboard-login/accounts/b0041912d9d6f68d352814cbd24bf6da/credentials.json').read_text())
headers={'access-token':c['DHAN_ACCESS_TOKEN'],'client-id':c['DHAN_CLIENT_ID'],'Content-Type':'application/json'}
cache=OUT/'options';cache.mkdir(exist_ok=True);rate=threading.Lock();next_at=[0.]
tasks=[(a,b,s,k) for a,b in [('2026-09-01','2026-09-30'),('2026-09-30','2026-10-20')] for s in ('CALL','PUT') for k in range(-10,11)]
def work(t):
 a,b,s,k=t;f=cache/f'{a}_{b}_{s}_{k:+d}.json'
 if f.exists():return {'file':f.name,'cached':True}
 payload=dict(exchangeSegment='NSE_FNO',interval='1',securityId='13',instrument='OPTIDX',expiryFlag='WEEK',expiryCode=1,strike='ATM' if not k else f'ATM{k:+d}',drvOptionType=s,requiredData=['open','high','low','close','volume','strike','spot','oi'],fromDate=a,toDate=b)
 for attempt in range(2):
  with rate:
   time.sleep(max(0,next_at[0]-time.monotonic()));next_at[0]=time.monotonic()+.5
  try:
   r=requests.post('https://api.dhan.co/v2/charts/rollingoption',headers=headers,json=payload,timeout=(5,60));d=(r.json().get('data') or {}).get('ce' if s=='CALL' else 'pe')
   if r.status_code in (401,403):return {'file':f.name,'error':'AUTH_REQUIRED'}
   if d and d.get('timestamp'):
    f.write_text(json.dumps({'request':payload,'data':d}));return {'file':f.name,'bars':len(d['timestamp'])}
   error='HTTP_'+str(r.status_code)+'_EMPTY'
  except Exception as e:error=type(e).__name__
  time.sleep(1)
 return {'file':f.name,'error':error}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for item in pool.map(work,tasks):
  results.append(item);(OUT/'download-status.json').write_text(json.dumps({'status':'DOWNLOADING','completed':len(results),'planned':len(tasks),'responses':results}))
  if len(results)%10==0:print('Historical requests completed',len(results),'/',len(tasks),flush=True)
(OUT/'download-status.json').write_text(json.dumps({'status':'FINISHED','responses':results,'failures':[r for r in results if r.get('error')]}))
print('Download finished. Failed responses:',sum(bool(r.get('error')) for r in results),flush=True)

