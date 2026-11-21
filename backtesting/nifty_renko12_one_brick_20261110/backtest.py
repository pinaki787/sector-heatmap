"""Research-only one-brick-reversal Renko12; minute-close path approximation."""
import os,json,math,time,hashlib,threading,concurrent.futures,subprocess,gzip,io,sys,zipfile,argparse
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timedelta
import numpy as np,pandas as pd
import vectorbt as vbt
import plotly.graph_objects as go
from job_runtime import progress
PROJECT=Path('/home/trading/sector-heatmap')
sys.path.insert(0,str(PROJECT))
from strategies.renko_supertrend.nse_contract_lots import archive,source_url,contract_date
STUDY=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--range-lock',action='store_true');args=parser.parse_args()
ROOT=STUDY/'entry_brick_range_lock' if args.range_lock else STUDY;ROOT.mkdir(exist_ok=True)
RAW=STUDY/'raw';RAW.mkdir(exist_ok=True)
progress('initializing',variant='entry_brick_range_lock' if args.range_lock else 'plain')
SIX=STUDY.parent/'nifty_sma30_six_month_20261110';BASE=STUDY.parent/'nifty_sma30_options_20261110';OCT=STUDY.parent/'nifty_sma30_five_minute_20261110'
def frame(rows):
 d=pd.DataFrame([x[:6] for x in rows],columns=['epoch','open','high','low','close','volume'])
 d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata')
 assert not d.index.duplicated().any()
 assert ((d.low<=d[['open','close']].min(axis=1))&(d.high>=d[['open','close']].max(axis=1))).all()
 return d.sort_index()
