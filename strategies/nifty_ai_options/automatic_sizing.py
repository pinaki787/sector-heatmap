"""User-started native sizing refresh and causal entry gating.

Existing positions and pending broker intents retain their original geometry.
Flat engines are rebuilt from the exact consumed confirmed observations before
new entries can use a changed size. Warm-up actions never become broker orders.
"""
import threading,time,secrets
from pathlib import Path
try:
    from .native_sizing import ensure,acquire,apply_reference
    from .run import atomic
except ImportError:
    from native_sizing import ensure,acquire,apply_reference
    from run import atomic

class ReferenceMonitor:
    def __init__(self,config,*,clock=time.time,fetch=acquire,start=True):
        self.config=dict(config);self.clock=clock;self.fetch=fetch;self.lock=threading.RLock();self.stop=threading.Event()
        self.reference=config.get('reference_context');self.error=None;self.updated_at=None
        self.thread=None
        if start:
            self.thread=threading.Thread(target=self._run,daemon=True,name='native-sizing-refresh');self.thread.start()
    def refresh(self):
        with self.lock:
            ref=self.reference
            if ref and ref.get('valid_until',0)>self.clock():return
        try:
            result=self.fetch(self.config)
            with self.lock:self.reference=result;self.error=None;self.updated_at=self.clock()
        except Exception as error:
            with self.lock:self.error=str(error) if isinstance(error,ValueError) else 'Native sizing connection unavailable';self.updated_at=self.clock()
    def _run(self):
        while not self.stop.is_set():self.refresh();self.stop.wait(5)
    def current(self):
        with self.lock:
            r=self.reference
            return dict(r) if r and r.get('valid_until',0)>self.clock() else None
    def status(self):
        with self.lock:return dict(state='READY' if self.current() else 'WAITING_FOR_NATIVE_SIZE',error=self.error,updated_at=self.updated_at,valid_until=(self.reference or {}).get('valid_until'))
    def close(self):self.stop.set()

