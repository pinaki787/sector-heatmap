"""Causal completed-unit basis; candle indicator is committed once per host.
Live observations build only their own forming OHLC. A completed price brick
evaluates a copy of the last committed candle state, never feeds a synthetic
brick into AIRenko, and never advances its RMA once per tick.
"""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
import math
IST=ZoneInfo('Asia/Kolkata')
def bucket(engine,stamp):
 seconds=engine.config['timeframe']*60
 local=datetime.fromtimestamp(stamp,IST)
 opening=engine.config.get('opening_minutes',540 if engine.config.get('market')=='MCX' else 555 if engine.config.get('market') in ('NSE','BSE') else 0)
 anchor=local.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()+opening*60
 return anchor+math.floor((stamp-anchor)/seconds)*seconds

def attributes(engine,kind):
 if kind=='underlying':return engine.under_renko,engine.under_ai,'under_result'
 return engine.option_renko,engine.option_ai,'premium_result'

def store(engine):
 if not hasattr(engine,'hybrid_hosts'):engine.hybrid_hosts={}
 return engine.hybrid_hosts

def record_signal(engine,event,kind,bar,result):
 if engine.config.get('supertrend_basis')!='COMPLETED_RENKO':return
 symbol=engine.config['underlying'] if kind=='underlying' else engine.contract['symbol']
 if kind=='underlying':
  from strategies.nifty_ai_options.swing_targets import book
  available=event.get('available_at',event.get('closed_at',event.get('timestamp',0)))
  book(engine).observe(bar,available);engine.swing_observed_at=available
 if not hasattr(engine,'completed_signal_queue'):engine.completed_signal_queue=[]
 if not hasattr(engine,'completed_signal_counts'):engine.completed_signal_counts={}
 index=engine.completed_signal_counts.get(symbol,0)+1;engine.completed_signal_counts[symbol]=index
 stamp=event.get('timestamp')
 engine.completed_signal_queue.append(dict(symbol=symbol,index=index,source_time=stamp,available_at=event.get('available_at',event.get('closed_at',stamp+engine.config['timeframe']*60)),open=bar['open'],high=bar['high'],low=bar['low'],close=bar['close'],st=result.get('st'),direction=result.get('direction'),midline=result.get('midline'),midline_period=result.get('midline_period'),brick=engine.spot_size if kind=='underlying' else engine.contract['option_brick']))

def seed(engine,event,kind):
 renko,ai,field=attributes(engine,kind)
 bars=renko.update(event['close'])
 store(engine)[kind]=dict(frame=engine.config['timeframe'],confirmed_at=event['timestamp'],forming=None,waiting=False)
 return bars

def price(engine,event,kind,*,indicator=True):
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (event.get('timestamp'),event.get('available_at'),event.get('close'))) or event['timestamp']>event['available_at']:
  raise ValueError('Exact causal broker price required')
 renko,ai,field=attributes(engine,kind)
 state=store(engine).setdefault(kind,dict(confirmed_at=engine.last_time.get(kind),forming=None,waiting=False))
 if state.get('frame',engine.config['timeframe'])!=engine.config['timeframe']:
  state.update(confirmed_at=None,forming=None,frame=engine.config['timeframe'],waiting=True)
 start=bucket(engine,event['timestamp']);seconds=engine.config['timeframe']*60
 prior=state.get('forming')
 if prior and start<prior['start']:raise ValueError('Hybrid price precedes current forming candle')
 value=event['close']
 if not prior or start!=prior['start']:
  state['forming']=dict(start=start,open=value,high=value,low=value,close=value)
 else:
  prior.update(high=max(prior['high'],value),low=min(prior['low'],value),close=value)
 # Do not skip an unconfirmed source candle while evaluating next-host prices.
 # The last complete broker candle must cover the previous active interval.
 confirmed=state.get('confirmed_at')
 state['waiting']=confirmed is None or start>confirmed+seconds
 if state['waiting']:return [],None
 bars=renko.update(value)
 if not bars:return [],None
 if not indicator:
  for bar in bars:record_signal(engine,event,kind,bar,{})
  return bars,None
 if engine.config.get('supertrend_basis')=='COMPLETED_RENKO':
  previous=getattr(engine,field,None)
  for bar in bars:
   result=ai.update(bar)
   result['flip']=bool(previous and previous['direction']!=result['direction'])
   result['decision_basis']='COMPLETED_RENKO_BRICK'
   result['host_committed']=True
   bar['_signal_result']=dict(result)
   record_signal(engine,event,kind,bar,result)
   previous=result
  return bars,result
 forming=state['forming']
 probe=deepcopy(ai)
 result=probe.update({k:forming[k] for k in ('open','high','low','close')})
 previous=getattr(engine,field,None)
 result['flip']=bool(previous and previous['direction']!=result['direction'])
 result['decision_basis']='COMPLETED_RENKO_BRICK'
 result['host_committed']=False
 return bars,result

def confirmed(engine,event,kind):
 closed=event.get('closed_at');available=event.get('available_at')
 if event.get('closed') is not True or not isinstance(closed,(int,float)) or not isinstance(available,(int,float)) or not event['timestamp']<closed<=available:
  raise ValueError('Completed provider candle availability required')
 renko,ai,field=attributes(engine,kind)
 if engine.config.get('supertrend_basis')=='COMPLETED_RENKO':
  previous=getattr(engine,field,None)
  bars=renko.update(event['close'])
  for bar in bars:
   result=ai.update(bar)
   result['flip']=bool(previous and previous['direction']!=result['direction'])
   result['decision_basis']='COMPLETED_RENKO_BRICK'
   result['host_committed']=True
   bar['_signal_result']=dict(result)
   record_signal(engine,event,kind,bar,result)
   previous=result
  state=store(engine).setdefault(kind,dict(forming=None))
  state.update(frame=engine.config['timeframe'],confirmed_at=event['timestamp'],waiting=False,confirmed_bricks=bars)
  return dict(previous,flip=bool(bars and getattr(engine,field,None) and previous['direction']!=getattr(engine,field)['direction'])) if previous else None
 result=ai.update({k:event[k] for k in ('open','high','low','close')})
 previous=getattr(engine,field,None)
 result['flip']=bool(previous and previous['direction']!=result['direction'])
 result['decision_basis']='COMPLETED_SMALL_CANDLE_BODY'
 result['host_committed']=True
 state=store(engine).setdefault(kind,dict(forming=None))
 state.update(frame=engine.config['timeframe'],confirmed_at=event['timestamp'],waiting=False)
 return result

def brick_event(event,units):
 if not units:return event
 unit=units[-1]
 if unit.get('kind')!='brick':return event
 return dict(event,hybrid_completed_brick=dict(unit))
