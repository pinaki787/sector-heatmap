import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from position_control import PositionManager,enqueue,close_action
from manual_entry import runtime_identity
class PositionControlTests(unittest.TestCase):
 def fixture(self,root,*,side='CE'):
  config=dict(account='a'*32,broker='FYERS',execution_mode='LIVE',execution_route='OPTIONS',underlying='MCX:CRUDEOILM26DECFUT',timeframe=1,runtime_session='b'*32,product='MARGIN')
  own=dict(symbol='MCX:CRUDEOILM26DEC7650CE',quantity=1,side=side,product='MARGIN',entry_timestamp=50,fill_price=100)
  engine=SimpleNamespace(position=dict(own),pending_underlying_flip=None)
  executor=SimpleNamespace(state=dict(position=dict(own),pending=None,seen=[]),save=Mock())
  broker=dict(quantity=-1 if side=='SHORT' else 1,orders=False,available=True)
  submissions=[]
  def verify(position,*,flat=False):
   if not broker['available']:raise ValueError('Broker reads unavailable')
   if broker['orders']:raise ValueError('Broker order pending')
   if position is None:return dict(flat=True)
   expected=-position['quantity'] if position['side']=='SHORT' else position['quantity'];qty=broker['quantity']
   if flat is True and qty:raise ValueError('Not broker flat')
   if flat is False and qty!=expected or flat is None and qty not in (0,expected):raise ValueError('Ownership mismatch')
   return dict(flat=qty==0)
  def submit(action):
   submissions.append(action);broker['quantity']=0;executor.state['position']=None
   return dict(filled_quantity=1)
  def attach(holding):
   if holding['symbol']!=own['symbol'] or holding['quantity']!=abs(broker['quantity']):raise ValueError('Holding changed')
   return dict(own,attached_existing=True)
  manager=PositionManager(config,root,engine,executor,verify=verify,attach=attach,submit=submit,clock=lambda:100)
  return config,own,engine,executor,broker,submissions,manager
 def queue(self,root,config,operation,identifier='c'*32,holding=None):
  return enqueue(root,config,dict(runtime_identity(config,root,'LIVE'),operation=operation,request_id=identifier,**(dict(holding=holding) if holding else {})),now=100)
 def test_stop_reduces_exact_owned_call_and_confirms_flat_before_success(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);self.queue(root,c,'STOP')
   self.assertTrue(m.poll());self.assertEqual(s[0]['action'],'SELL');self.assertEqual(s[0]['position'],p)
   self.assertEqual(m.request['phase'],'STOPPED');self.assertTrue(m.request['broker_flat_confirmed']);self.assertTrue(m.entry_blocked)
   self.assertFalse(m.poll());self.assertEqual(len(s),1)
 def test_stop_already_externally_flat_sends_no_order(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);b['quantity']=0;self.queue(root,c,'STOP')
   self.assertTrue(m.poll());self.assertEqual(s,[]);self.assertIsNone(x.state['position'])
 def test_long_short_exit_actions_never_open_opposite_position(self):
  for side,expected in [('CE','SELL'),('PE','SELL'),('LONG','CLOSE_LONG'),('SHORT','CLOSE_SHORT')]:
   self.assertEqual(close_action(dict(side=side),100)['action'],expected)
 def test_partial_or_unknown_fill_retains_pending_and_never_resubmits(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root)
   def partial(action):
    s.append(action);x.state['pending']=dict(stage='UNRESOLVED_FILL');raise RuntimeError('Partial fill')
   m.submit=partial;self.queue(root,c,'STOP')
   self.assertFalse(m.poll());self.assertEqual(m.request['phase'],'RECOVERY_REQUIRED');self.assertIsNotNone(x.state['position']);self.assertTrue(m.blocked)
   self.queue(root,c,'STOP','d'*32);self.assertFalse(m.poll());self.assertEqual(len(s),1)
 def test_unavailable_final_verification_preserves_recovery_without_duplicate_close(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);original=m.submit
   def fill(action):
    result=original(action);b['available']=False;return result
   m.submit=fill;self.queue(root,c,'STOP');self.assertFalse(m.poll())
   self.assertIn('stop_verification_position',x.state);self.assertEqual(m.request['phase'],'RECOVERY_REQUIRED')
   b['available']=True;self.queue(root,c,'STOP','d'*32);self.assertTrue(m.poll());self.assertEqual(len(s),1)
 def test_stop_waits_for_fresh_quote_without_reporting_flat(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);m.submit=lambda action:dict(deferred=True)
   self.queue(root,c,'STOP');self.assertFalse(m.poll());self.assertEqual(m.request['phase'],'WAITING_FOR_SOURCE');self.assertIsNotNone(x.state['position']);self.assertTrue(m.blocked);self.assertNotIn('broker_flat_confirmed',m.request)
 def test_detach_then_attach_leaves_broker_open_and_places_no_entry(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);self.queue(root,c,'DETACH');self.assertFalse(m.poll())
   self.assertEqual(m.request['phase'],'DETACHED');self.assertEqual(b['quantity'],1);self.assertIsNone(x.state['position']);self.assertTrue(m.blocked)
   self.queue(root,c,'ATTACH','d'*32,dict(symbol=p['symbol'],quantity=1,product='MARGIN'));m.poll()
   self.assertEqual(m.request['phase'],'ATTACHED');self.assertEqual(x.state['position']['symbol'],p['symbol']);self.assertEqual(b['quantity'],1);self.assertEqual(s,[]);self.assertTrue(m.entry_blocked);self.assertFalse(m.blocked)
 def test_detach_rejects_quantity_change_or_broker_order(self):
  for field,value in [('quantity',2),('orders',True),('available',False)]:
   with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);b[field]=value;self.queue(root,c,'DETACH');m.poll()
    self.assertEqual(m.request['phase'],'REJECTED');self.assertIsNotNone(x.state['position']);self.assertEqual(s,[])
 def test_stop_after_detach_closes_retained_exact_holding(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);self.queue(root,c,'DETACH');m.poll();self.queue(root,c,'STOP','d'*32)
   self.assertTrue(m.poll());self.assertEqual(len(s),1);self.assertEqual(b['quantity'],0)
 def test_duplicate_ids_and_cross_account_session_are_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);first=self.queue(root,c,'DETACH')
   self.assertEqual(self.queue(root,c,'DETACH'),first)
   with self.assertRaisesRegex(ValueError,'different'):self.queue(root,c,'STOP')
   payload=dict(runtime_identity(c,root,'LIVE'),operation='STOP',request_id='d'*32,account_id='e'*32)
   with self.assertRaisesRegex(ValueError,'account'):enqueue(root,c,payload)
 def test_attach_changed_holding_fails_without_new_order_or_releasing_detached_record(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root);self.queue(root,c,'DETACH');m.poll()
   self.queue(root,c,'ATTACH','d'*32,dict(symbol='MCX:OTHER',quantity=1,product='MARGIN'));m.poll()
   self.assertEqual(m.request['phase'],'REJECTED');self.assertIsNotNone(x.state['detached_position']);self.assertEqual(s,[])

