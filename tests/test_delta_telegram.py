import unittest
from tests import test_delta_india as fixture
class Tests(unittest.TestCase):
 def setUp(self):fixture.LiveTests.setUp(self)
 def ticket(self):return dict(mode='LIVE',symbol='BTCUSD',side='buy',contracts=1,order_type='limit_order',limit_price='102',time_in_force='gtc',reduce_only=False,request_id='telegram-test-123',strategy='TELEGRAM_DISCRETIONARY',telegram_stop_price='101.5')
 def test_native_stop_limit_without_strategy_adoption(self):
  p,body,q=self.b._validate_order(self.ticket(),runner=True)
  self.assertEqual(body['stop_price'],'101.5');self.assertEqual(body['stop_order_type'],'stop_loss_order');self.assertEqual(body['stop_trigger_method'],'last_traded_price');self.assertNotIn('_managed_submit',self.ticket());self.assertFalse(self.b.runner['running'])
 def test_invalid_tick_or_already_crossed_trigger_blocks(self):
  for trigger in ['101.25','100','NaN']:
   with self.assertRaises(ValueError):self.b._validate_order(self.ticket()|dict(telegram_stop_price=trigger),runner=True)
  self.assertEqual(self.req.posts,0)
 def test_held_strategy_blocks_without_mutation(self):
  self.b.paper['position']={'symbol':'TEST','contracts':10}
  with self.assertRaisesRegex(ValueError,'held'):self.b.submit_discretionary(self.ticket())
  self.assertEqual(self.b.paper['position'],{'symbol':'TEST','contracts':10});self.assertEqual(self.req.posts,0)
