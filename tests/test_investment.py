import unittest,time,math
from sector_heatmap.investment import options,assess,COLUMNS,AI_SCHEMA
from sector_heatmap.section_permissions import allowed,FEATURES
from sector_heatmap.job_http import operation
class InvestmentTests(unittest.TestCase):
 def row(self,**kw):
  d=dict(name='TEST',description='Test company',close=98,**{'High.All':100,'SMA50':95,'SMA200':85,'Perf.6M':20,'Perf.Y':30,'market_cap_basic':2e10,'average_volume_30d_calc':1e6,'return_on_equity':20,'price_earnings_ttm':25,'earnings_per_share_diluted_yoy_growth_ttm':20,'total_revenue_yoy_growth_ttm':15,'sector':'Test','time':time.time(),'isin':'INE000000001'})
  d.update(kw);return assess({'d':[d.get(k) for k in COLUMNS]},options({}),time.time())
 def test_quality(self):
  r=self.row();self.assertEqual(r['rule_status'],'QUALITY_REVIEW');self.assertEqual(r['conviction'],'NOT_ESTABLISHED')
 def test_ath(self):
  r=self.row(close=88);self.assertFalse(r['eligible']);self.assertIn('Near reported ATH failed or unavailable',r['reasons'])
 def test_missing_ath(self):self.assertFalse(self.row(**{'High.All':None})['eligible'])
 def test_missing_financial(self):self.assertFalse(self.row(return_on_equity=None)['quality_pass'])
 def test_stale(self):self.assertFalse(self.row(time=time.time()-6*86400)['eligible'])
 def test_extended(self):self.assertEqual(self.row(SMA50=80)['rule_status'],'EXTENDED_WAIT')
 def test_symbol_normalization(self):self.assertEqual(options({'symbols':'NSE:PASHUPATI-EQ, TECHM TECHM'})['symbols'],['PASHUPATI','TECHM'])
 def test_invalid(self):
  for p in ({'distance_pct':float('nan')},{'distance_pct':31},{'mode':'OPENAI'},{'symbols':'A;sh'}):
   with self.assertRaises(ValueError):options(p)
 def test_permission(self):
  self.assertIn('investment',FEATURES)
  self.assertFalse(allowed({'features':['screener']},'/api/investment/analyze'))
  self.assertTrue(allowed({'features':['investment']},'/api/investment/analyze'))
  self.assertTrue(allowed({'features':['investment']},'/api/jobs'))
 def test_job(self):self.assertEqual(operation('/api/investment/analyze'),('ANALYSIS','investment'))
 def test_missing_price(self):self.assertFalse(self.row(close=None)['eligible'])
 def test_negative_pe(self):self.assertFalse(self.row(price_earnings_ttm=-10)['quality_pass'])
if __name__=='__main__':unittest.main()

