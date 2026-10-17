"""Read-only browser stream and isolated FYERS order notifications.

Order notifications wake reconciliation; REST remains authoritative for owned fills.
No notification can submit an order or manufacture a journal fill.
"""
from copy import deepcopy
import hashlib
import json
import threading
import time
from fyers_apiv3.FyersWebsocket import order_ws
from sector_heatmap.config import load_config
from sector_heatmap.market_data import configure_websocket_ca_bundle


class IndependentOrderSocket(order_ws.FyersOrderSocket):
    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def _FyersOrderSocket__on_open(self, ws):
        # SDK connect() calls on_open after a fixed sleep, before a slow
        # handshake can finish. Notify on the actual transport opening too.
        super()._FyersOrderSocket__on_open(ws)
        self.on_open()

    def _FyersOrderSocket__on_close(self, ws, close_code=None, close_reason=None):
        self.on_close({'s':'error','message':'Order transport closed.'})
        super()._FyersOrderSocket__on_close(ws,close_code,close_reason)


class QuietLogger:
    # SDK exception text may contain tokens; report only generic stream state.
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class OrderNotifications:
    def __init__(self, runner, wake, log_path):
        self.runner, self.wake, self.log_path = runner, wake, log_path
        self.socket = None
        self.connected = False
        self.received_at = None
        self.error = None
        self.lock = threading.Lock()
        self.generation = 0
        self.created_at = None
        self.next_recovery_at = 0
        self.recoveries = 0
        self.token_hash = None

    def start(self):
        with self.lock:
            if self.socket:
                return
            configure_websocket_ca_bundle()
            token=load_config().get('FYERS_ACCESS_TOKEN','')
            self.token_hash=hashlib.sha256(token.encode()).digest()
            self.generation+=1
            generation=self.generation
            self.created_at=time.time()
            subscribed_transport=None
            def changed(message):
                with self.lock:
                    if generation!=self.generation:return
                    self.received_at = time.time()
                    if isinstance(message,dict) and message.get('s')=='error':
                        self.connected=False
                        self.error='FYERS rejected an order-stream response; broker reconciliation active.'
                self.runner.wake.set()
                self.wake.set()
            def opened():
                nonlocal subscribed_transport
                with self.lock:
                    if generation!=self.generation:return
                    socket=self.socket
                    transport = getattr(socket,'_FyersOrderSocket__ws_object',None)
                    if not transport or not getattr(getattr(transport,'sock',None),'connected',False):
                        self.connected = False
                        self.error = 'FYERS order connection is not yet established.'
                        self.wake.set()
                        return
                    if transport is subscribed_transport:return
                    subscribed_transport=transport
                    self.connected, self.error = True, None
                socket.subscribe(data_type='OnOrders,OnTrades,OnPositions')
                self.runner.wake.set()
                self.wake.set()
            def closed(*args):
                with self.lock:
                    if generation!=self.generation:return
                    self.connected = False
                self.wake.set()
            def failed(*args):
                with self.lock:
                    if generation!=self.generation:return
                    self.connected = False
                    self.error = 'FYERS order stream unavailable; reconciliation remains active.'
                self.wake.set()
            self.socket = IndependentOrderSocket(access_token=token,write_to_file=False,
                log_path=str(self.log_path),on_orders=changed,on_trades=changed,on_positions=changed,
                on_general=changed,on_connect=opened,on_close=closed,on_error=failed,reconnect=True)
            self.socket.order_logger = QuietLogger()
            socket=self.socket
            def connect():
                try:socket.connect()
                except Exception:failed()
            threading.Thread(target=connect,daemon=True,name='renko-order-notifications').start()

    def recover(self):
        now=time.time()
        with self.lock:
            if self.socket is None or now<self.next_recovery_at:return
            try:changed=hashlib.sha256(load_config().get('FYERS_ACCESS_TOKEN','').encode()).digest()!=self.token_hash
            except Exception:return
            transport=getattr(self.socket,'_FyersOrderSocket__ws_object',None)
            healthy=self.connected and bool(getattr(getattr(transport,'sock',None),'connected',False))
            if not healthy:self.connected=False
            # Quiet accounts legitimately have no order messages for hours.
            if not changed and (healthy or now-(self.created_at or now)<45):return
            old=self.socket
            self.generation+=1
            self.socket=None;self.connected=False;self.received_at=None
            self.error='Order notification transport recovering; broker reconciliation active.'
            self.recoveries+=1
            self.next_recovery_at=now+min(60*2**min(self.recoveries-1,3),300)
        # SDK close joins its threads without bounds; never block reconciliation
        # or a browser heartbeat on that cleanup.
        def close():
            try:old.close_connection()
            except Exception:pass
        threading.Thread(target=close,daemon=True,name='renko-old-order-close').start()
        self.start()

    def snapshot(self):
        self.recover()
        with self.lock:
            return {'connected':self.connected,'received_at':self.received_at,'error':self.error,'recoveries':self.recoveries,
                'basis':'FYERS order/trade websocket notifications; owned fills verified by broker reconciliation.'}


