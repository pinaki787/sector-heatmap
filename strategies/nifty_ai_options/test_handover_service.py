import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from ui_bridge import Service
class HandoverServiceTests(unittest.TestCase):
 def fixture(self,directory):
  service=Service.__new__(Service);service.lock=threading.RLock();service.cancelled=False;service.error=None;service.owner='a'*32;service.launching=False
  child=Mock();child.poll.return_value=1;service.process=child;service.run=dict(id='run',directory=directory,mode='PAPER')
  command=dict(request_id='request',phase='READY_TO_HANDOVER',runtime_session='old',target_config=dict(account='a'*32,underlying='ETHUSD',runtime_session='old'))
  (directory/'reconfigure.json').write_text(json.dumps(command))
  (directory/'heartbeat.json').write_text(json.dumps(dict(terminal=True,position=None,pending=None,runtime_session='old')))
  return service,child
 def test_only_flat_old_child_can_launch_and_ready_target_is_acknowledged(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);service,child=self.fixture(directory)
   def launch(path,live):
    self.assertFalse(live);self.assertEqual(path,directory)
    target=json.loads((directory/'config.json').read_text());self.assertEqual(target['underlying'],'ETHUSD')
    target['runtime_session']='new';(directory/'config.json').write_text(json.dumps(target))
    (directory/'heartbeat.json').write_text(json.dumps(dict(terminal=False,runtime_session='new')))
    service.process=Mock();service.process.poll.return_value=None
   service._launch=Mock(side_effect=launch)
   service._handover(child,directory,False,'request')
   service._launch.assert_called_once()
   self.assertEqual(json.loads((directory/'reconfigure.json').read_text())['phase'],'APPLIED')
 def test_cancelled_or_replaced_child_never_restarts(self):
  for cancelled in (True,False):
   with self.subTest(cancelled=cancelled),tempfile.TemporaryDirectory() as folder:
    directory=Path(folder);service,child=self.fixture(directory);service.cancelled=cancelled
    if not cancelled:service.process=Mock()
    service._launch=Mock();service._handover(child,directory,False,'request');service._launch.assert_not_called()
 def test_owned_or_pending_terminal_state_blocks_handover(self):
  for heartbeat in (dict(position={'symbol':'BTCUSD'},pending=None),dict(position=None,pending={'id':'unknown'})):
   with self.subTest(heartbeat=heartbeat),tempfile.TemporaryDirectory() as folder:
    directory=Path(folder);service,child=self.fixture(directory)
    (directory/'heartbeat.json').write_text(json.dumps(dict(heartbeat,terminal=True)))
    service._launch=Mock();service._handover(child,directory,False,'request');service._launch.assert_not_called()
    self.assertEqual(json.loads((directory/'reconfigure.json').read_text())['phase'],'REJECTED')
 def test_revoked_live_capability_never_launches(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);service,child=self.fixture(directory);service._launch=Mock()
   with patch('ui_bridge.live_capability',return_value=False):service._handover(child,directory,True,'request')
   service._launch.assert_not_called()
 def test_target_failure_is_not_reported_as_applied(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);service,child=self.fixture(directory)
   service._launch=Mock(side_effect=lambda *args:setattr(service,'error','preflight rejected'))
   service._handover(child,directory,False,'request')
   receipt=json.loads((directory/'reconfigure.json').read_text())
   self.assertEqual(receipt['phase'],'REJECTED');self.assertIn('preflight',receipt['error'])

 def test_stop_without_exact_saved_context_never_terminates_a_worker(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);service,child=self.fixture(directory)
   with self.assertRaisesRegex(ValueError,'configuration unavailable'):service.stop(dict(run_id='run'))
   child.terminate.assert_not_called()

 def preparing_fixture(self,directory):
  service,child=self.fixture(directory);child.poll.return_value=None;service.run['id']=directory.name
  config=dict(account='a'*32,broker='DELTA_INDIA',underlying='BTCUSD',runtime_session='old',execution_route='DIRECT',execution_mode='PAPER',timeframe=5,lots=1,product='MARGIN',sma_exit_enabled=False)
  (directory/'config.json').write_text(json.dumps(config))
  service.snapshot=Mock(return_value=dict(running=True,heartbeat_age=0,heartbeat=dict(runtime_session='old',reconfigure_capable=True)))
  payload=dict(account_id='a'*32,broker='DELTA_INDIA',run_id=directory.name,runtime_session='old',underlying='ETHUSD',timeframe=5,confirmed=True)
  return service,child,config,payload
 def test_stop_cancels_preparation_but_never_terminates_instead_of_square_off(self):
  from manual_entry import runtime_identity
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);service,child,config,payload=self.preparing_fixture(directory)
   config['runtime_session']='b'*32
   (directory/'config.json').write_text(json.dumps(config))
   service.snapshot.return_value['heartbeat']['runtime_session']=config['runtime_session']
   payload['runtime_session']=config['runtime_session']
   service.position_action=Mock(return_value=dict(queued=True))
   def ensure(target):
    self.assertEqual(json.loads((directory/'reconfigure.json').read_text())['phase'],'PREPARING_TARGET')
    service.stop(dict(runtime_identity(config,directory,'PAPER'),operation='STOP',request_id='c'*32))
    return target
   with patch('native_sizing.ensure',side_effect=ensure),patch('ui_bridge.option_preview',return_value=dict(direct=dict(product_type='PERPETUAL'))),self.assertRaisesRegex(ValueError,'cancelled'):
    service.reconfigure(payload)
   child.terminate.assert_not_called()
   service.position_action.assert_called_once()
   self.assertEqual(json.loads((directory/'reconfigure.json').read_text())['phase'],'CANCELLED')

 def test_target_failure_is_audited_and_does_not_leave_old_entries_permanently_paused(self):
  with tempfile.TemporaryDirectory() as folder:
   directory=Path(folder);service,child,config,payload=self.preparing_fixture(directory)
   with patch('native_sizing.ensure',side_effect=ValueError('fixture unavailable')),self.assertRaisesRegex(ValueError,'unavailable'):
    service.reconfigure(payload)
   self.assertEqual(json.loads((directory/'reconfigure.json').read_text())['phase'],'REJECTED')
   child.terminate.assert_not_called()
