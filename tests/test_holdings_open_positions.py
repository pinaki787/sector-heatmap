from types import SimpleNamespace
import unittest
from unittest.mock import patch
from sector_heatmap.native_holdings import DhanHoldings
from sector_heatmap.holdings_analysis import HoldingsAnalysis

class PositionInventoryTests(unittest.TestCase):
    def adapter(self,positions,holdings=None):
        def request(method,path):
            return {'/profile':{'dhanClientId':'123'},'/holdings':holdings or [],'/positions':positions}[path]
        client=SimpleNamespace(client_id='123',request=request)
        master=SimpleNamespace(load=lambda now:[dict(SEM_SMST_SECURITY_ID='42',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='D',SEM_TRADING_SYMBOL='TEST-OPTION')])
        return DhanHoldings(SimpleNamespace(_client=lambda:client,account={'id':'test'},master=master))
    def test_empty_demat_keeps_longs_shorts_and_excludes_flat(self):
        rows=self.adapter([dict(netQty=q,securityId='42',exchangeSegment='NSE_FNO',productType='MARGIN',buyAvg=10,sellAvg=12) for q in (5,-5,0)]).inventory()
        self.assertEqual([r['quantity'] for r in rows],[5,-5])
        self.assertEqual([r['average_price'] for r in rows],[10,12])
        self.assertEqual(len({r['id'] for r in rows}),2)
        self.assertTrue(all(r['kind']=='OPEN_POSITION' for r in rows))
    def test_unresolved_is_visible_and_other_account_is_rejected(self):
        self.assertIsNone(self.adapter([dict(netQty=1,securityId='99',exchangeSegment='NSE_FNO')]).inventory()[0]['native_identity'])
        with self.assertRaises(PermissionError):self.adapter([dict(netQty=1,dhanClientId='other')]).inventory()
        with self.assertRaises(ValueError):self.adapter([dict(netQty=None)]).inventory()
    def test_compact_master_without_isin_uses_exact_native_id_and_symbol(self):
        holding=dict(totalQty=500,securityId='42',exchange='ALL',isin='INE124Y01028',tradingSymbol='TEST-OPTION',avgCostPrice=85.08,mtf_qty=500)
        adapter=self.adapter([], [holding])
        adapter.execution.master.load=lambda now:[dict(SEM_SMST_SECURITY_ID='42',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='E',SEM_TRADING_SYMBOL='TEST-OPTION')]
        row=adapter.inventory()[0]
        self.assertEqual(row['kind'],'DELIVERY_EQUITY')
        self.assertEqual(row['native_identity']['securityId'],'42')
        self.assertEqual(row['holding_type'],'MTF funded equity')
        holding['tradingSymbol']='WRONG'
        self.assertIsNone(adapter.inventory()[0]['native_identity'])
        holding['tradingSymbol']='TEST-OPTION'
        adapter.execution.master.load=lambda now:[dict(SEM_SMST_SECURITY_ID='42',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='E',SEM_TRADING_SYMBOL='TEST-OPTION',SEM_ISIN_CODE='WRONG')]
        self.assertIsNone(adapter.inventory()[0]['native_identity'])
    def test_positions_survive_batch_analysis_with_review_reason(self):
        adapter=self.adapter([dict(netQty=-2,securityId='42',exchangeSegment='NSE_FNO',sellAvg=12,unrealizedProfit=4)])
        with patch.object(adapter,'enrich',lambda rows:rows):
            report=HoldingsAnalysis().batch(adapter,limit=5)
        self.assertEqual(report['total'],1)
        self.assertEqual(report['rows'][0]['action'],'REVIEW_NEEDED')
        self.assertEqual(report['rows'][0]['broker_unrealized_pnl'],4)
        self.assertIn('Open trading position',report['rows'][0]['reasons'][0])

if __name__=='__main__':unittest.main()
