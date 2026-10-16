from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from sector_heatmap.job_http import install,operation


class JobHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.entered=threading.Event();self.release=threading.Event();self.calls=[];self.running=False;self.observed_run='one';self.fail_stop=False
        test=self
        class Auth:
            def check(self,h,mutation=False):return True
            def authorize(self,headers,mutation=False):return dict(id=headers.get('X-Test-User','alice'),admin=True)
        class Handler(BaseHTTPRequestHandler):
            def read_json(self):return json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            def send_json(self,status,value):
                b=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            def do_POST(self):
                body=self.read_json();test.calls.append(self.path)
                if self.path=='/api/analysis-handoff/analyze':
                    test.entered.set();test.release.wait(2);self.send_json(200,{'analysis_id':'one','cards':[{'answer':42}]})
                elif self.path=='/api/chartink/analyze':
                    offset=body.get('offset',0)
                    self.send_json(200,dict(results=[{'symbol':str(offset)}],analyzed=1,total=3,has_more=offset<2,operational_limits={'batch_size':1}))
                elif self.path=='/api/renko-supertrend/start':test.running=True;self.send_json(200,dict(running=True,run_id='one'))
                elif self.path=='/api/renko-supertrend/stop':test.running=False;self.send_json(200,dict(running=False,run_id='one'))
                else:self.send_json(200,{'ordinary':True})
            def do_GET(self):
                if self.path.startswith('/api/holdings-analysis?'):
                    from urllib.parse import urlsplit,parse_qs
                    q=parse_qs(urlsplit(self.path).query);offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['1'])[0])
                    end=offset if q.get('inventory_only',['0'])[0]=='1' else min(offset+limit,3)
                    test.calls.append(self.path)
                    self.send_json(200,dict(capture_id='capture',broker='FYERS',rows=[{'symbol':str(i)} for i in range(offset,end)],total=3,analysed=end,next_offset=end if end<3 else None))
                else:self.send_json(200,dict(running=test.running,run_id='one'))
            def log_message(self,*args):pass
        def handles(handler,path,payload,result):
            if not path.endswith('/renko-supertrend/start'):return None
            def snapshot():return dict(running=test.running,run_id=test.observed_run)
            def stop():
                test.calls.append('/api/renko-supertrend/stop')
                if test.fail_stop:raise ValueError('Fixture Stop failure')
                test.running=False
            return [(snapshot,stop)]
        self.store=install(Handler,Path(self.tmp.name),local_auth=Auth(),runner_factory=handles if getattr(self,'direct_monitor',False) else None)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.release.set();self.running=False;self.store.close()
        self.server.shutdown();self.server.server_close();self.thread.join(1)
    def request(self,method,path,body=None,user='alice',key=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        headers={'X-Test-User':user,'Content-Type':'application/json'}
        if key:headers['X-Job-Request-ID']=key
        c.request(method,path,json.dumps(body) if body is not None else None,headers)
        r=c.getresponse();value=json.loads(r.read());status=r.status;c.close();return status,value
    def wait(self,job_id,terminal=True):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            status,value=self.request('GET','/api/jobs?job_id='+job_id)
            if value['terminal']==terminal:return value
            time.sleep(.02)
        self.fail('Job did not settle')
    def test_immediate_acceptance_durable_output_and_user_isolation(self):
        start=time.monotonic();status,job=self.request('POST','/api/analysis-handoff/analyze',{'mode':'intraday'},key='same')
        self.assertEqual(status,202);self.assertLess(time.monotonic()-start,.5);self.assertTrue(self.entered.wait(1))
        status,again=self.request('POST','/api/analysis-handoff/analyze',{'mode':'intraday'},key='same')
        self.assertEqual(job['job_id'],again['job_id'])
        status,_=self.request('GET','/api/jobs?job_id='+job['job_id'],user='bob');self.assertEqual(status,403)
        self.release.set();value=self.wait(job['job_id']);self.assertEqual(value['output']['cards'],[{'answer':42}])
        self.assertEqual(self.calls.count('/api/analysis-handoff/analyze'),1)
    def test_stop_analysis_does_not_publish_a_late_result(self):
        _,job=self.request('POST','/api/analysis-handoff/analyze',{})
        self.assertTrue(self.entered.wait(1));_,value=self.request('POST','/api/jobs/cancel',{'job_id':job['job_id']})
        self.assertEqual(value['status'],'CANCELLING');self.release.set()
        self.assertEqual(self.wait(job['job_id'])['status'],'CANCELLED')
    def test_runner_stop_routes_to_existing_owned_workflow_once(self):
        _,job=self.request('POST','/api/renko-supertrend/start',{'underlying':'NIFTY'})
        deadline=time.monotonic()+1
        while not self.running and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(self.running)
        self.request('POST','/api/jobs/cancel',{'job_id':job['job_id']})
        value=self.wait(job['job_id']);self.assertEqual(value['status'],'CANCELLED');self.assertFalse(self.running)
        self.assertEqual(self.calls.count('/api/renko-supertrend/stop'),1)
    def test_one_submission_completes_all_screener_pages_without_browser_followups(self):
        status,job=self.request('POST','/api/chartink/analyze',{'symbols':['A','B','C'],'offset':0,'limit':1})
        self.assertEqual(status,202)
        value=self.wait(job['job_id'])
        self.assertEqual(value['status'],'COMPLETED')
        self.assertEqual([r['symbol'] for r in value['output']['results']],['0','1','2'])
        self.assertFalse(value['output']['has_more'])
        self.assertEqual(self.calls.count('/api/chartink/analyze'),3)

    def test_holdings_submission_executes_every_read_only_batch_on_server(self):
        status,job=self.request('POST','/api/holdings-analysis/analyze',{'broker':'FYERS','inventory_only':1,'offset':0,'limit':2})
        self.assertEqual(status,202)
        value=self.wait(job['job_id']);self.assertEqual(value['status'],'COMPLETED')
        self.assertEqual([r['symbol'] for r in value['output']['rows']],['0','1','2'])
        self.assertIsNone(value['output']['next_offset'])
        self.assertEqual(value['feature'],'holdings')
        self.assertEqual(len([p for p in self.calls if p.startswith('/api/holdings-analysis?')]),3)

    def test_backtest_and_analysis_keep_original_strategy_feature(self):
        for path,feature in [('/api/renko-engine/account/backtest','renko-engine'),('/api/renko-supertrend/analyze','renko-supertrend'),('/api/ema-band/analysis','ema-band')]:
            self.assertEqual(operation(path),('ANALYSIS',feature))

    def test_order_mutations_are_never_background_jobs(self):
        for path in ('/api/trade-ticket/submit','/api/trade-ticket/prepare','/api/renko-supertrend/override-entry','/api/straddle-squareoff/submit'):
            self.assertIsNone(operation(path));status,value=self.request('POST',path,{})
            self.assertEqual(status,200);self.assertTrue(value['ordinary'])


class DirectRunnerJobHTTPTests(JobHTTPTests):
    direct_monitor=True
    def test_failed_stop_never_claims_that_active_runner_was_cancelled(self):
        self.fail_stop=True
        _,job=self.request('POST','/api/renko-supertrend/start',{'underlying':'NIFTY'})
        deadline=time.monotonic()+1
        while not self.running and time.monotonic()<deadline:time.sleep(.01)
        self.request('POST','/api/jobs/cancel',{'job_id':job['job_id']})
        value=self.wait(job['job_id'])
        self.assertEqual(value['status'],'FAILED');self.assertTrue(self.running)
        self.assertIn('Stop failed',value['error'])
        self.assertTrue(value['output']['running'])
        self.assertEqual(self.calls.count('/api/renko-supertrend/stop'),1)

    def test_replacement_run_is_never_adopted_by_older_job(self):
        self.observed_run='replacement'
        _,job=self.request('POST','/api/renko-supertrend/start',{'underlying':'NIFTY'})
        value=self.wait(job['job_id'])
        self.assertEqual(value['status'],'COMPLETED')
        self.assertTrue(self.running)
        self.assertEqual(self.calls.count('/api/renko-supertrend/stop'),0)
        self.assertEqual(value['output']['run_id'],'one')
