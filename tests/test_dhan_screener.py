import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from sector_heatmap.dhan_screener import DhanScreener
from sector_heatmap.section_permissions import allowed
from sector_heatmap.job_http import operation
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.dhan_execution import DhanExecutionService

class DhanScreenerTests(TestCase):
    def setUp(self):
        self.execution=SimpleNamespace(account={'id':'owned'},_client=Mock())
        self.provider=Mock()
        self.provider.resolve.side_effect=lambda symbol:{'securityId':{'NSE:ABC-EQ':'12','NSE:XYZ-EQ':'13'}[symbol]}
        self.provider._request.return_value={'status':'success','data':{'NSE_EQ':{'12':{'last_price':110,'ohlc':{'close':100},'volume':500}}}}
        self.service=Mock(provider=self.provider)
        from threading import Lock
        self.service.candidate_scan_lock=Lock()
        patcher=patch('sector_heatmap.dhan_screener.DhanSectorAnalysisService',return_value=self.service)
        patcher.start();self.addCleanup(patcher.stop)
        self.research=DhanScreener(self.execution)
    def test_source_membership_retained_and_quotes_use_native_security_ids(self):
        fetch=Mock(return_value={'status':'READY','candidates':['ABC','XYZ'],'source_sectors':{}})
        result=self.research.refresh({'url':'https://chartink.com/screener/sample'},fetch,lambda *a:{})
        self.assertEqual(result['candidates'],['ABC','XYZ'])
        self.assertEqual(result['account_id'],'owned');self.assertTrue(result['read_only'])
        self.assertEqual(result['market_data']['ABC']['day_change_pct'],10.000000000000009)
        self.assertEqual(result['market_data_provider'],'DHAN_READ_ONLY')
        self.provider._request.assert_called_once_with('/marketfeed/quote',{'NSE_EQ':[12,13]})
        self.assertIn('1 candidate',result['market_data_error'])
    def test_quote_failure_preserves_membership_without_another_provider(self):
        self.provider._request.side_effect=RuntimeError('private provider failure')
        result=self.research.refresh({},lambda *a:{'status':'READY','candidates':['ABC']},lambda *a:{})
        self.assertEqual(result['candidates'],['ABC']);self.assertEqual(result['market_data'],{})
        self.assertNotIn('private provider failure',result['market_data_error'])
    def test_partial_timeframes_cannot_produce_trade_plan(self):
        self.service._timeframe_candles.return_value={}
        with patch('sector_heatmap.dhan_screener.calculate_timeframe_state',return_value={'data_quality':'UNAVAILABLE'}),patch('sector_heatmap.dhan_screener.mtf_alignment',return_value='UNAVAILABLE'):
            result=self.research.analyze({'symbols':['ABC'],'prices':{'ABC':999999}})
        self.assertEqual(result['results'][0]['decision'],'REJECT')
        self.assertEqual(result['account_id'],'owned');self.assertEqual(result['analyzed'],1)
    def test_analysis_uses_owned_quotes_not_browser_price(self):
        self.service._timeframe_candles.return_value={}
        with patch('sector_heatmap.dhan_screener.calculate_timeframe_state',return_value={'data_quality':'READY'}),patch('sector_heatmap.dhan_screener.mtf_alignment',return_value='FULL BULLISH ALIGNMENT'),patch('sector_heatmap.dhan_screener.build_equity_opportunity',return_value={'entry':110,'recommended_invalidation':{'price':100}}) as build,patch('sector_heatmap.dhan_screener.evidence_conviction',return_value={'rating':'High'}):
            result=self.research.analyze({'symbols':['ABC'],'prices':{'ABC':999999}})
        self.assertEqual(build.call_args.args[0]['price'],110)
        self.assertEqual(result['results'][0]['target'],130)
    def test_screener_permission_does_not_follow_other_dhan_permissions(self):
        self.assertTrue(allowed({'features':['screener']},'/api/dhan/chartink/analyze'))
        self.assertFalse(allowed({'features':['broker']},'/api/dhan/chartink/analyze'))
        self.assertEqual(operation('/api/dhan/chartink/analyze?account_id=owned'),('ANALYSIS','screener'))
    def test_prepare_failure_never_fetches_source(self):
        self.provider.prepare.side_effect=PermissionError('wrong account')
        with self.assertRaises(PermissionError):DhanScreener(self.execution)

