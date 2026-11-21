"""Real loopback HTTP acceptance of unactivated worker candidate routes.

All registries, accounts and order stores are temporary. Broker adapters are fake.
Set CHART_ORDER_CANDIDATE to a reviewed candidate directory on Ubuntu.
"""
import ast, http.client, importlib.util, json, os, tempfile, threading, unittest
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from types import SimpleNamespace
from sector_heatmap.workspaces import WorkspaceStore, COOKIE
from sector_heatmap.chart_trading import ChartTradingService
from sector_heatmap.chart_trade_plan import ChartTradePlan

CANDIDATE=Path(os.environ.get("CHART_ORDER_CANDIDATE","/unavailable"))

class SimulatedAdapter:
    def __init__(self,account):
        self.account_id=account["id"];self.broker=account["broker"];self.submissions=0
        self.execution=SimpleNamespace(lock=threading.RLock())
    def live_enabled(self):return True
    def prepare(self,payload):
        return ChartTradePlan(self.account_id,self.broker,"TEST:SIMULATED","BUY",1,"25","22","30",
                              "LIMIT","25","MARGIN",".05",1,"AT_OR_BELOW")
    def refresh(self,plan):return plan
    def submit_bracket(self,plan,*,idempotency_key):
        self.submissions+=1
        return dict(account_id=self.account_id,symbol=plan.symbol,entry_order_id="SIMULATED-ONLY")
    def reconcile(self,plan,**kwargs):
        return dict(account_id=self.account_id,broker=self.broker,symbol=plan.symbol,status="ENTRY_PENDING",
                    protection_confirmed=False,filled_quantity=0,pending_quantity=1,retry_allowed=False)

