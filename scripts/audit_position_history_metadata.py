"""Read-only exact-contract historical valuation evidence, no broker API calls."""
import csv,json,time
from pathlib import Path
import requests
root=Path(__file__).resolve().parents[1]
state=json.loads((root/'.private/ema-crossover-state.json').read_text())
result={};sources={}
for symbol in sorted({r['symbol'] for r in state.get('order_history',[])}):
 segment='MCX_COM' if symbol.startswith('MCX:') else symbol.split(':')[0]+'_FO'
 if segment not in sources:
  response=requests.get(f'https://public.fyers.in/sym_details/{segment}_sym_master.json',timeout=15);response.raise_for_status()
  sources[segment]=response.json()
 record=sources[segment].get(symbol,{})
 path=root/'.private/ema-band-masters'/f'{segment}.csv'
 row=next((r for r in csv.reader(path.open()) if len(r)>16 and r[9]==symbol),None)
 if not row:continue
 try:
  if record.get('symTicker')!=symbol or str(record.get('fyToken'))!=row[0] or float(record['minLotSize'])!=float(row[3]) or float(record['expiryDate'])!=float(row[8]) or record['optType']!=row[16] or float(record['strikePrice'])!=float(row[15]):continue
  lot,mult=float(record['minLotSize']),float(record['qtyMultiplier'])
  if lot<=0 or mult<=0:continue
  result[symbol]=dict(lot_size=lot,quantity_multiplier=mult,verified_at=time.time(),source=f'https://public.fyers.in/sym_details/{segment}_sym_master.json')
 except (ValueError,TypeError,KeyError):continue
(root/'output/position-history-valuation-evidence.json').write_text(json.dumps(result,indent=2))
(root/'position-history-metadata.js').write_text('/* Read-only frozen exact-contract JSON/CSV valuation audit; 2026-10-01. */\nwindow.PositionHistoryMetadata='+json.dumps(result)+';\n')
print(json.dumps(result,indent=2))
