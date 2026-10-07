import sys,json,requests
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.config import load_config
out=Path(__file__).resolve().parent
r=requests.get('https://api-t1.fyers.in/data/history/fno/expired/expiry-dates',params=dict(symbol='MCX:CRUDEOIL26OCTFUT',range_from='2026-07-01',range_to='2026-10-06',date_format='1'),headers={'Authorization':load_config()['FYERS_ACCESS_TOKEN']},timeout=25)
try:d=r.json()
except ValueError:d={'non_json_response':True}
(out/'expired_probe.json').write_text(json.dumps({'http_status':r.status_code,'response':d},indent=2))
print('expired endpoint HTTP',r.status_code,'response keys',list(d),'code',d.get('code'),'message',d.get('message'))
