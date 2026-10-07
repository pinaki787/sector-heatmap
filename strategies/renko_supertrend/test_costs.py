import unittest
from .costs import fee,ledger_costs,trade_costs,settings
from .history import trade_history
from .sideways import freeze

class CostModelTests(unittest.TestCase):
    def order(self,side,qty,price,tag):
        return dict(tag=tag,lifecycle_id='OWNED',symbol='BSE:SENSEX26O0872700CE',mode='PAPER',side=side,requested=qty,filled=qty,remaining=0,average_price=price,quantity_multiplier=1,lot_size=20,filled_at=1791264000+(side=='SELL')*60,first_fill_confirmed_at=1791264000+(side=='SELL')*60,submitted_at=1791264000+(side=='SELL')*60,reason='TEST',indicator_snapshot={'settings':{'additional_slippage_points':0}})
    def test_buy_sell_asymmetry_and_user_brokerage(self):
        buy=fee(100000,'BUY');sell=fee(100000,'SELL')
        self.assertEqual(buy['brokerage'],15);self.assertEqual(sell['brokerage'],15)
        self.assertEqual(buy['stt'],0);self.assertEqual(sell['stamp'],0)
        self.assertEqual(sell['stt'],150);self.assertEqual(buy['stamp'],3)
        self.assertEqual(buy['gst'],8.57);self.assertEqual(buy['total'],59.17)
    def test_closed_gross_net_and_no_double_slippage(self):
        orders=[self.order('BUY',40,10,'B'),self.order('SELL',40,11,'S')]
        t=trade_history(orders)[0];c=t['costs']
        self.assertEqual(t['realized_pnl'],40)
        self.assertEqual(c['incurred']['brokerage'],30)
        self.assertEqual(c['realized_additional_slippage'],0)
        self.assertAlmostEqual(c['realized_net'],40-c['incurred']['total'],2)
        self.assertIn('Embedded',c['actual_slippage'])
    def test_partial_fill_one_order_fee_and_partial_exit_allocation(self):
        orders=[self.order('BUY',13,10,'B'),self.order('SELL',5,11,'S')]
        p=dict(lifecycle_id='OWNED')
        t=trade_history(orders,p,16,dict(bid=12,exchange_at=1791264100))[0];c=t['costs']
        self.assertEqual(c['incurred']['brokerage'],30)
        self.assertAlmostEqual(c['entry_costs_allocated_realized']+c['entry_costs_remaining'],c['entry_costs_incurred'],2)
        self.assertEqual(c['estimated_exit_costs']['brokerage'],15)
        self.assertLess(c['unrealized_net'],16)
        self.assertEqual(len(ledger_costs([orders[0],orders[0]])),1)
    def test_open_costs_and_stale_mark_net_unavailable(self):
        orders=[self.order('BUY',40,10,'B')]
        p=dict(lifecycle_id='OWNED')
        c=trade_history(orders,p,40,dict(bid=11))[0]['costs']
        self.assertEqual(c['realized_net'],0)
        self.assertEqual(c['incurred']['brokerage'],15)
        self.assertEqual(c['estimated_exit_costs']['brokerage'],15)
        self.assertLess(c['unrealized_net'],40)
        self.assertIsNone(trade_history(orders,p,None,None)[0]['costs']['unrealized_net'])
    def test_unknown_contract_rates_and_invalid_model_are_unavailable(self):
        row=self.order('BUY',40,10,'B');row['symbol']='MCX:UNKNOWNCE'
        self.assertFalse(trade_history([row])[0]['costs']['available'])
        for n in [True,-1,float('nan')]:
            with self.assertRaises(ValueError):settings(dict(additional_slippage_points=n))
    def test_configured_extra_points_separate_from_fills_and_net_loss_range(self):
        orders=[self.order('BUY',40,10,'B'),self.order('SELL',40,10.1,'S')]
        t=trade_history(orders)[0]
        self.assertGreater(t['realized_pnl'],0);self.assertLess(t['costs']['realized_net'],0)
        exposure=dict(entry_at=1791264000,high=72750,low=72700)
        lock=freeze(exposure,1791264060,t['costs']['realized_net'],60,dict(sideways_enabled=True),'T','BSE:SENSEX-INDEX')
        self.assertIsNotNone(lock)
        orders[0]['indicator_snapshot']['settings']['additional_slippage_points']=1
        changed=trade_history(orders)[0]['costs']
        self.assertEqual(changed['realized_additional_slippage'],80)
        self.assertAlmostEqual(t['costs']['realized_net']-changed['realized_net'],80)
    def test_day_rounding_is_cumulative_not_per_fill(self):
        rows=[self.order('SELL',40,10,'S1'),self.order('SELL',40,10,'S2')]
        c=ledger_costs(rows)
        self.assertEqual(c['S1']['stt']+c['S2']['stt'],1)
