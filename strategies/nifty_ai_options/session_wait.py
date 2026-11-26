"""Cached, fail-closed regular-session readiness. No authentication or orders."""
import time
from datetime import datetime
from zoneinfo import ZoneInfo
IST=ZoneInfo("Asia/Kolkata")

class SessionWait:
    def __init__(self,check,opening,closing,*,clock=time.time,refresh_seconds=15,bounds=None):
        self.check=check;self.opening=opening;self.closing=closing
        self.clock=clock;self.refresh_seconds=refresh_seconds
        self.checked_at=None;self.ready=False;self.error=None;self.session_day=None
        self.state="WAITING_FOR_MARKET";self.changed=False
        self.bounds=bounds;self.bounds_day=None;self.bounds_checked_at=None
    def poll(self,force=False):
        now=self.clock();local=datetime.fromtimestamp(now,IST)
        if self.bounds is not None and self.bounds_day!=local.date():
            if self.bounds_checked_at is not None and now-self.bounds_checked_at<self.refresh_seconds:
                self.changed=self.ready;self.ready=False;self.state='WAITING_FOR_MARKET_STATUS'
                return False
            self.bounds_checked_at=now
            try:
                metadata=self.bounds()
                opening,closing=metadata['opening_minutes'],metadata['closing_minutes']
                if any(isinstance(v,bool) or not isinstance(v,int) for v in (opening,closing)) or not 0<=opening<closing<=1440:raise ValueError('Invalid current regular-session bounds')
                self.opening,self.closing=opening,closing;self.bounds_day=local.date()
            except Exception as exc:
                self.changed=self.ready;self.ready=False;self.error=type(exc).__name__;self.state='WAITING_FOR_MARKET_STATUS'
                return False
        within=self.opening<=local.hour*60+local.minute<self.closing
        prior=self.ready
        if not within:
            self.ready=False;self.error=None;self.checked_at=None
        elif force or self.checked_at is None or now-self.checked_at>=self.refresh_seconds:
            self.checked_at=now
            try:self.ready=bool(self.check());self.error=None
            except Exception as exc:self.ready=False;self.error=type(exc).__name__
        self.changed=prior!=self.ready or self.ready and self.session_day!=local.date()
        if self.ready:self.session_day=local.date()
        self.state="READY" if self.ready else "WAITING_FOR_MARKET_STATUS" if self.error else "WAITING_FOR_MARKET"
        return self.ready
    def snapshot(self):
        return dict(market_state=self.state,market_status_checked_at=self.checked_at,market_status_error=self.error)


def reconcile_bodies(engine,confirmed,symbols,frame,stamp,opening,*,sma_enabled=False):
    """Recover only missed confirmation candles, never historical orders/prices.

    Renko continues from its retained state on the next actual fresh broker
    price. Historical bodies cannot arm an entry or become live-price inputs.
    Exact provider confirmation retains every recovery read and its availability.
    """
    local=datetime.fromtimestamp(stamp,IST)
    anchor=local.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()+opening*60
    recovered=[]
    for kind,symbol,minutes in list((kind,symbol,frame) for kind,symbol in symbols)+([('sma',symbols[0][1],1)] if sma_enabled else []):
        seconds=minutes*60;bucket=anchor+int((stamp-anchor)//seconds)*seconds
        prior=engine.last_time.get(kind)
        if prior is None:continue
        start=max(anchor,prior+seconds)
        for at in range(int(start),int(bucket),seconds):
            event=confirmed.confirm(dict(kind=kind,timestamp=at,close=1),symbol,minutes,previous=prior,continuous=False,opening_minutes=opening)
            if kind=='sma':
                # Historical updates maintain SMA memory, with broker ownership
                # restored after each update and every historical action discarded.
                owned=engine.position
                try:
                    engine.position=None
                    engine.update(event)
                finally:engine.position=owned
            else:
                if kind=='underlying' and hasattr(engine,'band'):
                    engine.band.observe(event,engine.config)
                    engine.session_band_exit_pending=engine.band.exit_reason(engine.position)
                engine.last_time[kind]=at
            prior=at;recovered.append(dict(kind=kind,symbol=symbol,timestamp=at,source_basis=event['source_basis']))
    if sma_enabled and any(item['kind']=='sma' for item in recovered) and engine.position:
        diff=getattr(engine.sma,'previous',None)
        side=engine.position.get('side')
        if diff is not None and ((side in ('LONG','CE') and diff<0) or (side in ('SHORT','PE') and diff>0)):
            engine.session_sma_exit_pending=True
    try:from .manual_entry import clear_entry_signal
    except ImportError:from manual_entry import clear_entry_signal
    clear_entry_signal(engine)
    return recovered


class ReopenConnection:
    """One bounded reconnect on regular reopening, not endless SDK retries."""
    def __init__(self,reconnect):
        self.reconnect=reconnect;self.saw_closed=False;self.restarting=False
    def observe(self,ready):
        if not ready:
            self.saw_closed=True;return False
        if not self.saw_closed:return False
        self.restarting=True
        try:self.reconnect()
        finally:self.restarting=False
        self.saw_closed=False
        return True


class SavedAccountSession:
    """Reload changed exact-account saved credentials; never log in or write them."""
    def __init__(self,current,paths,*,load,verify,apply):
        self.current=current;self.paths=tuple(paths);self.load=load;self.verify=verify;self.apply=apply
        self.signature=self._signature()
    def _signature(self):
        result=[]
        for path in self.paths:
            info=path.stat();result.append((info.st_ino,info.st_mtime_ns,info.st_size))
        return tuple(result)
    def refresh(self,force=False):
        signature=self._signature()
        if not force and signature==self.signature:return self.current
        replacement=self.load()
        try:self.verify(replacement)
        except Exception:
            if replacement is not self.current:replacement._sector_pulse_ipv4_session.close()
            raise
        previous=self.current
        self.apply(replacement);self.current=replacement;self.signature=signature
        if previous is not replacement:
            previous._sector_pulse_ipv4_session.close()
        return replacement
