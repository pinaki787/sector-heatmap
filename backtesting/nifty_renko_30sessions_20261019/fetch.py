"""Research-only historical downloads. No order or runner mutations."""
import sys,os,json,pathlib,sqlite3,subprocess,datetime,time
ROOT=pathlib.Path('/home/trading/sector-heatmap');OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from sector_heatmap.network_policy import install_ipv4_only
install_ipv4_only()
if len(sys.argv)==1:
 from sector_heatmap.workspaces import isolated_environment
 db=sqlite3.connect('file:'+str(ROOT/'.private/dashboard-login/registry.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 a=dict(db.execute("select * from accounts where id=?",('bf46fc364b610a0dfd338419e133cb41',)).fetchone());base=ROOT/'.private/dashboard-login/accounts'/a['id'];env=isolated_environment(a,base,ROOT/'.private/dashboard-login/registry.sqlite3',8080);env['PYTHONPATH']=str(base/'source');env['PYTHONDONTWRITEBYTECODE']='1'
 r=subprocess.run([sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'underlying'],cwd=base/'source',env=env,capture_output=True,text=True,timeout=90)
 print(r.stdout if r.returncode==0 else 'FYERS historical retrieval failed; no mutations.',flush=True)
 import requests
 creds=json.loads((ROOT/'.private/dashboard-login/accounts/b0041912d9d6f68d352814cbd24bf6da/credentials.json').read_text());headers={'access-token':creds['DHAN_ACCESS_TOKEN'],'client-id':creds['DHAN_CLIENT_ID'],'Content-Type':'application/json'}
 cache=OUT/'options';cache.mkdir(exist_ok=True);progress=[]
 for start,end in [('2026-09-01','2026-09-30'),('2026-09-30','2026-10-20')]:
  for side in ('CALL','PUT'):
   for offset in range(-10,11):
    file=cache/f'{start}_{end}_{side}_{offset:+d}.json'
    if file.exists():continue
    payload=dict(exchangeSegment='NSE_FNO',interval='1',securityId='13',instrument='OPTIDX',expiryFlag='WEEK',expiryCode=1,strike='ATM' if not offset else f'ATM{offset:+d}',drvOptionType=side,requiredData=['open','high','low','close','volume','strike','spot','oi'],fromDate=start,toDate=end)
    try:
     res=requests.post('https://api.dhan.co/v2/charts/rollingoption',headers=headers,json=payload,timeout=(5,25));data=res.json();d=(data.get('data') or {}).get('ce' if side=='CALL' else 'pe')
     if res.status_code in (401,403):
      (OUT/'download-status.json').write_text(json.dumps({'status':'AUTH_REQUIRED','provider':'Dhan','completed':len(progress)}));print('Dhan historical session unavailable; authentication required.',flush=True);sys.exit(2)
     if d and d.get('timestamp'):file.write_text(json.dumps(dict(request=payload,data=d)));progress.append({'file':file.name,'bars':len(d['timestamp'])})
     else:progress.append({'file':file.name,'http':res.status_code,'bars':0})
    except Exception as e:progress.append({'file':file.name,'error':type(e).__name__})
    (OUT/'download-status.json').write_text(json.dumps({'status':'DOWNLOADING','responses':progress}));print('Option history responses',len(progress),'latest bars',progress[-1].get('bars',0),flush=True);time.sleep(.35)
 (OUT/'download-status.json').write_text(json.dumps({'status':'FINISHED','responses':progress}))
else:
 from sector_heatmap.fyers_execution import _current_client
 client=_current_client();q=dict(symbol='NSE:NIFTY50-INDEX',resolution='1',date_format=1,range_from='2026-07-22',range_to='2026-10-19',cont_flag=0)
 data=client.history(q);rows=data.get('candles',[])
 (OUT/'underlying.json').write_text(json.dumps({'request':q,'provider':'FYERS','rows':rows,'status':data.get('s'),'code':data.get('code')}));print('FYERS underlying bars',len(rows),flush=True)

