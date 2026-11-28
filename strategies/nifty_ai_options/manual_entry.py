"""One-shot operator entry requests consumed only by their already-running AI child.
No broker client, process activation, order retry, position adoption or mode changes.
"""
import json,re,time,math,threading
from pathlib import Path
try:from .run import atomic
except ImportError:from run import atomic

IDENTITY=('account_id','broker','run_id','runtime_session','underlying','mode','route','timeframe')
TERMINAL={'FILLED','REJECTED','FAILED_OR_PENDING'}
class ManualNotReady(ValueError):pass

def runtime_identity(config,directory,mode):
    session=config.get('runtime_session')
    if not isinstance(session,str) or not re.fullmatch('[a-f0-9]{32}',session):raise ValueError('Current runtime session is required for manual entry')
    return dict(account_id=config['account'],broker=config['broker'],run_id=Path(directory).name,runtime_session=session,
                underlying=config['underlying'],mode=mode,route=config['execution_route'],timeframe=config['timeframe'])

def enqueue(directory,expected,payload,*,now=None):
    now=time.time() if now is None else now;directory=Path(directory)
    for key in IDENTITY:
        if payload.get(key)!=expected.get(key):raise ValueError('Manual entry differs from the active '+key.replace('_',' '))
    identifier=payload.get('request_id')
    if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('A unique manual entry request is required')
    allowed={'LONG','SHORT'} if expected['route']=='DIRECT' else {'CE','PE'}
    if payload.get('direction') not in allowed:raise ValueError('Select an explicit manual entry direction')
    root=directory/'manual-entry';receipt=root/'receipts'/(identifier+'.json')
    if receipt.exists():
        previous=json.loads(receipt.read_text())
        if any(previous.get(key)!=expected.get(key) for key in IDENTITY) or previous.get('direction')!=payload['direction']:raise ValueError('Manual request identifier was already used for another action')
        return previous
    current=root/'command.json'
    if current.exists():
        old=json.loads(current.read_text());old_receipt=root/'receipts'/(str(old.get('request_id'))+'.json')
        if old_receipt.exists() and json.loads(old_receipt.read_text()).get('phase') not in TERMINAL:raise ValueError('Another manual entry request is still pending')
    request=dict(expected,request_id=identifier,direction=payload['direction'],requested_at=now,expires_at=now+30,phase='QUEUED')
    atomic(receipt,request);atomic(root/'latest.json',request);atomic(current,request)
    return request

class ManualInbox:
    def __init__(self,config,directory,mode,*,clock=time.time):
        self.directory=Path(directory);self.root=self.directory/'manual-entry';self.expected=runtime_identity(config,directory,mode);self.clock=clock;self.last_stat=None
    def update(self,request,phase,**details):
        result=dict(request,phase=phase,updated_at=self.clock(),**details)
        atomic(self.root/'receipts'/(request['request_id']+'.json'),result);atomic(self.root/'latest.json',result)
        return result
    def claim(self):
        path=self.root/'command.json'
        try:stat=path.stat()
        except FileNotFoundError:return None
        identity=(stat.st_ino,stat.st_mtime_ns,stat.st_size)
        if identity==self.last_stat:return None
        self.last_stat=identity;request=json.loads(path.read_text());identifier=request.get('request_id')
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid manual command identity')
        receipt=self.root/'receipts'/(identifier+'.json')
        if not receipt.exists():raise ValueError('Manual command has no durable receipt')
        previous=json.loads(receipt.read_text())
        if previous.get('phase')!='QUEUED':return None
        if any(request.get(key)!=self.expected[key] for key in IDENTITY):
            self.update(request,'REJECTED',error='Manual command belongs to a different runtime');return None
        if not request.get('requested_at',0)<=self.clock()<=request.get('expires_at',0):
            self.update(request,'REJECTED',error='Manual entry request expired');return None
        self.update(request,'CLAIMED');return request

class ManualDispatcher:
    def __init__(self,config,directory,mode,engine,executor,*,prepare,quote_ready,submit,clock=time.time):
        self.inbox=ManualInbox(config,directory,mode,clock=clock);self.engine=engine;self.executor=executor;self.prepare=prepare;self.quote_ready=quote_ready;self.submit=submit;self.clock=clock;self.pending=None;self.prepared=False
    def poll(self):
        if self.pending is None:
            self.pending=self.inbox.claim();self.prepared=False
            if self.pending is not None:clear_entry_signal(self.engine)
        request=self.pending
        if request is None:return
        try:
            if self.clock()>request['expires_at']:raise ValueError('Manual entry request expired before a fresh quote was available')
            if self.executor.state.get('position') or self.executor.state.get('pending') or self.engine.position:raise ValueError('Manual entry requires no owned position or pending order')
            if not self.prepared:
                self.prepare(request['direction']);self.prepared=True;self.inbox.update(request,'PREPARING')
            at=self.quote_ready()
            action=self.engine.manual_entry(request['direction'],at)
        except ManualNotReady:return
        except ValueError as error:
            self.inbox.update(request,'REJECTED',error=str(error));self.pending=None;return
        self.inbox.update(request,'SUBMITTING')
        try:
            result=self.submit(action) or {}
            if result.get('deferred') is True:
                self.inbox.update(request,'REJECTED',error='Market entry remained unfilled; no position opened' if result.get('terminal_no_fill') else (str(result.get('detail') or 'Executable depth unavailable')+'; no order sent') if result.get('reason')=='ENTRY_DEPTH_UNAVAILABLE' else 'Position control paused entry; no order sent' if result.get('reason')=='WAITING_FOR_POSITION_CONTROL' else 'Source unavailable before submission; no order sent' if result.get('reason')=='WAITING_FOR_SOURCE' else 'Market closed before submission; no order sent')
                self.pending=None;return
            own=self.executor.state.get('position')
            if self.executor.state.get('pending') or not own or own.get('symbol')!=action['position']['symbol']:raise RuntimeError('Manual fill is unresolved; retained for reconciliation')
            if self.engine.position is not None:self.engine.position['entry_confirmed_at']=self.clock()
            self.inbox.update(request,'FILLED',operation='OPEN',confirmed_at=self.clock(),symbol=own['symbol'],quantity=own.get('quantity'),fill_price=own.get('fill_price',own.get('entry_price')),order_id=result.get('order_id'),strategy_exits_active=True)
            self.pending=None
        except Exception as error:
            self.inbox.update(request,'FAILED_OR_PENDING',error=str(error) if isinstance(error,(ValueError,RuntimeError)) else 'Manual entry result requires reconciliation')
            self.pending=None
            raise

