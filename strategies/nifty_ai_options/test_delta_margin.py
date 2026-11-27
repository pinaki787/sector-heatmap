import unittest
from decimal import Decimal
from unittest.mock import Mock
from strategies.nifty_ai_options.delta_margin import requirement
class MarginTests(unittest.TestCase):
 def setUp(self):
  self.d=Mock();self.d.clock.return_value=100;self.d._private.return_value={'result':{'product_id':123,'leverage':'100'}}
  self.p=dict(id=123,symbol='PAXGUSD',contract_type='perpetual_futures',quoting_currency='USD',settlement_currency='USD',contract_value='.001',initial_margin='1',max_leverage_notional='50000',initial_margin_scaling_factor='.00001',position_size_limit=200000,position_notional_limit='1250000',taker_commission_rate='.0001')
  self.q=dict(symbol='PAXGUSD',bid=3649,ask=3650,exchange_at=100)
 def test_100_contracts_100x_margin_not_full_notional(self):
  r=requirement(self.d,self.p,100,self.q)
  self.assertEqual(Decimal(r['initial_margin']),Decimal('3.65'))
  self.assertEqual(Decimal(r['required']),Decimal('7.386140'))
  self.d._private.assert_called_once_with('GET','/v2/products/123/orders/leverage')
 def test_configured_lower_leverage_is_used(self):
  self.d._private.return_value['result']['leverage']='10'
  self.assertEqual(Decimal(requirement(self.d,self.p,100,self.q)['initial_margin']),Decimal('36.5'))
 def test_size_tier_limits_maximum(self):
  self.p['max_leverage_notional']='100';r=requirement(self.d,self.p,100,self.q)
  self.assertGreater(Decimal(r['initial_margin']),Decimal('3.65'));self.assertLess(Decimal(r['max_tier_leverage']),100)
 def test_missing_foreign_or_invalid_leverage_blocks(self):
  for row in ({},{'product_id':999,'leverage':'100'},{'product_id':123,'leverage':'NaN'}):
   self.d._private.return_value={'result':row}
   with self.assertRaises(ValueError):requirement(self.d,self.p,100,self.q)
 def test_stale_quote_and_missing_tier_block(self):
  self.q['exchange_at']=1
  with self.assertRaises(ValueError):requirement(self.d,self.p,100,self.q)
  self.q['exchange_at']=100;self.p.pop('max_leverage_notional')
  with self.assertRaises(ValueError):requirement(self.d,self.p,100,self.q)
