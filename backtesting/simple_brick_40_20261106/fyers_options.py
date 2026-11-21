"""Read-only FYERS exact-contract repair and wider premium surface."""
from pathlib import Path
import sys,json,os,subprocess,sqlite3,time
ROOT=Path('/home/trading/sector-heatmap');OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from sector_heatmap.network_policy import install_ipv4_only
install_ipv4_only()
if len(sys.argv)==1:
 from sector_heatmap.workspaces import isolated_environment
 db=sqlite3.connect('file:'+str(ROOT/'.private/dashboard-login/registry.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 a=dict(db.execute("select * from accounts where id=?",('bf46fc364b610a0dfd338419e133cb41',)).fetchone());base=ROOT/'.private/dashboard-login/accounts'/a['id']
 env=isolated_environment(a,base,ROOT/'.private/dashboard-login/registry.sqlite3',8080);env['PYTHONPATH']=str(base/'source')
 r=subprocess.run([sys.executable,'-u',str(Path(__file__).resolve()),'fetch'],cwd=base/'source',env=env)
 sys.exit(r.returncode)
sys.path.remove(str(ROOT))
from sector_heatmap.config import load_config
import requests
token=load_config()['FYERS_ACCESS_TOKEN'];cache=OUT/'fyers-options';cache.mkdir(exist_ok=True)
def get(path,query,name):
 f=cache/(name+'.json')
 if f.exists():return json.loads(f.read_text())['response']
 time.sleep(1.3)
 r=requests.get('https://api-t1.fyers.in'+path,params=query,headers={'Authorization':token},timeout=30);d=r.json()
 f.write_text(json.dumps({'path':path,'request':query,'http':r.status_code,'response':d}))
 print(name,r.status_code,d.get('s'),len(d.get('candles') or []),d.get('message','')[:160],flush=True)
 return d
d=get('/data/history/fno/expired/expiry-dates',dict(symbol='NSE:NIFTY50-INDEX',range_from='2026-09-23',range_to='2026-11-05',date_format=1),'expiries')
print('expiry metadata',str(d)[:600],flush=True)
d=get('/data/history/fno/expired/underlying-symbols',dict(symbol='NSE:NIFTY50-INDEX',expiry_date='2026-11-03'),'contracts-2026-11-03')
print('contract fields',list((d.get('data') or {}).keys()),flush=True)

request_file=OUT/'repair_requests.json'
if request_file.exists():
 import re,csv,datetime
 requests_list=json.loads(request_file.read_text())
 for request in requests_list:
  expiry=request['expiry'];side=request['side'];strike=request['strike'];day=request['day']
  if expiry<='2026-11-05':
   metadata=get('/data/history/fno/expired/underlying-symbols',dict(symbol='NSE:NIFTY50-INDEX',expiry_date=expiry),'contracts-'+expiry)
   options=(metadata.get('data') or {}).get('contracts',{}).get('options',[])
  else:
   master=Path(os.environ['HOME'])/'.fyers/sym_master/NSE_FO.csv'
   options=[row[9] for row in csv.reader(master.open()) if len(row)>9]
  suffix=str(int(strike))+('CE' if side=='CALL' else 'PE')
  # Match full expiry-specific ticker, not a hand-constructed contract.
  code=expiry[2:4]+'123456789OND'[int(expiry[5:7])-1]+expiry[8:10]
  monthly=expiry[2:4]+datetime.date.fromisoformat(expiry).strftime('%b').upper()
  names=[name for name in options if name in ('NSE:NIFTY'+code+suffix,'NSE:NIFTY'+monthly+suffix)]
  if not names:print('MISSING CONTRACT',expiry,side,strike,flush=True);continue
  symbol=names[0]
  expired=expiry<='2026-11-05'
  params=dict(symbol=symbol,resolution='1',date_format=1,range_from=day,range_to=day)
  if not expired:params['cont_flag']=0
  get('/data/history/fno/expired/historical-data' if expired else '/data/history',params,'hist-'+symbol.replace(':','_')+'-'+day)
