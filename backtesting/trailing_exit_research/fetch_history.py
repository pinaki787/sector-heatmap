"""Read-only FYERS history probes using existing application credentials. No login."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.fyers_execution import _current_client
OUT=Path(__file__).resolve().parent
s=json.loads((ROOT/'.private/renko-supertrend-state.json').read_text())
orders=s.get('order_history',[])
symbols=sorted({r.get('symbol') for r in orders if r.get('symbol')})
print('recorded contract count',len(symbols))
(OUT/'recorded_contracts.json').write_text(json.dumps([{k:r.get(k) for k in ('symbol','strike','expiry_epoch','option_type','lot_size','quantity_multiplier','filled','fill_price','first_fill_confirmed_at','filled_at','side','mode','indicator_snapshot')} for r in orders],indent=2))
client=_current_client()
requests=[('underlying',s['config']['underlying'],'2026-07-01','2026-10-06')]+[(f'option_{i}',v,'2026-08-01','2026-10-06') for i,v in enumerate(symbols[-3:])]
for name,symbol,first,last in requests:
 try:
  result=client.history(dict(symbol=symbol,resolution='1',date_format=1,range_from=first,range_to=last,cont_flag=0,oi_flag=1))
  payload=dict(request=dict(symbol=symbol,first=first,last=last),response=result)
  (OUT/(name+'.json')).write_text(json.dumps(payload))
  print(name,symbol,'status',result.get('s'),'code',result.get('code'),'rows',len(result.get('candles',[])))
 except Exception as e:print(name,'error class',type(e).__name__)
 time.sleep(.4)
