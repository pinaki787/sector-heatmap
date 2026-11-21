import unittest,tempfile
from unittest.mock import Mock
from direct_execution import DirectExecution
class DirectExecutionTests(unittest.TestCase):
    def setup_executor(self,directory,product='MARGIN'):
        api=Mock();master=Mock(return_value=dict(product_type='FUTURE',expiry_epoch=999999,lot_size=10,tick_size=.05))
        return api,master,DirectExecution(api,'account',directory,lots=2,product=product,master=master)
    def position(self,side):return dict(symbol='MCX:GOLD-FUT',underlying='MCX:GOLD-FUT',execution_route='DIRECT',side=side,entry_timestamp=100,spot_brick=1)
    def test_paper_long_and_short_fills_never_send_real_orders(self):
        for direction in ['LONG','SHORT']:
            with tempfile.TemporaryDirectory() as folder:
                api,master,executor=self.setup_executor(folder)
                p=self.position(direction)
                opened=executor.submit(dict(action='OPEN_'+direction,timestamp=100,position=p),dict(timestamp=100,ltp=100),now=100)
                self.assertEqual(opened['payload']['side'],1 if direction=='LONG' else -1)
                self.assertEqual(executor.state['position']['quantity'],20)
                closed=executor.submit(dict(action='CLOSE_'+direction,timestamp=101,position=p),dict(timestamp=101,ltp=105),now=101)
                self.assertEqual(closed['payload']['side'],-1 if direction=='LONG' else 1)
                self.assertIsNone(executor.state['position']);api.place_order.assert_not_called();executor.close()
    def test_no_unowned_exit_or_expired_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            api,master,e=self.setup_executor(folder)
            with self.assertRaises(ValueError):e.submit(dict(action='CLOSE_LONG',timestamp=100,position=self.position('LONG')),dict(timestamp=100,ltp=100),now=100)
            master.return_value['expiry_epoch']=100
            with self.assertRaises(ValueError):e.submit(dict(action='OPEN_LONG',timestamp=100,position=self.position('LONG')),dict(timestamp=100,ltp=100),now=100)
            api.place_order.assert_not_called();e.close()
    def test_stock_overnight_short_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            api,master,e=self.setup_executor(folder)
            master.return_value['product_type']='STOCK'
            with self.assertRaises(ValueError):e.submit(dict(action='OPEN_SHORT',timestamp=100,position=self.position('SHORT')),dict(timestamp=100,ltp=100),now=100)
            api.place_order.assert_not_called();e.close()
    def test_fake_live_short_entry_and_reduce_cover_reconcile_signed_quantity(self):
        from unittest.mock import patch
        from contextlib import nullcontext
        with tempfile.TemporaryDirectory() as folder:
            api,master,e=self.setup_executor(folder);e.live=True;e.account_folder=folder;e.margin=Mock(return_value=500)
            api.positions.side_effect=[{'s':'ok','netPositions':[]},{'s':'ok','netPositions':[{'symbol':'MCX:GOLD-FUT','netQty':-20,'productType':'MARGIN'}]}]
            api.funds.return_value={'s':'ok','fund_limit':[{'id':10,'equityAmount':1000}]}
            api.place_order.side_effect=[{'s':'ok','id':'short1'},{'s':'ok','id':'cover1'}]
            api.orderbook.side_effect=[{'s':'ok','orderBook':[]},{'s':'ok','orderBook':[{'id':'short1','status':2,'filledQty':20,'tradedPrice':100}]},{'s':'ok','orderBook':[]},{'s':'ok','orderBook':[{'id':'cover1','status':2,'filledQty':20,'tradedPrice':90}]}]
            p=self.position('SHORT')
            with patch('sector_heatmap.chart_trade_admission.entry_lock',return_value=nullcontext()),patch('sector_heatmap.chart_trade_admission.mark_entry_attempt'),patch('direct_execution.time.sleep'):
                e.submit(dict(action='OPEN_SHORT',timestamp=100,position=p),dict(timestamp=100,ltp=100),now=100)
                self.assertEqual(e.state['position']['side'],'SHORT')
                e.submit(dict(action='CLOSE_SHORT',timestamp=101,position=p),dict(timestamp=101,ltp=90),now=101)
            self.assertEqual([c.kwargs['data']['side'] for c in api.place_order.call_args_list],[-1,1]);self.assertIsNone(e.state['position']);e.close()


class DirectRouteOwnershipTests(unittest.TestCase):
    def test_options_ownership_blocks_direct_route_after_worker_stops(self):
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)/'account';directory.mkdir()
            (directory/'paper.json').write_text(json.dumps(dict(position={'symbol':'EXACT-OPTION'},pending=None)))
            api=Mock()
            with self.assertRaisesRegex(ValueError,'Another AI route'):
                DirectExecution(api,'account',folder,lots=1,product='MARGIN',master=Mock())
            api.place_order.assert_not_called()