class LatestQuote:
    """One cached quote per owned symbol; broker callbacks keep it fresh during fills."""
    def __init__(self,symbol,*,clock=time.time,max_age=5):
        self.symbol=symbol;self.clock=clock;self.max_age=max_age;self.lock=threading.Lock();self.value=None
    def accept(self,tick):
        if not isinstance(tick,dict) or tick.get('symbol')!=self.symbol:return False
        stamp=tick.get('exch_feed_time') or tick.get('last_traded_time');price=tick.get('ltp')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (stamp,price)) or price<=0:return False
        if stamp>1e12:stamp/=1000
        if not 0<=self.clock()-stamp<=self.max_age:return False
        with self.lock:
            if self.value and stamp<self.value['timestamp']:return False
            self.value=dict(timestamp=stamp,ltp=price)
        return True
    def get(self):
        with self.lock:quote=dict(self.value) if self.value else None
        if not quote or not 0<=self.clock()-quote['timestamp']<=self.max_age:raise ManualNotReady('Waiting for a fresh selected-broker quote')
        return quote

def clear_entry_signal(engine):
    if hasattr(engine,'sma_only_pending'):engine.sma_only_pending=None
    band=getattr(engine,'band',None)
    if band:band.consume_entry()
    premium_gate=getattr(engine,'premium_entry_confirmation',None)
    if premium_gate:premium_gate.clear()
    if hasattr(engine,'pending_direction'):engine.pending_direction=None
    if hasattr(engine,'pending_underlying_flip'):engine.pending_underlying_flip=None
    if hasattr(engine,'pending_underlying_flip_source_at'):engine.pending_underlying_flip_source_at=None
    gate=getattr(engine,'entry_confirmation',None)
    if gate:gate.clear()

def restore_unsubmitted(engine,executor,action):
    """Restore retained ownership after a proven pre-submission deferral."""
    owned=executor.state.get('position')
    if owned:
        restored=dict(owned)
        original=action.get('position') or {}
        if action.get('action') in ('SELL','CLOSE_LONG','CLOSE_SHORT') and original.get('symbol')==owned.get('symbol'):
            restored.update(original)
        engine.position=restored
    else:engine.position=None
    clear_entry_signal(engine)

def automatic_actions(engine,executor,manual,actions):
    if getattr(engine,'entry_paused',False):
        if any(a['action'] in ('BUY','OPEN_LONG','OPEN_SHORT') for a in actions):engine.position=None
        clear_entry_signal(engine)
        return [a for a in actions if a['action'] not in ('BUY','OPEN_LONG','OPEN_SHORT','SELECT')]
    if manual.pending is None:return actions
    if executor.state.get('position') or executor.state.get('pending'):raise ValueError('Manual preparation encountered retained exposure')
    engine.position=None;clear_entry_signal(engine)
    return []


def confirm_entry_fill(engine,executor,action,*,clock=time.time):
    if action.get('action') not in ('BUY','OPEN_LONG','OPEN_SHORT'):return
    owned=executor.state.get('position')
    if executor.state.get('pending') or not owned or owned.get('symbol')!=action['position']['symbol']:raise ValueError('Entry fill ownership is unresolved')
    if engine.position is not None:engine.position['entry_confirmed_at']=clock()
    if engine.config.get('swing_targets_enabled'):engine.swing_wait=None
    from strategies.nifty_ai_options.zone_targets import filled,enabled as zone_enabled
    if zone_enabled(engine) and engine.position is not None:
        engine.position.update({k:owned[k] for k in ('fill_price','order_id') if k in owned})
    filled(engine)
    from strategies.nifty_ai_options.support_retest import get
    retest=get(engine)
    if retest:
        if engine.position is not None:engine.position.update({k:owned[k] for k in ('fill_price','order_id') if k in owned})
        retest.capture(engine,dict(action=action['action'],timestamp=action['timestamp'],position=engine.position)) if engine.position is not None else None
        if engine.position is not None:
            owned.pop('retained_swing_target',None)
            if engine.position.get('retained_swing_target'):owned['retained_swing_target']=__import__('copy').deepcopy(engine.position['retained_swing_target'])
            executor.save()
        retest.filled(engine,owned)


def confirmed_flat_entry(engine,executor):
    """Opposite/new entry cannot advance while a close retains ownership or intent."""
    if executor.state.get('position') or executor.state.get('pending'):return None
    return engine.selected_gate_entry()
