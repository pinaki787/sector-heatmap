"""Read-only, exact-owner FYERS 30m query-window volume audit; no order paths."""
import os,json,sqlite3,hashlib,sys,time
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
root=Path(__file__).resolve().parents[1];workspace='bf46fc364b610a0dfd338419e133cb41';registry=root/'.private/dashboard-login/registry.sqlite3'
with sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True) as db:
 account=db.execute('SELECT broker,credential_identity FROM accounts WHERE id=?',(workspace,)).fetchone()
folder=registry.parent/'accounts'/workspace;source=folder/'source'
creds=json.loads((folder/'credentials.json').read_text());saved=json.loads((folder/'home/.fyers/token.json').read_text())
app=creds.get('FYERS_APP_ID')
assert account and account[0]=='FYERS' and app and saved.get('app_id')==app
assert hashlib.sha256(('FYERS|'+app).encode()).hexdigest()==account[1]
os.environ['FYERS_APP_ID']=app;os.environ['FYERS_ACCESS_TOKEN']=saved['access_token']
sys.path.insert(0,str(source))
import sector_heatmap
sector_heatmap.__path__.insert(0,str(source/'sector_heatmap'))
from sector_heatmap.fyers_transport import client as factory
from sector_heatmap.fyers_history import history
api=factory(client_id=os.environ['FYERS_APP_ID'],token=os.environ['FYERS_ACCESS_TOKEN'])
out=root/'.private/chart-order-rollouts/fyers-custom-hours-20261119';raws={}
try:
 for name,start,end in [('wide','2026-11-04','2026-11-19'),('narrow','2026-11-12','2026-11-18')]:
  if raws:time.sleep(1.5)
  reply=history(api,{'symbol':'NSE:NIFTY50-INDEX','resolution':'30','date_format':1,'range_from':start,'range_to':end,'cont_flag':0})
  if not isinstance(reply,dict) or reply.get('s')!='ok':raise RuntimeError('Selected broker historical query failed; stopped without retry.')
  (out/f'raw-30m-{name}.json').write_text(json.dumps(reply))
  raws[name]=reply['candles']
 zone=ZoneInfo('Asia/Kolkata')
 sums={}
 for name,rows in raws.items():
  days=defaultdict(lambda:dict(volume=0,count=0))
  for r in rows:
   dt=datetime.fromtimestamp(r[0],zone)
   if dt.hour*60+dt.minute<555 or dt.hour*60+dt.minute>=930:continue
   days[dt.date().isoformat()]['volume']+=r[5];days[dt.date().isoformat()]['count']+=1
  sums[name]=dict(days)
 report={'read_only':True,'requests':2,'symbol':'NSE:NIFTY50-INDEX','resolution':'30','daily_sums':sums,'orders_submitted':0}
 (out/'raw-volume-window-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:api._sector_pulse_ipv4_session.close()
