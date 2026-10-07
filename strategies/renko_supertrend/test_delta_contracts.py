"""Broker-boundary tests; never connect to a broker or place an order."""
import unittest
from .delta_contracts import configuration, option_contract, position, order_intent, owned_order

NOW = 1791300000


def product():
    return dict(id=123, symbol='C-BTC-90000-071026', contract_type='call_options',
                state='live', trading_status='operational', contract_value='0.001',
                tick_size='0.1', notional_type='vanilla', is_quanto=False,
                underlying='BTC', contract_unit_currency='BTC',
                quoting_currency='USD', settlement_currency='USD',
                settlement_time='2026-10-08T12:00:00Z', strike_price='90000')


class DeltaBoundaryTests(unittest.TestCase):
    def test_contract_units_are_not_fyers_lot_multiplier(self):
        meta = option_contract(product(), NOW)
        self.assertEqual(meta['lot_size'], 1)
        self.assertEqual(meta['quantity_multiplier'], .001)
        self.assertEqual(meta['quote_currency'], 'USD')
        self.assertEqual(meta['product_id'], 123)

    def test_unverified_metadata_is_rejected(self):
        for key, value in [('contract_value', 0), ('contract_value', True),
                           ('tick_size', 'NaN'), ('is_quanto', True),
                           ('notional_type', 'inverse'), ('settlement_currency', 'INR'),
                           ('contract_unit_currency', 'USD'), ('id', 1.5),
                           ('settlement_time', '2026-10-08T12:00:00'),
                           ('settlement_time', '2026-01-01T00:00:00Z'),
                           ('trading_status', 'disrupted')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                option_contract({**product(), key: value}, NOW)

    def test_position_identity_and_long_options_only(self):
        row = dict(product_id=123, product_symbol=product()['symbol'], size=4, entry_price='22.5')
        self.assertEqual(position(row, product(), NOW)['netQty'], 4)
        for key, value in [('size', -4), ('size', 1.5), ('entry_price', None),
                           ('product_id', 124), ('product_symbol', 'BTCUSD')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                position({**row, key: value}, product(), NOW)
        with self.assertRaises(ValueError):
            position(row, {**product(), 'contract_type': 'perpetual_futures'}, NOW)

    def test_marketability_tick_rounding_and_reduce_only(self):
        quote = dict(bid=22.34, ask=22.46, exchange_at=NOW-1, received_at=NOW)
        buy = order_intent(product()['symbol'], 4, 1, quote, product(), NOW)
        sell = order_intent(product()['symbol'], 4, -1, quote, product(), NOW)
        self.assertEqual(buy['limit_price'], '22.6')
        self.assertEqual(sell['limit_price'], '22.2')
        self.assertFalse(buy['reduce_only'])
        self.assertTrue(sell['reduce_only'])
        self.assertEqual(sell['time_in_force'], 'ioc')

    def test_stale_crossed_future_or_missing_quotes_never_build_order(self):
        quote = dict(bid=22, ask=23, exchange_at=NOW-1, received_at=NOW)
        for change in [dict(exchange_at=NOW-16), dict(received_at=NOW+1),
                       dict(bid=24), dict(ask=None), dict(exchange_at=True)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                order_intent(product()['symbol'], 4, 1, {**quote, **change}, product(), NOW)

    def owned(self):
        return dict(account_identity='account-a', request_id='renko-request-1',
                    client_order_id='spdi_test', order_id=456, symbol=product()['symbol'],
                    request=dict(product_id=123, size=4, side='sell', reduce_only=True,
                                 order_type='limit_order', time_in_force='ioc', limit_price='22.2'),
                    status='cancelled', filled_contracts=2, average_fill_price='22.3', commission='0.02')

    def test_cancelled_partial_fill_remains_real_exposure_evidence(self):
        row = owned_order(self.owned(), 'account-a')
        self.assertEqual((row['status'], row['filledQty'], row['remainingQuantity']), (1, 2, 2))
        self.assertEqual(row['tradedPrice'], 22.3)
        self.assertEqual(row['commission'], '0.02')

    def test_unknown_ack_is_nonterminal_and_never_a_fill(self):
        owned = {**self.owned(), 'status': 'UNKNOWN', 'filled_contracts': 0,
                 'order_id': None, 'average_fill_price': None}
        row = owned_order(owned, 'account-a')
        self.assertEqual(row['status'], 6)
        self.assertIsNone(row['tradedPrice'])
        self.assertEqual(row['id'], 'spdi_test')

    def test_mismatched_or_inconsistent_fill_evidence_is_rejected(self):
        changes = [dict(account_identity='other'), dict(filled_contracts=5),
                   dict(filled_contracts=-1), dict(status='closed'),
                   dict(average_fill_price=None), dict(status='unexpected')]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                owned_order({**self.owned(), **change}, 'account-a')
        owned = self.owned(); owned['request']['reduce_only'] = False
        with self.assertRaises(ValueError):
            owned_order(owned, 'account-a')

    def test_policy_requires_explicit_delta_values(self):
        payload = dict(broker='DELTA_INDIA', underlying='BTCUSD',
                       price_source='PERPETUAL_LAST_TRADE', order_terms='MARKETABLE_LIMIT_IOC',
                       session_deadline='23:30', carry_policy='DAILY_SQUARE_OFF',
                       strategy='RENKO_SUPERTREND_V1', exit_policy='OPPOSITE_CONFIRMED_SIGNAL',
                       mode='PAPER', lots=1, max_trades=2)
        config = configuration(payload)
        self.assertEqual(config['underlying'], 'BTCUSD')
        self.assertEqual(config['session_segment'], 'DELTA_INDIA')
        for change in [dict(broker='FYERS'), dict(price_source='INDEX'),
                       dict(timeframe='2 minutes'), dict(session_deadline=None),
                       dict(session_deadline='24:00'), dict(carry_policy='CARRY'),
                       dict(order_terms='MARKET')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                configuration({**payload, **change})


if __name__ == '__main__':
    unittest.main()
