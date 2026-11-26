import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from runtime_control import enqueue,RuntimeControl
class RuntimeControlTests(unittest.TestCase):
 def setup(self,directory):
  config=dict(account='a'*32,broker='DELTA_INDIA',runtime_session='b'*32,underlying='BTCUSD',timeframe=5)
  payload=dict(account_id=config['account'],broker=config['broker'],runtime_session=config['runtime_session'],run_id=Path(directory).name,underlying='BTCUSD',timeframe=1)
  return config,payload
 def test_change_waits_for_pending_action_then_applies_once(self):
  with tempfile.TemporaryDirectory() as directory:
   config,payload=self.setup(directory);enqueue(directory,config,payload)
   apply=Mock();control=RuntimeControl(config,directory,apply=apply)
   control.poll(busy=True);apply.assert_not_called();self.assertEqual(config['timeframe'],5)
   control.poll();control.poll();apply.assert_called_once_with(1)
   self.assertEqual(json.loads(Path(directory,'config.json').read_text())['timeframe'],1)
   self.assertEqual(json.loads(Path(directory,'reconfigure.json').read_text())['phase'],'APPLIED')
 def test_wrong_session_or_symbol_never_changes_active_state(self):
  with tempfile.TemporaryDirectory() as directory:
   config,payload=self.setup(directory)
   for patch in [dict(runtime_session='c'*32),dict(account_id='d'*32),dict(underlying='ETHUSD'),dict(timeframe=True)]:
    with self.subTest(patch=patch),self.assertRaises(ValueError):enqueue(directory,config,dict(payload,**patch))
   self.assertFalse(Path(directory,'reconfigure.json').exists())
 def test_latest_queued_request_supersedes_older_request(self):
  with tempfile.TemporaryDirectory() as directory:
   config,payload=self.setup(directory);enqueue(directory,config,payload);enqueue(directory,config,dict(payload,timeframe=30))
   apply=Mock();RuntimeControl(config,directory,apply=apply).poll();apply.assert_called_once_with(30)

 def test_instrument_handover_waits_for_flat_and_never_mutates_old_config(self):
  from runtime_control import HandoverReady
  with tempfile.TemporaryDirectory() as directory:
   config,payload=self.setup(directory);target=dict(config,underlying='ETHUSD')
   enqueue(directory,config,dict(payload,underlying='ETHUSD'),target_config=target)
   apply=Mock();control=RuntimeControl(config,directory,apply=apply)
   control.poll(position=True);self.assertTrue(control.entry_blocked);apply.assert_not_called()
   self.assertEqual(config['underlying'],'BTCUSD')
   control.poll(busy=True,position=False)
   with self.assertRaises(HandoverReady):control.poll(position=False)
   self.assertEqual(json.loads(Path(directory,'reconfigure.json').read_text())['phase'],'READY_TO_HANDOVER')
   self.assertEqual(config['underlying'],'BTCUSD')
 def test_handover_cannot_change_account_mode_quantity_or_optional_exits(self):
  with tempfile.TemporaryDirectory() as directory:
   config,payload=self.setup(directory)
   for key,value in [('account','other'),('execution_mode','LIVE'),('lots',99),('sma_exit_enabled',True)]:
    with self.subTest(key=key),self.assertRaises(ValueError):
     enqueue(directory,config,dict(payload,underlying='ETHUSD'),target_config=dict(config,underlying='ETHUSD',**{key:value}))

 def test_preparation_pauses_entries_without_applying_or_exiting_then_rejection_unpauses(self):
  from run import atomic
  with tempfile.TemporaryDirectory() as directory:
   config,payload=self.setup(directory)
   command=enqueue(directory,config,dict(payload,underlying='ETHUSD'),target_config=dict(config,underlying='ETHUSD'),preparing=True)
   apply=Mock();control=RuntimeControl(config,directory,apply=apply)
   control.poll(position=False);self.assertTrue(control.entry_blocked);apply.assert_not_called()
   self.assertFalse(Path(directory,'handover-ready.json').exists())
   atomic(Path(directory)/'reconfigure.json',dict(command,phase='REJECTED'))
   control.poll();self.assertFalse(control.entry_blocked)
