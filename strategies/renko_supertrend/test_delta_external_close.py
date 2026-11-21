import unittest
from copy import deepcopy
from .delta_external_close import confirmed_close

class ExternalDeltaTests(unittest.TestCase):
    def setUp(self):
        self.p=dict(product_id=1,symbol='C-ETH',quantity=10,entry_side=1,entry_order_id='entry',product='DELTA_LONG_OPTION')
        self.rows=[dict(id='a',product_id=1,order_id='entry',side='buy',size='10',price='4.1',commission='0.01',created_at='2026-11-07T06:28:53Z'),
                   dict(id='b',product_id=1,order_id='exit',side='sell',size='10',price='3.8',commission='0.02',created_at='2026-11-07T06:36:24Z')]
    def check(self,rows=None,orders=None,size=0):
        return confirmed_close(self.p,self.rows if rows is None else rows,orders or [],size)
    def test_full_external_close_preserves_contract_units_and_fill_price(self):
        result=self.check()
        self.assertEqual((result['quantity'],result['price'],result['commission']),(10,3.8,.02))
    def test_split_fills_of_one_exit_order(self):
        self.rows[1]['size']='4'
        extra={**self.rows[1],'id':'c','size':'6','price':'3.9'}
        result=self.check(self.rows+[extra])
        self.assertAlmostEqual(result['price'],3.86)
    def test_short_perpetual_close(self):
        self.p['entry_side']=-1;self.rows[0]['side']='sell';self.rows[1]['side']='buy'
        self.assertEqual(self.check()['side'],1)
    def test_partial_missing_duplicate_intervening_and_other_order_fail_closed(self):
        variants=[]
        for key,value in [('size','9'),('side','buy'),('price','NaN'),('order_id','entry')]:
            rows=deepcopy(self.rows);rows[1][key]=value;variants.append(rows)
        variants += [self.rows[:1],self.rows+self.rows[1:],self.rows+[{**self.rows[1],'id':'c','order_id':'another'}]]
        for rows in variants:
            with self.subTest(rows=rows),self.assertRaises((ValueError,ArithmeticError)):self.check(rows)
        with self.assertRaises(ValueError):self.check(size=10)
        with self.assertRaises(ValueError):self.check(orders=[dict(product_id=1)])
    def test_other_product_cannot_supply_exit(self):
        self.rows[1]['product_id']=2
        with self.assertRaises(ValueError):self.check()

class RetainedOppositeExitTests(unittest.TestCase):
    def test_expired_entry_event_keeps_completed_exit_only(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from .price_basis import retain_opposite_exit
        for side,opposite in [('BULLISH','BEARISH'),('BEARISH','BULLISH')]:
            for flag in (None,'provisional','is_forming','no_brick','same_color','before_entry','future'):
                p=dict(direction=side)
                state=dict(position=p,config=dict(strategy_mode='SIMPLE_BRICK',strategy_basis='RENKO'))
                row=dict(timestamp=10,market_event_at=10,has_completed_brick=True,brick_direction=opposite)
                if flag in ('provisional','is_forming'):row[flag]=True
                if flag=='no_brick':row['has_completed_brick']=False
                if flag=='same_color':row['brick_direction']=side
                if flag=='future':row['market_event_at']=101
                r=SimpleNamespace(state=state,clock=lambda:100,exit_is_later=lambda row,p:flag!='before_entry',
                                  indicator_snapshot=lambda row,why:dict(reason=why),save=Mock())
                self.assertEqual(retain_opposite_exit(r,row),flag is None)
                self.assertEqual(bool(p.get('exit_requested')),flag is None)
                self.assertEqual(r.save.call_count,int(flag is None))
