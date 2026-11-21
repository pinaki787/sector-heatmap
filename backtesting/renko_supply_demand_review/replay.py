"""One-minute underlying-price stop replay. No broker/order APIs."""
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backtesting/renko_regime_lifecycle'))
sys.path.insert(0,str(ROOT/'backtesting/renko_regime_calibration'))
from strategies.renko_supertrend.signals import Engine
from strategies.renko_supertrend import exit_indicators,ema_proximity,zone_target
from grid import gate
from review import stats as base_stats
IST=ZoneInfo('Asia/Kolkata')
EXITS={
 'SelectedExits':{},
 'Hard1ATR':dict(hard=1.),
 'Hard1_5ATR':dict(hard=1.5),
 'Hard2ATR':dict(hard=2.),
 'Trail1ATR':dict(hard=1.5,trail=1.,activation=1.),
 'Trail1_5ATR':dict(hard=2.,trail=1.5,activation=1.),
 'Trail2ATR':dict(hard=2.,trail=2.,activation=1.),
 'Breakeven1ATR':dict(hard=1.5,breakeven=1.),
 'Breakeven1_5ATR':dict(hard=2.,breakeven=1.5),
 'TrailAndBreakeven':dict(hard=2.,trail=1.5,activation=1.,breakeven=1.),
 'LossCooldown15m':dict(cooldown=900),
 'LossCooldown30m':dict(cooldown=1800),
 'LossCooldown60m':dict(cooldown=3600)}
def day(stamp):return datetime.fromtimestamp(stamp,IST).date().isoformat()
def stop_level(value,direction):
 rounding=ROUND_FLOOR if direction=='BULLISH' else ROUND_CEILING
 return float((Decimal(str(value))/Decimal('.05')).to_integral_value(rounding=rounding)*Decimal('.05'))
def stop_fill(position,bar):
 level=position.get('stop')
 if level is None:return None
 if position['direction']=='BULLISH':
  if bar['open']<=level:return bar['open'],'STOP_GAP_OPEN'
  if bar['low']<=level:return level,'STOP_TOUCHED'
 else:
  if bar['open']>=level:return bar['open'],'STOP_GAP_OPEN'
  if bar['high']>=level:return level,'STOP_TOUCHED'
 return None
def target_fill(position,bar):
 level=position.get('target')
 if level is None:return None
 if position['direction']=='BULLISH':
  if bar['high']>=level:return level,'TARGET_TOUCHED'
 else:
  if bar['low']<=level:return level,'TARGET_TOUCHED'
 return None
def update_stop(position,bar,rule,drag):
 sign=1 if position['direction']=='BULLISH' else -1
 position['favorable']=max(position['favorable'],sign*(bar['high' if sign>0 else 'low']-position['entry_price']))
 levels=[]
 if rule.get('trail') and position['favorable']>=rule['activation']*position['atr']:
  levels.append(position['entry_price']+sign*(position['favorable']-rule['trail']*position['atr']))
 if rule.get('breakeven') and position['favorable']>=rule['breakeven']*position['atr']:
  levels.append(position['entry_price']+sign*drag)
 for level in levels:
  level=stop_level(level,position['direction'])
  if position.get('stop') is None or sign*(level-position['stop'])>0:position['stop']=level
def stats(trades,drag=2):
 result=base_stats(trades,drag);streak=maximum=0
 for t in trades:
  streak=streak+1 if t['gross_points']-drag<=.0000001 else 0;maximum=max(maximum,streak)
 result['max_nonpositive_streak']=maximum
 return result
