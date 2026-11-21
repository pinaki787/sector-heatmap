"""Offline research of current production Renko formulas. Never instantiates a runner."""
import sys,json,pathlib,datetime,math,pickle,gzip,hashlib,copy,argparse,csv
from collections import defaultdict,Counter
from zoneinfo import ZoneInfo
ROOT=pathlib.Path('/home/trading/sector-heatmap');OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backtesting/nifty_atm_options'))
from strategies.renko_supertrend.signals import Engine
from strategies.renko_supertrend import sideways,ema_proximity,exit_indicators,trailing_stop
from strategies.renko_supertrend.costs import fee
from expiry_calendar import expected_weekly_expiry
Z=ZoneInfo('Asia/Kolkata');LOT=65;CAPITAL=100000
def clock(ts):return datetime.datetime.fromtimestamp(ts,Z)
def aggregate(rows,n):
 buckets=defaultdict(list)
 for r in rows:
  t=clock(r['timestamp']);anchor=int(t.replace(hour=9,minute=15,second=0,microsecond=0).timestamp());start=anchor+(r['timestamp']-anchor)//(n*60)*(n*60);buckets[start].append(r)
 result=[]
 for start,rs in sorted(buckets.items()):
  if len(rs)!=n or any(r['timestamp']!=start+i*60 for i,r in enumerate(rs)):continue
  result.append(dict(timestamp=start,open=rs[0]['open'],high=max(r['high'] for r in rs),low=min(r['low'] for r in rs),close=rs[-1]['close'],volume=sum(r['volume'] for r in rs)))
 return result
def configs(base):
 yield 'saved_5m_15m',{}
 yield 'prior_1m_5m',{'timeframe':'1 minute','supertrend_timeframe':'5 minutes'}
 yield 'host_3m_15m',{'timeframe':'3 minutes','supertrend_timeframe':'15 minutes'}
 for key,vs in [('factor',[2.,2.5,3.5,4.]),('atr_length',[7,10,14]),('manual_brick',[12.5,20.,30.,40.]),('widening_window',[3,4]),('ema_proximity_distance',[.25,.75,1.]),('sideways_max_candles',[3,4]),('supertrend_timeframe',['30 minutes','1 hour'])]:
  for v in vs:yield key+'_'+str(v),{key:v}
 for v in [20.,25.,30.]:yield 'ADX_'+str(v),{'use_adx':True,'adx_threshold':v}
 yield 'retest_off',{'retest_enabled':False}
 yield 'sideways_off',{'sideways_enabled':False}
 yield 'HTF_off',{'higher_timeframe_enabled':False}
 yield 'RSI_slope_only',{'rsi_level_enabled':False}
 yield 'RSI_wider',dict(rsi_bullish_min=55.,rsi_bullish_max=75.,rsi_bearish_min=25.,rsi_bearish_max=45.)
 yield 'EMA_8_21',dict(ema_fast_length=8,ema_slow_length=21,ema_exit_length=21,retest_enabled=False)
 yield 'EMA_13_50',dict(ema_fast_length=13,ema_slow_length=50,ema_exit_length=50,retest_enabled=False)
 yield 'ST_exit_only',dict(ema_exit_enabled=False,ema_slow_exit_enabled=False)
 yield 'EMA10_exit',dict(ema_exit_length=10,ema_slow_exit_enabled=False)
 yield 'gap_contraction_exit',{'ema_widening_exit_enabled':True}
 yield 'trailing_10pct',dict(trailing_enabled=True,trailing_basis='OPTION_PREMIUM_PERCENT',trailing_distance=10.)
 yield 'combo_ADX25_widen3',dict(use_adx=True,adx_threshold=25.,widening_window=3)
 yield 'combo_ADX25_proximity025',dict(use_adx=True,adx_threshold=25.,ema_proximity_distance=.25)
def load_spot():
 raw=json.loads((OUT/'underlying.json').read_text())['rows'];unique={};dups=bad=off=0
 for r in raw:
  if r[0] in unique:dups+=1;continue
  t=clock(r[0]);m=t.hour*60+t.minute
  if not 555<=m<930:off+=1;continue
  if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in r) or min(r[1:5])<=0 or not r[3]<=min(r[1],r[4])<=max(r[1],r[4])<=r[2]:bad+=1;continue
  unique[r[0]]=dict(zip(('timestamp','open','high','low','close','volume'),r))
 rows=[unique[k] for k in sorted(unique)];by=defaultdict(list)
 for r in rows:by[clock(r['timestamp']).date().isoformat()].append(r)
 full=[d for d,rs in sorted(by.items()) if len(rs)==375 and all(b['timestamp']-a['timestamp']==60 for a,b in zip(rs,rs[1:])) and clock(rs[0]['timestamp']).strftime('%H:%M')=='09:15' and clock(rs[-1]['timestamp']).strftime('%H:%M')=='15:29']
 days=full[-30:]
 if len(days)<30:raise ValueError('Fewer than 30 complete underlying sessions')
 audit=dict(provider='FYERS',days=days,full_sessions=len(full),duplicates=dups,invalid=bad,offsession=off,incomplete_sessions={d:len(rs) for d,rs in by.items() if d not in full},daily_counts={d:len(by[d]) for d in days})
 return rows,days,audit
