"""Read-only Delta public-trade capture for seconds and transaction-count charts."""

from collections import deque
import heapq
import json
import logging
from math import isfinite
from threading import Event, Lock, Thread
import time


LOGGER = logging.getLogger(__name__)


def trade_bars(trades, interval, coverage_start, now, *, delta_width=None):
    width = delta_width if delta_width is not None else int(interval[:-1])
    tick = delta_width is None and interval.endswith("T")
    groups = {}
    for index, (stamp, price, size, chart_stamp, side) in enumerate(trades):
        if tick:
            key = index // width
        else:
            second = stamp // 1_000_000
            elapsed = second % 86400 if delta_width is not None else second
            key = second - elapsed % width
            if key * 1_000_000 < coverage_start:
                continue
        if delta_width is not None:
            row, count = groups.setdefault(key, ([key, 0, 0, 0, 0], 0))
            if side == 0:
                row[1:] = [None] * 4
            elif row[4] is not None:
                row[4] += side * size
                row[2] = max(row[2], row[4])
                row[3] = min(row[3], row[4])
            groups[key] = row, count + 1
        elif key in groups:
            row, count = groups[key]
            row[2] = max(row[2], price)
            row[3] = min(row[3], price)
            row[4] = price
            row[5] += size
            groups[key] = row, count + 1
        else:
            opening = chart_stamp / 1_000_000 if tick else key
            groups[key] = [opening, price, price, price, price, size], 1
    completed, forming = [], []
    for key, (row, count) in groups.items():
        end = min(key + width, key - key % 86400 + 86400) if delta_width is not None else key + width
        if (count == width if tick else end <= now):
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
        self.latest_received = None
        self.last_stamp = None
        self.connected = False
        self.started = None
        self.revision = 0
        self.stopped = Event()
        self.socket = None
        self.thread = Thread(target=self.run, name="delta-chart-public-trades", daemon=True)

    def run(self):
        import websocket

        def opened(socket):
            if self.stopped.is_set():
                socket.close()
                return
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

        while not self.stopped.is_set():
            socket = websocket.WebSocketApp(
                "wss://public-socket.india.delta.exchange", on_open=opened, on_message=message,
            )
            self.socket = socket
            if self.stopped.is_set():
                break
            try:
                socket.run_forever(ping_interval=20, ping_timeout=10)
            except (OSError, websocket.WebSocketException) as error:
                LOGGER.warning("Delta chart trade socket failed: %s", type(error).__name__)
            finally:
                self.disconnect(time.time())
            self.stopped.wait(2)

    def stop(self):
        self.stopped.set()
        app = self.socket
        if app is not None:
            app.keep_running = False
            socket = app.sock
            if socket is not None:
                socket.abort()

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
            self.latest_received = None
            self.connected = False
            self.revision += 1

    def reset(self, stamp):
        with self.lock:
            self.started = stamp
            self.connected = False
            self.trades.clear()
            self.pending.clear()
            self.last_stamp = None
            self.latest_received = None
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
            self.latest_received = max(stamp, self.latest_received or stamp)
            self.sequence += 1
            # The buyer is the aggressor only when its role is taker.
            role = packet.get("r")
            side = 1 if role == "t" else -1 if role == "m" else 0
            heapq.heappush(self.pending, (stamp, self.sequence, price, size, side))
            self.drain(int((now - self.REORDER_SECONDS) * 1_000_000))

    def drain(self, watermark):
        while self.pending and self.pending[0][0] <= watermark:
            stamp, _, price, size, side = heapq.heappop(self.pending)
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
            # Keep real execution time for seconds buckets and segment cutoffs.
            # Tick bars need distinct chart coordinates even for equal execution times.
            previous = self.trades[-1] if self.trades else (
                self.closed_segments[-1][0][-1] if self.closed_segments else None
            )
            chart_stamp = max(stamp, previous[3] + 1) if previous else stamp
            self.trades.append((stamp, price, size, chart_stamp, side))
            self.last_stamp = stamp
            if len(self.trades) > self.MAX_TRADES:
                for _ in range(self.EVICT):
                    self.trades.popleft()
                self.started = self.trades[0][0] + 1
            self.revision += 1

    def snapshot(self, interval, now=None, *, delta_width=None):
        now = time.time() if now is None else now
        watermark = now - self.REORDER_SECONDS
        with self.lock:
            self.drain(int(watermark * 1_000_000))
            trades, started = list(self.trades), self.started
            connected, revision = self.connected, self.revision
            archived = tuple(self.closed_segments)
            discontinuities = self.discontinuities
            latest_received = self.latest_received
        if delta_width is not None:
            segments = (*archived, (trades, started, watermark)) if trades else archived
            delta_segments = []
            for segment, opening, cutoff in segments:
                delta, forming = trade_bars(segment, interval, opening, cutoff, delta_width=delta_width)
                active = segment is trades and connected
                if active:
                    delta.extend(forming)
                if delta:
                    delta_segments.append({"from": delta[0][0], "through": int(cutoff),
                                           "active": active, "rows": delta})
            return {"provider": "Delta India", "symbol": self.symbol, "connected": connected,
                    "revision": [revision, int(watermark)],
                    "trade_delta": {"method": "aggressor_side", "segments": delta_segments}}
        # Drop the live time bucket once it closes, even if no new trade arrives.
        clock = int(watermark) // int(interval[:-1]) if interval.endswith("S") else None
        completed = []
        for segment, opening, cutoff in archived:
            closed, _ = trade_bars(segment, interval, opening, cutoff)
            completed.extend(closed)
        rows, forming = trade_bars(trades, interval, started, watermark) if trades else ([], [])
        completed.extend(rows)
        result = {"provider": "Delta India", "symbol": self.symbol, "connected": connected,
                  "revision": [revision, clock],
                  "latest_tick": latest_received / 1_000_000 if latest_received is not None else None,
                  "completed": completed[-750:], "rows": forming, "discontinuities": discontinuities}
        return result
