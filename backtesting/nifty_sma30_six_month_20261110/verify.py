"""Read-only validation, coverage audit, monthly attribution and fixed-path execution sensitivity."""
import json,hashlib,math,functools,os,time
from pathlib import Path
import pandas as pd,numpy as np
from openalgo import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
P=Path(__file__).resolve().parent;B=P.parent/'nifty_sma30_options_20261110';OCT=P.parent/'nifty_sma30_five_minute_20261110'
t=pd.read_csv(P/'entries.csv');l=pd.read_csv(P/'legs.csv');o=pd.read_csv(P/'orders.csv');ev=pd.read_csv(P/'events.csv');eq=pd.read_csv(P/'equity.csv');r=json.loads((P/'results.json').read_text());candidates=pd.read_csv(P/'candidate_signals.csv')
raw=json.loads(Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']+json.loads((B/'raw/spot_oct24_31.json').read_text())['candles']
spot=pd.DataFrame(raw,columns=['epoch','open','high','low','close','volume']);spot.index=pd.to_datetime(spot.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata');spot=spot.between_time('09:15','15:29').loc['2026-04-01':]
five=spot.resample('5min',origin='start_day',offset='9h15min').agg({'open':'first','high':'max','low':'min','close':'last','epoch':'count'}).dropna();assert five.epoch.eq(5).all()
five['sma']=ta.sma(five.close,30);five['up']=(five.close>five.sma)&(five.close.shift(1)<=five.sma.shift(1));five['down']=(five.close<five.sma)&(five.close.shift(1)>=five.sma.shift(1))
holidays={'2026-05-01','2026-05-28','2026-06-26','2026-09-14','2026-10-02','2026-10-20'}
expected={str(x.date()) for x in pd.bdate_range('2026-05-01','2026-10-31') if str(x.date()) not in holidays}
actual={str(x) for x in spot.loc['2026-05-01':'2026-10-31'].index.date}
assert expected==actual and len(expected)==125
assert spot.loc['2026-05-01':'2026-10-31'].groupby(lambda x:x.date()).size().eq(375).all()
en=pd.to_datetime(t.entry_time);ex=pd.to_datetime(t.exit_time)
assert len(t)==721 and len(l)==1442 and o.order_id.is_unique
assert 'initial_stop' not in t.columns and not o.reason.eq('initial_stop').any()
assert (en.dt.date==ex.dt.date).all() and (en.iloc[1:].reset_index(drop=True)>=ex.iloc[:-1].reset_index(drop=True)).all()
assert (en-pd.to_datetime(t.signal_time)).dt.total_seconds().eq(300).all()
assert en.dt.minute.mod(5).eq(0).all() and en.dt.strftime('%H:%M').le('15:28').all()
assert (en>=pd.to_datetime(t.grid_available_at)).all()
assert len(t)+sum(r['skipped_or_ignored'].values())==len(candidates)==815
for x in t.to_dict('records'):
 s=pd.Timestamp(x['signal_time'])
 assert bool(five.loc[s,'up'] if x['side']=='CE' else five.loc[s,'down'])
 assert x['quantity']==130
for x in ev[ev.event=='exit_trigger'].to_dict('records'):
 ts=pd.Timestamp(x['time']);ent=t[t.entry_id==x['entry_id']].iloc[0]
 if x['reason']=='pre_target_SMA_flip':
  assert not ent.activated and pd.isna(x['stop']) and ts.minute%5==4
  f=five.loc[ts-pd.Timedelta(minutes=4)];assert bool(f.down if ent.side=='CE' else f.up)
 else:
  assert ent.activated
  assert spot.loc[ts,'low']<=x['stop'] if ent.side=='CE' else spot.loc[ts,'high']>=x['stop']
for x in ev[ev.event=='midpoint_trail_after_close'].to_dict('records'):
 ts=pd.Timestamp(x['time']);source=pd.Timestamp(x['midpoint_source_start']);ent=t[t.entry_id==x['entry_id']].iloc[0]
 assert source==ts-pd.Timedelta(minutes=4) and ts.minute%5==4
 f=five.loc[source];mid=(f.high+f.low)/2
 expected_mid=mid if pd.isna(x['prior_stop']) else max(x['prior_stop'],mid) if ent.side=='CE' else min(x['prior_stop'],mid)
 assert abs(x['stop']-expected_mid)<1e-7 and pd.Timestamp(x['effective_at'])==source+pd.Timedelta(minutes=5)
for x in t[t.reversal_from_entry_id.notna()].to_dict('records'):
 prev=t[t.entry_id==int(x['reversal_from_entry_id'])].iloc[0]
 assert prev.exit_reason=='pre_target_SMA_flip' and prev.side!=x['side'] and prev.exit_time==x['entry_time']
 assert o[(o.entry_id==prev.entry_id)&(o.side=='SELL')].order_id.max()<o[(o.entry_id==x['entry_id'])&(o.side=='BUY')].order_id.min()
sources=json.loads((P/'data_sources.json').read_text());prices={};input_manifest={};invalid_rows=0;outside_rows=0;gcdvol={}
for sym,path in sources.items():
 raw=json.loads(Path(path).read_text());rows=raw.get('candles',raw.get('data',{}).get('candles',[]));d=pd.DataFrame([x[:6] for x in rows],columns=['epoch','open','high','low','close','volume'])
 d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata');assert not d.index.duplicated().any()
 valid=(d.low<=d[['open','close']].min(axis=1))&(d.high>=d[['open','close']].max(axis=1))&d[['open','high','low','close']].gt(0).all(axis=1)
 invalid_rows+=int((~valid).sum());prices[sym]=d
 reg=d.between_time('09:15','15:29');outside_rows+=len(d)-len(reg)
 for month,x in reg.groupby(reg.index.strftime('%Y-%m')):
  values=x.volume[x.volume>0].astype(int)
  if len(values):gcdvol[month]=math.gcd(gcdvol.get(month,0),functools.reduce(math.gcd,values))
 input_manifest[path]=dict(sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),bars=len(d),regular_bars=len(reg),invalid_OHLC=int((~valid).sum()))
# All used OHLC/premiums must be valid; outside/unconsumed input anomalies remain disclosed.
assert invalid_rows==0,invalid_rows
o.time=pd.to_datetime(o.time);bytime={k:v for k,v in o.groupby('time')};sym=t.set_index('entry_id').symbol.to_dict()
cash=0.;inventory={};maxerr=0.
for x in eq.to_dict('records'):
 ts=pd.Timestamp(x['timestamp'])
 if ts in bytime:
  for order in bytime[ts].to_dict('records'):
   sign=1 if order['side']=='BUY' else -1;qty=sign*order['quantity'];ident=order['entry_id']
   assert prices[sym[ident]].loc[ts,'volume']>0
   assert abs(prices[sym[ident]].loc[ts,'open']-order['premium'])<1e-7
   cash-=qty*order['premium']+order['costs'];inventory[ident]=inventory.get(ident,0)+qty;assert inventory[ident]>=0
 mark=sum(qty*prices[sym[ident]].loc[ts,'close'] for ident,qty in inventory.items() if qty)
 err=abs(cash+mark-x['net_pnl']);maxerr=max(maxerr,err);assert err<1e-6
assert all(q==0 for q in inventory.values()) and abs(cash-r['net_pnl'])<1e-6
assert abs(t.net_pnl.sum()-cash)<1e-6 and abs(l.net_pnl.sum()-cash)<1e-6 and abs(o.costs.sum()-r['costs'])<1e-6
# Strict unchanged entry policy: distinguish missing bars from zero-volume bars.
dec=pd.read_csv(P/'signal_decisions.csv');exclusions=[]
for x in dec[dec.reason=='unavailable_entry_premium'].to_dict('records'):
 ts=pd.Timestamp(x['time']);candidate=candidates[pd.to_datetime(candidates.entry_time)==ts].iloc[0];pr=prices[candidate.symbol]
 exists=ts in pr.index;after=pr[(pr.index>ts)&(pr.index.strftime('%Y-%m-%d')==str(ts.date()))&(pr.index.strftime('%H:%M')<='15:28')&(pr.volume>0)]
 exclusions.append(dict(signal_time=candidate.signal_time,entry_time=str(ts),symbol=candidate.symbol,bar_present=exists,volume=float(pr.loc[ts,'volume']) if exists else None,reason='zero_volume_entry_candle' if exists else 'missing_entry_candle',next_positive_bar=str(after.index[0]) if len(after) else None))
pd.DataFrame(exclusions).to_csv(P/'execution_exclusions.csv',index=False)
delayed=ev[ev.extra_delay_minutes.fillna(0)>0];delayed.to_csv(P/'delayed_exit_events.csv',index=False)
# Exact October overlap: ignore global entry IDs but compare prices/rules/P&L.
octnew=t[en.dt.strftime('%Y-%m')=='2026-10'].reset_index(drop=True);octold=pd.read_csv(OCT/'entries.csv')
assert len(octnew)==len(octold)==102
for col in ['signal_time','entry_time','symbol','side','expiry','strike','exit_time','exit_reason','activated','partial_booked']:
 assert octnew[col].astype(str).equals(octold[col].astype(str)),col
for col in ['entry_premium','entry_cost','first_target','stop','gross_pnl','costs','net_pnl']:
 assert np.allclose(octnew[col].astype(float),octold[col].astype(float),rtol=0,atol=1e-7,equal_nan=True),col
# Monthly figures and drawdown reset at each month's initial flat equity.
t['month']=en.dt.strftime('%Y-%m');t['holding_minutes']=(ex-en).dt.total_seconds()/60
eq.timestamp=pd.to_datetime(eq.timestamp);eq['month']=eq.timestamp.dt.strftime('%Y-%m')
def metric(d):
 gain=d.net_pnl[d.net_pnl>0].sum();loss=-d.net_pnl[d.net_pnl<0].sum()
 return dict(entries=len(d),wins=int(d.net_pnl.gt(0).sum()),win_rate_pct=d.net_pnl.gt(0).mean()*100,profit_factor=gain/loss if loss else None,gross_pnl=d.gross_pnl.sum(),costs=d.costs.sum(),net_pnl=d.net_pnl.sum(),target_hits=int(d.activated.sum()),target_hit_pct=d.activated.mean()*100)
monthly=[]
for month,d in t.groupby('month'):
 e=eq[eq.month==month];net=e.net_pnl-e.net_pnl.iloc[0];dd=net-net.cummax().clip(lower=0)
 m=dict(month=month,sessions=len({x.date() for x in e.timestamp}),**metric(d),max_drawdown_rupees=float(-dd.min()),partial_exits=int(o[(o.reason=='first_target_partial')&(o.time.dt.strftime('%Y-%m')==month)].shape[0]))
 monthly.append(m)
monthly=pd.DataFrame(monthly);monthly.to_csv(P/'monthly_results.csv',index=False)
groups=t.groupby('exit_reason').agg(entries=('entry_id','size'),gross_pnl=('gross_pnl','sum'),costs=('costs','sum'),net_pnl=('net_pnl','sum')).reset_index();groups.to_csv(P/'exit_attribution.csv',index=False)
t['day']=en.dt.strftime('%Y-%m-%d');daily=t.groupby('day').net_pnl.sum().reset_index();daily.to_csv(P/'daily_results.csv',index=False)
# Cost schedule sensitivity on unchanged fills/path; no optimization or signal retest.
def cost(p,qty,buy):
 v=p*qty;taxable=20+v*(.000355299+.00009+.000001+.000000001)
 return taxable*1.18+v*(.00003 if buy else .0015)
def slipcase(delta):
 altered=o.copy();altered['new_premium']=np.where(altered.side=='BUY',altered.premium+delta,np.maximum(0,altered.premium-delta))
 altered['new_cost']=[cost(p,q,s=='BUY') for p,q,s in zip(altered.new_premium,altered.quantity,altered.side)]
 altered['gross_flow']=np.where(altered.side=='BUY',-1,1)*altered.quantity*altered.new_premium
 per=altered.groupby('entry_id').agg(gross=('gross_flow','sum'),costs=('new_cost','sum'));per['net_pnl']=per.gross-per.costs
 changes=altered.gross_flow-altered.new_cost-(np.where(altered.side=='BUY',-1,1)*altered.quantity*altered.premium-altered.costs)
 changes=pd.DataFrame({'time':altered.time,'change':changes}).groupby('time').change.sum()
 e=eq.net_pnl.to_numpy()+changes.reindex(pd.DatetimeIndex(eq.timestamp),fill_value=0).cumsum().to_numpy()
 peak=np.maximum.accumulate(np.maximum(e,0));dd=np.max(peak-e)
 loss=-per.net_pnl[per.net_pnl<0].sum()
 return dict(adverse_premium_points_each_fill=delta,gross_pnl=per.gross.sum(),costs=per.costs.sum(),net_pnl=per.net_pnl.sum(),win_rate_pct=per.net_pnl.gt(0).mean()*100,profit_factor=per.net_pnl[per.net_pnl>0].sum()/loss,max_drawdown_rupees=dd)
slippage=pd.DataFrame([slipcase(x) for x in [0,.05,.10,.25,.50,1.0]]);assert abs(slippage.iloc[0].net_pnl-r['net_pnl'])<1e-6;slippage.to_csv(P/'slippage_sensitivity.csv',index=False)
analysis=dict(overall=metric(t),max_drawdown_rupees=r['max_drawdown_rupees'],profitable_months=int(monthly.net_pnl.gt(0).sum()),losing_months=int(monthly.net_pnl.lt(0).sum()),profitable_days=int(daily.net_pnl.gt(0).sum()),losing_days=int(daily.net_pnl.lt(0).sum()),best_month=monthly.nlargest(1,'net_pnl').iloc[0].to_dict(),worst_month=monthly.nsmallest(1,'net_pnl').iloc[0].to_dict(),best_5_days_net=daily.nlargest(5,'net_pnl').net_pnl.sum(),remaining_days_without_best_5_net=r['net_pnl']-daily.nlargest(5,'net_pnl').net_pnl.sum(),costs_pct_gross=r['costs']/r['gross_pnl']*100,average_net_winner=t.net_pnl[t.net_pnl>0].mean(),average_net_loser=t.net_pnl[t.net_pnl<0].mean(),execution_exclusions=exclusions,delayed_exits=delayed.to_dict('records'),monthly=monthly.to_dict('records'),exit_attribution=groups.to_dict('records'),slippage_sensitivity=slippage.to_dict('records'))
(P/'analysis.json').write_text(json.dumps(analysis,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
coverage=dict(requested_start='2026-05-01',requested_end='2026-10-31',actual_first='2026-05-04',actual_last='2026-10-30',expected_regular_sessions=125,observed_regular_sessions=125,missing_sessions=[],extra_sessions=[],spot_regular_minutes=len(eq),spot_five_minute_candles=len(eq)//5,contracts_loaded=len(prices),execution_exclusions=exclusions,extra_delayed_exit_events=len(delayed),invalid_option_OHLC_rows=invalid_rows,option_outside_session_rows_retained_not_executed=outside_rows,monthly_volume_gcd_units=gcdvol,calendar_source='https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf',lot_size=65,lot_size_source='https://fyers.in/notice-board/revision-in-index-derivatives-contracts-lot-size',lot_size_note='Published transition to65 for weekly/monthly January2026-and-later expiries; raw traded-volume GCD is corroboration, not the lot-size definition.',NSE_monthly_contract_file_probe='Remote read timed out; published exchange/broker transition schedule used rather than assuming current lot size.')
(P/'coverage.json').write_text(json.dumps(coverage,indent=2))
verification=dict(status='PASS_WITH_DISCLOSED_EXECUTION_EXCLUSIONS',calendar_sessions_match=True,completed_5m_signal_and_midpoint_checks=True,minute_equity_independent_max_error=maxerr,no_previous_candle_touch_stop=True,all_order_premiums_match_real_broker_opens=True,all_executed_order_bars_positive_volume=True,all_signals_reconciled=True,no_overlapping_or_overnight_inventory=True,partial_legs_and_actual_order_fees_reconcile=True,October_102_trades_all_fields_and_PnL_match=True,October_net_pnl=float(octnew.net_pnl.sum()),vectorbt_terminal_verified=r['vectorbt_terminal_pnl_verified'])
(P/'verification.json').write_text(json.dumps(verification,indent=2))
(P/'input_manifest.json').write_text(json.dumps(input_manifest,indent=2))
inputs=[P/'backtest.py',P/'verify.py',Path('sector-pulse-v1.pine'),OCT/'results.json',OCT/'entries.csv',B/'raw/spot_oct24_31.json',Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/manifest.json')]
(P/'provenance.json').write_text(json.dumps({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in inputs},indent=2))
fig=make_subplots(rows=2,cols=1,subplot_titles=['Six-month net marked option P&L','Monthly net P&L'])
fig.add_trace(go.Scatter(x=eq.timestamp,y=eq.net_pnl,name='Net rupees'),row=1,col=1)
fig.add_trace(go.Bar(x=monthly.month,y=monthly.net_pnl,name='Monthly net',marker_color=['#37b98d' if x>0 else '#e16b6b' for x in monthly.net_pnl]),row=2,col=1)
fig.update_layout(template='plotly_dark',title='Unchanged5m SMA30 two-lot strategy: May–October2026',height=800);fig.write_html(P/'comparison.html',include_plotlyjs=True)
monthly.to_csv(P/'comparison.csv',index=False)
status=json.loads((P/'job_status.json').read_text());status.update(status='VERIFIED_COMPLETE_WITH_EXECUTION_EXCLUSIONS',stage='verified',verified_epoch=time.time(),verification_pid=os.getpid());(P/'job_status.json').write_text(json.dumps(status,indent=2))
print(json.dumps(dict(verification=verification,coverage=coverage,analysis=analysis),indent=2,default=str))

