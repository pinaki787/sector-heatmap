import unittest,tempfile,json
from pathlib import Path
from sector_heatmap.service_restart import stopped_state_paths
class LargeStateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.file=self.root/'.private/renko-delta-state.json';self.file.parent.mkdir()
  self.state={'schema':1,'status':'STOPPED','running':False,'accepting_entries':False,'position':None,'pending':None,'config':{'strategy':'RENKO_SUPERTREND_V1'},'renko_engine':{'state':{},'identity':{},'last':{},'rows':[]},'history':['x'*10000]*410}
 def write(self):self.file.write_text(json.dumps(self.state))
 def test_typed_stopped_renko_history_is_preserved(self):
  self.write();before=self.file.read_bytes();self.assertEqual(stopped_state_paths(self.root),[self.file]);self.assertEqual(self.file.read_bytes(),before)
 def test_active_exposure_and_pending_still_block(self):
  self.state['status']='SIDEWAYS_LOCKED'
  self.write();self.assertEqual(stopped_state_paths(self.root),[self.file])
  for key in ['running','accepting_entries','position','positions','pending','active','loop_running']:
   before=dict(self.state);self.state[key]=({'id':'exposure'} if key in ('position','pending') else True);self.write()
   with self.assertRaisesRegex(ValueError,'Restart blocked'):stopped_state_paths(self.root)
   self.state=before
 def test_unsupported_large_state_remains_blocked(self):
  self.state['config']['strategy']='UNKNOWN';self.write()
  with self.assertRaisesRegex(ValueError,'unsupported'):stopped_state_paths(self.root)
 def test_excessive_size_remains_blocked(self):
  self.state['history']='x'*16000001;self.write()
  with self.assertRaisesRegex(ValueError,'Oversized'):stopped_state_paths(self.root)
