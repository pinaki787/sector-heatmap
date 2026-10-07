"""Read-only FYERS ETF volume history; never calls an order endpoint."""
import sys,json
from pathlib import Path
from datetime import date,timedelta,datetime
from zoneinfo import ZoneInfo
import pandas as pd
from fyers_apiv3 import fyersModel
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from sector_heatmap.web import load_config
OUT=Path(__file__).resolve().parent
if __name__=='__main__':
    app,token=load_config()['FYERS_ACCESS_TOKEN'].split(':',1)
    client=fyersModel.FyersModel(client_id=app,token=token)
    rows=[];cursor=date(2025,8,15);end=date(2026,9,28)
    while cursor<=end:
        stop=min(cursor+timedelta(days=89),end)
        r=client.history(dict(symbol='NSE:NIFTYBEES-EQ',resolution='5',date_format=1,
            range_from=str(cursor),range_to=str(stop),cont_flag=1))
        if r.get('s')!='ok':raise RuntimeError(r.get('message','History unavailable'))
        rows.extend(row for row in r['candles'] if cursor<=datetime.fromtimestamp(row[0],ZoneInfo('Asia/Kolkata')).date()<=stop)
        cursor=stop+timedelta(days=1)
    d=pd.DataFrame(rows,columns=['epoch','open','high','low','close','volume']).drop_duplicates()
    if d.epoch.duplicated().any():
        conflicts=d[d.epoch.duplicated(keep=False)]
        conflicts.to_csv(OUT/'volume_conflicts.csv',index=False)
        print('Conflicting rows:',len(conflicts));print(conflicts.head(8).to_string(index=False))
    # Only volume is used. Two revised ETF OHLC rows have identical volume.
    assert d.groupby('epoch').volume.nunique().max()==1,'Conflicting volume bars'
    d=d.drop_duplicates('epoch',keep='last')
    d.index=pd.to_datetime(d.pop('epoch'),unit='s',utc=True).dt.tz_convert('Asia/Kolkata')
    d=d.sort_index();d.to_csv(OUT/'niftybees_5m.csv')
    audit=dict(symbol='NSE:NIFTYBEES-EQ',source='FYERS history',start=str(d.index[0]),end=str(d.index[-1]),
               bars=len(d),positive_volume_bars=int((d.volume>0).sum()),negative_volume_bars=int((d.volume<0).sum()))
    (OUT/'volume_audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))
