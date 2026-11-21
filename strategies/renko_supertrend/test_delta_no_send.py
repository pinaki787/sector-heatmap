from pathlib import Path
from types import SimpleNamespace
import tempfile,threading,unittest
from copy import deepcopy
from unittest.mock import Mock
from .delta_no_send import record,recover,verify,receipt_path
from .delta_broker import Broker
from .delta_runner import DeltaRunner

class NoSendTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  self.order=dict(symbol='C-ETH',qty=20,side=1,productType='DELTA_LONG_OPTION',orderTag='EC1234567890')
  self.delta=SimpleNamespace(live_path=Path(tmp.name)/'delta-live.json',live={'orders':{}},lock=threading.RLock(),_private=Mock(side_effect=ValueError('Delta India order_not_found (HTTP 400).')),_position=Mock(return_value=0))
  self.adapter=SimpleNamespace(delta=self.delta,execution=SimpleNamespace(account_identity='account',active_orders=Mock(return_value=[])),authenticated_client=Mock())
  self.r=SimpleNamespace(adapter=self.adapter,state=dict(config={'mode':'LIVE'},account_identity='account',position=None,pending=dict(id=None,tag=self.order['orderTag'],order=self.order,position={'product_id':123}),squareoff_requested=True,running=True,accepting_entries=False,run_id='run'),is_entry_order=lambda a,b:True,record_order=Mock(),event=Mock(),stop=Mock(),save=Mock(),clock=lambda:100)
 def receipt(self):return record(self.delta,self.order,'account')
 def test_receipt_and_fresh_absence_finish_requested_stop_without_orders(self):
  self.receipt();self.assertTrue(recover(self.r));self.assertIsNone(self.r.state['pending']);self.r.stop.assert_called_once();self.r.record_order.assert_called_once();self.assertFalse(self.r.state['accepting_entries'])
  self.assertEqual(self.delta._private.call_args.args[0],'GET')
 def test_legacy_unknown_without_receipt_is_not_auto_cleared(self):
  before=deepcopy(self.r.state);self.assertFalse(recover(self.r));self.assertEqual(self.r.state,before);self.delta._private.assert_not_called()
 def test_durable_native_intent_never_gets_no_send_receipt(self):
  self.delta.live['orders'][self.order['orderTag']]={'status':'UNKNOWN'}
  with self.assertRaises(ValueError):self.receipt()
 def test_native_intent_appearing_after_receipt_blocks_recovery(self):
  self.receipt();self.delta.live['orders'][self.order['orderTag']]={'status':'SUBMITTING'}
  with self.assertRaises(ValueError):recover(self.r)
  self.assertIsNotNone(self.r.state['pending'])
 def test_broker_order_fill_or_timeout_does_not_clear_pending(self):
  self.receipt()
  for error in [ConnectionError('timeout'),ValueError('Delta India request_rejected (HTTP 500).')]:
   self.delta._private.side_effect=error
   with self.assertRaises(type(error)):recover(self.r)
   self.assertIsNotNone(self.r.state['pending'])
  self.delta._private.side_effect=None;self.delta._private.return_value={'result':{'id':1}}
  with self.assertRaises(ValueError):recover(self.r)
 def test_position_or_active_order_blocks_recovery(self):
  self.receipt();self.delta._position.return_value=1
  with self.assertRaises(ValueError):recover(self.r)
  self.delta._position.return_value=0;self.adapter.execution.active_orders.return_value=[{'product_id':123}]
  with self.assertRaises(ValueError):recover(self.r)
 def test_account_and_order_identity_are_strict(self):
  self.receipt();self.r.state['account_identity']='another'
  with self.assertRaises(ValueError):recover(self.r)
  self.r.state['account_identity']='account';self.order['qty']=21
  with self.assertRaises(ValueError):recover(self.r)
 def test_no_stop_request_leaves_trading_unarmed_for_review(self):
  self.receipt();self.r.state['squareoff_requested']=False
  self.assertTrue(recover(self.r));self.assertFalse(self.r.state['running']);self.assertFalse(self.r.state['accepting_entries']);self.assertEqual(self.r.state['status'],'RECOVERY_REQUIRED');self.r.stop.assert_not_called()

 def test_startup_no_send_stop_recovers_without_rearming(self):
  self.receipt();self.r.state['running']=False;self.r.lock=threading.RLock()
  worker=DeltaRunner.recover_unsubmitted_intent(self.r);worker.join(3)
  self.assertFalse(worker.is_alive());self.assertIsNone(self.r.state['pending']);self.r.stop.assert_called_once()
 def test_startup_unknown_without_receipt_keeps_intent(self):
  self.r.state['running']=False;self.r.lock=threading.RLock()
  self.assertIsNone(DeltaRunner.recover_unsubmitted_intent(self.r));self.assertIsNotNone(self.r.state['pending'])

 def test_actual_submission_boundary_persists_receipt_before_rejecting(self):
  broker=Broker.__new__(Broker);broker.delta=self.delta;broker.execution=self.adapter.execution
  broker._place=Mock(side_effect=ValueError('Preflight failed before native submission'))
  response=broker.place(self.order)
  self.assertEqual(response['code'],400)
  self.assertTrue(receipt_path(self.delta,self.order['orderTag']).exists())
  self.assertTrue(recover(self.r));self.assertIsNone(self.r.state['pending'])

if __name__=='__main__':unittest.main()
