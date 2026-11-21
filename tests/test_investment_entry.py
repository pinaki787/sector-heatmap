from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import json

from sector_heatmap.investment_entry import DhanEntry, session_slot
from sector_heatmap.market_calendar import IST
from sector_heatmap.persistent_jobs import JobCancelled


def instant(hour, minute, day=16):
    return datetime(2026, 11, day, hour, minute, tzinfo=IST)


class Broker:
    client_id = 'fixture'

    def __init__(self):
        self.orders = []
        self.holdings = []
        self.positions = []
        self.forever = []
        self.writes = []
        self.fail_send = False

    def request(self, method, path, payload=None):
        if method == 'POST' and path == '/orders':
            self.writes.append(payload)
            if self.fail_send:
                raise TimeoutError()
            row = dict(payload, orderId=str(len(self.writes)), orderStatus='PENDING', filledQty=0)
            self.orders.append(row)
            return row
        if path.startswith('/orders/external/'):
            return next(r for r in self.orders if r['correlationId'] == path.split('/')[-1])
        responses = {
            '/profile': {'dhanClientId': self.client_id},
            '/ip/getIP': {'primaryIP': '192.0.2.1'},
            '/fundlimit': {'dhanClientId': self.client_id, 'availableBalance': 100000},
            '/margincalculator': {'totalMargin': 500, 'availableBalance': 100000},
            '/orders': self.orders, '/positions': self.positions, '/holdings': self.holdings,
            '/forever/orders': self.forever,
        }
        return responses[path]


class InvestmentEntryTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.broker = Broker()
        contract = dict(exchange_segment='NSE_EQ', security_id='123', lot_size=1, tick_size=.05)
        account = dict(id='fixture-account', broker='DHAN', label='Fixture', live_enabled=True)
        execution = SimpleNamespace(
            folder=Path(temporary.name), account=account, lock=RLock(),
            execution_allowed=lambda: True, _client=lambda: self.broker,
            _submission_lock=nullcontext, egress=lambda: '192.0.2.1',
            master=SimpleNamespace(resolve=lambda *_: contract),
        )
        self.entry = DhanEntry(execution, lambda: account)
        self.plan = dict(symbol='NSE:TEST-EQ', security_id='123', limit_price='95.05', quantity=10)
        self.context = SimpleNamespace(checkpoint=lambda: None, store=SimpleNamespace(guard=RLock()))

    def check(self, now):
        with patch('sector_heatmap.investment_entry.datetime', wraps=datetime) as patched:
            patched.now.return_value = now
            return self.entry.check(self.plan, 'test-monitor', self.context, now, session_slot(now))

    def test_schedule_skips_nights_and_closed_days(self):
        self.assertEqual(session_slot(instant(9, 15)), 'OPEN')
        self.assertEqual(session_slot(instant(16, 15)), 'AMO')
        self.assertIsNone(session_slot(instant(9, 25)))
        self.assertIsNone(session_slot(instant(15, 59)))
        self.assertIsNone(session_slot(instant(9, 15, 15)))  # Sunday
        self.assertIsNone(session_slot(instant(9, 15, 24)))  # NSE holiday

    def test_regular_order_pending_then_expired_partial_replaced_once_by_amo(self):
        self.assertEqual(self.check(instant(9, 15)), ('BROKER_ACKNOWLEDGED', 0))
        self.assertFalse(self.broker.writes[0]['afterMarketOrder'])
        self.assertEqual(self.check(instant(16, 15)), ('WORKING_ORDER', 0))
        self.assertEqual(len(self.broker.writes), 1)
        self.broker.orders[0].update(orderStatus='EXPIRED', filledQty=4)
        self.broker.positions.append(dict(securityId='123', exchangeSegment='NSE_EQ', netQty=4, productType='CNC'))
        self.assertEqual(self.check(instant(16, 15)), ('BROKER_ACKNOWLEDGED', 4))
        replacement = self.broker.writes[1]
        self.assertEqual(replacement['quantity'], 6)
        self.assertTrue(replacement['afterMarketOrder'])
        self.assertEqual(replacement['amoTime'], 'OPEN')
        self.broker.orders[1].update(orderStatus='TRADED', filledQty=6)
        self.broker.positions[0]['netQty'] = 10
        self.assertEqual(self.check(instant(9, 15, 17)), ('COMPLETE', 10))
        self.assertEqual(len(self.broker.writes), 2)

    def test_existing_holding_blocks_entry(self):
        self.broker.holdings.append(dict(securityId='123', totalQty=1))
        self.assertEqual(self.check(instant(9, 15)), ('EXISTING_POSITION', 0))
        self.assertFalse(self.broker.writes)

    def test_existing_forever_buy_blocks_a_second_entry(self):
        self.broker.forever.append(dict(securityId='123', exchangeSegment='NSE_EQ',
                                        transactionType='BUY', orderStatus='CONFIRM'))
        self.assertEqual(self.check(instant(9, 15)), ('WORKING_ORDER', 0))
        self.assertFalse(self.broker.writes)

    def test_uncertain_send_is_never_retried(self):
        self.broker.fail_send = True
        with self.assertRaisesRegex(ValueError, 'uncertain'):
            self.check(instant(9, 15))
        path = next(self.entry.journal.glob('*.json'))
        self.assertEqual(json.loads(path.read_text())['status'], 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'reconciliation'):
            self.check(instant(16, 15))
        self.assertEqual(len(self.broker.writes), 1)

    def test_stop_before_committing_the_order(self):
        checkpoints = iter((None, JobCancelled()))
        def checkpoint():
            error = next(checkpoints)
            if error:
                raise error
        self.context.checkpoint = checkpoint
        with self.assertRaises(JobCancelled):
            self.check(instant(9, 15))
        self.assertFalse(self.broker.writes)
        self.assertFalse(list(self.entry.journal.glob('*.json')))

    def test_fresh_plan_uses_broker_tick_and_exact_level(self):
        row = dict(symbol='NSE:TEST-EQ', eligible=True,
                   daily_pullback=dict(as_of='2026-11-13', price_56=95.079))
        plan = self.entry.plan(row, '56', 10, instant(9, 15))
        self.assertEqual(plan['limit_price'], '95.05')
        self.assertEqual(plan['notional'], '950.50')
        with self.assertRaisesRegex(ValueError, 'fresh'):
            self.entry.plan(row, '56', 10, instant(16, 15))

