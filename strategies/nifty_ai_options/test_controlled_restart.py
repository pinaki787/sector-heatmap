import unittest,tempfile,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from .controlled_restart import verify,digest,accepts
class ControlledRestartTests(unittest.TestCase):
 def setup_case(self,d,position=None,quantity=0):
  state=dict(position=position,pending=None,management_mode='MANAGED')
  root=Path(d);p=root/'ledger.json';p.write_text(json.dumps(state))
  cfg=dict(account='owner',underlying='BTCUSD')
  proof=dict(user_approved=True,operation='SUPPORT_RETEST_DEPLOY',account='owner',underlying='BTCUSD',run_id=root.name,authorized_at=100,state_sha256=digest(state))
  (root/'restart-authorization.json').write_text(json.dumps(proof))
  delta=SimpleNamespace(product=lambda s:dict(id=27),_position=lambda p:quantity,ticker=lambda s:dict(bid=99,ask=100,exchange_at=100))
  return root,p,cfg,state,delta
 def test_flat_verified_once(self):
  with tempfile.TemporaryDirectory() as d:
   r,p,c,s,delta=self.setup_case(d)
   with patch('strategies.renko_supertrend.delta_execution.Execution') as E:
    E.return_value.active_orders.return_value=[]
    proof=verify(delta,c,r,p,clock=lambda:100)
    self.assertTrue(accepts(proof,s,'owner',100));self.assertFalse((r/'restart-authorization.json').exists())
    with self.assertRaises(FileNotFoundError):verify(delta,c,r,p,clock=lambda:100)
 def test_exact_owned_short_can_resume_without_adopting(self):
  with tempfile.TemporaryDirectory() as d:
   owned=dict(symbol='BTCUSD',product_id=27,side='SHORT',quantity=20,order_id='123',fill_price=99)
   r,p,c,s,delta=self.setup_case(d,owned,-20)
   with patch('strategies.renko_supertrend.delta_execution.Execution') as E:
    E.return_value.active_orders.return_value=[];proof=verify(delta,c,r,p,clock=lambda:100)
    self.assertEqual(proof['position'],owned)
 def test_unmanaged_or_changed_exposure_rejected(self):
  for owned,q in [(None,20),(dict(symbol='BTCUSD',product_id=27,side='SHORT',quantity=20,order_id='123'),-19)]:
   with tempfile.TemporaryDirectory() as d:
    r,p,c,s,delta=self.setup_case(d,owned,q)
    with patch('strategies.renko_supertrend.delta_execution.Execution') as E:
     E.return_value.active_orders.return_value=[]
     with self.assertRaises(ValueError):verify(delta,c,r,p,clock=lambda:100)
 def test_pending_broker_orders_fail_without_consuming_proof(self):
  with tempfile.TemporaryDirectory() as d:
   r,p,c,s,delta=self.setup_case(d)
   with patch('strategies.renko_supertrend.delta_execution.Execution') as E:
    E.return_value.active_orders.return_value=[dict(product_id=27)]
    with self.assertRaises(ValueError):verify(delta,c,r,p,clock=lambda:100)
    self.assertTrue((r/'restart-authorization.json').exists())
 def test_failed_authentication_never_implies_flat(self):
  with tempfile.TemporaryDirectory() as d:
   r,p,c,s,delta=self.setup_case(d)
   with patch('strategies.renko_supertrend.delta_execution.Execution') as E:
    E.return_value.authenticate.side_effect=ValueError('Auth')
    with self.assertRaises(ValueError):verify(delta,c,r,p,clock=lambda:100)
 def test_expired_and_other_owner_and_mutated_ledger_fail(self):
  state=dict(position=None,pending=None)
  proof=dict(account='owner',at=100,state_sha256=digest(state))
  self.assertFalse(accepts(proof,state,'other',100));self.assertFalse(accepts(proof,state,'owner',131))
  self.assertFalse(accepts(proof,dict(state,pending=dict(id=1)),'owner',100))
if __name__=='__main__':unittest.main()
