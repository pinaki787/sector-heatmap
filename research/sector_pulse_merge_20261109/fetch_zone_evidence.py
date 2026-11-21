import json
from pathlib import Path
from sector_heatmap.fyers_transport import client
from datetime import datetime
from zoneinfo import ZoneInfo
root=Path('/home/trading/sector-heatmap');base=Path(__file__).parent
p=root/'.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/home/.fyers/token.json'
t=json.loads(p.read_text()); app=t.get('app_id') or t.get('client_id');token=t.get('access_token') or t.get('token')
if ':' in token:token=token.split(':',1)[1]
api=client(client_id=app,token=token)
for symbol in ['NSE:HCLTECH-EQ','NSE:INFY-EQ']:
 r=api.history(data=dict(symbol=symbol,resolution='5',date_format='1',range_from='2026-11-02',range_to='2026-11-09',cont_flag='1'))
 base.joinpath(symbol.split(':')[1]+'.json').write_text(json.dumps(r))
 print(symbol,r.get('s'),r.get('code'),len(r.get('candles',[])))
 if r.get('s')!='ok':break
 if 'HCL' in symbol:
  for b in r['candles']:
   dt=datetime.fromtimestamp(b[0],ZoneInfo('Asia/Kolkata'))
   if str(dt.date())=='2026-11-09':print(dt.strftime('%H:%M'),b[1:5])
