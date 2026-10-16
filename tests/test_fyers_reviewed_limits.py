from copy import deepcopy
from unittest.mock import patch
import unittest
from .test_fyers_execution import FakeClient,FyersExecutionTests
from sector_heatmap.fyers_execution import PreviewChanged,FyersExecutionUnavailable


class MovingClient(FakeClient):
    def __init__(self):
        super().__init__();self.move=0;self.balance=100000;self.sent=[];self.timeout=False
    def quotes(self,data=None):
        value=super().quotes(data)
        for row in value['d']:
            row['v']['tt']+=self.move
            for k in ('bid','ask','lp'):row['v'][k]+=self.move
        return value
    def funds(self):
        return {'s':'ok','fund_limit':[{'id':10,'equityAmount':self.balance}]}
    def place_order(self,order):
        self.sent.append(deepcopy(order))
        if self.timeout:raise TimeoutError('uncertain')
        return {'s':'ok','id':'one'}
    def place_basket_orders(self,orders):
        self.sent.extend(deepcopy(orders));return {'s':'ok','data':[{'id':str(i)} for i in range(len(orders))]}


@patch('sector_heatmap.fyers_execution.load_config',return_value={'FYERS_ACCESS_TOKEN':'APP:test'})
class ReviewedLimitTests(unittest.TestCase):
    make_service=FyersExecutionTests.make_service
    def payload(self,symbol='NSE:TEST-EQ',entry=100):
        return dict(broker='fyers',underlying=symbol,invalidation=entry-5,quantity=10,
                    proposal=dict(kind='EQUITY',direction='BULLISH',target=entry+10,quantity=10),
                    daily_loss_limit=5000,idea_risk_limit=2000,risk_reserve=1000)
    def service(self):
        client=MovingClient();s=self.make_service(client);s.live_gate=lambda:True
        return s,client
    def test_moving_quote_timestamps_and_balances_submit_reviewed_limit_once(self,_):
        s,c=self.service();p=s.prepare(self.payload());c.move=1;c.balance=99999
        s.submit(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(c.sent[0]['limitPrice'],100);self.assertEqual(c.sent[0]['qty'],10)
        with self.assertRaises(ValueError):s.submit(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(len(c.sent),1)
    def test_fresh_funds_duplicates_and_stop_crossing_still_block(self,_):
        for cause in ('funds','duplicate','position','stop'):
            s,c=self.service();p=s.prepare(self.payload())
            if cause=='funds':c.balance=1
            if cause=='duplicate':c.orders_data=[dict(symbol='NSE:TEST-EQ',status=6)]
            if cause=='position':c.positions_data=[dict(symbol='NSE:TEST-EQ',netQty=10)]
            if cause=='stop':c.move=-6
            with self.assertRaises(FyersExecutionUnavailable):s.submit(p['preview_id'],p['confirmation_phrase'])
            self.assertEqual(c.sent,[])
    def test_material_contract_metadata_change_requires_new_preview(self,_):
        s,c=self.service();p=s.prepare(self.payload());original=s.cm_master.lookup
        s.cm_master.lookup=lambda symbols:{k:{**v,'tick_size':.1} for k,v in original(symbols).items()}
        with self.assertRaises(PreviewChanged):s.submit(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(c.sent,[])
    def test_uncertain_submission_cannot_be_retried(self,_):
        s,c=self.service();p=s.prepare(self.payload());c.timeout=True
        with self.assertRaises(TimeoutError):s.submit(p['preview_id'],p['confirmation_phrase'])
        with self.assertRaises(ValueError):s.submit(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(len(c.sent),1)
    def test_batch_keeps_reviewed_quantities_and_limits_as_quotes_move(self,_):
        s,c=self.service();p=s.prepare_batch(dict(items=[self.payload(),self.payload('NSE:TEST2-EQ',200)]))
        before=[(x['instrument']['quantity'],x['instrument']['contracts'][0]['limit_price']) for x in p['items']]
        c.move=1;c.balance-=1;s.submit_batch(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual([(o['qty'],o['limitPrice']) for o in c.sent],before)
    def test_batch_fresh_funds_still_block(self,_):
        s,c=self.service();p=s.prepare_batch(dict(items=[self.payload(),self.payload('NSE:TEST2-EQ',200)]))
        c.balance=1
        with self.assertRaises(FyersExecutionUnavailable):s.submit_batch(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(c.sent,[])
