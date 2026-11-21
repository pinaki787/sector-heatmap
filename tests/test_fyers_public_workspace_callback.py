import unittest
from unittest.mock import patch
from sector_heatmap.authentication import validated_config
class CallbackTests(unittest.TestCase):
 def config(self,url):
  return dict(FYERS_APP_ID='test',FYERS_SECRET_KEY='test',FYERS_REDIRECT_URI=url)
 def test_exact_account_public_callback(self):
  with patch.dict('os.environ',{'SECTOR_PULSE_WORKSPACE_ID':'account-a'}),patch('sector_heatmap.authentication.public_origin',return_value='https://utrading.pinakicloud.com'),patch('sector_heatmap.authentication.load_config',return_value=self.config('https://utrading.pinakicloud.com/broker-workspace/account-a/callback')):
   self.assertTrue(validated_config(8102))
 def test_other_account_callback_rejected(self):
  with patch.dict('os.environ',{'SECTOR_PULSE_WORKSPACE_ID':'account-a'}),patch('sector_heatmap.authentication.public_origin',return_value='https://utrading.pinakicloud.com'),patch('sector_heatmap.authentication.load_config',return_value=self.config('https://utrading.pinakicloud.com/broker-workspace/account-b/callback')):
   with self.assertRaises(RuntimeError):validated_config(8102)
 def test_local_callback_still_requires_matching_port(self):
  with patch('sector_heatmap.authentication.public_origin',return_value=''),patch('sector_heatmap.authentication.load_config',return_value=self.config('http://127.0.0.1:8103/callback')):
   with self.assertRaises(RuntimeError):validated_config(8102)

class RunningCallbackTests(unittest.TestCase):
 def runtime(self):
  from sector_heatmap.workspaces import WorkspaceRuntime
  import threading
  from unittest.mock import Mock
  r=object.__new__(WorkspaceRuntime);r.lock=threading.RLock();r.running=lambda aid:True;r.store=Mock()
  r.store.account.return_value=dict(broker='FYERS',live_enabled=True)
  return r
 def test_redirect_only_update_allowed_while_running(self):
  r=self.runtime();r.configure({},'account',{'FYERS_REDIRECT_URI':'https://example/callback','FYERS_APP_ID':'','FYERS_SECRET_KEY':''},True)
  r.store.configure.assert_called_once()
 def test_secret_or_capability_change_remains_blocked(self):
  for fields,live in [({'FYERS_SECRET_KEY':'changed'},True),({'FYERS_REDIRECT_URI':'https://example/callback'},False)]:
   r=self.runtime()
   with self.assertRaises(ValueError):r.configure({},'account',fields,live)
   r.store.configure.assert_not_called()

class CentralCallbackTests(unittest.TestCase):
 def test_registered_central_callback_allowed(self):
  with patch.dict('os.environ',{'SECTOR_PULSE_WORKSPACE_ID':'a'*32}),patch('sector_heatmap.authentication.public_origin',return_value='https://utrading.pinakicloud.com'),patch('sector_heatmap.authentication.load_config',return_value=dict(FYERS_APP_ID='test',FYERS_SECRET_KEY='test',FYERS_REDIRECT_URI='https://utrading.pinakicloud.com/callback')):
   self.assertTrue(validated_config(8102))
 def test_routing_requires_well_formed_account_state(self):
  from sector_heatmap.fyers_oauth_routing import account_from_state
  self.assertEqual(account_from_state('a'*32+'.'+'x'*32),'a'*32)
  for state in [None,'','../callback','a'*32+'.short','z'*32+'.'+'x'*32,'a'*32+'.'+'x'*32+'&account=other']:
   self.assertIsNone(account_from_state(state))


class FyersSessionReuseTests(unittest.TestCase):
    def test_sign_in_start_reuses_valid_session_and_waits_for_verified_expiry(self):
        import ast
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock

        source = Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py"
        tree = ast.parse(source.read_text())
        route, = (
            node for node in ast.walk(tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "path == '/api/auth/start'"
        )
        module = ast.parse("def start(self): pass")
        module.body[0].body = [route]
        handler = compile(module, str(source), "exec")
        for current, expected_status, oauth in (
            ({"authenticated": True, "message": "Session already valid"}, 200, False),
            ({"authenticated": False, "message": "Verification unavailable"}, 503, False),
            ({"authenticated": False, "reauthentication_required": True}, 200, True),
        ):
            with self.subTest(current=current):
                start_oauth = Mock(return_value="https://example.invalid/sign-in")
                state = {}
                environment = {
                    "path": "/api/auth/start", "fyers_auth_status": lambda: current,
                    "authorization_url": start_oauth, "secrets": SimpleNamespace(token_urlsafe=lambda n: "nonce"),
                    "workspace_guard": SimpleNamespace(account_id="selected-account"), "port": 8100,
                    "state": state,
                }
                exec(handler, environment)
                response = Mock()
                environment["start"](response)
                status, payload = response.send_json.call_args.args
                self.assertEqual(status, expected_status)
                self.assertEqual("url" in payload, oauth)
                self.assertEqual(start_oauth.called, oauth)
                self.assertEqual("oauth_state" in state, oauth)
                if oauth:
                    self.assertEqual(state["oauth_state"], "selected-account.nonce")
