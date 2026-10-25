import unittest,time
from copy import deepcopy
from sector_heatmap.investment_rs import calculate
from sector_heatmap.investment_plan import plan
class SectorStrengthTests(unittest.TestCase):
 def setUp(self):
  self.now=time.time();self.rows=[dict(symbol='NSE:T'+str(i)+'-EQ',sector='Technology',metrics={'Perf.6M':10.,'Perf.Y':20.,'time':self.now},missing=['Benchmark-relative strength']) for i in range(5)]
  self.benchmark=dict(metrics={'Perf.6M':2.,'Perf.Y':5.},bar_time=self.now)
 def test_equal_weight_sector_and_stock_strength(self):
  context=calculate(self.rows,self.benchmark,self.now)
  self.assertEqual(context['status'],'AVAILABLE');s=self.rows[0]['sector_strength']
  self.assertEqual(s['status'],'LEADING');self.assertEqual(s['windows']['6m']['excess_pp'],8.);self.assertEqual(s['windows']['12m']['excess_pp'],15.)
  self.assertEqual(self.rows[0]['relative_strength']['windows']['12m'],15.)
 def test_missing_minimum_peers(self):
  calculate(self.rows[:4],self.benchmark,self.now);self.assertEqual(self.rows[0]['sector_strength']['status'],'UNAVAILABLE')
 def test_mismatched_session(self):
  self.rows[0]['metrics']['time']-=86400
  calculate(self.rows,self.benchmark,self.now)
  self.assertIsNone(self.rows[0]['relative_strength']['windows']['6m']);self.assertEqual(self.rows[0]['sector_strength']['status'],'UNAVAILABLE')
 def test_missing_benchmark(self):
  calculate(self.rows,{},self.now);self.assertIsNone(self.rows[0]['sector_strength']['windows']['6m']['excess_pp'])
 def test_missing_window(self):
  self.benchmark['metrics']['Perf.Y']=None
  calculate(self.rows,self.benchmark,self.now);self.assertEqual(self.rows[0]['relative_strength']['status'],'UNAVAILABLE')
 def test_stale_benchmark(self):
  self.benchmark['bar_time']-=6*86400
  calculate(self.rows,self.benchmark,self.now);self.assertEqual(self.rows[0]['sector_strength']['status'],'UNAVAILABLE')
 def test_lagging(self):
  self.benchmark['metrics']={'Perf.6M':30.,'Perf.Y':40.}
  calculate(self.rows,self.benchmark,self.now);self.assertEqual(self.rows[0]['sector_strength']['status'],'LAGGING')
class PlanTests(unittest.TestCase):
 def setUp(self):
  self.now=time.time();self.row=dict(price=98.,reported_ath=100.,eligible=True,market_bar_at='session',metrics={'ATR':2.,'time':self.now})
 def test_tick_aligned_2r(self):
  p=plan(self.row,.05,self.now)
  self.assertEqual(p['entry'],100.05);self.assertEqual(p['stoploss'],96.05);self.assertEqual(p['target'],108.05);self.assertEqual(p['reward_risk'],2.)
 def test_missing_atr(self):
  self.row['metrics']['ATR']=None;self.assertEqual(plan(self.row,.05,self.now)['status'],'UNAVAILABLE')
 def test_unrepresentable_tick(self):self.assertEqual(plan(self.row,.001,self.now)['status'],'UNAVAILABLE')
 def test_negative_stop(self):
  self.row['metrics']['ATR']=100;self.assertEqual(plan(self.row,.05,self.now)['status'],'UNAVAILABLE')
 def test_excluded_candidate(self):
  self.row['eligible']=False;self.assertEqual(plan(self.row,.05,self.now)['status'],'OUTSIDE_SCREEN_RULES')
if __name__=='__main__':unittest.main()

