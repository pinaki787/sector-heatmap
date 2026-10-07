import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.fyers_execution import _current_client
OUT=Path(__file__).resolve().parent
client=_current_client()
orders=json.loads((ROOT/'.private/renko-supertrend-state.json').read_text()).get('order_history',[])
symbols=sorted({r['symbol'] for r in orders if r.get('symbol','').startswith('MCX:CRUDE') and r['symbol'].endswith(('CE','PE'))})
for i,symbol in enumerate(symbols):
 r=client.history(dict(symbol=symbol,resolution='1',date_format=1,range_from='2026-07-01',range_to='2026-10-06',cont_flag=0,oi_flag=1))
 (OUT/f'crude_option_{i}.json').write_text(json.dumps(dict(request=dict(symbol=symbol),response=r)))
 print(symbol,r.get('s'),r.get('code'),len(r.get('candles',[])))
 time.sleep(.4)
print('expired SDK available',hasattr(client,'history_fno_expired'))
