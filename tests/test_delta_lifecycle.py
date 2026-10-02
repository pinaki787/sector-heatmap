import unittest
from decimal import Decimal
from sector_heatmap.delta_lifecycle import lifecycles

def fill(i,side,q,price,after,fee='1',cumulative=None):
 return dict(id=i,product_id=1,symbol='BTCUSD',settlement_currency='USD',created_at=f'2026-10-01T00:{i:02d}:00Z',side=side,size=str(q),price=str(price),position_size_after=str(after) if after is not None else None,linear_contract_value='0.1',commission=fee,position_realized_pnl=cumulative,order_id=i)
class LifecycleTests(unittest.TestCase):
 def test_scaled_long_partial_exit_weighted_values_and_latest_cumulative(self):
  fs=[fill(1,'buy',2,100,2),fill(2,'buy',2,120,4),fill(3,'sell',1,130,3,cumulative='2'),fill(4,'sell',3,140,0,cumulative='11')]
  r=lifecycles(fs,[],True)[0];self.assertEqual(r['status'],'CLOSED');self.assertEqual(Decimal(r['entry_price']),110);self.assertEqual(Decimal(r['entry_value']),44);self.assertEqual(Decimal(r['exit_value']),55);self.assertEqual(Decimal(r['gross_realized_pnl']),11);self.assertEqual(Decimal(r['net_realized_pnl']),7);self.assertEqual(r['broker_position_realized_pnl'],'11')
 def test_short_and_reversal_fee_split_no_cumulative_duplication(self):
  rs=lifecycles([fill(1,'sell',2,100,-2),fill(2,'buy',3,90,1,fee='3',cumulative='2'),fill(3,'sell',1,95,0)],[],True)
  long,short=rs;self.assertEqual(short['direction'],'SHORT');self.assertEqual(Decimal(short['gross_realized_pnl']),2);self.assertEqual(Decimal(short['fees']),3);self.assertIsNone(short['broker_position_realized_pnl']);self.assertEqual(Decimal(long['fees']),2);self.assertEqual(Decimal(long['gross_realized_pnl']),Decimal('.5'));self.assertEqual(long['broker_position_realized_pnl'],'2');self.assertEqual(sum(len(r['details']) for r in rs),4)
 def test_missing_opening_and_truncation_no_fabricated_price_or_pnl(self):
  r=lifecycles([fill(1,'sell',2,100,0)],[],False)[0];self.assertIn('opening fills missing',r['status']);self.assertIn('history incomplete',r['status']);self.assertIsNone(r['entry_price']);self.assertIsNone(r['entry_value']);self.assertIsNone(r['gross_realized_pnl']);self.assertEqual(r['matched_contracts'],'0')
 def test_open_partial_remaining_reconciles_external_position(self):
  fs=[fill(1,'buy',3,100,3),fill(2,'sell',1,110,2)]
  r=lifecycles(fs,[dict(product_id=1,settlement_currency='USD',size='2')],True)[0];self.assertEqual(r['status'],'OPEN');self.assertEqual(r['remaining_contracts'],'2');self.assertEqual(Decimal(r['gross_realized_pnl']),1);self.assertIsNone(r['net_realized_pnl'])
 def test_duplicates_currency_scope_missing_units_and_discontinuity(self):
  f=fill(1,'buy',1,100,1);g=fill(2,'sell',1,110,0);g['linear_contract_value']=None
  r=lifecycles([f,f,g],[],True)[0];self.assertEqual(len(r['details']),2);self.assertIsNone(r['gross_realized_pnl']);self.assertIsNone(r['entry_value'])
  r=lifecycles([fill(1,'buy',1,100,None),fill(2,'sell',1,110,None)],[],True)[0];self.assertEqual(r['status'],'UNRECONCILED');self.assertIsNone(r['net_realized_pnl'])
  a=fill(1,'buy',1,100,1);b=fill(2,'sell',1,110,0);b['settlement_currency']='INR';rs=lifecycles([a,b],[],True);self.assertEqual(len(rs),2)
 def test_unknown_fee_and_position_gap(self):
  rs=lifecycles([fill(1,'buy',1,100,1,fee=None),fill(2,'sell',1,110,0)],[],True);self.assertIsNone(rs[0]['fees']);self.assertIsNone(rs[0]['net_realized_pnl'])
  rs=lifecycles([fill(1,'buy',1,100,1),fill(2,'sell',2,110,0)],[],True);self.assertEqual(len(rs),2);self.assertTrue(any('UNRECONCILED' in r['status'] for r in rs))

 def test_external_open_snapshot_without_fills_remains_incomplete(self):
  r=lifecycles([],[dict(product_id=1,product_symbol='BTCUSD',settlement_currency='USD',size='-3')],True)[0];self.assertEqual(r['direction'],'SHORT');self.assertEqual(r['remaining_contracts'],'3');self.assertIn('opening fills missing',r['status']);self.assertIsNone(r['entry_price']);self.assertIsNone(r['net_realized_pnl']);self.assertIsNone(r['fees'])
