import time
from unittest.mock import patch
from tests.test_investment_http import InvestmentHTTPTests
class SeasonalityHTTPTests(InvestmentHTTPTests):
 def test_seasonality_assignment_and_visibility(self):
  path='/api/investment/seasonality/analyze';payload={'symbol':'NSE:KOTAKBANK-EQ'}
  self.assertEqual(self.request(path,payload,{'X-Test-Deny':'1'})[0],403)
  self.auth.store.visible=False
  self.assertEqual(self.request(path,payload)[0],403)
 def test_async_owner_scoped_seasonal_output(self):
  with patch('sector_heatmap.seasonality.fetch_public',return_value={'schema':'seasonality/v1','symbol':'NSE:KOTAKBANK'}):
   status,accepted=self.request('/api/investment/seasonality/analyze',{'symbol':'NSE:KOTAKBANK-EQ'})
   self.assertEqual(status,202)
   for _ in range(100):
    _,job=self.request('/api/jobs?job_id='+accepted['job_id'])
    if job.get('terminal'):break
    time.sleep(.01)
   self.assertEqual(job['status'],'COMPLETED');self.assertEqual(job['output']['schema'],'seasonality/v1')
   self.assertEqual(self.request('/api/jobs?job_id='+accepted['job_id'],headers={'X-Test-Owner':'other'})[0],403)
 def test_no_unidentified_symbol(self):self.assertEqual(self.request('/api/investment/seasonality/analyze',{'symbol':'BTCUSD'})[0],409)
 def test_holding_section_cannot_be_reached_with_investment_only(self):
  payload={'broker':'DHAN','review_job_id':'b'*32,'row_id':'0'}
  self.assertEqual(self.request('/api/dhan/holdings-analysis/seasonality/analyze',payload)[0],403)
