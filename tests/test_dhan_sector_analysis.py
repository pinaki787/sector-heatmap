"""Dhan sector candles, analysis and HTTP routing with deterministic broker data."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sector_heatmap.dhan_execution import DhanExecutionService, IST
from sector_heatmap.dhan_sector_analysis import (
    DhanCandleHistoryProvider, DhanSectorAnalysisService, INDEX_NAMES,
)
from sector_heatmap.sectors import BENCHMARK_SYMBOL, SECTOR_DEFINITIONS
from sector_heatmap.section_permissions import allowed


class Client:
    client_id = '123'

    def __init__(self):
        self.owner = '123'
        self.plan = 'Active'
        self.calls = []
        self.quote_failure = False

    def request(self, method, path, payload=None):
        self.calls.append((method, path, deepcopy(payload)))
        if path == '/profile':
            return dict(dhanClientId=self.owner, dataPlan=self.plan)
        if path == '/marketfeed/ohlc':
            if self.quote_failure:
                raise RuntimeError('Dhan quote service unavailable')
            return {'data': {'NSE_EQ': {str(s): {'last_price': 110, 'ohlc': {'close': 100}}
                                      for s in payload['NSE_EQ']}}}
        if path in ('/charts/historical', '/charts/intraday'):
            cursor = datetime.fromisoformat(payload['fromDate']).replace(tzinfo=IST)
            end = datetime.fromisoformat(payload['toDate']).replace(tzinfo=IST)
            out = {k: [] for k in ('timestamp', 'open', 'high', 'low', 'close', 'volume')}
            daily = path == '/charts/historical'
            while cursor < end:
                if cursor.weekday() < 5 and (daily or 9*60+15 <= cursor.hour*60+cursor.minute < 15*60+30):
                    price = 100 + cursor.timestamp()/86400/100
                    values = (int(cursor.timestamp()), price, price+2, price-2, price+1, 1000)
                    for key, value in zip(out, values):
                        out[key].append(value)
                cursor += timedelta(days=1) if daily else timedelta(minutes=int(payload['interval']))
            return out
        raise AssertionError('Unexpected broker operation: ' + path)


class DhanSectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.now = datetime(2026, 10, 13, 10, 7, tzinfo=IST)
        self.client = Client()
        self.rows = [dict(SEM_EXM_EXCH_ID='NSE', SEM_SEGMENT='I', SEM_TRADING_SYMBOL=names[-1],
                          SEM_CUSTOM_SYMBOL='', SEM_SMST_SECURITY_ID=str(i), SEM_INSTRUMENT_NAME='INDEX')
                     for i, names in enumerate(INDEX_NAMES.values(), 1)]
        tickers = {item.ticker for sector in SECTOR_DEFINITIONS for item in sector.constituents}
        self.rows += [dict(SEM_EXM_EXCH_ID='NSE', SEM_SEGMENT='E', SEM_SERIES='EQ',
                           SEM_TRADING_SYMBOL=ticker, SEM_SMST_SECURITY_ID=str(100+i))
                      for i, ticker in enumerate(sorted(tickers))]
        account = dict(id='a'*32, broker='DHAN', label='Dhan', account_ref='123', live_enabled=False)
        (self.folder/'credentials.json').write_text(json.dumps(dict(DHAN_CLIENT_ID='123', DHAN_ACCESS_TOKEN='fake')))
        self.execution = DhanExecutionService(account, self.folder, client_factory=lambda _: self.client,
                                             master=SimpleNamespace(load=lambda now: self.rows))
        self.provider = DhanCandleHistoryProvider(self.execution, now=lambda: self.now)
        self.pause = patch('sector_heatmap.dhan_sector_analysis.time.sleep')
        self.pause.start()
        self.addCleanup(self.pause.stop)

    def test_index_and_cash_mapping_rejects_ambiguity_and_missing_symbols(self):
        self.provider.prepare()
        for symbol in INDEX_NAMES:
            self.assertEqual(self.provider.resolve(symbol)['exchangeSegment'], 'IDX_I')
        ticker = SECTOR_DEFINITIONS[0].constituents[0].ticker
        self.assertEqual(self.provider.resolve('NSE:'+ticker+'-EQ')['exchangeSegment'], 'NSE_EQ')
        self.rows.append(dict(self.rows[0]))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.provider.resolve(BENCHMARK_SYMBOL)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            self.provider.resolve('NSE:MISSING-EQ')

    def test_profile_identity_and_data_subscription_are_required(self):
        self.client.owner = 'someone-else'
        with self.assertRaises(PermissionError):
            self.provider.prepare()
        self.client.owner, self.client.plan = '123', 'Inactive'
        with self.assertRaisesRegex(ValueError, 'subscription'):
            self.provider.prepare()
        self.assertTrue(all(path == '/profile' for _, path, _ in self.client.calls))

    def test_intraday_chunks_are_bounded_and_current_candles_excluded_and_cached(self):
        self.provider.prepare()
        bars = self.provider.get(BENCHMARK_SYMBOL, '1h')
        calls = [p for _, path, p in self.client.calls if path == '/charts/intraday']
        self.assertEqual(len(calls), 3)
        for payload in calls:
            self.assertLessEqual((datetime.fromisoformat(payload['toDate'])-datetime.fromisoformat(payload['fromDate'])).days, 89)
            self.assertEqual(payload['interval'], '60')
            self.assertEqual(payload['instrument'], 'INDEX')
        self.assertTrue(bars)
        self.assertTrue(all(bar['timestamp']+3600 <= self.now.timestamp() for bar in bars))
        before = len(self.client.calls)
        self.assertEqual(bars, self.provider.get(BENCHMARK_SYMBOL, '1h'))
        self.assertEqual(before, len(self.client.calls))

    def test_daily_uses_daily_endpoint_weekly_is_derived_and_today_is_excluded(self):
        self.provider.prepare()
        daily = self.provider.get(BENCHMARK_SYMBOL, 'daily')
        weekly = self.provider.get(BENCHMARK_SYMBOL, 'weekly')
        self.assertGreater(len(weekly), 210)
        self.assertTrue(all(datetime.fromtimestamp(bar['timestamp'], IST).date() < self.now.date() for bar in daily))
        calls = [p for _, path, p in self.client.calls if path == '/charts/historical']
        self.assertTrue(calls)
        self.assertTrue(all('interval' not in p and p['expiryCode'] == 0 for p in calls))

    def test_malformed_candles_are_rejected(self):
        good = dict(timestamp=[1], open=[10], high=[12], low=[9], close=[11], volume=[0])
        for update in (dict(close=[]), dict(open=[float('nan')]), dict(high=[8]),
                       dict(low=[13]), dict(volume=[-1]), dict(timestamp=[True])):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.provider.parse(dict(good, **update))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.provider.parse({k: v*2 for k, v in good.items()})

    def service(self):
        return DhanSectorAnalysisService(self.execution, provider=self.provider, now=lambda: self.now)

    def test_summary_detail_rankings_and_constituents_use_only_selected_dhan_data(self):
        service = self.service()
        with patch('sector_heatmap.sector_service.SECTOR_DEFINITIONS', SECTOR_DEFINITIONS[:1]):
            service.refresh()
        summary = service.snapshot('swing')
        self.assertEqual(summary['provider'], 'DHAN')
        self.assertEqual(summary['account_id'], self.execution.account['id'])
        self.assertIsNone(summary['error'])
        sector = summary['sectors'][0]
        self.assertEqual(sector['rank'], 1)
        self.assertIsNotNone(sector['overall_score'])
        self.assertEqual(sector['top_contributors'][0]['change'], 10)
        for item in sector['top_contributors']:
            self.assertAlmostEqual(item['contribution'], item['weight']*.1)
        self.assertNotIn('series', sector['timeframe_states']['daily'])
        detail = service.snapshot('swing', 'bank')
        self.assertTrue(detail['sector']['timeframe_states']['daily']['series'])
        self.assertEqual(detail['provider'], 'DHAN')
        self.assertEqual(service.store.path, self.folder/'dhan-sector-analysis-history.json')
        self.assertTrue(service.store.path.exists())
        self.assertTrue(all(path in ('/profile','/charts/historical','/charts/intraday','/marketfeed/ohlc')
                            for _, path, _ in self.client.calls))
        self.assertFalse(service.running)

    def test_quote_failure_keeps_candle_analysis_and_reports_missing_contributions(self):
        service = self.service()
        self.client.quote_failure = True
        with patch('sector_heatmap.sector_service.SECTOR_DEFINITIONS', SECTOR_DEFINITIONS[:1]):
            service.refresh()
        result = service.snapshot()
        self.assertIsNotNone(result['sectors'][0]['overall_score'])
        self.assertEqual(result['sectors'][0]['top_contributors'], [])
        self.assertIn('unavailable', result['constituent_quote_error'])

    def test_disconnection_blocks_cached_snapshot(self):
        service = self.service()
        (self.folder/'disconnected.json').write_text('{}')
        with self.assertRaisesRegex(PermissionError, 'disconnected'):
            service.snapshot()

    def test_sector_permissions_do_not_grant_dhan_order_access(self):
        user = {'features': ['sectors']}
        self.assertTrue(allowed(user, '/api/dhan/sector-analysis'))
        self.assertTrue(allowed(user, '/api/dhan/sector-analysis/detail'))
        self.assertFalse(allowed(user, '/api/dhan/prepare'))
        self.assertFalse(allowed({'features': ['broker']}, '/api/dhan/sector-analysis'))


class DhanSectorRouteTests(unittest.TestCase):
    def test_real_handler_authorizes_each_request_and_reuses_one_analysis_service(self):
        source = (Path(__file__).resolve().parents[1]/'sector_heatmap/web.py').read_text()
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name in ('dhan_service', 'dhan_sector_analysis')]
        code = 'class Handler:\n' + '\n'.join('        '+ast.get_source_segment(source, node) for node in methods)
        account = dict(id='a'*32, broker='DHAN', label='Dhan', account_ref='123')
        user = {'id': 'owner'}
        def owned(u, aid):
            if u is not user or aid != account['id']:
                raise PermissionError('Account belongs to another user.')
            return account
        execution = SimpleNamespace(account=account)
        analysis = SimpleNamespace(start=unittest.mock.Mock(), snapshot=unittest.mock.Mock(return_value={'sectors': []}))
        env = dict(__package__='sector_heatmap', workspace_guard=None,
                   local_auth=SimpleNamespace(authorize=lambda *args: user,
                                             store=SimpleNamespace(account=owned)),
                   dhan_services={account['id']: execution}, dhan_services_lock=threading.RLock(),
                   dhan_sector_services={})
        exec(code, env)
        handler = env['Handler']()
        handler.headers, handler.command = {}, 'GET'
        responses = []
        handler.send_json = lambda status, data: responses.append((status, data))
        with patch('sector_heatmap.dhan_sector_analysis.DhanSectorAnalysisService', return_value=analysis):
            handler.dhan_sector_analysis({'account_id': [account['id']], 'mode': ['swing']})
            analysis.snapshot.return_value = {'sector': {'sector_id': 'bank'}}
            handler.dhan_sector_analysis({'account_id': [account['id']], 'sector': ['bank']}, detail=True)
            self.assertEqual(analysis.start.call_count, 1)
            analysis.snapshot.assert_called_with(mode='intraday', sector_id='bank')
            self.assertEqual([status for status, _ in responses], [200, 200])
            with self.assertRaises(PermissionError):
                handler.dhan_sector_analysis({'account_id': ['b'*32]})
            account['broker'] = 'FYERS'
            with self.assertRaises(PermissionError):
                handler.dhan_sector_analysis({'account_id': [account['id']]})


if __name__ == '__main__':
    unittest.main()
