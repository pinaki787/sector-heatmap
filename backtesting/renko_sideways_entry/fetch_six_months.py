"""Read-only FYERS history retrieval; never submits or changes orders."""
import hashlib,json,time
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from sector_heatmap.fyers_transport import client
ROOT=Path(__file__).resolve().parent
ACCOUNT=Path('.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41')
def main():
    token=json.loads((ACCOUNT/'home/.fyers/token.json').read_text())
    app=token.get('app_id') or token.get('client_id')
    value=token.get('access_token') or token.get('token')
    if not app or not value:raise RuntimeError('Saved account token incomplete')
    if ':' in value:
        prefix,value=value.split(':',1)
        if prefix!=app:raise RuntimeError('Account/token application mismatch')
    api=client(client_id=app,token=value)
    profile=api.get_profile()
    if profile.get('s')!='ok':raise RuntimeError('FYERS account authentication failed: '+str(profile.get('code')))
    start=date(2026,3,23);end=date(2026,10,11);cursor=start;allrows={};chunks=[];duplicates=0;revisions=0
    while cursor<=end:
        stop=min(end,cursor+timedelta(days=29))
        response=api.history(data=dict(symbol='NSE:NIFTY50-INDEX',resolution='5',date_format='1',range_from=cursor.isoformat(),range_to=stop.isoformat(),cont_flag='1'))
        if response.get('s')!='ok':raise RuntimeError('FYERS history failed '+cursor.isoformat()+' code '+str(response.get('code'))+' '+str(response.get('message')))
        bars=response.get('candles',[])
        for r in bars:
            if r[0] in allrows:
                duplicates+=1;revisions+=allrows[r[0]]!=r
            allrows[r[0]]=r
        chunks.append(dict(start=cursor.isoformat(),end=stop.isoformat(),bars=len(bars)))
        print(cursor,stop,'bars',len(bars),flush=True)
        cursor=stop+timedelta(days=1);time.sleep(.3)
    rows=sorted(allrows.values())
    result=dict(symbol='NSE:NIFTY50-INDEX',resolution_minutes=5,requested_start=str(start),requested_end=str(end),retrieved_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),chunks=chunks,duplicates=duplicates,revisions=revisions,rows=rows)
    dest=ROOT/'six_month_candles.json';dest.write_text(json.dumps(result))
    print('Total bars',len(rows),'sha256',hashlib.sha256(dest.read_bytes()).hexdigest())
if __name__=='__main__':main()

