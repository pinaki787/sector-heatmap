"""Exercise the actual HTTP dispatcher with fake authenticated accounts and brokers."""
import tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from strategies.renko_supertrend.test_runner import FakeBroker

class RouteTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.account=dict(id='a'*32,broker='FYERS',live_enabled=True)
  self.user=dict(id='owner')
  def account(user,aid):
   if aid!=self.account['id']:raise PermissionError('Account belongs to another user.')
   return self.account
  self.store=SimpleNamespace(account=account,folder=lambda a:Path(self.tmp.name))
  self.env=dict(__name__="sector_heatmap.engine_test",__package__="sector_heatmap",workspace_guard=SimpleNamespace(store=self.store),local_auth=None,engine_services={},engine_services_lock=threading.RLock(),RenkoSupertrendBroker=lambda *a:FakeBroker(),ema_master_dir=None,ema_band_candles=None,select_ema_atm_option=None,automation_policy=SimpleNamespace(current=lambda:{}),json=__import__('json'))
  source=(Path(__file__).resolve().parents[1]/'sector_heatmap/web.py').read_text()
  method=source[source.index('        def renko_engine('):source.index('        def dhan_strategy(')]
  exec('class Handler:\n'+method,self.env)
  self.h=self.env['Handler']();self.h.workspace_identity=(self.user,self.account);self.h.send_json=lambda status,value:setattr(self,'response',(status,value))
 def test_private_fyers_capabilities_and_isolated_state(self):
  self.h.renko_engine('/api/renko-engine/'+self.account['id']+'/capabilities')
  self.assertEqual(self.response[0],200);self.assertEqual(self.response[1]['modes'],['PAPER','LIVE','BACKTEST'])
  service=self.env['engine_services'][self.account['id']]
  self.assertEqual(service.runner.path,Path(self.tmp.name)/'renko-engine/state.json');self.assertFalse(service.runner.state['running'])
 def test_cross_account_rejected(self):
  with self.assertRaises(PermissionError):self.h.renko_engine('/api/renko-engine/'+'b'*32+'/capabilities')
  self.assertEqual(self.env['engine_services'],{})
 def test_shared_fyers_fallback_rejected(self):
  self.env['workspace_guard']=None;self.env['local_auth']=SimpleNamespace(store=self.store,authorize=lambda *a:self.user)
  self.h.headers={};self.h.command='GET'
  with self.assertRaisesRegex(PermissionError,'private account'):self.h.renko_engine('/api/renko-engine/'+self.account['id']+'/capabilities')
 def test_private_dhan_route_uses_dhan_adapter(self):
  self.account['broker']='DHAN';self.h.dhan_service=lambda aid:None
  with patch('sector_heatmap.dhan_strategy_broker.Broker',side_effect=lambda *a:FakeBroker()):
   self.h.renko_engine('/api/renko-engine/'+self.account['id']+'/capabilities')
  service=self.env['engine_services'][self.account['id']]
  self.assertEqual(service.broker,'DHAN');self.assertFalse(service.runner.state['running'])
 def test_private_delta_ignores_shared_environment_credentials(self):
  import json,os
  self.account['broker']='DELTA_INDIA'
  Path(self.tmp.name,'credentials.json').write_text(json.dumps(dict(DELTA_INDIA_API_KEY='private-key',DELTA_INDIA_API_SECRET='private-secret')))
  class Delta:
   def __init__(inner,*a):inner.live={};inner.runner={}
   def _gate(inner):return inner._credentials()['DELTA_INDIA_ENABLE_LIVE_ORDERS']=='1'
  class Broker(FakeBroker):
   def __init__(inner,delta,*a):super().__init__();inner.delta=delta
   def live_enabled(inner):return inner.delta._gate()
  with patch('sector_heatmap.delta_india.DeltaIndia',Delta),patch('strategies.renko_supertrend.delta_broker.Broker',Broker),patch.dict(os.environ,dict(DELTA_INDIA_API_KEY='shared-key',DELTA_INDIA_API_SECRET='shared-secret')):
   self.h.renko_engine('/api/renko-engine/'+self.account['id']+'/capabilities')
  service=self.env['engine_services'][self.account['id']]
  credentials=service.runner.adapter.delta._credentials()
  self.assertEqual(credentials['DELTA_INDIA_API_KEY'],'private-key')
  self.account['live_enabled']=False;self.assertFalse(service.runner.adapter.live_enabled())
if __name__=='__main__':unittest.main()
