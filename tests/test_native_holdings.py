from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from sector_heatmap.native_holdings import DhanHoldings,MotilalHoldings,quote_time
from sector_heatmap.section_permissions import allowed

class NativeHoldingsTests(TestCase):
 def dhan(self,rows,owner='client-one'):
  client=SimpleNamespace(client_id='client-one',request=Mock(side_effect=[{'dhanClientId':owner},rows]))
  master=Mock(return_value=[dict(SEM_SEGMENT='E',SEM_SMST_SECURITY_ID='123',SEM_EXM_EXCH_ID='NSE',SEM_ISIN_CODE='ISIN1',SEM_TRADING_SYMBOL='TEST')])
  return SimpleNamespace(_client=lambda:client,account={'id':'account-one'},master=SimpleNamespace(load=master))
 def test_dhan_maps_native_identity_and_does_not_add_collateral(self):
  row=dict(securityId='123',exchange='ALL',isin='ISIN1',tradingSymbol='TEST',totalQty=10,dpQty=8,t1Qty=2,collateralQty=8,avgCostPrice=100)
  result=DhanHoldings(self.dhan([row])).inventory()[0]
  self.assertEqual(result['quantity'],10)
  self.assertEqual(result['native_identity']['securityId'],'123')
  self.assertEqual(result['symbol'],'NSE:TEST-EQ')
 def test_dhan_identity_is_verified_before_holdings_read(self):
  service=self.dhan([],owner='another-client')
  with self.assertRaises(PermissionError):DhanHoldings(service).inventory()
  self.assertEqual(service._client().request.call_count,1)
 def test_empty_dhan_holdings_do_not_download_master(self):
  service=self.dhan([]);self.assertEqual(DhanHoldings(service).inventory(),[])
  service.master.load.assert_not_called()
 def test_unresolved_dhan_is_retained_for_review(self):
  rows=DhanHoldings(self.dhan([dict(securityId='123',isin='DIFFERENT',totalQty=3)])).inventory()
  self.assertEqual(rows[0]['kind'],'OTHER_HOLDING');self.assertEqual(rows[0]['quantity'],3)
 def test_motilal_dp_quantity_is_not_inflated_with_collateral(self):
  meta=dict(symbol='MO:NSE:123',token=123,isin='ISIN1',exchange='NSE')
  service=SimpleNamespace(account={'id':'account-one'},book=lambda kind:{'data':[dict(dpquantity=10,collateralquantity=8,nsesymboltoken=123,scripisinno='ISIN1',buyavgprice=100)]},master=SimpleNamespace(rows=lambda exchange:[meta]))
  with patch('sector_heatmap.motilal_strategy_broker.cash_row',return_value=True):result=MotilalHoldings(service).inventory()[0]
  self.assertEqual(result['quantity'],10);self.assertEqual(result['symbol'],'MO:NSE:123')
 def test_native_holdings_permissions_do_not_require_unrelated_sections(self):
  for path in ['/api/dhan/holdings-analysis/analyze','/api/motilal/holdings-analysis/analyze']:
   self.assertTrue(allowed({'features':['holdings']},path))
   self.assertFalse(allowed({'features':['renko-supertrend']},path))
 def test_missing_exchange_timestamp_is_not_replaced_with_receipt(self):
  self.assertIsNone(quote_time(None));self.assertIsNone(quote_time('unavailable'))
  self.assertEqual(quote_time(1790000000000),1790000000)
