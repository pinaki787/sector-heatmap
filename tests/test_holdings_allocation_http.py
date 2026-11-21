import time
from unittest.mock import patch
from tests.test_investment_http import InvestmentHTTPTests
class HoldingsAllocationHTTPTests(InvestmentHTTPTests):
 def test_assignment_hidden_owner_and_parent_binding(self):
  path='/api/dhan/holdings-analysis/sectors/analyze'
  payload={'review_job_id':'missing','account_id':'account','broker':'DHAN'}
  self.auth.store.account=lambda user,account: {'id':account}
  self.auth.authorize=lambda headers,mutation=False:{'id':headers.get('X-Test-Owner','owner'),'admin':False,'features':['holdings']}
  self.assertEqual(self.request(path,payload)[0],403)
  self.auth.authorize=lambda headers,mutation=False:{'id':headers.get('X-Test-Owner','owner'),'admin':False,'features':['holdings','holdings-allocation']}
  self.auth.store.sidebar_visibility=lambda:{'holdings':True,'holdings-allocation':False}
  self.assertEqual(self.request(path,payload)[0],403)
  self.auth.store.sidebar_visibility=lambda:{'holdings':True,'holdings-allocation':True}
  parent=self.store.submit('owner:account','ANALYSIS','holdings','Review',{},lambda context:{'account_id':'account','broker':'DHAN','rows':[{'id':'r','symbol':'NSE:TECHM-EQ','kind':'DELIVERY_EQUITY'}]},'parent')
  for _ in range(100):
   parent=self.store.get('owner:account',parent['job_id'])
   if parent['terminal']:break
   time.sleep(.01)
  payload['review_job_id']=parent['job_id']
  with patch('sector_heatmap.holdings_sectors.lookup',return_value={'schema':'holdings-sectors/v1','classifications':{}}) as lookup:
   status,job=self.request(path,payload);self.assertEqual(status,202)
   for _ in range(100):
    _,job=self.request('/api/jobs?account_id=account&job_id='+job['job_id'])
    if job['terminal']:break
    time.sleep(.01)
   self.assertEqual(job['status'],'COMPLETED')
   self.assertEqual(lookup.call_count,1)
   # A different user cannot read the result or obtain the saved parent.
   self.assertEqual(self.request('/api/jobs?account_id=account&job_id='+job['job_id'],headers={'X-Test-Owner':'other'})[0],403)
   status,wrong=self.request(path,{**payload,'broker':'FYERS'});self.assertEqual(status,202)
   for _ in range(100):
    _,wrong=self.request('/api/jobs?account_id=account&job_id='+wrong['job_id'])
    if wrong['terminal']:break
    time.sleep(.01)
   self.assertEqual(wrong['status'],'FAILED');self.assertEqual(lookup.call_count,1)
