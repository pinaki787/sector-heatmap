import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from sector_heatmap.handoff_bridge import OwnedBridge
from sector_heatmap.handoff_runtime import Runtime
from sector_heatmap.workspaces import WorkspaceStore

class BridgeTests(unittest.TestCase):
 def test_normalized_bought_put_keeps_bearish_direction(self):
  card=dict(candidate=dict(direction="BEARISH"),analysis=dict(conviction=dict(rating="HIGH",score=6,maximum_score=7)))
  p=dict(instrument=dict(kind="LONG_OPTION",contracts=[dict(symbol="NSE:TEST26OCT100PE",action="BUY",limit_price=10,lot_size=50)]),
   protection=dict(stop_loss_price=8,target_price=14),submission_eligible=True)
  r=OwnedBridge.normalized(p,card,dict(underlying="NSE:TEST-EQ"))
  self.assertEqual(r["direction"],"BEARISH");self.assertEqual(r["lot_size"],50)
 def test_cash_action_must_match_bearish_recommendation(self):
  card=dict(candidate=dict(direction="BEARISH"),analysis=dict(conviction=dict(rating="HIGH",score=6,maximum_score=6)))
  preview=dict(instrument=dict(kind="EQUITY",contracts=[dict(symbol="NSE:TEST-EQ",action="BUY",limit_price=100)]),
      protection=dict(stop_loss_price=95,target_price=110),submission_eligible=True)
  with self.assertRaisesRegex(ValueError,"action differs"):OwnedBridge.normalized(preview,card,{"underlying":"NSE:TEST-EQ"})
 def test_backend_without_native_protection_never_becomes_validated(self):
  with self.assertRaises(ValueError):OwnedBridge.normalized(dict(instrument=dict(contracts=[])),{},{})

 def test_collect_accepts_actual_engine_title_case_high_rating(self):
  b=object.__new__(OwnedBridge);b.account=dict(broker="FYERS");b.account_id="owned"
  card=dict(card_id="card-1",candidate=dict(symbol="NSE:TEST-EQ",direction="BULLISH"),
      analysis=dict(kind="EQUITY",entry=100,conviction=dict(rating="High",score=6,maximum_score=6)))
  b.analysis=lambda route,p:dict(source=dict(broker="FYERS"),analysis_id="analysis",risk_policy={},
      cards=[card] if route=="cash_equity" else [],exclusions=[])
  def request(operation,payload):
   if operation=="size":return dict(fresh_quote=dict(price=100),active_invalidation=dict(price=95,target=108))
   return dict(instrument=dict(kind="EQUITY",contracts=[dict(symbol="NSE:TEST-EQ",action="BUY",limit_price=100,tick_size=.05)]),
     protection=dict(stop_loss_price=95,target_price=108),submission_eligible=True)
  b.request=request
  rows,report=b.collect(dict(capital=100000,cash_product="INTRADAY"))
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]["conviction"]["rating"],"High")

class SubmitBoundaryTests(unittest.TestCase):
 def test_pre_submit_quote_rejection_never_creates_an_intent_or_calls_submit(self):
  from sector_heatmap.handoff_errors import PreflightRejected
  b=object.__new__(OwnedBridge);b.auto_ready=lambda:True
  b.request=Mock(return_value={})
  b.normalized=lambda *a:dict(symbol="NSE:TEST-EQ",kind="EQUITY",entry=101)
  plan=dict(ticket_payload={"proposal":{}},quantity=1,report_card={},symbol="NSE:TEST-EQ",kind="EQUITY",allocation="100")
  with self.assertRaises(PreflightRejected):b.execute(plan,{})
  self.assertEqual([call.args[0] for call in b.request.call_args_list],["prepare"])
 def test_failure_after_submit_boundary_remains_uncertain_and_keeps_intent(self):
  import tempfile
  from sector_heatmap.handoff_errors import PreflightRejected
  with tempfile.TemporaryDirectory() as folder:
   b=object.__new__(OwnedBridge);b.auto_ready=lambda:True;b.account={"broker":"FYERS"};b.account_id="owned";b.folder=Path(folder);b.clock=lambda:100
   b.normalized=lambda *a:dict(symbol="NSE:TEST-EQ",kind="EQUITY",entry=99,stop=90,target=120)
   def request(operation,p):
    if operation=="submit":raise TimeoutError("unknown")
    return dict(live_submission_enabled=True,preview_id="TEST",confirmation_phrase="CONFIRM TEST")
   b.request=request
   plan=dict(ticket_payload={"proposal":{}},quantity=1,report_card={},symbol="NSE:TEST-EQ",kind="EQUITY",allocation="100",fingerprint="a"*64)
   import sqlite3
   with sqlite3.connect(Path(folder)/"handoff-schedule.sqlite3") as db:
    db.execute("CREATE TABLE receipts(fingerprint TEXT,state TEXT,body TEXT)")
    db.execute("INSERT INTO receipts VALUES(?,'SUBMITTING',?)",(plan["fingerprint"],json.dumps({"plan":plan})))
   with self.assertRaises(TimeoutError):b.execute(plan,{})
   self.assertTrue((Path(folder)/"handoff-intents"/("a"*64+".json")).exists())

