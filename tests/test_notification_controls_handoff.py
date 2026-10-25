import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sector_heatmap import notification_controls as controls
from sector_heatmap import handoff_cards as handoff
from sector_heatmap.trade_notifications import Outbox

class ControlsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"preferences.json"
        self.patch=patch.object(controls,"PREFERENCES",self.path);self.patch.start()
    def tearDown(self):
        self.patch.stop();self.tmp.cleanup()

    def test_pause_channel_scope_and_resume_new_only(self):
        controls.set_paused("sector","telegram",True,clock=lambda:100)
        self.assertEqual(controls.gate("telegram",{"kind":"SECTOR_CARD"},101)[0],"PAUSED")
        self.assertEqual(controls.gate("email",{"kind":"SECTOR_CARD"},101),(None,None))
        self.assertEqual(controls.gate("telegram",{"kind":"HANDOFF_CARD"},101),(None,None))
        controls.set_paused("sector","telegram",False,clock=lambda:110)
        self.assertEqual(controls.gate("telegram",{"kind":"SECTOR_CARD"},105)[0],"SKIPPED")
        self.assertEqual(controls.gate("telegram",{"kind":"SECTOR_CARD"},111),(None,None))
        self.assertEqual(self.path.stat().st_mode&0o777,0o600)

    def test_global_override_and_trade_occurrence_time(self):
        controls.set_paused("all","email",True,clock=lambda:100)
        self.assertEqual(controls.gate("email",{"kind":"HANDOFF_CARD"},101)[0],"PAUSED")
        controls.set_paused("all","email",False,clock=lambda:110)
        self.assertEqual(controls.gate("email",{"time":105},120)[0],"SKIPPED")

    def test_preference_corruption_holds_delivery(self):
        self.path.write_text("invalid")
        self.assertEqual(controls.gate("email",{},100)[0],"PAUSED")

    def test_owner_only_callbacks_and_commands(self):
        config={"telegram":{"chat_id":42}}
        calls=[]
        request=lambda config,method,body:calls.append((method,body))
        message={"message_id":4,"from":{"id":42},"chat":{"id":42,"type":"private"},"date":100,"text":"/pause_email"}
        self.assertEqual(controls.handle_update({"message":message},config,request,path=self.path),"PANEL")
        self.assertTrue(controls.preferences(self.path)["scopes"]["all"]["email"]["paused"])
        message["from"]["id"]=43
        count=len(calls)
        self.assertEqual(controls.handle_update({"message":message},config,request,path=self.path),"IGNORED")
        self.assertEqual(len(calls),count)
        callback={"id":"synthetic","from":{"id":42},"message":{"message_id":4,"chat":{"id":42,"type":"private"}},"data":"set:all:email:0"}
        self.assertEqual(controls.handle_update({"callback_query":callback},config,request,path=self.path),"UPDATED")
        self.assertFalse(controls.preferences(self.path)["scopes"]["all"]["email"]["paused"])

    def test_outbox_pause_does_not_send_and_resume_skips_backlog(self):
        box=Outbox(Path(self.tmp.name)/"outbox.sqlite3",lambda:100)
        event={"id":"synthetic","kind":"SECTOR_CARD"}
        with box.db:
            box.db.execute("INSERT INTO events VALUES(?,?,?)",("synthetic",json.dumps(event),100))
            for channel in ("telegram","email"):
                box.db.execute("INSERT INTO delivery(event,channel,state) VALUES(?,?,'PENDING')",("synthetic",channel))
        controls.set_paused("sector","telegram",True,clock=lambda:101)
        calls=[]
        sender=lambda channel,config,event:(calls.append(channel) or ("SENT",None))
        box.deliver({},sender=sender)
        self.assertEqual(calls,["email"])
        self.assertEqual(box.status()["deliveries"],{"PAUSED":1,"SENT":1})
        controls.set_paused("sector","telegram",False,clock=lambda:110)
        box.deliver({},sender=sender)
        self.assertEqual(calls,["email"])
        self.assertEqual(box.status()["deliveries"],{"SENT":1,"SKIPPED":1})
        box.db.close()

    def test_duplicate_resume_does_not_extend_cutoff(self):
        controls.set_paused("all","telegram",True,clock=lambda:100)
        controls.set_paused("all","telegram",False,clock=lambda:110)
        controls.set_paused("all","telegram",False,clock=lambda:130)
        self.assertEqual(controls.gate("telegram",{},120),(None,None))


