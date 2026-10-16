"""Holding-product routing and recovery without network or orders."""
import unittest
from unittest.mock import patch
from .runner import Broker, BaseBroker, Runner


class HoldingProductTests(unittest.TestCase):
    symbol = 'MCX:TESTCE'

    def broker(self):
        b = Broker.__new__(Broker)
        b.contract = lambda s: dict(symbol=s,lot_size=10,tick_size=.05)
        return b

    def resolve(self,b,holding):
        with patch.object(BaseBroker,'resolve',return_value=dict(symbol=self.symbol,lot_size=10,tick_size=.05)):
            if holding == 'CARRY_FORWARD':
                b.session_policy=lambda c: dict(master_regular_session='0900-2330')
                with patch('strategies.renko_supertrend.runner.commodity_expiry_exit_at',return_value=9999999999):
                    return b.resolve(dict(commodity_holding=holding),'BULLISH')
            return b.resolve(dict(commodity_holding=holding),'BULLISH')

    def test_intraday_entry_exit_and_reconciliation(self):
        b=self.broker();self.resolve(b,'INTRADAY')
        for side in (1,-1):
            order=b.order(self.symbol,10,side,{})
            self.assertEqual(order['productType'],'INTRADAY')
            b.validate_order(order)
        b.positions=lambda:[dict(symbol=self.symbol,netQty=10,productType='INTRADAY')]
        b.reconcile_position(self.symbol,10)
        b.positions=lambda:[dict(symbol=self.symbol,netQty=10,productType='MARGIN')]
        with self.assertRaisesRegex(ValueError,'product'):b.reconcile_position(self.symbol,10)
        with self.assertRaisesRegex(ValueError,'product'):
            b.validate_order({**order,'productType':'MARGIN'})

    def test_carry_forward_remains_margin(self):
        b=self.broker();self.resolve(b,'CARRY_FORWARD')
        order=b.order(self.symbol,10,1,{})
        self.assertEqual(order['productType'],'MARGIN');b.validate_order(order)

    def test_legacy_position_defaults_to_margin(self):
        b=self.broker()
        self.assertEqual(b.order(self.symbol,10,-1,{})['productType'],'MARGIN')

    def test_intraday_still_enforces_lots_and_market_terms(self):
        b=self.broker();self.resolve(b,'INTRADAY')
        order=b.order(self.symbol,10,1,{})
        for change in (dict(qty=11),dict(type=1),dict(limitPrice=1),dict(offlineOrder=True)):
            with self.assertRaises(ValueError):b.validate_order({**order,**change})

    def test_recovery_uses_saved_product_and_legacy_fallback(self):
        r=Runner.__new__(Runner);r.adapter=self.broker()
        for saved,expected in (({},'MARGIN'),({'broker_product':'INTRADAY'},'INTRADAY'),({'broker_product':'MARGIN'},'MARGIN')):
            r.state=dict(config=dict(commodity_holding='INTRADAY'),position=dict(symbol=self.symbol,**saved))
            r.restore_holding_product()
            self.assertEqual(r.adapter.order(self.symbol,10,-1,{})['productType'],expected)
        r.state=dict(pending=dict(position=dict(symbol=self.symbol),order=dict(productType='INTRADAY')))
        r.restore_holding_product()
        self.assertEqual(r.adapter.option_products[self.symbol],'INTRADAY')
