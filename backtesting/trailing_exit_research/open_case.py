"""Read-only open-position evidence; no runner or order mutations."""
import sys,json,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.fyers_execution import _current_client
OUT=Path(__file__).resolve().parent
s=json.loads((ROOT/'.private/renko-supertrend-state.json').read_text());p=s.get('position') or {}
now=time.time();print('current position present',bool(p))
keep={k:p.get(k) for k in ('symbol','entry_price','quantity','remaining_quantity','lots','lot_size','quantity_multiplier','opened_at','direction','entry_side','exit_requested','exit_reason','exposure_range','renko_trailing')}
if p:
 response=_current_client().depth(dict(symbol=p['symbol'],ohlcv_flag=1))
else:response=None
payload=dict(captured_at=datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata')).isoformat(),position=keep,quote_response=response,realized_run=s.get('realized_pnl'),config={k:s.get('config',{}).get(k) for k in ('mode','underlying','timeframe','trailing_enabled','ema_exit_enabled')},user_screen_report=dict(observed_at='2026-10-07 about 22:47 IST',symbol='MCX:CRUDEOIL26OCT8600PE',entry_premium=263.3,displayed_quantity=2,open_unrealized_before_costs=3880,realized_run_before_costs=120,total_run_before_costs=4000,after_costs_available=False,source='User-provided screen evidence; separate from current read-only probe.'))
(OUT/'open_case.json').write_text(json.dumps(payload,indent=2));print(json.dumps(keep));print('realized run',s.get('realized_pnl'),'quote status',response.get('s') if response else None)
