from pathlib import Path
import tempfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from sector_heatmap.workspace_proxy import proxy,bootstrap

class Backend(BaseHTTPRequestHandler):
    seen=[]
    def do_GET(self):
        self.seen.append((self.path,dict(self.headers)))
        body=(b'{"data":"'+b'x'*(17*1024*1024)+b'"}' if self.path=='/api/large-chart' else b'<script src="/workspace-bootstrap.js"></script>' if self.path=='/' else
              b'window.SectorPulseWorkspace={workspace:{broker:"FYERS"}};' if self.path.startswith('/workspace-bootstrap.js') else
              b'{"workspace":{"broker":"FYERS"},"portal_url":"http://127.0.0.1:8080"}')
        self.send_response(200);self.send_header('Content-Type','text/html' if self.path=='/' else 'application/json' if self.path.startswith('/api/') else 'application/javascript')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        size=int(self.headers.get('Content-Length',0));self.seen.append((self.path,dict(self.headers),self.rfile.read(size)))
        body=b'{"ok":true}';self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

class Handler:
    def __init__(self,path,method='GET',body=b''):
        self.path=path;self.command=method;self.headers={'Host':'127.0.0.1:8080','Cookie':'sector_pulse_session=test'}
        self.rfile=BytesIO(body);self.wfile=BytesIO();self.result_headers={}
        if body:self.headers.update({'Content-Length':str(len(body)),'Origin':'http://127.0.0.1:8080'})
    def send_response(self,code):self.status=code
    def send_header(self,key,value):self.result_headers[key]=value
    def end_headers(self):pass

class ProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Backend)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()

    def setUp(self):
        self.aid='a'*32;port=self.server.server_port;aid=self.aid
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);folder=Path(tmp.name)
        class Store:
            def folder(inner,account):return folder
            def account(inner,user,selected):
                if selected!=aid:raise PermissionError('Not your account.')
                return dict(id=aid,port=port)
        class Runtime:
            def running(inner,selected):return True
        class Auth:
            store=Store();runtime=Runtime()
            def authorize(inner,headers,mutation=False):
                if mutation and headers.get('Origin')!='http://127.0.0.1:8080':raise PermissionError('Cross-origin action.')
                return dict(id='user')
            def json(inner,handler,status,value):
                handler.send_response(status);handler.wfile.write(json.dumps(value).encode())
        self.auth=Auth();Backend.seen=[]

    def test_large_chart_json_streams_without_the_html_buffer_limit(self):
        h=Handler('/broker-workspace/'+self.aid+'/api/large-chart')
        proxy(self.auth,h)
        self.assertEqual(h.status,200)
        self.assertEqual(len(json.loads(h.wfile.getvalue())['data']),17*1024*1024)

    def test_large_chart_is_compressed_when_browser_accepts_gzip(self):
        import gzip
        h=Handler('/broker-workspace/'+self.aid+'/api/large-chart');h.headers['Accept-Encoding']='gzip, deflate'
        proxy(self.auth,h)
        self.assertEqual(h.status,200)
        self.assertEqual(h.result_headers['Content-Encoding'],'gzip')
        self.assertEqual(len(json.loads(gzip.decompress(h.wfile.getvalue()))['data']),17*1024*1024)
        self.assertLess(len(h.wfile.getvalue()),200000)

    def test_document_bootstrap_bound_to_account_path(self):
        h=Handler('/broker-workspace/'+self.aid+'/');self.assertTrue(proxy(self.auth,h))
        self.assertEqual(h.status,200)
        self.assertIn(('/broker-workspace/'+self.aid+'/workspace-bootstrap.js').encode(),h.wfile.getvalue())
        self.assertEqual(Backend.seen[0][1]['Host'],'127.0.0.1:'+str(self.server.server_port))

    def test_every_request_rejects_another_users_account(self):
        h=Handler('/broker-workspace/'+'b'*32+'/api/runner')
        proxy(self.auth,h);self.assertEqual(h.status,403);self.assertEqual(Backend.seen,[])

    def test_mutation_checks_front_origin_then_rewrites_upstream_origin(self):
        h=Handler('/broker-workspace/'+self.aid+'/api/test','POST',b'{"broker":"FYERS"}')
        proxy(self.auth,h,True);self.assertEqual(h.status,200)
        self.assertEqual(Backend.seen[0][1]['Origin'],'http://127.0.0.1:'+str(self.server.server_port))
        self.assertEqual(Backend.seen[0][2],b'{"broker":"FYERS"}')
        Backend.seen=[]
        h.headers['Origin']='https://attacker.example'
        proxy(self.auth,h,True);self.assertEqual(h.status,403);self.assertEqual(Backend.seen,[])

    def test_bootstrap_and_context_use_portal_not_client_loopback(self):
        h=Handler('/broker-workspace/'+self.aid+'/workspace-bootstrap.js')
        proxy(self.auth,h);body=h.wfile.getvalue()
        self.assertIn(b'window.fetch=function',body);self.assertIn(b'window.EventSource=class',body)
        self.assertIn(self.aid.encode(),body)
        h=Handler('/broker-workspace/'+self.aid+'/api/workspace-context')
        proxy(self.auth,h);self.assertEqual(json.loads(h.wfile.getvalue())['portal_url'],'/accounts')

    def test_bootstrap_scopes_private_broker_but_keeps_inventory_and_dhan_on_portal(self):
        import shutil,subprocess
        node=shutil.which('node') or str(Path('.private/setup-tools/node/bin/node').resolve())
        if not Path(node).exists():self.skipTest('Node runtime unavailable')
        prefix='/broker-workspace/'+self.aid
        script="const assert=require('node:assert/strict');const seen=[];global.location={href:'https://portal.example"+prefix+"/',origin:'https://portal.example'};global.window={fetch:(url)=>seen.push(url),EventSource:class{}};"
        script+=bootstrap(prefix)
        script+='''
for(const path of ['/api/ema/runner','/api/workspace-context']) {
 window.fetch(path);assert.equal(seen.pop(),location.origin+PREFIX_TEST+path);
}
for(const path of ['/api/workspaces/accounts','/api/dhan/status','/api/renko-dhan/owned/runner','/api/ema-dhan/owned/runner','/api/band-dhan/owned/runner','/api/kama-dhan/owned/runner']) {
 window.fetch(path);assert.equal(seen.pop(),location.origin+path);
}
window.fetch('https://other.example/api/read');assert.equal(seen.pop(),'https://other.example/api/read');
'''.replace('PREFIX_TEST',repr(prefix))
        subprocess.run([node,'-e',script],check=True,capture_output=True)

    def test_regular_user_main_document_requires_owned_dhan_and_renko_permission(self):
        from sector_heatmap.local_dashboard_auth import LocalDashboardAuth
        from types import SimpleNamespace
        auth=LocalDashboardAuth.__new__(LocalDashboardAuth)
        auth.root=Path('.').resolve();auth.store=self.auth.store
        user=dict(id='user',admin=False,features=['renko-supertrend'])
        auth.authorize=lambda headers,mutation=False:user
        original=auth.store.account
        auth.store.account=lambda u,aid:dict(original(u,aid),broker='DHAN')
        handler=Handler('/?renkoBroker=DHAN&brokerAccount='+self.aid)
        self.assertTrue(auth.check(handler))
        user['features']=[]
        self.assertFalse(auth.check(handler));self.assertEqual(handler.status,303)
        user['features']=['renko-supertrend']
        handler=Handler('/')
        self.assertFalse(auth.check(handler));self.assertEqual(handler.status,303)
        handler=Handler('/api/ema-band/runner')
        auth.json=lambda h,status,value:h.send_response(status)
        self.assertFalse(auth.check(handler));self.assertEqual(handler.status,403)

    def test_unknown_and_traversal_account_paths_do_not_connect(self):
        for aid in ('../accounts','x'*32,'a'*31):
            h=Handler('/broker-workspace/'+aid+'/');proxy(self.auth,h)
            self.assertEqual(h.status,403)
        self.assertEqual(Backend.seen,[])

    def test_non_workspace_paths_remain_unhandled(self):
        h=Handler('/api/renko-supertrend/runner')
        self.assertFalse(proxy(self.auth,h));self.assertEqual(Backend.seen,[])

if __name__=='__main__':unittest.main()