class FyersPositionViewTests(unittest.TestCase):
 def test_exact_account_product_signed_quantity_and_pending_order_checks(self):
  import hashlib
  from position_brokers import FyersPositions
  api=Mock();api.get_profile.return_value=dict(s='ok',data=dict(fy_id='account'))
  config=dict(product='MARGIN')
  api.positions.return_value=dict(s='ok',netPositions=[dict(symbol='EXACT',productType='MARGIN',netQty=-2)])
  api.orderbook.return_value=dict(s='ok',orderBook=[])
  view=FyersPositions(api,config,None,hashlib.sha256(b'account').hexdigest());own=dict(symbol='EXACT',quantity=2,side='SHORT')
  self.assertFalse(view.verify(own,flat=False)['flat'])
  with self.assertRaises(ValueError):view.verify(dict(own,side='LONG'),flat=False)
  with self.assertRaises(ValueError):view.verify(own,flat=True)
  api.orderbook.return_value=dict(s='ok',orderBook=[dict(symbol='EXACT',status=6)])
  with self.assertRaises(ValueError):view.verify(own,flat=False)
  api.get_profile.return_value=dict(s='ok',data=dict(fy_id='another'))
  with self.assertRaisesRegex(ValueError,'identity'):view.verify(own,flat=False)
if __name__=='__main__':unittest.main()


class ManualSupersessionTests(unittest.TestCase):
 fixture=PositionControlTests.fixture
 queue=PositionControlTests.queue
 def test_stop_cancels_only_unsubmitted_manual_preparation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c,p,e,x,b,s,m=self.fixture(root)
   inbox=SimpleNamespace(update=Mock())
   m.manual=SimpleNamespace(pending=dict(request_id='f'*32),prepared=True,inbox=inbox)
   self.queue(root,c,'STOP');self.assertTrue(m.poll())
   inbox.update.assert_called_once()
   self.assertIsNone(m.manual.pending)
   self.assertEqual(m.request['phase'],'STOPPED')


class OwnershipAdmissionTests(unittest.TestCase):
 def test_other_strategy_ownership_is_rechecked_before_attachment_without_order(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder:
   base=PositionControlTests();root=Path(folder);c,p,e,x,b,s,m=base.fixture(root)
   base.queue(root,c,'DETACH');m.poll()
   base.queue(root,c,'ATTACH','d'*32,dict(symbol=p['symbol'],quantity=1,product='MARGIN'))
   with patch('ownership.legacy_ownership',return_value=dict(running=False,position=dict(symbol='OTHER'),pending=None)):
    m.poll()
   self.assertEqual(m.request['phase'],'REJECTED');self.assertEqual(s,[]);self.assertEqual(b['quantity'],1)
   self.assertIsNotNone(x.state['detached_position'])
 def test_native_legacy_view_covers_all_account_runtime_families(self):
  from unittest.mock import patch
  from ownership import legacy_ownership
  paths=[Path('/fake/family-one/state.json'),Path('/fake/family-two/state.json')]
  with patch('sector_heatmap.service_restart.runtime_states',return_value=paths),patch('sector_heatmap.restart_state_read.read_runtime_state',side_effect=[dict(running=False,positions=[dict(symbol='OTHER')]),dict(pending=dict(id='pending'))]):
   state=legacy_ownership('a'*32)
  self.assertTrue(state['position']);self.assertTrue(state['pending']);self.assertFalse(state['running'])

class FrozenGeometryControlTests(unittest.TestCase):
 def test_detach_and_reattach_retain_full_precision_geometry_and_entry_cost(self):
  with tempfile.TemporaryDirectory() as folder:
   base=PositionControlTests();root=Path(folder);c,p,e,x,b,s,m=base.fixture(root)
   geometry=dict(spot_brick=7.142857142857143,option_brick=3.5714285714285716,fill_price=390)
   p.update(geometry);x.state['position'].update(geometry)
   base.queue(root,c,'DETACH');m.poll()
   self.assertEqual({k:x.state['detached_position'][k] for k in geometry},geometry)
   base.queue(root,c,'ATTACH','d'*32,dict(symbol=p['symbol'],quantity=1,product='MARGIN'));m.poll()
   self.assertEqual({k:x.state['position'][k] for k in geometry},geometry);self.assertEqual(s,[])