def prepare():
 rows,days,audit=load_spot();state=ROOT/'.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/source/.private/renko-instances/9abcfe9c2d417c1e7efe/state.json'
 base=json.loads((OUT/'saved-config.json').read_text()) if (OUT/'saved-config.json').exists() else json.loads(state.read_text())['config'];(OUT/'saved-config.json').write_text(json.dumps(base,indent=2));base.pop('indicator_family_choices',None);base.pop('indicator_family_applied',None)
 grid=[]
 for name,delta in configs(base):
  c={**base,**delta,'chart_entry_guards':True,'session_deadline':'15:10'};n=int(c['timeframe'].split()[0]);h=60 if c['supertrend_timeframe']=='1 hour' else int(c['supertrend_timeframe'].split()[0])
  c['_chart_higher_rows']=aggregate(rows,h);host=aggregate(rows,n);cache=OUT/(name+'.pkl.gz')
  clean={k:v for k,v in c.items() if not k.startswith('_')};grid.append({'name':name,'changes':delta,'config':clean})
  if cache.exists():
   with gzip.open(cache,'rb') as f:cached=pickle.load(f)
   if cached[2]==clean:continue
  eng=Engine(c,.05);signals=[eng.update(r) for r in host]
  # Prefix checks, with higher-timeframe rows restricted to the known prefix.
  cut=len(host)//2;pc={**c,'_chart_higher_rows':[r for r in c['_chart_higher_rows'] if r['timestamp']+h*60<=host[cut-1]['timestamp']+n*60]};pe=Engine(pc,.05);prefix=[pe.update(r) for r in host[:cut]]
  keys=['direction','entry_direction','entry_qualified','rsi14','ema10','ema30','adx','supertrend']
  assert all(prefix[-1].get(k)==signals[cut-1].get(k) for k in keys),'Future leakage'
  clean={k:v for k,v in c.items() if not k.startswith('_')}
  with gzip.open(OUT/(name+'.pkl.gz'),'wb') as f:pickle.dump((host,signals,clean),f)
  print('Prepared',name,flush=True)
 plan=dict(scope='Thirty complete trading sessions, one lot, ATM nearest-week at entry, fixed strike until exit, call/put buying only, no manual overrides.',data=audit,development=days[:20],validation=days[20:],selection='Development only: >=8 trades, positive net at 0.2% slippage/side, positive call AND put net, positive in both development halves. Rank stress net minus 0.5*sampled drawdown. Validation never replaces failed selected winner. Require >=5 validation trades and positive stress net and both sides before paper consideration; low sample never live-ready.',variants=grid,source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'strategies/renko_supertrend').glob('*.py')},limitations=['Chronological validation overlaps dates examined in prior research; not pristine unseen evidence.','Manual brick numeric candidates fixed over history; saved 24.92 was configured later, retrospective comparison only.','Production formulas reused rather than alternate indicator libraries.','9:15 daily arming with historical warmup; first entry after completed host candle; no stale prior-session entry.','Daily quota reset to saved max_trades models user daily start, unlike a continuous lifetime quota.','Bid/ask and tick path unavailable; use next contiguous minute open, no synthetic option prices.','Quick-loss range uses observed minute opens, approximate versus live ticks.','Slippage scenarios rerun exits and trailing paths.','No live config, schedule, runner or order mutations.'])
 (OUT/'plan.json').write_text(json.dumps(plan,indent=2));print('Preparation complete',len(grid),audit['days'][0],audit['days'][-1],flush=True)
