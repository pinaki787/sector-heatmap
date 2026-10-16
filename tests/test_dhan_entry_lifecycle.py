from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from tests.test_dhan_strategy_broker import Tests as Fixtures
from sector_heatmap.dhan_strategy_service import DhanRenkoRunner
from strategies.ema_crossover.runner import Runner as Base

class EntryLifecycleTests(TestCase):
    setUp=Fixtures.setUp
    def runner(self):
        r=DhanRenkoRunner(self.broker,Path(self.temp.name)/'runner.json',clock=lambda:self.now)
        self.addCleanup(r.release)
        r.state.update(config=dict(mode='LIVE',max_trades=2,timeframe='1 minute',label='test',underlying='NSE:NIFTY'),running=True,accepting_entries=True,trades_used=0,last_signal=dict(timestamp=self.now-60))
        return r
    def submit(self,r,order=None):
        position=dict(symbol='NSE_FNO:1',direction='BULLISH',entry_side=1,lot_size=25,quantity=25,quantity_multiplier=1,tick_size=.05)
        with patch.object(r,'validate_entry_authorization'):
            Base.submit(r,order or self.order,position,'RENKO_EMA_ENTRY')
    def test_price_move_defers_without_order_or_stop(self):
        r=self.runner()
        self.submit(r,dict(self.order,limitPrice=9.95))
        self.assertEqual(r.state['status'],'ENTRY_DEFERRED')
        self.assertTrue(r.state['running'])
        self.assertTrue(r.state['accepting_entries'])
        self.assertIsNone(r.state['pending'])
        self.assertEqual(r.state['trades_used'],0)
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,b in self.client.calls))
    def test_zero_fill_does_not_consume_quota(self):
        r=self.runner();self.submit(r)
        self.assertEqual(r.state['trades_used'],0)
        p=r.state['pending']
        self.client.orders=[dict(orderId='123',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',transactionType='BUY',productType='MARGIN',quantity=25,filledQty=0,averageTradedPrice=0,orderStatus='CANCELLED',correlationId=p['tag'])]
        r.reconcile()
        self.assertEqual(r.state['trades_used'],0)
        self.assertIsNone(r.state['position'])
        self.assertTrue(r.state['running'])
    def test_partial_fill_consumes_one_entry(self):
        r=self.runner();self.submit(r);p=r.state['pending']
        self.client.orders=[dict(orderId='123',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',transactionType='BUY',productType='MARGIN',quantity=25,filledQty=10,averageTradedPrice=10,orderStatus='CANCELLED',correlationId=p['tag'])]
        self.client.positions=[dict(dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',netQty=10,costPrice=10,productType='MARGIN')]
        r.reconcile()
        self.assertEqual(r.state['trades_used'],1)
        self.assertEqual(r.state['position']['quantity'],10)
    def test_uncertain_submission_retains_pending(self):
        r=self.runner();self.client.fail_submit=True;self.submit(r)
        self.assertEqual(r.state['status'],'ORDER_STATUS_UNKNOWN')
        self.assertIsNotNone(r.state['pending'])
        self.assertEqual(r.state['trades_used'],0)

    def test_mcx_day_ticket_and_native_payload(self):
        self.broker.contracts['MCX_COMM:77']=dict(self.broker.contract('NSE_FNO:1'),exchange_segment='MCX_COMM',security_id='77')
        self.broker.contract=lambda symbol:self.broker.contracts['MCX_COMM:77']
        order=self.broker.order('MCX_COMM:77',25,1,dict(bid=9.95,ask=10))
        self.assertEqual(order['validity'],'DAY')
        self.broker.validate_order(order)
        self.assertEqual(self.broker._native(order,self.client)['validity'],'DAY')
    def test_day_pending_cancel_waits_for_terminal_reconciliation(self):
        r=self.runner();self.submit(r);p=r.state['pending']
        p['order']['validity']='DAY'
        p['submitted_at']=self.now-31
        self.client.orders=[dict(orderId='123',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',transactionType='BUY',productType='MARGIN',quantity=25,filledQty=0,averageTradedPrice=0,orderStatus='PENDING',correlationId=p['tag'])]
        with patch.object(self.broker,'validate_order'):
            r.reconcile()
        self.assertIsNotNone(r.state['pending'])
        self.assertTrue(r.state['pending']['cancel_requested'])
        self.assertTrue(any(m=='DELETE' for m,p,b in self.client.calls))
        self.client.orders[0]['orderStatus']='CANCELLED'
        r.reconcile()
        self.assertIsNone(r.state['pending'])
        self.assertEqual(r.state['trades_used'],0)
