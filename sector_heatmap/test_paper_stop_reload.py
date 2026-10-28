import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from sector_heatmap.workspace_bounce import reload_states
from sector_heatmap.service_restart import stopped_state_paths
from strategies.renko_supertrend.stop_recovery import paper_stop_identity

def state():
 return dict(schema=1,status="DRAINING",running=True,accepting_entries=False,squareoff_requested=True,run_id="run",account_identity="account",
  config=dict(mode="PAPER",broker="DELTA_INDIA",strategy_basis="RENKO",renko_confirmation="PRICE",underlying="BTCUSD"),
  position=dict(symbol="C-BTC",quantity=1,run_id="run",underlying_symbol="BTCUSD",entry_event_at=100,exit_requested=True,exit_reason="MANUAL_SQUARE_OFF"),
  pending=None,order_history=[dict(run_id="run",is_entry=True,symbol="C-BTC",entry_event_at=100,mode="PAPER",status="FILLED",paper_order_id="PAPER-1",order_id=None)])

class PaperStopReloadTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.source=Path(self.tmp.name)/"source";self.path=self.source/".private/renko-delta-instances/test/renko-delta-state.json";self.path.parent.mkdir(parents=True)
 def save(self,s):self.path.write_text(json.dumps(s))
 def test_only_broker_scoped_reload_can_continue_existing_paper_stop(self):
  self.save(state());before=self.path.read_bytes()
  paths,drains=reload_states(self.source,"DELTA_INDIA")
  self.assertEqual(paths,[self.path]);self.assertEqual(drains[self.path]["run_id"],"run");self.assertEqual(self.path.read_bytes(),before)
  with self.assertRaises(ValueError):stopped_state_paths(self.source)
 def test_other_active_state_blocks_even_with_eligible_paper_drain(self):
  self.save(state());other=self.source/".private/delta-india-live.json";other.write_text(json.dumps(dict(running=True,config=dict(mode="LIVE"))))
  with self.assertRaises(ValueError):reload_states(self.source,"DELTA_INDIA")
 def test_fail_closed_on_pending_live_wrong_identity_and_new_entry_authority(self):
  changes=[lambda s:s["config"].update(mode="LIVE"),lambda s:s.update(accepting_entries=True),lambda s:s.update(squareoff_requested=False),lambda s:s.update(pending={"tag":"uncertain"}),lambda s:s["position"].update(run_id="other"),lambda s:s["position"].update(exit_reason="TAKE_PROFIT"),lambda s:s["order_history"][0].update(order_id="REAL-ID"),lambda s:s.update(order_history=[])]
  for change in changes:
   s=state();change(s);self.save(s)
   with self.assertRaises(ValueError):reload_states(self.source,"DELTA_INDIA")
 def test_non_delta_and_noncanonical_runtime_cannot_use_paper_exception(self):
  self.save(state())
  with self.assertRaises(ValueError):reload_states(self.source,"FYERS")
  original=self.path;self.path=self.source/".private/other/state.json";self.path.parent.mkdir();self.save(state());original.unlink()
  with self.assertRaises(ValueError):reload_states(self.source,"DELTA_INDIA")
 def test_reload_identity_ignores_heartbeat_but_detects_contract_quantity_or_config_changes(self):
  s=state();baseline=paper_stop_identity(s);s["updated_at"]=999;s["events"]=[{"at":999}];self.assertEqual(paper_stop_identity(s),baseline)
  for section,key,value in [("position","quantity",2),("config","underlying","ETHUSD")]:
   changed=deepcopy(s);changed[section][key]=value
   try:self.assertNotEqual(paper_stop_identity(changed),baseline)
   except ValueError:pass
