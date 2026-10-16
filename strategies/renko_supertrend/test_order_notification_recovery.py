import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from .stream import IndependentOrderSocket,OrderNotifications


class Socket:
    instances=[]
    def __init__(self,**kwargs):
        self.callbacks=kwargs;self._FyersOrderSocket__ws_object=None
        self.subscribe=Mock();self.closed=threading.Event()
        self.instances.append(self)
    def connect(self):self.callbacks['on_connect']()
    def close_connection(self):self.closed.set()
    def open(self):
        self._FyersOrderSocket__ws_object=SimpleNamespace(sock=SimpleNamespace(connected=True))
        self.callbacks['on_connect']()


class OrderRecoveryTests(unittest.TestCase):
    def setUp(self):
        Socket.instances=[];self.now=100;self.token='account:old'
        for target,value in [('IndependentOrderSocket',Socket),('configure_websocket_ca_bundle',lambda:None),('load_config',lambda:{'FYERS_ACCESS_TOKEN':self.token}),('time.time',lambda:self.now)]:
            p=patch('strategies.renko_supertrend.stream.'+target,value);p.start();self.addCleanup(p.stop)
        self.runner=Mock();self.wake=threading.Event()
        self.notifications=OrderNotifications(self.runner,self.wake,tempfile.gettempdir())
        self.notifications.start();self.socket=Socket.instances[-1]

    def test_delayed_open_subscribes_once_per_actual_transport(self):
        self.socket.open();self.socket.callbacks['on_connect']()
        self.assertTrue(self.notifications.snapshot()['connected'])
        self.socket.subscribe.assert_called_once_with(data_type='OnOrders,OnTrades,OnPositions')
        self.socket.open();self.assertEqual(self.socket.subscribe.call_count,2)

    def test_exhausted_connection_replaced_with_backoff_and_old_callbacks_ignored(self):
        self.now=146;self.notifications.snapshot()
        replacement=Socket.instances[-1]
        self.assertIsNot(replacement,self.socket)
        self.assertTrue(self.socket.closed.wait(1))
        self.socket.callbacks['on_connect']();self.socket.callbacks['on_orders']({})
        self.assertFalse(self.notifications.connected);self.assertIsNone(self.notifications.received_at)
        replacement.open();self.socket.callbacks['on_error']('secret')
        self.assertTrue(self.notifications.connected);self.assertIsNone(self.notifications.error)
        replacement.callbacks['on_close']();self.now=180;self.notifications.snapshot()
        self.assertEqual(len(Socket.instances),2)
        self.now=207;self.notifications.snapshot();self.assertEqual(len(Socket.instances),3)
        self.runner.adapter.place.assert_not_called()

    def test_healthy_quiet_socket_is_not_recycled_but_new_token_is(self):
        self.socket.open();self.now=1000;self.notifications.snapshot()
        self.assertEqual(len(Socket.instances),1)
        self.token='account:new';self.notifications.snapshot()
        self.assertEqual(Socket.instances[-1].callbacks['access_token'],'account:new')
        self.assertEqual(len(Socket.instances),2)

    def test_transport_loss_detected_even_if_sdk_omits_close_callback(self):
        self.socket.open();self.socket._FyersOrderSocket__ws_object.sock.connected=False
        self.now=146;self.notifications.snapshot()
        self.assertEqual(len(Socket.instances),2)

    def test_actual_sdk_open_hook_notifies_after_transport_initialization(self):
        sock=IndependentOrderSocket.__new__(IndependentOrderSocket)
        sock.on_open=Mock()
        with patch('fyers_apiv3.FyersWebsocket.order_ws.FyersOrderSocket._FyersOrderSocket__on_open') as opened:
            sock._FyersOrderSocket__on_open('transport')
        opened.assert_called_once_with('transport');sock.on_open.assert_called_once_with()
