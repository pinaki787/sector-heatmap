import threading
import unittest
from .delta_execution import Execution
from .test_delta_contracts import product, NOW


class FakeDelta:
    def __init__(self):
        self.lock = threading.RLock()
        self.runner = {}; self.live = {}; self.calls = []
        self.pages = [dict(result=[], meta={})]
        self.size = 0
    def clock(self): return NOW
    def verify_auth(self): self.calls.append('authenticate')
    def _identity(self): return 'account-a'
    def product(self, symbol): return product()
    def _position(self, product_id): return self.size
    def _private(self, method, path, params=None):
        self.calls.append((method, path, params))
        return self.pages.pop(0)
    def submit(self, payload, runner=False):
        self.calls.append(('submit', payload, runner))
        return payload
    def _owned(self, payload): return dict(strategy='OTHER_STRATEGY')
    def cancel(self, payload): raise AssertionError('Must not cancel unrelated order')


class DeltaExecutionTests(unittest.TestCase):
    def test_complete_external_order_inventory_uses_pagination(self):
        delta = FakeDelta()
        delta.pages = [dict(result=[dict(id=1)], meta=dict(after='next')),
                       dict(result=[dict(id=2)], meta={})]
        self.assertEqual([r['id'] for r in Execution(delta).active_orders()], [1, 2])
        self.assertEqual(delta.calls[-1][2]['after'], 'next')

    def test_ambiguous_pagination_blocks(self):
        delta = FakeDelta()
        delta.pages = [dict(result=[dict(id=1)], meta=dict(after='next')),
                       dict(result=[dict(id=1)], meta={})]
        with self.assertRaises(ValueError): Execution(delta).active_orders()

    def submit(self, delta, side=1):
        return Execution(delta).submit(product()['symbol'], 4, side,
            dict(bid=22, ask=23, exchange_at=NOW, received_at=NOW),
            'ECpersisted-intent', 'BTCUSD', 'EMA_ENTRY')

    def test_native_durable_submit_receives_renko_terms_without_rsi_activation(self):
        delta = FakeDelta(); result = self.submit(delta)
        self.assertEqual(result['request_id'], 'ECpersisted-intent')
        self.assertEqual(result['strategy'], 'RENKO_SUPERTREND_V1')
        self.assertEqual(delta.calls[-1][2], True)
        self.assertNotIn('_managed_submit', result)

    def test_external_position_or_order_blocks_entry(self):
        for position_size, orders in [(1, []), (0, [dict(id=7, product_id=123)])]:
            delta = FakeDelta(); delta.size = position_size
            delta.pages = [dict(result=orders, meta={})]
            with self.assertRaises(ValueError): self.submit(delta)
            self.assertFalse(any(isinstance(call, tuple) and call[0] == 'submit' for call in delta.calls))

    def test_owned_existing_delta_strategy_blocks(self):
        delta = FakeDelta(); delta.runner['running'] = True
        with self.assertRaises(ValueError): self.submit(delta)

    def test_exit_is_reduce_only(self):
        delta = FakeDelta(); result = self.submit(delta, -1)
        self.assertTrue(result['reduce_only'])
        self.assertEqual(result['side'], 'sell')

    def test_cannot_cancel_unrelated_strategy(self):
        with self.assertRaises(ValueError): Execution(FakeDelta()).cancel('external')

    def test_account_change_fails_closed(self):
        execution = Execution(FakeDelta()); execution.account_identity = 'previous-account'
        with self.assertRaises(ValueError): execution.authenticate()


if __name__ == '__main__': unittest.main()
