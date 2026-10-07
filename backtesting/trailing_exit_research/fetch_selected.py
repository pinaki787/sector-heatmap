"""Read-only exact listed-contract historical candles; no auth mutation/orders."""
import sys,json,csv,re,time,requests
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent;ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.config import load_config
from sector_heatmap.fyers_execution import _current_client
IST=ZoneInfo('Asia/Kolkata'); catalog=[]
for p in OUT.glob('catalog_*.json'):
 d=json.loads(p.read_text())['data'];expiry=d['expiry_date']
 for symbol in d['contracts']['options']:
  m=re.search(r'(\d{4,5})(CE|PE)$',symbol)
  if m:catalog.append(dict(symbol=symbol,expiry=expiry,strike=int(m[1]),type=m[2],lot=None,multiplier=None,source=p.name))
for row in csv.reader((ROOT/'.private/ema-band-masters/MCX_COM.csv').open()):
 if len(row)>16 and row[13]=='CRUDEOIL' and row[16] in ('CE','PE'):
  expiry=str(datetime.fromtimestamp(float(row[8]),IST).date())
  catalog.append(dict(symbol=row[9],expiry=expiry,strike=float(row[15]),type=row[16],lot=int(float(row[3])),multiplier=None,source='current_master'))
trades=json.loads((OUT/'entries.json').read_text());selected=[]
for t in trades:
 day=str(datetime.fromtimestamp(t['at'],IST).date());typ='CE' if t['sign']==1 else 'PE'
 candidates=[c for c in catalog if c['expiry']>=day and c['type']==typ]
 if not candidates:continue
 expiry=min(c['expiry'] for c in candidates);cs=[c for c in candidates if c['expiry']==expiry]
 c=min(cs,key=lambda c:(abs(c['strike']-t['price']),c['strike'],c['symbol']))
 selected.append({**t,'contract':c})
(OUT/'selected_entries.json').write_text(json.dumps(selected,indent=2));(OUT/'contract_catalog.json').write_text(json.dumps(catalog,indent=2))
symbols=sorted({t['contract']['symbol'] for t in selected});print('selected',len(selected),'contracts',len(symbols),flush=True)
client=_current_client();headers={'Authorization':load_config()['FYERS_ACCESS_TOKEN']};directory=OUT/'selected_history';directory.mkdir(exist_ok=True)
for i,symbol in enumerate(symbols):
 path=directory/(symbol.replace(':','_')+'.json')
 c=next(t['contract'] for t in selected if t['contract']['symbol']==symbol)
 first=min(str(datetime.fromtimestamp(t['at'],IST).date()) for t in selected if t['contract']['symbol']==symbol)
 last=min(c['expiry'],'2026-10-06')
 if path.exists():
  old=json.loads(path.read_text())['request']
  if old.get('range_from','9999')<=first and old.get('range_to','0000')>=last:continue
 params=dict(symbol=symbol,resolution='1',date_format='1',range_from=first,range_to=last)
 try:
  if c['source']=='current_master':result=client.history({**params,'cont_flag':0,'oi_flag':1})
  else:result=requests.get('https://api-t1.fyers.in/data/history/fno/expired/historical-data',params={**params,'include_oi':'1'},headers=headers,timeout=25).json()
  path.write_text(json.dumps(dict(request=params,response=result)))
  print(i+1,len(symbols),symbol,result.get('s'),list(result),len(result.get('candles',[])),flush=True)
 except Exception as e:print(symbol,type(e).__name__,flush=True)
 time.sleep(.4)
