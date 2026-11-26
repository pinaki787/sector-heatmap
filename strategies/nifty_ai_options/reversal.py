"""Durable netted-contract reversal: retain a signal, close first, never overlap."""
import copy,hashlib,json,time

def remember(engine,executor,action):
 name=action.get('action')
 if name not in ('CLOSE_LONG','CLOSE_SHORT'):return None
 target='SHORT' if name=='CLOSE_LONG' else 'LONG'
 pending=getattr(engine,'pending_direction',None)
 session=getattr(engine,'config',{}).get('runtime_session')
 if not session or pending!=(target,action['timestamp']):return None
 owned=executor.state.get('position') or {}
 if owned.get('symbol')!=action['position'].get('symbol') or owned.get('side')!=action['position'].get('side'):return None
 previous=executor.state.get('pending_reversal')
 if previous and previous.get('phase') not in ('CANCELLED','COMPLETE'):return previous
 scope=dict(runtime_session=session,account=engine.config.get('account'),symbol=owned['symbol'],direction=target,signal_at=action['timestamp'])
 identity=hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()
 row=dict(scope,id=identity,phase='WAITING_FOR_FLAT',close_action=copy.deepcopy(action))
 closing=(getattr(engine,'contract',None) or {}).get('closing_minutes')
 if isinstance(closing,int) and not isinstance(closing,bool) and 0<closing<=1440:
  from datetime import datetime,timedelta
  from zoneinfo import ZoneInfo
  day=datetime.fromtimestamp(action['timestamp'],ZoneInfo('Asia/Kolkata')).replace(hour=0,minute=0,second=0,microsecond=0)
  row['expires_at']=(day+timedelta(minutes=closing)).timestamp()

 executor.state['pending_reversal']=row;executor.save();return row

def cancel(executor,row,reason):
 row.update(phase='CANCELLED',reason=reason)
 executor.state.setdefault('reversal_history',[]).append(dict(row))
 executor.state['reversal_history']=executor.state['reversal_history'][-200:]
 executor.state['pending_reversal']=None;executor.save()

def retry_verified_exit(engine,executor,row,submit):
 owned=executor.state.get('position')
 failure=executor.state.get('retained_exit_failure') or {}
 intent=failure.get('intent') or {}
 if (not owned or executor.state.get('pending') or row.get('phase')!='WAITING_FOR_FLAT'
     or failure.get('stage') not in ('CANCELLED_WITHOUT_FILL','PARTIAL_EXIT_REMAINS','EXIT_PRECHECK_FAILED')
     or owned.get('symbol')!=row['symbol'] or owned.get('side')==row['direction']
     or intent.get('action')!=row['close_action']['action']
     or (intent.get('position') or {}).get('symbol')!=owned['symbol']):return None
 now=time.time()
 if now-row.get('last_exit_attempt_at',0)<1:return None
 action=dict(copy.deepcopy(row['close_action']),timestamp=now,position=copy.deepcopy(owned))
 row['last_exit_attempt_at']=now;row['exit_attempts']=row.get('exit_attempts',0)+1;executor.save()
 return submit(action)

def advance(engine,executor,submit):
 row=executor.state.get('pending_reversal')
 if not row:return None
 config=getattr(engine,'config',{})
 if config.get('runtime_session')!=row['runtime_session'] or config.get('account')!=row.get('account'):
  cancel(executor,row,'Different run/account; previous signal not replayed');return None
 if row.get('expires_at') is not None and time.time()>=row['expires_at']:
  cancel(executor,row,'Trading session ended; old signal not replayed');return None
 if executor.state.get('pending'):return None
 if executor.state.get('position'):return retry_verified_exit(engine,executor,row,submit)
 if getattr(engine,'entry_paused',False):return None
 if row.get('phase') not in ('WAITING_FOR_FLAT','WAITING_FOR_ENTRY'):return None
 current=getattr(engine,'under_result',None)
 if config.get('supertrend_enabled',True):
  if not current:return None
  direction='LONG' if current['direction']<0 else 'SHORT'
  if direction!=row['direction']:
   cancel(executor,row,'Confirmed trend invalidated the retained reversal');return None
 if (getattr(engine,'contract',None) or {}).get('symbol')!=row['symbol']:
  cancel(executor,row,'Selected contract changed');return None
 engine.position=None;engine.pending_direction=(row['direction'],row['signal_at'])
 entry=engine.selected_gate_entry()
 if entry is None:
  row['phase']='WAITING_FOR_ENTRY';executor.save();return None
 if entry['action']!='OPEN_'+row['direction'] or entry['position'].get('symbol')!=row['symbol'] or entry['timestamp']!=row['signal_at']:
  engine.position=None;cancel(executor,row,'Entry differs from retained signal');raise ValueError('Retained direct reversal entry identity mismatch')
 row.update(phase='ENTRY_PREPARED',entry_action=copy.deepcopy(entry));executor.save()
 try:result=submit(entry)
 except Exception:
  row['phase']='ENTRY_UNCERTAIN' if executor.state.get('pending') else 'ENTRY_BLOCKED'
  executor.save();raise
 if result and result.get('deferred'):
  row['phase']='WAITING_FOR_ENTRY';executor.save();return result
 owned=executor.state.get('position')
 if executor.state.get('pending') or not owned or owned.get('symbol')!=row['symbol'] or owned.get('side')!=row['direction']:
  row['phase']='ENTRY_UNCERTAIN';executor.save();return result
 row['phase']='COMPLETE'
 executor.state.setdefault('reversal_history',[]).append(dict(row));executor.state['reversal_history']=executor.state['reversal_history'][-200:]
 executor.state['pending_reversal']=None;executor.save();return result


def execute(engine,executor,action,send):
 """Retain ownership after an unresolved close without repeating submission."""
 remember(engine,executor,action)
 if executor.state.get('pending'):
  engine.position=copy.deepcopy(executor.state.get('position'))
  return dict(deferred=True,reason='WAITING_FOR_ORDER_RECONCILIATION')
 try:return send()
 except (ValueError,RuntimeError) as error:
  owned=executor.state.get('position')
  if action.get('action') not in ('CLOSE_LONG','CLOSE_SHORT') or not owned or owned.get('symbol')!=action['position'].get('symbol'):raise
  if not executor.state.get('pending'):
   executor.state['retained_exit_failure']=dict(intent=copy.deepcopy(action),stage='EXIT_PRECHECK_FAILED',notice=str(error));executor.save()
  engine.position=copy.deepcopy(owned)
  return dict(deferred=True,reason='WAITING_FOR_EXIT_RECONCILIATION' if executor.state.get('pending') else 'WAITING_FOR_EXIT_PRECHECK')

def entered(executor,action):
 row=executor.state.get('pending_reversal')
 if not row or not action.get('action','').startswith('OPEN_') or executor.state.get('pending'):return
 owned=executor.state.get('position')
 if not owned or owned.get('symbol')!=row['symbol']:return
 row.update(phase='COMPLETE',entry_action=copy.deepcopy(action))
 executor.state.setdefault('reversal_history',[]).append(dict(row));executor.state['pending_reversal']=None;executor.save()

def suppress_pending(engine,executor,actions):
 if not executor.state.get('pending'):return actions
 engine.position=copy.deepcopy(executor.state.get('position'))
 try:from .manual_entry import clear_entry_signal
 except ImportError:from manual_entry import clear_entry_signal
 clear_entry_signal(engine)
 return []
