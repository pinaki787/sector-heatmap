import unittest
from unittest.mock import Mock, patch
from .stream import browser_frame, IndependentOrderSocket
from .runner import Broker


class StreamTests(unittest.TestCase):
    def test_forming_feed_and_owned_state_are_separate(self):
        runner=Mock(); runner.snapshot.return_value={'running':False,'position':None,'pending':None}
        broker=Mock();broker.live_price.return_value=(10,130);broker.connected=True;broker.frame_seconds={('NSE:TEST',60):True}
        broker.forming.return_value={'timestamp':120,'close':10,'is_forming':True}
        orders=Mock();orders.snapshot.return_value={'connected':True}
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
