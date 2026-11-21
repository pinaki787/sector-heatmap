from pathlib import Path
import json,requests,sys
ROOT=Path('/home/trading/sector-heatmap');sys.path.insert(0,str(ROOT))
from sector_heatmap.network_policy import install_ipv4_only
install_ipv4_only()
c=json.loads((ROOT/'.private/dashboard-login/accounts/fd46b26f73022af571be11b1027c5291/credentials.json').read_text())
p=dict(exchangeSegment='NSE_FNO',interval='1',securityId='13',instrument='OPTIDX',expiryFlag='WEEK',expiryCode=1,strike='ATM',drvOptionType='CALL',requiredData=['open','high','low','close','volume','strike','spot','oi'],fromDate='2026-11-05',toDate='2026-11-05')
r=requests.post('https://api.dhan.co/v2/charts/rollingoption',headers={'access-token':c['DHAN_ACCESS_TOKEN'],'client-id':c['DHAN_CLIENT_ID'],'Content-Type':'application/json'},json=p,timeout=30)
d=r.json();print(r.status_code,{k:v for k,v in d.items() if k!='data'});print('data keys',list((d.get('data') or {}).keys()))
(Path(__file__).parent/'option_probe.json').write_text(json.dumps({'request':p,'response':d,'http':r.status_code}))
