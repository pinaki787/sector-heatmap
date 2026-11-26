import unittest
from unittest.mock import Mock
from strategies.nifty_ai_options.delta_execution import DeltaExecution
class Recovery(unittest.TestCase):
 def executor(self,filled=0,active=None,position=0):
  e=DeltaExecution.__new__(DeltaExecution);e.live=True
  e.state=dict(pending=dict(key='owned',intent=dict(position=dict(product_id=123))),seen=['owned'])
  e.native=Mock();e.native.reconcile.return_value=dict(native_status='cancelled',filledQty=filled,orderTag='owned',product_id=123)
  e.native.active_orders.return_value=active or []
  e.delta=Mock();e.delta._position.return_value=position;e.delta.clock.return_value=100
  e.save=Mock();return e
 def test_terminal_zero_fill_verified_flat_releases_only_pending(self):
  e=self.executor();e.reconcile_pending();self.assertIsNone(e.state['pending']);self.assertEqual(e.state['seen'],['owned']);self.assertEqual(len(e.state['reconciled_intents']),1)
 def test_partial_fill_stays_blocked(self):
  e=self.executor(filled=2);e.reconcile_pending();self.assertIsNotNone(e.state['pending']);e.save.assert_not_called()
 def test_exposure_or_selected_active_order_stays_blocked(self):
  for kwargs in [dict(position=1),dict(active=[dict(product_id=123)])]:
   e=self.executor(**kwargs);e.reconcile_pending();self.assertIsNotNone(e.state['pending'])
if __name__=='__main__':unittest.main()
