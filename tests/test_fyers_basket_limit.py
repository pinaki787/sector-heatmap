import unittest
from unittest.mock import Mock
from sector_heatmap.fyers_execution import FyersExecutionService
class FyersBasketLimit(unittest.TestCase):
 def test_oversized_preview_blocked_before_any_broker_read_or_submission(self):
  service=FyersExecutionService(client_factory=Mock(side_effect=AssertionError('broker accessed')))
  for n in (11,12,100):
   with self.subTest(n=n),self.assertRaisesRegex(ValueError,'at most 10'):
    service._batch_preflight({'items':[{'underlying':str(i),'proposal':{'kind':'EQUITY'}} for i in range(n)],'allocation_budget':50000})
  service.client_factory.assert_not_called()
 def test_ten_equities_reach_normal_read_only_allocation_validation(self):
  service=FyersExecutionService();service._budget_equity_batch=Mock(return_value='validated')
  self.assertEqual(service._batch_preflight({'items':[{'underlying':str(i),'proposal':{'kind':'EQUITY'}} for i in range(10)],'allocation_budget':50000}),'validated')
 def test_old_oversized_preview_cannot_bypass_submission_limit(self):
  service=FyersExecutionService(client_factory=Mock(side_effect=AssertionError('broker accessed')))
  service._live_submission_enabled=lambda:True
  service.previews['P']={'batch':True,'payload':{'items':[{}]*12}}
  with self.assertRaisesRegex(ValueError,'no orders were sent'):service.submit_batch('P','CONFIRM P')
  service.client_factory.assert_not_called()
