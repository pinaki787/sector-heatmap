import http.client
from http.server import ThreadingHTTPServer
import json
import tempfile
import threading
import unittest
from unittest.mock import Mock
from .motilal_server import handler_factory
from .motilal_api import MotilalError
from .motilal_execution import Tickets


class MountedRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.user=dict(id='USER1',username='tester',admin=True,csrf='csrf-fixture')
        self.account=dict(id='a'*32,broker='MOTILAL_OSWAL',account_ref='CLIENT1',live_enabled=True)
        self.guard=Mock();self.guard.authorize.return_value=(self.user,self.account)
        self.guard.store.sidebar_visibility.return_value={'broker':True}
        self.guard.context.return_value=dict(workspace=self.account)
        self.client=Mock(live_enabled=True);self.client.profile.return_value=dict(exchanges=['NSE'],products=['Delivery'],usertype='Investorclient')
        self.client.request.return_value=dict(uniqueorderid='ORDER123')
        master=Mock();master.exact.return_value=dict(symbol='MO:NSE:1',name='Native equity',exchange='NSE',token=1,lot_size=1,tick_size=.05,instrument='EQ')
        feed=Mock();feed.quote.return_value=dict(bid=100,ask=100.05,exchange_at=1000)
        self.service=Mock();self.service.tickets=Tickets(self.temp.name,self.client,master,feed,self.account['id'],clock=lambda:1000)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.guard,self.service))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,payload=None,csrf='csrf-fixture'):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        connection.request('POST' if payload is not None else 'GET',path,json.dumps(payload) if payload is not None else None,{'Content-Type':'application/json','X-CSRF-Token':csrf})
        response=connection.getresponse();body=response.read();status=response.status;connection.close()
        return status,json.loads(body)
    def test_standalone_trading_endpoints_are_removed(self):
        for path in ('/api/motilal/preview','/api/motilal/submit','/api/motilal/reconcile'):
            status,_=self.request(path,{'broker':'MOTILAL_OSWAL'})
            self.assertEqual(status,404)
        self.client.request.assert_not_called()
    def test_csrf_rejection_before_broker_call(self):
        status,_=self.request('/api/motilal/login-start',{},csrf='wrong')
        self.assertEqual(status,403);self.service.login_start.assert_not_called()
    def test_feature_permission_and_visibility_enforced(self):
        self.user['admin']=False;self.user['features']=[]
        status,_=self.request('/api/motilal/status');self.assertEqual(status,403)
        self.user['features']=['broker'];self.guard.store.sidebar_visibility.return_value={'broker':False}
        status,_=self.request('/api/motilal/status');self.assertEqual(status,403)
        self.service.status.assert_not_called()
    def test_wrong_broker_worker_cannot_serve_route(self):
        self.account['broker']='FYERS'
        status,_=self.request('/api/motilal/status');self.assertEqual(status,403)
        self.service.status.assert_not_called()
