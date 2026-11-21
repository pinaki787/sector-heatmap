import hashlib
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from sector_heatmap.chart_workspace import DhanChartStream


class Socket:
    def __init__(self,url,**hooks):self.hooks=hooks;self.sent=[]
    def send(self,value):self.sent.append(value)
    def run_forever(self,**kwargs):pass
    def close(self):self.hooks["on_close"]()


class Thread:
    def __init__(self,*args,**kwargs):pass
    def start(self):pass


class DhanChartTickTests(unittest.TestCase):
    def setUp(self):
        self.now=100.5
        with patch("websocket.WebSocketApp",Socket),patch("threading.Thread",Thread):
            self.stream=DhanChartStream(SimpleNamespace(client_id="client",headers={"access-token":"test-token"}),
                symbol="NSE_FNO:123",account_id="account",clock=lambda:self.now)
        self.addCleanup(self.stream.stop)
        self.stream.socket.hooks["on_open"](self.stream.socket)

    def tick(self,*,segment=2,security=123,price=25,stamp=100,code=2):
        self.stream.ingest(self.stream.socket,struct.pack("<BHbIfI",code,16,segment,security,price,stamp))

    def test_exact_account_symbol_native_identity_and_raw_socket_timing(self):
        self.tick()
        tick=self.stream.execution_tick("NSE_FNO:123")
        self.assertEqual(tick["account_id"],"account")
        self.assertEqual(tick["symbol"],"NSE_FNO:123")
        self.assertEqual(tick["native_account_hash"],hashlib.sha256(b"client").hexdigest())
        self.assertEqual(tick["source"],"BROKER_WEBSOCKET")
        self.assertEqual((tick["provider_at"],tick["received_at"]),(100,100.5))
        self.assertEqual(tick["sequence"],1)
        self.assertEqual(len(tick["stream_id"]),32)
        tick["price"]="999"
        self.assertEqual(self.stream.execution_tick("NSE_FNO:123")["price"],"25.0")

    def test_same_second_ticks_have_distinct_receipt_sequence(self):
        self.tick();first=self.stream.execution_tick("NSE_FNO:123")
        self.tick(price=25.05);second=self.stream.execution_tick("NSE_FNO:123")
        self.assertGreater(second["sequence"],first["sequence"])
        self.assertEqual(second["provider_at"],first["provider_at"])

    def test_disconnect_reconnect_and_stop_clear_execution_evidence(self):
        self.tick()
        self.stream.socket.hooks["on_close"]()
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))
        self.tick()
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))
        self.stream.socket.hooks["on_open"](self.stream.socket)
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))
        self.tick()
        self.assertEqual(self.stream.execution_tick("NSE_FNO:123")["connection_revision"],2)
        self.stream.stop()
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))

    def test_bad_packet_future_price_and_unsubscribed_security_are_not_execution_ticks(self):
        for values in (dict(price=float("nan")),dict(price=0),dict(stamp=105),
                       dict(security=456),dict(segment=1),dict(code=4)):
            self.tick(**values)
            self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))
        self.stream.ingest(self.stream.socket,b"not a packet")
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))

    def test_stale_and_out_of_order_packets_cannot_replace_fresh_execution_evidence(self):
        self.tick()
        self.tick(stamp=99,price=30)
        self.assertEqual(self.stream.execution_tick("NSE_FNO:123")["price"],"25.0")
        self.now=103
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))
        self.tick(stamp=100,price=30)
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))
        self.tick(stamp=103,price=26)
        self.assertEqual(self.stream.execution_tick("NSE_FNO:123")["price"],"26.0")

    def test_unbound_read_only_chart_stream_cannot_supply_execution_tick(self):
        self.stream.account_id=None;self.tick()
        self.assertIsNone(self.stream.execution_tick("NSE_FNO:123"))


if __name__=="__main__":unittest.main()
