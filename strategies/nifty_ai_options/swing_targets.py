"""Confirmed Renko swing targets; frozen per entry and causal breakout re-entry."""
from copy import deepcopy
import math
def enabled(engine):return engine.config.get('swing_targets_enabled',False) and engine.config.get('display_mode','RENKO')=='RENKO'
class SwingBook:
 def __init__(self):self.rows=[];self.high=self.low=None;self.count=0;self.highs=[];self.lows=[];self._active_highs=[];self._active_lows=[]
 def observe(self,bar,at):
  if bar.get('provisional') or bar.get('closed') is False:return
  close=bar.get('close')
  if isinstance(close,bool) or not isinstance(close,(int,float)) or not math.isfinite(close):return
  for attr,is_high in (('_active_highs',True),('_active_lows',False)):
   active=[]
   for ref in getattr(self,attr):
    if at>ref['confirmed_at'] and (close>ref['price'] if is_high else close<ref['price']):ref['broken_at']=at
    else:active.append(ref)
   setattr(self,attr,active)
  self.count+=1;self.rows.append(dict(price=close,time=at))
  if len(self.rows)>=5:
   w=self.rows[-5:];c=w[2];others=w[:2]+w[3:]
   for key,up in [('high',True),('low',False)]:
    if all(c['price']>r['price'] if up else c['price']<r['price'] for r in others):
     ref=dict(price=c['price'],origin_at=c['time'],confirmed_at=at)
     setattr(self,key,ref)
     retained=getattr(self,'highs' if up else 'lows')
     identifier=str(c['time'])+'|'+str(c['price'])+'|'+key
     if not any(r['id']==identifier for r in retained):
      saved=dict(ref,id=identifier,broken_at=None);retained.append(saved)
      getattr(self,'_active_highs' if up else '_active_lows').append(saved)
     if len(retained)>4096:del retained[:-4096]
  self.rows=self.rows[-5:]
 def snapshot(self):return dict(high=deepcopy(self.high),low=deepcopy(self.low),count=self.count,pivot_left=2,pivot_right=2)
def book(engine):
 if not hasattr(engine,'swing_book'):engine.swing_book=SwingBook()
 return engine.swing_book
def capture(engine,position):
 if not enabled(engine):return position
 if engine.config.get('swing_retest_required',False):return position
 direction='LONG' if position['side'] in ('LONG','CE') else 'SHORT'
 close=(engine.under_result or {}).get('bar_close')
 ref=getattr(book(engine),'high' if direction=='LONG' else 'low')
 if ref and isinstance(close,(int,float)) and (ref['price']>close if direction=='LONG' else ref['price']<close):
  position['swing_target']=dict(deepcopy(ref),direction=direction,entry_underlying_close=close)
 return position
def admission(engine,side,result):
 from strategies.nifty_ai_options.support_retest import get
 policy=get(engine)
 if policy:return policy.admission(engine,side,result)
 wait=getattr(engine,'swing_wait',None)
 if not enabled(engine) or not wait:return True
 direction='LONG' if side in ('LONG','CE') else 'SHORT';close=(result or {}).get('bar_close')
 if direction!=wait['direction']:return True
 return direction==wait['direction'] and isinstance(close,(int,float)) and (close>wait['price'] if direction=='LONG' else close<wait['price']) and getattr(engine,'swing_observed_at',0)>wait['exited_at']
def target_exit(engine,units,at):
 if not enabled(engine) or not engine.position or engine.config.get('swing_retest_required',False):return None
 target=engine.position.get('swing_target')
 if not target:return None
 entered=engine.position.get('entry_confirmed_at',engine.position.get('entry_timestamp',0))
 for unit in units:
  if unit.get('kind')!='brick' or unit.get('closed') is not True or unit.get('provisional') or unit.get('historyOnly'):continue
  available=unit.get('available_at',0);closed=unit.get('closed_at',0)
  if available<=entered or closed>available:continue
  close=unit['close'];hit=close>=target['price'] if target['direction']=='LONG' else close<=target['price']
  if hit:
   engine.swing_wait=dict(target,exited_at=available)
   actions=engine.exit(at,'CONFIRMED_RENKO_SWING_TARGET')
   actions[0]['swing_target']=dict(target);actions[0]['confirmation']=dict(unit)
   return actions
 return None