class HandoffTest(unittest.TestCase):
    def result(self):
        return {"source":{"broker":"FYERS","mode":"intraday"},"generated_at":"2026-10-20T10:00:00+05:30",
                "cards":[{"candidate":{"name":"Synthetic","symbol":"TEST","direction":"BULLISH"},
                          "analysis":{"status":"REQUIRES_INVALIDATION_ACCEPTANCE","kind":"EQUITY",
                                      "entry":100,"stop_invalidation":95,"target":110,"reward_to_risk":2}}],
                "candidates":[{}],"exclusions":[]}

    def test_summary_preserves_analysis_authority_and_levels(self):
        summary=handoff.summary(self.result(),"FYERS",0)
        self.assertTrue(summary["no_order_authority"])
        self.assertEqual(summary["rows"][0]["entry"],100)
        self.assertEqual(summary["rows"][0]["status"],"REQUIRES_INVALIDATION_ACCEPTANCE")
        with self.assertRaises(ValueError):handoff.summary(self.result(),"DHAN",0)

    def test_empty_completed_outcome_and_png(self):
        result=self.result();result["cards"]=[]
        summary=handoff.summary(result,"FYERS",0,historical=True)
        self.assertEqual(summary["rows"],[])
        self.assertIn("NOT CURRENT",summary["freshness"])
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"empty.png";handoff.render_handoff(summary,p)
            self.assertEqual(p.read_bytes()[:8],b"\x89PNG\r\n\x1a\n")

    def test_historical_not_replayed_and_job_dedup(self):
        clock=handoff.parse_time("2026-10-20T10:01:00+05:30").timestamp()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(handoff,"PRIVATE",Path(folder)):
                box=handoff.HandoffOutbox(Path(folder)/"outbox.sqlite3",lambda:clock)
                account={"id":"owned","broker":"FYERS"}
                self.assertIsNone(box.enqueue_job(account,"old",clock-100,self.result()))
                self.assertIsNotNone(box.enqueue_job(account,"new",clock+1,self.result()))
                box.enqueue_job(account,"new",clock+1,self.result())
                self.assertEqual(box.status()["events"],1)
                box.db.close()

    def test_job_reader_filters_owner_feature_state_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            registry=root/".private/dashboard-login/registry.sqlite3";registry.parent.mkdir(parents=True)
            with sqlite3.connect(registry) as db:
                db.execute("CREATE TABLE users(id TEXT,username TEXT)")
                db.execute("INSERT INTO users VALUES(?,?)",("owner","pinaki87"))
            p=root/".private/dashboard-login/accounts/owned/source/.private/persistent-jobs.sqlite3";p.parent.mkdir(parents=True)
            with sqlite3.connect(p) as db:
                db.execute("CREATE TABLE jobs(id TEXT,updated REAL,output TEXT,owner TEXT,feature TEXT,kind TEXT,status TEXT,request TEXT)")
                for identity,status in [("owner:owned","COMPLETED"),("other:owned","COMPLETED"),("owner:owned","RUNNING")]:
                    db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",(identity+status,100,json.dumps(self.result()),identity,"handoff","ANALYSIS",status,"{}"))
                db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",("intermediate",101,json.dumps(self.result()),"owner:owned","handoff","ANALYSIS","COMPLETED",json.dumps({"payload":{"handoff_automation_intermediate":True}})))
            before=p.read_bytes()
            rows=list(handoff.completed_jobs({"owner_username":"pinaki87","accounts":[{"id":"owned","broker":"FYERS"}]},root))
            self.assertEqual(len(rows),1);self.assertEqual(p.read_bytes(),before)

    def test_market_handoff_keeps_premium_units(self):
        result={"kind":"MARKET_HANDOFF","broker":"FYERS","completed_at":100,
                "instruments":[{"symbol":"TEST","recommendation":{"decision":"WAIT"},"recommended_plan":None}]}
        summary=handoff.summary(result,"FYERS",100)
        self.assertEqual(summary["rows"][0]["direction"],"WAIT")
        self.assertIsNone(summary["rows"][0]["entry"])


if __name__=="__main__":unittest.main()

