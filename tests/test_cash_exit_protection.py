import unittest
from sector_heatmap.premium_exit_mapping import cash_exits

class CashProtectionTests(unittest.TestCase):
    def test_long_rounds_stop_towards_entry_and_target_towards_entry(self):
        p=cash_exits(entry=100,stop=95.01,target=110.04,action='BUY',tick=.05)
        self.assertEqual((p['stop_loss_price'],p['target_price']),(95.05,110))
    def test_short_rounds_without_widening_stop(self):
        p=cash_exits(entry=100,stop=104.99,target=90.01,action='SELL',tick=.05)
        self.assertEqual((p['stop_loss_price'],p['target_price']),(104.95,90.05))
    def test_collapsed_wrong_side_and_nonfinite_fail(self):
        for stop,target in [(99.99,110),(105,110),(95,90),(float('nan'),110),(95,None)]:
            with self.subTest(stop=stop,target=target),self.assertRaises(ValueError):
                cash_exits(entry=100,stop=stop,target=target,action='BUY',tick=.05)
