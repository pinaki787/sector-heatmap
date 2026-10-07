"""Read-only browser stream and isolated FYERS order notifications.

Order notifications wake reconciliation; REST remains authoritative for owned fills.
No notification can submit an order or manufacture a journal fill.
"""
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
    return {'runner':runner.snapshot(),'forming':forming,'market':{'connected':broker.connected,
            'fresh':forming is not None,'error':error,'tick_exchange_at':tick_at,'tick_fresh':tick_at is not None,'tick_error':tick_error},'orders':order_stream.snapshot(),
            'server_at':now,'bar_seconds':broker.frame_seconds and next((n for s,n in broker.frame_seconds if s==config['underlying']),None)}
