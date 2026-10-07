import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.fyers_execution import _current_client
OUT=Path(__file__).resolve().parent;client=_current_client()
symbols=sorted({r['symbol'] for r in json.loads((OUT/'journal_cases.json').read_text())})
for i,symbol in enumerate(symbols+["MCX:CRUDEOIL26OCTFUT"]):
 result=client.history(dict(symbol=symbol,resolution='1',date_format=1,range_from='2026-10-06',range_to='2026-10-07',cont_flag=0))
 (OUT/f'case_history_{i}.json').write_text(json.dumps(dict(symbol=symbol,response=result)))
 print(symbol,result.get('s'),len(result.get('candles',[])),flush=True);time.sleep(.4)
