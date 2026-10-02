import tempfile,unittest
from pathlib import Path
from sector_heatmap.delta_india import DeltaIndia
from tests.test_delta_india import PRODUCT
class AccountTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.b=DeltaIndia(Path(self.tmp.name)/'paper.json',clock=lambda:100000);self.pages=[];self.positions=[];self.calls=[]
  self.b.catalog=lambda:{'instruments':[self.b._metadata(PRODUCT)]}
  def private(method,path,params=None):
   self.calls.append((method,path,params));self.assertEqual(method,'GET')
   if path.endswith('balances'):return {'result':[{'asset_symbol':'USD','balance':'100'}]}
   if path.endswith('margined'):return {'result':self.positions}
   index=1 if params.get('after') else 0;return self.pages[index] if self.pages else {'result':[],'meta':{}}
  self.b._private=private
 def test_external_positions_broker_pnl_and_calculated_signed_linear_units(self):
  self.positions=[dict(product_id=27,product_symbol='BTCUSD',size=3,entry_price='100',mark_price='110',unrealized_pnl='9',product=PRODUCT),dict(product_id=27,size=-2,entry_price='100',mark_price='110',product=PRODUCT)]
  d=self.b.account();self.assertEqual(d['positions'][0]['unrealized_pnl'],'9');self.assertEqual(d['positions'][1]['unrealized_pnl'],'-0.020');self.assertEqual(d['positions'][1]['settlement_currency'],'USD');self.assertIn('Calculated',d['positions'][1]['pnl_basis'])
 def test_paginated_fill_projection_ignores_private_metadata_and_cumulative_is_separate(self):
  fill=dict(id='f1',product_symbol='BTCUSD',side='buy',size='1',price='101',created_at='2026-10-01T10:00:00Z',commission='.1',settling_asset_symbol='USD',meta_data={'ip':'private-ip','new_position':{'realized_pnl':'8'}})
  self.pages=[{'result':[fill],'meta':{'after':'next'}},{'result':[fill|dict(id='f2')],'meta':{}}]
  d=self.b.account();self.assertTrue(d['history_complete']);self.assertEqual(len(d['fills']),2);self.assertIsNone(d['fills'][0]['realized_pnl']);self.assertEqual(d['fills'][0]['position_realized_pnl'],'8');self.assertNotIn('private-ip',str(d));self.assertEqual(self.calls[-1][2]['after'],'next')
 def test_unknown_contract_pnl_and_incomplete_history_are_explicit(self):
  self.positions=[dict(product_id=28,size=1,entry_price='100',mark_price='110')]
  self.pages=[{'result':[],'meta':{'after':'repeat'}},{'result':[],'meta':{'after':'repeat'}}]
  d=self.b.account();self.assertIsNone(d['positions'][0]['unrealized_pnl']);self.assertIn('unavailable',d['positions'][0]['pnl_basis']);self.assertFalse(d['history_complete']);self.assertIn('repeated',d['history_error'])
