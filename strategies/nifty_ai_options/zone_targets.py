"""Causal opposing structural-shift zones and completed-Renko continuation.
No broker requests or order submission. Uses only the owning engine's validated OHLC.
"""
from copy import deepcopy
from collections import deque
import hashlib,json,math
from pathlib import Path

REVISION='opposing-structure-zone-v1'
SOURCE_SECONDS=300
def finite(x):return not isinstance(x,bool) and isinstance(x,(int,float)) and math.isfinite(x)
def enabled(engine):return (engine.config.get('zone_targets_enabled',False) or engine.config.get('grid_trailing_enabled',False)) and engine.config.get('display_mode','RENKO')=='RENKO'
def side(position):return 'LONG' if position.get('side') in ('LONG','CE') else 'SHORT'
def identity(config):
 return {k:config.get(k) for k in ('account','underlying','runtime_session','market_data_account','market_data_broker','reference_value','timeframe')}
def validate(config):
 if not (config.get('zone_targets_enabled') or config.get('grid_trailing_enabled')):return
 if config.get('supertrend_basis')!='COMPLETED_RENKO' or config.get('display_mode','RENKO')!='RENKO':raise ValueError('Strong-zone continuation requires completed Renko mode')
 if config.get('timeframe') not in (1,5):raise ValueError('Strong-zone source needs verified 1m or 5m OHLC; 30m cannot reconstruct 5m zones')
 if config.get('signal_source','UNDERLYING')!='UNDERLYING':raise ValueError('Strong-zone continuation uses the selected underlying source')
 if not config.get('supertrend_enabled',True):raise ValueError('Strong-zone continuation requires Supertrend episode direction')
 if config.get('grid_trailing_enabled') and config.get('execution_route')!='DIRECT':raise ValueError('Grid trailing currently requires a direct instrument so entry break-even uses its actual fill price')
 if config.get('zone_targets_enabled') and config.get('swing_targets_enabled'):raise ValueError('Choose strong-zone targets or swing targets, not both')

class ZoneBook:
 """Same causal geometry criteria as V1 rzEngine; only structural direction
 changes qualify as strong. Previous completed source is processed, as Pine [1].
 """
 def __init__(self,provenance):
  self.provenance=provenance;self.rows=[];self.records=[];self.high=self.low=None
  self.high_broken=self.low_broken=False;self.last_side=None;self.last_up=self.last_down=None
  self.atr=None;self.tr_seed=[];self.processed=-1;self.last_available=None
 def observe(self,row):
  if self.rows and row['time']<=self.rows[-1]['time']:
   old=next((r for r in reversed(self.rows) if r['time']==row['time']),None)
   if old and all(old[k]==row[k] for k in ('open','high','low','close')):return
   raise ValueError('Conflicting/out-of-order strong-zone source')
  previous=self.rows[-1]['close'] if self.rows else row['close']
  tr=max(row['high']-row['low'],abs(row['high']-previous),abs(row['low']-previous))
  if self.atr is None:
   self.tr_seed.append(tr)
   if len(self.tr_seed)==14:self.atr=sum(self.tr_seed)/14
  else:self.atr+=(tr-self.atr)/14
  self.rows.append(dict(row,atr=self.atr))
  if len(self.rows)>64:
   removed=len(self.rows)-64;self.rows=self.rows[-64:]
   if self.last_up is not None:self.last_up-=removed
   if self.last_down is not None:self.last_down-=removed
  self.last_available=row['available_at']
  i=len(self.rows)-2
  if i<0 or self.rows[i]['atr'] is None:return
  self.processed=i;r=self.rows[i];now=r['closed_at']
  self.records=[z for z in self.records if now-z['origin_at']<=15*86400]
  for z in self.records:
   if z['invalidated_at'] is None and now>z['born_at']:
    invalid=r['close']<z['low'] if z['side']=='DEMAND' else r['close']>z['high']
    if invalid:z['invalidated_at']=now
  if i>=10:
   w=self.rows[i-10:i+1];center=w[5];others=w[:5]+w[6:]
   # Strict comparisons deliberately refuse ambiguous equal-price pivots.
   if all(center['high']>x['high'] for x in others):self.high=center['high'];self.high_broken=False
   if all(center['low']<x['low'] for x in others):self.low=center['low'];self.low_broken=False
  up=self.high is not None and not self.high_broken and r['close']>self.high
  down=self.low is not None and not self.low_broken and r['close']<self.low
  if up:self.high_broken=True
  if down:self.low_broken=True
  direction=1 if up else -1 if down else 0
  if not direction:return
  shifted=self.last_side is not None and direction!=self.last_side
  self.last_side=direction
  ratio=abs(r['close']-r['open'])/r['atr'] if r['atr'] else 0
  last=self.last_up if direction==1 else self.last_down
  if ratio<.8 or last is not None and i-last<3:return
  origin=next((x for x in reversed(self.rows[max(0,i-12):i]) if (x['close']<x['open'] if direction==1 else x['close']>x['open'])),None)
  if not origin or origin['high']<=origin['low']:return
  label='DEMAND' if direction==1 else 'SUPPLY'
  if any(z['side']==label and (z['origin_at']==origin['time'] or z['invalidated_at'] is None and abs((z['high']+z['low']-origin['high']-origin['low'])/2)<=r['atr']*.35) for z in self.records):return
  token=json.dumps([self.provenance,label,origin['time'],now],sort_keys=True)
  self.records.append(dict(id=hashlib.sha256(token.encode()).hexdigest(),side=label,low=origin['low'],high=origin['high'],origin_at=origin['time'],born_at=now,available_at=row['available_at'],invalidated_at=None,strong=shifted,body_atr=ratio,pivot_strength=5,source_frame=5,provenance=deepcopy(self.provenance),revision=REVISION))
  if direction==1:self.last_up=i
  else:self.last_down=i
  self.records=self.records[-180:]
 def fresh(self,at):return self.last_available is not None and 0<=at-self.last_available<=330
 def select(self,direction,price,at,excluded=()):
  rows=[z for z in self.records if z['strong'] and z['invalidated_at'] is None and z['available_at']<=at and at-z['origin_at']<=15*86400 and z['id'] not in excluded and (z['side']=='SUPPLY' and z['low']>price if direction=='LONG' else z['side']=='DEMAND' and z['high']<price)]
  return deepcopy(min(rows,key=lambda z:z['low']-price if direction=='LONG' else price-z['high'])) if rows else None

