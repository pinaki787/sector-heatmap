"""Read-only provider resolution diagnosis; sanitized metadata only."""
from sector_heatmap.config import load_config
from fyers_apiv3 import fyersModel
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
c=load_config()['FYERS_ACCESS_TOKEN'];app,token=c.split(':',1);client=fyersModel.FyersModel(client_id=app,token=token)
now=datetime.now(ZoneInfo('Asia/Kolkata'))
for resolution,days in [('30',99),('1W',365),('1M',365)]:
 r=client.history({'symbol':'MCX:CRUDEOILM26OCTFUT','resolution':resolution,'date_format':1,'range_from':(now-timedelta(days=days-1)).date().isoformat(),'range_to':now.date().isoformat(),'cont_flag':0})
 print(resolution,{k:r.get(k) for k in ('s','code','message')},'candles',len(r.get('candles',[])))
