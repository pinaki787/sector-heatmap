import tempfile,unittest,json
from pathlib import Path
from types import SimpleNamespace
from reversal import remember,advance
class ReversalTests(unittest.TestCase):
 def setup(self):
  e=SimpleNamespace(config=dict(runtime_session='run',account='owner',supertrend_enabled=True),pending_direction=('SHORT',100),contract=dict(symbol='FUT'),under_result=dict(direction=1),position=None,entry_paused=False)
  e.selected_gate_entry=lambda:dict(action='OPEN_SHORT',timestamp=100,position=dict(symbol='FUT',side='SHORT',entry_timestamp=100))
  x=SimpleNamespace(state=dict(position=dict(symbol='FUT',side='LONG',quantity=1),pending=None),save=lambda:None)
  a=dict(action='CLOSE_LONG',timestamp=100,position=dict(symbol='FUT',side='LONG'))
  return e,x,a
 def test_opposite_signal_survives_close_wait_without_duplicate_or_overlap(self):
  e,x,a=self.setup();remember(e,x,a);x.state['pending']=dict(stage='SUBMITTED')
  sent=[]
  self.assertIsNone(advance(e,x,lambda a:sent.append(a)));self.assertEqual(sent,[])
  x.state=json.loads(json.dumps(x.state));e.pending_direction=None
  x.state.update(position=None,pending=None)
  def submit(action):
   sent.append(action);x.state['position']=action['position'];return dict(fill_price=100)
  advance(e,x,submit);advance(e,x,submit)
  self.assertEqual([a['action'] for a in sent],['OPEN_SHORT']);self.assertIsNone(x.state['pending_reversal'])
 def test_new_run_and_invalidated_trend_do_not_replay_signal(self):
  for change in ('run','trend'):
   e,x,a=self.setup();remember(e,x,a);x.state['position']=None
   if change=='run':e.config['runtime_session']='new'
   else:e.under_result=dict(direction=-1)
   sent=[];advance(e,x,lambda a:sent.append(a))
   self.assertEqual(sent,[]);self.assertIsNone(x.state['pending_reversal'])
 def test_uncertain_entry_is_never_retried(self):
  e,x,a=self.setup();remember(e,x,a);x.state['position']=None;sent=[]
  def submit(action):
   sent.append(action);x.state['pending']=dict(stage='UNCERTAIN');raise RuntimeError('unknown')
  with self.assertRaises(RuntimeError):advance(e,x,submit)
  x.state['pending']=None;advance(e,x,submit)
  self.assertEqual(len(sent),1);self.assertEqual(x.state['pending_reversal']['phase'],'ENTRY_UNCERTAIN')
 def test_missing_band_qualification_keeps_signal_without_placing_order(self):
  e,x,a=self.setup();remember(e,x,a);x.state['position']=None;e.selected_gate_entry=lambda:None
  sent=[];advance(e,x,lambda a:sent.append(a))
  self.assertEqual(sent,[]);self.assertEqual(x.state['pending_reversal']['phase'],'WAITING_FOR_ENTRY')

 def test_confirmed_partial_exit_closes_only_residual_before_opposite_entry(self):
  from unittest.mock import patch
  e,x,a=self.setup();remember(e,x,a)
  x.state['position']['quantity']=1
  x.state['retained_exit_failure']=dict(intent=a,stage='PARTIAL_EXIT_REMAINS')
  sent=[]
  def submit(action):
   sent.append(action)
   x.state['position']=None if action['action'].startswith('CLOSE') else action['position']
   return dict(fill_price=100)
  with patch('reversal.time.time',return_value=200):advance(e,x,submit)
  self.assertEqual([r['action'] for r in sent],['CLOSE_LONG']);self.assertEqual(sent[0]['position']['quantity'],1)
  advance(e,x,submit)
  self.assertEqual([r['action'] for r in sent],['CLOSE_LONG','OPEN_SHORT'])
 def test_unknown_exit_is_not_retried_and_precheck_retries_are_throttled(self):
  from unittest.mock import patch
  e,x,a=self.setup();remember(e,x,a);sent=[]
  x.state['retained_exit_failure']=dict(intent=a,stage='UNKNOWN')
  advance(e,x,lambda action:sent.append(action));self.assertEqual(sent,[])
  x.state['retained_exit_failure']['stage']='EXIT_PRECHECK_FAILED'
  with patch('reversal.time.time',return_value=200):
   advance(e,x,lambda action:sent.append(action));advance(e,x,lambda action:sent.append(action))
  self.assertEqual(len(sent),1)
  x.state['pending']=dict(stage='UNCERTAIN')
  with patch('reversal.time.time',return_value=202):advance(e,x,lambda action:sent.append(action))
  self.assertEqual(len(sent),1)
 def test_exit_precheck_failure_retains_ownership_and_a_persistent_notice(self):
  from reversal import execute
  e,x,a=self.setup()
  def send():raise ValueError('Fresh quote unavailable')
  result=execute(e,x,a,send)
  self.assertTrue(result['deferred']);self.assertEqual(x.state['position']['side'],'LONG')
  self.assertEqual(x.state['retained_exit_failure']['stage'],'EXIT_PRECHECK_FAILED')
