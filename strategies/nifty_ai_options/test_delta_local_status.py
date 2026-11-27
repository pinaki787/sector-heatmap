import unittest,copy
from strategies.nifty_ai_options.delta_local_status import resolved
class LocalStatus(unittest.TestCase):
 def fixture(self):
  c=dict(broker='DELTA_INDIA',account='owner',underlying='PAXGUSD',runtime_session='session')
  r=dict(phase='LOCAL_REJECTION_CONFIRMED',account_id='owner',run_id='run',symbol='PAXGUSD',runtime_session='session',key='exact',completed_at=100,broker_flat=True,orders_submitted=0)
  o=dict(position=None,pending=None,reconciled_intents=[dict(key='exact',phase='LOCAL_REJECTION_CONFIRMED',broker_flat=True,orders_submitted=0,at=99)])
  return r,c,o
 def test_exact_audited_zero_submission_recovery(self):
  r,c,o=self.fixture();self.assertTrue(resolved(r,'owner','run',c,o))
 def test_unresolved_or_different_run_never_hidden(self):
  for key,value in [('pending',{'key':'uncertain'}),('position',{'quantity':1}),('closing_legs',{'x':{'quantity':1}}),('reconciled_intents',[])]:
   r,c,o=self.fixture();o[key]=value;self.assertFalse(resolved(r,'owner','run',c,o))
  for key,value in [('account_id','other'),('run_id','other'),('runtime_session','other'),('key','other'),('symbol','ETHUSD'),('orders_submitted',1),('broker_flat',False),('completed_at',float('nan'))]:
   r,c,o=self.fixture();r[key]=value;self.assertFalse(resolved(r,'owner','run',c,o))
