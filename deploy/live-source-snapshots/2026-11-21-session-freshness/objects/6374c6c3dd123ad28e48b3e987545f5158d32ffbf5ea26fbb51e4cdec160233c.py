import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock
from sector_heatmap.handoff_runtime import Runtime
from sector_heatmap.handoff_bridge import OwnedBridge
from sector_heatmap.workspaces import WorkspaceStore

class Bridge:
 calls=[]
 def __init__(self,*args):self.account=args[3]
 def identity(self):return None
 def exposure(self,p):return dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,daily_loss=0,exposed_underlyings=[])
 normalized=staticmethod(OwnedBridge.normalized)
 def request(self,op,payload):
  if op!="prepare":raise AssertionError("Prepare must not submit.")
  return dict(preview_id="native-"+str(payload["quantity"]),confirmation_phrase="CONFIRM native",
    instrument=dict(kind="EQUITY",contracts=[dict(symbol="NSE:TEST-EQ",action="BUY",quantity=payload["quantity"],limit_price=100,tick_size=.05)]),
    protection=dict(stop_loss_price=95,target_price=108),submission_eligible=True,live_submission_enabled=True)
 def submit_prepared(self,plan,preview):
  self.calls.append((plan,preview));return dict(preview_id=preview["preview_id"],order_ids=["owned-order"],status="OPEN",protection_confirmed=True)

class ManualReview(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=WorkspaceStore(self.root/"registry.sqlite3")
  with self.store.db() as db:db.execute("INSERT INTO users VALUES(?,?,?,?,?)",("owner","owner","synthetic","synthetic",1))
  self.user=dict(id="owner",admin=True,features=["handoff"])
  self.account=self.store.create_account(self.user,"FYERS","Mine","synthetic")
  self.runtime=Runtime(self.store,self.root,bridge_factory=Bridge);self.runtime.stopping.set()
  self.item=self.runtime.entry(self.user,self.account["id"]);self.schedule=self.item["schedule"]
  self.schedule.configure(dict(enabled=True,mode="MANUAL"))
  self.card=dict(candidate=dict(symbol="NSE:TEST-EQ",direction="BULLISH"),analysis=dict(kind="EQUITY",conviction=dict(rating="High",score=6,maximum_score=6)))
  row=dict(fingerprint="a"*64,symbol="NSE:TEST-EQ",underlying="NSE:TEST-EQ",kind="EQUITY",direction="BULLISH",
   entry=100,stop=95,target=108,conviction=self.card["analysis"]["conviction"],validated=True,lot_size=1,
   report_card=self.card,ticket_payload=dict(underlying="NSE:TEST-EQ",proposal=dict(kind="EQUITY",quantity=1)))
  with self.schedule.db() as db:db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)",
    ("slot","COMPLETED",time.time(),time.time(),json.dumps(dict(recommendations=[row])),None))
  Bridge.calls=[]
 def tearDown(self):self.runtime.close();self.tmp.cleanup()
 def prepare(self):return self.runtime.manual.prepare(self.user,self.account["id"],"synthetic-token",["a"*64])
 def test_prepare_has_no_mutation_and_respects_one_lakh_pool(self):
  p=self.prepare();self.assertFalse(Bridge.calls)
  self.assertEqual(p["items"][0]["quantity"],1000);self.assertEqual(float(p["allocated"]),100000)
  with self.schedule.db() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],0)
 def test_small_quote_increase_resizes_cash_before_the_human_reviews_it(self):
  class Moving(Bridge):
   reads=0
   def request(self,operation,payload):
    preview=super().request(operation,payload);self.reads+=1
    preview["instrument"]["contracts"][0]["limit_price"]=100 if self.reads==1 else 100.02
    return preview
  self.runtime.bridge_factory=Moving
  review=self.prepare()
  self.assertEqual(review["items"][0]["quantity"],999)
  self.assertLessEqual(float(review["allocated"]),100000)
  self.assertFalse(Bridge.calls)
 def test_selection_that_became_exposed_is_excluded_before_any_preview(self):
  class Exposed(Bridge):
   def exposure(self,p):return {**super().exposure(p),"exposed_underlyings":["NSE:TEST-EQ"]}
  self.runtime.bridge_factory=Exposed
  with self.assertRaisesRegex(ValueError,"existing exposure"):self.prepare()
  self.assertFalse(Bridge.calls)
 def test_wrong_confirmation_and_other_owner_cannot_submit(self):
  p=self.prepare()
  with self.assertRaises(PermissionError):self.runtime.manual.submit(self.user,self.account["id"],p["preview_id"],"wrong")
  with self.assertRaises(PermissionError):self.runtime.manual.submit({**self.user,"id":"other"},self.account["id"],p["preview_id"],p["confirmation_phrase"])
  self.assertFalse(Bridge.calls)
 def test_explicit_submit_consumes_group_and_durable_claim_prevents_replay(self):
  p=self.prepare()
  r=self.runtime.manual.submit(self.user,self.account["id"],p["preview_id"],p["confirmation_phrase"])
  self.assertEqual(r["status"],"BROKER_REGISTERED");self.assertEqual(len(Bridge.calls),1)
  with self.assertRaises(PermissionError):self.runtime.manual.submit(self.user,self.account["id"],p["preview_id"],p["confirmation_phrase"])
  with self.assertRaises(ValueError):
   again=self.prepare()
   self.runtime.manual.submit(self.user,self.account["id"],again["preview_id"],again["confirmation_phrase"])
  self.assertEqual(len(Bridge.calls),1)
 def test_mode_change_invalidates_exact_review(self):
  p=self.prepare();self.schedule.configure(dict(enabled=False))
  with self.assertRaises(PermissionError):self.runtime.manual.submit(self.user,self.account["id"],p["preview_id"],p["confirmation_phrase"])
  self.assertFalse(Bridge.calls)


