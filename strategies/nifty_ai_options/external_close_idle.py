"""Instrument-owned worker ends after authoritative external full closure.
No process activation, order submission or broker client is created here.
"""
import copy,fcntl,hashlib,json,math,os,time
from pathlib import Path
from strategies.nifty_ai_options.run import atomic
from strategies.nifty_ai_options.manual_entry import runtime_identity,clear_entry_signal
INTERVAL=10

def owned_rows(state):
 rows=([state['position']] if state.get('position') else [])+list(state.get('positions') or [])
 rows += [s['position'] for s in state.get('closing_legs',{}).values() if s.get('position')]
 found={}
 for row in rows:
  if not isinstance(row,dict) or not row.get('symbol') or isinstance(row.get('quantity'),bool) or not isinstance(row.get('quantity'),(int,float)) or not math.isfinite(row['quantity']) or row['quantity']<=0:raise ValueError('Exact managed position required')
  key=(row['symbol'],row.get('side'),row.get('order_id'),row['quantity'])
  found.setdefault(key,copy.deepcopy(row))
 return list(found.values())

def uncertain(state):
 if state.get('pending') or state.get('detached_position') or state.get('stop_verification_position'):return True
 if any(s.get('pending') for s in state.get('closing_legs',{}).values()):return True
 return any(r.get('phase') in ('SUBMITTING','UNCERTAIN') for r in state.get('entry_requests',{}).values())

def append_once(directory,record):
 path=Path(directory)/'events.jsonl';key=record['external_close_receipt']
 if path.exists():
  with path.open() as rows:
   for line in rows:
    if line.strip() and json.loads(line).get('external_close_receipt')==key:return
 with path.open('a') as out:
  out.write(json.dumps(record)+'\n');out.flush();os.fsync(out.fileno())

