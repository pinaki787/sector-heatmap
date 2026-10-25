import unittest
from datetime import date
from sector_heatmap.closed_pnl import report_range, range_report, category, _CACHE

class ClosedReports(unittest.TestCase):
    def test_ranges_and_rejection(self):
        today=date(2026,10,24)
        self.assertEqual(report_range('weekly',today),(date(2026,10,19),today))
        self.assertEqual(report_range('annual',date(2026,2,4))[0],date(2025,4,1))
        for a,b in [('2026-03-31','2026-04-02'),('2026-10-25','2026-10-25'),('2026-10-24','2026-10-20'),('2026-10-01',None)]:
            with self.assertRaises(ValueError): report_range('monthly',today,a,b)
    def test_account_isolation_and_no_fee_allocation(self):
        _CACHE.clear();calls=[]
        def fetch(a,t,f,l):
            calls.append((a,t,f,l));return {'supported':True,'data':[{'symbol_name':'NSE:ABC','segment_name':'NSE_FNO','realized_pnl':100}],'summary_data':{'gross_pnl':100,'charges':20,'net_pnl':80}}
        a=range_report('app','one','weekly',date(2026,10,24),fetch,start='2026-10-19',end='2026-10-20')
        range_report('app','one','weekly',date(2026,10,24),fetch,start='2026-10-19',end='2026-10-20')
        range_report('app','two','weekly',date(2026,10,24),fetch,start='2026-10-19',end='2026-10-20')
        self.assertEqual(len(calls),2);self.assertEqual(a['summary']['net_pnl'],80)
        self.assertNotIn('net_pnl',a['records'][0]);self.assertNotIn('charges',a['records'][0])
        self.assertEqual(a['records'][0]['from_date'],'2026-10-19')
    def test_metadata_categories(self):
        row={'symbol_name':'NSE:ABC','segment_name':'NSE_FNO','exchange_name':'NSE'}
        self.assertEqual(category(row,{'NSE:ABC':15}),'NSE · Stock options')
        self.assertEqual(category(row,{'NSE:ABC':14}),'NSE · Index options')
        self.assertIn('type unavailable',category(row,{}))
        self.assertEqual(category({'segment_name':'MCX','exchange_name':'MCX'},{}),'MCX commodities')
if __name__=='__main__':unittest.main()
