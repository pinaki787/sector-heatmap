import unittest
from .delta_costs import order_cost, trade_costs
from .costs import ledger_costs
from .sideways import freeze


class NativeCostsTests(unittest.TestCase):
    def row(self,side='BUY',price=10):
        return dict(tag=side,broker='DELTA_INDIA',filled=10,average_price=price,
                    quantity_multiplier=.001,quote_currency='USD',side=side,
                    native_fee_policy=dict(taker_rate='0.0001',index_price=90000))
    def test_current_premium_cap_and_gst(self):
        cost=order_cost(self.row())
        self.assertAlmostEqual(cost['commission'],.0035)
        self.assertAlmostEqual(cost['total'],.00413)
        self.assertEqual(cost['currency'],'USD')
    def test_recorded_commission_has_precedence_over_estimate(self):
        cost=order_cost({**self.row(),'native_commission':'0.001'})
        self.assertAlmostEqual(cost['total'],.00118)
    def test_missing_fee_evidence_is_not_free_or_fyers_costs(self):
        row=self.row();row.pop('native_fee_policy')
        self.assertIsNone(order_cost(row));self.assertIsNone(ledger_costs([row])['BUY'])
    def test_closed_native_after_cost_loss_can_freeze_exact_exposure_range(self):
        rows=[self.row(),self.row('SELL',11)]
        trade=dict(orders=rows,entry_filled=10,exit_filled=10,remaining_quantity=0,realized_pnl=.001,quantity_multiplier=.001)
        costs=trade_costs(trade,ledger_costs(rows))
        self.assertLess(costs['realized_net'],0)
        lock=freeze(dict(entry_at=100,high=110,low=100),120,costs['realized_net'],60,dict(sideways_enabled=True,sideways_max_candles=3),'trade','BTCUSD')
        self.assertEqual((lock['high'],lock['low']),(110,100))
    def test_nonfinite_and_negative_commissions_fail_closed(self):
        for value in ['NaN','-1',True]:self.assertIsNone(order_cost({**self.row(),'native_commission':value}))
