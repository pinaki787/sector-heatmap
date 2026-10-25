import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from .motilal_service import Service


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.now=1000
        (self.folder/'credentials.json').write_text(json.dumps(dict(MO_CLIENT_ID='CLIENT1',MO_API_KEY='fixture-key',MO_API_SECRET='fixture-secret')))
        self.client=Mock();self.client.request.return_value={'accesstoken':'fixture-access'};self.client.profile.return_value={'clientcode':'CLIENT1'}
        self.factory=Mock(return_value=self.client);self.feed=Mock()
        self.service=Service(self.folder,dict(id='A'*32,account_ref='CLIENT1',live_enabled=True),client_factory=self.factory,feed_factory=Mock(return_value=self.feed),clock=lambda:self.now)
        self.user=dict(id='USER1');self.token='fixture-session'
    def tearDown(self):self.temp.cleanup()
    def test_login_bound_to_session_and_native_profile_before_persist(self):
        start=self.service.login_start(self.user,self.token)
        self.assertIn('apikey=fixture-key',start['url'])
        result=self.service.login_complete(self.user,self.token,'fixture-auth')
        self.assertEqual(result['client_id'],'CLIENT1')
        saved=json.loads(self.service.session_path.read_text())
        self.assertEqual(saved['MO_ACCESS_TOKEN'],'fixture-access')
        self.assertNotIn('fixture-auth',json.dumps(result))
        self.assertEqual(self.service.session_path.stat().st_mode&0o777,0o600)
        self.assertFalse((self.folder/'motilal-login-intent.json').exists())
    def test_foreign_session_or_user_cannot_complete(self):
        self.service.login_start(self.user,self.token)
        for user,token in [(self.user,'another-session'),(dict(id='OTHER'),self.token)]:
            with self.assertRaises(PermissionError):self.service.login_complete(user,token,'fixture-auth')
        self.factory.assert_not_called();self.assertFalse(self.service.session_path.exists())
    def test_failed_profile_does_not_persist_token_and_cannot_replay_intent(self):
        self.service.login_start(self.user,self.token);self.client.profile.side_effect=PermissionError('Different client')
        with self.assertRaises(PermissionError):self.service.login_complete(self.user,self.token,'fixture-auth')
        self.assertFalse(self.service.session_path.exists())
        with self.assertRaises(PermissionError):self.service.login_complete(self.user,self.token,'fixture-auth')
        self.factory.assert_called_once()
    def test_expired_login_intent_blocks(self):
        self.service.login_start(self.user,self.token);self.now+=601
        with self.assertRaises(PermissionError):self.service.login_complete(self.user,self.token,'fixture-auth')
        self.factory.assert_not_called()
    def test_no_cross_account_credentials(self):
        self.service.account['account_ref']='OTHER'
        with self.assertRaises(PermissionError):self.service.login_start(self.user,self.token)

class ServerNetworkTests(unittest.TestCase):
    def test_linux_uses_actual_route_interface_mac_instead_of_random_uuid(self):
        from unittest.mock import patch
        import socket
        from .motilal_service import server_mac
        with patch('sys.platform','linux'),patch('socket.if_nameindex',return_value=[(1,'eth0')]),patch('fcntl.ioctl',return_value=b'\0'*20+socket.inet_aton('10.0.0.2')),patch('pathlib.Path.read_text',return_value='02:11:22:33:44:55\n'),patch('uuid.getnode') as random:
            self.assertEqual(server_mac('10.0.0.2'),'02:11:22:33:44:55')
            random.assert_not_called()

    def test_wrong_interface_and_multicast_mac_are_rejected(self):
        from unittest.mock import patch
        import socket
        from .motilal_service import server_mac
        for ip,mac in [('10.0.0.3','02:11:22:33:44:55'),('10.0.0.2','03:11:22:33:44:55')]:
            with patch('sys.platform','linux'),patch('socket.if_nameindex',return_value=[(1,'eth0')]),patch('fcntl.ioctl',return_value=b'\0'*20+socket.inet_aton(ip)),patch('pathlib.Path.read_text',return_value=mac),patch('uuid.getnode') as random:
                with self.assertRaises(ValueError):server_mac('10.0.0.2')
                random.assert_not_called()

class ReportOwnershipTests(unittest.TestCase):
    setUp=SessionTests.setUp
    tearDown=SessionTests.tearDown

    def test_foreign_or_missing_report_owner_is_not_returned(self):
        self.service.client=self.client
        for data in [[{'clientid':'OTHER'}],[{'symboltoken':1}]]:
            self.client.request.return_value={'data':data,'_timing':{}}
            with self.assertRaises(PermissionError):self.service.book('orders')

    def test_verified_native_report_rows_are_returned(self):
        self.service.client=self.client
        data=[{'clientid':'CLIENT1','symboltoken':1}]
        self.client.request.return_value={'data':data,'_timing':{}}
        self.assertEqual(self.service.book('orders')['data'],data)
