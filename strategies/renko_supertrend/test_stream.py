import unittest
from unittest.mock import Mock, patch
from .stream import browser_frame, IndependentOrderSocket, BrowserSnapshotCache
from .runner import Broker


class StreamTests(unittest.TestCase):
    def test_forming_feed_and_owned_state_are_separate(self):
        runner=Mock(); runner.snapshot.return_value={'running':False,'position':None,'pending':None}
        broker=Mock();broker.live_price.return_value=(10,130);broker.connected=True;broker.frame_seconds={('NSE:TEST',60):True}
        broker.forming.return_value={'timestamp':120,'close':10,'is_forming':True}
        orders=Mock();orders.snapshot.return_value={'connected':True}
        with patch('strategies.renko_supertrend.stream.browser_snapshot',return_value=dict(runner=runner.snapshot.return_value,runner_snapshot_fresh=True)):
            result=browser_frame(runner,broker,{'underlying':'NSE:TEST','timeframe':'1 minute'},orders,130)
        self.assertTrue(result['market']['fresh']);self.assertFalse(result['runner']['running'])
        runner.activate.assert_not_called();broker.submit.assert_not_called()
        broker.forming.side_effect=ValueError('stale')
        result=browser_frame(runner,broker,{'underlying':'NSE:TEST'},orders,150)
        self.assertIsNone(result['forming']);self.assertFalse(result['market']['fresh'])

    def test_order_sockets_are_independent_without_connecting(self):
        self.assertIsNot(IndependentOrderSocket.__new__(IndependentOrderSocket),IndependentOrderSocket.__new__(IndependentOrderSocket))

    def test_executable_bid_age_must_be_fresh_for_option_valuation(self):
        with patch('strategies.renko_supertrend.runner.BaseBroker.quote',return_value={'bid':10,'ask':11,'received_at':100,'exchange_at':100}),patch('strategies.renko_supertrend.runner.time.time',return_value=110):
            self.assertEqual(Broker.quote(Broker.__new__(Broker),'TEST')['bid'],10)
        with patch('strategies.renko_supertrend.runner.BaseBroker.quote',return_value={'bid':10,'ask':11,'received_at':100,'exchange_at':90}),patch('strategies.renko_supertrend.runner.time.time',return_value=110):
            with self.assertRaises(ValueError):Broker.quote(Broker.__new__(Broker),'TEST')

    def test_slow_snapshot_never_blocks_heartbeat_and_old_evidence_stays_stale(self):
        import threading,time
        entered=threading.Event();release=threading.Event();completed=threading.Event();now=[100]
        def slow():
            entered.set();release.wait(2);completed.set();return dict(updated_at=90,pnl=dict(available=True,unrealized=5))
        cache=BrowserSnapshotCache(slow,lambda:now[0])
        start=time.monotonic();first=cache.read(100)
        self.assertLess(time.monotonic()-start,.1);self.assertIsNone(first['runner']);self.assertFalse(first['runner_snapshot_fresh'])
        self.assertTrue(entered.wait(.5));self.assertIsNone(cache.read(101)['runner']);release.set();self.assertTrue(completed.wait(.5))
        cache.worker.join(.5)
        self.assertFalse(cache.worker.is_alive())
        value=cache.read(101)
        self.assertIsNotNone(value['runner']);self.assertEqual(value['runner']['updated_at'],90)
        self.assertTrue(value['runner_snapshot_fresh'])
        cache.busy=True  # Hold the next refresh; cached evidence must age normally.
        stale=cache.read(106)
        self.assertFalse(stale['runner_snapshot_fresh']);self.assertEqual(stale['runner_snapshot_at'],100)
        self.assertFalse(stale['runner']['pnl']['available']);self.assertIsNone(stale['runner']['pnl']['unrealized'])
