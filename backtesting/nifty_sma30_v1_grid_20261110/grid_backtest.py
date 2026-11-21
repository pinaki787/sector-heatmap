"""Read-only October V1 grid trailing study; run from project root."""
import json,hashlib,math
from pathlib import Path
import pandas as pd,numpy as np
import vectorbt as vbt
import plotly.graph_objects as go
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'nifty_sma30_options_20261110'
rows=json.loads(Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']
rows+=json.loads((BASE/'raw/spot_oct24_31.json').read_text())['candles']
def frame(rows):
 d=pd.DataFrame([x[:6] for x in rows],columns=['epoch','open','high','low','close','volume'])
 d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata')
 assert not d.index.duplicated().any()
 return d.sort_index()
spot=frame(rows).between_time('09:15','15:29')
month=spot.loc['2026-10-01':'2026-10-31']
signals=pd.read_csv(BASE/'trades.csv')
for k in ['signal_time','entry_time']:signals[k]=pd.to_datetime(signals[k])
candidates={x['entry_time']:x for x in signals.to_dict('records')}
grids=pd.read_csv(ROOT/'causal_daily_grid.csv')
grids['available_at']=pd.to_datetime(grids.available_at)
gridbyday={x['day']:x for x in grids.to_dict('records')}
prices={}
for s in signals.symbol.unique():
 raw=json.loads((BASE/'raw'/('option_'+s.replace(':','_')+'.json')).read_text())
 prices[s]=frame(raw.get('candles',raw.get('data',{}).get('candles',[])))
LOT=65
def costs(p,buy):
 v=p*LOT;brokerage=20.;exchange=v*.000355299;sebi=v*.000001;ipft=v*.000000001;clearing=v*.00009
 gst=.18*(brokerage+exchange+sebi+ipft+clearing)
 return dict(brokerage=brokerage,exchange=exchange,sebi=sebi,ipft=ipft,clearing=clearing,gst=gst,stamp=v*.00003 if buy else 0.,stt=0. if buy else v*.0015)
def step(direction,stop,targets,reached,entry,lo,hi):
 # Old stop governs this whole bar. Confirm target touches at bar close;
 # an advanced stop first becomes active in the following minute.
 hit=lo<=stop if direction==1 else hi>=stop
 favorable=[i for i,x in enumerate(targets) if (hi>=x if direction==1 else lo<=x)]
 new_count=max([reached]+[i+1 for i in favorable])
 ambiguous=hit and new_count>reached
 if hit:return True,stop,reached,ambiguous
 new_stop=stop
 if new_count>reached:new_stop=entry if new_count==1 else targets[new_count-2]
 if direction==1:new_stop=max(stop,new_stop)
 else:new_stop=min(stop,new_stop)
 return False,new_stop,new_count,False
# Meaningful execution-rule checks, including mirrored PUT and an ambiguous bar.
assert step(1,90,[110,120],0,100,89,121)==(True,90,0,True)
assert step(1,90,[110,120],0,100,95,111)==(False,100,1,False)
assert step(-1,110,[90,80],0,100,89,105)==(False,100,1,False)
assert step(-1,110,[90,80],1,100,79,99)==(False,90,2,False)
assert step(1,90,[110,120,130],0,100,95,131)==(False,120,3,False)
trades=[];events=[];decisions=[];equity=[];active=None;cash=0.;blocked=None
for ts,row in month.iterrows():
 candidate=candidates.get(ts)
 was_held=active is not None
 if candidate and was_held:decisions.append(dict(time=ts,reason='signal_ignored_while_held',side=candidate['side']))
 if active and ts==active.get('pending_exit'):
  q=prices[active['symbol']].loc[ts];exitp=float(q.open);exitfees=costs(exitp,False)
  cash+=(exitp-active['entry_premium'])*LOT-sum(exitfees.values())
  done={k:v for k,v in active.items() if k not in ['targets','pending_exit','stop','direction']}
  done.update(exit_time=ts,exit_premium=exitp,exit_cost=sum(exitfees.values()),final_stop=active['stop'],targets_reached=active['reached'])
  done.update({k:active['entry_cost_components'][k]+exitfees[k] for k in exitfees})
  done.pop('entry_cost_components')
  done['gross_pnl']=(exitp-done['entry_premium'])*LOT
  done['costs']=done['entry_cost']+done['exit_cost'];done['net_pnl']=done['gross_pnl']-done['costs']
  trades.append(done);active=None
 if candidate and not was_held:
  g=gridbyday.get(str(ts.date()));reason=None
  if not g or g['available_at']>ts:reason='daily_grid_not_available'
  direction=1 if candidate['side']=='CE' else -1
  pos=spot.index.get_loc(candidate['signal_time'])
  previous=spot.iloc[pos-1]
  initial=float(previous.low if direction==1 else previous.high)
  entryspot=float(row.open)
  if reason is None and (initial>=entryspot if direction==1 else initial<=entryspot):reason='initial_stop_invalid_after_entry_gap'
  if g:
   centers=sorted([g['high']+n*g['span'] for n in range(1,11)]+[g['low']-n*g['span'] for n in range(1,11)])
   targets=[x for x in centers if x>entryspot] if direction==1 else [x for x in centers[::-1] if x<entryspot]
  else:targets=[]
  if reason is None and not targets:reason='no_favorable_center_within_T1_T10'
  q=prices[candidate['symbol']]
  if reason is None and (ts not in q.index or q.loc[ts,'volume']<=0):reason='unavailable_entry_premium'
  if reason:
   decisions.append(dict(time=ts,reason=reason,side=candidate['side']))
  else:
   p=float(q.loc[ts,'open']);fees=costs(p,True)
   active=dict(signal_time=candidate['signal_time'],entry_time=ts,symbol=candidate['symbol'],side=candidate['side'],expiry=candidate['expiry'],strike=candidate['strike'],quantity=LOT,direction=direction,entry_spot=entryspot,previous_candle_time=spot.index[pos-1],initial_stop=initial,stop=initial,grid_available_at=g['available_at'],grid_high=g['high'],grid_low=g['low'],grid_span=g['span'],targets=targets,reached=0,entry_premium=p,entry_cost=sum(fees.values()),entry_cost_components=fees)
   cash-=sum(fees.values())
   events.append(dict(time=ts,event='entry',symbol=active['symbol'],spot=entryspot,stop=initial,targets=json.dumps(targets)))
 # EOD is a scheduled known-in-advance order at 15:29 open, not an intrabar fill.
 if active and ts.strftime('%H:%M')=='15:29' and 'pending_exit' not in active:
  q=prices[active['symbol']].loc[ts]
  if q.volume<=0:raise RuntimeError('Unavailable EOD bar')
  exitp=float(q.open);exitfees=costs(exitp,False)
  cash+=(exitp-active['entry_premium'])*LOT-sum(exitfees.values())
  done={k:v for k,v in active.items() if k not in ['targets','pending_exit','stop','direction']}
  done.update(exit_time=ts,exit_premium=exitp,exit_cost=sum(exitfees.values()),final_stop=active['stop'],targets_reached=active['reached'],exit_reason='scheduled_15:29')
  done.update({k:active['entry_cost_components'][k]+exitfees[k] for k in exitfees});done.pop('entry_cost_components')
  done['gross_pnl']=(exitp-done['entry_premium'])*LOT;done['costs']=done['entry_cost']+done['exit_cost'];done['net_pnl']=done['gross_pnl']-done['costs'];trades.append(done);active=None
 if active and 'pending_exit' not in active:
  old=active['stop'];oldcount=active['reached']
  hit,newstop,reached,ambiguous=step(active['direction'],old,active['targets'],oldcount,active['entry_spot'],row.low,row.high)
  if hit:
   wanted=ts+pd.Timedelta(minutes=1)
   q=prices[active['symbol']]
   available=q[(q.index>=wanted)&(q.index.strftime('%Y-%m-%d')==str(ts.date()))&(q.index.strftime('%H:%M')<='15:29')&(q.volume>0)]
   if available.empty:raise RuntimeError('No next executable exit for '+str(ts))
   active['pending_exit']=available.index[0];active['exit_reason']='initial_stop' if oldcount==0 else 'trailing_stop'
   active['stop_trigger_bar']=ts;active['exit_delay_minutes']=(available.index[0]-wanted).total_seconds()/60
   events.append(dict(time=ts,event='stop_trigger',stop=old,same_bar_target_touch=ambiguous,execute_at=available.index[0],symbol=active['symbol']))
  elif reached>oldcount:
   active['stop']=newstop;active['reached']=reached
   events.append(dict(time=ts,event='trail_advance_after_close',prior_stop=old,stop=newstop,target_count=reached,effective_at=ts+pd.Timedelta(minutes=1),symbol=active['symbol']))
 mark=0.
 if active:
  q=prices[active['symbol']]
  if ts not in q.index:raise RuntimeError('Missing held-contract mark '+str(ts))
  mark=(q.loc[ts,'close']-active['entry_premium'])*LOT
 equity.append(dict(timestamp=ts,net_pnl=cash+mark))
assert active is None
t=pd.DataFrame(trades);eq=pd.DataFrame(equity).set_index('timestamp')
eq['drawdown_rupees']=eq.net_pnl-eq.net_pnl.cummax().clip(lower=0)
t.to_csv(ROOT/'grid_trades.csv',index=False);eq.to_csv(ROOT/'grid_equity.csv')
pd.DataFrame(events).to_csv(ROOT/'grid_events.csv',index=False);pd.DataFrame(decisions).to_csv(ROOT/'signal_decisions.csv',index=False)
assert abs(t.net_pnl.sum()-cash)<1e-6
n=len(t);p=np.array([t.entry_premium.values,t.exit_premium.values])
pf=vbt.Portfolio.from_orders(p,size=np.array([np.full(n,LOT),np.full(n,-LOT)]),price=p,fixed_fees=np.array([t.costs.values,np.zeros(n)]),init_cash=100000,min_size=LOT,size_granularity=LOT,raise_reject=True)
assert abs(pf.total_profit().sum()-cash)<1e-6
entry=pd.to_datetime(t.entry_time);exit=pd.to_datetime(t.exit_time)
assert (entry.dt.date==exit.dt.date).all()
assert (entry>=pd.to_datetime(t.grid_available_at)).all()
assert (pd.to_datetime(t.previous_candle_time)<pd.to_datetime(t.signal_time)).all()
assert ((pd.to_datetime(t.signal_time)-pd.to_datetime(t.previous_candle_time)).dt.total_seconds().eq(60) | (entry.dt.strftime('%H:%M')=='09:16')).all()
win=t.net_pnl[t.net_pnl>0].sum();loss=-t.net_pnl[t.net_pnl<0].sum()
summary=dict(status='COMPLETE',start=str(month.index[0]),end=str(month.index[-1]),sessions=20,trades=n,wins=int(t.net_pnl.gt(0).sum()),win_rate_pct=t.net_pnl.gt(0).mean()*100,profit_factor=win/loss,gross_pnl=t.gross_pnl.sum(),costs=t.costs.sum(),net_pnl=cash,max_drawdown_rupees=-eq.drawdown_rupees.min(),cost_breakdown={k:t[k].sum() for k in costs(100,True)},skipped_or_ignored=pd.Series([x['reason'] for x in decisions]).value_counts().to_dict(),stop_first_ambiguous_bars=sum(x.get('same_bar_target_touch',False) for x in events),trail_advancements=sum(x['event']=='trail_advance_after_close' for x in events),exit_reasons=t.exit_reason.value_counts().to_dict(),delayed_exit_bars=int(t.get('exit_delay_minutes',pd.Series([0])).fillna(0).gt(0).sum()),max_targets_reached=int(t.targets_reached.max()),quantity=LOT,vectorbt_terminal_pnl_verified=True,synthetic_rule_checks=5,source_sha256=hashlib.sha256(Path('sector-pulse-v1.pine').read_bytes()).hexdigest())
(ROOT/'grid_results.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
baseline=json.loads((BASE/'results.json').read_text())
compare=pd.DataFrame({'SMA30 flip baseline':{k:baseline[k] for k in ['trades','win_rate_pct','profit_factor','gross_pnl','costs','net_pnl','max_drawdown_rupees']},'V1 grid trail':{k:summary[k] for k in ['trades','win_rate_pct','profit_factor','gross_pnl','costs','net_pnl','max_drawdown_rupees']}})
compare.to_csv(ROOT/'comparison.csv')
fig=go.Figure();fig.add_trace(go.Scatter(x=eq.index,y=eq.net_pnl,name='Grid trail net P&L'))
be=pd.read_csv(BASE/'equity.csv');fig.add_trace(go.Scatter(x=be.timestamp,y=be.net_pnl,name='SMA30 flip baseline'))
fig.update_layout(template='plotly_dark',title='October 2026 SMA30 options: grid trail versus flip',yaxis_title='Net rupees')
fig.write_html(ROOT/'comparison.html',include_plotlyjs=True)
print(json.dumps(summary,indent=2,default=str));print(compare.to_string())

