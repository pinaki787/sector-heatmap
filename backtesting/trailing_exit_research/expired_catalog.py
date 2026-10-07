import sys,json,requests,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.config import load_config
OUT=Path(__file__).resolve().parent
headers={'Authorization':load_config()['FYERS_ACCESS_TOKEN']}
for expiry in ('2026-07-16','2026-08-17','2026-09-17'):
 r=requests.get('https://api-t1.fyers.in/data/history/fno/expired/underlying-symbols',params=dict(symbol='MCX:CRUDEOIL26OCTFUT',expiry_date=expiry),headers=headers,timeout=25)
 d=r.json();(OUT/f'catalog_{expiry}.json').write_text(json.dumps(d))
 print(expiry,'status',d.get('s'),'data',str(d.get('data'))[:700]);time.sleep(.4)
