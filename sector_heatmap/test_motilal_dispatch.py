"""Mount the actual shared-dashboard dispatch method without arming its runners."""
import ast,http.client,json,tempfile,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from urllib.parse import parse_qs,urlparse
from .workspaces import WorkspaceStore
from .motilal_shared_routes import Routes

class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.store=WorkspaceStore(root/'registry.sqlite3');self.owner=self.store.create_user('owner','long-test-password',bootstrap=True);self.other=self.store.create_user('other','another-test-password',actor=self.owner)
        self.account=self.store.create_account(self.owner,'MOTILAL_OSWAL','MO','CLIENT1');self.fyers=self.store.create_account(self.owner,'FYERS','FYERS','APP1')
        self.service=Mock();self.service.account=self.account;self.service.folder=self.store.folder(self.account);self.service.folder.mkdir(parents=True,exist_ok=True)
        self.service.client.live_enabled=True;self.service.status.return_value=dict(authenticated=True,broker='MOTILAL_OSWAL')
        self.routes=Routes(root);self.routes.services[self.account['id']]=self.service
        self.current=self.owner;auth=SimpleNamespace(store=self.store,authorize=lambda *args:self.current)
        candidate=Path('sector_heatmap/web.py')
        if 'def motilal_shared(' not in candidate.read_text():candidate=Path('outputs/motilal-oswal-integration/shared-route-patch/sector_heatmap/web.py')
        tree=ast.parse(candidate.read_text());node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='motilal_shared')
        scope=dict(parse_qs=parse_qs,urlparse=urlparse,workspace_guard=None,local_auth=auth,motilal_routes=self.routes,motilal_batches={},analysis_runs={},analysis_opportunities=lambda p,provider:dict(broker=provider.broker,account_id=provider.execution.account['id'],cards=[]))
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(candidate),'exec'),scope)
        dispatch=scope['motilal_shared']
        class Handler(BaseHTTPRequestHandler):
            motilal_shared=dispatch
            def send_json(self,status,value):
                body=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def do_GET(self):self.call()
            def do_POST(self):self.call(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            def call(self,payload=None):
                try:self.motilal_shared(urlparse(self.path).path,payload)
                except PermissionError as e:self.send_json(403,dict(error=str(e)))
                except Exception as e:self.send_json(409,dict(error=str(e)))
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,payload=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        connection.request('GET' if payload is None else 'POST',path,None if payload is None else json.dumps(payload),{'Content-Type':'application/json'})
        response=connection.getresponse();value=json.loads(response.read());status=response.status;connection.close();return status,value
    def test_owner_native_status_uses_actual_account(self):
        status,value=self.request('/api/motilal/status?account_id='+self.account['id']);self.assertEqual(status,200);self.assertEqual(value['broker'],'MOTILAL_OSWAL');self.service.client.request.assert_not_called()
    def test_other_user_cannot_use_same_account(self):
        self.current=self.other;status,_=self.request('/api/motilal/status?account_id='+self.account['id']);self.assertEqual(status,403);self.service.status.assert_not_called()
    def test_different_broker_account_cannot_use_native_route(self):
        status,_=self.request('/api/motilal/status?account_id='+self.fyers['id']);self.assertEqual(status,403)
    def test_conflicting_renko_account_ids_are_rejected(self):
        status,_=self.request('/api/renko-motilal/'+self.account['id']+'/runner?account_id='+self.fyers['id']);self.assertEqual(status,403)
    def test_sector_request_delegates_to_native_provider(self):
        sectors=Mock();sectors.snapshot.return_value=dict(broker='MOTILAL_OSWAL',sectors=[],history_policy='Native capture warmup')
        with patch.object(self.routes,'sector',return_value=sectors):status,value=self.request('/api/motilal/sector-analysis?account_id='+self.account['id']+'&mode=intraday')
        self.assertEqual(status,200);self.assertEqual(value['broker'],'MOTILAL_OSWAL');sectors.snapshot.assert_called_once_with('intraday',None)
    def test_handoff_runs_existing_analysis_with_native_provider(self):
        provider=SimpleNamespace(broker='MOTILAL_OSWAL',execution=self.service)
        with patch.object(self.routes,'handoff',return_value=provider):status,value=self.request('/api/motilal/analysis-handoff/analyze',dict(account_id=self.account['id'],broker='MOTILAL_OSWAL'))
        self.assertEqual(status,200);self.assertEqual(value['account_id'],self.account['id']);self.assertEqual(value['cards'],[])
