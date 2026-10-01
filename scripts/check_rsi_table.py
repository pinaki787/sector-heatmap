"""Read-only live endpoint check; no orders or runner mutation."""
import json,time,urllib.request
from pathlib import Path
if __name__=='__main__':
 url='http://127.0.0.1:8080/api/rsi-table?symbol=MCX%3ACRUDEOILM26OCTFUT&rsi_length=14&ma_length=14&ma_type=SMA'
 start=time.monotonic();data=json.load(urllib.request.urlopen(url,timeout=60));print('Fetch seconds',round(time.monotonic()-start,2))
 for row in data['rows']:print(row)
 Path('output/rsi-table-final.json').write_text(json.dumps(data,indent=2))
 start=time.monotonic();second=json.load(urllib.request.urlopen(url,timeout=60));print('Cached seconds',round(time.monotonic()-start,3));assert [(r.get('history_fetched_at'),r.get('rsi')) for r in second['rows']]==[(r.get('history_fetched_at'),r.get('rsi')) for r in data['rows']]
