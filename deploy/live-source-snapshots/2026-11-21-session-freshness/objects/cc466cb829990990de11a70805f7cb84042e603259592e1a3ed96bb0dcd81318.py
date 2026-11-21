import tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
from sector_heatmap.market_calendar import IST
from sector_heatmap.handoff_schedule import Schedule,slot_at
from test_handoff_allocation import idea
class Scheduling(unittest.TestCase):
 def make(self,path,execute=None,ready=None):
  return Schedule(path,"owned","FYERS",lambda p:([idea()],{"cards":[]}),lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[]),execute=execute,auto_ready=ready)
 def test_session_closed(self):
  self.assertIsNone(slot_at(datetime(2026,10,20,10,tzinfo=IST)))
 def test_quarter_hour_slot(self):
  self.assertEqual(slot_at(datetime(2026,10,21,9,29,tzinfo=IST)),datetime(2026,10,21,9,15,tzinfo=IST).isoformat())
 def test_disabled_default(self):
  with tempfile.TemporaryDirectory() as t:self.assertEqual(self.make(Path(t)/"s.db").step(datetime(2026,10,21,10,tzinfo=IST))["state"],"DISABLED")
 def test_manual_collects_never_executes(self):
  with tempfile.TemporaryDirectory() as t:
   calls=[];s=self.make(Path(t)/"s.db",lambda *a:calls.append(a),lambda:True);s.configure({"enabled":True})
   self.assertEqual(s.step(datetime(2026,10,21,10,tzinfo=IST))["state"],"COMPLETED");self.assertFalse(calls)
 def test_slot_not_replayed_after_restart(self):
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/"s.db";s=self.make(path);s.configure({"enabled":True});now=datetime(2026,10,21,10,tzinfo=IST);s.step(now)
   self.assertEqual(self.make(path).step(now)["state"],"ALREADY_PROCESSED")
 def test_duplicate_levels_next_slot_suppressed(self):
  with tempfile.TemporaryDirectory() as t:
   s=self.make(Path(t)/"s.db");s.configure({"enabled":True});now=datetime(2026,10,21,10,tzinfo=IST);s.step(now)
   second=s.step(now+timedelta(minutes=15))
   self.assertEqual(second["report"]["automation_selection"]["new_recommendations"],0)
   self.assertTrue(second["plans"]) # current Manual review stays available without another alert
 def test_pre_submit_rejection_releases_capital_without_replaying_the_idea(self):
  from sector_heatmap.handoff_errors import PreflightRejected
  with tempfile.TemporaryDirectory() as t:
   calls=[]
   def execute(plan,p):
    calls.append(plan["fingerprint"])
    if len(calls)==1:raise PreflightRejected("Fresh price exceeds allocated capital.")
    return {"protection_confirmed":True}
   s=self.make(Path(t)/"s.db",execute,lambda:True)
   base=s.exposure;s.exposure=lambda p:{**base(p),"daily_loss":0}
   s.configure({"enabled":True,"mode":"AUTO","live_authorized":True})
   now=datetime(2026,10,21,10,tzinfo=IST)
   first=s.step(now)
   self.assertEqual(first["state"],"COMPLETED")
   self.assertEqual(first["executions"][0]["status"],"NOT_SUBMITTED")
   self.assertFalse(s.claims.unsettled("owned"))
   self.assertFalse(s.step(now+timedelta(minutes=15))["plans"])
   with s.db() as db:self.assertEqual(db.execute("SELECT state FROM receipts").fetchone()[0],"NOT_SUBMITTED")
 def test_reported_untraded_idea_can_be_submitted_once_after_fresh_auto_analysis(self):
  with tempfile.TemporaryDirectory() as t:
   calls=[]
   def execute(plan,p):
    calls.append(plan["fingerprint"])
    return dict(protection_confirmed=True,entry_fill_price="100",protected_quantity=plan["quantity"])
   s=self.make(Path(t)/"s.db",execute,lambda:True)
   base=s.exposure;s.exposure=lambda p:{**base(p),"daily_loss":0}
   s.configure({"enabled":True});now=datetime(2026,10,21,10,tzinfo=IST)
   first=s.step(now);self.assertEqual(first["report"]["automation_selection"]["new_recommendations"],1)
   s.configure({"mode":"AUTO","live_authorized":True})
   second=s.step(now+timedelta(minutes=15))
   self.assertEqual(second["state"],"COMPLETED")
   self.assertEqual(second["report"]["automation_selection"]["new_recommendations"],0)
   self.assertEqual(len(calls),1)
   s.step(now+timedelta(minutes=30));self.assertEqual(len(calls),1)
 def test_auto_requires_authorization(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):self.make(Path(t)/"s.db").configure({"mode":"AUTO"})
 def test_auto_requires_verified_adapter(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):self.make(Path(t)/"s.db").configure({"mode":"AUTO","live_authorized":True})
 def test_unverified_exposure_blocks(self):
  with tempfile.TemporaryDirectory() as t:
   s=self.make(Path(t)/"s.db");s.configure({"enabled":True});s.exposure=lambda p:{}
   self.assertEqual(s.step(datetime(2026,10,21,10,tzinfo=IST))["state"],"REVIEW")
 def test_amo_not_silently_sent(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):self.make(Path(t)/"s.db").configure({"amo":True})
 def test_invalid_budget_blocked(self):
  with tempfile.TemporaryDirectory() as t:
   for amount in (True,0,100001,float("inf")):
    with self.assertRaises(ValueError):self.make(Path(t)/"s.db").configure({"capital":amount})

