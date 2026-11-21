import json,tempfile,unittest
from pathlib import Path
from sector_heatmap.restart_state_read import read_runtime_state
from sector_heatmap.workspace_bounce import reload_states
from sector_heatmap.service_restart import stopped_state_paths
class BoundedRestartTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.path=self.root/'.private/renko-delta-state.json';self.path.parent.mkdir()
  self.value=dict(schema=1,status='STOPPED',running=False,accepting_entries=False,position=None,pending=None,config=dict(strategy='RENKO_SUPERTREND_V1'),renko_engine=dict(state={},identity={},last={},rows=[]),events=['x'*10000]*410)
 def write(self):self.path.write_text(json.dumps(self.value))
 def test_same_validation_and_no_history_mutation(self):
  self.write();before=self.path.read_bytes()
  self.assertEqual(stopped_state_paths(self.root),[self.path])
  paths,drains=reload_states(self.root,'DELTA_INDIA');self.assertEqual(paths,[self.path]);self.assertEqual(drains,{})
  self.assertEqual(self.path.read_bytes(),before)
 def test_active_or_owned_exposure_is_never_accepted(self):
  for key,value in [('running',True),('accepting_entries',True),('position',{'qty':1}),('pending',{'order_id':'x'}),('positions',[{'qty':1}]),('active',True),('loop_running',True)]:
   old=dict(self.value);self.value[key]=value;self.write()
   with self.assertRaises(ValueError):stopped_state_paths(self.root)
   # No large-state Paper Stop escape: it still uses verified recovery identity.
   with self.assertRaises(ValueError):reload_states(self.root,'DELTA_INDIA')
   self.value=old
 def test_unknown_schema_status_or_missing_lifecycle_fails_closed(self):
  for key,value in [('schema',2),('schema',True),('status','UNKNOWN'),('running',None)]:
   old=dict(self.value);self.value[key]=value;self.write()
   with self.assertRaises(ValueError):read_runtime_state(self.path,self.root)
   self.value=old
  del self.value['pending'];self.write()
  with self.assertRaises(ValueError):read_runtime_state(self.path,self.root)
 def test_symlink_file_and_parent_directory_are_rejected(self):
  self.write();actual=self.root/'actual.json';actual.write_bytes(self.path.read_bytes());self.path.unlink();self.path.symlink_to(actual)
  with self.assertRaises(ValueError):read_runtime_state(self.path,self.root)
  self.path.unlink();self.path.parent.rmdir();actual_dir=self.root/'actual';actual_dir.mkdir();(actual_dir/self.path.name).write_bytes(actual.read_bytes());self.path.parent.symlink_to(actual_dir,target_is_directory=True)
  with self.assertRaises(ValueError):read_runtime_state(self.path,self.root)
 def test_outside_native_roots_is_rejected(self):
  self.write();outside=self.root/'outside.json';outside.write_text('{}')
  with self.assertRaises(ValueError):read_runtime_state(outside,self.root)
 def test_malformed_duplicate_nonfinite_and_size_cap(self):
  for text in ('{','[]','{"running":false,"running":true}','{"value":NaN}'):
   self.path.write_text(text)
   with self.assertRaises(ValueError):read_runtime_state(self.path,self.root)
  self.path.write_bytes(b' '*16000001)
  with self.assertRaisesRegex(ValueError,'Oversized'):read_runtime_state(self.path,self.root)
 def test_bounded_shape_depth_and_rows(self):
  self.value['renko_engine']['rows']=[{}];self.write()
  with self.assertRaises(ValueError):read_runtime_state(self.path,self.root)
  self.value['renko_engine']['rows']=[]
  deep={}
  for _ in range(50):deep={'next':deep}
  self.value['deep']=deep;self.write()
  with self.assertRaisesRegex(ValueError,'structure'):read_runtime_state(self.path,self.root)

 def test_large_paper_recovery_cannot_bypass_flat_guard(self):
  from unittest.mock import patch
  self.value['position']={'qty':1};self.write()
  with patch('strategies.renko_supertrend.stop_recovery.paper_stop_identity',return_value={'valid':'identity'}) as recovery:
   with self.assertRaisesRegex(ValueError,'stopped, flat'):reload_states(self.root,'DELTA_INDIA')
   recovery.assert_not_called()
 def test_file_change_during_inspection_fails_closed(self):
  from unittest.mock import patch
  import os
  self.write();original=os.fstat;calls=[]
  def changed(fd):
   value=original(fd);calls.append(1)
   if len(calls)==2:
    with self.path.open('ab') as out:out.write(b' ')
   return value
  with patch('sector_heatmap.restart_state_read.os.fstat',side_effect=changed):
   with self.assertRaisesRegex(ValueError,'changed'):read_runtime_state(self.path,self.root)
