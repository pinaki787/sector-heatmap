"""Chart assignment and broker ownership boundaries using isolated test registries."""
import tempfile,unittest
from pathlib import Path
from sector_heatmap.workspaces import WorkspaceStore,COOKIE
from sector_heatmap.workspace_guard import WorkspaceGuard
from sector_heatmap.section_permissions import allowed,FEATURES

class ChartSectionPermissionsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=WorkspaceStore(Path(self.tmp.name)/'registry.sqlite3',clock=lambda:10000)
  self.admin=self.store.create_user('admin','test-admin-password',bootstrap=True)
  self.alice=self.store.create_user('alice','test-alice-password',actor=self.admin)
  self.bob=self.store.create_user('bob','test-bob-password',actor=self.admin)
 def test_chart_assignment_is_checked_again_on_existing_session(self):
  self.assertIn('chart-workspace',FEATURES)
  self.store.set_features(self.admin,'alice',['sectors','chart-workspace'])
  token,_=self.store.login('alice','test-alice-password')
  paths=['/api/chart-workspace/history','/api/chart-workspace/live','/api/chart-workspace/instruments']
  for path in paths:self.assertTrue(allowed(self.store.session(token),path))
  self.assertFalse(allowed(self.store.session(token),'/api/account'))
  self.store.set_features(self.admin,'alice',['sectors'])
  for path in paths:self.assertFalse(allowed(self.store.session(token),path))
  self.assertEqual(self.store.session(token)['features'],['sectors'])
 def test_visibility_changes_preserve_assignments_and_other_global_choices(self):
  self.store.set_features(self.admin,'alice',['chart-workspace'])
  settings=self.store.sidebar_visibility();settings['straddles']=False;settings['chart-workspace']=False
  self.store.set_sidebar_visibility(self.admin,settings)
  self.assertFalse(self.store.sidebar_visibility()['chart-workspace'])
  token,_=self.store.login('alice','test-alice-password')
  self.assertEqual(self.store.session(token)['features'],['chart-workspace'])
  settings['chart-workspace']=True;self.store.set_sidebar_visibility(self.admin,settings)
  self.assertFalse(self.store.sidebar_visibility()['straddles'])
  self.assertEqual(self.store.session(token)['features'],['chart-workspace'])
 def test_chart_permission_does_not_grant_other_users_broker_accounts(self):
  self.store.set_features(self.admin,'alice',['chart-workspace'])
  self.store.set_features(self.admin,'bob',['chart-workspace'])
  account=self.store.create_account(self.alice,'FYERS','Test only','ALICE')
  token,_=self.store.login('alice','test-alice-password')
  guard=WorkspaceGuard(self.store,account['id'],account['port'],8079)
  headers={'Host':'127.0.0.1:'+str(account['port']),'Cookie':COOKIE+'='+token}
  self.assertEqual(guard.authorize(headers)[1]['id'],account['id'])
  for username,password in [('bob','test-bob-password'),('admin','test-admin-password')]:
   other,_=self.store.login(username,password)
   with self.assertRaises(PermissionError):guard.authorize(dict(headers,Cookie=COOKIE+'='+other))
  with self.assertRaises(PermissionError):
   guard.validate_account_binding(account,'/api/chart-workspace/history?account_id='+'f'*32)
if __name__=='__main__':unittest.main()
