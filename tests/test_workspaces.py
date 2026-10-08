import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from sector_heatmap.workspaces import WorkspaceStore, WorkspaceRuntime, isolated_environment, COOKIE
from sector_heatmap.workspace_guard import WorkspaceGuard
from sector_heatmap.workspace_portal import handler_factory


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.now=10000
        self.store=WorkspaceStore(self.root/'registry.sqlite3',clock=lambda:self.now)
        self.admin=self.store.create_user('admin','administrator-password',bootstrap=True)
        self.alice=self.store.create_user('alice','alice-private-password',actor=self.admin)
        self.bob=self.store.create_user('bob','bob-private-password',actor=self.admin)
        self.a=self.store.create_account(self.alice,'FYERS','Alice trading','ALICE-ID')
        self.b=self.store.create_account(self.bob,'DELTA_INDIA','Bob crypto','BOB-ID')
    def tearDown(self):self.tmp.cleanup()

    def test_password_hash_and_session_are_not_plaintext(self):
        token,user=self.store.login('alice','alice-private-password')
        self.assertEqual(self.store.session(token)['id'],self.alice['id'])
        raw=self.store.path.read_bytes()
        self.assertNotIn(b'alice-private-password',raw);self.assertNotIn(token.encode(),raw)
        self.store.logout(token)
        with self.assertRaises(PermissionError):self.store.session(token)

    def test_sessions_expire_and_password_change_revokes_all(self):
        token,user=self.store.login('alice','alice-private-password')
        other,_=self.store.login('alice','alice-private-password')
        self.store.change_password(user,'alice-private-password','a-new-private-password')
        for t in (token,other):
            with self.assertRaises(PermissionError):self.store.session(t)
        with self.assertRaises(PermissionError):self.store.login('alice','alice-private-password')
        t,_=self.store.login('alice','a-new-private-password');self.now+=8*3600
        with self.assertRaises(PermissionError):self.store.session(t)

    def test_wrong_password_and_rate_limit(self):
        for _ in range(5):
            with self.assertRaises(PermissionError):self.store.login('alice','wrong')
        with self.assertRaisesRegex(PermissionError,'Too many'):self.store.login('alice','alice-private-password')
        self.now+=61;self.store.login('alice','alice-private-password')

    def test_admin_creates_users_but_cannot_read_other_accounts(self):
        with self.assertRaises(PermissionError):self.store.create_user('charlie','charlie-private-password',actor=self.alice)
        with self.assertRaises(PermissionError):self.store.create_user('second','administrator-password',bootstrap=True)
        self.assertEqual(self.store.accounts(self.bob)[0]['id'],self.b['id'])
        self.assertEqual(self.store.accounts(self.admin),[])
        for user in (self.admin,self.bob):
            with self.assertRaises(PermissionError):self.store.account(user,self.a['id'])

    def test_multiple_users_and_multiple_accounts(self):
        a2=self.store.create_account(self.alice,'DELTA_INDIA','Alice crypto','ALICE-DELTA')
        self.assertEqual(len(self.store.accounts(self.alice)),2)
        self.assertNotEqual(self.a['port'],a2['port']);self.assertNotEqual(self.a['port'],self.b['port'])
        with self.assertRaises(ValueError):self.store.create_account(self.bob,'FYERS','Duplicate','alice-id')
        with self.assertRaises(ValueError):self.store.create_account(self.alice,'UNKNOWN','No','ID')

    def test_credential_ownership_and_duplicate_identity(self):
        fields={'FYERS_APP_ID':'FAKE-APP','FYERS_SECRET_KEY':'FAKE-SECRET'}
        with self.assertRaises(PermissionError):self.store.configure(self.bob,self.a['id'],fields)
        saved=self.store.configure(self.alice,self.a['id'],fields)
        self.assertFalse(saved['live_enabled'])
        a2=self.store.create_account(self.bob,'FYERS','Other','OTHER-ID')
        with self.assertRaisesRegex(ValueError,'already belongs'):self.store.configure(self.bob,a2['id'],fields)
        with self.assertRaisesRegex(ValueError,'new workspace'):self.store.configure(self.alice,self.a['id'],{**fields,'FYERS_APP_ID':'OTHER-APP'})
        path=self.store.folder(self.a)/'credentials.json'
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertNotIn('FAKE-SECRET',str(self.store.accounts(self.alice)))

    def test_credential_validation(self):
        fields={'FYERS_APP_ID':'FAKE-APP','FYERS_SECRET_KEY':'FAKE-SECRET'}
        for bad in ({'FYERS_ACCESS_TOKEN':'token'},{'FYERS_APP_ID':'x\nFYERS_ACCESS_TOKEN=bad'}, {**fields,'FYERS_REDIRECT_URI':'http://example.com/callback'}):
            with self.assertRaises(ValueError):self.store.configure(self.alice,self.a['id'],bad)
        with self.assertRaises(ValueError):self.store.configure(self.alice,self.a['id'],fields,live_enabled='true')

    def test_environment_does_not_inherit_credentials_or_live_gates(self):
        with patch.dict(os.environ,{'FYERS_ACCESS_TOKEN':'PRIVATE','DELTA_INDIA_API_KEY':'PRIVATE','OPENAI_API_KEY':'PRIVATE','SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS':'1','SECTOR_ANALYSIS_STATE_FILE':'/shared/state'}):
            env=isolated_environment(self.a,self.store.folder(self.a),self.store.path,8079)
        self.assertNotIn('FYERS_ACCESS_TOKEN',env);self.assertNotIn('DELTA_INDIA_API_KEY',env);self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('SECTOR_ANALYSIS_STATE_FILE',env)
        self.assertEqual(env['SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS'],'0')
        self.assertTrue(env['FYERS_TOKEN_FILE'].startswith(str(self.store.folder(self.a))))
        self.assertNotEqual(env['HOME'],os.environ.get('HOME'))
        b={**self.b,'live_enabled':True}
        env=isolated_environment(b,self.store.folder(b),self.store.path,8079)
        self.assertEqual(env['DELTA_INDIA_ENABLE_LIVE_ORDERS'],'1');self.assertEqual(env['SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS'],'0')

    def test_worker_checks_identity_host_and_origin(self):
        guard=WorkspaceGuard(self.store,self.a['id'],self.a['port'],8079)
        token,_=self.store.login('alice','alice-private-password')
        h={'Host':f"127.0.0.1:{self.a['port']}",'Cookie':f'{COOKIE}={token}'}
        self.assertEqual(guard.authorize(h)[1]['id'],self.a['id'])
        with self.assertRaises(PermissionError):guard.authorize(h,mutation=True)
        h['Origin']='http://'+h['Host'];guard.authorize(h,mutation=True)
        h['Origin']='http://evil.example'
        with self.assertRaises(PermissionError):guard.authorize(h,mutation=True)
        bob,_=self.store.login('bob','bob-private-password');h['Cookie']=f'{COOKIE}={bob}'
        with self.assertRaises(PermissionError):guard.authorize(h)
        h['Host']='evil.example'
        with self.assertRaises(PermissionError):guard.authorize(h)

    def test_worker_process_lock_survives_portal_restart(self):
        from sector_heatmap.file_lock import unlock_file
        folder=self.store.folder(self.a)
        env={'SECTOR_PULSE_WORKSPACE_REGISTRY':str(self.store.path),'SECTOR_PULSE_WORKSPACE_ID':self.a['id'],
             'HEATMAP_PORT':str(self.a['port']),'SECTOR_PULSE_PORTAL_PORT':'8079'}
        fake_file=str(folder/'source/sector_heatmap/workspace_guard.py')
        with patch.dict(os.environ,env),patch('sector_heatmap.workspace_guard.__file__',fake_file):
            guard=WorkspaceGuard.from_environment()
            try:
                runtime=WorkspaceRuntime(self.store,self.root)
                self.assertTrue(runtime.running(self.a['id']))
                with self.assertRaises(ValueError):runtime.configure(self.alice,self.a['id'],{},False)
                with self.assertRaises(RuntimeError):WorkspaceGuard.from_environment()
            finally:unlock_file(guard.owner_fd);os.close(guard.owner_fd)
        self.assertFalse(runtime.running(self.a['id']))
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(ValueError,'isolated source'):WorkspaceGuard.from_environment()

    def test_wrong_broker_action_and_running_credential_changes(self):
        guard=WorkspaceGuard(self.store,self.a['id'],self.a['port'],8079)
        guard.validate_action(self.a,'/api/renko-supertrend/start',{})
        for a,path,p in [(self.a,'/api/delta-india/submit',{}),(self.b,'/api/fyers-execution/submit',{}),(self.b,'/api/renko-instances/start-selected',{'broker':'FYERS'}),(self.b,'/api/delta-india/connect',{})]:
            with self.assertRaises(PermissionError):guard.validate_action(a,path,p)
        runtime=WorkspaceRuntime(self.store,self.root)
        with patch.object(runtime,'running',return_value=True):
            with self.assertRaises(ValueError):runtime.configure(self.alice,self.a['id'],{},False)

    def test_provision_from_git_excludes_untracked_secrets_and_isolates_state(self):
        repo=self.root/'repo';repo.mkdir()
        subprocess.run(['git','init','-q',str(repo)],check=True)
        (repo/'sector_heatmap').mkdir();(repo/'sector_heatmap/workspaces.py').write_text('# source')
        (repo/'heatmap_server.py').write_text('# entry')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.com','commit','-qm','fixture'],cwd=repo,check=True)
        (repo/'.fyers.env').write_text('PRIVATE=secret')
        runtime=WorkspaceRuntime(self.store,repo)
        folder=runtime.provision(self.a);other=runtime.provision(self.b)
        self.assertFalse((folder/'source/.fyers.env').exists())
        self.assertTrue((folder/'source/heatmap_server.py').exists())
        (folder/'source/.private').mkdir();(folder/'source/.private/state.json').write_text('alice-only')
        self.assertFalse((other/'source/.private/state.json').exists())
        self.assertTrue((folder/'source-commit.txt').exists())

    def test_provision_without_git_verifies_release_inventory(self):
        source=self.root/'release';(source/'sector_heatmap').mkdir(parents=True)
        payload=b'# source';(source/'sector_heatmap/workspaces.py').write_bytes(payload)
        inventory={'commit':'a'*40,'files':[{'path':'sector_heatmap/workspaces.py','sha256':hashlib.sha256(payload).hexdigest()}]}
        (source/'release-source-files.json').write_text(json.dumps(inventory))
        runtime=WorkspaceRuntime(self.store,source)
        self.assertTrue((runtime.provision(self.a)/'source/sector_heatmap/workspaces.py').exists())
        (source/'sector_heatmap/workspaces.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):runtime.provision(self.b)


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=WorkspaceStore(self.root/'registry.sqlite3')
        self.admin=self.store.create_user('admin','administrator-password',bootstrap=True)
        self.user=self.store.create_user('alice','alice-private-password',actor=self.admin)
        self.runtime=WorkspaceRuntime(self.store,self.root)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args: None)
        self.port=self.server.server_port
        self.server.RequestHandlerClass=handler_factory(self.store,self.runtime,self.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,data=None,cookie='',csrf='',origin=True,host=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        h={'Host':host or f'127.0.0.1:{self.port}','Cookie':cookie,'X-CSRF-Token':csrf}
        body=None
        if data is not None:
            body=json.dumps(data);h['Content-Type']='application/json'
            if origin:h['Origin']=f'http://127.0.0.1:{self.port}'
        c.request('GET' if data is None else 'POST',path,body,h);r=c.getresponse();status=r.status;headers=dict(r.getheaders());raw=r.read();c.close()
        return status,headers,json.loads(raw) if headers.get('Content-Type')=='application/json' else raw
    def login(self,name='alice',password='alice-private-password'):
        status,h,user=self.request('/api/workspaces/login',{'username':name,'password':password})
        self.assertEqual(status,200)
        self.assertIn('HttpOnly',h['Set-Cookie']);return h['Set-Cookie'].split(';')[0],user['csrf']
    def test_login_list_create_and_logout(self):
        self.assertEqual(self.request('/api/workspaces/accounts')[0],401)
        cookie,csrf=self.login()
        status,_,a=self.request('/api/workspaces/accounts',{'broker':'FYERS','label':'Private','account_ref':'ACCOUNT-1'},cookie,csrf)
        self.assertEqual(status,201);self.assertNotIn('credential_identity',a)
        status,_,result=self.request('/api/workspaces/accounts',cookie=cookie)
        self.assertEqual(len(result['accounts']),1);self.assertEqual(status,200)
        self.assertEqual(self.request('/api/workspaces/logout',{},cookie,csrf)[0],200)
        self.assertEqual(self.request('/api/workspaces/accounts',cookie=cookie)[0],401)
    def test_csrf_host_and_cross_origin_requests_rejected(self):
        cookie,csrf=self.login()
        p={'broker':'FYERS','label':'Private','account_ref':'ACCOUNT-1'}
        self.assertEqual(self.request('/api/workspaces/accounts',p,cookie,'bad')[0],403)
        self.assertEqual(self.request('/api/workspaces/accounts',p,cookie,csrf,origin=False)[0],403)
        self.assertEqual(self.request('/',host='evil.example')[0],403)
    def test_nonadmin_cannot_create_user_or_open_foreign_account(self):
        a=self.store.create_account(self.admin,'FYERS','Admin','ADMIN-1');cookie,csrf=self.login()
        self.assertEqual(self.request('/api/workspaces/users',{'username':'newuser','password':'newuser-private-password'},cookie,csrf)[0],403)
        with patch.object(self.runtime,'provision') as provision:
            self.assertEqual(self.request('/api/workspaces/open',{'account_id':a['id']},cookie,csrf)[0],403)
            provision.assert_not_called()
    def test_credentials_are_not_returned_or_stored_in_listing(self):
        a=self.store.create_account(self.user,'FYERS','Private','ACCOUNT-1');cookie,csrf=self.login()
        status,_,result=self.request('/api/workspaces/configure',{'account_id':a['id'],'credentials':{'FYERS_APP_ID':'FAKE-ID','FYERS_SECRET_KEY':'FAKE-SECRET'}},cookie,csrf)
        self.assertEqual(status,200);self.assertNotIn('FAKE-SECRET',json.dumps(result))
        result=self.request('/api/workspaces/accounts',cookie=cookie)[2]
        self.assertNotIn('FAKE-SECRET',json.dumps(result));self.assertTrue(result['accounts'][0]['configured'])


if __name__=='__main__':unittest.main()
