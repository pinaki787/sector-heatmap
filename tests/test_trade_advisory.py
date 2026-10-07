from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase, mock
import json
import requests

from sector_heatmap import trade_advisory as ai


class Response:
    def __init__(self, body=None, status=200):
        self.body, self.status_code = body, status
    def json(self):
        return self.body
    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError()


def report(verdict='PASS'):
    return dict(verdict=verdict, reasons=['Price structure supports the plan.'], missing_evidence=[],
                **{f: 'Evidence-based assessment' for f in ai.FIELDS})


class AdvisoryTests(TestCase):
    def setUp(self):
        self.config = mock.patch.object(ai, 'settings', return_value={'OPENAI_API_KEY': 'test-only', 'OPENAI_MODEL': ''})
        self.config.start()
        self.addCleanup(self.config.stop)
        self.preview = mock.Mock(return_value={'parsed': {'source_text': 'PRIVATE DO NOT SEND', 'action': 'BUY', 'entry': 39,
                                                       'stop_loss': 35, 'targets': [45], 'entry_instruction': 'STOP_LIMIT'},
                                             'mapping': {'status': 'EXACT', 'contract': {'symbol': 'NSE:EXAMPLE', 'underlying': 'EXAMPLE'}}})
        self.evidence = {'series': {role + '_' + res: {'fresh': True} for role in ('instrument', 'underlying') for res in ('5', 'D')},
                         'missing': [], 'captured_at': '2026-09-28T15:30:00+05:30', 'contract': {'symbol': 'NSE:EXAMPLE'}}

    def run_ai(self, post):
        return ai.analyze(self.preview, {'entry_mode': 'STOP_LIMIT', 'trigger_price': 40}, lambda: 'app:token', Path('/unused'), post=post)

    def test_disconnected_does_not_fetch_market_or_ai(self):
        with mock.patch.object(ai, 'settings', return_value={'OPENAI_API_KEY': '', 'OPENAI_MODEL': ''}):
            post = mock.Mock()
            result = self.run_ai(post)
        self.assertEqual(result['status'], 'SKIPPED')
        self.preview.assert_not_called()
        post.assert_not_called()

    def test_pass_fail_are_advisory_and_ticket_override_is_used(self):
        output = {'intraday': report('PASS'), 'swing': report('FAIL')}
        post = mock.Mock(return_value=Response({'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps(output)}]}]}))
        with mock.patch.object(ai, 'collect_evidence', return_value=self.evidence) as collect:
            result = self.run_ai(post)
        self.assertEqual(result['intraday']['verdict'], 'PASS')
        self.assertEqual(result['swing']['verdict'], 'FAIL')
        self.assertTrue(result['advisory_only'])
        self.assertEqual(collect.call_args.args[0]['entry'], 40)
        self.assertNotIn('source_text', collect.call_args.args[0])
        self.assertFalse(post.call_args.kwargs['json']['store'])

    def test_timeout_quota_and_malformed_output_are_unavailable(self):
        posts = [mock.Mock(side_effect=requests.Timeout()), mock.Mock(return_value=Response({}, 429)),
                 mock.Mock(return_value=Response({'status': 'completed', 'output': []}))]
        with mock.patch.object(ai, 'collect_evidence', return_value=self.evidence):
            for post in posts:
                result = self.run_ai(post)
                self.assertEqual(result['status'], 'UNAVAILABLE')
                self.assertIsNone(result['intraday'])
        self.assertTrue(ai._BUSY.acquire(False))
        ai._BUSY.release()

    def test_missing_essential_evidence_cannot_be_pass_or_fail(self):
        self.evidence['series']['instrument_D']['fresh'] = False
        data = ai.validate_reports({'intraday': report(), 'swing': report('FAIL')}, self.evidence)
        self.assertEqual(data['intraday']['verdict'], 'PASS')
        self.assertEqual(data['swing']['verdict'], 'UNAVAILABLE')
        self.assertIn('essential', data['swing']['entry'])

    def test_all_stale_skips_openai(self):
        self.evidence['series'] = {}
        post = mock.Mock()
        with mock.patch.object(ai, 'collect_evidence', return_value=self.evidence):
            result = self.run_ai(post)
        self.assertEqual(result['status'], 'UNAVAILABLE')
        post.assert_not_called()

    def test_busy_skips_immediately(self):
        ai._BUSY.acquire()
        try:
            self.assertEqual(self.run_ai(mock.Mock())['status'], 'SKIPPED')
            self.preview.assert_not_called()
        finally:
            ai._BUSY.release()

    def test_completed_bars_exclude_forming_and_reject_conflicting_duplicates(self):
        now = datetime(2026, 9, 29, 10, 4, tzinfo=ai.IST)
        ts = int(now.replace(hour=9, minute=55).timestamp())
        row = [ts, 10, 12, 9, 11, 100]
        rows = [row, row, [ts + 300, 11, 13, 10, 12, 100]]
        self.assertEqual(len(ai.completed_bars(rows, '5', now)), 1)
        with self.assertRaises(ValueError):
            ai.completed_bars([row, [ts, 10, 12, 9, 10, 100]], '5', now)
        self.assertEqual(ai.completed_bars([row], 'D', now), [])

    def test_stale_history_and_no_full_session_vwap(self):
        now = datetime(2026, 9, 29, 10, 4, tzinfo=ai.IST)
        bars = [{'timestamp': int((now - timedelta(days=4, minutes=5 * (40 - i))).timestamp()),
                 'open': 10, 'high': 12, 'low': 9, 'close': 11, 'volume': 100} for i in range(40)]
        summary = ai.summarize(bars, '5', now, 'NSE:TEST-EQ')
        self.assertFalse(summary['fresh'])
        self.assertIsNone(summary['session_typical_price_vwap_proxy'])
        self.assertIsNone(summary['volume_profile'])

    def test_no_order_endpoint_or_method_is_used(self):
        import inspect
        source = inspect.getsource(ai)
        self.assertNotIn('place_order', source)
        self.assertNotIn('/orders', source)

    def test_credentials_not_served_by_static_handler(self):
        import ast
        from sector_heatmap.config import ROOT
        source = ast.parse((ROOT / 'sector_heatmap/web.py').read_text())
        method = next(n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name == 'send_head')
        scope = {'Path': Path, 'ROOT': ROOT}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<test>', 'exec'), scope)
        for path in ('.env.local', '.env', '.private/token.json'):
            handler = mock.Mock()
            handler.translate_path.return_value = str(ROOT / path)
            self.assertIsNone(scope['send_head'](handler))
            handler.send_error.assert_called_once_with(404)
