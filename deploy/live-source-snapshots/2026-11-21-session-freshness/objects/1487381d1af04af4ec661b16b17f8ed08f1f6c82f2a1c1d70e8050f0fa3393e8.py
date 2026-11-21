"""Read-only Delta public-trade capture for seconds and transaction-count charts."""

from collections import deque
import heapq
import json
import logging
from math import isfinite
from threading import Lock, Thread
import time


LOGGER = logging.getLogger(__name__)


def trade_bars(trades, interval, coverage_start, now):
    width = int(interval[:-1])
    tick = interval.endswith("T")
    groups = {}
    for index, (stamp, price, size) in enumerate(trades):
        if tick:
            key = index // width
        else:
            key = stamp // (width * 1_000_000) * width
            if key * 1_000_000 < coverage_start:
                continue
        if key in groups:
            row, count = groups[key]
            row[2] = max(row[2], price)
            row[3] = min(row[3], price)
            row[4] = price
            row[5] += size
            groups[key] = row, count + 1
        else:
            opening = stamp / 1_000_000 if tick else key
            groups[key] = [opening, price, price, price, price, size], 1
    completed, forming = [], []
    for key, (row, count) in groups.items():
        if (count == width if tick else key + width <= now):
            completed.append(row)
        else:
            forming.append(row)
    return completed[-750:], forming


class DeltaChartTrades:
    MAX_TRADES = 80000
    # Rolling eviction preserves the alignment of every supported tick size.
    EVICT = 1000
    REORDER_SECONDS = 3

    def __init__(self, symbol="BTCUSD"):
        self.symbol = symbol
        self.lock = Lock()
        self.trades = deque()
        self.pending = []
        self.closed_segments = deque()
        self.closed_trades = 0
        self.discontinuities = 0
        self.sequence = 0
        self.last_stamp = None
        self.connected = False
        self.started = None
        self.revision = 0
        self.thread = Thread(target=self.run, name="delta-chart-public-trades", daemon=True)

    def run(self):
        import websocket

        def opened(socket):
            self.reset(int(time.time() * 1_000_000))
            socket.send(json.dumps({"type": "subscribe", "payload": {
                "channels": [{"name": "trades", "symbols": [self.symbol]}]
            }}))

        def message(socket, raw):
            try:
                packet = json.loads(raw)
            except ValueError:
                return
            self.ingest(packet)

        while True:
            socket = websocket.WebSocketApp(
                "wss://public-socket.india.delta.exchange", on_open=opened, on_message=message,
            )
            try:
                socket.run_forever(ping_interval=20, ping_timeout=10)
            except (OSError, websocket.WebSocketException) as error:
                LOGGER.warning("Delta chart trade socket failed: %s", type(error).__name__)
            finally:
                self.disconnect(time.time())
            time.sleep(2)

    def archive(self, through):
        if not self.trades:
            return
        segment = tuple(self.trades)
        self.closed_segments.append((segment, self.started, through))
        self.closed_trades += len(segment)
        while self.closed_trades > self.MAX_TRADES or len(self.closed_segments) > 32:
            self.closed_trades -= len(self.closed_segments.popleft()[0])
        self.discontinuities += 1

    def disconnect(self, now):
        through = now - self.REORDER_SECONDS
        with self.lock:
            self.drain(int(through * 1_000_000))
            self.archive(through)
            self.trades.clear()
            self.pending.clear()
            self.last_stamp = None
            self.connected = False
            self.revision += 1

    def reset(self, stamp):
        with self.lock:
            self.started = stamp
            self.connected = False
            self.trades.clear()
            self.pending.clear()
            self.last_stamp = None
            self.revision += 1

    def ingest(self, packet):
        if not isinstance(packet, dict):
            return
        with self.lock:
            if packet.get("type") == "subscriptions":
                if {"name": "trades", "symbols": [self.symbol]} in packet.get("channels", []):
                    self.connected = True
                return
            if not self.connected or packet.get("type") != "trades" or packet.get("sy") != self.symbol:
                return
            try:
                stamp, price, size = int(packet["t"]), float(packet["p"]), float(packet["s"])
            except (KeyError, TypeError, ValueError, OverflowError):
                return
            now = time.time()
            if not self.started <= stamp <= int((now + 5) * 1_000_000) or not all(isfinite(v) and v > 0 for v in (price, size)):
                return
            self.sequence += 1
            heapq.heappush(self.pending, (stamp, self.sequence, price, size))
            self.drain(int((now - self.REORDER_SECONDS) * 1_000_000))

    def drain(self, watermark):
        while self.pending and self.pending[0][0] <= watermark:
            stamp, _, price, size = heapq.heappop(self.pending)
            if self.last_stamp is not None and stamp < self.last_stamp:
                # A late trade can invalidate the last bucket. Retain only bars
                # preceding the affected trade, and begin a new segment.
                cutoff = stamp / 1_000_000
                while self.trades and self.trades[-1][0] >= stamp:
                    self.trades.pop()
                self.archive(cutoff)
                self.trades.clear()
                self.started = stamp
                self.last_stamp = None
                self.revision += 1
            unique = max(stamp, self.trades[-1][0] + 1) if self.trades else stamp
            self.trades.append((unique, price, size))
            self.last_stamp = stamp
            if len(self.trades) > self.MAX_TRADES:
                for _ in range(self.EVICT):
                    self.trades.popleft()
                self.started = self.trades[0][0] + 1
            self.revision += 1

    def snapshot(self, interval, now=None):
        now = time.time() if now is None else now
        watermark = now - self.REORDER_SECONDS
        with self.lock:
            self.drain(int(watermark * 1_000_000))
            trades, started = list(self.trades), self.started
            connected, revision = self.connected, self.revision
            archived = tuple(self.closed_segments)
            discontinuities = self.discontinuities
        # Drop the live time bucket once it closes, even if no new trade arrives.
        clock = int(watermark) // int(interval[:-1]) if interval.endswith("S") else None
        completed = []
        for segment, opening, cutoff in archived:
            closed, _ = trade_bars(segment, interval, opening, cutoff)
            completed.extend(closed)
        rows, forming = trade_bars(trades, interval, started, watermark) if trades else ([], [])
        completed.extend(rows)
        return {"provider": "Delta India", "symbol": self.symbol, "connected": connected,
                "revision": [revision, clock], "latest_tick": trades[-1][0] / 1_000_000 if trades else None,
                "completed": completed[-750:], "rows": forming, "discontinuities": discontinuities}
