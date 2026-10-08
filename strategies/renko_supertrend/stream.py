"""Read-only browser stream and isolated FYERS order notifications.

Order notifications wake reconciliation; REST remains authoritative for owned fills.
No notification can submit an order or manufacture a journal fill.
"""
from copy import deepcopy
import json
import threading
import time
from fyers_apiv3.FyersWebsocket import order_ws
from sector_heatmap.config import load_config
from sector_heatmap.market_data import configure_websocket_ca_bundle


class IndependentOrderSocket(order_ws.FyersOrderSocket):
    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)


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

    def start(self):
        with self.lock:
            if self.socket:
                return
            configure_websocket_ca_bundle()
            def changed(message):
                self.received_at = time.time()
                self.runner.wake.set()
                self.wake.set()
            def opened():
                transport = getattr(self.socket,'_FyersOrderSocket__ws_object',None)
                if not transport or not getattr(getattr(transport,'sock',None),'connected',False):
                    self.connected = False
                    self.error = 'FYERS order connection is not yet established.'
                    self.wake.set()
                    return
                self.connected, self.error = True, None
                self.socket.subscribe(data_type='OnOrders,OnTrades,OnPositions')
                self.runner.wake.set()
                self.wake.set()
            def closed(*args):
                self.connected = False
                self.wake.set()
            def failed(*args):
                self.connected = False
                self.error = 'FYERS order stream unavailable; reconciliation remains active.'
                self.wake.set()
            self.socket = IndependentOrderSocket(access_token=load_config().get('FYERS_ACCESS_TOKEN',''),write_to_file=False,
                log_path=str(self.log_path),on_orders=changed,on_trades=changed,on_positions=changed,
                on_general=changed,on_connect=opened,on_close=closed,on_error=failed,reconnect=True)
            self.socket.order_logger = QuietLogger()
            threading.Thread(target=self.socket.connect,daemon=True,name='renko-order-notifications').start()

    def snapshot(self):
        return {'connected':self.connected,'received_at':self.received_at,'error':self.error,
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
    tick_at, tick_error = None, None
    try:
        _, tick_at = broker.live_price(config, now)
    except (ValueError, RuntimeError) as exc:
        tick_error = str(exc)
    return {**browser_snapshot(runner,now),'forming':forming,'market':{'connected':broker.connected,
            'fresh':forming is not None,'error':error,'tick_exchange_at':tick_at,'tick_fresh':tick_at is not None,'tick_error':tick_error},'orders':order_stream.snapshot(),
            'server_at':now,'bar_seconds':broker.frame_seconds and next((n for s,n in broker.frame_seconds if s==config['underlying']),None)}
