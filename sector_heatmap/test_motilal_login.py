import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from .motilal_service import Service
from .motilal_login import SavedLogin
from .motilal_api import MotilalError

class SavedLoginTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.folder=self.root/'.private/accounts/a';self.folder.mkdir(parents=True)
  self.credentials=dict(MO_CLIENT_ID='CLIENT1',MO_API_KEY='fixture-key',MO_API_SECRET='fixture-secret',MO_PUBLIC_IP='1.2.3.4',MO_LOCAL_IP='10.0.0.1',MO_MAC_ADDRESS='02:11:22:33:44:55')
  (self.folder/'credentials.json').write_text(json.dumps(self.credentials));self.now=1000
  self.service=Service(self.folder,dict(id='a',account_ref='CLIENT1',live_enabled=True),clock=lambda:self.now)
  self.login=SavedLogin(self.service);self.user={'id':'USER'};self.token='dashboard-session'
  self.payload=dict(client_id='CLIENT1',password='private-test-password',pan='ABCDE1234F',consent=True)
  self.login.save(self.payload)
 def tearDown(self):self.temp.cleanup()
 def mock_request(self):
  self.client=Mock();self.client.headers.return_value={};self.client.credentials={**self.credentials,'MO_SESSION_EXPIRES_AT':99999}
  self.client.request.return_value={'accesstoken':'access-test'};self.client.profile.return_value={'clientcode':'CLIENT1'}
  self.service.client_factory=Mock(return_value=self.client);self.service.install=Mock()
  response=Mock(status_code=200);response.json.return_value=dict(status='SUCCESS',AuthToken='auth-test',isAuthTokenVerified='FALSE')
  self.client.requester.post.return_value=response
  return response
 def test_encrypted_vault_contains_no_plain_password_or_pan(self):
  raw=self.login.vault.read_bytes();self.assertNotIn(self.payload['password'].encode(),raw);self.assertNotIn(self.payload['pan'].encode(),raw)
  value=self.login.read(self.login.vault);self.assertNotIn('password',value)
  self.assertEqual(value['password_hash'],hashlib.sha256(('private-test-passwordfixture-key').encode()).hexdigest())
  self.assertEqual(self.login.vault.stat().st_mode&0o777,0o600)
 def test_requires_consent_and_exact_account(self):
  for change,error in [({'consent':False},ValueError),({'client_id':'OTHER'},PermissionError),({'pan':'wrong'},ValueError)]:
   with self.assertRaises(error):self.login.save({**self.payload,**change})
 def test_otp_challenge_and_profile_before_session_save(self):
  reply=self.mock_request();result=self.login.start(self.user,self.token);self.assertTrue(result['otp_required'])
  self.assertFalse(self.service.session_path.exists());self.assertNotIn('auth-test',json.dumps(result))
  body=self.client.requester.post.call_args.kwargs['json'];self.assertNotIn('totp',body);self.assertNotIn('private-test-password',json.dumps(body))
  reply.json.return_value=dict(status='SUCCESS');result=self.login.verify(self.user,self.token,'123456')
  self.assertTrue(result['authenticated']);self.service.install.assert_called_once();self.assertFalse(self.login.pending.exists())
  self.assertEqual(self.client.request.call_args.args,('access_token',))
 def test_other_user_or_browser_cannot_verify(self):
  self.mock_request();self.login.start(self.user,self.token)
  for user,token in [({'id':'OTHER'},self.token),(self.user,'other-session')]:
   with self.assertRaises(PermissionError):self.login.verify(user,token,'123456')
  self.assertTrue(self.login.pending.exists())
 def test_failed_otp_consumed_no_token_saved_no_replay(self):
  reply=self.mock_request();self.login.start(self.user,self.token);reply.json.return_value=dict(status='ERROR',message='sensitive broker text')
  with self.assertRaises(MotilalError) as caught:self.login.verify(self.user,self.token,'123456')
  self.assertNotIn('sensitive',str(caught.exception));self.assertFalse(self.login.pending.exists());self.assertFalse(self.service.session_path.exists())
  with self.assertRaises(ValueError):self.login.verify(self.user,self.token,'123456')
 def test_expiry_and_rate_limit(self):
  self.mock_request();self.login.start(self.user,self.token)
  with self.assertRaises(ValueError):self.login.start(self.user,self.token)
  self.now+=301
  with self.assertRaises(ValueError):self.login.verify(self.user,self.token,'123456')
 def test_application_key_change_requires_resaving(self):
  self.credentials['MO_API_KEY']='changed';(self.folder/'credentials.json').write_text(json.dumps(self.credentials))
  with self.assertRaises(ValueError):self.login.start(self.user,self.token)
 def test_foreign_profile_cannot_install_session(self):
  reply=self.mock_request();self.login.start(self.user,self.token);reply.json.return_value=dict(status='SUCCESS');self.client.profile.return_value=dict(clientcode='OTHER')
  with self.assertRaises(PermissionError):self.login.verify(self.user,self.token,'123456')
  self.assertFalse(self.service.session_path.exists());self.service.install.assert_not_called()
 def test_removal_keeps_existing_session(self):
  self.service.session_path.write_text('existing');self.login.forget();self.assertFalse(self.login.vault.exists());self.assertEqual(self.service.session_path.read_text(),'existing')
 def test_swapped_account_vault_rejected(self):
  self.service.account['id']='other'
  with self.assertRaises(PermissionError):self.login.read(self.login.vault)

 def test_already_verified_broker_token_replaces_login_placeholder_before_access_exchange(self):
  reply=self.mock_request();self.client.credentials['MO_AUTH_TOKEN']='LOGIN'
  reply.json.return_value=dict(status='SUCCESS',AuthToken='verified-auth',isAuthTokenVerified='TRUE')
  def access(operation):
   self.assertEqual(operation,'access_token');self.assertEqual(self.client.credentials['MO_AUTH_TOKEN'],'verified-auth');return {'accesstoken':'access-test'}
  self.client.request.side_effect=access
  result=self.login.start(self.user,self.token);self.assertTrue(result['authenticated']);self.assertFalse(self.login.pending.exists())

 def test_disconnect_logs_out_old_session_and_requires_fresh_otp_even_if_login_verified(self):
  from unittest.mock import patch
  reply=self.mock_request();self.service.client=self.client;self.service.feed=Mock()
  reply.json.return_value=dict(status='SUCCESS',AuthToken='new-auth',isAuthTokenVerified='TRUE')
  self.service.session_path.write_text('old-session')
  with patch('sector_heatmap.workspace_disconnect.idle_states',return_value=[]),patch('sector_heatmap.workspace_disconnect.check_flat') as guard:
   result=self.login.disconnect_rechallenge(self.user,self.token)
  guard.assert_called_once();self.client.request.assert_called_once_with('logout',dict(userid='CLIENT1'))
  self.assertTrue(result['otp_required']);self.assertTrue((self.folder/'motilal-reauthentication.json').exists());self.assertFalse(self.service.session_path.exists())
  self.assertEqual(self.client.requester.post.call_count,2);self.assertIn('resendotp',self.client.requester.post.call_args.args[0]);self.service.install.assert_not_called()
 def test_active_exposure_prevents_logout_and_challenge(self):
  from unittest.mock import patch
  self.mock_request();self.service.client=self.client
  with patch('sector_heatmap.workspace_disconnect.idle_states',return_value=[]),patch('sector_heatmap.workspace_disconnect.check_flat',side_effect=ValueError('Position open')):
   with self.assertRaises(ValueError):self.login.disconnect_rechallenge(self.user,self.token)
  self.client.request.assert_not_called();self.client.requester.post.assert_not_called()
 def test_otp_failure_after_logout_retains_disconnected_state(self):
  from unittest.mock import patch
  reply=self.mock_request();self.service.client=self.client;self.service.feed=Mock()
  reply.json.return_value=dict(status='ERROR')
  with patch('sector_heatmap.workspace_disconnect.idle_states',return_value=[]),patch('sector_heatmap.workspace_disconnect.check_flat'):
   with self.assertRaisesRegex(ValueError,'was logged out'):self.login.disconnect_rechallenge(self.user,self.token)
  self.assertTrue((self.folder/'motilal-reauthentication.json').exists());self.assertFalse(self.service.session_path.exists())
 def test_successful_otp_removes_disconnected_marker(self):
  reply=self.mock_request();(self.folder/'motilal-reauthentication.json').write_text('{"reauthentication_required":true}')
  self.login.start(self.user,self.token);reply.json.return_value=dict(status='SUCCESS');self.login.verify(self.user,self.token,'123456')
  self.assertFalse((self.folder/'motilal-reauthentication.json').exists())

 def test_resend_matches_sdk_payload_and_renews_expired_challenge(self):
  reply=self.mock_request();self.login.start(self.user,self.token);self.now+=301
  result=self.login.resend(self.user,self.token);self.assertTrue(result['otp_required']);self.assertEqual(result['expires_at'],self.now+300)
  self.assertEqual(self.client.requester.post.call_args.kwargs['json'],{'clientcode':''})
  self.assertEqual(self.service.client_factory.call_args.args[0]['MO_AUTH_TOKEN'],'auth-test')
 def test_resend_checks_session_and_cooldown_without_network(self):
  self.mock_request();self.login.start(self.user,self.token);self.client.requester.post.reset_mock()
  with self.assertRaises(PermissionError):self.login.resend(self.user,'other-browser')
  with self.assertRaises(ValueError):self.login.resend(self.user,self.token)
  self.client.requester.post.assert_not_called()

 def test_already_verified_resend_response_is_not_reported_as_otp_sent(self):
  reply=self.mock_request();reply.json.return_value=dict(status='SUCCESS',message='Already Authenticated')
  with self.assertRaisesRegex(MotilalError,'did not confirm sending'):self.login.request(self.client,'resend',{'clientcode':''})
 def test_logout_can_recover_owned_verified_authorization_without_saved_session(self):
  from unittest.mock import patch
  reply=self.mock_request();self.login.start(self.user,self.token);self.service.client=None;self.service.feed=Mock()
  self.service.install.side_effect=lambda c:setattr(self.service,'client',c)
  reply.json.return_value=dict(status='SUCCESS',AuthToken='fresh-auth',isAuthTokenVerified='TRUE')
  with patch('sector_heatmap.workspace_disconnect.idle_states',return_value=[]),patch('sector_heatmap.workspace_disconnect.check_flat'):
   result=self.login.disconnect_rechallenge(self.user,self.token)
  self.assertTrue(result['otp_required']);self.assertIn(('logout',),[c.args[:1] for c in self.client.request.call_args_list]);self.assertFalse(self.service.session_path.exists())
