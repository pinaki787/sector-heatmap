import threading
import unittest
from types import SimpleNamespace
from .delta_broker import Broker


class SubmissionBoundaryTests(unittest.TestCase):
    def broker(self, action):
        broker = Broker.__new__(Broker)
        broker.delta = SimpleNamespace(lock=threading.RLock(), live={'orders': {}})
        broker._place = action
        return broker

    def test_local_preflight_failure_is_definitive_rejection(self):
        def action(order):
            raise ValueError('Outstanding unrelated owned order')
        broker = self.broker(action)
        self.assertEqual(broker.place({'orderTag': 'owned'})['code'], 400)
        self.assertEqual(broker.delta.live['orders'], {})

    def test_persisted_unknown_submission_is_never_cleared(self):
        def action(order):
            broker.delta.live['orders']['owned'] = {'status': 'UNKNOWN'}
            raise ConnectionError('lost response')
        broker = self.broker(action)
        with self.assertRaises(ConnectionError):
            broker.place({'orderTag': 'owned'})
        self.assertEqual(broker.delta.live['orders']['owned']['status'], 'UNKNOWN')

    def test_existing_intent_blocks_definitive_rejection(self):
        def action(order):
            raise ValueError('identity mismatch')
        broker = self.broker(action)
        broker.delta.live['orders']['owned'] = {'status': 'SUBMITTING'}
        with self.assertRaises(ValueError):
            broker.place({'orderTag': 'owned'})

    def test_success_response_preserved(self):
        broker = self.broker(lambda order: {'s': 'ok', 'id': '123'})
        self.assertEqual(broker.place({'orderTag': 'owned'}), {'s': 'ok', 'id': '123'})
