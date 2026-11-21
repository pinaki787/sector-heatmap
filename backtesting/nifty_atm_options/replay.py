"""Offline option-candle replay. No broker, service, order or runner objects."""
import bisect,copy,datetime,hashlib,itertools,json,math,sys
from pathlib import Path
from zoneinfo import ZoneInfo
from expiry_calendar import expected_weekly_expiry
IST=ZoneInfo('Asia/Kolkata');SECONDS=300;LOT=65;CAPITAL=100000.;SLIPPAGE=.0005

def aggregate(rows,minutes):
 buckets={}
 for r in rows:
  t=datetime.datetime.fromtimestamp(r['timestamp'],IST);anchor=t.replace(hour=9,minute=15,second=0,microsecond=0).timestamp();start=int(anchor+(r['timestamp']-anchor)//(minutes*60)*minutes*60);buckets.setdefault(start,[]).append(r)
 result=[]
 for start,rs in sorted(buckets.items()):
  if len(rs)!=minutes//5 or any(r['timestamp']!=start+i*300 for i,r in enumerate(rs)):continue
  result.append(dict(timestamp=start,open=rs[0]['open'],high=max(r['high'] for r in rs),low=min(r['low'] for r in rs),close=rs[-1]['close'],volume=sum(r['volume'] for r in rs)))
 return result

def atm_strike(price):return float(math.floor(price/50+.5)*50)

def fixed_quote(quotes,timestamp,side,strike,expected_expiry=None):
 # The key is frozen at entry. There is deliberately no rolling-ATM fallback.
 q=quotes.get((int(timestamp),side,float(strike)))
 if q is not None and expected_expiry is not None:
  expiry=q.get('expected_expiry') or expected_weekly_expiry(datetime.datetime.fromtimestamp(timestamp,IST).date())
  if expiry!=expected_expiry:return None
 return q

def load_quotes(directories):
 quotes={};conflicts=set();invalid=offsession=0;files=0
 from strategies.renko_supertrend.costs import fee
 for directory in directories:
  for path in sorted(Path(directory).glob('*.json')):
   obj=json.loads(path.read_text())
   if 'request' not in obj or not isinstance(obj.get('data'),dict):continue
   d=obj['data'];side=obj['request']['drvOptionType'];files+=1
   fields=('open','high','low','close','strike','volume')
   if any(len(d.get(k,[]))!=len(d.get('timestamp',[])) for k in fields):raise ValueError('Unequal option arrays: '+path.name)
   for i,ts in enumerate(d['timestamp']):
    time=datetime.datetime.fromtimestamp(ts,IST);minute=time.hour*60+time.minute
    if not 555<=minute<930:offsession+=1;continue
    q={k:d[k][i] for k in fields}
    if not all(isinstance(q[k],(int,float)) and math.isfinite(q[k]) for k in fields) or min(q[k] for k in ('open','high','low','close','strike'))<=0 or not q['low']<=min(q['open'],q['close'])<=max(q['open'],q['close'])<=q['high']:invalid+=1;continue
    key=(int(ts),side,float(q['strike']))
    if key in quotes and any(abs(quotes[key][k]-q[k])>.051 for k in ('open','high','low','close')):conflicts.add(key)
    buy=q['open']*(1+SLIPPAGE);sell=q['open']*(1-SLIPPAGE)
    q.update(expected_expiry=expected_weekly_expiry(time.date()),buy=buy,sell=sell,buy_fee=fee(buy*LOT,'BUY',exchange_rate=.000355299)['total'],sell_fee=fee(sell*LOT,'SELL',exchange_rate=.000355299)['total'],close_sell_fee=fee(q['close']*(1-SLIPPAGE)*LOT,'SELL',exchange_rate=.000355299)['total'])
    quotes.setdefault(key,q)
 for key in conflicts:quotes.pop(key,None)
 return quotes,dict(files=files,unique_quotes=len(quotes),conflicts=len(conflicts),invalid_candles=invalid,offsession_rows=offsession)

def metrics(trades,curve):
 wins=[t['net'] for t in trades if t['net']>0];losses=[-t['net'] for t in trades if t['net']<0];peak=0.;dd=0.;streak=worst=0
 for value in curve:peak=max(peak,value);dd=max(dd,peak-value)
 for t in trades:
  streak=streak+1 if t['net']<0 else 0;worst=max(worst,streak)
 return dict(trades=len(trades),wins=len(wins),losses=len(losses),win_rate=len(wins)/len(trades) if trades else None,gross=sum(t['gross'] for t in trades),estimated_fees=sum(t['fees'] for t in trades),net=sum(t['net'] for t in trades),stress_net=sum(t['stress_net'] for t in trades),very_stress_net=sum(t['very_stress_net'] for t in trades),raw_gross=sum(t['raw_gross'] for t in trades),slippage_cost=sum(t['slippage_cost'] for t in trades),expectancy=sum(t['net'] for t in trades)/len(trades) if trades else None,profit_factor=sum(wins)/sum(losses) if losses else None,max_drawdown=dd,largest_win=max(wins,default=0),largest_loss=-max(losses,default=0),average_win=sum(wins)/len(wins) if wins else None,average_loss=-sum(losses)/len(losses) if losses else None,max_consecutive_losses=worst,calls=sum(t['side']=='CALL' for t in trades),puts=sum(t['side']=='PUT' for t in trades))

def simulate(rows,signals,quotes,entry_config,risk,zone_timeline,rsi_context,period_days,keep_trades=False):
 from strategies.renko_supertrend import sideways,trailing_stop,ema_proximity,zone_target
 c=dict(entry_config,sideways_enabled=risk['sideways'],sideways_max_candles=2,trailing_enabled=risk['trailing'],trailing_basis='OPTION_PREMIUM_PERCENT',trailing_distance=10.,execution_route='OPTIONS')
 period_of={d:name for name,days in period_days.items() for d in days};trades={k:[] for k in period_days};curves={k:[] for k in period_days};realized={k:0. for k in period_days};problems=[];p=None;pending=None;lock=None;rearm=False;last_exit=-1;boundary=-1;day=None;used=0;entry_skips=0
 def close(q,at,why):
  nonlocal p,lock,rearm,last_exit
  sell=q['sell'];gross=(sell-p['buy'])*LOT;fees=p['buy_fee']+q['sell_fee'];net=gross-fees
  # Fixed-trade-path sensitivity, additional 0.15% per side. Not a risk-path rerun.
  stress=net-(p['raw_buy']+q['open'])*LOT*.0015
  trade=dict(entry_signal_at=p['signal_at'],entry_at=p['entry_at'],exit_at=at,side=p['side'],strike=p['strike'],expiry_series='WEEK1_SAME_SESSION',expected_expiry=p['expected_expiry'],expiry_basis='NSE calendar-derived; broker expiry date unavailable',quantity=LOT,buy=p['buy'],sell=sell,raw_gross=(q['open']-p['raw_buy'])*LOT,slippage_cost=((q['open']-p['raw_buy'])*LOT-gross),gross=gross,fees=fees,net=net,stress_net=stress,very_stress_net=net-(p['raw_buy']+q['open'])*LOT*.0045,exit_reason=why,holding_minutes=(at-p['entry_at'])/60,entry_indicators=p['entry_indicators'])
  name=period_of[p['day']];trades[name].append(trade);realized[name]+=net
  lock=sideways.freeze(p['exposure'],at,net,300,c,str(len(trades[name])),'NSE:NIFTY50-INDEX') if risk['sideways'] else None
  p=None;rearm=True;last_exit=at
 for i,(r,s) in enumerate(zip(rows,signals)):
  at=r['timestamp'];date=r.get('_day') or datetime.datetime.fromtimestamp(at,IST).date().isoformat();name=period_of.get(date)
  if name is None:continue
  minute=r.get('_minute')
  if minute is None:
   clock=datetime.datetime.fromtimestamp(at,IST);minute=clock.hour*60+clock.minute
  if date!=day:
   if p:problems.append(dict(type='OVERNIGHT_UNPRICED',at=at));break
   day=date;used=0;boundary=at;pending=None;rearm=False
  exited=False
  if p:
   q=fixed_quote(quotes,at,p['side'],p['strike'],p['expected_expiry'])
   if q is None:problems.append(dict(type='MISSING_HELD_CONTRACT',at=at,side=p['side'],strike=p['strike']));break
   p['exposure']=sideways.observe(p['exposure'],p['entry_at'],r['open'],at,at)
   if minute>=915 or pending and pending['action']=='EXIT':
    close(q,at,'SESSION_EXIT' if minute>=915 else pending['reason']);pending=None;exited=True
   elif risk['trailing']:
    state,hit=trailing_stop.advance(p.get('trail'),c,'BULLISH' if p['side']=='CALL' else 'BEARISH',q['open'],at,at,at,p['entry_at']);p['trail']=state
    if hit:close(q,at,'SAMPLED_PREMIUM_TRAILING');exited=True
  if lock:
   reason=sideways.breakout(lock,r['open'],at,at)
   if reason:lock=None;boundary=at;rearm=False
  if pending and pending['action']=='ENTRY' and not p and not exited:
   desired=pending;pending=None
   if at!=desired['expected'] or minute>=915 or used>=2 or lock:continue
   if risk['proximity']:
    try:
     # Current open is the sampled fresh price. Live EMA is updated from the last completed EMA.
     live=desired['ema10']+2/11*(r['open']-desired['ema10']);ema_proximity.check(dict(c,ema_proximity_enabled=True,ema_proximity_mode='ATR',ema_proximity_distance=.5),r['open'],live,desired['host_atr'])
    except ValueError:entry_skips+=1;continue
   side='CALL' if desired['direction']=='BULLISH' else 'PUT';strike=atm_strike(r['open']);q=fixed_quote(quotes,at,side,strike)
   if q is None:problems.append(dict(type='MISSING_ENTRY_CONTRACT',at=at,side=side,strike=strike));break
   prior_quote=fixed_quote(quotes,at-300,side,strike)
   if prior_quote is None:problems.append(dict(type='MISSING_PRE_ENTRY_CONTRACT',at=at-300,side=side,strike=strike));break
   if prior_quote['volume']<=0:entry_skips+=1;continue
   equity=CAPITAL+sum(realized.values())
   if q['buy']*LOT+q['buy_fee']>equity:entry_skips+=1;continue
   p=dict(side=side,strike=strike,expected_expiry=q.get('expected_expiry') or expected_weekly_expiry(datetime.datetime.fromtimestamp(at,IST).date()),entry_at=at,signal_at=desired['signal_at'],day=date,buy=q['buy'],raw_buy=q['open'],buy_fee=q['buy_fee'],entry_indicators=desired['indicators'],exposure=sideways.observe(None,at,r['open'],at,at));used+=1;rearm=False
   if risk['trailing']:p['trail'],_=trailing_stop.advance(None,c,desired['direction'],q['open'],at,at,at,at)
  # All decisions below occur after this host bar closes; fills are at the next contiguous open.
  event=at+300
  if p:
   direction='BULLISH' if p['side']=='CALL' else 'BEARISH';opposite='BEARISH' if direction=='BULLISH' else 'BULLISH';why=None
   if risk['exit']=='ST' and s.get('raw_supertrend_cross_direction')==opposite:why='ST_REVERSAL'
   if risk['exit'] in ('EMA10','EMA30'):
    ema=s['ema10'] if risk['exit']=='EMA10' else s['ema30']
    if r['close']<ema if direction=='BULLISH' else r['close']>ema:why=risk['exit']+'_CONFIRMED_BREACH'
   if risk['contraction'] and i and abs(s['ema_gap'])<abs(signals[i-1]['ema_gap']):why=why or 'EMA_GAP_CONTRACTION'
   if risk['zones'] and i:
    result=zone_target.assess_known(r,rows[i-1],zone_timeline[i-1],{'direction':direction,'opened_at':p['entry_at']},event)
    why=why or result['reason']
   if why:pending=dict(action='EXIT',reason=why)
  elif not exited and not lock and used<2 and minute<910 and event>boundary:
   direction=s['entry_direction']
   if rearm and s['entry_qualified'] and event>last_exit:direction=s['direction']
   if direction and risk['rsi_mtf']:
    times,values=rsi_context;j=bisect.bisect_right(times,event)-1;bull=direction=='BULLISH';passing=j>=0 and 0<=event-times[j]<1800
    if passing:
     h=values[j];passing=h['rsi14'] is not None and h['rsi14_slope'] is not None and (h['rsi14']>50 and h['rsi14_slope']>0 if bull else h['rsi14']<50 and h['rsi14_slope']<0)
    if not passing:direction=None
   if direction and risk['proximity']:
    try:ema_proximity.check(dict(c,ema_proximity_enabled=True,ema_proximity_mode='ATR',ema_proximity_distance=.5),r['close'],s['ema10'],s['host_atr'])
    except ValueError:direction=None
   if direction:
    pending=dict(action='ENTRY',direction=direction,signal_at=event,expected=event,ema10=s['ema10'],host_atr=s['host_atr'],indicators={k:s.get(k) for k in ('direction','ema10','ema30','rsi14','rsi14_slope','adx','host_atr')})
  mark=0.
  if p:
   q=fixed_quote(quotes,at,p['side'],p['strike'],p['expected_expiry'])
   # Close mark is historical premium, not executable bid. Charge provision uses open fee as an estimate.
   mark=(q['close']*(1-SLIPPAGE)-p['buy'])*LOT-p['buy_fee']-q.get('close_sell_fee',q['sell_fee'])
  curves[name].append(realized[name]+mark)
 if p and not problems:problems.append(dict(type='UNRESOLVED_FINAL_POSITION',at=rows[-1]['timestamp']))
 result=dict(metrics={name:metrics(trades[name],curves[name]) for name in period_days},valid=not problems,problems=problems,entry_skips=entry_skips)
 if keep_trades:result['trades']=trades;result['equity']=curves
 return result