def load_quotes():
 quotes={};conflict=set();bad=off=0
 for f in sorted((OUT/'options').glob('*.json')):
  o=json.loads(f.read_text());d=o['data'];side=o['request']['drvOptionType'];fields=['open','high','low','close','volume','strike']
  assert all(len(d[k])==len(d['timestamp']) for k in fields)
  for i,ts in enumerate(d['timestamp']):
   t=clock(ts);m=t.hour*60+t.minute
   if not 555<=m<930:off+=1;continue
   q={k:d[k][i] for k in fields}
   if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in q.values()) or min(q[k] for k in ['open','high','low','close','strike'])<=0 or not q['low']<=min(q['open'],q['close'])<=max(q['open'],q['close'])<=q['high']:bad+=1;continue
   key=(int(ts),side,float(q['strike']))
   if key in quotes and any(abs(q[k]-quotes[key][k])>.051 for k in ['open','high','low','close']):conflict.add(key)
   else:quotes.setdefault(key,q)
 for k in conflict:quotes.pop(k,None)
 return quotes,dict(provider='Dhan expired nearest-week rolling strike history, reconstructed fixed strike',quotes=len(quotes),conflicts=len(conflict),invalid=bad,offsession=off)
def measure(trades,curve):
 vals=[t['net'] for t in trades];g=sum(v for v in vals if v>0);l=-sum(v for v in vals if v<0);peak=dd=0.;streak=worst=0
 for x in curve:peak=max(peak,x);dd=max(dd,peak-x)
 for v in vals:streak=streak+1 if v<0 else 0;worst=max(worst,streak)
 daily=defaultdict(float)
 for t in trades:daily[t['day']]+=t['net']
 return dict(trades=len(vals),net=sum(vals),gross=sum(t['gross'] for t in trades),fees=sum(t['fees'] for t in trades),win_rate=sum(v>0 for v in vals)/len(vals) if vals else None,profit_factor=g/l if l else None,expectancy=sum(vals)/len(vals) if vals else None,max_drawdown=dd,largest_win=max([v for v in vals if v>0],default=0),largest_loss=min([v for v in vals if v<0],default=0),max_consecutive_losses=worst,calls=sum(t['net'] for t in trades if t['side']=='CALL'),puts=sum(t['net'] for t in trades if t['side']=='PUT'),call_trades=sum(t['side']=='CALL' for t in trades),put_trades=sum(t['side']=='PUT' for t in trades),positive_days=sum(v>0 for v in daily.values()),active_days=len(daily),worst_day=min(daily.values(),default=0))
