import json
from pathlib import Path
import tempfile
import unittest
from .service_restart import stopped_state_paths, stopped_runtime
from .workspace_bounce import stopped_states

class RestartStateGuardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.folder=Path(self.tmp.name);self.source=self.folder/'source'
  self.private=self.source/'.private';self.private.mkdir(parents=True)
 def put(self,rel,data):
  p=self.folder/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data));return p
 def test_archived_jobs_backups_nested_accounts_and_large_research_do_not_block(self):
  current=self.put('source/.private/renko/state.json',{'running':False})
  for directory in ('state.jobs','backup-old','snapshot','stage','history','cache','evidence','deploy-copy'):
   self.put('source/.private/renko/'+directory+'/state.json',{'running':True,'position':{'quantity':1}})
  self.put('source/.private/dashboard-login/accounts/another/source/.private/renko/state.json',{'running':True})
  p=self.private/'research.json';p.write_text('x'*4000001)
  for guard in (stopped_states,stopped_state_paths):
   self.assertEqual(guard(self.source),[current])
  stopped_runtime(self.source)
 def test_operational_audit_captures_do_not_own_runners(self):
  current=self.put('source/.private/renko-instances/current/state.json',{'running':False})
  for rel in ('fyers-reconciliation-reload-20261022/original-state.json',
              'fyers-reconciliation-reload-20261022/quiesced-original-state.json',
              'momentum-proximity-1792734445/activation/active-paper-state.json'):
   self.put('source/.private/'+rel,{'running':True,'position':{'quantity':1}})
  self.assertEqual(stopped_state_paths(self.source),[current])
 def test_all_current_ownership_flags_block_both_restart_paths(self):
  p=self.put('source/.private/renko/state.json',{})
  for key in ('running','accepting_entries','position','positions','pending','active','loop_running'):
   p.write_text(json.dumps({key:True,'config':{'underlying':'BTCUSD','mode':'PAPER'}}))
   for guard in (stopped_states,stopped_runtime):
    with self.subTest(key=key,guard=guard.__name__):
     with self.assertRaisesRegex(ValueError,'BTCUSD.*PAPER.*No restart was sent'):
      guard(self.source)
 def test_native_dhan_and_motilal_positions_are_checked(self):
  for name in ('dhan-strategies','motilal-strategies'):
   p=self.put(name+'/renko/test/state.json',{'position':{'quantity':1}})
   for guard in (stopped_states,stopped_runtime):
    with self.assertRaises(ValueError):guard(self.source)
   p.unlink()
 def test_unreadable_nonobject_and_oversized_current_states_fail_closed(self):
  p=self.put('source/.private/renko/state.json',{})
  for raw in ('{','[]','x'*4000001):
   p.write_text(raw)
   for guard in (stopped_states,stopped_runtime):
    with self.assertRaises(ValueError):guard(self.source)
 def test_nonstandard_authoritative_legacy_states_checked(self):
  for name in ('delta-india-live.json','delta-india-paper.json','kama-chart.json'):
   p=self.put('source/.private/'+name,{'running':True})
   with self.assertRaises(ValueError):stopped_states(self.source)
   p.unlink()
 def test_stopped_lock_paths_preserved_and_reads_do_not_modify_state(self):
  p=self.put('source/.private/renko/state.json',{'running':False,'order_history':[{'id':1}]})
  before=p.read_bytes();self.assertEqual(stopped_states(self.source),[p]);self.assertEqual(p.read_bytes(),before)