def simulate(hosts,minutes,config,entry_rule,exit_name,score_start,drag=2,entry_filter=None,recovery=False,rearm=False,zone_context=None,zone_exits=False,remove_atr_target=False):
 rule=dict(EXITS[exit_name])
 if remove_atr_target:rule.pop("target",None)
 engine=Engine(config,.05);history=[];index=0;position=None;used={};trades=[];cooldown_until=0;skipped=0
 lock=None
 closed=0.;curves=[];year_peaks={};year_start={};year_dd={}
 def finish(price,at,reason,interval_start=None):
  nonlocal position,closed,cooldown_until,lock
  sign=1 if position['direction']=='BULLISH' else -1
  gross=sign*(price-position['entry_price'])
  t=dict(position,exit_at=at,exit_price=price,reason=reason,gross_points=gross,exit_interval_start=interval_start)
  trades.append(t);closed+=gross-drag
  # Known full one-minute exposure ranges only; lock activates at the exit event.
  if recovery and gross-drag<0 and int((at if interval_start is None else interval_start)//300-position['entry_at']//300)+1<=2:
   lock=dict(high=position.get('high',position['entry_price']),low=position.get('low',position['entry_price']),at=at)
  if gross-drag<0 and rule.get('cooldown'):cooldown_until=at+rule['cooldown']
  position=None;engine.state['ema_qualified']=None
 for minute_index,bar in enumerate(minutes):
  if minute_index%5000==0 and (Path(__file__).parent/"CANCEL").exists():raise InterruptedError("Supply/demand replay cancelled.")
  at=bar['timestamp'];d=day(at);clock=datetime.fromtimestamp(at,IST);minute=clock.hour*60+clock.minute
  if position and minute>=910:finish(bar['open'],at,'SESSION_CUTOFF')
  while index<len(hosts) and hosts[index]['timestamp']+300<=at:
   host=hosts[index];index+=1
   sig=engine.update(host);history=(history+[sig])[-100:]
   if lock and host['timestamp']+300>lock['at'] and (host['close']>lock['high'] or host['close']<lock['low']):lock=None
   if position:
    reason=exit_indicators.reason(config,dict(sig,supertrend_cross_direction=sig.get('raw_supertrend_cross_direction')),position['direction'])
    if config.get('ema_exit_enabled') and (host['close']<sig['ema30'] if position['direction']=='BULLISH' else host['close']>sig['ema30']):reason=reason or 'EMA30_BREACH'
    if zone_exits:
     z=zone_context[host["timestamp"]]
     try:
      decision=zone_target.assess_known(host,z["previous"],z["before"],dict(direction=position["direction"],opened_at=position["entry_at"]),host["timestamp"]+300)
     except ValueError:
      decision=dict(reason=None,state="SOURCE_GAP")
     position["last_zone_assessment"]=decision
     reason=reason or decision.get("reason")
    if reason:finish(bar['open'],at,reason)
   elif sig.get('entry_direction') and host['timestamp']+300==at and minute<910 and used.get(d,0)<2 and at>=cooldown_until:
    if lock or not gate(history,entry_rule,sig['entry_direction']) or entry_filter is not None and not entry_filter(sig,bar["open"]):
     skipped+=1
     if rearm:engine.state['ema_qualified']=None
     continue
    try:ema_proximity.check(config,bar['open'],sig['ema10'],sig['host_atr'],sig,sig['entry_direction'])
    except ValueError:skipped+=1;continue
    sign=1 if sig['entry_direction']=='BULLISH' else -1
    position=dict(entry_at=at,entry_day=d,entry_price=bar['open'],direction=sig['entry_direction'],atr=sig['host_atr'],favorable=0.,
      stop=stop_level(bar['open']-sign*rule['hard']*sig['host_atr'],sig['entry_direction']) if rule.get('hard') else None)
    if rule.get('target'):
     # Profit levels round away from entry; no favorable gap fill is invented.
     other='BEARISH' if sign>0 else 'BULLISH'
     position['target']=stop_level(bar['open']+sign*rule['target']*sig['host_atr'],other)
    if zone_context is not None:
     from zones import entry_distance
     position["zone_at_entry"]=entry_distance(zone_context[host["timestamp"]]["after"],position["direction"],bar["open"],sig["host_atr"])
    used[d]=used.get(d,0)+1
  if position:
   position['high']=max(position.get('high',position['entry_price']),bar['high'])
   position['low']=min(position.get('low',position['entry_price']),bar['low'])
   hit=stop_fill(position,bar)
   if hit:finish(hit[0],at if hit[1]=='STOP_GAP_OPEN' else at+60,hit[1],interval_start=at)
   else:
    target=target_fill(position,bar)
    if target:finish(target[0],at+60,target[1],interval_start=at)
    else:update_stop(position,bar,rule,drag)
  if d>=score_start:
   year='earlier' if d<'2025-10-25' else 'latest'
   if year not in year_start:year_start[year]=closed;year_peaks[year]=0.;year_dd[year]=0.
   floating=(1 if position['direction']=='BULLISH' else -1)*(bar['close']-position['entry_price'])-drag if position else 0
   value=closed-year_start[year]+floating
   year_peaks[year]=max(year_peaks[year],value);year_dd[year]=max(year_dd[year],year_peaks[year]-value)
   if minute==929:curves.append(dict(day=d,closed_points=closed,marked_points=closed+floating))
 if position:raise ValueError('Unexpected open position at end of complete-session replay.')
 trades=[t for t in trades if t['entry_day']>=score_start]
 summaries={}
 for label in ('earlier','latest','all'):
  chosen=[t for t in trades if label=='all' or (t['entry_day']<'2025-10-25')==(label=='earlier')]
  summaries[label]={str(cost):stats(chosen,cost) for cost in (0,2,4)}
 return dict(entry=entry_rule,exit=exit_name,trades=trades,splits=summaries,minute_close_drawdown_by_year=year_dd,curve=curves,skipped=skipped)