class BoundedQuoteTests(unittest.TestCase):
 def test_cash_quantity_shrinks_before_review_and_never_submits(self):
  from sector_heatmap.handoff_bridge import bounded_preview
  bridge=Mock();bridge.request.return_value={}
  bridge.normalized.side_effect=[dict(kind="EQUITY",entry=100.02),dict(kind="EQUITY",entry=100.03)]
  payload={"proposal":{}}
  preview,current,quantity=bounded_preview(bridge,payload,{},1000,100000)
  self.assertEqual(quantity,999);self.assertLessEqual(current["entry"]*quantity,100000)
  self.assertEqual([call.args[0] for call in bridge.request.call_args_list],["prepare","prepare"])
 def test_option_lot_cannot_be_silently_reduced_to_fit_new_premium(self):
  from sector_heatmap.handoff_bridge import bounded_preview
  bridge=Mock();bridge.request.return_value={}
  bridge.normalized.return_value=dict(kind="LONG_OPTION",entry=10.02)
  with self.assertRaises(ValueError):bounded_preview(bridge,{"proposal":{}},{},50,500)
  self.assertEqual(bridge.request.call_count,1)

class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.store=WorkspaceStore(self.root/"registry.sqlite3",clock=lambda:100)
  with self.store.db() as db:
   db.execute("INSERT INTO users VALUES(?,?,?,?,?)",("owner","owner","synthetic","synthetic",1))
   db.execute("INSERT INTO users VALUES(?,?,?,?,?)",("other","other","synthetic","synthetic",1))
  self.user=dict(id="owner",admin=True,features=["handoff"])
  self.other=dict(id="other",admin=True,features=["handoff"])
  self.a=self.store.create_account(self.user,"FYERS","Mine","test")
  self.b=self.store.create_account(self.other,"FYERS","Other","other-test")
  self.bridge=Mock();self.bridge.auto_ready.return_value=True
  self.runtime=Runtime(self.store,self.root,bridge_factory=lambda *a:self.bridge)
  self.runtime.stopping.set() # Never start background work in this unit fixture.
 def tearDown(self):
  self.runtime.close()
  for item in self.runtime.entries.values():
   if item["thread"]:item["thread"].join(timeout=1)
  self.temp.cleanup()
 def test_diagnostic_runs_real_bound_analysis_without_publication_or_execution(self):
  class Immediate:
   def __init__(self,target,**kwargs):self.target=target
   def start(self):self.target()
  self.bridge.collect.return_value=([dict(symbol="NSE:TEST-EQ")],dict(analysis_scopes=[],exclusions=[]))
  with patch("sector_heatmap.handoff_runtime.Thread",Immediate):
   result=self.runtime.diagnose(self.user,self.a["id"],"synthetic-token")
  self.assertEqual(result["state"],"COMPLETED")
  self.assertEqual(result["eligible"],1)
  self.assertFalse(result["published"])
  self.assertEqual(result["orders_submitted"],0)
  self.bridge.execute.assert_not_called()
  self.assertFalse(self.runtime.entry(self.user,self.a["id"])["schedule"].policy()["enabled"])
 def test_account_scope_and_section_permission(self):
  with self.assertRaises(PermissionError):self.runtime.status(self.user,self.b["id"])
  with self.assertRaises(PermissionError):self.runtime.status({**self.user,"features":[]},self.a["id"])
 def test_get_status_cannot_arm_or_read_broker(self):
  r=self.runtime.status(self.user,self.a["id"])
  self.assertFalse(r["policy"]["enabled"]);self.assertEqual(r["activation"],"AUTH_REQUIRED")
  self.bridge.exposure.assert_not_called();self.bridge.execute.assert_not_called()
 def test_explicit_save_binds_session_and_preserves_daily_cutoff(self):
  r=self.runtime.configure(self.user,self.a["id"],"synthetic-token",dict(enabled=True,mode="AUTO",live_authorized=True))
  self.assertEqual(r["policy"]["daily_loss_limit"],10000);self.assertTrue(r["session_bound"])
  self.bridge.execute.assert_not_called()
 def test_inactive_unbound_auto_sibling_does_not_block_fyers_rebind(self):
  other=self.store.create_account(self.user,"DHAN","Inactive Dhan","inactive-dhan")
  sibling=self.runtime.entry(self.user,other["id"])
  with sibling["schedule"].db() as db:
   p=sibling["schedule"].policy();p.update(enabled=False,mode="AUTO",live_authorized=True)
   db.execute("UPDATE policy SET body=? WHERE id=1",(json.dumps(p),))
  result=self.runtime.configure(self.user,self.a["id"],"synthetic-token",dict(enabled=True,mode="AUTO",live_authorized=True))
  self.assertTrue(result["session_bound"])
  self.assertTrue(result["policy"]["enabled"])
  self.assertIsNone(sibling["bridge"])
  self.assertFalse(sibling["schedule"].policy()["enabled"])
  self.bridge.execute.assert_not_called()
 def test_bound_without_watch_thread_is_not_ready(self):
  item=self.runtime.entry(self.user,self.a["id"]);item["bridge"]=self.bridge
  result=self.runtime.status(self.user,self.a["id"])
  self.assertEqual(result["activation"],"NOT_RUNNING")
  self.assertFalse(result["scheduler_running"])
 def test_selecting_different_owned_account_pauses_previous_schedule(self):
  second=self.store.create_account(self.user,"FYERS","Second","test2")
  self.runtime.configure(self.user,self.a["id"],"synthetic-token",dict(enabled=True))
  self.runtime.configure(self.user,second["id"],"synthetic-token",dict(enabled=True))
  self.assertFalse(self.runtime.status(self.user,self.a["id"])["policy"]["enabled"])
  self.assertTrue(self.runtime.status(self.user,second["id"])["policy"]["enabled"])

