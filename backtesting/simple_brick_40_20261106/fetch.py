"""Read-only research downloads; no runner or order methods."""
from pathlib import Path
import sys,json,os,subprocess,sqlite3,datetime,time,concurrent.futures,threading
ROOT=Path('/home/trading/sector-heatmap');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from sector_heatmap.network_policy import install_ipv4_only
install_ipv4_only()
def status(**values):
 p=OUT/'progress.json';data={'updated_at':time.time(),**values};p.with_suffix('.tmp').write_text(json.dumps(data));p.with_suffix('.tmp').replace(p)
if len(sys.argv)>1:
 from sector_heatmap.fyers_execution import _current_client
 client=_current_client()
 for name,res,start,end in [('recent_1m','1','2026-10-24','2026-11-05'),('daily','D','2025-11-05','2026-11-05')]:
  f=OUT/(name+'.json')
  if f.exists():continue
  q=dict(symbol='NSE:NIFTY50-INDEX',resolution=res,date_format=1,range_from=start,range_to=end,cont_flag=0)
  d=client.history(q)
  f.write_text(json.dumps({'request':q,'provider':'FYERS','response':d}))
  print(name,'status',d.get('s'),'bars',len(d.get('candles',[])),flush=True)
 sys.exit()
status(phase='UNDERLYING',pid=os.getpid())
from sector_heatmap.workspaces import isolated_environment
db=sqlite3.connect('file:'+str(ROOT/'.private/dashboard-login/registry.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
a=dict(db.execute("select * from accounts where id=?",('bf46fc364b610a0dfd338419e133cb41',)).fetchone());base=ROOT/'.private/dashboard-login/accounts'/a['id']
env=isolated_environment(a,base,ROOT/'.private/dashboard-login/registry.sqlite3',8080);env['PYTHONPATH']=str(base/'source')
r=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'underlying'],cwd=base/'source',env=env,capture_output=True,text=True,timeout=90)
print(r.stdout,flush=True)
if r.returncode:status(phase='ERROR',reason='Underlying download failed');sys.exit(2)
import requests
creds=json.loads((ROOT/'.private/dashboard-login/accounts/fd46b26f73022af571be11b1027c5291/credentials.json').read_text())
headers={'access-token':creds['DHAN_ACCESS_TOKEN'],'client-id':creds['DHAN_CLIENT_ID'],'Content-Type':'application/json'}
cache=OUT/'options';cache.mkdir(exist_ok=True);rate=threading.Lock();next_at=[0.];stop=threading.Event()
days=[datetime.date(2026,10,21)+datetime.timedelta(days=i) for i in range(16)]
tasks=[(str(d),str(d+datetime.timedelta(days=1)),s,k) for d in days if d.weekday()<5 for s in ('CALL','PUT') for k in range(-10,11)]
def work(task):
 a,b,s,k=task;f=cache/f'{a}_{b}_{s}_{k:+d}.json'
 if (OUT/'STOP').exists() or stop.is_set():return {'file':f.name,'error':'STOPPED'}
 if f.exists():return {'file':f.name,'cached':True}
 payload=dict(exchangeSegment='NSE_FNO',interval='1',securityId='13',instrument='OPTIDX',expiryFlag='WEEK',expiryCode=1,strike='ATM' if not k else f'ATM{k:+d}',drvOptionType=s,requiredData=['open','high','low','close','volume','strike','spot','oi'],fromDate=a,toDate=b)
 for attempt in range(2):
  with rate:
   time.sleep(max(0,next_at[0]-time.monotonic()));next_at[0]=time.monotonic()+.4
  try:
   r=requests.post('https://api.dhan.co/v2/charts/rollingoption',headers=headers,json=payload,timeout=(5,45))
   if r.status_code in (401,403):stop.set();return {'file':f.name,'error':'AUTH_REQUIRED'}
   body=r.json();d=(body.get('data') or {}).get('ce' if s=='CALL' else 'pe')
   if d and d.get('timestamp'):
    f.write_text(json.dumps({'request':payload,'data':d}));return {'file':f.name,'bars':len(d['timestamp'])}
   error='HTTP_'+str(r.status_code)+'_EMPTY'
  except Exception as exc:error=type(exc).__name__
  time.sleep(1)
 return {'file':f.name,'error':error}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for future in concurrent.futures.as_completed([pool.submit(work,t) for t in tasks]):
  item=future.result();results.append(item)
  status(phase='OPTIONS',pid=os.getpid(),completed=len(results),planned=len(tasks),failures=sum(bool(x.get('error')) for x in results))
  if len(results)%10==0:print('Options',len(results),'/',len(tasks),flush=True)
(OUT/'download_manifest.json').write_text(json.dumps(results,indent=2))
status(phase='DOWNLOADED',pid=os.getpid(),completed=len(results),planned=len(tasks),failures=sum(bool(x.get('error')) for x in results))
print('Download complete',len(results),'failures',sum(bool(x.get('error')) for x in results),flush=True)
