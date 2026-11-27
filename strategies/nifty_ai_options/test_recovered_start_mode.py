import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from strategies.nifty_ai_options.position_control import PositionManager
from strategies.nifty_ai_options.position_brokers import DeltaPositions

class RecoveredStart(unittest.TestCase):
 def fixture(self):
  config=dict(account='a'*32,broker='DELTA_INDIA',execution_mode='LIVE',execution_route='DIRECT',underlying='PAXGUSD',timeframe=1,runtime_session='b'*32)
  state=dict(position=None,pending=None,management_mode='RECOVERY_REQUIRED',seen=['old-intent'],reconciled_intents=[dict(phase='RECOVERED_CLOSED',historical_pair_closed=True,account_id='a'*32,proof='evidence')])
  executor=SimpleNamespace(state=state,management_only=False,save=Mock())
  engine=SimpleNamespace(position=None,pending_direction=('LONG',10),entry_confirmation=Mock())
  verify=Mock(return_value=dict(flat=True,quantity=0))
  return config,executor,engine,verify
 def manager(self,directory,config,executor,engine,verify):
  return PositionManager(config,directory,engine,executor,verify=verify,attach=Mock(),submit=Mock(),clock=lambda:100)
 def test_new_user_start_rearms_only_verified_closed_recovery_in_memory(self):
  c,x,e,v=self.fixture()
  with tempfile.TemporaryDirectory() as d:m=self.manager(d,c,x,e,v)
  self.assertEqual(m.mode,'MANAGED');self.assertFalse(m.entry_blocked);self.assertFalse(m.blocked)
  self.assertEqual(x.state['management_mode'],'MANAGED');self.assertEqual(x.state['seen'],['old-intent'])
  self.assertIsNone(e.pending_direction);e.entry_confirmation.clear.assert_called_once()
  v.assert_called_once_with(None,flat=True)
  self.assertEqual(x.state['management_audit'][-1]['orders_submitted'],0)
 def test_retained_or_unverified_recovery_never_rearms(self):
  for key,value in [('position',dict(quantity=10)),('pending',dict(key='unresolved')),('detached_position',dict(quantity=10)),('stop_verification_position',dict(quantity=10)),('reconciled_intents',[])]:
   c,x,e,v=self.fixture();x.state[key]=value
   with tempfile.TemporaryDirectory() as d:m=self.manager(d,c,x,e,v)
   self.assertTrue(m.entry_blocked);self.assertEqual(m.mode,'RECOVERY_REQUIRED');v.assert_not_called()
 def test_management_only_or_attachment_never_arms_new_entries(self):
  for attach in (False,True):
   c,x,e,v=self.fixture()
   if attach:c['_managed_resume']=True
   else:x.management_only=True
   with tempfile.TemporaryDirectory() as d:m=self.manager(d,c,x,e,v)
   self.assertTrue(m.entry_blocked);v.assert_not_called()
 def test_broker_rejection_leaves_recovery_mode_and_signal_untouched(self):
  c,x,e,v=self.fixture();v.side_effect=ValueError('Broker not flat')
  with tempfile.TemporaryDirectory() as d,self.assertRaisesRegex(ValueError,'Broker not flat'):self.manager(d,c,x,e,v)
  self.assertEqual(x.state['management_mode'],'RECOVERY_REQUIRED');x.save.assert_not_called()

class SelectedBrokerFlat(unittest.TestCase):
 def test_empty_owned_slot_is_not_accepted_as_broker_flat(self):
  for quantity,orders in [(50,[]),(0,[dict(product_id=123006)])]:
   delta=Mock();delta.product.return_value=dict(id=123006);delta._position.return_value=quantity
   native=Mock();native.active_orders.return_value=orders
   view=DeltaPositions(delta,dict(underlying='PAXGUSD',execution_route='DIRECT'),native)
   with self.assertRaises(ValueError):view.verify(None,flat=True)
   delta.submit.assert_not_called()
 def test_exact_selected_contract_is_verified_without_orders(self):
  delta=Mock();delta.product.return_value=dict(id=123006);delta._position.return_value=0
  native=Mock();native.active_orders.return_value=[]
  view=DeltaPositions(delta,dict(underlying='PAXGUSD',execution_route='DIRECT'),native)
  self.assertTrue(view.verify(None,flat=True)['flat'])
  native.authenticate.assert_called_once();delta._position.assert_called_once_with(123006)
  delta.submit.assert_not_called()