class MotilalOwnedBridgeTests(unittest.TestCase):
 def test_native_analysis_never_uses_legacy_http_or_another_broker(self):
  b=object.__new__(OwnedBridge);b.account={"broker":"MOTILAL_OSWAL"};b.account_id="owned"
  b.identity=Mock();b.tickets=Mock();b.request=Mock(side_effect=AssertionError("legacy HTTP must not be used"))
  b.tickets.call.return_value={"source":{"broker":"MOTILAL_OSWAL"}}
  report=b.analysis("cash_equity",dict(capital=100000,ai_provider="RULES_ONLY"))
  self.assertEqual(report["source"]["broker"],"MOTILAL_OSWAL")
  operation,payload=b.tickets.call.call_args.args
  self.assertEqual(operation,"analysis");self.assertEqual(payload["account_id"],"owned")
  self.assertEqual(payload["broker"],"MOTILAL_OSWAL");b.identity.assert_called_once()
 def test_motilal_execution_requests_cannot_fall_through_to_unprotected_http(self):
  b=object.__new__(OwnedBridge);b.account={"broker":"MOTILAL_OSWAL"};b.identity=Mock(return_value=({},{"broker":"MOTILAL_OSWAL"}))
  b.tickets=Mock();b.tickets.call.side_effect=ValueError("native protected execution unavailable")
  for action in ["prepare","submit","size","capabilities"]:
   with self.assertRaisesRegex(ValueError,"protected execution"):b.request(action,{})
  self.assertFalse(b.auto_ready())