rows=json.loads((PROJECT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']+json.loads((BASE/'raw/spot_oct24_31.json').read_text())['candles']
spot=frame(rows).between_time('09:15','15:29').loc['2026-05-01':'2026-10-31']
counts=spot.groupby(spot.index.date).size();assert counts.eq(375).all() and len(counts)==125
def cents(value):
 result=Decimal(str(value))*100
 assert result==result.to_integral_value()
 return int(result)
def step(level,price):
 result=[]
 while abs(price-level)>=1200:
  side=1 if price>level else -1;new=level+side*1200
  result.append((level,new,side));level=new
 return level,result
assert step(10000,11199)==(10000,[])
assert step(10000,11200)==(11200,[(10000,11200,1)])
assert step(11200,10000)==(10000,[(11200,10000,-1)])
assert len(step(10000,13800)[1])==3 and step(10000,13800)[0]==13600
assert step(13600,12500)[1]==[]
assert step(13600,12400)[1][0]==(13600,12400,-1)
bricks=[];observations=[];sequence=0
for day,d in spot.groupby(spot.index.date):
 level=cents(d.iloc[0].open);previous_direction=0
 for ts,row in d.iterrows():
  level,new=step(level,cents(row.close))
  if not new:continue
  available=ts+pd.Timedelta(minutes=1)
  for i,(opened,closed,sign) in enumerate(new):
   sequence+=1
   bricks.append(dict(brick_id=sequence,day=str(day),source_minute=ts,known_at=available,source_close=row.close,brick_open=opened/100,brick_close=closed/100,direction=sign,reversal=bool(previous_direction and sign!=previous_direction),source_event_index=i))
   previous_direction=sign
  observations.append(dict(source_minute=ts,known_at=available,spot_signal_close=float(row.close),direction=new[-1][2],completed_bricks=len(new),first_brick_id=sequence-len(new)+1,last_brick_id=sequence))
pd.DataFrame(bricks).to_csv(ROOT/'bricks.csv',index=False)
obs=pd.DataFrame(observations);obs.to_csv(ROOT/'brick_observations.csv',index=False)
groups={x['known_at']:x for x in observations if x['known_at'].strftime('%H:%M')<='15:29'}
rate_lock=threading.Lock();last=[0.]
def provider(path,params,name):
 p=RAW/(name+'.json')
 if p.exists():return json.loads(p.read_text())
 token=json.loads(Path(os.environ['FYERS_RESEARCH_TOKEN_FILE']).read_text())
 app=token.get('app_id') or token.get('client_id');value=(token.get('access_token') or token.get('token')).split(':',1)[-1]
 for attempt in range(3):
  with rate_lock:
   delay=.42-(time.monotonic()-last[0])
   if delay>0:time.sleep(delay)
   last[0]=time.monotonic()
  try:
   r=requests.get('https://api-t1.fyers.in/data/'+path,headers={'Authorization':app+':'+value},params=params,timeout=(4,25))
   r.raise_for_status();body=r.json()
   if body.get('s') not in ('ok','no_data',None):raise RuntimeError(str(body))
   tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(body));tmp.replace(p);return body
  except (requests.RequestException,ValueError):
   if attempt==2:raise
   time.sleep(1+attempt)
# Exact provider-listed expiry symbols, no synthetic strike strings.
import requests
expiry=json.loads((SIX/'raw/expiries_may_nov.json').read_text())['data']['expiry_dates']['options']
contracts={}
for e in sorted({min(e for e in expiry if e>=str(day)) for day in counts.index}):
 p=SIX/'raw'/('contracts_'+e+'.json')
 if not p.exists():p=BASE/'raw'/p.name
 contracts[e]=json.loads(p.read_text())['data']['contracts']['options']
records=[]
for x in observations:
 if x['known_at'].strftime('%H:%M')>'15:28':continue
 day=str(x['known_at'].date());e=min(e for e in contracts if e>=day)
 strike=int(math.floor(x['spot_signal_close']/50+.5)*50);side='CE' if x['direction']==1 else 'PE'
 matches=[s for s in contracts[e] if s.endswith(str(strike)+side)]
 if len(matches)!=1:raise RuntimeError('Exact provider-listed ATM missing '+str((day,e,strike,side,matches)))
 records.append(dict(**x,entry_time=x['known_at'],day=day,symbol=matches[0],expiry=e,strike=strike,side=side))
candidate=pd.DataFrame(records);candidate.to_csv(ROOT/'candidate_signals.csv',index=False)
bytime={x['entry_time']:x for x in records}
progress('daily_contract_masters',sessions_total=125,sessions_completed=0,completed_bricks=len(bricks),candidate_observations=len(records))
# Exact daily source evidence, no current-size or circular-based fallback.
needed={day:part for day,part in candidate.groupby('day')}
lot_evidence={}
def master(day,part):
 manifests=list((PROJECT/'data/backtesting/nse-contract-masters/manifests'/day).glob('*.json'))
 if manifests:
  m=json.loads(manifests[0].read_text());blob=(PROJECT/m['source_file']).read_bytes()
  assert hashlib.sha256(blob).hexdigest()==m['source_sha256']
 else:
  url=source_url(day)
  r=subprocess.run(['curl','-4','--http1.1','-f','-sS','-A','Mozilla/5.0','--connect-timeout','4','--max-time','25','--retry','2',url],capture_output=True)
  if r.returncode:raise RuntimeError('NSE daily master download failed '+day+': '+r.stderr.decode()[:150])
  blob=r.stdout;m=archive(PROJECT,day,blob,url)
 fields=['StockNm','FinInstrmId','FinInstrmNm','TckrSymb','XpryDt','StrkPric','OptnTp','MinLot','NewBrdLotQty','StartDt']
 d=pd.read_csv(io.BytesIO(gzip.decompress(blob)),dtype=str,usecols=fields)
 out=[]
 for sym,rows in part.groupby('symbol'):
  exact=d[d.StockNm==sym.removeprefix('NSE:')]
  if len(exact)>1:raise RuntimeError('Conflicting exact dated NSE contracts '+day+' '+sym)
  if len(exact)==0:
   # Same-date EOD MII files can omit today's expiring instruments.
   # Same-date official UDiFF bhavcopy retains exact symbol and Market Lot Size.
   path=RAW/('bhavcopy_'+day+'.zip')
   url='https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_'+day.replace('-','')+'_F_0000.csv.zip'
   if not path.exists():
    fetched=subprocess.run(['curl','-4','--http1.1','-f','-sS','-A','Mozilla/5.0','--connect-timeout','4','--max-time','25','--retry','1',url],capture_output=True)
    if fetched.returncode:raise RuntimeError('NSE dated bhavcopy unavailable '+day)
    path.write_bytes(fetched.stdout)
   with zipfile.ZipFile(path) as z:
    bhav=pd.read_csv(z.open(z.namelist()[0]),dtype=str)
   matches=bhav[bhav.FinInstrmNm.eq(sym.removeprefix('NSE:'))]
   if len(matches)!=1:raise RuntimeError('Exact dated NSE master and bhavcopy both omit '+day+' '+sym)
   row=matches.iloc[0];expected=rows.iloc[0];lot=int(row.NewBrdLotQty)
   assert row.TradDt==day and row.BizDt==day and row.Src=='NSE' and row.TckrSymb=='NIFTY'
   assert row.XpryDt==expected.expiry and row.FininstrmActlXpryDt==expected.expiry
   assert row.OptnTp==expected.side and Decimal(row.StrkPric)==Decimal(str(expected.strike))
   assert lot>0 and Decimal(row.NewBrdLotQty)==lot
   out.append(dict(day=day,symbol=sym,expiry=expected.expiry,strike=int(expected.strike),side=expected.side,lot_size=lot,source_file=str(path.relative_to(PROJECT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_url=url,effective_from=day,effective_to=day,exchange_token=row.FinInstrmId,provider='NSE_UDIFF_DAILY_BHAVCOPY'))
   continue
  row=exact.iloc[0];expected=rows.iloc[0];lot=int(row.NewBrdLotQty)
  assert row.FinInstrmNm=='OPTIDX' and row.TckrSymb=='NIFTY'
  assert lot>0 and float(row.MinLot)==lot and float(row.NewBrdLotQty)==lot
  assert contract_date(row.XpryDt)==expected.expiry and row.OptnTp==expected.side and Decimal(row.StrkPric)/100==Decimal(str(expected.strike))
  assert contract_date(row.StartDt)<=day<=expected.expiry
  out.append(dict(day=day,symbol=sym,expiry=expected.expiry,strike=int(expected.strike),side=expected.side,lot_size=lot,source_file=m['source_file'],source_sha256=m['source_sha256'],source_url=m['source_url'],effective_from=day,effective_to=day,exchange_token=row.FinInstrmId,provider='NSE_DAILY_MII_MASTER'))
 return day,out
cached_lots=STUDY/'dated_lot_evidence.csv'
if args.range_lock and cached_lots.exists():
 cached=pd.read_csv(cached_lots);checked_sources=set()
 for x in cached.to_dict('records'):
  path=PROJECT/x['source_file']
  if str(path) not in checked_sources:
   assert hashlib.sha256(path.read_bytes()).hexdigest()==x['source_sha256'];checked_sources.add(str(path))
  lot_evidence[(x['day'],x['symbol'])]=x
 assert all((x['day'],x['symbol']) in lot_evidence for x in records)
 progress('daily_contract_masters',sessions_completed=len(needed),lot_cache_verified=True)
 print('reused exact dated lot evidence',len(lot_evidence),flush=True)
if not lot_evidence:
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  jobs=[pool.submit(master,day,part) for day,part in needed.items()]
  for i,f in enumerate(concurrent.futures.as_completed(jobs)):
   day,rows=f.result()
   for x in rows:lot_evidence[(day,x['symbol'])]=x
   progress('daily_contract_masters',sessions_completed=i+1,last_day=day)
   print('dated master',i+1,len(needed),day,flush=True)
pd.DataFrame(lot_evidence.values()).to_csv(ROOT/'dated_lot_evidence.csv',index=False)
# Require historical quantity evidence for all candidates, not merely filled trades.
assert all((x['day'],x['symbol']) in lot_evidence for x in records)
prices={};sources={};symbols=list(candidate.symbol.unique())
progress('option_download',contracts_total=len(symbols),contracts_completed=0)
def load(sym):
 part=candidate[candidate.symbol==sym];first=part.day.min();lastday=part.day.max();name='option_'+sym.replace(':','_')+'.json'
 paths=[RAW/name]
 # Earlier six-month files retain request coverage through the candidate dates only.
 # A wider new strategy cannot silently borrow a narrower cached file.
 for folder in [SIX/'raw',BASE/'raw',OCT/'raw']:
  p=folder/name
  if not p.exists():continue
  raw=json.loads(p.read_text());rows=raw.get('candles',raw.get('data',{}).get('candles',[]))
  if rows:
   start=pd.Timestamp(rows[0][0],unit='s',tz='UTC').tz_convert('Asia/Kolkata').strftime('%Y-%m-%d')
   end=pd.Timestamp(rows[-1][0],unit='s',tz='UTC').tz_convert('Asia/Kolkata').strftime('%Y-%m-%d')
   if start<=first and end>=lastday:paths.append(p)
 p=next((p for p in paths if p.exists()),None)
 if p:raw=json.loads(p.read_text());source=str(p)
 else:raw=provider('history/fno/expired/historical-data',dict(symbol=sym,resolution='1',date_format='1',range_from=first,range_to=lastday),name[:-5]);source=str(RAW/name)
 d=frame(raw.get('candles',raw.get('data',{}).get('candles',[])))
 if d.empty:raise RuntimeError('No real option data '+sym)
 return sym,d,source
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 jobs=[pool.submit(load,s) for s in symbols]
 for i,f in enumerate(concurrent.futures.as_completed(jobs)):
  sym,data,source=f.result();prices[sym]=data;sources[sym]=source;progress('option_download',contracts_completed=i+1,last_contract=sym)
  print('option',i+1,len(symbols),sym,len(data),flush=True)
(ROOT/'data_sources.json').write_text(json.dumps(sources,indent=2))
def cost(p,qty,buy):
 v=p*qty;brokerage=20.;exchange=v*.000355299;sebi=v*.000001;ipft=v*.000000001;clearing=v*.00009;gst=.18*(brokerage+exchange+sebi+ipft+clearing)
 return dict(brokerage=brokerage,exchange=exchange,sebi=sebi,ipft=ipft,clearing=clearing,gst=gst,stamp=v*.00003 if buy else 0.,stt=0. if buy else v*.0015)
def exit_time(sym,wanted):
 p=prices[sym];a=p[(p.index>=wanted)&(p.index.strftime('%Y-%m-%d')==str(wanted.date()))&(p.index.strftime('%H:%M')<='15:29')&(p.volume>0)]
 if a.empty:raise RuntimeError('No available exit before EOD '+sym+' '+str(wanted))
 return a.index[0]
trades=[];orders=[];decisions=[];equity=[];cash=0.;active=None;flips=0;events=[]
lock=None;lock_events=[];session_day=None;brick_lookup={x['brick_id']:x for x in bricks};batch_lookup={}
for x in bricks:batch_lookup.setdefault(x['known_at'],[]).append(x)
def eligible_breakout(batch,lock,at):
 if at<=lock['activated_at']:return None,'pre_loss_brick_batch'
 for b in batch:
  if b['brick_close']>lock['high'] and b['direction']==1:return b,None
  if b['brick_close']<lock['low'] and b['direction']==-1:return b,None
 if any(b['brick_close']>lock['high'] or b['brick_close']<lock['low'] for b in batch):return None,'outside_but_wrong_color'
 return None,'inside_or_equal_lock_range'
fixture=dict(low=100.,high=112.,activated_at=pd.Timestamp('2026-05-04 10:00',tz='Asia/Kolkata'))
assert eligible_breakout([dict(brick_close=124,direction=1)],fixture,fixture['activated_at'])[0] is None
assert eligible_breakout([dict(brick_close=112,direction=1)],fixture,fixture['activated_at']+pd.Timedelta(minutes=1))[0] is None
assert eligible_breakout([dict(brick_close=100,direction=-1)],fixture,fixture['activated_at']+pd.Timedelta(minutes=1))[0] is None
assert eligible_breakout([dict(brick_close=124,direction=1)],fixture,fixture['activated_at']+pd.Timedelta(minutes=1))[0]['direction']==1
assert eligible_breakout([dict(brick_close=88,direction=-1)],fixture,fixture['activated_at']+pd.Timedelta(minutes=1))[0]['direction']==-1
def close(ts,reason):
 global active,cash,lock
 price=float(prices[active['symbol']].loc[ts,'open']);fees=cost(price,active['quantity'],False)
 cash+=(price-active['entry_premium'])*active['quantity']-sum(fees.values())
 done={**active,'exit_time':ts,'exit_premium':price,'exit_reason':reason,'exit_cost':sum(fees.values()),'gross_pnl':(price-active['entry_premium'])*active['quantity']}
 done['costs']=done['entry_cost']+done['exit_cost'];done['net_pnl']=done['gross_pnl']-done['costs'];trades.append(done)
 orders.append(dict(entry_id=active['entry_id'],time=ts,side='SELL',symbol=active['symbol'],quantity=active['quantity'],premium=price,reason=reason,costs=sum(fees.values()),**fees))
 if args.range_lock and done['net_pnl']<0:
  entry_brick=brick_lookup[done['entry_brick_id']]
  lock=dict(low=min(entry_brick['brick_open'],entry_brick['brick_close']),high=max(entry_brick['brick_open'],entry_brick['brick_close']),activated_at=ts,losing_entry_id=done['entry_id'],entry_brick_id=done['entry_brick_id'])
  lock_events.append(dict(event='lock_activated',time=ts,**lock,realized_net_pnl=done['net_pnl']))
 active=None
for i,(ts,row) in enumerate(spot.iterrows()):
 if i%250==0:progress('simulation',minutes_completed=i,minutes_total=len(spot),completed_trades=len(trades),latest_bar=str(ts))
 if str(ts.date())!=session_day:
  if lock:lock_events.append(dict(event='session_reset',time=ts,**lock))
  lock=None;session_day=str(ts.date())
 group=groups.get(ts);candidate_row=bytime.get(ts);old_active=active is not None;closed_for_flip=False
 if active and active.get('pending_exit_time')==ts:
  close(ts,'opposite_brick');closed_for_flip=True
 if ts.strftime('%H:%M')=='15:29':
  if active:close(ts,'scheduled_15:29')
 elif group:
  if active and group['direction']!=active['direction'] and 'pending_exit_time' not in active:
   flips+=1;when=exit_time(active['symbol'],ts)
   active['exit_signal_known_at']=ts;active['exit_signal_brick_id']=group['last_brick_id']
   active['exit_extra_delay_minutes']=(when-ts).total_seconds()/60
   if when==ts:close(ts,'opposite_brick');closed_for_flip=True
   else:active['pending_exit_time']=when
  if active is None and candidate_row:
   selected_brick=brick_lookup[candidate_row['first_brick_id']]
   if args.range_lock and lock:
    selected_brick,blocked=eligible_breakout(batch_lookup[ts],lock,ts)
    if blocked:
     decisions.append(dict(time=ts,symbol=candidate_row['symbol'],reason='range_lock_'+blocked,brick_id=candidate_row['first_brick_id'],low=lock['low'],high=lock['high'],activated_at=lock['activated_at']))
     selected_brick=None
   sym=candidate_row['symbol'];p=prices[sym]
   if selected_brick is None:
    equity.append(dict(timestamp=ts,net_pnl=cash,held_quantity=0,lock_active=lock is not None))
    continue
   if ts not in p.index or p.loc[ts,'volume']<=0:
    decisions.append(dict(time=ts,symbol=sym,reason='missing_entry_candle' if ts not in p.index else 'zero_volume_entry_candle',brick_id=candidate_row['last_brick_id']))
   else:
    if args.range_lock and lock:
     lock_events.append(dict(event='lock_breakout_entry',time=ts,**lock,breakout_brick_id=selected_brick['brick_id'],breakout_brick_close=selected_brick['brick_close'],breakout_direction=selected_brick['direction']))
     lock=None
    evidence=lot_evidence[(str(ts.date()),sym)];qty=evidence['lot_size'];premium=float(p.loc[ts,'open']);fees=cost(premium,qty,True);ident=len(trades)+1
    active=dict(entry_id=ident,signal_source_minute=candidate_row['source_minute'],signal_known_at=ts,entry_time=ts,symbol=sym,side=candidate_row['side'],expiry=candidate_row['expiry'],strike=candidate_row['strike'],quantity=qty,direction=candidate_row['direction'],entry_premium=premium,entry_cost=sum(fees.values()),entry_brick_id=selected_brick['brick_id'],source_close=candidate_row['spot_signal_close'],lot_source_sha256=evidence['source_sha256'],lot_source_day=evidence['day'],reversal_entry=closed_for_flip)
    cash-=sum(fees.values());orders.append(dict(entry_id=ident,time=ts,side='BUY',symbol=sym,quantity=qty,premium=premium,reason='brick_reversal' if closed_for_flip else 'completed_brick',costs=sum(fees.values()),**fees))
  elif active is not None:decisions.append(dict(time=ts,symbol=active['symbol'],reason='hold_same_color' if group['direction']==active['direction'] else 'waiting_pending_exit',brick_id=group['last_brick_id']))
 mark=0.
 if active:
  p=prices[active['symbol']]
  if ts not in p.index:raise RuntimeError('Missing held premium mark '+active['symbol']+' '+str(ts))
  mark=(p.loc[ts,'close']-active['entry_premium'])*active['quantity']
 equity.append(dict(timestamp=ts,net_pnl=cash+mark,held_quantity=active['quantity'] if active else 0,lock_active=lock is not None))
assert active is None
t=pd.DataFrame(trades);o=pd.DataFrame(orders);eq=pd.DataFrame(equity).set_index('timestamp');eq['drawdown_rupees']=eq.net_pnl-eq.net_pnl.cummax().clip(lower=0)
pd.DataFrame(lock_events).to_csv(ROOT/'lock_events.csv',index=False)
t.to_csv(ROOT/'trades.csv',index=False);o.to_csv(ROOT/'orders.csv',index=False);pd.DataFrame(decisions).to_csv(ROOT/'decisions.csv',index=False);eq.to_csv(ROOT/'equity.csv')
assert abs(t.net_pnl.sum()-cash)<1e-6 and abs(o.costs.sum()-t.costs.sum())<1e-6
p=np.array([t.entry_premium.values,t.exit_premium.values]);q=np.array([t.quantity.values,-t.quantity.values])
pf=vbt.Portfolio.from_orders(p,size=q,price=p,fixed_fees=np.array([t.costs.values,np.zeros(len(t))]),init_cash=100000,min_size=1,size_granularity=1,raise_reject=True)
assert abs(pf.total_profit().sum()-cash)<1e-6
summary=dict(status='REPLAY_COMPLETE_PENDING_AUDIT',fidelity='ONE_MINUTE_CLOSE_PATH_APPROXIMATION_NOT_TICK_REPLAY',brick_points=12,reversal_bricks=1,session_anchor='Each09:15 actual spot open; reset daily; no overnight gap bricks',requested_start='2026-05-01',requested_end='2026-10-31',first=str(spot.index[0]),last=str(spot.index[-1]),sessions=125,completed_bricks=len(bricks),brick_observation_groups=len(obs),trades=len(t),wins=int(t.net_pnl.gt(0).sum()),win_rate_pct=t.net_pnl.gt(0).mean()*100,profit_factor=t.net_pnl[t.net_pnl>0].sum()/-t.net_pnl[t.net_pnl<0].sum(),gross_pnl=t.gross_pnl.sum(),costs=t.costs.sum(),net_pnl=cash,max_drawdown_rupees=-eq.drawdown_rupees.min(),exit_reasons=t.exit_reason.value_counts().to_dict(),entry_exclusions=len([x for x in decisions if x['reason'] in ('missing_entry_candle','zero_volume_entry_candle')]),dated_lot_sizes=sorted(t.quantity.unique().tolist()),reversal_entries=int(t.reversal_entry.sum()),delayed_exit_count=int(t.get('exit_extra_delay_minutes',pd.Series(dtype=float)).fillna(0).gt(0).sum()),vectorbt_terminal_verified=True,synthetic_brick_checks=6,range_lock_enabled=args.range_lock,range_lock_synthetic_checks=5 if args.range_lock else 0,lock_activations=sum(x['event']=='lock_activated' for x in lock_events),breakout_entries=sum(x['event']=='lock_breakout_entry' for x in lock_events),range_filtered_observations=sum(x['reason'].startswith('range_lock_') for x in decisions),minutes_locked=int(eq.lock_active.sum()),opposite_brick_exit_signals=flips,entry_brick_policy='FIRST qualifying brick in each known observation batch; price/ATM use actual observed spot close')
(ROOT/'results.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
print(json.dumps(summary,indent=2,default=str))

