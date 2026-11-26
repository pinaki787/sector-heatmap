"""Cross-process entry admission and durable account entry revision.

This never enables trading. Callers retain native permission, preview, risk,
position and quote checks. Reduce-only/exit paths do not acquire this lock.
"""
from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import stat
import threading
from .file_lock import lock_file,unlock_file

_LOCAL=threading.local()
_FD_MUTEX=threading.Lock()
_OPEN_FDS=set()


def _after_fork_child():
    global _FD_MUTEX
    # Close inherited descriptors without unlocking the parent's open-file lock.
    for fd in tuple(_OPEN_FDS):
        try:os.close(fd)
        except OSError:pass
    _OPEN_FDS.clear()
    _LOCAL.active={}
    _FD_MUTEX=threading.Lock()


def _before_fork():
    _FD_MUTEX.acquire()


def _after_fork_parent():
    _FD_MUTEX.release()


if hasattr(os,"register_at_fork"):
    os.register_at_fork(before=_before_fork,after_in_parent=_after_fork_parent,after_in_child=_after_fork_child)


class ChartOrderNotSent(ValueError):
    """Only raised before invoking the native placement API."""


def _path(broker,folder=None):
    account=os.environ.get("SECTOR_PULSE_WORKSPACE_ID")
    registry=os.environ.get("SECTOR_PULSE_WORKSPACE_REGISTRY")
    explicit=Path(folder).absolute() if folder is not None else None
    if explicit is not None and (not explicit.is_dir() or explicit.resolve()!=explicit):
        raise ValueError("The explicit account entry-admission folder is unavailable.")
    if not account and not registry:
        return explicit/"entry-admission.lock" if explicit is not None else None
    if not account or not registry or len(account)!=32 or any(c not in "0123456789abcdef" for c in account):
        raise ValueError("Invalid account entry-admission binding.")
    expected=os.environ.get("SECTOR_PULSE_WORKSPACE_BROKER")
    if expected and expected!=broker:raise PermissionError("Entry broker differs from this private workspace.")
    folder=Path(registry).resolve().parent/"accounts"/account
    if explicit is not None and explicit!=folder:
        raise PermissionError("Explicit account entry admission differs from this private workspace.")
    if not folder.is_dir() or folder.resolve()!=folder:
        raise ValueError("The registered private account folder is unavailable.")
    return folder/"entry-admission.lock"


@contextmanager
def entry_lock(broker,*,blocking=True,folder=None):
    path=_path(broker,folder)
    if path is None:
        yield None;return
    active=getattr(_LOCAL,"active",None)
    if active is None:active={};_LOCAL.active=active
    key=str(path)
    if key in active:
        yield active[key];return
    with _FD_MUTEX:
        fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
        _OPEN_FDS.add(fd)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError("Invalid entry admission file.")
        try:lock_file(fd,blocking=blocking)
        except BlockingIOError as error:
            if not blocking:
                raise ChartOrderNotSent("Another account entry is being checked; refresh this order before retrying.") from error
            raise
        active[key]=fd
        try:yield fd
        finally:
            del active[key]
            unlock_file(fd)
    finally:
        with _FD_MUTEX:
            _OPEN_FDS.discard(fd)
            os.close(fd)


def _revision(fd):
    os.lseek(fd,0,os.SEEK_SET)
    text=os.read(fd,128).strip(b"\0\r\n ")
    if not text:return 0
    if not text.isdigit() or len(text)>30:raise ValueError("Account entry revision is invalid.")
    return int(text)


def entry_revision(broker,*,folder=None):
    with entry_lock(broker,folder=folder) as fd:
        return str(_revision(fd)) if fd is not None else ""


def mark_entry_attempt(broker,*,folder=None):
    with entry_lock(broker,folder=folder) as fd:
        if fd is None:return ""
        revision=_revision(fd)+1
        raw=(str(revision)+"\n").encode()
        os.lseek(fd,0,os.SEEK_SET);os.write(fd,raw);os.ftruncate(fd,len(raw));os.fsync(fd)
        return str(revision)


def serialized_fyers_entry(method):
    @wraps(method)
    def call(*args,**kwargs):
        with entry_lock("FYERS"):return method(*args,**kwargs)
    return call


