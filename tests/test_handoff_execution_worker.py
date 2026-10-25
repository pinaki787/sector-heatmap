import json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from sector_heatmap.handoff_execution_worker import Worker

class TicketWorkerTests(unittest.TestCase):
 def make(self,root,mode="AUTO"):
  worker=object.__new__(Worker);worker.aid="owned";worker.folder=root;worker.schedule=root/"handoff-schedule.sqlite3"
  worker.account=dict(broker="FYERS");worker.live_gate=lambda:True
  worker.service=Mock()
  fingerprint="a"*64
  plan=dict(symbol="NSE:TEST-EQ",quantity=10,kind="EQUITY",stop=95,target=108)
  with sqlite3.connect(worker.schedule) as db:
   db.execute("CREATE TABLE policy(id INTEGER,body TEXT)")
   db.execute("INSERT INTO policy VALUES(1,?)",(json.dumps(dict(enabled=True,mode=mode,live_authorized=True,broker="FYERS",capital=100000)),))
   db.execute("CREATE TABLE loss_halts(day TEXT PRIMARY KEY,observed REAL,created REAL)")
   db.execute("CREATE TABLE receipts(fingerprint TEXT,state TEXT,body TEXT)")
   db.execute("INSERT INTO receipts VALUES(?,?,?)",(fingerprint,"SUBMITTING",json.dumps(dict(plan=plan))))
  with sqlite3.connect(worker.schedule.with_suffix(".claims.sqlite3")) as db:
   db.execute("CREATE TABLE claims(account TEXT,fingerprint TEXT,underlying TEXT,amount TEXT,state TEXT)")
   db.execute("INSERT INTO claims VALUES(?,?,?,?,?)",("owned",fingerprint,"NSE:TEST-EQ","1000","RESERVED"))
  (root/"handoff-intents").mkdir()
  (root/"handoff-intents"/(fingerprint+".json")).write_text(json.dumps(dict(preview_id="preview",account_id="owned")))
  preview=dict(underlying="NSE:TEST-EQ",instrument=dict(kind="EQUITY",contracts=[dict(symbol="NSE:TEST-EQ",quantity=10,limit_price=100,tick_size=.05)]),protection=dict(stop_loss_price=95,target_price=108),submission_eligible=True)
  worker.service.previews={"preview":dict(preview=preview)}
  return worker,fingerprint
 def state(self,loss=0):
  return dict(daily_loss=loss,exposed_underlyings=[],used_capital=0,available_funds=100000)
 def test_manual_cannot_submit_even_with_valid_claim(self):
  with tempfile.TemporaryDirectory() as t:
   w,f=self.make(Path(t),"MANUAL")
   with patch("sector_heatmap.handoff_broker_read.read") as read:
    with self.assertRaises(PermissionError):w.call("submit",dict(preview_id="preview",fingerprint=f,confirmation="CONFIRM preview"))
    read.assert_not_called();w.service.submit.assert_not_called()
 def test_daily_loss_cutoff_blocks_submission_and_latches(self):
  with tempfile.TemporaryDirectory() as t:
   w,f=self.make(Path(t))
   with patch("sector_heatmap.handoff_broker_read.read",return_value=self.state(10000)):
    with self.assertRaises(PermissionError):w.submit_gate("preview",f)
   w.service.submit.assert_not_called()
   with sqlite3.connect(w.schedule) as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM loss_halts").fetchone()[0],1)
 def test_matching_live_reservation_passes_only_once_service_consumes(self):
  with tempfile.TemporaryDirectory() as t:
   w,f=self.make(Path(t))
   with patch("sector_heatmap.handoff_broker_read.read",return_value=self.state()):
    w.call("submit",dict(preview_id="preview",fingerprint=f,confirmation="CONFIRM preview"))
   w.service.submit.assert_called_once_with("preview","CONFIRM preview")
 def test_changed_quantity_and_exits_block_before_mutation(self):
  for field in ("quantity","target"):
   with tempfile.TemporaryDirectory() as t:
    w,f=self.make(Path(t));preview=w.service.previews["preview"]["preview"]
    if field=="quantity":preview["instrument"]["contracts"][0]["quantity"]=11
    else:preview["protection"]["target_price"]=110
    with patch("sector_heatmap.handoff_broker_read.read",return_value=self.state()):
     with self.assertRaises(ValueError):w.call("submit",dict(preview_id="preview",fingerprint=f,confirmation="CONFIRM preview"))
    w.service.submit.assert_not_called()
 def test_preview_operation_does_not_call_submit(self):
  w=object.__new__(Worker);w.service=Mock()
  w.call("prepare",dict(underlying="NSE:TEST-EQ"));w.service.prepare.assert_called_once();w.service.submit.assert_not_called()

 def test_exact_owner_reviewed_manual_receipt_can_submit(self):
  import time
  with tempfile.TemporaryDirectory() as t:
   w,f=self.make(Path(t),"MANUAL");w.account["user_id"]="owner"
   with sqlite3.connect(w.schedule) as db:
    row=db.execute("SELECT body FROM receipts").fetchone()
    saved=json.loads(row[0]);saved["authorization"]=dict(mode="MANUAL",user_id="owner",preview_id="preview",expires_at=time.time()+60,policy_revision=None)
    db.execute("UPDATE receipts SET body=?",(json.dumps(saved),))
   with patch("sector_heatmap.handoff_broker_read.read",return_value=self.state()):
    w.call("submit",dict(preview_id="preview",fingerprint=f,confirmation="CONFIRM preview"))
   w.service.submit.assert_called_once_with("preview","CONFIRM preview")

class MotilalAnalysisBoundaryTests(unittest.TestCase):
 def test_motilal_native_analysis_cannot_reach_any_order_operation(self):
  w=object.__new__(Worker);w.account={"broker":"MOTILAL_OSWAL"};w.service=Mock();w.submit_gate=Mock()
  caps=w.call("capabilities",{})
  self.assertFalse(caps["live_submission_enabled"])
  self.assertTrue(caps["native_analysis_available"])
  for operation in ["prepare","submit","reconcile"]:
   with self.assertRaisesRegex(ValueError,"no unprotected order"):w.call(operation,{})
  w.service.prepare.assert_not_called();w.service.submit.assert_not_called();w.service.reconcile_protection.assert_not_called();w.submit_gate.assert_not_called()
 def test_motilal_analysis_uses_native_provider_without_fyers_or_dhan(self):
  w=object.__new__(Worker);w.account={"broker":"MOTILAL_OSWAL"};w.service=Mock();w.folder=Path("/tmp/synthetic")
  sectors=Mock();provider=Mock();report={"source":{"broker":"MOTILAL_OSWAL"}}
  with patch("sector_heatmap.motilal_analysis.Sectors",return_value=sectors),patch("sector_heatmap.motilal_analysis.Handoff",return_value=provider),patch("sector_heatmap.handoff_analysis.opportunities",return_value=report) as run:
   self.assertEqual(w.call("analysis",{"instrument_route":"cash_equity"}),report)
   run.assert_called_once_with({"instrument_route":"cash_equity"},provider,{})
  provider.sectors.refresh.assert_called_once()
  w.service.submit.assert_not_called()