class OwnershipTests(TestCase):
    def test_other_user_cannot_resolve_account_before_provider_construction(self):
        with tempfile.TemporaryDirectory() as folder:
            store=WorkspaceStore(Path(folder)/'registry.sqlite3')
            owner=store.create_user('owner','long-owner-password',bootstrap=True)
            other=store.create_user('other','long-other-password',actor=owner)
            account=store.create_account(owner,'DHAN','Algo','123')
            with self.assertRaises(PermissionError):store.account(other,account['id'])
            store.configure(owner,account['id'],{'DHAN_CLIENT_ID':'123','DHAN_ACCESS_TOKEN':'token'})
            service=DhanExecutionService(store.account(owner,account['id']),store.folder(account))
            # Account-scoped profile client ID must agree before any data request.
            service.client_factory=lambda values:SimpleNamespace(client_id='123',request=lambda *a,**kw:{'dhanClientId':'456','dataPlan':'Active'})
            from sector_heatmap.dhan_sector_analysis import DhanCandleHistoryProvider
            with self.assertRaises(PermissionError):DhanCandleHistoryProvider(service).prepare()

class JobBoundaryTests(TestCase):
    def test_native_screener_job_is_durable_owned_and_not_visible_to_another_user(self):
        import io,time
        from email.message import Message
        from sector_heatmap.local_dashboard_auth import LocalDashboardAuth
        from sector_heatmap.workspaces import COOKIE
        from sector_heatmap.job_http import install
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=WorkspaceStore(root/'registry.sqlite3')
            admin=store.create_user('admin','long-admin-password',bootstrap=True)
            owner=store.create_user('owner','long-owner-password',actor=admin)
            other=store.create_user('other','long-other-password',actor=admin)
            store.set_features(admin,'owner',['screener']);store.set_features(admin,'other',['screener'])
            token,user=store.login('owner','long-owner-password')
            token2,user2=store.login('other','long-other-password')
            account=store.create_account(user,'DHAN','Algo','123')
            auth=LocalDashboardAuth(root,8080,store)
            calls=[]
            class Handler:
                def do_GET(self):self.send_json(404,{})
                def do_POST(self):
                    payload=self.read_json();u=auth.authorize(self.headers,True)
                    a=store.account(u,payload['account_id']);calls.append(a['id'])
                    self.send_json(200,dict(status='READY',broker='DHAN',account_id=a['id'],read_only=True,results=[],analyzed=0,total=0,has_more=False))
                def read_json(self):return json.loads(self.rfile.read())
                def send_json(self,status,value):self.response=(status,value)
            jobs=install(Handler,root,auth)
            try:
                def make(path,session,body=None):
                    h=Handler();h.path=path;h.command='POST' if body is not None else 'GET';h.wfile=io.BytesIO();h.rfile=io.BytesIO(json.dumps(body or {}).encode());h.headers=Message()
                    for k,v in {'Host':'127.0.0.1:8080','Origin':'http://127.0.0.1:8080','Cookie':COOKIE+'='+session}.items():h.headers[k]=v
                    return h
                h=make('/api/dhan/chartink/analyze?account_id='+account['id'],token,{'account_id':account['id'],'symbols':['ABC']});h.do_POST()
                self.assertEqual(h.response[0],202);jid=h.response[1]['job_id']
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    job=jobs.get(user['id']+':'+account['id'],jid)
                    if job['terminal']:break
                    time.sleep(.01)
                self.assertEqual(job['status'],'COMPLETED');self.assertEqual(job['output']['account_id'],account['id'])
                bad=make('/api/jobs?account_id='+account['id']+'&job_id='+jid,token2);bad.do_GET();self.assertEqual(bad.response[0],403)
                bad=make('/api/dhan/chartink/analyze',token2,{'account_id':account['id'],'symbols':['ABC']});bad.do_POST();self.assertEqual(bad.response[0],403)
                self.assertEqual(calls,[account['id']])
            finally:jobs.close()
