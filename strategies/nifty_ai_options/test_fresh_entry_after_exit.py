import tempfile,unittest,threading,time
from pathlib import Path
from types import SimpleNamespace
from core import Strategy
from manual_entry import confirmed_flat_entry,runtime_identity
from position_control import enqueue,entry_guard,EntryBlocked
class FreshEntryAfterExitTests(unittest.TestCase):
 def engine(self):
  e=Strategy(dict(reference_value=12,market='NSE',timeframe=1,signal_source='UNDERLYING',entry_gate='underlying_flip',exit_supertrend='underlying'))
  e.reset_contract(dict(symbol='CALL',option_type='CE'),.5)
  for i,price in enumerate([100,98,96,94,92]):e.update(dict(kind='underlying',timestamp=100+i*60,close=price));e.position=None
  e.pending_underlying_flip=None
  return e
 def test_existing_bearish_small_body_closes_call_but_cannot_create_put_entry(self):
  e=self.engine();self.assertEqual(e.under_result['direction'],1);e.manual_entry('CE',1000)
  actions=e.update_hybrid(dict(kind='underlying',timestamp=1020,open=92.5,high=93,low=91,close=92,closed_at=1080,available_at=1081,body_available=True,source_basis='PROVIDER_CONFIRMED_CLOSE'))
  self.assertEqual(actions[0]['action'],'SELL');self.assertNotIn('entry_confirmation',actions[0]);self.assertIsNone(e.pending_underlying_flip)
  e.reset_contract(dict(symbol='PUT',option_type='PE'),-.5)
  self.assertIsNone(confirmed_flat_entry(e,SimpleNamespace(state=dict(position=None,pending=None))))
  self.assertEqual(e.update_hybrid(dict(kind='price',series='underlying',timestamp=1082,close=92)),[])
 def test_real_flip_entry_waits_for_filled_reconciled_exit(self):
  e=self.engine();e.reset_contract(dict(symbol='PUT',option_type='PE'),-.5);e.manual_entry('PE',1000)
  exits=[]
  for i,price in enumerate([94,96,98,100,102,104,106]):
   exits=e.update_hybrid(dict(kind='price',series='underlying',timestamp=1100+i,close=price))
   if exits:break
  self.assertEqual(exits[0]['action'],'SELL');self.assertIn('entry_confirmation',exits[0]);self.assertIsNotNone(e.pending_underlying_flip)
  executor=SimpleNamespace(state=dict(position=dict(exits[0]['position']),pending=None))
  self.assertIsNone(confirmed_flat_entry(e,executor))
  executor.state=dict(position=None,pending=dict(stage='UNRESOLVED_FILL'));self.assertIsNone(confirmed_flat_entry(e,executor))
  executor.state=dict(position=None,pending=None);e.reset_contract(dict(symbol='CALL',option_type='CE'),.5)
  self.assertEqual(confirmed_flat_entry(e,executor)['action'],'BUY')
 def test_stop_acceptance_and_entry_submission_are_serialized(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);c=dict(account='a'*32,broker='FYERS',underlying='MCX:CRUDEOILM26DECFUT',execution_mode='LIVE',execution_route='OPTIONS',timeframe=1,runtime_session='b'*32)
   executor=SimpleNamespace(state=dict(position=None,pending=None));accepted=threading.Event()
   payload=dict(runtime_identity(c,root,'LIVE'),operation='STOP',request_id='c'*32)
   def stop():enqueue(root,c,payload);accepted.set()
   with entry_guard(root,executor):
    thread=threading.Thread(target=stop);thread.start()
    self.assertFalse(accepted.wait(.03),'Stop must not be acknowledged while an earlier entry submission owns the boundary')
   self.assertTrue(accepted.wait(1));thread.join()
   with self.assertRaises(EntryBlocked):
    with entry_guard(root,executor):self.fail('Entry cannot begin after accepted Stop')
if __name__=='__main__':unittest.main()
