import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock
from strategies.nifty_ai_options.runtime_control import enqueue,RuntimeControl

class ExecutionBasisPinTests(unittest.TestCase):
 def config(self,mode):
  return dict(account="a",broker="DELTA_INDIA",runtime_session="session",underlying="BTCUSD",timeframe=5,display_mode=mode,calculation_mode="HYBRID",supertrend_basis="COMPLETED_RENKO",exit_confirmation_mode="RENKO_BRICKS_ONLY" if mode=="RENKO" else "HYBRID_COMPLETED_UNITS",indicator_length=1 if mode=="RENKO" else 14,indicator_factor=2.1 if mode=="RENKO" else 3)
 def payload(self,c,directory,**change):
  return dict(account_id=c["account"],broker=c["broker"],runtime_session=c["runtime_session"],run_id=Path(directory).name,underlying=c["underlying"],timeframe=c["timeframe"],**change)
 def test_both_started_bases_refuse_view_mutation_before_queue_write(self):
  for mode,other in [("RENKO","CANDLES"),("CANDLES","RENKO")]:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
    c=self.config(mode);before=dict(c)
    with self.assertRaisesRegex(ValueError,"pinned"):enqueue(d,c,self.payload(c,d,display_mode=other))
    self.assertEqual(c,before);self.assertFalse(Path(d,"reconfigure.json").exists())
 def test_old_or_forged_queued_view_change_is_rejected_without_callbacks(self):
  for mode,other in [("RENKO","CANDLES"),("CANDLES","RENKO")]:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
    c=self.config(mode);before=dict(c);apply=Mock();apply_mode=Mock()
    command=dict(self.payload(c,d,display_mode=other),request_id="old",phase="QUEUED",requested_at=time.time())
    Path(d,"reconfigure.json").write_text(json.dumps(command))
    control=RuntimeControl(c,d,apply=apply,apply_mode=apply_mode);control.poll(position=True)
    self.assertEqual(c,before);apply.assert_not_called();apply_mode.assert_not_called()
    self.assertEqual(json.loads(Path(d,"reconfigure.json").read_text())["phase"],"REJECTED")
    self.assertFalse(control.entry_blocked)
 def test_timeframe_request_retains_all_captured_basis_fields(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.config("RENKO");before={k:c[k] for k in ("display_mode","calculation_mode","supertrend_basis","exit_confirmation_mode","indicator_length","indicator_factor")}
   payload=self.payload(c,d,display_mode="RENKO");payload["timeframe"]=1
   Path(d,"reconfigure.json").write_text(json.dumps(dict(payload,request_id="same-basis",phase="QUEUED",requested_at=time.time())))
   apply=Mock();apply_mode=Mock();RuntimeControl(c,d,apply=apply,apply_mode=apply_mode).poll()
   apply.assert_called_once_with(1);apply_mode.assert_not_called()
   self.assertEqual({k:c[k] for k in before},before)
 def test_signal_basis_cannot_be_changed_via_handover(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.config("RENKO")
   with self.assertRaisesRegex(ValueError,"pinned"):enqueue(d,c,self.payload(c,d,calculation_mode="CANDLES"),target_config=dict(c,calculation_mode="CANDLES"))
