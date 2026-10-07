import unittest
from unittest.mock import patch
from . import test_runner as fixtures
from .runner import Broker

class FirstOptionQuoteTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    start=fixtures.RenkoLifecycleTests.start
    def test_first_subscription_retries_same_fresh_signal_once_quote_arrives(self):
        original=self.b.quote;calls=[]
        def quote(symbol):
            calls.append(symbol)
            if len(calls)==1:raise ValueError('FYERS stream has no tick for '+symbol+'; subscription requested.')
            return original(symbol)
        self.b.quote=quote
        self.start();eligible=self.r.state['eligible_since']
        self.r.step()
        self.assertEqual(self.r.state['status'],'WAITING_FOR_OPTION_QUOTE')
        self.assertFalse(self.r.state.get('pending'));self.assertFalse(self.r.state.get('order_history'))
        self.assertFalse(self.r.state['seen'])
        self.assertEqual(self.r.state['eligible_since'],eligible)
        self.b.now+=1;self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(len(self.r.state['order_history']),1)
        self.assertEqual(self.r.snapshot()['execution_signals'][0]['status'],'FILLED')
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1)
        self.assertEqual(self.b.sent,[])
    def test_expired_quote_wait_never_replays(self):
        def quote(symbol):raise ValueError('FYERS stream has no tick for '+symbol+'; subscription requested.')
        self.b.quote=quote;self.start();self.r.step()
        self.b.now+=61;self.r.step()
        self.assertFalse(self.r.state.get('position'));self.assertFalse(self.r.state.get('order_history'))
        self.assertEqual(self.r.snapshot()['execution_signals'][0]['status'],'EXPIRED')
    def test_unrelated_validation_error_remains_blocked(self):
        self.b.quote=lambda symbol:(_ for _ in ()).throw(ValueError('Option bid/ask missing or crossed.'))
        self.start()
        with self.assertRaises(ValueError):self.r.step()
        self.assertEqual(self.r.snapshot()['execution_signals'][0]['status'],'BLOCKED')
        self.assertFalse(self.r.state.get('pending'))

class OptionWarmupTests(unittest.TestCase):
    def test_warms_both_directions_without_order_and_throttles(self):
        broker=object.__new__(Broker);resolved=[];subscriptions=[]
        def resolve(config,direction):
            resolved.append(direction)
            return {'symbol':direction}
        def tick(symbol):
            subscriptions.append(symbol)
            raise ValueError('FYERS stream has no tick for '+symbol)
        broker.resolve=resolve;broker.tick=tick
        broker.place=lambda order:self.fail('Warmup must never place an order')
        with patch('strategies.renko_supertrend.runner.time.time',return_value=100):
            broker.warm_options({});broker.warm_options({})
        self.assertEqual(resolved,['BULLISH','BEARISH'])
        self.assertEqual(subscriptions,resolved)