class BrowserSnapshotCache:
    """Read snapshots off the chart heartbeat; never acquire the strategy lock there."""
    def __init__(self, snapshot, clock=time.time):
        self.snapshot,self.clock=snapshot,clock
        self.lock=threading.Lock()
        self.value=None;self.captured_at=None;self.requested_at=None;self.busy=False

    def refresh(self):
        try:
            value=self.snapshot()
            with self.lock:
                self.value=value;self.captured_at=self.clock()
        except Exception:
            pass  # Retain last evidence with its real timestamp, not a fresh-looking replacement.
        finally:
            with self.lock:self.busy=False

    def read(self, now):
        with self.lock:
            if not self.busy and (self.requested_at is None or now-self.requested_at>=2):
                self.busy=True;self.requested_at=now
                self.worker=threading.Thread(target=self.refresh,daemon=True,name='renko-browser-snapshot')
                self.worker.start()
            fresh=self.captured_at is not None and 0<=now-self.captured_at<=5
            value=deepcopy(self.value)
            if value is not None and not fresh:
                value['pnl']={**(value.get('pnl') or {}),'available':False,'unrealized':None}
            return dict(runner=value,runner_snapshot_at=self.captured_at,runner_snapshot_fresh=fresh)


_snapshot_caches_lock=threading.Lock()


def recover_chart_candles(broker, config, now):
    """Backfill chart OHLC off the SSE heartbeat, using only its broker.

    One bounded history request at a time, at most once per ten seconds.
    Recovery seeds chart observations only; it cannot assess or replay entries.
    """
    with _snapshot_caches_lock:
        recovery=vars(broker).setdefault('_browser_candle_recovery',dict(busy=False,requested_at=None))
        if recovery['busy'] or (recovery['requested_at'] is not None and now-recovery['requested_at']<10):
            return
        recovery.update(busy=True,requested_at=now)
    def refresh():
        try:
            rows=broker.candles(deepcopy(config))
            broker.observe(config,rows)
        except (ValueError, RuntimeError):
            pass  # The frame retains its real failure until a verified bar exists.
        finally:
            with _snapshot_caches_lock:recovery['busy']=False
    worker=threading.Thread(target=refresh,daemon=True,name='renko-chart-candle-recovery')
    recovery['worker']=worker
    worker.start()


def browser_snapshot(runner, now):
    with _snapshot_caches_lock:
        cache=vars(runner).get('_browser_snapshot_cache')
        if cache is None:
            cache=BrowserSnapshotCache(runner.snapshot)
            runner._browser_snapshot_cache=cache
    return cache.read(now)


def browser_managers(runners, now):
    rows=[]
    for key,runner in runners.items():
        snapshot=browser_snapshot(runner,now)
        if snapshot['runner'] is None:return {}  # Keep the prior UI until every manager has evidence.
        rows.append(dict(id=key,**snapshot['runner'],snapshot_fresh=snapshot['runner_snapshot_fresh']))
    return dict(adopted_managers=rows)


def browser_frame(runner, broker, config, order_stream, now=None):
    now = time.time() if now is None else now
    forming, error = None, None
    try:
        forming = broker.forming(config, [], now)
    except (ValueError, RuntimeError) as exc:
        error = str(exc)
    tick_price, tick_at, tick_error = None, None, None
    try:
        tick_price, tick_at = broker.live_price(config, now)
    except (ValueError, RuntimeError) as exc:
        tick_error = str(exc)
    if forming is None:
        if tick_at is not None:
            recover_chart_candles(broker,config,now)
        error='Chart forming OHLC unavailable; '+('broker history recovery pending.' if tick_at is not None else 'waiting for fresh broker ticks.')
        if not config.get('intrabar_entries',False):
            error+=' Completed-candle runner decisions use separate confirmed history.'
    return {**browser_snapshot(runner,now),'forming':forming,'market':{'connected':broker.connected,
            'fresh':forming is not None,'error':error,'tick_exchange_at':tick_at,'tick_price':tick_price,'tick_fresh':tick_at is not None,'tick_error':tick_error},'orders':order_stream.snapshot(),
            'server_at':now,'bar_seconds':broker.frame_seconds and next((n for s,n in broker.frame_seconds if s==config['underlying']),None)}
