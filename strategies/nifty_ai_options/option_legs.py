"""Independent bought-option ownership in one durable account ledger.

Only user-started workers call this coordinator. Retiring exits never occupy the
active leg's pending slot. Every child uses the existing broker's order checks.
"""
import copy,hashlib,json,threading,time
from pathlib import Path
try:from .run import atomic
except ImportError:from run import atomic

def capture_fill(state,action,result,at,key):
 state['last_fill']=dict(id=str(result.get('order_id') or key)+'|'+str(result.get('filled_quantity',result.get('payload',{}).get('qty',''))),action=copy.deepcopy(action),result=copy.deepcopy(result),confirmed_at=at)

class OptionLegBook:
 def __init__(self,base,directory,config,*,quote,ready=lambda:True,clock=time.time):
  if config.get('execution_route','OPTIONS')!='OPTIONS':raise ValueError('Option leg book cannot manage a netted direct contract')
  self.base=base;self.root=base.state;self.directory=Path(directory);self.config=config
  self.quote=quote;self.ready=ready;self.clock=clock;self.lock=threading.RLock();self.last_poll=0
  self.root.setdefault('closing_legs',{});self.root.setdefault('entry_requests',{})
  self.original_save=base.save;base.save=self.save;self.save()
 @property
 def state(self):return self.root
 def __getattr__(self,name):return getattr(self.base,name)
 def save(self):
  with self.lock:
   positions=[self.root['position']] if self.root.get('position') else []
   positions.extend(slot['position'] for slot in self.root.get('closing_legs',{}).values() if slot.get('position'))
   self.root['positions']=copy.deepcopy(positions);self.original_save()
 def close(self):self.base.close()
 def has_symbol(self,symbol):
  return any((slot.get('position') or (slot.get('pending') or {}).get('intent',{}).get('position') or {}).get('symbol')==symbol for slot in self.root['closing_legs'].values())
 def _child(self,slot):
  child=copy.copy(self.base);child.state=slot
  slot['seen']=self.root.setdefault('seen',[])
  child.confirmation_timeout=0
  child.save=self.save
  return child
 def request_exit(self,action):
  owned=self.root.get('position')
  if action.get('action')!='SELL' or not owned or owned.get('symbol')!=action['position'].get('symbol'):raise ValueError('Only an exact owned bought option may retire')
  if self.root.get('pending'):raise ValueError('Active option order must reconcile before ownership transfer')
  if owned.get('side') not in ('CE','PE'):raise ValueError('Direct positions cannot overlap')
  key=hashlib.sha256(json.dumps([self.config.get('account'),owned['symbol'],owned.get('order_id'),owned.get('entry_timestamp')],sort_keys=True).encode()).hexdigest()[:24]
  if key in self.root['closing_legs']:raise ValueError('This exact option holding is already retiring')
  self.root['closing_legs'][key]=dict(position=copy.deepcopy(owned),pending=None,seen=self.root.setdefault('seen',[]),original_position=copy.deepcopy(owned),exit_intent=dict(copy.deepcopy(action),position=copy.deepcopy(owned)),origin=str(self.directory),attempts=0,created_at=self.clock(),delivered=[])
  self.root['position']=None;self.last_poll=0;self.save()
  return dict(deferred=True,reason='PREVIOUS_OPTION_EXIT_MANAGED_SEPARATELY',independent_exit=True)
 def remember_entry(self,action):
  if action.get('action')!='BUY' or action.get('manual_override'):return None
  p=action['position'];identity=hashlib.sha256(json.dumps([self.config.get('account'),self.config.get('runtime_session',self.directory.name),p['symbol'],p.get('signal_timestamp',action['timestamp']),p.get('side')],sort_keys=True).encode()).hexdigest()
  if identity not in self.root['entry_requests']:
   row=dict(id=identity,action=copy.deepcopy(action),phase='WAITING_FOR_SOURCE',runtime_session=self.config.get('runtime_session',self.directory.name),created_at=self.clock())
   closing=p.get('closing_minutes')
   if isinstance(closing,int) and not isinstance(closing,bool):
    from datetime import datetime,timedelta
    from zoneinfo import ZoneInfo
    day=datetime.fromtimestamp(action['timestamp'],ZoneInfo('Asia/Kolkata')).replace(hour=0,minute=0,second=0,microsecond=0)
    row['expires_at']=(day+timedelta(minutes=closing)).timestamp()
   self.root['entry_requests'][identity]=row;self.save()
  return self.root['entry_requests'][identity]
 def submit(self,action,quote=None,now=None):
  if action.get('action')=='SELL' and action.get('reason')!='USER_STOP_SQUARE_OFF':return self.request_exit(action)
  request=self.remember_entry(action)
  if request and request['phase'] not in ('WAITING_FOR_SOURCE','WAITING_FOR_SAME_OPTION_EXIT'):return dict(deferred=True,reason='OPTION_SIGNAL_ALREADY_CLAIMED')
  if action.get('action')=='BUY' and self.has_symbol(action['position']['symbol']):
   if request:request['phase']='WAITING_FOR_SAME_OPTION_EXIT';self.save()
   return dict(deferred=True,reason='WAITING_FOR_SAME_OPTION_EXIT')
  if request:request['phase']='SUBMITTING';self.save()
  try:result=self.base.submit(action,quote) if now is None else self.base.submit(action,quote,now=now)
  except (ValueError,RuntimeError) as error:
   if request:
    request['phase']='UNCERTAIN' if self.root.get('pending') else 'FAILED';request['error']=str(error);self.save()
    return dict(deferred=True,terminal_no_fill=not bool(self.root.get('pending')),reason='OPTION_ENTRY_RECONCILIATION_REQUIRED' if self.root.get('pending') else 'OPTION_ENTRY_BLOCKED',detail=str(error))
   raise
  if request:request['phase']='FAILED' if result.get('terminal_no_fill') else 'WAITING_FOR_SOURCE' if result.get('deferred') else 'COMPLETE';self.save()
  self.save();return result
 def dispatch_entries(self,send,valid):
  if self.root.get('position') or self.root.get('pending') or self.root.get('management_mode') not in (None,'MANAGED'):return None
  for row in self.root['entry_requests'].values():
   if row['phase'] not in ('WAITING_FOR_SOURCE','WAITING_FOR_SAME_OPTION_EXIT'):continue
   if row['runtime_session']!=self.config.get('runtime_session',self.directory.name) or row.get('expires_at',float('inf'))<=self.clock():
    row.update(phase='CANCELLED',reason='Run or trading session changed');self.save();continue
   action=row['action']
   if self.has_symbol(action['position']['symbol']):continue
   allowed=valid(action)
   if allowed is False:row.update(phase='CANCELLED',reason='Confirmed entry conditions invalidated');self.save();continue
   if allowed is None:return None
   return send(copy.deepcopy(action))
 def _deliver(self,slot):
  fill=slot.get('last_fill')
  if not fill:return
  identity=fill['id']
  if identity in slot.setdefault('delivered',[]):return
  origin=Path(slot['origin']).resolve()
  # Every origin is a run of this same owner, never an arbitrary journal path.
  if origin.parent!=self.directory.resolve().parent:raise ValueError('Option exit journal belongs to another owner')
  origin.mkdir(parents=True,exist_ok=True)
  action=fill['action'];result=fill['result'];at=fill['confirmed_at']
  event_path=origin/'events.jsonl'
  recorded=False
  if event_path.exists():
   with event_path.open() as events:
    for line in events:
     if not line.strip():continue
     if json.loads(line).get('option_leg_receipt')==identity:recorded=True;break
  if not recorded:
   with event_path.open('a') as out:
    out.write(json.dumps(dict(action=action,result=result,recorded_at=at,option_leg_receipt=identity))+'\n');out.flush()
    __import__('os').fsync(out.fileno())
  markers_path=origin/'markers.json'
  markers=json.loads(markers_path.read_text()) if markers_path.exists() else []
  if not any(row.get('receipt_id')==identity for row in markers):
   markers.append(dict(receipt_id=identity,timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=at,symbol=action['position']['symbol'],action=action['action'],price=result.get('fill_price',result.get('simulated_fill')),mode=self.config['execution_mode'],order_id=result.get('order_id'),confirmed=True))
   atomic(markers_path,markers[-1000:])
  slot['delivered'].append(identity);self.save()
 def _complete_leg(self,key,slot,now):
  self.root.setdefault('closed_legs',[]).append(dict(symbol=slot['exit_intent']['position']['symbol'],closed_at=now,position=slot.get('original_position',slot['exit_intent']['position']),broker_flat_confirmed=bool(self.base.live),simulated=not self.base.live))
  self.root['closed_legs']=self.root['closed_legs'][-200:]
  self.root['closing_legs'].pop(key,None);self.save()
 def poll(self,*,force=False):
  now=self.clock()
  if not force and now-self.last_poll<1:return
  self.last_poll=now
  if self.root.get('pending'):
   try:
    receipt=self.base.reconcile_pending()
    if receipt and receipt.get('filled_quantity') and self.root.get('last_fill'):
     delivery=dict(origin=str(self.directory),last_fill=self.root['last_fill'],delivered=self.root.setdefault('active_delivered',[]))
     self._deliver(delivery)
    if not self.root.get('pending'):
     for request in self.root['entry_requests'].values():
      if request['phase']=='UNCERTAIN':request['phase']='COMPLETE' if self.root.get('position') else 'FAILED'
     self.save()
   except (ValueError,RuntimeError) as error:self.root['reconciliation_notice']=str(error);self.save()
  for key,slot in list(self.root['closing_legs'].items()):
   child=self._child(slot)
   if slot.get('pending'):
    try:
     receipt=child.reconcile_pending()
     if receipt and receipt.get('filled_quantity'):
      slot['last_fill']=dict(id=str(receipt['order_id'])+'|'+str(receipt['filled_quantity']),action=receipt['action'],result=dict(order_id=receipt['order_id'],filled_quantity=receipt['filled_quantity'],fill_price=receipt.get('fill_price')),confirmed_at=receipt.get('checked_at',now))
      self.save()
    except (ValueError,RuntimeError) as error:slot['last_error']=str(error);self.save()
   self._deliver(slot)
   if slot.get('pending'):continue
   if not slot.get('position'):
    self._complete_leg(key,slot,now);continue
   if not self.ready():continue
   owned=slot['position']
   action=dict(slot['exit_intent'],position=copy.deepcopy(owned),timestamp=now if slot['attempts'] else slot['exit_intent']['timestamp'])
   try:
    quote=self.quote(owned['symbol'])
    slot['attempts']+=1;slot['last_attempt_at']=now;self.save()
    result=child.submit(action,quote)
    if not result.get('deferred') and not slot.get('position') and not slot.get('pending'):
     slot['last_fill']=dict(id=str(result.get('order_id') or key)+'|'+str(slot['attempts']),action=action,result=result,confirmed_at=now);self.save();self._deliver(slot);self._complete_leg(key,slot,now)
   except (ValueError,RuntimeError,KeyError) as error:
    slot['last_error']=str(error)
    if not slot.get('pending'):slot['retained_exit_failure']=dict(intent=action,stage='EXIT_PRECHECK_FAILED')
    self.save()
   if key in self.root['closing_legs'] and slot.get('pending'):
    try:child.reconcile_pending()
    except (ValueError,RuntimeError) as error:slot['last_error']=str(error);self.save()
    self._deliver(slot)
    if not slot.get('pending') and not slot.get('position'):self._complete_leg(key,slot,now)
 def stop_all(self,request_id='stop',*,force=False):
  receipt=self.root.get('book_stop')
  if not receipt or receipt['id']!=request_id:
   receipt=dict(id=request_id,positions=copy.deepcopy(self.root.get('positions',[])),requested_at=self.clock());self.root['book_stop']=receipt;self.save()
  for row in self.root.get('entry_requests',{}).values():
   if row.get('phase') not in ('COMPLETE','FAILED'):row['phase']='CANCELLED'
  self.poll(force=force)
  if self.root.get('position') and not self.root.get('pending'):
   p=self.root['position']
   if not any(r.get('symbol')==p['symbol'] and r.get('entry_timestamp')==p.get('entry_timestamp') for r in receipt['positions']):receipt['positions'].append(copy.deepcopy(p))
   self.request_exit(dict(action='SELL',timestamp=self.clock(),position=copy.deepcopy(p),reason='USER_STOP_SQUARE_OFF'))
   self.poll(force=force)
  return dict(flat=not self.root.get('position') and not self.root.get('pending') and not self.root['closing_legs'],positions=receipt['positions'])

def entry_valid(engine,action):
 if getattr(engine,'entry_paused',False):return None
 p=action['position']
 if (getattr(engine,'contract',None) or {}).get('symbol')!=p['symbol']:return False
 side=engine.signal_side()
 if side is None:return None
 if side!=p.get('side'):return False
 config=engine.config
 if config.get('supertrend_enabled',True) and config.get('entry_gate')!='underlying_flip':
  premium=getattr(engine,'premium_result',None)
  if not premium:return None
  if premium['direction']>=0:return False
 # The saved action already passed its retest/confirmation. Recheck current
 # band direction, without demanding that one-shot confirmation a second time.
 return engine.band.allows(p['side'],dict(config,sma_retest_required=False),at=getattr(engine,'entry_observation_at',action['timestamp']))

def retain_pending_actions(engine,book,actions):
 if not book.state.get('pending'):return actions
 engine.position=copy.deepcopy(book.state.get('position'))
 try:from .manual_entry import clear_entry_signal
 except ImportError:from manual_entry import clear_entry_signal
 clear_entry_signal(engine);return []
