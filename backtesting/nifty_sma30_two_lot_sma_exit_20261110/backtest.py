"""Corrected two-lot pre-target SMA flip, then partial and midpoint trail; read-only."""
import json,hashlib,argparse
from openalgo import ta
from pathlib import Path
import pandas as pd,numpy as np
import vectorbt as vbt
import plotly.graph_objects as go
STUDY=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--conflict-priority',choices=['target','flip'],default='target');args=parser.parse_args()
ROOT=STUDY if args.conflict_priority=='target' else STUDY/'sensitivity_flip_priority';ROOT.mkdir(exist_ok=True)
BASE=STUDY.parent/'nifty_sma30_options_20261110'
GRID=STUDY.parent/'nifty_sma30_v1_grid_20261110'
rows=json.loads(Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']+json.loads((BASE/'raw/spot_oct24_31.json').read_text())['candles']
def frame(rows):
 d=pd.DataFrame([x[:6] for x in rows],columns=['epoch','open','high','low','close','volume'])
 d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata')
 assert not d.index.duplicated().any()
 return d.sort_index()
spot=frame(rows).between_time('09:15','15:29')
spot['sma30']=ta.sma(spot.close,30)
spot['cross_up']=(spot.close>spot.sma30)&(spot.close.shift(1)<=spot.sma30.shift(1))
spot['cross_down']=(spot.close<spot.sma30)&(spot.close.shift(1)>=spot.sma30.shift(1))
month=spot.loc['2026-10-01':'2026-10-31']
signals=pd.read_csv(BASE/'trades.csv')
for k in ['signal_time','entry_time']:signals[k]=pd.to_datetime(signals[k])
candidates={x['entry_time']:x for x in signals.to_dict('records')}
grids=pd.read_csv(GRID/'causal_daily_grid.csv');grids.available_at=pd.to_datetime(grids.available_at)
gridbyday={x['day']:x for x in grids.to_dict('records')}
prices={}
for s in signals.symbol.unique():
 r=json.loads((BASE/'raw'/('option_'+s.replace(':','_')+'.json')).read_text())
 prices[s]=frame(r.get('candles',r.get('data',{}).get('candles',[])))
LOT=65
def costs(p,qty,buy):
 v=p*qty;brokerage=20.;exchange=v*.000355299;sebi=v*.000001;ipft=v*.000000001;clearing=v*.00009
 gst=.18*(brokerage+exchange+sebi+ipft+clearing)
 return dict(brokerage=brokerage,exchange=exchange,sebi=sebi,ipft=ipft,clearing=clearing,gst=gst,stamp=v*.00003 if buy else 0.,stt=0. if buy else v*.0015)
def bar_rule(direction,stop,first_target,activated,lo,hi,opposite_flip,priority='target'):
 midpoint=(lo+hi)/2
 if activated:
  if (lo<=stop if direction==1 else hi>=stop):return dict(exit_reason='midpoint_stop',target_hit=False,conflict=False,new_stop=stop)
  return dict(exit_reason=None,target_hit=False,conflict=False,new_stop=max(stop,midpoint) if direction==1 else min(stop,midpoint))
 target_hit=hi>=first_target if direction==1 else lo<=first_target
 conflict=bool(target_hit and opposite_flip)
 # Target touch precedes close-confirmed SMA flip. No newly computed midpoint
 # may stop the remainder retroactively inside this target candle.
 if opposite_flip and (not target_hit or priority=='flip'):
  return dict(exit_reason='pre_target_SMA_flip',target_hit=False,conflict=conflict,new_stop=None)
 return dict(exit_reason=None,target_hit=target_hit,conflict=conflict,new_stop=midpoint if target_hit else None)
assert bar_rule(1,None,110,False,70,109,False)['exit_reason'] is None
assert bar_rule(1,None,110,False,95,109,True)['exit_reason']=='pre_target_SMA_flip'
assert bar_rule(-1,None,90,False,91,105,True)['exit_reason']=='pre_target_SMA_flip'
assert bar_rule(1,None,110,False,95,111,True)['target_hit']
assert bar_rule(1,None,110,False,95,111,True,'flip')['exit_reason']=='pre_target_SMA_flip'
assert bar_rule(1,None,110,False,90,112,False)['new_stop']==101
assert bar_rule(-1,None,90,False,88,104,False)['new_stop']==96
assert bar_rule(1,104,110,True,105,106,True)['new_stop']==105.5
assert bar_rule(-1,96,90,True,94,104,True)['exit_reason']=='midpoint_stop'
assert bar_rule(1,104,110,True,105,105,False)['new_stop']==105
def next_exit(symbol,ts):
 q=prices[symbol];wanted=ts+pd.Timedelta(minutes=1)
 a=q[(q.index>=wanted)&(q.index.strftime('%Y-%m-%d')==str(ts.date()))&(q.index.strftime('%H:%M')<='15:29')&(q.volume>0)]
 if a.empty:raise RuntimeError('No next executable exit '+str(ts))
 return a.index[0],(a.index[0]-wanted).total_seconds()/60
entries=[];legs=[];orders=[];events=[];decisions=[];equity=[];active=None;cash=0.
def sell(a,ts,qty,reason):
 global cash
 q=prices[a['symbol']].loc[ts];assert q.volume>0 and q.open>0
 premium=float(q.open);fees=costs(premium,qty,False)
 order_id=len(orders)+1
 orders.append(dict(order_id=order_id,entry_id=a['entry_id'],time=ts,side='SELL',quantity=qty,premium=premium,reason=reason,costs=sum(fees.values()),**fees))
 cash+=(premium-a['entry_premium'])*qty-sum(fees.values())
 for leg_id in ([2] if qty==65 and a['remaining']==65 else [1] if qty==65 else [1,2]):
  fraction=65/qty
  leg=dict(entry_id=a['entry_id'],leg=leg_id,symbol=a['symbol'],side=a['side'],entry_time=a['entry_time'],exit_time=ts,quantity=65,entry_premium=a['entry_premium'],exit_premium=premium,entry_cost=a['entry_cost']/2,exit_cost=sum(fees.values())*fraction,exit_order_id=order_id,exit_reason=reason)
  leg.update({k:a['entry_cost_components'][k]/2+fees[k]*fraction for k in fees})
  leg['gross_pnl']=(premium-a['entry_premium'])*65;leg['costs']=leg['entry_cost']+leg['exit_cost'];leg['net_pnl']=leg['gross_pnl']-leg['costs'];legs.append(leg)
 a['remaining']-=qty
 events.append(dict(entry_id=a['entry_id'],time=ts,event=reason,quantity=qty,premium=premium,stop=a['stop']))
 if a['remaining']==0:
  done={k:v for k,v in a.items() if k not in ['entry_cost_components','direction','pending_partial','pending_full','remaining']}
  own=[l for l in legs if l['entry_id']==a['entry_id']]
  done.update(exit_time=ts,exit_reason=reason,partial_booked=any(l['exit_reason']=='first_target_partial' for l in own),gross_pnl=sum(l['gross_pnl'] for l in own),costs=sum(l['costs'] for l in own),net_pnl=sum(l['net_pnl'] for l in own),exit_orders=len({l['exit_order_id'] for l in own}))
  entries.append(done)
for ts,row in month.iterrows():
 candidate=candidates.get(ts);was_held=active is not None;closed_for_flip=None
 if active:
  if ts==active.get('pending_full'):
   if active['pending_reason']=='pre_target_SMA_flip':closed_for_flip=active['entry_id']
   sell(active,ts,active['remaining'],active['pending_reason']);active=None
  elif ts.strftime('%H:%M')=='15:29':
   sell(active,ts,active['remaining'],'scheduled_15:29');active=None
  elif ts==active.get('pending_partial'):
   sell(active,ts,65,'first_target_partial');active.pop('pending_partial')
 allow_entry=not was_held or closed_for_flip is not None
 if candidate and not allow_entry:decisions.append(dict(time=ts,reason='signal_ignored_after_target_or_during_pending_exit'))
 if candidate and allow_entry:
  g=gridbyday.get(str(ts.date()));reason=None
  if not g or g['available_at']>ts:reason='daily_grid_not_available'
  direction=1 if candidate['side']=='CE' else -1
  entryspot=float(row.open)
  if g:
   centers=sorted([g['high']+n*g['span'] for n in range(1,11)]+[g['low']-n*g['span'] for n in range(1,11)])
   targets=[x for x in centers if x>entryspot] if direction==1 else [x for x in centers[::-1] if x<entryspot]
  else:targets=[]
  if reason is None and not targets:reason='no_favorable_grid_center'
  q=prices[candidate['symbol']]
  if reason is None and (ts not in q.index or q.loc[ts,'volume']<=0):reason='unavailable_entry_premium'
  if reason:decisions.append(dict(time=ts,reason=reason))
  else:
   premium=float(q.loc[ts,'open']);fees=costs(premium,130,True);ident=len(entries)+1
   active=dict(entry_id=ident,signal_time=candidate['signal_time'],entry_time=ts,symbol=candidate['symbol'],side=candidate['side'],expiry=candidate['expiry'],strike=candidate['strike'],quantity=130,remaining=130,direction=direction,entry_spot=entryspot,stop=None,first_target=targets[0],grid_available_at=g['available_at'],grid_high=g['high'],grid_low=g['low'],activated=False,entry_premium=premium,entry_cost=sum(fees.values()),entry_cost_components=fees,reversal_from_entry_id=closed_for_flip)
   cash-=sum(fees.values())
   orders.append(dict(order_id=len(orders)+1,entry_id=ident,time=ts,side='BUY',quantity=130,premium=premium,reason='SMA30_reversal' if closed_for_flip is not None else 'SMA30_cross',costs=sum(fees.values()),**fees))
 if active and 'pending_full' not in active:
  opposite=bool(row.cross_down if active['direction']==1 else row.cross_up)
  rule=bar_rule(active['direction'],active['stop'],active['first_target'],active['activated'],row.low,row.high,opposite,args.conflict_priority)
  if rule['conflict']:
   events.append(dict(entry_id=active['entry_id'],time=ts,event='target_SMA_same_candle',priority=args.conflict_priority,close=row.close,sma30=row.sma30))
  if rule['exit_reason']:
   execute,delay=next_exit(active['symbol'],ts)
   active['pending_full']=execute;active['pending_reason']=rule['exit_reason']
   if active.get('pending_partial',execute)>execute:active.pop('pending_partial',None)
   events.append(dict(entry_id=active['entry_id'],time=ts,event='exit_trigger',reason=rule['exit_reason'],stop=active['stop'],close=row.close,sma30=row.sma30,cross_up=row.cross_up,cross_down=row.cross_down,execute_at=execute,extra_delay_minutes=delay))
  else:
   if rule['target_hit']:
    active['activated']=True;execute,delay=next_exit(active['symbol'],ts)
    active['pending_partial']=execute;active['target_touch_bar']=ts
    events.append(dict(entry_id=active['entry_id'],time=ts,event='target_confirmed',first_target=active['first_target'],execute_at=execute,extra_delay_minutes=delay))
   if active['activated']:
    old=active['stop'];active['stop']=rule['new_stop']
    events.append(dict(entry_id=active['entry_id'],time=ts,event='midpoint_trail_after_close',prior_stop=old,stop=active['stop'],candle_midpoint=(row.high+row.low)/2,effective_at=ts+pd.Timedelta(minutes=1)))
 mark=0.
 if active:
  q=prices[active['symbol']]
  if ts not in q.index:raise RuntimeError('Missing held mark '+str(ts))
  mark=(q.loc[ts,'close']-active['entry_premium'])*active['remaining']
 equity.append(dict(timestamp=ts,net_pnl=cash+mark,held_quantity=active['remaining'] if active else 0))
assert active is None
t=pd.DataFrame(entries);l=pd.DataFrame(legs);o=pd.DataFrame(orders);ev=pd.DataFrame(events);eq=pd.DataFrame(equity).set_index('timestamp')
eq['drawdown_rupees']=eq.net_pnl-eq.net_pnl.cummax().clip(lower=0)
for name,data in [('entries',t),('legs',l),('orders',o),('events',ev),('signal_decisions',pd.DataFrame(decisions)),('equity',eq)]:data.to_csv(ROOT/(name+'.csv'),index=name=='equity')
assert len(l)==len(t)*2 and l.groupby('entry_id').quantity.sum().eq(130).all()
assert abs(t.net_pnl.sum()-cash)<1e-6 and abs(l.net_pnl.sum()-cash)<1e-6
assert abs(o.costs.sum()-t.costs.sum())<1e-6
n=len(l);p=np.array([l.entry_premium.values,l.exit_premium.values])
pf=vbt.Portfolio.from_orders(p,size=np.array([np.full(n,65),np.full(n,-65)]),price=p,fixed_fees=np.array([l.costs.values,np.zeros(n)]),init_cash=100000,min_size=65,size_granularity=65,raise_reject=True)
assert abs(pf.total_profit().sum()-cash)<1e-6
def metrics(d):
 return dict(count=len(d),wins=int(d.net_pnl.gt(0).sum()),win_rate_pct=d.net_pnl.gt(0).mean()*100,profit_factor=d.net_pnl[d.net_pnl>0].sum()/-d.net_pnl[d.net_pnl<0].sum())
summary=dict(status='COMPLETE',start=str(month.index[0]),end=str(month.index[-1]),sessions=20,entry_quantity=130,lot_size=65,whole_entry=metrics(t),lot_legs=metrics(l),trades=len(t),win_rate_pct=metrics(t)['win_rate_pct'],profit_factor=metrics(t)['profit_factor'],gross_pnl=t.gross_pnl.sum(),costs=t.costs.sum(),net_pnl=cash,max_drawdown_rupees=-eq.drawdown_rupees.min(),partial_exits=int(o.reason.eq('first_target_partial').sum()),executed_orders=len(o),exit_reasons=t.exit_reason.value_counts().to_dict(),skipped_or_ignored=pd.Series([x['reason'] for x in decisions]).value_counts().to_dict(),extra_delayed_exit_bars=int(ev.get('extra_delay_minutes',pd.Series(dtype=float)).fillna(0).gt(0).sum()),max_entry_premium_debit=float((t.entry_premium*130+t.entry_cost).max()),cost_breakdown={k:o[k].sum() for k in costs(100,65,True)},vectorbt_terminal_pnl_verified=True,synthetic_rule_checks=10,conflict_priority=args.conflict_priority,target_SMA_same_candle_count=int(ev.event.eq('target_SMA_same_candle').sum()),same_open_reversals=int(o.reason.eq('SMA30_reversal').sum()),pre_target_previous_candle_stop_enabled=False)
(ROOT/'results.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
b=json.loads((BASE/'results.json').read_text());g=json.loads((GRID/'grid_results.json').read_text());oldtwo=json.loads((STUDY.parent/'nifty_sma30_two_lot_midpoint_20261110/results.json').read_text())
keys=['trades','win_rate_pct','profit_factor','gross_pnl','costs','net_pnl','max_drawdown_rupees']
comparison=pd.DataFrame({'1-lot flip':{k:b[k] for k in keys},'1-lot grid trail':{k:g[k] for k in keys},'2-lot prior-candle stop':{k:oldtwo[k] for k in keys},'2-lot corrected SMA flip':{k:summary[k] for k in keys}})
comparison.to_csv(ROOT/'comparison.csv')
fig=go.Figure()
for name,path in [('1-lot flip',BASE/'equity.csv'),('1-lot grid trail',GRID/'grid_equity.csv'),('2-lot prior stop',STUDY.parent/'nifty_sma30_two_lot_midpoint_20261110/equity.csv'),('2-lot corrected SMA flip',ROOT/'equity.csv')]:
 d=pd.read_csv(path);fig.add_trace(go.Scatter(x=d.timestamp,y=d.net_pnl,name=name))
fig.update_layout(template='plotly_dark',title='October 2026 options: unnormalized exposure comparison',yaxis_title='Net rupees');fig.write_html(ROOT/'comparison.html',include_plotlyjs=True)
print(json.dumps(summary,indent=2,default=str));print(comparison.to_string())

