"""Five-minute signal and midpoint timeframe; minute-level option execution, read-only."""
import json,hashlib,argparse,math,time,os,requests,threading,concurrent.futures
from job_runtime import progress
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
spot=frame(rows).between_time('09:15','15:29').loc['2026-04-01':]
five=spot.resample('5min',origin='start_day',offset='9h15min').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum','epoch':'count'}).dropna()
assert five.epoch.eq(5).all()
five['sma30']=ta.sma(five.close,30)
five['cross_up']=(five.close>five.sma30)&(five.close.shift(1)<=five.sma30.shift(1))
five['cross_down']=(five.close<five.sma30)&(five.close.shift(1)>=five.sma30.shift(1))
up=pd.Series(ta.exrem(five.cross_up.fillna(False),five.cross_down.fillna(False)),index=five.index)
down=pd.Series(ta.exrem(five.cross_down.fillna(False),up.fillna(False)),index=five.index)
five['entry_direction']=np.where(up,1,np.where(down,-1,0))
month=spot.loc['2026-05-01':'2026-10-31']
monthfive=five.loc['2026-05-01':'2026-10-31'];monthfive.to_csv(ROOT/'spot_5m.csv')
assert len(monthfive)*5==len(month)
counts=month.groupby(month.index.date).size();assert counts.eq(375).all()
progress('metadata',spot_sessions=len(counts),spot_bars=len(month),five_minute_bars=len(monthfive))
fiveclosed={ts+pd.Timedelta(minutes=4):r for ts,r in five.iterrows()}
extra_raw=STUDY/'raw';extra_raw.mkdir(exist_ok=True)
rate_lock=threading.Lock();last_request=[0.]
def provider(path,params,name):
 p=extra_raw/(name+'.json')
 if p.exists():return json.loads(p.read_text())
 token=json.loads(Path(os.environ['FYERS_RESEARCH_TOKEN_FILE']).read_text())
 app=token.get('app_id') or token.get('client_id');value=(token.get('access_token') or token.get('token')).split(':',1)[-1]
 for attempt in range(3):
  with rate_lock:
   delay=.42-(time.monotonic()-last_request[0])
   if delay>0:time.sleep(delay)
   last_request[0]=time.monotonic()
  try:
   response=requests.get('https://api-t1.fyers.in/data/'+path,headers={'Authorization':app+':'+value},params=params,timeout=(4,25))
   if response.status_code in (401,403):raise RuntimeError('FYERS authorization rejected')
   response.raise_for_status();body=response.json()
   if body.get('s') not in ('ok','no_data',None):raise RuntimeError(str(body))
   tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(body));tmp.replace(p)
   return body
  except (requests.RequestException,ValueError):
   if attempt==2:raise
   time.sleep(1+attempt)
expirydata=provider('history/fno/expired/expiry-dates',dict(symbol='NSE:NIFTY50-INDEX',date_format='1',range_from='2026-05-01',range_to='2026-11-06'),'expiries_may_nov')
expiries=sorted(expirydata['data']['expiry_dates']['options'])
contracts={}
needed_expiries=sorted({min(e for e in expiries if e>=str(day)) for day in counts.index})
for i,e in enumerate(needed_expiries):
 old=BASE/'raw'/('contracts_'+e+'.json')
 body=json.loads(old.read_text()) if old.exists() else provider('history/fno/expired/underlying-symbols',dict(symbol='NSE:NIFTY50-INDEX',expiry_date=e),'contracts_'+e)
 contracts[e]=body['data']['contracts']['options']
 progress('contract_metadata',metadata_completed=i+1,metadata_total=len(needed_expiries))
records=[]
for ts,r in monthfive.iterrows():
 if not r.entry_direction:continue
 execute=ts+pd.Timedelta(minutes=5)
 if execute.strftime('%H:%M')>'15:28':continue
 side='CE' if r.entry_direction==1 else 'PE'
 expiry=min(e for e in contracts if e>=str(ts.date()))
 strike=int(math.floor(r.close/50+.5)*50)
 matches=[x for x in contracts[expiry] if x.endswith(str(strike)+side)]
 assert len(matches)==1,(expiry,strike,side,matches)
 records.append(dict(signal_time=ts,signal_confirmed_at=execute,entry_time=execute,symbol=matches[0],expiry=expiry,strike=strike,side=side))
signals=pd.DataFrame(records);signals.to_csv(ROOT/'candidate_signals.csv',index=False)
candidates={x['entry_time']:x for x in records}
# Rebuild the unchanged current-day V1 reference over the complete test window.
refs=[]
for day,x in month.groupby(month.index.date):
 f=x.resample('5min',origin='start_day',offset='9h15min').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna().iloc[1:]
 red=f[f.close<f.open]
 if len(red):
  ref=red.iloc[0];ts=red.index[0];refs.append(dict(day=str(day),available_at=ts+pd.Timedelta(minutes=5),high=ref.high,low=ref.low,span=ref.high-ref.low))
