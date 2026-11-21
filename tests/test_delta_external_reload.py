import unittest
from copy import deepcopy
from unittest.mock import patch,Mock
from pathlib import Path
from strategies.renko_supertrend.delta_external_close import stopped_external_identity

class DeltaExternalReloadTests(unittest.TestCase):
 def setUp(self):
  self.state=dict(schema=1,run_id='run',account_identity='account',squareoff_requested=True,accepting_entries=False,
   config=dict(mode='LIVE',broker='DELTA_INDIA',underlying='ETHUSD'),
   position=dict(run_id='run',underlying_symbol='ETHUSD',exit_requested=True,exit_reason='MANUAL_SQUARE_OFF',
                 symbol='C-ETH',product_id=1,quantity=10,entry_order_id='entry',opened_at=100))
 def identity(self,state):
  with patch('sector_heatmap.delta_india.DeltaIndia') as delta,patch('strategies.renko_supertrend.delta_execution.Execution'),patch('strategies.renko_supertrend.delta_external_close.read_evidence',return_value={'order_id':'exit'}) as read:
   result=stopped_external_identity(Path('/tmp/test-source'),state)
   self.assertEqual(read.call_count,2)
   return result
 def test_already_requested_live_stop_gets_proof(self):
  self.assertEqual(self.identity(self.state)['kind'],'DELTA_EXTERNAL_CLOSE_STOP')
 def test_new_activation_and_other_exposure_cannot_use_exception(self):
  for key,value in [('accepting_entries',True),('squareoff_requested',False),('account_identity',None),
                    ('positions',[{}]),('pending',{'id':'unresolved'})]:
   state=deepcopy(self.state);state[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.identity(state)
  for key,value in [('run_id','other'),('exit_requested',False),('exit_reason','OTHER')]:
   state=deepcopy(self.state);state['position'][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.identity(state)
 def test_changing_fill_evidence_blocks_reload(self):
  with patch('sector_heatmap.delta_india.DeltaIndia'),patch('strategies.renko_supertrend.delta_execution.Execution'),patch('strategies.renko_supertrend.delta_external_close.read_evidence',side_effect=[{'order_id':'a'},{'order_id':'b'}]),self.assertRaises(ValueError):
   stopped_external_identity(Path('/tmp/test-source'),self.state)
