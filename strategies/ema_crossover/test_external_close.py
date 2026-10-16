import unittest
from copy import deepcopy
from .external_close import confirmed_close

class ExternalCloseTests(unittest.TestCase):
    def setUp(self):
        self.position=dict(symbol='NSE:TESTCE',quantity=65,entry_side=1,entry_order_id='entry')
        self.positions=[dict(symbol='NSE:TESTCE',netQty=0,productType='MARGIN')]
        self.entry=dict(symbol='NSE:TESTCE',id='entry',side=1,qty=65,filledQty=65,status=2,productType='MARGIN',orderDateTime='15-Oct-2026 10:46:26',tradedPrice=118.7)
        self.exit={**self.entry,'id':'exit','side':-1,'orderDateTime':'15-Oct-2026 10:54:33','tradedPrice':120.5}
    def check(self,rows=None):return confirmed_close(self.position,self.positions,rows or [self.entry,self.exit])
    def test_confirmed_exit_and_later_independent_trades(self):
        later={**self.entry,'id':'later','qty':130,'filledQty':130,'orderDateTime':'15-Oct-2026 11:01:21'}
        self.assertEqual(self.check([self.entry,self.exit,later])['order_id'],'exit')
    def test_nonflat_blocks(self):
        self.positions[0]['netQty']=65
        with self.assertRaises(ValueError):self.check()
    def test_missing_entry_blocks(self):
        with self.assertRaises(ValueError):self.check([self.exit])
    def test_other_product_exit_blocks(self):
        self.exit['productType']='INTRADAY'
        with self.assertRaises(ValueError):self.check()
    def test_partial_exit_blocks(self):
        self.exit['filledQty']=30
        with self.assertRaises(ValueError):self.check()
    def test_intervening_buy_blocks(self):
        other={**self.entry,'id':'other','orderDateTime':'15-Oct-2026 10:50:00'}
        with self.assertRaises(ValueError):self.check([self.entry,other,self.exit])
    def test_pending_order_blocks(self):
        other={**self.exit,'id':'pending','status':6,'filledQty':0}
        with self.assertRaises(ValueError):self.check([self.entry,self.exit,other])
    def test_bad_price_blocks(self):
        self.exit['tradedPrice']=float('nan')
        with self.assertRaises(ValueError):self.check()
    def test_read_only(self):
        before=deepcopy([self.position,self.positions,self.entry,self.exit]);self.check()
        self.assertEqual(before,[self.position,self.positions,self.entry,self.exit])

class StopIntegrationTests(unittest.TestCase):
    def test_confirmed_external_exit_stops_without_sending(self):
        import tempfile
        from pathlib import Path
        from .runner import Runner
        fixture=ExternalCloseTests();fixture.setUp()
        class Broker:
            sent=[]
            def positions(self):return fixture.positions
            def orders(self):return [fixture.entry,fixture.exit]
            def stop(self):pass
            def place(self,*args):self.sent.append(args);raise AssertionError('No order allowed')
        with tempfile.TemporaryDirectory() as directory:
            broker=Broker();runner=Runner(broker,Path(directory)/'state.json')
            runner.state.update(config={'mode':'LIVE','broker':'FYERS'},running=True,accepting_entries=False,squareoff_requested=True,pending=None,
                position={**fixture.position,'entry_price':118.7,'lot_size':65,'quantity_multiplier':1},losses={},realized_pnl=0)
            runner.snapshot=lambda:dict(runner.state)
            self.assertTrue(runner.reconcile_external_stop())
            self.assertIsNone(runner.state['position']);self.assertIsNone(runner.state['pending'])
            self.assertFalse(runner.state['running']);self.assertEqual(broker.sent,[])
            self.assertAlmostEqual(runner.state['realized_pnl'],117.0)
            self.assertFalse(runner.reconcile_external_stop())
    def test_without_stop_request_preserves_position(self):
        import tempfile
        from pathlib import Path
        from .runner import Runner
        with tempfile.TemporaryDirectory() as directory:
            runner=Runner(object(),Path(directory)/'state.json')
            runner.state.update(config={'mode':'LIVE','broker':'FYERS'},squareoff_requested=False,position={'quantity':65})
            self.assertFalse(runner.reconcile_external_stop())
            self.assertEqual(runner.state['position'],{'quantity':65})
