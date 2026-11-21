import json,tempfile,unittest,threading,http.client,hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer
from sector_heatmap.report_delivery import ReportDelivery
from sector_heatmap.workspaces import WorkspaceStore,COOKIE
from sector_heatmap.notification_admin import handler_factory
class ReportDeliveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.store=WorkspaceStore(self.root/'registry.sqlite3',clock=lambda:100)
  self.folder=self.root/'.private/notifications';self.folder.mkdir(parents=True)
  self.config={'owner_username':'owner','telegram_destinations':{'enabled':True,'shared_market':{'enabled':True,'title':'Shared report channel','chat_id':-1001,'activated_at':10},'private_trades':{'enabled':True,'chat_id':-1002}},'combined_reports':{'enabled':True},'telegram':{'token':'synthetic-token'}}
  (self.folder/'config.json').write_text(json.dumps(self.config));self.running=True;self.actions=[]
  def service(action):
   if action!='status':self.actions.append(action);self.running=action=='start'
   return self.running
  self.controller=ReportDelivery(self.root,self.store,service=service,clock=lambda:100)
  with self.store.db() as db:
   for uid,name,admin in [('o','owner',1),('u','user',0)]:
    db.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid,name,'synthetic','synthetic',admin));db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256((uid+'-token').encode()).hexdigest(),uid,'csrf',1000))
  self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(self.store,0,reports=self.controller));self.port=self.server.server_port;self.server.RequestHandlerClass=handler_factory(self.store,self.port,reports=self.controller);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close)
 def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
 def request(self,method='GET',payload=None,token='o-token',origin='http://127.0.0.1:8080',csrf='csrf'):
  conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3);headers={'Cookie':COOKIE+'='+token,'Origin':origin,'X-CSRF-Token':csrf,'Content-Type':'application/json'};conn.request(method,'/api/notification-admin/reports?section=sectors',json.dumps(payload) if payload is not None else None,headers);r=conn.getresponse();v=json.loads(r.read());status=r.status;conn.close();return status,v
 def test_interval_persists_without_changing_delivery_or_private_route(self):
  for interval in (300000,900000):
   code,data=self.request('POST',{'section':'sectors','refresh_interval_ms':interval})
   self.assertEqual(code,200);self.assertEqual(data['refresh_interval_ms'],interval)
   self.assertTrue(data['enabled'])
   saved=json.loads((self.folder/'config.json').read_text())
   self.assertEqual(saved['telegram_destinations'],self.config['telegram_destinations'])
  for interval in (0,True,12345):
   self.assertEqual(self.request('POST',{'section':'sectors','refresh_interval_ms':interval})[0],400)
 def test_status_no_secrets_or_changes(self):
  status,data=self.request();self.assertEqual(status,200);self.assertTrue(data['enabled']);self.assertNotIn('chat_id',json.dumps(data));self.assertNotIn('synthetic-token',json.dumps(data));self.assertEqual(self.actions,[])
 def test_unauthenticated_and_other_owner_denied(self):
  for token in ('invalid','u-token'):self.assertEqual(self.request(token=token)[0],403)
 def test_csrf_and_origin(self):
  for kwargs in [{'csrf':''},{'origin':'https://other.example'}]:self.assertEqual(self.request('POST',{'section':'sectors','enabled':False},**kwargs)[0],403)
  self.assertEqual(self.actions,[])
 def test_pause_resume_persistence_and_private_unchanged(self):
  for enabled in (False,True):
   code,v=self.request('POST',{'section':'sectors','enabled':enabled});self.assertEqual(code,200);self.assertEqual(v['enabled'],enabled);self.assertEqual(self.request()[1]['enabled'],enabled)
   saved=json.loads((self.folder/'config.json').read_text());self.assertEqual(saved['telegram_destinations']['private_trades'],self.config['telegram_destinations']['private_trades']);self.assertEqual(saved['telegram']['token'],'synthetic-token')
  self.assertEqual(self.actions,[]);self.assertEqual(saved['telegram_destinations']['shared_market']['activated_at'],100)
  self.assertEqual((self.folder/'config.json').stat().st_mode&0o777,0o600)
 def test_invalid_payload_and_destination_rejected(self):
  for p in [{'section':'sectors','enabled':'true'},{'section':'sectors','enabled':True,'chat_id':-99},{'section':'renko','enabled':True}]:self.assertEqual(self.request('POST',p)[0],400)
  self.config['telegram_destinations']['shared_market']['chat_id']=-1002;(self.folder/'config.json').write_text(json.dumps(self.config));self.assertEqual(self.request('POST',{'section':'sectors','enabled':True})[0],400);self.assertEqual(self.actions,[])
 def test_global_visibility_and_assignment_enforced(self):
  owner={'username':'owner','admin':True};visibility=self.store.sidebar_visibility();visibility['sectors']=False;self.store.set_sidebar_visibility(owner,visibility)
  self.assertEqual(self.request()[0],403)
  with self.assertRaises(PermissionError):self.controller.status({'username':'owner','admin':False,'features':[]},'handoff')
 def test_global_pause_does_not_unpause_private_notifications(self):
  from sector_heatmap.notification_controls import set_paused
  set_paused('all','telegram',True,path=self.folder/'preferences.json',clock=lambda:90)
  code,data=self.request('POST',{'section':'sectors','enabled':True});self.assertEqual(code,200);self.assertTrue(data['configured_enabled']);self.assertFalse(data['enabled']);self.assertTrue(data['global_paused'])
if __name__=='__main__':unittest.main()
