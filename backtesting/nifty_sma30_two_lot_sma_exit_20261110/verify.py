"""Independent read-only checks of corrected study and collision sensitivity."""
import json,hashlib
from pathlib import Path
import pandas as pd
from openalgo import ta
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'nifty_sma30_options_20261110'
rows=json.loads(Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']+json.loads((BASE/'raw/spot_oct24_31.json').read_text())['candles']
spot=pd.DataFrame(rows,columns=['epoch','open','high','low','close','volume']);spot.index=pd.to_datetime(spot.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata')
spot=spot.between_time('09:15','15:29');spot['sma']=ta.sma(spot.close,30)
spot['up']=(spot.close>spot.sma)&(spot.close.shift(1)<=spot.sma.shift(1));spot['down']=(spot.close<spot.sma)&(spot.close.shift(1)>=spot.sma.shift(1))
all_audits={}
for p in [ROOT,ROOT/'sensitivity_flip_priority']:
 t=pd.read_csv(p/'entries.csv');l=pd.read_csv(p/'legs.csv');o=pd.read_csv(p/'orders.csv');ev=pd.read_csv(p/'events.csv');eq=pd.read_csv(p/'equity.csv');r=json.loads((p/'results.json').read_text())
 assert 'initial_stop' not in t.columns and not o.reason.eq('initial_stop').any()
 assert len(l)==2*len(t) and o.order_id.is_unique
 assert o[o.side=='BUY'].quantity.eq(130).all()
 assert l.groupby('entry_id').quantity.sum().eq(130).all()
 en=pd.to_datetime(t.entry_time);ex=pd.to_datetime(t.exit_time)
 assert (en.iloc[1:].reset_index(drop=True)>=ex.iloc[:-1].reset_index(drop=True)).all()
 assert (en.dt.date==ex.dt.date).all()
 assert (en>=pd.to_datetime(t.grid_available_at)).all()
 assert (en-pd.to_datetime(t.signal_time)).dt.total_seconds().eq(60).all()
 assert len(t)+sum(r['skipped_or_ignored'].values())==657
 for x in ev[ev.event=='exit_trigger'].to_dict('records'):
  bar=spot.loc[pd.Timestamp(x['time'])];ent=t[t.entry_id==x['entry_id']].iloc[0]
  if x['reason']=='pre_target_SMA_flip':
   assert not ent.activated and pd.isna(x['stop'])
   assert bool(bar.down if ent.side=='CE' else bar.up)
   assert bar.close<bar.sma if ent.side=='CE' else bar.close>bar.sma
  else:
   assert ent.activated
   assert bar.low<=x['stop'] if ent.side=='CE' else bar.high>=x['stop']
 for x in ev[ev.event=='midpoint_trail_after_close'].to_dict('records'):
  ent=t[t.entry_id==x['entry_id']].iloc[0];bar=spot.loc[pd.Timestamp(x['time'])]
  midpoint=(bar.high+bar.low)/2
  expected=midpoint if pd.isna(x['prior_stop']) else max(x['prior_stop'],midpoint) if ent.side=='CE' else min(x['prior_stop'],midpoint)
  assert abs(x['stop']-expected)<1e-7
  assert pd.Timestamp(x['effective_at'])==pd.Timestamp(x['time'])+pd.Timedelta(minutes=1)
 for x in t[t.reversal_from_entry_id.notna()].to_dict('records'):
  prev=t[t.entry_id==int(x['reversal_from_entry_id'])].iloc[0]
  assert prev.exit_reason=='pre_target_SMA_flip' and prev.side!=x['side'] and prev.exit_time==x['entry_time']
  oldsell=o[(o.entry_id==prev.entry_id)&(o.side=='SELL')].iloc[-1]
  newbuy=o[(o.entry_id==x['entry_id'])&(o.side=='BUY')].iloc[0]
  assert oldsell.order_id<newbuy.order_id
 prices={}
 for s in t.symbol.unique():
  raw=json.loads((BASE/'raw'/('option_'+s.replace(':','_')+'.json')).read_text());d=pd.DataFrame(raw['candles']).iloc[:,:6]
  d.index=pd.to_datetime(d[0],unit='s',utc=True).dt.tz_convert('Asia/Kolkata');prices[s]=d
 o.time=pd.to_datetime(o.time);bytime={k:v for k,v in o.groupby('time')}
 sym=t.set_index('entry_id').symbol.to_dict();cash=0.;inventory={};maxerr=0.
 for x in eq.to_dict('records'):
  ts=pd.Timestamp(x['timestamp'])
  if ts in bytime:
   for order in bytime[ts].to_dict('records'):
    signed=order['quantity'] if order['side']=='BUY' else -order['quantity']
    cash-=signed*order['premium']+order['costs'];ident=order['entry_id'];inventory[ident]=inventory.get(ident,0)+signed
    assert inventory[ident]>=0
  mark=sum(qty*float(prices[sym[ident]].loc[ts,4]) for ident,qty in inventory.items() if qty)
  err=abs(cash+mark-x['net_pnl']);maxerr=max(maxerr,err);assert err<1e-6
 assert all(qty==0 for qty in inventory.values())
 assert abs(cash-r['net_pnl'])<1e-6 and abs(l.net_pnl.sum()-cash)<1e-6 and abs(t.net_pnl.sum()-cash)<1e-6
 assert abs(o.costs.sum()-r['costs'])<1e-6
 terminal=t.groupby('exit_reason').agg(entries=('entry_id','size'),gross_pnl=('gross_pnl','sum'),costs=('costs','sum'),net_pnl=('net_pnl','sum')).reset_index()
 terminal['pct_entries']=terminal.entries/len(t)*100;terminal.to_csv(p/'exit_reason_summary.csv',index=False)
 legsummary=l.groupby('exit_reason').agg(legs=('leg','size'),gross_pnl=('gross_pnl','sum'),costs=('costs','sum'),net_pnl=('net_pnl','sum')).reset_index();legsummary.to_csv(p/'leg_exit_summary.csv',index=False)
 audit=dict(no_previous_candle_touch_stop=True,completed_opposite_SMA_flip_checked=True,midpoint_next_bar_and_monotonic_checked=True,reversals_sell_before_buy_checked=True,all_signals_reconciled=True,no_overnight=True,independent_cash_inventory_max_error=maxerr,whole_entry_and_leg_PnL_reconciles=True,exit_breakdown=terminal.to_dict('records'),leg_exit_breakdown=legsummary.to_dict('records'),target_reached=int(t.activated.sum()),executed_unit_sides=int(o.quantity.sum()))
 (p/'verification.json').write_text(json.dumps(audit,indent=2));all_audits[p.name]=audit
r=json.loads((ROOT/'results.json').read_text());s=json.loads((ROOT/'sensitivity_flip_priority/results.json').read_text())
sensitivity={key:{'target_before_close_SMA':r[key],'conservative_close_flip_override':s[key]} for key in ['trades','win_rate_pct','profit_factor','gross_pnl','costs','net_pnl','max_drawdown_rupees','partial_exits','same_open_reversals','target_SMA_same_candle_count']}
(ROOT/'collision_sensitivity.json').write_text(json.dumps(sensitivity,indent=2))
inputs=[ROOT/'backtest.py',ROOT/'verify.py',Path('sector-pulse-v1.pine'),BASE/'provenance.json',BASE/'results.json',BASE/'trades.csv',ROOT.parent/'nifty_sma30_v1_grid_20261110/causal_daily_grid.csv',ROOT.parent/'nifty_sma30_two_lot_midpoint_20261110/results.json']
(ROOT/'provenance.json').write_text(json.dumps({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in inputs},indent=2))
print(json.dumps(dict(verification=all_audits,sensitivity=sensitivity),indent=2))