grids=pd.DataFrame(refs);grids.to_csv(ROOT/'causal_daily_grid.csv',index=False);gridbyday={x['day']:x for x in refs}
prices={};old5=STUDY.parent/'nifty_sma30_five_minute_20261110'
symbols=list(signals.symbol.unique());progress('option_download',contracts_total=len(symbols),contracts_completed=0)
def load_option(sym):
 name='option_'+sym.replace(':','_')+'.json'
 used=signals[signals.symbol==sym];first=str(used.entry_time.min().date());last=str(used.entry_time.max().date())
 # Earlier archives were explicitly requested for October only. Existence
 # does not establish coverage for a September entry in the same contract.
 paths=[extra_raw/name]
 if first>='2026-10-01' and last<='2026-10-31':paths.extend([BASE/'raw'/name,old5/'raw'/name])
 p=next((p for p in paths if p.exists()),None)
 if p:r=json.loads(p.read_text());origin=str(p)
 else:
  used=signals[signals.symbol==sym]
  first=str(used.entry_time.min().date());last=str(used.entry_time.max().date())
  r=provider('history/fno/expired/historical-data',dict(symbol=sym,resolution='1',date_format='1',range_from=first,range_to=last),name[:-5]);origin=str(extra_raw/name)
 d=frame(r.get('candles',r.get('data',{}).get('candles',[])))
 if d.empty:raise RuntimeError('No real option candles '+sym)
 return sym,d,origin
data_sources={}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 jobs={pool.submit(load_option,s):s for s in symbols}
 for i,future in enumerate(concurrent.futures.as_completed(jobs)):
  sym,data,origin=future.result();prices[sym]=data;data_sources[sym]=origin
  progress('option_download',contracts_completed=i+1,last_contract=sym)
  print('contract',i+1,len(symbols),sym,'bars',len(data),flush=True)
(ROOT/'data_sources.json').write_text(json.dumps(data_sources,indent=2))
progress('simulation',contracts_completed=len(symbols),candidate_signals=len(signals),minutes_completed=0)
LOT=65
def costs(p,qty,buy):
 v=p*qty;brokerage=20.;exchange=v*.000355299;sebi=v*.000001;ipft=v*.000000001;clearing=v*.00009
 gst=.18*(brokerage+exchange+sebi+ipft+clearing)
 return dict(brokerage=brokerage,exchange=exchange,sebi=sebi,ipft=ipft,clearing=clearing,gst=gst,stamp=v*.00003 if buy else 0.,stt=0. if buy else v*.0015)
def bar_rule(direction,stop,first_target,activated,lo,hi,opposite_flip,priority='target'):
 stop_hit=activated and stop is not None and (lo<=stop if direction==1 else hi>=stop)
 if stop_hit:return dict(exit_reason='midpoint_stop',target_hit=False,conflict=False)
 target_hit=not activated and (hi>=first_target if direction==1 else lo<=first_target)
 conflict=bool(target_hit and opposite_flip)
 if not activated and opposite_flip and (not target_hit or priority=='flip'):
  return dict(exit_reason='pre_target_SMA_flip',target_hit=False,conflict=conflict)
 return dict(exit_reason=None,target_hit=target_hit,conflict=conflict)
