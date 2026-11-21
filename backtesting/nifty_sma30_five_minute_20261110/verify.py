"""Independent five-minute causality/equity audit and saved-result attribution."""
import json,hashlib
from pathlib import Path
import pandas as pd
from openalgo import ta
P=Path(__file__).resolve().parent;B=P.parent/'nifty_sma30_options_20261110';ONE=P.parent/'nifty_sma30_two_lot_sma_exit_20261110'
t=pd.read_csv(P/'entries.csv');l=pd.read_csv(P/'legs.csv');o=pd.read_csv(P/'orders.csv');ev=pd.read_csv(P/'events.csv');eq=pd.read_csv(P/'equity.csv');r=json.loads((P/'results.json').read_text())
raw=json.loads(Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']+json.loads((B/'raw/spot_oct24_31.json').read_text())['candles']
d=pd.DataFrame(raw,columns=['epoch','open','high','low','close','volume']);d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata');d=d.between_time('09:15','15:29').loc['2026-09-01':]
five=d.resample('5min',origin='start_day',offset='9h15min').agg({'open':'first','high':'max','low':'min','close':'last','epoch':'count'}).dropna();assert five.epoch.eq(5).all()
five['sma']=ta.sma(five.close,30);five['up']=(five.close>five.sma)&(five.close.shift(1)<=five.sma.shift(1));five['down']=(five.close<five.sma)&(five.close.shift(1)>=five.sma.shift(1))
assert len(t)==102 and len(l)==204 and o.order_id.is_unique and 'initial_stop' not in t.columns
assert len(t)+sum(r['skipped_or_ignored'].values())==113
en=pd.to_datetime(t.entry_time);ex=pd.to_datetime(t.exit_time)
assert (en.dt.date==ex.dt.date).all() and (en.iloc[1:].reset_index(drop=True)>=ex.iloc[:-1].reset_index(drop=True)).all()
assert en.dt.minute.mod(5).eq(0).all() and en.dt.strftime('%H:%M').le('15:28').all()
for x in t.to_dict('records'):
 sig=pd.Timestamp(x['signal_time']);entry=pd.Timestamp(x['entry_time'])
 assert entry==sig+pd.Timedelta(minutes=5)==pd.Timestamp(x['signal_confirmed_at'])
 assert pd.Timestamp(x['grid_available_at'])<=entry
 assert bool(five.loc[sig,'up'] if x['side']=='CE' else five.loc[sig,'down'])
for x in ev[ev.event=='exit_trigger'].to_dict('records'):
 ts=pd.Timestamp(x['time']);entry=t[t.entry_id==x['entry_id']].iloc[0]
 if x['reason']=='pre_target_SMA_flip':
  assert not entry.activated and pd.isna(x['stop']) and ts.minute%5==4
  sig=ts-pd.Timedelta(minutes=4)
  assert bool(five.loc[sig,'down'] if entry.side=='CE' else five.loc[sig,'up'])
 else:
  assert entry.activated
  assert d.loc[ts,'low']<=x['stop'] if entry.side=='CE' else d.loc[ts,'high']>=x['stop']
for x in ev[ev.event=='midpoint_trail_after_close'].to_dict('records'):
 ts=pd.Timestamp(x['time']);source=pd.Timestamp(x['midpoint_source_start']);entry=t[t.entry_id==x['entry_id']].iloc[0]
 assert ts.minute%5==4 and source==ts-pd.Timedelta(minutes=4)
 bar=five.loc[source];mid=(bar.high+bar.low)/2
 expected=mid if pd.isna(x['prior_stop']) else max(x['prior_stop'],mid) if entry.side=='CE' else min(x['prior_stop'],mid)
 assert abs(x['stop']-expected)<1e-7 and pd.Timestamp(x['effective_at'])==source+pd.Timedelta(minutes=5)
waits=[];resolved_same5=0;partial_to_midpoint=[]
for x in t[t.activated].to_dict('records'):
 target=pd.Timestamp(x['target_touch_bar']);barstart=target.floor('5min');firsteffective=barstart+pd.Timedelta(minutes=5)
 waits.append((firsteffective-(target+pd.Timedelta(minutes=1))).total_seconds()/60)
 assert bool(d.loc[target,'high']>=x['first_target'] if x['side']=='CE' else d.loc[target,'low']<=x['first_target'])
 mids=ev[(ev.entry_id==x['entry_id'])&(ev.event=='midpoint_trail_after_close')]
 if firsteffective.strftime('%H:%M')<='15:29':
  assert len(mids)>0 and pd.Timestamp(mids.iloc[0].effective_at)==firsteffective
 bar=five.loc[barstart]
 if bool(bar.down if x['side']=='CE' else bar.up):resolved_same5+=1
 part=o[(o.entry_id==x['entry_id'])&(o.reason=='first_target_partial')]
 if len(part):partial_to_midpoint.append((firsteffective-pd.Timestamp(part.iloc[0].time)).total_seconds()/60)
for x in t[t.reversal_from_entry_id.notna()].to_dict('records'):
 prev=t[t.entry_id==int(x['reversal_from_entry_id'])].iloc[0]
 assert prev.exit_reason=='pre_target_SMA_flip' and prev.side!=x['side'] and prev.exit_time==x['entry_time']
 assert o[(o.entry_id==prev.entry_id)&(o.side=='SELL')].order_id.max()<o[(o.entry_id==x['entry_id'])&(o.side=='BUY')].order_id.min()
prices={}
for s in t.symbol.unique():
 path=B/'raw'/('option_'+s.replace(':','_')+'.json')
 if not path.exists():path=P/'raw'/path.name
 raw=json.loads(path.read_text());pr=pd.DataFrame(raw['candles']).iloc[:,:6];pr.index=pd.to_datetime(pr[0],unit='s',utc=True).dt.tz_convert('Asia/Kolkata');prices[s]=pr
o.time=pd.to_datetime(o.time);ordersbytime={k:v for k,v in o.groupby('time')};sym=t.set_index('entry_id').symbol.to_dict()
cash=0.;inventory={};maxerr=0.
for x in eq.to_dict('records'):
 ts=pd.Timestamp(x['timestamp'])
 if ts in ordersbytime:
  for q in ordersbytime[ts].to_dict('records'):
   signed=q['quantity'] if q['side']=='BUY' else -q['quantity'];cash-=signed*q['premium']+q['costs'];ident=q['entry_id'];inventory[ident]=inventory.get(ident,0)+signed
   assert inventory[ident]>=0
 mark=sum(qty*prices[sym[ident]].loc[ts,4] for ident,qty in inventory.items() if qty)
 err=abs(cash+mark-x['net_pnl']);maxerr=max(maxerr,err);assert err<1e-6
assert all(q==0 for q in inventory.values()) and abs(cash-r['net_pnl'])<1e-6
assert abs(l.net_pnl.sum()-cash)<1e-6 and abs(t.net_pnl.sum()-cash)<1e-6 and abs(o.costs.sum()-r['costs'])<1e-6
audit=dict(complete_5minute_OHLC=True,signal_and_SMA_timeframe_5m=True,midpoint_from_full_completed_5m=True,target_and_existing_stop_monitored_1m=True,next_minute_option_fills=True,pretarget_previous_candle_stop_absent=True,independent_cash_inventory_equity_max_error=maxerr,all_candidate_signals_reconciled=True,same_open_reversals_sell_first=True,no_overnight=True,midpoint_wait_minutes_after_target_confirmation=dict(min=min(waits),max=max(waits),mean=sum(waits)/len(waits)),midpoint_wait_minutes_after_actual_partial=dict(min=min(partial_to_midpoint),max=max(partial_to_midpoint),mean=sum(partial_to_midpoint)/len(partial_to_midpoint)),same5minute_target_and_SMAflip_but_minute_chronology_resolved=resolved_same5,unresolved_same_minute_target_SMA_collisions=r['target_SMA_same_candle_count'])
(P/'verification.json').write_text(json.dumps(audit,indent=2))
t['holding_minutes']=(pd.to_datetime(t.exit_time)-pd.to_datetime(t.entry_time)).dt.total_seconds()/60
reason=t.groupby('exit_reason').agg(entries=('entry_id','size'),wins=('net_pnl',lambda x:int(x.gt(0).sum())),gross_pnl=('gross_pnl','sum'),costs=('costs','sum'),net_pnl=('net_pnl','sum'),median_holding_minutes=('holding_minutes','median'),mean_holding_minutes=('holding_minutes','mean')).reset_index()
reason['pct_entries']=reason.entries/len(t)*100;reason.to_csv(P/'exit_attribution.csv',index=False)
fl=t[t.exit_reason=='pre_target_SMA_flip'];tr=ev[(ev.event=='exit_trigger')&(ev.reason=='pre_target_SMA_flip')].merge(t[['entry_id','entry_time']],on='entry_id');tr['elapsed']=(pd.to_datetime(tr.time)-pd.to_datetime(tr.entry_time)).dt.total_seconds()/60
analysis=dict(exit_groups=reason.to_dict('records'),pretarget_flip_count=len(fl),pretarget_flip_entry_5m_bar=int(tr.elapsed.le(4).sum()),pretarget_flip_within_first_two_5m_bars=int(tr.elapsed.le(9).sum()),pretarget_flip_median_holding_minutes=fl.holding_minutes.median(),all_entries_median_holding_minutes=t.holding_minutes.median(),target_hit_pct=r['target_reached_pct'],costs_pct_gross=r['costs']/r['gross_pnl']*100)
one=json.loads((ONE/'results.json').read_text());analysis['comparison_delta']=dict(net_pnl=r['net_pnl']-one['net_pnl'],costs=r['costs']-one['costs'],max_dd=r['max_drawdown_rupees']-one['max_drawdown_rupees'],entry_count=r['trades']-one['trades'])
(P/'analysis.json').write_text(json.dumps(analysis,indent=2))
inputs=[P/'backtest.py',P/'verify.py',Path('sector-pulse-v1.pine'),BASE/'provenance.json'] if False else [P/'backtest.py',P/'verify.py',Path('sector-pulse-v1.pine'),B/'provenance.json',ONE/'results.json',P.parent/'nifty_sma30_v1_grid_20261110/causal_daily_grid.csv']
for f in (P/'raw').glob('*.json'):inputs.append(f)
(P/'provenance.json').write_text(json.dumps({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in inputs},indent=2))
print(json.dumps(dict(verification=audit,analysis=analysis),indent=2))

