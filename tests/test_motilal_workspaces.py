import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sector_heatmap.workspaces import WorkspaceStore,isolated_environment
from sector_heatmap.workspace_guard import WorkspaceGuard

class MotilalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=WorkspaceStore(Path(self.tmp.name)/'registry.sqlite3')
        self.user=self.store.create_user('admin','long-test-password',bootstrap=True)
        self.account=self.store.create_account(self.user,'MOTILAL_OSWAL','MO test','CLIENT1')
    def tearDown(self):self.tmp.cleanup()
    @patch('sector_heatmap.motilal_service.network_identity',return_value=dict(MO_PUBLIC_IP='192.0.2.1',MO_LOCAL_IP='10.0.0.1',MO_MAC_ADDRESS='00:11:22:33:44:55'))
    def test_native_credentials_and_live_gate_are_account_scoped(self,network):
        account=self.store.configure(self.user,self.account['id'],dict(MO_CLIENT_ID='CLIENT1',MO_API_KEY='fixture-key',MO_API_SECRET='fixture-secret'),True)
        folder=self.store.folder(account);saved=json.loads((folder/'credentials.json').read_text())
        self.assertEqual(saved['MO_CLIENT_ID'],'CLIENT1')
        env=isolated_environment(account,folder,self.store.path,8079)
        self.assertEqual(env['MOTILAL_ENABLE_LIVE_ORDERS'],'1')
        self.assertEqual(env['SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS'],'0')
        self.assertEqual(env['DELTA_INDIA_ENABLE_LIVE_ORDERS'],'0')
        self.assertNotIn('MO_API_SECRET',env)
        self.assertEqual(env['SECTOR_PULSE_WORKSPACE_BROKER'],'MOTILAL_OSWAL')
    @patch('sector_heatmap.motilal_service.network_identity')
    def test_foreign_client_and_broker_credentials_are_rejected(self,network):
        with self.assertRaises(ValueError):self.store.configure(self.user,self.account['id'],dict(MO_CLIENT_ID='OTHER',MO_API_KEY='key',MO_API_SECRET='secret'),True)
        with self.assertRaises(ValueError):self.store.configure(self.user,self.account['id'],dict(FYERS_APP_ID='key'),True)
        network.assert_not_called()
    def test_visibility_default_and_previous_choices_are_preserved(self):
        values=self.store.sidebar_visibility();self.assertNotIn('motilal-oswal',values);self.assertTrue(values['broker']);values['screener']=False
        self.store.set_sidebar_visibility(self.user,values)
        self.assertFalse(self.store.sidebar_visibility()['screener'])
        self.assertTrue(self.store.sidebar_visibility()['broker'])
    def test_cross_broker_action_is_blocked(self):
        guard=WorkspaceGuard(self.store,self.account['id'],8100,8079)
        with self.assertRaises(PermissionError):guard.validate_action(self.account,'/api/trade-ticket/submit',{'broker':'FYERS'})
        guard.validate_action(self.account,'/api/motilal/submit',{'broker':'MOTILAL_OSWAL'})