assert bar_rule(1,None,110,False,70,109,False)['exit_reason'] is None
assert bar_rule(1,None,110,False,95,109,True)['exit_reason']=='pre_target_SMA_flip'
assert bar_rule(-1,None,90,False,91,105,True)['exit_reason']=='pre_target_SMA_flip'
assert bar_rule(1,None,110,False,95,111,True)['target_hit']
assert bar_rule(1,None,110,False,95,111,True,'flip')['exit_reason']=='pre_target_SMA_flip'
assert bar_rule(1,None,110,True,70,111,True)['exit_reason'] is None
assert bar_rule(1,104,110,True,103,112,False)['exit_reason']=='midpoint_stop'
assert bar_rule(-1,96,90,True,88,97,True)['exit_reason']=='midpoint_stop'
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
for minute_number,(ts,row) in enumerate(month.iterrows()):
 if minute_number%250==0:progress('simulation',minutes_completed=minute_number,minutes_total=len(month),completed_entries=len(entries),latest_spot_bar=str(ts))
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
   active=dict(entry_id=ident,signal_time=candidate['signal_time'],signal_confirmed_at=candidate['signal_confirmed_at'],entry_time=ts,symbol=candidate['symbol'],side=candidate['side'],expiry=candidate['expiry'],strike=candidate['strike'],quantity=130,remaining=130,direction=direction,entry_spot=entryspot,stop=None,first_target=targets[0],grid_available_at=g['available_at'],grid_high=g['high'],grid_low=g['low'],activated=False,entry_premium=premium,entry_cost=sum(fees.values()),entry_cost_components=fees,reversal_from_entry_id=closed_for_flip)
   cash-=sum(fees.values())
   orders.append(dict(order_id=len(orders)+1,entry_id=ident,time=ts,side='BUY',quantity=130,premium=premium,reason='SMA30_reversal' if closed_for_flip is not None else 'SMA30_cross',costs=sum(fees.values()),**fees))
 if active and 'pending_full' not in active:
  completed=fiveclosed.get(ts)
  opposite=bool(completed.cross_down if active['direction']==1 else completed.cross_up) if completed is not None else False
  rule=bar_rule(active['direction'],active['stop'],active['first_target'],active['activated'],row.low,row.high,opposite,args.conflict_priority)
  if rule['conflict']:
   events.append(dict(entry_id=active['entry_id'],time=ts,event='target_SMA_same_candle',priority=args.conflict_priority,close=row.close,sma30=completed.sma30 if completed is not None else np.nan))
  if rule['exit_reason']:
   execute,delay=next_exit(active['symbol'],ts)
   active['pending_full']=execute;active['pending_reason']=rule['exit_reason']
   if active.get('pending_partial',execute)>execute:active.pop('pending_partial',None)
   events.append(dict(entry_id=active['entry_id'],time=ts,event='exit_trigger',reason=rule['exit_reason'],stop=active['stop'],close=row.close,sma30=completed.sma30 if completed is not None else np.nan,cross_up=bool(completed.cross_up) if completed is not None else False,cross_down=bool(completed.cross_down) if completed is not None else False,execute_at=execute,extra_delay_minutes=delay))
  else:
   if rule['target_hit']:
    active['activated']=True;execute,delay=next_exit(active['symbol'],ts)
    active['pending_partial']=execute;active['target_touch_bar']=ts
    events.append(dict(entry_id=active['entry_id'],time=ts,event='target_confirmed',first_target=active['first_target'],execute_at=execute,extra_delay_minutes=delay))
   if active['activated'] and completed is not None:
    old=active['stop'];midpoint=(completed.high+completed.low)/2
    active['stop']=midpoint if old is None else max(old,midpoint) if active['direction']==1 else min(old,midpoint)
    events.append(dict(entry_id=active['entry_id'],time=ts,event='midpoint_trail_after_close',prior_stop=old,stop=active['stop'],candle_midpoint=midpoint,effective_at=ts+pd.Timedelta(minutes=1),midpoint_source_start=ts-pd.Timedelta(minutes=4)))
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
summary=dict(status='COMPLETE',start=str(month.index[0]),end=str(month.index[-1]),sessions=len(counts),entry_quantity=130,lot_size=65,whole_entry=metrics(t),lot_legs=metrics(l),trades=len(t),win_rate_pct=metrics(t)['win_rate_pct'],profit_factor=metrics(t)['profit_factor'],gross_pnl=t.gross_pnl.sum(),costs=t.costs.sum(),net_pnl=cash,max_drawdown_rupees=-eq.drawdown_rupees.min(),partial_exits=int(o.reason.eq('first_target_partial').sum()),executed_orders=len(o),exit_reasons=t.exit_reason.value_counts().to_dict(),skipped_or_ignored=pd.Series([x['reason'] for x in decisions]).value_counts().to_dict(),extra_delayed_exit_bars=int(ev.get('extra_delay_minutes',pd.Series(dtype=float)).fillna(0).gt(0).sum()),max_entry_premium_debit=float((t.entry_premium*130+t.entry_cost).max()),cost_breakdown={k:o[k].sum() for k in costs(100,65,True)},vectorbt_terminal_pnl_verified=True,synthetic_rule_checks=8,conflict_priority=args.conflict_priority,target_SMA_same_candle_count=int(ev.event.eq('target_SMA_same_candle').sum()),same_open_reversals=int(o.reason.eq('SMA30_reversal').sum()),pre_target_previous_candle_stop_enabled=False,signal_timeframe_minutes=5,midpoint_timeframe_minutes=5,touch_monitor_minutes=1,candidate_signal_count=len(signals),target_reached_entries=int(t.activated.sum()),target_reached_pct=float(t.activated.mean()*100))
(ROOT/'results.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
progress('writing_results',minutes_completed=len(month),completed_entries=len(t))
one=STUDY.parent/'nifty_sma30_five_minute_20261110'
prior=json.loads((one/'results.json').read_text())
keys=['trades','win_rate_pct','profit_factor','gross_pnl','costs','net_pnl','max_drawdown_rupees']
comparison=pd.DataFrame({'October5m baseline':{k:prior[k] for k in keys},'Six-month5m':{k:summary[k] for k in keys}})
comparison.to_csv(ROOT/'comparison.csv')
fig=go.Figure()
for name,path in [('October5m baseline',one/'equity.csv'),('Six-month5m',ROOT/'equity.csv')]:
 d=pd.read_csv(path);fig.add_trace(go.Scatter(x=d.timestamp,y=d.net_pnl,name=name))
fig.update_layout(template='plotly_dark',title='October2026: 1m versus5m strategy candles, minute executions',yaxis_title='Net rupees')
fig.write_html(ROOT/'comparison.html',include_plotlyjs=True)
print(json.dumps(summary,indent=2,default=str));print(comparison.to_string())
