import unittest
from strategies.ema_crossover.broker import FyersBroker
class MarketPayloadTests(unittest.TestCase):
 def test_buy_and_sell_market_payload(self):
  b=FyersBroker.__new__(FyersBroker);b.contract=lambda symbol:dict(lot_size=10,tick_size=.05)
  for side in [1,-1]:
   order=b.order('NSE:TESTCE',10,side,dict(bid=10,ask=11));b.validate_order(order)
   self.assertEqual(order['type'],2);self.assertEqual(order['limitPrice'],0)
   self.assertFalse(order['offlineOrder']);self.assertEqual(order['side'],side)
   with self.assertRaises(ValueError):b.validate_order(dict(order,type=1,limitPrice=11))
if __name__=='__main__':unittest.main()
