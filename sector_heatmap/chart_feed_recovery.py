"""Bounded recovery for read-only chart sockets; never changes runner state."""
import hashlib
import threading
import time


def safe_stream_error(message):
    """Keep error category without echoing arbitrary broker text or tokens."""
    message = message if isinstance(message, dict) else {}
    code = message.get('code')
    category = {'cn':'authentication', 'sub':'subscription'}.get(message.get('type'), 'transport-or-unknown')
    return dict(category=category, code=code if isinstance(code, (int, float)) else None)


class ChartFeedRecoveryMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chart_recovery_lock = threading.Lock()
        self._chart_token = None
        self._chart_created = 0.
        self._chart_last_valid = 0.
        self._chart_checked = 0.
        self._chart_next_recovery = 0.
        self._chart_recoveries = 0
        self._chart_failures = 0
        self._chart_recovery_reason = None

    def _chart_token_hash(self):
        from sector_heatmap.config import load_config
        value = load_config().get('FYERS_ACCESS_TOKEN', '')
        return hashlib.sha256(value.encode()).digest()

    def start(self):
        if self.socket is None:
            self._chart_token = self._chart_token_hash()
            self._chart_created = time.time()
            self._chart_last_valid = 0.
        return super().start()

    def _recover_chart(self, symbol, now):
        with self.lock:
            item = self.ticks.get(symbol)
            socket = self.socket
        if item and now-item[1] <= 15:
            stamp = item[0].get('exch_feed_time', item[0].get('last_traded_time'))
            try:
                if abs(now-float(stamp)) <= 60:
                    self._chart_failures = 0
                    self._chart_recovery_reason = None
                    self._chart_last_valid = now
            except (TypeError, ValueError):
                pass
        if now-self._chart_checked < 10:
            return
        self._chart_checked = now
        try:
            changed = self._chart_token_hash() != self._chart_token
        except Exception:
            self._chart_recovery_reason = 'Credential refresh unavailable'
            return
        if not changed and now < self._chart_next_recovery:
            return
        stalled = now-(self._chart_last_valid or self._chart_created) >= 45
        if not changed and not stalled:
            return
        if not self._chart_recovery_lock.acquire(blocking=False):
            return
        self._chart_failures += 1
        self._chart_next_recovery = now + min(60 * 2**min(self._chart_failures-1, 3), 300)
        self._chart_recovery_reason = 'Credentials refreshed' if changed else 'No fresh chart ticks'

        def replace():
            try:
                with self.lock:
                    if self.socket is not socket:
                        return
                    # Invalidate old callbacks before closing their transport.
                    self.stream_generation += 1
                    self.socket = None
                    self.connected = False
                    self.ticks = {}
                    self.last_subscribe = {}
                    self.stream_error = 'Chart feed reconnecting; waiting for a fresh tick.'
                if socket:
                    # SDK close joins its ping/message threads without a timeout.
                    # Do not let that block creation of the replacement chart socket.
                    def close_old():
                        try:
                            socket.close_connection()
                        except Exception:
                            pass
                    cleanup = threading.Thread(target=close_old, daemon=True, name='chart-feed-close')
                    cleanup.start()
                    cleanup.join(timeout=2)
                self.start()
                self._chart_recoveries += 1
            except Exception:
                with self.lock:
                    self.stream_error = 'Chart connection setup failed; bounded recovery pending.'
            finally:
                self._chart_recovery_lock.release()
        threading.Thread(target=replace, daemon=True, name='chart-feed-recovery').start()

    def tick(self, symbol):
        self._recover_chart(symbol, time.time())
        return super().tick(symbol)

    def subscribe_all(self):
        # One rejected symbol must not prevent healthy chart subscriptions.
        if not self.subscription_lock.acquire(blocking=False):
            return
        def subscribe():
            try:
                with self.lock:
                    socket, generation = self.socket, self.stream_generation
                    symbols = sorted(self.symbols)
                    if not socket or not self.connected:
                        return
                for symbol in symbols:
                    with self.lock:
                        if socket is not self.socket or generation != self.stream_generation:
                            return
                        self.last_subscribe[symbol] = time.time()
                    try:
                        socket.subscribe(symbols=[symbol], data_type='SymbolUpdate')
                    except Exception:
                        with self.lock:
                            if generation == self.stream_generation:
                                self.stream_error = 'Chart subscription failed; bounded recovery pending.'
            finally:
                self.subscription_lock.release()
        threading.Thread(target=subscribe, daemon=True, name='chart-feed-subscriptions').start()

    def stream_status(self):
        return dict(super().stream_status(), chart_recovery=dict(
            revision='chart-transport-recovery-v1', attempts=self._chart_recoveries,
            reason=self._chart_recovery_reason))
