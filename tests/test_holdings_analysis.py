from datetime import datetime, timedelta
from math import sin
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sector_heatmap.holdings_analysis import FyersHoldings, DeltaHoldings, HoldingsAnalysis, review, review_linear, indicators, IST
from sector_heatmap.market_calendar import is_trading_day
from sector_heatmap.section_permissions import allowed

NOW = datetime(2026, 10, 14, 14, 0, tzinfo=IST).timestamp()
SESSION = '2026-10-13'


def candles(down=False, extended=False):
    days = []; date = datetime(2025, 11, 1, tzinfo=IST)
    while date.date().isoformat() <= SESSION:
        if is_trading_day(date.date()): days.append(date)
        date += timedelta(days=1)
    result = []
    for i, date in enumerate(days):
        close = 200 + (-.2 if down else .2) * i + sin(i * .65) * 1.5
        if extended and i > len(days) - 8: close += 5 * (i - len(days) + 8)
        result.append({'timestamp': date.timestamp(), 'open': close, 'high': close + 2, 'low': close - 2, 'close': close})
    return result


def holding(history, cost=200):
    return {'id': '0', 'symbol': 'NSE:TEST-EQ', 'kind': 'DELIVERY_EQUITY', 'quantity': 10,
            'average_price': cost, 'price': history[-1]['close'], 'quote_timestamp': NOW - 10, 'currency': 'INR'}


