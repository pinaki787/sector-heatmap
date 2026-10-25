import json,sqlite3,tempfile,unittest
from pathlib import Path
from sector_heatmap.handoff_observer import Observer
from sector_heatmap.trade_notifications import Outbox,render
from sector_heatmap.notification_destinations import telegram_destination

class PrivateObserver(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
  self.clock=1000.;self.account=dict(id="owned",broker="FYERS",owner_username="owner")
  self.observer=Observer(self.folder,self.account,lambda:self.clock)
  plan=dict(fingerprint="a"*64,symbol="NSE:TEST-EQ",kind="EQUITY",direction="BULLISH",quantity=10)
  with sqlite3.connect(self.folder/"handoff-schedule.sqlite3") as db:
   db.execute("CREATE TABLE receipts(body TEXT)")
   db.execute("INSERT INTO receipts VALUES(?)",(json.dumps(dict(plan=plan,result=dict(preview_id="preview",order_ids=["entry"]))),))
  self.config=dict(modes=["LIVE"],fill_policy="EACH",owner_username="owner")
  self.outbox=Outbox(self.folder/"outbox.sqlite3",lambda:self.clock)
 def tearDown(self):
  self.outbox.db.close();self.temp.cleanup()
 def state(self,fills=None,positions=None):
  return dict(positions_verified=True,orders_verified=True,filled_orders=fills or [],positions=positions or [],daily_pnl=0)
 def read(self):return json.loads(self.observer.path.read_text())
 def fill(self,ident="entry",parent=None,side="BUY"):
  return dict(id=ident,parent_id=parent,symbol="NSE:TEST-EQ",side=side,filled=10,requested=10,price=100)
 def test_baseline_old_fills_not_replayed_and_new_fill_is_exact(self):
  self.observer.update(self.state([self.fill()]))
  data=self.read();self.assertEqual(data["order_history"][0]["filled_at"],0)
  self.outbox.ingest(self.account,data["order_history"],self.config)
  self.assertEqual(self.outbox.status()["events"],0)
 def test_new_entry_and_linked_exit_but_unrelated_trade_is_not_adopted(self):
  self.observer.update(self.state());self.clock+=1
  self.observer.update(self.state([self.fill(),self.fill("unrelated",None,"SELL")]))
  rows=self.read()["order_history"];self.assertEqual(len(rows),1);self.assertTrue(rows[0]["is_entry"])
  self.outbox.ingest(self.account,rows,self.config);self.assertEqual(self.outbox.status()["events"],1)
  self.clock+=1
  self.observer.update(self.state([self.fill(),self.fill("exit","entry","SELL")]))
  rows=self.read()["order_history"];self.outbox.ingest(self.account,rows,self.config)
  events=[json.loads(r[0]) for r in self.outbox.db.execute("SELECT payload FROM events")]
  self.assertEqual([r["action"] for r in events],["ENTRY","EXIT"])
 def test_missing_parent_and_missing_correlation_cannot_confirm_an_exit(self):
  with sqlite3.connect(self.folder/"handoff-schedule.sqlite3") as db:
   saved=json.loads(db.execute("SELECT body FROM receipts").fetchone()[0]);saved["result"]={}
   db.execute("UPDATE receipts SET body=?",(json.dumps(saved),))
  self.observer.update(self.state());self.clock+=1
  closing=self.fill("foreign-target",None,"SELL")
  closing.update(leg_name="TARGET_LEG",correlation_id=None)
  self.observer.update(self.state([closing]))
  self.assertEqual(self.read()["order_history"],[])
 def test_disappearance_without_broker_fill_never_creates_exit(self):
  pos=[dict(symbol="NSE:TEST-EQ",netQty=10,pnl=1)]
  self.observer.update(self.state(positions=pos));self.clock+=60;self.observer.update(self.state())
  self.assertEqual(self.read()["order_history"],[])
 def test_position_summary_is_private_only_and_deduplicated(self):
  self.clock+=1
  positions=[dict(symbol="NSE:TEST-EQ",netQty=10,pnl=-20)]
  self.observer.update(self.state(positions=positions))
  data=self.read();self.outbox.ingest_summaries(self.account,data["position_summaries"],self.config)
  self.outbox.ingest_summaries(self.account,data["position_summaries"],self.config)
  event=json.loads(self.outbox.db.execute("SELECT payload FROM events").fetchone()[0])
  self.assertIn("PRIVATE POSITION UPDATE",render(event));self.assertIn("\n",render(event))
  self.assertEqual(self.outbox.db.execute("SELECT channel FROM delivery").fetchall(),[("telegram",)])
  config=dict(owner_username="owner",telegram=dict(chat_id=42),telegram_destinations=dict(enabled=True,
    private_trades=dict(enabled=True,chat_id=-1001,activated_at=1),shared_market=dict(enabled=True,chat_id=-1002,activated_at=1)))
  routed,error=telegram_destination(config,event,self.clock)
  self.assertIsNone(error);self.assertEqual(routed["telegram"]["chat_id"],-1001)
  self.assertEqual(self.outbox.status()["events"],1)
 def test_unverified_positions_never_publish(self):
  with self.assertRaises(ValueError):self.observer.update(dict(positions_verified=False,orders_verified=True))
  self.assertFalse(self.observer.path.exists())
