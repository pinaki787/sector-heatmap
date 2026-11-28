"""Retained confirmed Renko levels, profit touch, failed-retest continuation.
Pure strategy state: no broker, process or order API. Disabled for legacy runs.
"""
from copy import deepcopy
from pathlib import Path
import math
REVISION='retained-support-and-trailing-pullback-v2'
def finite(v):return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)
def support_enabled(e):return e.config.get('swing_targets_enabled',False) and e.config.get('swing_retest_required',False)
def enabled(e):return (support_enabled(e) or e.config.get('trailing_reentry_enabled',False)) and e.config.get('display_mode','RENKO')=='RENKO'
def direction(p):return 'LONG' if p.get('side') in ('LONG','CE') else 'SHORT'
def favorable(d,a,b):return a>b if d=='LONG' else a<b
def get(e):return getattr(e,'support_retest',None) if enabled(e) else None
class Policy:
 def __init__(self,engine,path=None):
  self.scope={k:engine.config.get(k) for k in ('account','underlying','runtime_session','reference_value')}
  self.path=Path(path) if path else None;self.wait=None;self.used=[];self.last_quote=None;self.proof=None;self.notice='WAITING_FOR_NEW_SIGNAL';self.touch_arms={};self.extreme=None
  if self.path and self.path.exists():
   saved=__import__('json').loads(self.path.read_text())
   if saved.get('scope')==self.scope:
    self.wait=saved.get('wait');self.used=saved.get('used',[]);self.notice=saved.get('notice',self.notice);self.touch_arms=saved.get('touch_arms',{});self.extreme=saved.get('extreme')
 def save(self):
  if self.path:
   from .run import atomic
   atomic(self.path,dict(revision=REVISION,scope=self.scope,wait=self.wait,used=self.used,notice=self.notice,touch_arms=self.touch_arms,extreme=self.extreme))
 def snapshot(self):return dict(revision=REVISION,enabled=True,state=self.notice,wait=deepcopy(self.wait),consumed_levels=len(self.used))
 def before(self,e,event,*,clear,warm=False):
  self.proof=None;e.support_execution_clear=bool(clear)
  if warm:return
  if self.wait and not clear:
   self.notice='WAITING_FOR_CONFIRMED_FLAT';return
  at=event.get('available_at');stamp=event.get('timestamp');price=event.get('close')
  if event.get('kind')!='price' or event.get('series')!='underlying' or event.get('source_basis')!='BROKER_LIVE_PRICE':return
  if event.get('symbol')!=e.config['underlying'] or not all(finite(v) for v in (at,stamp,price)) or not 0<=at-stamp<=10:return
  if self.last_quote is not None and stamp<=self.last_quote:return
  self.last_quote=stamp
  if not self.wait:return
  w=self.wait
  if at<=w['exit_requested_at']:return
  if w.get('kind')=='TRAIL_PULLBACK':
   if w.get('flat_confirmed_at') is None:
    w['flat_confirmed_at']=at;self.notice=w['phase'];self.save()
   return
  # A genuine departure beyond the target precedes a separate return to it.
  d=w['direction'];level=w['price'];tick=(getattr(e,'contract',{}) or {}).get('tick_size',0)
  tick=tick if finite(tick) and tick>0 else e.spot_size*1e-9
  phase=w.get('phase','WAITING_FOR_DEPARTURE')
  if phase=='WAITING_FOR_DEPARTURE' and favorable(d,price,level+(tick if d=='LONG' else -tick)):
   w.update(phase='WAITING_FOR_RETEST',departed_at=at);self.notice=w['phase'];self.save()
  elif phase=='WAITING_FOR_RETEST' and at>w['departed_at'] and (price<=level if d=='LONG' else price>=level):
   w.update(phase='WAITING_FOR_FAILED_RETEST_BRICK',retested_at=at);self.notice=w['phase'];self.save()
  elif phase=='WAITING_FOR_FAILED_RETEST_BRICK':self.notice=phase
 def observe_unit(self,e,unit,result):
  if getattr(e,'zone_replaying',False) or getattr(e,'entry_paused',False):return
  at=unit.get('available_at');closed=unit.get('closed_at')
  if unit.get('kind')!='brick' or unit.get('closed') is not True or unit.get('provisional') or unit.get('historyOnly'):return
  if not all(finite(v) for v in (at,closed,unit.get('open'),unit.get('close'))) or closed>at or not math.isclose(abs(unit['close']-unit['open']),e.spot_size,rel_tol=2e-12):return
  if not result or result.get('bar_close')!=unit['close']:return
  position=getattr(e,'position',None)
  if position and at>=position.get('entry_timestamp',at+1):
   key=[position.get('symbol'),position.get('side'),position.get('entry_timestamp')]
   d=direction(position)
   if self.extreme is None or self.extreme['key']!=key or favorable(d,unit['close'],self.extreme['price']):
    self.extreme=dict(key=key,price=unit['close'],confirmed_at=at);self.save()
  w=self.wait
  if not w or w.get('kind')!='TRAIL_PULLBACK' or not getattr(e,'support_execution_clear',False) or not finite(w.get('flat_confirmed_at')):return
  if at<=max(w['exit_requested_at'],w['flat_confirmed_at'],getattr(e,'entry_reset_at',0)):return
  d=w['direction'];trend='LONG' if result.get('direction')==-1 else 'SHORT'
  if result.get('flip') is True and trend!=d:
   self.wait=None;self.used=[];self.notice='EPISODE_INVALIDATED_BY_OPPOSITE_FLIP';self.save();return
  counter=unit['close']<unit['open'] if d=='LONG' else unit['close']>unit['open']
  if w['phase']=='WAITING_FOR_COUNTER_BRICK' and counter:
   w.update(phase='WAITING_FOR_COMPLETED_PULLBACK_BREAK',pullback_at=at,pullback_open=unit['open'],pullback_close=unit['close'])
   self.notice=w['phase'];self.save()
 def arm_trailing(self,e,action,prior):
  position=action.get('position') or prior
  if not position:return
  if self.wait and self.wait.get('kind')=='TRAIL_PULLBACK' and self.wait.get('entry_order_id')==position.get('order_id'):return
  d=direction(position);at=action.get('timestamp');entered=position.get('entry_timestamp')
  if not finite(at) or not finite(entered):return
  key=[position.get('symbol'),position.get('side'),entered]
  refs=[self.extreme] if self.extreme and self.extreme['key']==key and self.extreme['confirmed_at']<=at else []
  from .swing_targets import book
  candidates=[dict(price=r['price'],confirmed_at=r['time']) for r in book(e).rows if entered<=r['time']<=at]
  refs+=candidates
  if not refs:
   # The last confirmed pre-entry brick is a causal fallback; no quote/fill level
   # is fabricated into a completed continuation reference.
   refs=[dict(price=r['price'],confirmed_at=r['time']) for r in book(e).rows if r['time']<=at][-1:]
  if not refs:self.notice='TRAILING_CONTINUATION_REFERENCE_UNAVAILABLE';self.save();return
  ref=(max if d=='LONG' else min)(refs,key=lambda r:r['price'])
  self.wait=dict(kind='TRAIL_PULLBACK',entry_order_id=position.get('order_id'),id='trail:'+str(position.get('order_id'))+':'+str(at),direction=d,price=ref['price'],reference_at=ref['confirmed_at'],exit_requested_at=at,phase='WAITING_FOR_COUNTER_BRICK',flat_confirmed_at=None)
  self.notice='WAITING_FOR_CONFIRMED_FLAT';self.proof=None;self.save()
  from .manual_entry import clear_entry_signal
  clear_entry_signal(e)
 def confirmation(self,e,unit,result):
  w=self.wait
  if not w or not getattr(e,'support_execution_clear',False):return False
  trailing=w.get('kind')=='TRAIL_PULLBACK'
  if w.get('phase')!=('WAITING_FOR_COMPLETED_PULLBACK_BREAK' if trailing else 'WAITING_FOR_FAILED_RETEST_BRICK'):return False
  at=unit.get('available_at');closed=unit.get('closed_at')
  if unit.get('kind')!='brick' or unit.get('closed') is not True or unit.get('provisional') or unit.get('historyOnly'):return False
  if not all(finite(x) for x in (at,closed,unit.get('open'),unit.get('close'))) or closed>at or at<=max(w['pullback_at'] if trailing else w['retested_at'],getattr(e,'entry_reset_at',0)):return False
  d=w['direction'];close=unit['close']
  if not math.isclose(abs(close-unit['open']),e.spot_size,rel_tol=2e-12):return False
  if not favorable(d,close,w['price']) or not favorable(d,close,unit['open']):return False
  if not result or result.get('bar_close')!=close or result.get('direction')!=(-1 if d=='LONG' else 1):return False
  self.proof=dict(price=w['price'],close=close,at=at,direction=d)
  return True
 def admission(self,e,side,result):
  if not self.wait:return True
  w=self.wait;d='LONG' if side in ('LONG','CE') else 'SHORT'
  # Only a genuine new opposite flip cancels the old directional episode.
  rd='LONG' if (result or {}).get('direction')==-1 else 'SHORT'
  if rd!=w['direction'] and (result or {}).get('flip') is True:
   self.wait=None;self.used=[];self.notice='EPISODE_INVALIDATED_BY_OPPOSITE_FLIP';self.save();return True
  return bool(d==w['direction'] and self.proof and self.proof['direction']==d and self.proof['at']==getattr(e,'entry_observation_at',None) and self.proof['close']==(result or {}).get('bar_close') and getattr(e,'support_execution_clear',False))
 def capture(self,e,action):
  p=action.get('position')
  if not p or action.get('action') not in ('BUY','OPEN_LONG','OPEN_SHORT'):return
  from .swing_targets import book
  d=direction(p);at=p.get('entry_timestamp',action.get('timestamp',0))
  key=[p.get('symbol'),p.get('side'),at]
  if e.config.get('trailing_reentry_enabled') and (not self.extreme or self.extreme['key']!=key):
   refs=[r for r in book(e).rows if finite(r.get('price')) and r['time']<=at]
   self.extreme=dict(key=key,price=refs[-1]['price'],confirmed_at=refs[-1]['time']) if refs else None
   self.save()
  if not support_enabled(e):return
  price=p.get('fill_price') if e.config.get('execution_route')=='DIRECT' and finite(p.get('fill_price')) else (e.under_result or {}).get('bar_close')
  if not finite(price):return
  p.pop('retained_swing_target',None)
  if e.position is not None:e.position.pop('retained_swing_target',None)
  key='highs' if d=='LONG' else 'lows'
  candidates=[r for r in getattr(book(e),key,[]) if r['confirmed_at']<=at and r.get('broken_at') is None and r['id'] not in self.used and favorable(d,r['price'],price)]
  if candidates:
   ref=min(candidates,key=lambda r:abs(r['price']-price))
   p['retained_swing_target']=dict(deepcopy(ref),direction=d,entry_underlying_close=price)
   if e.position is not None:e.position.update(retained_swing_target=deepcopy(p['retained_swing_target']))
  # Consume continuation only after broker fill; a rejected/unknown entry keeps wait.
 def filled(self,e,position):
  if not position:return
  if self.wait and position.get('entry_timestamp',0)>self.wait['exit_requested_at'] and direction(position)==self.wait['direction']:
   self.wait=None;self.notice='CONTINUATION_FILLED';self.save()
 def after(self,e,event,actions,prior):
  if any(a.get('action') in ('SELL','CLOSE_LONG','CLOSE_SHORT') for a in actions):
   close=next(a for a in actions if a.get('action') in ('SELL','CLOSE_LONG','CLOSE_SHORT'))
   if close.get('reason')=='TARGET_GRID_TRAILING_STOP' and e.config.get('trailing_reentry_enabled',False):
    self.arm_trailing(e,close,prior);return actions
   # Other protective exits retain their existing episode invalidation.
   self.wait=None;self.used=[];self.notice='PROTECTIVE_EXIT';self.save();return actions
  for a in actions:self.capture(e,a)
  if not prior or e.position is None or self.wait:return actions
  if not support_enabled(e):return actions
  target=e.position.get('retained_swing_target')
  if not target:return actions
  at=event.get('available_at');stamp=event.get('timestamp');price=event.get('close')
  if event.get('kind')!='price' or event.get('series')!='underlying' or event.get('source_basis')!='BROKER_LIVE_PRICE' or event.get('symbol')!=e.config['underlying']:return actions
  if not all(finite(v) for v in (at,stamp,price)) or not 0<=at-stamp<=10 or stamp<=prior.get('entry_timestamp',0):return actions
  d=target['direction'];level=target['price']
  if target.get('fresh_touch_after') is not None:
   if at<=target['fresh_touch_after']:return actions
   key=str(prior.get('order_id'))+'|'+target['id']
   armed=self.touch_arms.get(key,target.get('fresh_touch_armed',False))
   if not armed:
    waiting='WAITING_FOR_RETURN_BELOW_RESISTANCE' if d=='LONG' else 'WAITING_FOR_RETURN_ABOVE_SUPPORT'
    if self.notice!=waiting:self.notice=waiting;self.save()
    if (price<level if d=='LONG' else price>level):
     self.touch_arms[key]=True;self.notice='ARMED_FOR_FRESH_TARGET_TOUCH';self.save()
    return actions
  if not (price>=level if d=='LONG' else price<=level):return actions
  entry=prior.get('fill_price',target['entry_underlying_close'])
  if not favorable(d,price,entry):return actions
  self.wait=dict(target,exit_requested_at=at,phase='WAITING_FOR_DEPARTURE')
  self.used.append(target['id']);self.notice='WAITING_FOR_CONFIRMED_FLAT';self.save()
  from .manual_entry import clear_entry_signal
  clear_entry_signal(e)
  out=e.exit(at,'RETAINED_SWING_PROFIT_TOUCH')
  out[0]['retained_swing_target']=deepcopy(target)
  return actions+out
def install(e,config_path=None):
 if enabled(e):
  if e.config.get('trailing_reentry_enabled') and not e.config.get('grid_trailing_enabled'):raise ValueError('Trailing continuation requires target-grid trailing')
  if e.config.get('supertrend_basis')!='COMPLETED_RENKO':raise ValueError('Retest continuation requires completed Renko')
  if e.config.get('signal_source','UNDERLYING')!='UNDERLYING':raise ValueError('Retest continuation requires underlying signals')
  e.support_retest=Policy(e,Path(config_path).parent/'support-retest.json' if config_path else None)

def reconciled(engine,executor):
 p=get(engine)
 if not p or not p.wait:return
 state=executor.state;owned=state.get('position')
 if any(state.get(k) for k in ('pending','positions','closing_legs','detached_position')):return
 if owned and owned.get('order_id') and finite(owned.get('fill_price')) and finite(owned.get('quantity')) and owned['quantity']>0:
  p.filled(engine,owned)