class AutoSizedStrategy:
    _local={'_inner','_monitor','_factory','_exposure','_chart_source','_config_path','_events','_selection','_delta','_active_box','_active_window','_rebuilding'}
    def __init__(self,engine,monitor,*,exposure=lambda:False,chart_source=None,config_path=None):
        self._inner=engine;self._monitor=monitor;self._factory=type(engine);self._exposure=exposure;self._chart_source=chart_source;self._config_path=config_path
        self._events=[];self._selection=None;self._delta=None;self._active_box=engine.config['reference_value'];self._active_window=engine.config.get('reference_completed_parent_at');self._rebuilding=False
    def __getattr__(self,name):return getattr(self._inner,name)
    def __setattr__(self,name,value):
        if name in self._local or name.startswith('_'):object.__setattr__(self,name,value)
        else:setattr(self._inner,name,value)
    @property
    def native_sizing_status(self):return dict(self._monitor.status(),active_parent_box=self._active_box,active_parent_end=self._active_window,frozen=bool(self._inner.position or self._exposure()))
    def close_native_sizing(self):self._monitor.close()
    def reset_contract(self,contract,delta=None):
        old=(self._selection or {}).get('symbol')
        if delta is None:self._inner.reset_contract(contract)
        else:self._inner.reset_contract(contract,delta)
        self._selection=dict(contract);self._delta=delta
        if old!=contract['symbol']:self._events=[e for e in self._events if e['kind']!='premium' and not (e['kind']=='price' and e.get('series')=='premium')]
    def _refresh(self):
        ref=self._monitor.current()
        if not ref:return False
        if ref['native_box']==self._active_box:
            changed_window=self._active_window!=ref['completed_parent_at']
            self._active_window=ref['completed_parent_at']
            self._inner.config=ensure(self._inner.config) if self._inner.config.get('sizing_mode')=='MANUAL_PARENT' else apply_reference(self._inner.config,ref)
            if changed_window and self._config_path:atomic(self._config_path,self._inner.config)
            return True
        if self._inner.position or self._exposure():return False
        config=apply_reference(self._inner.config,ref);replacement=self._factory(config)
        if self._selection:
            if self._delta is None:replacement.reset_contract(self._selection)
            else:replacement.reset_contract(self._selection,self._delta)
        for event in self._events:
            (replacement.update_hybrid(event) if event.get('_hybrid') else replacement.update(event));replacement.position=None
        if hasattr(replacement,'pending_direction'):replacement.pending_direction=None
        if hasattr(replacement,'pending_underlying_flip'):replacement.pending_underlying_flip=None
        if getattr(replacement,'band',None):replacement.band.retest=None
        if getattr(replacement,'premium_entry_confirmation',None):replacement.premium_entry_confirmation.clear()
        self._inner=replacement;self._active_box=ref['native_box'];self._active_window=ref['completed_parent_at']
        if self._chart_source:
            for kind,symbol,brick in [('underlying',config['underlying'],replacement.spot_size),('premium',(getattr(replacement,'contract',{}) or {}).get('symbol'),(getattr(replacement,'contract',{}) or {}).get('option_brick'))]:
                rows=[[e['timestamp'],None,None,None,e['close'],None] for e in self._events if e['kind']==kind and not e.get('_hybrid')]
                if symbol and brick and rows:self._chart_source.seed(symbol,config['timeframe'],rows,brick,preserve_observations=True)
        if self._config_path:atomic(self._config_path,config)
        return True
    def _clear_entry(self):
        band=getattr(self._inner,'band',None)
        if band:band.retest=None
        premium_gate=getattr(self._inner,'premium_entry_confirmation',None)
        if premium_gate:premium_gate.clear()
        if hasattr(self._inner,'pending_direction'):self._inner.pending_direction=None
        if hasattr(self._inner,'pending_underlying_flip'):self._inner.pending_underlying_flip=None
        gate=getattr(self._inner,'entry_confirmation',None)
        if gate:gate.clear()
    def manual_entry(self,direction,at):
        if not self._refresh():raise ValueError('Fresh automatic sizing is required for manual entry')
        if self._exposure():raise ValueError('Owned exposure or a pending order prevents manual entry')
        return self._inner.manual_entry(direction,at)

    def selected_gate_entry(self):
        if getattr(self._inner,'entry_paused',False):self._clear_entry();return None
        if not self._refresh():self._clear_entry();return None
        return self._inner.selected_gate_entry()
    def update_hybrid(self,event):
        return self._update(dict(event,_hybrid=True),hybrid=True)
    def update(self,event):
        return self._update(event,hybrid=False)
    def _update(self,event,*,hybrid):
        ready=self._refresh();prior=self._inner.position
        actions=(self._inner.update_hybrid(event) if hybrid else self._inner.update(event));self._events.append(dict(event))
        if ready:return actions
        # Keep genuine exits for existing exposure; reject every stale-size entry.
        entries={'BUY','OPEN_LONG','OPEN_SHORT'}
        if any(a['action'] in entries for a in actions):self._inner.position=None
        self._clear_entry()
        return [a for a in actions if a['action'] not in entries and (prior is not None or a['action']=='SELECT')]

def runtime_configuration(config,output):
    """Every user-started adapter obtains verified automatic sizing before broker setup."""
    if config.get('_verification_only'):raise ValueError('Verification-only configuration cannot start a runtime')
    updated=ensure(config);reference=updated.get('reference_context') or {}
    manual=updated.get('sizing_mode')=='MANUAL_PARENT' and updated.get('reference_source')=='manual_parent_override' and updated.get('reference_native_provider')=='USER'
    if not manual and (updated.get('reference_native_provider')!='TRADINGVIEW' or not reference.get('verified_native_size') or not reference.get('completed_parent') or reference.get('valid_until',0)<=time.time()):
        raise ValueError('Fresh verified automatic native sizing is required before runtime setup')
    updated=dict(updated,runtime_session=secrets.token_hex(16))
    atomic(Path(output)/'config.json',updated)
    return updated

def automatic_strategy(engine,config,*,exposure,chart_source,config_path):
    if config.get('sizing_mode')=='MANUAL_PARENT':
        monitor=ReferenceMonitor(config,fetch=lambda c:ensure(c)['reference_context'])
        return AutoSizedStrategy(engine,monitor,exposure=exposure,chart_source=chart_source,config_path=config_path)
    if config.get('reference_native_provider')!='TRADINGVIEW':raise ValueError('Automatic native sizing is required for the runtime')
    return AutoSizedStrategy(engine,ReferenceMonitor(config),exposure=exposure,chart_source=chart_source,config_path=config_path)
