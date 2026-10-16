import unittest
from strategies.renko_supertrend.test_costs import CostModelTests
from strategies.renko_supertrend.history import trade_history
from strategies.renko_supertrend.dhan_costs import fee
from strategies.renko_supertrend.costs import ledger_costs
from strategies.renko_supertrend.sideways import freeze
class Tests(unittest.TestCase):
 def order(self,side,qty,price,tag):
  r=CostModelTests().order(side,qty,price,tag)
  r.update(broker='DHAN',symbol='NSE_FNO:123',dhan_exchange_rate=.000355299)
  return r
 def test_fees(self):
  b=fee(100000,'BUY',.000355299);s=fee(100000,'SELL',.000355299)
  self.assertEqual(b['brokerage'],20);self.assertEqual(b['exchange'],35.53)
  self.assertEqual(b['stamp'],3);self.assertEqual(s['stt'],150)
 def test_partial_fill_and_exit(self):
  orders=[self.order('BUY',13,10,'B'),self.order('SELL',5,11,'S')]
  c=trade_history(orders,dict(lifecycle_id='OWNED'),16,dict(bid=12))[0]['costs']
  self.assertTrue(c['available']);self.assertEqual(c['incurred']['brokerage'],40)
  self.assertEqual(c['estimated_exit_costs']['brokerage'],20)
  self.assertAlmostEqual(c['entry_costs_allocated_realized']+c['entry_costs_remaining'],c['entry_costs_incurred'],2)
  self.assertEqual(len(ledger_costs([orders[0],orders[0]])),1)
 def test_small_gross_win_is_net_loss(self):
  t=trade_history([self.order('BUY',40,10,'B'),self.order('SELL',40,10.1,'S')])[0]
  self.assertGreater(t['realized_pnl'],0);self.assertLess(t['costs']['realized_net'],0)
 def test_missing_rate_unavailable(self):
  r=self.order('BUY',40,10,'B');r.pop('dhan_exchange_rate')
  self.assertFalse(trade_history([r])[0]['costs']['available'])
