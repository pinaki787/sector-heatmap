import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from sector_heatmap.local_dashboard_auth import LocalDashboardAuth

class DashboardRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Mock();self.user={'admin':False,'username':'owner','features':[]}
        self.store.session.return_value=self.user
        self.auth=LocalDashboardAuth(Path(self.tmp.name),8080,self.store)
    def request(self,path,mutation=False):
        h=Mock();h.path=path;h.headers={'Host':'127.0.0.1:8080','Origin':'http://127.0.0.1:8080'};h.wfile=io.BytesIO()
        result=self.auth.check(h,mutation)
        return result,h
    def test_callback_preserved_for_admin_and_nonadmin(self):
        for admin in (True,False):
            self.user['admin']=admin
            ok,h=self.request('/?tokenId=abc%2B%2F%3D&next=https://evil.test')
            self.assertFalse(ok);h.send_response.assert_called_once_with(303)
            h.send_header.assert_any_call('Location','/accounts?tokenId=abc%2B%2F%3D')
            h.send_header.assert_any_call('Cache-Control','no-store')
            h.send_header.assert_any_call('Referrer-Policy','no-referrer')
    def test_invalid_callbacks_rejected(self):
        for q in ('tokenId=','tokenId=a&tokenId=b','tokenId=a%0D%0Ab','tokenId='+'a'*4097):
            ok,h=self.request('/?'+q);self.assertFalse(ok);h.send_response.assert_called_once_with(400)
    def test_home_is_available_without_shared_api_permissions(self):
        for path in ('/','/index.html','/workspace-entry'):
            self.assertTrue(self.request(path)[0])
        for path in ('/api/account','/api/live-pnl','/api/renko-supertrend/stop','/api/auth/start'):
            ok,h=self.request(path,True);self.assertFalse(ok)
    def test_account_selection_checks_ownership(self):
        self.store.account.side_effect=PermissionError('not yours')
        ok,h=self.request('/?brokerAccount=someone-else');self.assertFalse(ok)
        self.store.account.assert_called_once_with(self.user,'someone-else')
    def test_unauthenticated_callback_requires_signin(self):
        self.store.session.side_effect=PermissionError('signin')
        ok,h=self.request('/?tokenId=abc');self.assertFalse(ok)
        h.send_header.assert_any_call('Location','/auth/login?next=%2F%3FtokenId%3Dabc')
    def test_admin_api_behavior_unchanged(self):
        self.user['admin']=True;self.assertTrue(self.request('/api/account')[0])
    def test_wrong_host_is_rejected(self):
        h=Mock();h.path='/';h.headers={'Host':'evil.test'}
        self.assertFalse(self.auth.check(h));self.store.session.assert_not_called()