@unittest.skipUnless((CANDIDATE/"manifest.json").is_file(),"Set an explicit worker candidate for loopback acceptance")
class CandidateHTTPTests(unittest.TestCase):
    def run_candidate(self,broker,exercise):
        manifest=json.loads((CANDIDATE/"manifest.json").read_text())
        account_meta=next(a for a in manifest["accounts"] if a["broker"]==broker)
        source=CANDIDATE/account_meta["id"]/"source"
        with tempfile.TemporaryDirectory() as temp:
            store=WorkspaceStore(Path(temp)/"registry.sqlite3")
            admin=store.create_user("test-admin","test-only-admin-password",bootstrap=True)
            store.create_user("test-owner","test-only-owner-password",actor=admin)
            store.set_features(admin,"test-owner",["chart-workspace","broker"])
            token,user=store.login("test-owner","test-only-owner-password")
            account=store.create_account(user,broker,"Simulated account","TEST-REFERENCE")
            with store.db() as db:db.execute("UPDATE accounts SET live_enabled=1 WHERE id=?",(account["id"],))
            account=store.account(user,account["id"])
            store.set_sidebar_visibility(admin,dict(store.sidebar_visibility(),**{"chart-workspace":True}))
            spec=importlib.util.spec_from_file_location("sector_heatmap._candidate_http_guard",source/"sector_heatmap/workspace_guard.py")
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            guard=module.WorkspaceGuard(store,account["id"],0,0)
            tree=ast.parse((source/"sector_heatmap/web.py").read_text())
            original=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=="Handler")
            names={"do_POST","read_json","send_json","end_headers","log_message"}
            methods=[n for n in original.body if isinstance(n,ast.FunctionDef) and n.name in names]
            self.assertEqual({n.name for n in methods},names)
            klass=ast.ClassDef(name="Handler",bases=[ast.Name(id="SimpleHTTPRequestHandler",ctx=ast.Load())],
                               keywords=[],body=methods,decorator_list=[])
            scope=dict(__name__="sector_heatmap._candidate_http",__package__="sector_heatmap",
                       SimpleHTTPRequestHandler=SimpleHTTPRequestHandler,json=json,
                       local_auth=None,workspace_guard=guard,fyers_execution=None,delta_india=None)
            exec(compile(ast.fix_missing_locations(ast.Module(body=[klass],type_ignores=[])),
                         str(source/"sector_heatmap/web.py"),"exec"),scope)
            adapter=SimulatedAdapter(account)
            service=ChartTradingService(account,Path(temp)/"chart.sqlite3",lambda selected:adapter)
            server=ThreadingHTTPServer(("127.0.0.1",0),scope["Handler"])
            guard.port=server.server_port
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            def request(action,payload=None,*,cookie=True,origin=True,raw=None):
                connection=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
                headers={"Content-Type":"application/json"}
                if cookie:headers["Cookie"]=COOKIE+"="+token
                if origin:headers["Origin"]="http://127.0.0.1:"+str(server.server_port)
                else:headers["Origin"]="https://unrelated.invalid"
                body=raw if raw is not None else json.dumps(payload or dict(account_id=account["id"],broker=broker))
                connection.request("POST","/api/chart-workspace/trading/"+action,body,headers)
                reply=connection.getresponse();status=reply.status;data=json.loads(reply.read());connection.close()
                return status,data
            try:
                with patch("sector_heatmap.chart_trading.get_service",return_value=service):
                    thread.start()
                    exercise(request,adapter,store,admin,account)
            finally:
                server.shutdown();server.server_close();thread.join(5);service.close()
            self.assertFalse(thread.is_alive())
    def test_preview_confirmation_and_status_dispatch_once(self):
        for broker in ("FYERS","DELTA_INDIA"):
            with self.subTest(broker=broker):
                def exercise(request,adapter,store,admin,account):
                    status,preview=request("prepare")
                    self.assertEqual(status,200);self.assertEqual(preview["status"],"PREVIEW_ONLY")
                    self.assertEqual(adapter.submissions,0)
                    payload=dict(account_id=account["id"],broker=broker,preview_id=preview["preview_id"],mode="LIVE")
                    self.assertEqual(request("arm",payload)[0],403)
                    payload["confirmation"]=preview["confirmation_phrase"]
                    self.assertEqual(request("arm",payload)[0],200)
                    self.assertEqual(request("arm",payload)[0],200)
                    self.assertEqual(adapter.submissions,1)
                    status,value=request("status",payload)
                    self.assertEqual(status,200);self.assertEqual(value["result"]["status"],"ENTRY_PENDING")
                    self.assertFalse(value["result"]["protection_confirmed"])
                self.run_candidate(broker,exercise)
    def test_session_origin_json_and_exact_account_enforcement(self):
        for broker in ("FYERS","DELTA_INDIA"):
            with self.subTest(broker=broker):
                def exercise(request,adapter,store,admin,account):
                    self.assertEqual(request("prepare",cookie=False)[0],403)
                    self.assertEqual(request("prepare",origin=False)[0],403)
                    self.assertEqual(request("prepare",raw="[]")[0],400)
                    self.assertEqual(request("prepare",raw="{")[0],400)
                    for payload in (dict(account_id="other",broker=broker),dict(account_id=account["id"],broker="DHAN")):
                        self.assertEqual(request("prepare",payload)[0],403)
                    self.assertEqual(request("cancel-condition")[0],403)
                    self.assertEqual(adapter.submissions,0)
                self.run_candidate(broker,exercise)
    def test_permissions_and_global_visibility_enforced_before_submission(self):
        for broker in ("FYERS","DELTA_INDIA"):
            with self.subTest(broker=broker):
                def exercise(request,adapter,store,admin,account):
                    for features in (["chart-workspace"],["broker"],[]):
                        store.set_features(admin,"test-owner",features)
                        self.assertEqual(request("prepare")[0],403)
                    store.set_features(admin,"test-owner",["chart-workspace","broker"])
                    store.set_sidebar_visibility(admin,dict(store.sidebar_visibility(),**{"chart-workspace":False}))
                    self.assertEqual(request("prepare")[0],403)
                    self.assertEqual(adapter.submissions,0)
                self.run_candidate(broker,exercise)
if __name__=="__main__":unittest.main()