class RecommendationTests(unittest.TestCase):
    def test_aligned_winner_trails_and_new_holding_holds(self):
        data = candles()
        result = review(holding(data), data, SESSION, NOW)
        self.assertEqual(result['action'], 'TRAIL')
        self.assertLess(result['candidate_stop'], result['price'])
        self.assertGreater(result['candidate_stop'], result['average_price'])
        new = holding(data, data[-1]['close'] - .1)
        self.assertEqual(review(new, data, SESSION, NOW)['action'], 'HOLD')

    def test_breakdown_exits_and_extended_profit_books(self):
        down = candles(down=True)
        self.assertEqual(review(holding(down), down, SESSION, NOW)['action'], 'EXIT')
        extended = candles(extended=True)
        self.assertEqual(review(holding(extended), extended, SESSION, NOW)['action'], 'BOOK_PROFIT')

    def test_stale_quotes_history_malformed_candles_and_gap_do_not_advise(self):
        data = candles(); row = holding(data)
        for modified, history in [({**row, 'quote_timestamp': NOW - 180}, data), (row, data[:-1]),
                                  (row, data + [data[-1]]), ({**row, 'price': 1}, data),
                                  ({**row, 'average_price': 0}, data), (row, data[:50])]:
            with self.subTest(modified=modified):
                self.assertEqual(review(modified, history, SESSION, NOW)['action'], 'REVIEW_NEEDED')

    def test_current_forming_daily_candle_does_not_change_decision(self):
        data = candles(); row = holding(data)
        current = {'timestamp': datetime(2026, 10, 14, tzinfo=IST).timestamp(), 'open': 10, 'high': 10, 'low': 10, 'close': 10}
        self.assertEqual(review(row, data + [current], SESSION, NOW)['action'], review(row, data, SESSION, NOW)['action'])

    def test_closed_market_accepts_only_last_session_quote(self):
        data = candles(); row = holding(data)
        after = datetime(2026, 10, 14, 8, 0, tzinfo=IST).timestamp()
        row['quote_timestamp'] = datetime(2026, 10, 13, 15, 29, tzinfo=IST).timestamp()
        self.assertEqual(review(row, data, SESSION, after)['action'], 'TRAIL')
        row['quote_timestamp'] -= 86400
        self.assertEqual(review(row, data, SESSION, after)['action'], 'REVIEW_NEEDED')

    def test_derivatives_never_use_share_quantity_for_pnl(self):
        row = {'kind': 'DERIVATIVE_POSITION', 'quantity': 10, 'average_price': 100, 'price': 200}
        self.assertEqual(review_linear(row, [], NOW)['action'], 'REVIEW_NEEDED')
        self.assertIsNone(review_linear(row, [], NOW)['gross_pnl'])

    def test_linear_future_short_uses_units_and_direction(self):
        last_midnight = int(NOW // 86400) * 86400 - 86400
        data = [{'timestamp': last_midnight - (219-i)*86400, 'open': 300-i*.3+sin(i*.65),
                 'high': 302-i*.3+sin(i*.65), 'low': 298-i*.3+sin(i*.65), 'close': 300-i*.3+sin(i*.65)} for i in range(220)]
        row = {'kind': 'LINEAR_FUTURE', 'quantity': -5, 'average_price': 300, 'price': data[-1]['close'],
               'contract_value': .001, 'quote_timestamp': NOW - 2}
        result = review_linear(row, data, NOW)
        self.assertEqual(result['action'], 'TRAIL')
        self.assertAlmostEqual(result['gross_pnl'], -5*.001*(row['price']-300), places=6)
        self.assertGreater(result['candidate_stop'], row['price'])
        self.assertLess(result['candidate_stop'], 300)
        self.assertEqual(review_linear({**row, 'expiry_timestamp': NOW + 3600}, data, NOW)['action'], 'REVIEW_NEEDED')


class AdapterTests(unittest.TestCase):
    def test_holdings_preserve_t1_demat_and_remaining_quantity(self):
        client = SimpleNamespace(header='private-token')
        payload = {'s':'ok', 'holdings':[{'symbol':'NSE:TEST-EQ','holdingType':'HLD','remainingQuantity':4,'quantity':10,'costPrice':100},
                                      {'symbol':'NSE:TEST-EQ','holdingType':'T1','remainingQuantity':2,'costPrice':105},
                                      {'symbol':'NSE:SOLD-EQ','remainingQuantity':0,'quantity':10}]}
        with patch('sector_heatmap.holdings_analysis.account_read', return_value=payload):
            rows = FyersHoldings(client).inventory()
        self.assertEqual([r['quantity'] for r in rows], [4,2])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_broker_account_errors_are_not_an_empty_portfolio(self):
        with patch('sector_heatmap.holdings_analysis.account_read', return_value={'s':'error'}):
            with self.assertRaises(ValueError): FyersHoldings(SimpleNamespace(header='token')).inventory()

    def test_delta_reads_positions_without_mutating_lifecycle_account(self):
        calls = []
        delta = SimpleNamespace(_identity=lambda:'private', _private=lambda *args:(calls.append(args) or {'result':[]}))
        self.assertEqual(DeltaHoldings(delta).inventory(), [])
        self.assertEqual(calls, [('GET','/v2/positions/margined')])

    def test_feature_permission(self):
        self.assertTrue(allowed({'features':['broker']}, '/api/holdings-analysis'))
        self.assertTrue(allowed({'features':['holdings']}, '/api/holdings-analysis'))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.service = HoldingsAnalysis(clock=lambda:self.now)
        self.service.pace = lambda:None
        history = candles()
        self.adapter = SimpleNamespace(broker='FYERS', identity='account-one',
            inventory=lambda:[{**holding(history), 'id':str(i)} for i in range(7)], enrich=lambda rows:rows, candles=lambda row,now:history)

    def test_all_rows_pagination_and_duplicate_batch_are_idempotent(self):
        first = self.service.batch(self.adapter)
        self.assertEqual((first['total'], first['analysed'], first['next_offset']), (7,5,5))
        second = self.service.batch(self.adapter, first['capture_id'], 5)
        self.assertEqual((second['analysed'], second['next_offset']), (7,None))
        self.assertEqual(sum(second['summary'].values()),7)
        self.assertEqual(self.service.batch(self.adapter, first['capture_id'],5)['analysed'],7)
        self.assertTrue(second['portfolio']['complete'])

    def test_snapshot_cannot_cross_account_or_broker_and_expires(self):
        first = self.service.batch(self.adapter)
        self.adapter.identity = 'account-two'
        with self.assertRaises(ValueError): self.service.batch(self.adapter,first['capture_id'],5)
        self.adapter.identity = 'account-one'; self.adapter.broker = 'DELTA_INDIA'
        with self.assertRaises(ValueError): self.service.batch(self.adapter,first['capture_id'],5)
        self.adapter.broker = 'FYERS'; self.now += 601
        with self.assertRaises(ValueError): self.service.batch(self.adapter,first['capture_id'],5)

    def test_history_failure_remains_visible_and_does_not_abort_other_holdings(self):
        self.adapter.candles = lambda *args: (_ for _ in ()).throw(ValueError('secret broker message'))
        first = self.service.batch(self.adapter)
        self.assertEqual(first['analysed'],5)
        self.assertEqual(first['summary']['REVIEW_NEEDED'],5)
        self.assertNotIn('secret', str(first))

    def test_inventory_only_avoids_quote_and_history_calls(self):
        self.adapter.enrich = lambda rows: self.fail('Inventory must not fetch quotes')
        first = self.service.batch(self.adapter, inventory_only=True)
        self.assertEqual((first['total'],first['analysed'],first['next_offset']), (7,0,0))
        self.assertEqual(first['rows'],[])

    def test_repeat_inventory_is_throttled(self):
        self.service.batch(self.adapter)
        with self.assertRaises(ValueError):self.service.batch(self.adapter)


class EndpointTests(unittest.TestCase):
    def route(self, broker, bound=None):
        # Compile the real read-only route without initializing trading services.
        import ast
        from pathlib import Path
        from urllib.parse import parse_qs, urlparse
        tree = ast.parse(Path('sector_heatmap/web.py').read_text())
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run_server')
        handler = next(node for node in run.body if isinstance(node, ast.ClassDef) and node.name == 'Handler')
        dispatch = next(node for node in handler.body if isinstance(node, ast.FunctionDef) and node.name in ('diagnostic_get_dispatch','do_GET'))
        branch = next(node for node in dispatch.body if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and any(isinstance(n, ast.Constant) and n.value == '/api/holdings-analysis' for n in ast.walk(node.test)))
        function = ast.parse('def endpoint(self, path):\n    pass').body[0]
        function.body = [branch]
        created = []
        adapter = SimpleNamespace(broker=broker, identity='private-account', inventory=lambda:[], enrich=lambda rows:rows, candles=lambda *args:[])
        def factory(value):
            created.append(value)
            return adapter
        namespace = {'parse_qs':parse_qs, 'urlparse':urlparse, 'workspace_guard':bound is not None,
                     'FyersHoldings':factory, 'DeltaHoldings':factory, 'ema_readonly_client':lambda:'private-client',
                     'delta_india':'private-delta', 'holdings_analysis':HoldingsAnalysis(clock=lambda:NOW)}
        namespace['holdings_analysis'].pace = lambda:None
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), '<route-test>', 'exec'), namespace)
        output = []
        request = SimpleNamespace(path='/api/holdings-analysis?broker='+broker,
                                  workspace_identity=({'admin':False}, {'broker':bound}),
                                  send_json=lambda status, body:output.append((status,body)))
        namespace['endpoint'](request, '/api/holdings-analysis')
        return output[0], created

    def test_wrong_workspace_broker_denied_before_adapter_is_created(self):
        result, created = self.route('DELTA_INDIA','FYERS')
        self.assertEqual(result[0],403)
        self.assertEqual(created,[])

    def test_valid_empty_account_is_explicit_and_unknown_broker_rejected(self):
        result, created = self.route('FYERS','FYERS')
        self.assertEqual(result[0],200)
        self.assertEqual(result[1]['total'],0)
        self.assertEqual(created,['private-client'])
        result, created = self.route('UNKNOWN')
        self.assertEqual(result[0],409)
        self.assertEqual(created,[])


if __name__ == '__main__': unittest.main()
