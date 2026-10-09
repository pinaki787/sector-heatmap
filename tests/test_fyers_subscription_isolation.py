"""A stalled SDK subscription must not hold the strategy/status caller."""
import threading
import time
import unittest
from strategies.ema_crossover.broker import FyersBroker


class SubscriptionIsolation(unittest.TestCase):
    def test_stalled_subscription_is_single_flight_and_tick_fails_closed(self):
        entered, release = threading.Event(), threading.Event()
        class Socket:
            calls = 0
            def subscribe(self, **kwargs):
                self.calls += 1
                entered.set()
                release.wait(3)
        broker = FyersBroker('.', None, None)
        broker.socket = Socket()
        broker.connected = True
        try:
            started = time.monotonic()
            with self.assertRaisesRegex(ValueError, 'no tick'):
                broker.tick('MCX:TESTCE')
            self.assertLess(time.monotonic() - started, .5)
            self.assertTrue(entered.wait(1))
            for _ in range(20):
                broker.subscribe_all()
            self.assertEqual(broker.socket.calls, 1)
            self.assertTrue(broker.lock.acquire(timeout=.5))
            broker.lock.release()
        finally:
            release.set()
        self.assertTrue(broker.subscription_lock.acquire(timeout=1))
        broker.subscription_lock.release()

    def test_exception_releases_worker_for_retry(self):
        class Socket:
            def subscribe(self, **kwargs):
                raise RuntimeError('secret SDK detail')
        broker = FyersBroker('.', None, None)
        broker.socket, broker.connected = Socket(), True
        broker.subscribe_all()
        self.assertTrue(broker.subscription_lock.acquire(timeout=1))
        broker.subscription_lock.release()
        self.assertEqual(broker.stream_error, 'FYERS subscription failed; awaiting automatic retry.')


if __name__ == '__main__':
    unittest.main()