class MixedManualReview(unittest.TestCase):
 def setUp(self):
  ManualReview.setUp(self)
  class Mixed(Bridge):
   def __init__(self,*args):super().__init__(*args);self.reads={}
   def request(self,operation,payload):
    assert operation=="prepare"
    option=payload["proposal"]["kind"]=="LONG_OPTION";key="option" if option else "equity"
    self.reads[key]=self.reads.get(key,0)+1
    price=(10 if self.reads[key]==1 else 11) if option else (333 if self.reads[key]==1 else 334)
    symbol="NSE:OTHER26OCT100CE" if option else "NSE:TEST-EQ"
    quantity=50 if option else payload["quantity"]
    return dict(preview_id="native-"+key+"-"+str(quantity),confirmation_phrase="CONFIRM native",live_submission_enabled=True,
      instrument=dict(kind="LONG_OPTION" if option else "EQUITY",contracts=[dict(symbol=symbol,action="BUY",quantity=quantity,limit_price=price,tick_size=.05,lot_size=50 if option else 1)]),
      protection=dict(stop_loss_price=5 if option else 300,target_price=15 if option else 360),submission_eligible=True)
  self.mixed=Mixed;self.runtime.bridge_factory=Mixed
  option=dict(fingerprint="b"*64,symbol="NSE:OTHER26OCT100CE",underlying="NSE:OTHER-EQ",kind="LONG_OPTION",direction="BULLISH",
   entry=10,stop=5,target=15,conviction=dict(rating="HIGH",score=6,maximum_score=7),validated=True,lot_size=50,
   report_card=dict(candidate=dict(symbol="NSE:OTHER-EQ",direction="BULLISH"),analysis=dict(kind="LONG_OPTION",conviction=dict(rating="HIGH",score=6,maximum_score=7))),
   ticket_payload=dict(underlying="NSE:OTHER-EQ",proposal=dict(kind="LONG_OPTION",quantity=50),lots=1))
  with self.schedule.db() as db:
   record=json.loads(db.execute("SELECT output FROM runs").fetchone()[0]);record["recommendations"].append(option)
   db.execute("UPDATE runs SET output=?",(json.dumps(record),))
 def prepare(self):return self.runtime.manual.prepare(self.user,self.account["id"],"synthetic-token",["a"*64,"b"*64])
 tearDown=ManualReview.tearDown
 def test_one_option_lot_first_and_equity_uses_actual_remaining_budget(self):
  review=self.prepare();option,equity=review["items"]
  self.assertEqual(option["kind"],"LONG_OPTION");self.assertEqual(option["quantity"],50)
  self.assertEqual(equity["kind"],"EQUITY");self.assertEqual(equity["quantity"],297)
  self.assertEqual(float(review["allocated"]),99748)
  self.assertFalse(Bridge.calls)
 def test_existing_equity_is_excluded_and_remaining_option_can_still_be_reviewed(self):
  parent=self.mixed
  class Exposed(parent):
   def exposure(self,p):return {**super().exposure(p),"exposed_underlyings":["NSE:TEST-EQ"]}
  self.runtime.bridge_factory=Exposed
  review=self.prepare()
  self.assertEqual(len(review["items"]),1);self.assertEqual(review["items"][0]["quantity"],50)
  self.assertEqual(review["excluded"][0]["symbol"],"NSE:TEST-EQ")
  self.assertFalse(Bridge.calls)
