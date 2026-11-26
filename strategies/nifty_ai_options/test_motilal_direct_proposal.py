import unittest
from motilal_direct_proposal import propose
class Proposal(unittest.TestCase):
 def setUp(self):
  self.owner='a'*32;self.meta=dict(symbol='MO:NSE:123',broker='MOTILAL_OSWAL',instrument='EQ',lot_size=1,tick_size=.05)
  self.quote=dict(symbol=self.meta['symbol'],broker='MOTILAL_OSWAL',account=self.owner,bid=99.95,ask=100.05,exchange_at=100)
 def call(self,side='BUY',meta=None,quote=None,quantity=1):
  return propose(meta or self.meta,quote or self.quote,side=side,quantity=quantity,account=self.owner,now=101)
 def test_buy_sell_limits_are_capped_and_proposal_never_enables_execution(self):
  self.assertEqual(self.call()['limit_price'],100.10);self.assertEqual(self.call('SELL')['limit_price'],99.90)
  self.assertFalse(self.call()['enabled']);self.assertTrue(self.call()['approval_required']);self.assertEqual(self.call()['orders_submitted'],0)
 def test_quantization_stays_inside_original_one_tick_cap(self):
  self.assertLessEqual(self.call(quote=dict(self.quote,ask=100.02))['limit_price'],100.07)
  self.assertGreaterEqual(self.call('SELL',quote=dict(self.quote,bid=99.98))['limit_price'],99.93)
 def test_stale_wrong_contract_or_wrong_account_is_rejected(self):
  for changes in [dict(exchange_at=90),dict(exchange_at=102),dict(account='b'*32),dict(symbol='MO:NSE:999'),dict(broker='FYERS')]:
   with self.assertRaises(ValueError):self.call(quote=dict(self.quote,**changes))
 def test_only_orderable_direct_whole_lots_are_proposed(self):
  for changes in [dict(instrument='UNKNOWN'),dict(instrument='FUTSTK'),dict(instrument='INDEX'),dict(option_type='CE'),dict(suspended=True),dict(lot_size=25)]:
   with self.assertRaises(ValueError):self.call(meta=dict(self.meta,**changes))