class LiveCutoff(unittest.TestCase):
 def build(self,path,loss):
  calls=[]
  s=Schedule(path,"owned","FYERS",lambda p:([idea()],{"cards":[]}),
   lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[],daily_loss=loss),
   execute=lambda *a:(calls.append(a) or {"status":"OPEN","protection_confirmed":True}),auto_ready=lambda:True)
  s.configure({"enabled":True,"mode":"AUTO","live_authorized":True})
  return s,calls
 def test_ten_thousand_blocks_entries_but_reports(self):
  with tempfile.TemporaryDirectory() as t:
   s,calls=self.build(Path(t)/"s.db",10000)
   r=s.step(datetime(2026,10,21,10,tzinfo=IST));self.assertEqual(r["state"],"COMPLETED");self.assertFalse(calls);self.assertTrue(r["plans"])
 def test_below_cutoff_can_execute(self):
  with tempfile.TemporaryDirectory() as t:
   s,calls=self.build(Path(t)/"s.db",9999)
   self.assertEqual(s.step(datetime(2026,10,21,10,tzinfo=IST))["state"],"COMPLETED");self.assertEqual(len(calls),1)
 def test_unknown_daily_loss_no_entry(self):
  with tempfile.TemporaryDirectory() as t:
   s,calls=self.build(Path(t)/"s.db",None)
   self.assertEqual(s.step(datetime(2026,10,21,10,tzinfo=IST))["state"],"REVIEW");self.assertFalse(calls)

 def test_invalid_daily_loss_never_enters(self):
  for loss in (float("nan"),float("inf"),-1,True,"invalid"):
   with self.subTest(loss=loss),tempfile.TemporaryDirectory() as t:
    s,calls=self.build(Path(t)/"s.db",loss)
    self.assertEqual(s.step(datetime(2026,10,21,10,tzinfo=IST))["state"],"REVIEW")
    self.assertFalse(calls)

 def test_analysis_survives_exhausted_budget(self):
  with tempfile.TemporaryDirectory() as t:
   s,calls=self.build(Path(t)/"s.db",0)
   s.exposure=lambda p:dict(positions_verified=True,orders_verified=True,used_capital=100000,available_funds=0,exposed_underlyings=[],daily_loss=0)
   r=s.step(datetime(2026,10,21,10,tzinfo=IST))
   self.assertEqual(r["state"],"COMPLETED");self.assertFalse(calls)
   self.assertEqual(len(r["recommendations"]),1)
   self.assertEqual(r["report"]["automation_selection"]["new_recommendations"],1)

 def test_daily_cutoff_stays_latched_after_pnl_recovery(self):
  with tempfile.TemporaryDirectory() as t:
   s,calls=self.build(Path(t)/"s.db",10000)
   now=datetime(2026,10,21,10,tzinfo=IST)
   s.step(now)
   self.assertTrue(s.loss_halted(dict(daily_loss=0),now,10000))
   self.assertFalse(s.loss_halted(dict(daily_loss=0),now+timedelta(days=1),10000))
 def test_uncertain_entry_blocks_next_slot_until_readonly_reconciliation(self):
  with tempfile.TemporaryDirectory() as t:
   s,calls=self.build(Path(t)/"s.db",0)
   s.execute=lambda *a:dict(status="PENDING",preview_id="owned-preview",protection_confirmed=False)
   now=datetime(2026,10,21,10,tzinfo=IST)
   self.assertEqual(s.step(now)["state"],"REVIEW")
   self.assertTrue(s.claims.unsettled("owned"))
   seen=[]
   s.reconcile_receipts(lambda preview,plan:(seen.append(preview) or dict(protection_confirmed=True,preview_id=preview)))
   self.assertEqual(seen,["owned-preview"]);self.assertFalse(s.claims.unsettled("owned"))