class ExternalCloseIdle:
 def __init__(self,manager):
  self.manager=manager;self.next_at=0;self.failures=0;self.status=None
 def command_waiting(self):
  root=self.manager.directory/'position-controls';command=root/'command.json'
  if not command.exists():return False
  c=json.loads(command.read_text());receipt=root/'receipts'/(str(c.get('request_id'))+'.json')
  if not receipt.exists():return True
  return json.loads(receipt.read_text()).get('phase') in ('QUEUED','CLAIMED','WAITING_FOR_SOURCE','VERIFYING_FLAT')
 def poll(self,*,busy=False):
  m=self.manager;c=m.config;state=m.executor.state;now=m.clock()
  if c.get('execution_mode')!='LIVE' or not getattr(m.executor,'live',False) or busy or m.mode not in ('MANAGED','ATTACHED') or uncertain(state):return False
  if now<self.next_at:return False
  if self.command_waiting():return False
  positions=owned_rows(state)
  if not positions:return False
  if any(p.get('underlying',c['underlying'])!=c['underlying'] or p.get('account',c['account'])!=c['account'] for p in positions):
   self.status=dict(state='UNVERIFIED',checked_at=now,error='Managed position belongs to another instrument/account');return False
  self.next_at=now+INTERVAL
  root=m.directory/'position-controls';root.mkdir(parents=True,exist_ok=True)
  with (root/'inbox.lock').open('a') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:return False
   try:
    if self.command_waiting() or uncertain(state):return False
    proofs=[]
    for owned in positions:
     started=m.clock();proof=m.verify(owned,flat=None);finished=m.clock()
     if not isinstance(proof,dict) or type(proof.get('flat')) is not bool or isinstance(proof.get('quantity'),bool) or not isinstance(proof.get('quantity'),(int,float)) or not math.isfinite(proof['quantity']):raise ValueError('Authoritative broker quantity/flat confirmation required')
     checked=proof.get('checked_at',finished)
     if not isinstance(checked,(int,float)) or isinstance(checked,bool) or not math.isfinite(checked) or not 0<=finished-checked<=5 or not 0<=finished-started<=15:raise ValueError('Broker reconciliation is stale')
     if proof.get('account',c['account'])!=c['account'] or proof.get('broker',c['broker'])!=c['broker']:raise ValueError('Broker reconciliation belongs to another account')
     if proof['flat'] is not True or proof['quantity']!=0:
      self.status=dict(state='POSITION_STILL_OPEN',checked_at=finished);self.failures=0;return False
     proofs.append(dict(symbol=owned['symbol'],quantity=0,checked_at=checked,broker=c['broker'],account=c['account']))
    if self.command_waiting() or uncertain(state):return False
    now=m.clock()
    if any(not 0<=now-p['checked_at']<=15 for p in proofs):raise ValueError('Multi-leg broker reconciliation expired')
    identity=hashlib.sha256(json.dumps([c['account'],c.get('runtime_session'),positions],sort_keys=True).encode()).hexdigest()
    recovery=dict(revision='external-close-idle-v1',proof=identity,phase='PREPARED',positions=positions,broker_proofs=proofs,checked_at=now,orders_submitted=0,automatic_reentry=False)
    atomic(m.directory/'external-close-reconciliation.json',recovery)
    # Enrich with exact fills when an existing broker-specific reader supports it.
    # Lifecycle closure uses the successful authoritative flat checks above.
    collector=getattr(m.executor,'reconcile_external_close',None)
    for i,owned in enumerate(positions):
     fill=None;unavailable=None
     if callable(collector):
      try:fill=collector(owned)
      except Exception as error:unavailable=str(error)[:240]
     if fill and fill.get('broker_flat_confirmed') is True and fill.get('quantity')==owned['quantity']:
      action=dict(action='SELL' if owned.get('side') in ('CE','PE') else 'CLOSE_SHORT' if owned.get('side')=='SHORT' else 'CLOSE_LONG',position=owned,timestamp=fill.get('broker_trade_at',fill['broker_order_at']),reason='EXTERNAL_BROKER_CLOSE')
      result=dict(order_id=fill['exit_order'],filled_quantity=fill['quantity'],fill_price=fill['fill_price'],dry_run=False,external_exit=True,filled_at=fill.get('broker_trade_at',now),fill_time_basis=fill.get('fill_time_basis','broker-flat confirmation'),costs_unavailable_reason='Fees and taxes not reconciled')
     else:
      action=dict(action='EXTERNAL_FLAT',position=owned,timestamp=now,reason='EXTERNAL_BROKER_CLOSE')
      result=dict(broker_flat_confirmed=True,orders_submitted=0,fill_price=None,filled_quantity=None,fill_unavailable=unavailable or 'Exact closing fills unavailable; no price inferred')
     append_once(m.directory,dict(action=action,result=result,recorded_at=now,external_close_receipt=identity+'|'+str(i),broker_reconciliation=proofs[i]))
     if fill and result.get('fill_price') is not None:
      path=m.directory/'markers.json';markers=json.loads(path.read_text()) if path.exists() else []
      receipt_id=identity+'|'+str(i)
      if not any(row.get('receipt_id')==receipt_id for row in markers):
       markers.append(dict(receipt_id=receipt_id,timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=now,symbol=owned['symbol'],action=action['action'],price=result['fill_price'],mode='LIVE',order_id=result['order_id'],confirmed=True,external_exit=True))
       atomic(path,markers[-1000:])
    if any(not 0<=m.clock()-p['checked_at']<=15 for p in proofs):raise ValueError('Broker flat confirmation expired before lifecycle commit')
    state.setdefault('reconciliations',[]).append(dict(recovery,phase='EXTERNAL_CLOSED_IDLE'))
    state['reconciliations']=state['reconciliations'][-200:]
    state['position']=None;state['pending']=None;state['positions']=[];state['closing_legs']={}
    for request in state.get('entry_requests',{}).values():
     if request.get('phase') not in ('COMPLETE','FAILED'):request.update(phase='CANCELLED',reason='External broker closure; explicit new Start required')
    state.pop('entry_reservation',None)
    m.engine.position=None;clear_entry_signal(m.engine);m.engine.entry_paused=True
    m.save_mode('STOPPED')
    m.request=dict(runtime_identity(c,m.directory,'LIVE'),operation='STOP',request_id=identity[:32],requested_at=now,source='BROKER_CONFIRMED_EXTERNAL_CLOSE')
    m.update('STOPPED',notice='Manual broker exit confirmed · strategy stopped. Start again when ready.',broker_flat_confirmed=True,positions=positions,orders_submitted=0,automatic_reentry=False)
    atomic(m.directory/'external-close-reconciliation.json',dict(recovery,phase='EXTERNAL_CLOSED_IDLE',completed_at=m.clock()))
    self.status=dict(state='EXTERNAL_CLOSED_IDLE',checked_at=now);self.failures=0
    return True
   except Exception as error:
    self.failures+=1;self.next_at=m.clock()+min(60,INTERVAL*2**min(self.failures-1,3))
    self.status=dict(state='UNVERIFIED',checked_at=m.clock(),error=str(error)[:240],retry_at=self.next_at)
    return False