def serialized_chart_entry(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        adapter=kwargs["adapter"]
        # Delta's native execution lock is always outermost, matching its
        # existing manual/runner paths; the file lock remains reentrant.
        if adapter.broker=="DHAN":
            with adapter.execution.lock:
                with entry_lock("DHAN",folder=adapter.execution.folder):return method(self,*args,**kwargs)
        if adapter.broker=="DELTA_INDIA":
            with adapter.execution.lock:
                with entry_lock(adapter.broker):return method(self,*args,**kwargs)
        with entry_lock(adapter.broker):return method(self,*args,**kwargs)
    return call


def serialized_runner_entry(method):
    @wraps(method)
    def call(self,order,position,*args,**kwargs):
        config=self.state.get("config") or {}
        broker=getattr(self,"bound_broker",None) or config.get("broker") or "FYERS"
        if config.get("mode")=="LIVE" and broker=="DHAN" and self.is_entry_order(order,position):
            service=self.adapter.service
            with service.lock:
                with entry_lock("DHAN",folder=service.folder):
                    assert_dhan_chart_entry_allowed(service)
                    return method(self,order,position,*args,**kwargs)
        if config.get("mode")=="LIVE" and broker=="FYERS" and self.is_entry_order(order,position):
            with entry_lock(broker):return method(self,order,position,*args,**kwargs)
        return method(self,order,position,*args,**kwargs)
    return call


def serialized_delta_request(native_method):
    @wraps(native_method)
    def call(self,method,path,params=None,body=None,credentials=None):
        if method=="POST" and path=="/v2/orders" and isinstance(body,dict) and body.get("reduce_only") is not True:
            from .chart_trade_ownership import assert_workspace_chart_entry_allowed
            with entry_lock("DELTA_INDIA",blocking=False):
                try:
                    assert_workspace_chart_entry_allowed("DELTA_INDIA",client_order_id=body.get("client_order_id"))
                    mark_entry_attempt("DELTA_INDIA")
                except Exception as error:
                    raise ChartOrderNotSent("Delta entry admission failed before the native request.") from error
                return native_method(self,method,path,params=params,body=body,credentials=credentials)
        return native_method(self,method,path,params=params,body=body,credentials=credentials)
    return call


def place_fyers_entry(sender,payload):
    from .chart_trade_ownership import assert_workspace_chart_entry_allowed
    with entry_lock("FYERS",blocking=False):
        try:
            assert_workspace_chart_entry_allowed("FYERS")
            mark_entry_attempt("FYERS")
        except Exception as error:
            raise ChartOrderNotSent("FYERS entry admission failed before placement.") from error
        return sender(payload)


def serialized_fyers_strategy_entry(method):
    @wraps(method)
    def call(*args,**kwargs):
        if method.__globals__.get("DRY_RUN",True):return method(*args,**kwargs)
        with entry_lock("FYERS"):return method(*args,**kwargs)
    return call


def assert_dhan_chart_entry_allowed(service,*,client_order_id=None):
    from .chart_trade_ownership import assert_no_chart_entry_conflict
    if service.account.get("broker")!="DHAN":
        raise PermissionError("Selected account entry admission requires Dhan.")
    assert_no_chart_entry_conflict(Path(service.folder)/"chart-trading.sqlite3",
        service.account["id"],"DHAN",client_order_id=client_order_id)


def mark_dhan_entry_attempt(service,*,client_order_id=None):
    assert_dhan_chart_entry_allowed(service,client_order_id=client_order_id)
    return mark_entry_attempt("DHAN",folder=service.folder)


def serialized_dhan_entry(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        service=self if hasattr(self,"_submission_lock") else self.execution
        with service.lock:
            with entry_lock("DHAN",folder=service.folder):
                assert_dhan_chart_entry_allowed(service)
                return method(self,*args,**kwargs)
    return call


def serialized_dhan_strategy_entry(method):
    @wraps(method)
    def call(self,order,*args,**kwargs):
        # This existing long-option strategy adapter uses BUY for opening,
        # SELL for verified position exits. Generic short entries use chart plans.
        if order.get("side")==1:
            invoked=False
            try:
                with self.service.lock:
                    with entry_lock("DHAN",folder=self.service.folder):
                        assert_dhan_chart_entry_allowed(self.service)
                        invoked=True
                        return method(self,order,*args,**kwargs)
            except Exception as error:
                if invoked:raise
                return dict(s="error",code=400,message="Dhan entry admission rejected before submission: "+str(error))
        return method(self,order,*args,**kwargs)
    return call