class NextOpen(unittest.TestCase):
 def test_closed_session_persists_analysis_intent_without_orders(self):
  with tempfile.TemporaryDirectory() as t:
   calls=[];s=Schedule(Path(t)/"s.db","owned","FYERS",lambda p:(calls.append("analysis") or ([idea()],{"cards":[]})),
      lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[]))
   s.configure({"enabled":True})
   result=s.step(datetime(2026,10,20,18,tzinfo=IST))
   self.assertEqual(result["state"],"WAITING_NEXT_OPEN_REVALIDATION");self.assertFalse(calls)
   self.assertFalse(result["broker_amo_submitted"])
   self.assertEqual(s.status()["deferred"]["state"],"WAITING_FRESH_ANALYSIS")
   self.assertEqual(s.step(datetime(2026,10,21,9,15,tzinfo=IST))["state"],"COMPLETED")
   self.assertEqual(calls,["analysis"]);self.assertEqual(s.status()["deferred"]["state"],"FRESH_ANALYSIS_COMPLETED")
 def test_paused_schedule_has_no_deferred_instruction(self):
  with tempfile.TemporaryDirectory() as t:
   s=Schedule(Path(t)/"s.db","owned","FYERS",None,None)
   self.assertEqual(s.step(datetime(2026,10,20,18,tzinfo=IST))["state"],"DISABLED")
   self.assertIsNone(s.status()["deferred"])

class HaltSeparation(unittest.TestCase):
 def test_execution_halt_does_not_stop_analysis(self):
  with tempfile.TemporaryDirectory() as t:
   calls=[];s=Schedule(Path(t)/"s.db","owned","FYERS",lambda p:([idea()],{"cards":[]}),
    lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[],daily_loss=0),
    execute=lambda *a:calls.append(a),auto_ready=lambda:True)
   s.configure(dict(enabled=True,mode="AUTO",live_authorized=True))
   with s.db() as db:
    p=s.policy();p["entries_halted"]=True;db.execute("UPDATE policy SET body=?",( __import__("json").dumps(p),))
   result=s.step(datetime(2026,10,21,10,tzinfo=IST))
   self.assertEqual(result["state"],"COMPLETED");self.assertTrue(result["recommendations"]);self.assertFalse(calls)

class DuplicateReportPolicy(unittest.TestCase):
 def test_repeated_reports_do_not_replay_an_auto_order(self):
  with tempfile.TemporaryDirectory() as t:
   calls=[]
   s=Schedule(Path(t)/"s.db","owned","FYERS",lambda p:([{**idea(),"report_card":{"candidate":{"name":"Synthetic"}}}],{"cards":[]}),
    lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[],daily_loss=0),
    execute=lambda plan,p:(calls.append(plan["fingerprint"]) or dict(protection_confirmed=True,entry_fill_price="100",protected_quantity=plan["quantity"])),
    auto_ready=lambda:True)
   s.configure(dict(enabled=True,mode="AUTO",live_authorized=True,allow_duplicate_reports=True))
   now=datetime(2026,10,21,10,tzinfo=IST)
   first=s.step(now);second=s.step(now+timedelta(minutes=15))
   self.assertEqual(first["report"]["automation_selection"]["new_recommendations"],1)
   self.assertEqual(second["report"]["automation_selection"]["new_recommendations"],1)
   self.assertEqual(len(second["report"]["cards"]),1)
   self.assertEqual(len(calls),1);self.assertEqual(second["plans"],[])
 def test_default_is_off_and_only_boolean_values_are_accepted(self):
  with tempfile.TemporaryDirectory() as t:
   s=Scheduling().make(Path(t)/"s.db")
   self.assertFalse(s.policy()["allow_duplicate_reports"])
   for value in ["true",1,None]:
    with self.assertRaises(ValueError):s.configure({"allow_duplicate_reports":value})
   s.configure({"allow_duplicate_reports":True});self.assertTrue(s.policy()["allow_duplicate_reports"])
   s.configure({"allow_duplicate_reports":False});self.assertFalse(s.policy()["allow_duplicate_reports"])
