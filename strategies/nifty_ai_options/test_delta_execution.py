import unittest,tempfile
from unittest.mock import Mock,patch
from contextlib import nullcontext
from delta_execution import DeltaExecution
PRODUCT=dict(id=27,symbol='BTCUSD',contract_type='perpetual_futures',state='live',trading_status='operational',notional_type='vanilla',is_quanto=False,underlying='BTC',contract_unit_currency='BTC',quoting_currency='USD',settlement_currency='USD',contract_value='0.001',tick_size='0.5',initial_margin='0.5',maintenance_margin='0.25',taker_commission_rate='0.0005',product_specs={'only_reduce_only_orders_allowed':False})
class DeltaExecutionTests(unittest.TestCase):
    def position(self,side):return dict(symbol='BTCUSD',underlying='BTCUSD',side=side,entry_timestamp=100,execution_route='DIRECT',spot_brick=100)
    def quote(self):return dict(symbol='BTCUSD',bid=100,ask=101,exchange_at=100,received_at=100)
    def test_paper_long_and_short_never_invoke_native_orders(self):
        for side in ['LONG','SHORT']:
            with tempfile.TemporaryDirectory() as directory:
                delta=Mock();delta.clock.return_value=100;delta.product.return_value=PRODUCT;native=Mock()
                e=DeltaExecution(delta,'owner',directory,contracts=2,native=native)
                e.submit(dict(action='OPEN_'+side,timestamp=100,position=self.position(side)),self.quote())
                self.assertEqual(e.state['position']['fill_price'],101 if side=='LONG' else 100)
                e.submit(dict(action='CLOSE_'+side,timestamp=101,position=self.position(side)),self.quote())
                self.assertIsNone(e.state['position']);native.submit.assert_not_called();e.close()
    def test_fake_live_short_and_cover_keep_reduce_only_and_signed_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            delta=Mock();delta.clock.return_value=100;delta.product.return_value=PRODUCT;delta._position.return_value=-2
            native=Mock();native.reconcile.side_effect=[dict(status=2,filledQty=2,id='a',tradedPrice=100),dict(status=2,filledQty=2,id='b',tradedPrice=90)]
            e=DeltaExecution(delta,'a'*32,directory,contracts=2,native=native,live=True)
            with patch('sector_heatmap.chart_trade_admission.entry_lock',return_value=nullcontext()),patch('sector_heatmap.chart_trade_admission.mark_entry_attempt'),patch('sector_heatmap.chart_trade_ownership.assert_no_chart_entry_conflict'):
                e.submit(dict(action='OPEN_SHORT',timestamp=100,position=self.position('SHORT')),self.quote())
                e.submit(dict(action='CLOSE_SHORT',timestamp=101,position=self.position('SHORT')),self.quote())
            calls=native.submit.call_args_list;self.assertEqual([c.args[2] for c in calls],[-1,1]);self.assertEqual([c.kwargs['reduce_only'] for c in calls],[False,True]);self.assertIsNone(e.state['position']);e.close()
    def test_partial_or_unknown_result_keeps_pending_and_blocks_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            delta=Mock();delta.clock.return_value=100;delta.product.return_value=PRODUCT;native=Mock();native.reconcile.return_value=dict(status=1,filledQty=1)
            e=DeltaExecution(delta,'a'*32,directory,contracts=2,native=native,live=True)
            with patch('sector_heatmap.chart_trade_admission.entry_lock',return_value=nullcontext()),patch('sector_heatmap.chart_trade_admission.mark_entry_attempt'),patch('sector_heatmap.chart_trade_ownership.assert_no_chart_entry_conflict'),self.assertRaises(RuntimeError):e.submit(dict(action='OPEN_LONG',timestamp=100,position=self.position('LONG')),self.quote())
            self.assertEqual(e.state['pending']['stage'],'UNRESOLVED_FILL');e.close()
            with self.assertRaises(ValueError):DeltaExecution(delta,'a'*32,directory,contracts=2,native=native,live=True)
