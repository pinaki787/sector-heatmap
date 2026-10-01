import unittest
from unittest.mock import MagicMock, patch

from strategies.ema_crossover.broker import FyersBroker


class FundsTests(unittest.TestCase):
    def check(self, available=149143.27, required=4020, title_only=False, symbol='MCX:CRUDEOILM26OCT8900CE', qty=1):
        broker = FyersBroker('/tmp', None, None)
        broker.validate_order = lambda order: None
        broker.contract = lambda symbol: dict(symbol=symbol, quantity_multiplier=10 if symbol.startswith('MCX:') else 1)
        broker.quote = lambda symbol: dict(bid=401.9, ask=402)
        broker.positions = lambda: []
        broker.orders = lambda: []
        row = dict(title='Available Balance', equityAmount=available, commodityAmount=0)
        if not title_only:
            row['id'] = 10
        client = MagicMock()
        client.funds.return_value = dict(s='ok', fund_limit=[
            dict(id=1, title='Total Balance', equityAmount=999999, commodityAmount=0), row])
        response = MagicMock()
        response.json.return_value = dict(s='ok', data=dict(margin_total=required))
        with patch('strategies.ema_crossover.broker._current_client', return_value=client), \
             patch('strategies.ema_crossover.broker.load_config', return_value={}), \
             patch('strategies.ema_crossover.broker.requests.post', return_value=response) as margin:
            try:
                broker.preflight(dict(symbol=symbol, qty=qty), {})
            finally:
                self.margin_calls = margin.call_count

    def test_mcx_uses_shared_balance_and_still_checks_margin(self):
        self.check()
        self.assertEqual(self.margin_calls, 1)

    def test_available_balance_title_fallback(self):
        self.check(title_only=True)

    def test_nifty_shared_funds_and_reserve(self):
        self.check(symbol='NSE:NIFTY26O0622450CE', qty=65, available=26391.3)
        with self.assertRaisesRegex(ValueError, 'premium plus 1% reserve'):
            self.check(symbol='NSE:NIFTY26O0622450CE', qty=65, available=26391.29)

    def test_insufficient_shared_balance_preserves_reserve(self):
        with self.assertRaisesRegex(ValueError, 'premium plus 1% reserve'):
            self.check(available=4050)
        self.assertEqual(self.margin_calls, 0)

    def test_broker_margin_exceeding_shared_balance_blocks(self):
        with self.assertRaisesRegex(ValueError, 'margin unavailable or exceeds'):
            self.check(required=150000)


if __name__ == '__main__':
    unittest.main()
