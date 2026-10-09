import unittest
from unittest.mock import Mock
from sector_heatmap.telegram_options import recommendation_plan,trigger_satisfied,resolve_at_trigger
class OptionPlanTests(unittest.TestCase):
 def plan(self,action='BUY',instruction='STOP_LIMIT'):
  return recommendation_plan(dict(action=action,entry=100,entry_instruction=instruction,stop_loss=90,targets=[110]),'ETHUSD')
 def test_bearish_recommendation_buys_put_not_sells_option(self):
  p=self.plan('SELL');self.assertEqual((p['option_type'],p['side']),('PE','BUY'))
  self.assertEqual((self.plan()['option_type'],self.plan()['side']),('CE','BUY'))
 def test_strict_underlying_trigger_and_limit_conditions(self):
  p=self.plan();self.assertFalse(trigger_satisfied(p,100,1000,1000));self.assertTrue(trigger_satisfied(p,101,1000,1000))
  self.assertTrue(trigger_satisfied(self.plan('SELL'),99,1000,1000));self.assertFalse(trigger_satisfied(self.plan('SELL'),101,1000,1000))
  self.assertTrue(trigger_satisfied(self.plan(instruction='LIMIT'),99,1000,1000))
 def test_untriggered_recommendation_does_not_resolve_or_submit(self):
  d=Mock();r=resolve_at_trigger(d,self.plan(),99,1000,1000)
  self.assertEqual(r['status'],'WAITING_UNDERLYING_TRIGGER');d.chart_option.assert_not_called();d.submit.assert_not_called()
 def test_stale_future_invalid_underlying_cannot_trigger(self):
  for price,stamp in [(101,980),(101,1001),(float('nan'),1000),(True,1000)]:
   with self.assertRaises(ValueError):trigger_satisfied(self.plan(),price,stamp,1000)
 def test_underlying_levels_stay_out_of_option_order_terms(self):
  p=self.plan();self.assertEqual(p['underlying_entry'],100);self.assertNotIn('limit_price',p);self.assertNotIn('stop_price',p);self.assertEqual(p['exit_owner'],'RENKO_SUPERTREND')

 def route(self):
  return dict(signal_symbol='ETHUSD',side='buy',product=dict(id=1,symbol='C-ETH-100',contract_type='call_options',state='live',trading_status='operational',contract_value='.01',tick_size='.1',quoting_currency='USD',settlement_currency='USD',notional_type='vanilla',is_quanto=False,underlying='ETH',contract_unit_currency='ETH',settlement_time='1970-01-01T01:00:00+00:00',strike_price='100'),quote=dict(symbol='C-ETH-100',bid=4,ask=5,exchange_at=1000))
 def test_triggered_preview_resolves_option_ask_without_sizing_or_submission(self):
  d=Mock();d.chart_option.return_value=self.route();r=resolve_at_trigger(d,self.plan(),101,1000,1000)
  self.assertEqual(r['option_quote']['ask'],5);self.assertIsNone(r['quantity']);self.assertFalse(r['submission_enabled']);d.submit.assert_not_called()
 def test_underlying_mismatch_and_wrong_option_side_fail_closed(self):
  for field,value in [('signal_symbol','BTCUSD'),('side','sell')]:
   d=Mock();route=self.route();route[field]=value;d.chart_option.return_value=route
   with self.assertRaises(ValueError):resolve_at_trigger(d,self.plan(),101,1000,1000)
 def test_near_expiry_and_stale_option_quote_fail_closed(self):
  d=Mock();route=self.route();route['product']['settlement_time']='1970-01-01T00:17:00+00:00';d.chart_option.return_value=route
  with self.assertRaises(ValueError):resolve_at_trigger(d,self.plan(),101,1000,1000)
  route=self.route();route['quote']['exchange_at']=980;d.chart_option.return_value=route
  with self.assertRaises(ValueError):resolve_at_trigger(d,self.plan(),101,1000,1000)