class ZonePolicy:
 def __init__(self,engine,path=None):
  validate(engine.config);self.engine=engine;self.scope=identity(engine.config);self.book=ZoneBook(self.scope);self.grid=ReferenceGrid(engine.config);self.trailing=None;self.position_key=None
  self.path=Path(path) if path else None;self.wait=None;self.used=[];self.episode=None;self.source_pending={};self.last_source_event=None;self.notice='WARMING_SOURCE'
  if self.path and self.path.exists():
   saved=json.loads(self.path.read_text())
   if saved.get('scope')==self.scope:
    self.wait=saved.get('wait');self.used=saved.get('used',[]);self.episode=saved.get('episode');self.position_key=saved.get('position_key');self.trailing=TargetLadder.restore(saved['trailing']) if saved.get('trailing') else None
 def snapshot(self):
  return dict(revision=REVISION,active=enabled(self.engine),stop_confirmation_mode=self.engine.config.get('exit_confirmation_mode','RENKO_BRICKS_ONLY'),notice=self.notice,source_frame=5,source_available_at=self.book.last_available,eligible_zones=sum(z['strong'] and z['invalidated_at'] is None for z in self.book.records),continuation=deepcopy(self.wait),ladder=self.trailing.snapshot() if self.trailing else None)
 def reconcile(self,clear,at):
  if not self.wait:return
  phase='WAITING_FOR_COMPLETED_BREAK' if clear else 'WAITING_FOR_CONFIRMED_FLAT'
  if self.wait.get('phase')!=phase:
   self.wait['phase']=phase;self.notice=phase;self.save()
 def save(self):
  if self.path:
   from .run import atomic
   atomic(self.path,dict(revision=REVISION,scope=self.scope,wait=self.wait,used=self.used,episode=self.episode,position_key=self.position_key,trailing=self.trailing.snapshot() if self.trailing else None))
 def observe(self,engine,event,warm=False):
  if event.get('kind')!='underlying':return
  if event.get('symbol') not in (None,engine.config['underlying']):raise ValueError('Wrong strong-zone instrument')
  if not warm and (event.get('closed') is not True or event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE' or event.get('body_available') is not True):return
  if not all(finite(event.get(k)) and event[k]>0 for k in ('timestamp','open','high','low','close')):raise ValueError('Strong-zone source requires real completed OHLC')
  if not event['low']<=min(event['open'],event['close'])<=max(event['open'],event['close'])<=event['high']:raise ValueError('Invalid strong-zone OHLC')
  current=tuple(event[k] for k in ('timestamp','open','high','low','close'))
  if self.last_source_event and current[0]<=self.last_source_event[0]:
   if current==self.last_source_event:return
   raise ValueError('Conflicting/out-of-order completed zone candle')
  frame=engine.config['timeframe'];start=event['timestamp'];closed=event.get('closed_at',start+frame*60);available=event.get('available_at',closed)
  if not start<closed<=available:raise ValueError('Noncausal strong-zone candle')
  self.last_source_event=current
  row=dict(time=start,closed_at=closed,available_at=available,**{k:event[k] for k in ('open','high','low','close')})
  if frame==5:self.book.observe(row);self.grid.observe(row);return
  bucket=start-start%300;self.source_pending.setdefault(bucket,{})
  old=self.source_pending[bucket].get(start)
  if old and any(old[k]!=row[k] for k in ('open','high','low','close')):raise ValueError('Conflicting completed strong-zone minute')
  self.source_pending[bucket][start]=row
  values=self.source_pending[bucket]
  stamps=[bucket+60*i for i in range(5)]
  if all(t in values for t in stamps):
   ordered=[values[t] for t in stamps]
   combined=dict(time=bucket,closed_at=bucket+300,available_at=max(r['available_at'] for r in ordered),open=ordered[0]['open'],close=ordered[-1]['close'],high=max(r['high'] for r in ordered),low=min(r['low'] for r in ordered))
   self.book.observe(combined);self.grid.observe(combined)
   del self.source_pending[bucket]
  self.source_pending={t:v for t,v in self.source_pending.items() if t>=bucket-300}
 def admission(self,engine,direction,result):
  if getattr(engine,'zone_replaying',False):return True
  at=getattr(engine,'entry_observation_at',0)
  if engine.config.get('grid_trailing_enabled') and not (self.grid.valid(at) and self.book.fresh(at)):return False
  if not self.wait:return True
  trend='LONG' if (result or {}).get('direction')==-1 else 'SHORT' if (result or {}).get('direction')==1 else None
  if trend and trend!=self.wait['direction']:
   self.wait=None;self.episode=None;self.used=[];self.notice='EPISODE_INVALIDATED';self.save();return True
  if direction!=self.wait['direction']:return False
  close=(result or {}).get('bar_close')
  proof=getattr(engine,'zone_break_proof',None) or {}
  return bool(proof.get('zone_id')==self.wait['id'] and proof.get('available_at')==getattr(engine,'entry_observation_at',None) and proof.get('close')==close and getattr(engine,'zone_execution_clear',False) and self.book.fresh(getattr(engine,'entry_observation_at',0)) and finite(close) and (close>self.wait['high'] if direction=='LONG' else close<self.wait['low']))
 def capture(self,engine,action):
  position=engine.position
  if not position:return
  direction=side(position);at=action['timestamp'];price=(engine.under_result or {}).get('bar_close')
  if not finite(price):return
  continuation=self.wait and direction==self.wait['direction']
  if not continuation:
   self.episode=dict(direction=direction,started_at=at);self.used=[]
  target=self.book.select(direction,price,at,self.used) if engine.config.get('zone_targets_enabled') and self.book.fresh(at) else None
  position['zone_episode']=deepcopy(self.episode)
  position['target_grid']=deepcopy(self.grid.lock) if self.grid.valid(at) and self.book.fresh(at) else None
  self.trailing=None;self.position_key=None
  if target:position['zone_target']=dict(target,direction=direction,entry_underlying_close=price)
  position['zone_target_status']='READY' if target else 'NO_FRESH_STRONG_OPPOSING_ZONE'
  action['position']=deepcopy(position);self.notice=position['zone_target_status'];self.save()
 def after(self,engine,event,actions):
  for action in actions:
   if action.get('action') in ('BUY','OPEN_LONG','OPEN_SHORT'):self.capture(engine,action)
   elif action.get('action') in ('SELL','CLOSE_LONG','CLOSE_SHORT') and action.get('reason')!='STRONG_OPPOSING_ZONE_TOUCH':
    self.wait=None;self.episode=None;self.used=[];self.save()
  if actions or not engine.position or self.wait:return actions
  live_price=event.get('kind')=='price' and event.get('series','underlying')=='underlying' and event.get('source_basis')=='BROKER_LIVE_PRICE'
  completed_source=event.get('kind')=='underlying' and event.get('closed') is True and event.get('body_available') is True and event.get('source_basis')=='PROVIDER_CONFIRMED_CLOSE'
  if not (live_price or completed_source):return actions
  at=event.get('available_at');stamp=event.get('timestamp') if live_price else event.get('closed_at');price=event.get('close')
  if not all(finite(x) for x in (at,stamp,price)) or not 0<=at-stamp<=10 or at<=engine.position.get('entry_confirmed_at',engine.position.get('entry_timestamp',0)):return actions
  if engine.config.get('grid_trailing_enabled'):
   key=(engine.position.get('order_id'),engine.position.get('entry_timestamp'))
   grid=engine.position.get('target_grid');fill=engine.position.get('fill_price')
   if self.position_key!=list(key):
    self.trailing=None;self.position_key=list(key)
    if grid and finite(fill):self.trailing=TargetLadder(grid,fill,side(engine.position));self.save()
   if self.trailing:
    before=self.trailing.snapshot();self.trailing.advance(price)
    proof=completed_stop_confirmation(engine,at,self.trailing) if engine.config.get('exit_confirmation_mode','RENKO_BRICKS_ONLY')=='RENKO_BRICKS_ONLY' else None
    hit=bool(proof) if engine.config.get('exit_confirmation_mode','RENKO_BRICKS_ONLY')=='RENKO_BRICKS_ONLY' else self.trailing.crossed(price)
    if self.trailing.snapshot()!=before:self.save()
    if hit:
     actions=engine.exit(at,'TARGET_GRID_TRAILING_STOP');actions[0]['target_ladder']=self.trailing.snapshot();actions[0]['confirmation']=proof;self.wait=None;self.episode=None;self.save();return actions
  if not live_price:return actions
  target=engine.position.get('zone_target')
  if not target or not all(finite(x) for x in (at,stamp,price)) or not 0<=at-stamp<=10 or not self.book.fresh(at):return actions
  entered=engine.position.get('entry_confirmed_at',engine.position.get('entry_timestamp',0))
  if at<=entered:return actions
  direction=target['direction'];entry=engine.position.get('fill_price',target['entry_underlying_close']) if engine.config.get('execution_route')=='DIRECT' else target['entry_underlying_close']
  hit=price>=target['low'] and price>entry if direction=='LONG' else price<=target['high'] and price<entry
  if not hit:return actions
  self.wait=dict(deepcopy(target),direction=direction,exit_requested_at=at,phase='WAITING_FOR_CONFIRMED_FLAT')
  self.used.append(target['id']);self.used=self.used[-180:];self.notice='WAITING_FOR_CONFIRMED_FLAT';self.save()
  for name in ('entry_confirmation','premium_entry_confirmation'):
   gate=getattr(engine,name,None)
   if gate:gate.clear()
  engine.pending_direction=None;engine.pending_underlying_flip=None
  actions=engine.exit(at,'STRONG_OPPOSING_ZONE_TOUCH')
  actions[0]['zone_continuation']=deepcopy(self.wait)
  actions[0]['zone_touch']=dict(price=price,source_at=stamp,available_at=at)
  return actions

def policy(engine):return getattr(engine,'zone_policy',None) if enabled(engine) else None
def admission(engine,direction,result):
 p=policy(engine);return p.admission(engine,direction,result) if p else True
def continuation(engine):return bool(policy(engine) and engine.zone_policy.wait)
def filled(engine):
 p=policy(engine)
 if p and p.wait and engine.position and engine.position.get('entry_timestamp',0)>p.wait['exit_requested_at'] and side(engine.position)==p.wait['direction'] and engine.position.get('zone_episode')==p.episode:
  p.wait=None;p.notice='CONTINUATION_FILLED';p.save()

class ReferenceGrid:
 """First opposing (red underlying) source candle after session opening.
 Existing V1 spacing: up=high+n*span, down=low-n*span. No logical cap.
 """
 def __init__(self,config):self.config=config;self.parts={};self.session=None;self.lock=None;self.last_end=None
 def valid(self,at):
  india=self.config.get('market') in ('NSE','BSE');crypto=self.config.get('market')=='CRYPTO'
  reset=0 if india else (150 if crypto else 210)*60
  key=math.floor((at+19800-reset)/86400)
  return bool(self.lock and self.lock['available_at']<=at and self.lock['session']==key)
 def observe(self,row):
  india=self.config.get('market') in ('NSE','BSE');crypto=self.config.get('market')=='CRYPTO'
  width=300 if india else 1800;bucket=row['time']-row['time']%width
  self.parts={t:v for t,v in self.parts.items() if t>=bucket-width}
  self.parts.setdefault(bucket,{})[row['time']]=row
  stamps=list(range(int(bucket),int(bucket+width),300));parts=self.parts[bucket]
  if not all(t in parts for t in stamps):return
  data=[parts[t] for t in stamps];r=dict(time=bucket,closed_at=bucket+width,available_at=max(x['available_at'] for x in data),open=data[0]['open'],close=data[-1]['close'],high=max(x['high'] for x in data),low=min(x['low'] for x in data))
  reset=0 if india else (150 if crypto else 210)*60
  key=math.floor((bucket+19800-reset)/86400)
  first=key!=self.session or not india and not crypto and self.last_end is not None and bucket-self.last_end>=2700
  if first:self.session=key;self.lock=None
  if not first and self.lock is None and r['close']<r['open'] and r['high']>r['low']:
   self.lock=dict(high=r['high'],low=r['low'],origin_at=bucket,available_at=r['available_at'],source_frame=width//60,session=key,revision='v1-locked-reference-grid')
  self.last_end=r['closed_at'];self.parts={t:v for t,v in self.parts.items() if t>bucket}

class TargetLadder:
 def __init__(self,grid,entry,direction):
  if not all(finite(x) for x in (grid.get('high'),grid.get('low'),entry)) or grid['high']<=grid['low']:raise ValueError('A validated positive target-grid span is required')
  self.grid=deepcopy(grid);self.entry=entry;self.direction=direction;self.span=grid['high']-grid['low'];self.anchor=grid['high'] if direction=='LONG' else grid['low'];self.sign=1 if direction=='LONG' else -1
  self.first=max(1,math.floor(self.sign*(entry-self.anchor)/self.span)+1);self.achieved=0;self.stop=None
 def target(self,stage):return self.anchor+self.sign*(self.first+stage-1)*self.span
 def advance(self,price):
  # A single jump may achieve arbitrarily many target intervals.
  reached=max(0,math.floor(self.sign*(price-self.anchor)/self.span)-self.first+1)
  if reached>self.achieved:
   self.achieved=reached
   candidate=self.entry if reached==1 else self.target(reached-1)
   self.stop=candidate if self.stop is None else max(self.stop,candidate) if self.sign==1 else min(self.stop,candidate)
 def crossed(self,price):
  return self.stop is not None and (price<=self.stop if self.sign==1 else price>=self.stop)
 def observe(self,price):
  self.advance(price)
  return self.crossed(price)
 def snapshot(self):return dict(grid=self.grid,entry=self.entry,direction=self.direction,first=self.first,achieved=self.achieved,stop=self.stop)
 @classmethod
 def restore(cls,row):
  x=cls(row['grid'],row['entry'],row['direction']);x.first=row['first'];x.achieved=row['achieved'];x.stop=row['stop'];return x

def reconciled(engine,executor):
 """Only an already-reconciled owned ledger may acknowledge continuation fills.
 Does not fetch, clear broker intent, or synthesize flatness.
 """
 from strategies.nifty_ai_options.support_retest import reconciled as retest_reconciled
 retest_reconciled(engine,executor)
 p=policy(engine)
 if not p or not p.wait:return
 state=executor.state
 if state.get('pending') or state.get('positions') or state.get('closing_legs') or state.get('detached_position'):return
 own=state.get('position')
 if not own:p.reconcile(True,0);return
 if (own.get('entry_timestamp',0)>p.wait['exit_requested_at'] and side(own)==p.wait['direction']
     and own.get('zone_episode')==p.episode and own.get('order_id') and finite(own.get('fill_price'))):
  p.wait=None;p.notice='CONTINUATION_FILL_RECONCILED';p.save()

def record_exit_unit(engine,unit,result):
 if not engine.config.get('grid_trailing_enabled') or getattr(engine,'zone_replaying',False):return
 if unit.get('kind')=='brick' and unit.get('closed') is True and not unit.get('provisional') and not unit.get('historyOnly') and result and result.get('bar_close')==unit.get('close'):
  engine.grid_exit_unit=deepcopy(unit)

def completed_stop_confirmation(engine,at,ladder):
 unit=getattr(engine,'grid_exit_unit',None);position=engine.position
 if not unit or not position or ladder.stop is None:return None
 entered=position.get('entry_confirmed_at',position.get('entry_timestamp',0))
 if unit.get('kind')!='brick' or unit.get('closed') is not True or unit.get('provisional') or unit.get('historyOnly'):return None
 if not all(finite(unit.get(k)) for k in ('open','close','closed_at','available_at')) or unit['available_at']!=at or not entered<unit['closed_at']<=at:return None
 if not math.isclose(abs(unit['close']-unit['open']),engine.spot_size,rel_tol=2e-12):return None
 adverse=unit['close']<unit['open'] if side(position)=='LONG' else unit['close']>unit['open']
 if not adverse or not ladder.crossed(unit['close']):return None
 return dict(deepcopy(unit),confirmation_basis='COMPLETED_ADVERSE_RENKO_TRAILING_STOP',stop=ladder.stop)
