import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import requests
from sector_heatmap.broker_diagnostics import BrokerDiagnostics, broker_for_host, require_admin, install_http_timing


class DiagnosticsTests(unittest.TestCase):
    def test_isolation_spans_source_failure_and_expiry(self):
        trace = BrokerDiagnostics()
        trace.configure('FYERS', True, 1)
        with trace.span('FYERS', 'positions'):
            with trace.span('FYERS', 'HTTP'):
                pass
        with self.assertRaises(ValueError):
            with trace.span('FYERS', 'failed'):
                raise ValueError('never record this secret')
        events = trace.report('FYERS')['events']
        self.assertEqual(events[1]['parent_span_id'], events[0]['span_id'])
        self.assertTrue(Path(events[0]['script_path']).is_absolute())
        self.assertIsInstance(events[0]['line'], int)
        self.assertIsNotNone(events[0]['end_utc'])
        self.assertEqual(events[2]['outcome'], 'error')
        self.assertNotIn('never record', str(events))
        self.assertEqual(trace.report('DELTA_INDIA')['events'], [])
        with patch('sector_heatmap.broker_diagnostics.time.monotonic', return_value=trace.states['FYERS']['enabled_until'] + 1):
            self.assertFalse(trace.active('FYERS'))

    def test_http_wrapper_records_one_existing_call_without_secrets(self):
        trace = BrokerDiagnostics(); trace.configure('DELTA_INDIA', True)
        request = requests.Request('GET', 'https://api.india.delta.exchange/v2/test?token=DO_NOT_LOG_TOKEN_981', headers={'Authorization': 'DO_NOT_LOG_TOKEN_981'}).prepare()
        original = requests.sessions.Session.send
        try:
            with patch('sector_heatmap.broker_diagnostics.diagnostics', trace), patch.object(requests.sessions.Session, 'send', return_value='response') as sender:
                install_http_timing()
                self.assertEqual(requests.Session().send(request), 'response')
                sender.assert_called_once()
            self.assertNotIn('DO_NOT_LOG_TOKEN_981', str(trace.report('DELTA_INDIA')))
            self.assertEqual(len(trace.report('DELTA_INDIA')['events']), 1)
        finally:
            requests.sessions.Session.send = original

    def test_validation_and_admin(self):
        for user in (None, {}, {'admin': False}):
            with self.assertRaises(PermissionError): require_admin(user)
        require_admin({'admin': True})
        trace = BrokerDiagnostics()
        for args in [('FYERS', 'true'), ('UNKNOWN', True), ('FYERS', True, 61)]:
            with self.assertRaises(ValueError): trace.configure(*args)
        self.assertIsNone(broker_for_host('fyers.in.attacker.example'))
        self.assertEqual(broker_for_host('api.india.delta.exchange'), 'DELTA_INDIA')

    def test_capture_disable_does_not_stop_a_running_span_and_buffer_is_bounded(self):
        trace = BrokerDiagnostics(); trace.configure('FYERS', True)
        event = trace.begin('FYERS', 'inflight')
        trace.configure('FYERS', False); trace.end(event)
        self.assertEqual(trace.report('FYERS')['events'][0]['outcome'], 'ok')
        trace.configure('FYERS', True)
        for _ in range(1100): trace.mark('FYERS', 'tick')
        self.assertEqual(len(trace.report('FYERS')['events']), 1000)


class DiagnosticEndpointTests(unittest.TestCase):
    """Exercise the actual nested handler methods without starting trading services."""
    def handler(self, local_user=None, workspace_user=None, payload=None, origin='http://127.0.0.1:8080'):
        tree = ast.parse(Path('sector_heatmap/web.py').read_text())
        server = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_server')
        handler = next(n for n in server.body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
        methods = [n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name in {'diagnostic_api', 'diagnostic_user', 'diagnostic_broker'}]
        klass = ast.ClassDef(name='Harness', bases=[], keywords=[], body=methods, decorator_list=[])
        namespace = dict(diagnostics=BrokerDiagnostics(), require_admin=require_admin, parse_qs=parse_qs, urlparse=urlparse,
                         workspace_guard=object() if workspace_user is not None else None,
                         local_auth=SimpleNamespace(authorize=lambda *a: local_user) if local_user is not None else None)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[klass], type_ignores=[])), '<handler-test>', 'exec'), namespace)
        instance = namespace['Harness']()
        instance.path = '/api/admin/broker-diagnostics?broker=FYERS'
        instance.headers = {'Host': '127.0.0.1:8080', 'Origin': origin}
        instance.workspace_identity = (workspace_user, {'broker': 'FYERS'})
        instance.read_json = lambda: payload
        instance.send_json = lambda status, body: setattr(instance, 'result', (status, body))
        return instance

    def test_anonymous_and_regular_user_denied(self):
        for user in (None, {'admin': False}):
            handler = self.handler(local_user=user)
            handler.diagnostic_api()
            self.assertEqual(handler.result[0], 403)

    def test_admin_toggle_and_cross_origin_denial(self):
        handler = self.handler(local_user={'admin': True}, payload={'broker': 'FYERS', 'enabled': True})
        handler.diagnostic_api(True)
        self.assertEqual(handler.result[0], 200)
        self.assertTrue(handler.result[1]['enabled'])
        handler = self.handler(local_user={'admin': True}, payload={'broker': 'FYERS', 'enabled': True}, origin='http://attacker.example')
        handler.diagnostic_api(True)
        self.assertEqual(handler.result[0], 403)

    def test_workspace_cannot_capture_different_broker(self):
        handler = self.handler(workspace_user={'admin': True}, payload={'broker': 'DELTA_INDIA', 'enabled': True})
        handler.diagnostic_api(True)
        self.assertEqual(handler.result[0], 403)


if __name__ == '__main__': unittest.main()