def simulate(minute,host,signals,c,quotes,days,slip):
 n=int(c['timeframe'].split()[0]);step=n*60;hs={r['timestamp']+step:(r,s) for r,s in zip(host,signals)}
 p=None;pending=None;lock=None;rearm=False;last_exit=-1;day=None;used=0;trades=[];curve=[];problems=[];skips=Counter();realized=0.;lastsig=None;previous_gap=None;boundary=0
 def close(q,at,why):
  nonlocal p,realized,lock,rearm,last_exit
  sell=q['open']*(1-slip);gross=(sell-p['buy'])*LOT;fees=p['buy_fee']+fee(sell*LOT,'SELL',exchange_rate=.000355299)['total'];net=gross-fees
  trades.append({k:v for k,v in p.items() if k not in ('exposure','trail')}|dict(exit_at=at,sell=sell,exit_reason=why,gross=gross,fees=fees,net=net,holding_minutes=(at-p['entry_at'])/60))
  realized+=net;lock=sideways.freeze(p['exposure'],at,net,step,c,str(len(trades)),'NSE:NIFTY50-INDEX') if c['sideways_enabled'] else None;p=None;rearm=True;last_exit=at
 for r in minute:
  at=r['timestamp'];dt=clock(at);d=dt.date().isoformat();m=dt.hour*60+dt.minute
  if d not in days:continue
  if d!=day:
   if p:problems.append({'type':'UNPRICED_OVERNIGHT','at':at});break
   day=d;used=0;pending=None;rearm=False;lock=None;lastsig=None;previous_gap=None;boundary=int(dt.replace(hour=9,minute=15,second=0,microsecond=0).timestamp())
  exited=False
  q=quotes.get((at,p['side'],p['strike'])) if p else None
  if p and not q:problems.append({'type':'MISSING_HELD_CONTRACT','at':at,'side':p['side'],'strike':p['strike']});break
  if p:
   p['exposure']=sideways.observe(p['exposure'],p['entry_at'],r['open'],at,at)
   if m>=910 or pending and pending['action']=='EXIT':
    close(q,at,'SESSION_EXIT_1510' if m>=910 else pending['reason']);pending=None;exited=True
   elif c.get('trailing_enabled'):
    p['trail'],hit=trailing_stop.advance(p.get('trail'),c,'BULLISH' if p['side']=='CALL' else 'BEARISH',q['open']*(1-slip),at,at,at,p['entry_at'])
    if hit:close(q,at,'SAMPLED_TRAILING');exited=True
  if lock and sideways.breakout(lock,r['open'],at,at):lock=None;rearm=False;boundary=at
  if at in hs:
   bar,s=hs[at];lastsig=s
   if d!=clock(bar['timestamp']).date().isoformat():continue
   if p:
    direction='BULLISH' if p['side']=='CALL' else 'BEARISH';exit_ema=s.get('ema_exit',s['ema30']);reason=None
    # Projection EMA in Engine uses configured ema_exit_length. Compute separately below.
    if c.get('ema_exit_enabled') and (bar['close']<s['_exit_ema'] if direction=='BULLISH' else bar['close']>s['_exit_ema']):reason='EMA_CONFIRMED_BREACH'
    reason=reason or exit_indicators.reason(c,{**s,'close':bar['close'],'supertrend_cross_direction':s.get('raw_supertrend_cross_direction'),'exit_previous_ema_gap':previous_gap},direction)
    if reason:
     q=quotes.get((at,p['side'],p['strike']))
     if q:close(q,at,reason);exited=True
   elif not exited and not lock and used<c['max_trades'] and m<910 and at>boundary:
    direction=s.get('entry_direction')
    if rearm and s['entry_qualified'] and bar['timestamp']>last_exit:direction=s['direction']
    if direction:pending=dict(action='ENTRY',direction=direction,signal_at=at,expected=at,signal=s)
   previous_gap=s.get('ema_gap')
  if pending and pending['action']=='ENTRY' and not p and not exited:
   want=pending;pending=None;s=want['signal'];side='CALL' if want['direction']=='BULLISH' else 'PUT';strike=float(math.floor(r['open']/50+.5)*50)
   q=quotes.get((at,side,strike));prior=quotes.get((at-60,side,strike))
   if not q or not prior:problems.append({'type':'MISSING_ENTRY_CONTRACT','at':at,'side':side,'strike':strike});break
   if prior['volume']<=0:skips['ZERO_PRIOR_VOLUME']+=1;continue
   try:ema_proximity.check(c,r['open'],s['ema10']+2/(c['ema_fast_length']+1)*(r['open']-s['ema10']),s['host_atr'])
   except ValueError:skips['PROXIMITY_AT_FILL']+=1;continue
   buy=q['open']*(1+slip);bf=fee(buy*LOT,'BUY',exchange_rate=.000355299)['total']
   if buy*LOT+bf>CAPITAL+realized:skips['FUNDS']+=1;continue
   p=dict(day=d,side=side,strike=strike,expected_expiry=expected_weekly_expiry(dt.date()),entry_at=at,signal_at=want['signal_at'],buy=buy,buy_fee=bf,entry_indicators={k:s.get(k) for k in ['rsi14','rsi14_slope','adx','ema10','ema30','ema_gap','host_atr','direction']},exposure=sideways.observe(None,at,r['open'],at,at));used+=1;rearm=False
   if c.get('trailing_enabled'):p['trail'],_=trailing_stop.advance(None,c,want['direction'],q['open']*(1-slip),at,at,at,at)
  mark=0
  if p:
   q=quotes.get((at,p['side'],p['strike']));mark=(q['close']*(1-slip)-p['buy'])*LOT-p['buy_fee']-fee(q['close']*(1-slip)*LOT,'SELL',exchange_rate=.000355299)['total']
  curve.append(realized+mark)
 if p and not problems:problems.append({'type':'OPEN_FINAL_POSITION'})
 return dict(valid=not problems,problems=problems,skips=dict(skips),metrics=measure(trades,curve),trades=trades,curve=curve)
def run():
 plan=json.loads((OUT/'plan.json').read_text());minute,days,audit=load_spot();quotes,qa=load_quotes();results=[]
 for v in plan['variants']:
  with gzip.open(OUT/(v['name']+'.pkl.gz'),'rb') as f:host,signals,c=pickle.load(f)
  ev=None;alpha=2/(c.get('ema_exit_length',30)+1)
  for r,s in zip(host,signals):ev=r['close'] if ev is None else alpha*r['close']+(1-alpha)*ev;s['_exit_ema']=ev
  item={'name':v['name'],'changes':v['changes'],'scenarios':{}}
  for label,slip in [('base',.0005),('stress',.002)]:
   item['scenarios'][label]={}
   for period,ds in [('development',days[:20]),('validation',days[20:])]:
    sim=simulate(minute,host,signals,c,quotes,set(ds),slip);item['scenarios'][label][period]=sim
  results.append(item)
  (OUT/'results.json').write_text(json.dumps({'plan':plan,'option_audit':qa,'results':results}))
  b=item['scenarios']['base'];print(v['name'],'valid',b['development']['valid'],b['validation']['valid'],'dev',round(b['development']['metrics']['net'],2),'val',round(b['validation']['metrics']['net'],2),flush=True)
 print('All replay variants complete',len(results),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','run']);a=p.parse_args();prepare() if a.stage=='prepare' else run()

