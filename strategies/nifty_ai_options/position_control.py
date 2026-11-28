"""Durable user position controls. No broker or process actions on import.

Commands are bound to the exact account/run/session. The already-owning worker
consumes them between decisions; stopped jobs use the same execution lock.
"""
import fcntl,json,re,time
from contextlib import contextmanager
from pathlib import Path
try:
 from .run import atomic
 from .manual_entry import runtime_identity,clear_entry_signal
except ImportError:
 from run import atomic
 from manual_entry import runtime_identity,clear_entry_signal
REVISION='position-controls-v1'
TERMINAL={'STOPPED','DETACHED','ATTACHED','REJECTED','RECOVERY_REQUIRED'}
ACTIVE={'QUEUED','CLAIMED','WAITING_FOR_SOURCE','VERIFYING_FLAT'}
ACTIONS={'STOP','DETACH','ATTACH'}

def enqueue(directory,config,payload,*,now=None):
 directory=Path(directory);now=time.time() if now is None else now
 expected=runtime_identity(config,directory,config['execution_mode'])
 for key,value in expected.items():
  if payload.get(key)!=value:raise ValueError('Position control differs from active '+key)
 action=payload.get('operation');identifier=payload.get('request_id')
 if action not in ACTIONS or not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Exact position action and unique request id required')
 request=dict(expected,operation=action,request_id=identifier,requested_at=now,phase='QUEUED')
 if action=='ATTACH':
  holding=payload.get('holding')
  if not isinstance(holding,dict) or set(holding)!={'symbol','quantity','product'}:raise ValueError('Select the exact open broker position')
  if not isinstance(holding['symbol'],str) or not holding['symbol'] or isinstance(holding['quantity'],bool) or not isinstance(holding['quantity'],int) or holding['quantity']<=0:raise ValueError('Invalid holding selection')
  request['holding']=dict(holding)
 root=directory/'position-controls';root.mkdir(parents=True,exist_ok=True)
 with (root/'inbox.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  receipt=root/'receipts'/(identifier+'.json')
  if receipt.exists():
   previous=json.loads(receipt.read_text())
   for key in (*expected,'operation','holding'):
    if previous.get(key)!=request.get(key):raise ValueError('Request id was already used for a different position action')
   return previous
  current=root/'latest.json'
  if current.exists() and json.loads(current.read_text()).get('phase') in ACTIVE:raise ValueError('A position control is already pending')
  atomic(receipt,request);atomic(current,request);atomic(root/'command.json',request)
 return request

class EntryBlocked(ValueError):pass

@contextmanager
def entry_guard(directory,executor):
 root=Path(directory)/'position-controls';root.mkdir(parents=True,exist_ok=True)
 with (root/'inbox.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  path=root/'latest.json'
  receipt=json.loads(path.read_text()) if path.exists() else {}
  if receipt.get('phase') in ACTIVE or executor.state.get('management_mode') not in (None,'MANAGED'):
   raise EntryBlocked('Position control has paused new entries')
  if getattr(executor,'runner_config',{}).get('daily_max_loss') not in (None,''):
   from strategies.nifty_ai_options.daily_loss_filter import check
   try:loss=check(executor)
   except (ValueError,OSError,__import__('sqlite3').Error) as error:
    raise EntryBlocked('Daily loss evidence unavailable; new entries blocked, exits remain active') from error
   if loss.get('blocked'):raise EntryBlocked(loss['reason'])
  yield


def close_action(position,at):
 side=position.get('side')
 action='CLOSE_SHORT' if side=='SHORT' else 'CLOSE_LONG' if side=='LONG' else 'SELL' if side in ('CE','PE') else None
 if action is None:raise ValueError('Owned position side is unknown')
 return dict(action=action,timestamp=at,position=dict(position),reason='USER_STOP_SQUARE_OFF')

class PositionManager:
 def __init__(self,config,directory,engine,executor,*,verify,attach,submit,clock=time.time,manual=None):
  self.manual=manual
  self.config=config;self.directory=Path(directory);self.engine=engine;self.executor=executor
  self.verify=verify;self.attach=attach;self.submit=submit;self.clock=clock
  self.expected=runtime_identity(config,directory,config['execution_mode'])
  self.request=None;self.mode=executor.state.get('management_mode','MANAGED');self.closed_position=None
  if config.get('_managed_resume'):self.mode='DETACHED'
  elif self.mode=='STOPPED':
   self.mode='MANAGED';executor.state['management_mode']='MANAGED';executor.save()
  elif self.mode=='RECOVERY_REQUIRED' and config.get('execution_mode')=='LIVE' and config.get('broker')=='DELTA_INDIA' and config.get('execution_route')=='DIRECT' and not getattr(executor,'management_only',False):
   state=executor.state
   recovered=[r for r in state.get('reconciled_intents',[]) if r.get('phase')=='RECOVERED_CLOSED' and r.get('historical_pair_closed') is True and r.get('account_id')==config.get('account') and r.get('proof')]
   retained=any(state.get(k) for k in ('position','pending','positions','closing_legs','detached_position','stop_verification_position'))
   if recovered and not retained:
    # Only a new user-started run may retire this verified historical pause.
    # The owning in-memory manager must acknowledge MANAGED, not just its file.
    proof=self.verify(None,flat=True)
    if proof.get('flat') is not True:raise ValueError('Fresh broker-flat verification required before clearing recovery pause')
    state.setdefault('management_audit',[]).append(dict(operation='REARM_RECOVERED_ON_USER_START',at=self.clock(),proof=recovered[-1]['proof'],orders_submitted=0))
    self.save_mode('MANAGED')
  self.entry_blocked=self.mode!='MANAGED' or bool(config.get('_managed_resume'))
 @property
 def blocked(self):return self.mode in ('DETACHED','STOPPING','RECOVERY_REQUIRED','STOPPED')
 def status(self):
  return dict(external_reconciliation=getattr(getattr(self,'external_close_idle',None),'status',None),revision=REVISION,mode=self.mode,entries_paused=self.entry_blocked,
              detached_position=self.executor.state.get('detached_position'),pending_request=self.request)
 def update(self,phase,**details):
  if phase in ('STOPPED','DETACHED','ATTACHED'):
   details=dict(details);details.update(error=None,retained_position=None,retained_pending=None)
   details.setdefault('notice',{'STOPPED':'Stopped · broker exposure reconciled','DETACHED':'Position detached','ATTACHED':'Position attached'}[phase])
  request=dict(self.request,phase=phase,updated_at=self.clock(),**details)
  root=self.directory/'position-controls'
  atomic(root/'receipts'/(request['request_id']+'.json'),request);atomic(root/'latest.json',request)
  self.request=request
 def save_mode(self,mode):
  self.mode=mode;self.entry_blocked=mode!='MANAGED' or bool(self.config.get('_managed_resume'))
  self.executor.state['management_mode']=mode;self.executor.save();clear_entry_signal(self.engine)
 def poll(self,*,busy=False):
  if not hasattr(self,'external_close_idle'):
   from strategies.nifty_ai_options.external_close_idle import ExternalCloseIdle
   self.external_close_idle=ExternalCloseIdle(self)
  if self.external_close_idle.poll(busy=busy):return True
  if self.request is None or self.request.get('phase') in TERMINAL:
   path=self.directory/'position-controls/command.json'
   if not path.exists():return False
   command=json.loads(path.read_text());root=path.parent
   receipt=root/'receipts'/(str(command.get('request_id'))+'.json')
   if not receipt.exists():raise ValueError('Position command has no durable receipt')
   prior=json.loads(receipt.read_text())
   if prior.get('phase')!='QUEUED':return False
   self.expected=runtime_identity(self.config,self.directory,self.config['execution_mode'])
   self.request=prior
   if any(prior.get(k)!=v for k,v in self.expected.items()):
    self.update('REJECTED',error='Position command belongs to another run/session');return False
   if self.clock()-prior.get('requested_at',0)>120:
    self.update('REJECTED',error='Position command expired before claim');return False
   # Cancel an unsubmitted manual preparation before claiming management.
   if self.manual is not None and self.manual.pending is not None:
    if self.executor.state.get('pending'):
     return False
    self.manual.inbox.update(self.manual.pending,'REJECTED',error='Position control superseded unsubmitted manual entry')
    self.manual.pending=None;self.manual.prepared=False
   self.update('CLAIMED')
  if self.request.get('phase') in TERMINAL:return False
  operation=self.request['operation']
  try:
   if callable(getattr(self.executor,'stop_all',None)):
    if operation in ('DETACH','ATTACH') and self.executor.state.get('closing_legs'):
     raise ValueError('A previous option exit remains unresolved; finish its reconciliation before transferring ownership')
    if operation=='STOP':
     if self.mode!='STOPPING':self.save_mode('STOPPING')
     stopped=self.executor.stop_all(self.request['request_id'])
     self.engine.position=None if not self.executor.state.get('position') else dict(self.executor.state['position'])
     if not stopped['flat']:
      self.update('VERIFYING_FLAT',notice='Closing every managed option leg; unresolved orders remain retained',positions=stopped['positions'])
      return False
     positions=stopped['positions']
     if self.config['execution_mode']=='LIVE':
      for owned_leg in positions:self.verify(owned_leg,flat=True)
     self.save_mode('STOPPED')
     self.update('STOPPED',broker_flat_confirmed=bool(positions) and self.config['execution_mode']=='LIVE',simulated_flat_confirmed=bool(positions) and self.config['execution_mode']=='PAPER',no_owned_position=not bool(positions),positions=positions)
     return True
   if self.executor.state.get('pending') and operation=='STOP' and callable(getattr(self.executor,'reconcile_pending',None)):
    prior_owned=self.executor.state.get('position')
    self.executor.reconcile_pending()
    if prior_owned and self.executor.state.get('position') is None:self.closed_position=dict(prior_owned)
   if self.executor.state.get('pending'):raise ValueError('An unresolved order is retained; no duplicate order or ownership change is allowed')
   if operation=='DETACH':
    if self.config['execution_mode']!='LIVE':raise ValueError('Detach / Attach applies to actual Live broker holdings')
    owned=self.executor.state.get('position')
    if not owned:raise ValueError('No strategy-owned open position to detach')
    self.verify(owned,flat=False)
    self.executor.state['detached_position']=dict(owned)
    self.executor.state['position']=None
    self.executor.state.setdefault('management_audit',[]).append(dict(operation='DETACH',at=self.clock(),position=owned,orders_submitted=0))
    self.save_mode('DETACHED');self.engine.position=None
    self.update('DETACHED',position=owned,broker_position_left_open=True,orders_submitted=0)
    return False
   if operation=='ATTACH':
    try:from .ownership import assert_attach_available
    except ImportError:from ownership import assert_attach_available
    assert_attach_available(self.config)
    previous=self.executor.state.get('position')
    if previous and (previous.get('symbol')!=self.request['holding']['symbol'] or previous.get('quantity')!=self.request['holding']['quantity']):
     self.verify(previous,flat=True)
     self.executor.state.setdefault('management_audit',[]).append(dict(operation='EXTERNAL_FLAT_CONFIRMED',position=previous,at=self.clock(),orders_submitted=0))
     self.executor.state['position']=None;self.executor.save();previous=None
    if previous and self.mode not in ('DETACHED','RECOVERY_REQUIRED'):
     raise ValueError('A strategy-owned position already exists')
    owned=self.attach(self.request['holding'])
    self.verify(owned,flat=False)
    self.executor.state['position']=dict(owned);self.executor.state['detached_position']=None
    self.executor.state.setdefault('management_audit',[]).append(dict(operation='ATTACH',at=self.clock(),position=owned,orders_submitted=0))
    # Attachment manages this holding, without arming fresh entries or reversals.
    self.config['_managed_resume']=True
    self.save_mode('ATTACHED');self.engine.position=dict(owned,entry_confirmed_at=self.clock())
    self.update('ATTACHED',position=owned,orders_submitted=0,entries_paused=True)
    return False
   self.save_mode('STOPPING')
   owned=self.executor.state.get('position') or self.executor.state.get('detached_position') or self.executor.state.get('stop_verification_position')
   if owned and self.closed_position is None:
    broker=self.verify(owned,flat=None)
    if broker.get('flat'):
     self.closed_position=dict(owned)
     self.executor.state['position']=None;self.executor.state['detached_position']=None;self.executor.save()
    else:
     # Reclaim a detached holding solely for this explicitly requested close.
     self.executor.state['position']=dict(owned);self.executor.save()
     self.engine.position=dict(owned)
     result=self.submit(close_action(owned,self.clock())) or {}
     if result.get('deferred'):
      self.update('WAITING_FOR_SOURCE',notice='Waiting for market and a fresh executable quote; position remains open')
      return False
     if self.executor.state.get('pending') or self.executor.state.get('position'):raise ValueError('Close is not fully confirmed; retained exposure/order requires reconciliation')
     self.closed_position=dict(owned)
   self.update('VERIFYING_FLAT',notice='Checking broker flat state before reporting Stop complete')
   self.verify(self.closed_position,flat=True)
   self.executor.state['position']=None;self.executor.state['detached_position']=None;self.executor.state.pop('stop_verification_position',None);self.engine.position=None
   self.save_mode('STOPPED');self.update('STOPPED',broker_flat_confirmed=self.closed_position is not None and self.config['execution_mode']=='LIVE',simulated_flat_confirmed=self.closed_position is not None and self.config['execution_mode']=='PAPER',no_owned_position=self.closed_position is None,position=self.closed_position)
   return True
  except Exception as error:
   if operation=='STOP':
    self.save_mode('RECOVERY_REQUIRED')
    # Preserve the original owned contract even if fill confirmation preceded a failed broker read.
    if self.closed_position:self.executor.state['stop_verification_position']=dict(self.closed_position);self.executor.save()
   self.update('RECOVERY_REQUIRED' if operation=='STOP' else 'REJECTED',error=str(error),broker_flat_confirmed=False,
               retained_position=self.executor.state.get('position') or self.executor.state.get('detached_position'),
               retained_pending=self.executor.state.get('pending'))
   return False
