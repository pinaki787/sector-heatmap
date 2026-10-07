import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from strategies.renko_supertrend.history import trade_history
OUT=Path(__file__).resolve().parent
s=json.loads((ROOT/'.private/renko-supertrend-state.json').read_text())
trades=trade_history(s['order_history'],s.get('position'))
results=[]
for t in trades:
 if not (t.get('underlying_symbol') or '').startswith('MCX:CRUDE'):continue
 r={k:t.get(k) for k in ('symbol','mode','entry_time','exit_time','end_time','entry_price','exit_price','entry_filled','exit_filled','remaining_quantity','realized_pnl','lot_size','quantity_multiplier','exposure_range')}
 r['symbol']=t['contract'];r['exit_reasons']=t['exit_reasons'];r['costs']=t['costs'];r['entry_config']=(t.get('entry_indicator_snapshot') or {}).get('settings');results.append(r)
 print(json.dumps({k:v for k,v in r.items() if k not in ('costs','entry_config','exposure_range')}))
(OUT/'journal_cases.json').write_text(json.dumps(results,indent=2))
print('count',len(results),'trade keys',list(trades[-1]) if trades else [])
