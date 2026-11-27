import unittest
from sector_heatmap.dhan_option_catalog import search
TODAY='2026-11-27'
def host(ticker,exchange='NSE',segment='E',security='1',description=None):
 return dict(SEM_EXM_EXCH_ID=exchange,SEM_SEGMENT=segment,SEM_TRADING_SYMBOL=ticker,SEM_SMST_SECURITY_ID=security,SEM_CUSTOM_SYMBOL=description or ticker,SEM_SERIES='EQ' if segment=='E' else '')
def option(ticker,side='CE',expiry='2026-12-31',exchange='NSE',kind='OPTSTK'):
 return dict(SEM_EXM_EXCH_ID=exchange,SEM_SEGMENT='D',SEM_TRADING_SYMBOL=ticker+'-Dec2026-100-'+side,SEM_OPTION_TYPE=side,SEM_EXPIRY_DATE=expiry+' 15:30:00',SEM_STRIKE_PRICE='100',SEM_INSTRUMENT_NAME=kind)
def listed(ticker,**kw):return [host(ticker,**kw),option(ticker,exchange=kw.get('exchange','NSE'),kind='OPTIDX' if kw.get('segment')=='I' else 'OPTSTK'),option(ticker,'PE',exchange=kw.get('exchange','NSE'),kind='OPTIDX' if kw.get('segment')=='I' else 'OPTSTK')]
class OptionCatalogueTests(unittest.TestCase):
 def test_stock_filter_precedes_results_and_does_not_truncate(self):
  rows=listed('NIFTY',segment='I')+sum([listed('STOCK'+str(n).zfill(3),security=str(n+10)) for n in range(100)],[])
  result=search(rows,TODAY,'','NSE_STOCK')
  self.assertEqual(len(result),100);self.assertTrue(all(r['product_type']=='STOCK' for r in result));self.assertEqual(result[-1]['symbol'],'NSE:STOCK099')
 def test_piind_company_search_and_exact_native_identity(self):
  rows=listed('PIIND',security='24184',description='PI Industries')+listed('PIIND',exchange='BSE',security='523642')
  self.assertEqual([r['symbol'] for r in search(rows,TODAY,'PI Industries','NSE_STOCK')],['NSE:PIIND'])
  self.assertEqual(search(rows,TODAY,'NSE:PIIND','NSE_STOCK')[0]['chart_symbol'],'NSE_EQ:24184')
  self.assertEqual(search(rows,TODAY,'NSE:PIIND','BSE_STOCK'),[])
 def test_index_market_excludes_stocks_and_other_exchange(self):
  rows=listed('PIIND')+listed('NIFTY',segment='I')+listed('SENSEX',exchange='BSE',segment='I')
  self.assertEqual([r['symbol'] for r in search(rows,TODAY,'','NSE_INDEX')],['NSE:NIFTY'])
 def test_expired_unpaired_and_futures_do_not_qualify(self):
  rows=[host('OLD'),option('OLD',expiry='2026-11-01'),option('OLD','PE',expiry='2026-11-01'),host('ONE'),option('ONE'),host('FUT'),dict(option('FUT'),SEM_INSTRUMENT_NAME='FUTSTK',SEM_OPTION_TYPE='XX')]
  self.assertEqual(search(rows,TODAY,'','NSE_STOCK'),[])
 def test_hyphenated_underlying_and_duplicate_rows(self):
  rows=listed('A-B');rows+=rows[:]
  result=search(rows,TODAY,'A-B','NSE_STOCK');self.assertEqual(len(result),1);self.assertEqual(result[0]['underlying'],'A-B')
 def test_caller_cannot_mutate_cached_identity(self):
  rows=listed('PIIND');result=search(rows,TODAY,'','NSE_STOCK');result[0]['symbol']='BAD'
  self.assertEqual(search(rows,TODAY,'','NSE_STOCK')[0]['symbol'],'NSE:PIIND')
 def test_bse_group_a_equities_remain_eligible(self):
  rows=listed('PIIND',exchange='BSE');rows[0]['SEM_SERIES']='A'
  self.assertEqual([r['symbol'] for r in search(rows,TODAY,'','BSE_STOCK')],['BSE:PIIND'])
