"""Read-only availability probe for FYERS NIFTY one-minute history."""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from sector_heatmap.fyers_transport import client

def main():
    path=Path('.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/home/.fyers/token.json')
    if not path.exists():
        print('Saved token unavailable');return
    token=json.loads(path.read_text())
    app=token.get('app_id') or token.get('client_id')
    value=token.get('access_token') or token.get('token')
    if not app or not value:
        print('Saved token incomplete');return
    if ':' in value:
        prefix,value=value.split(':',1)
        if prefix!=app:
            print('Application mismatch');return
    api=client(client_id=app,token=value)
    for day in ['2025-10-27','2026-10-23']:
        r=api.history(data=dict(symbol='NSE:NIFTY50-INDEX',resolution='1',date_format='1',range_from=day,range_to=day,cont_flag='1'))
        rows=r.get('candles',[])
        result=dict(day=day,status=r.get('s'),code=r.get('code'),message=r.get('message'),bars=len(rows))
        if rows:
            result['first_ist']=datetime.fromtimestamp(rows[0][0],ZoneInfo('Asia/Kolkata')).isoformat()
            result['last_ist']=datetime.fromtimestamp(rows[-1][0],ZoneInfo('Asia/Kolkata')).isoformat()
        print(json.dumps(result))
        if r.get('s')!='ok':break
if __name__=='__main__':main()
