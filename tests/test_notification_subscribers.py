import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.notification_recipients import validate_email,subscribers
from sector_heatmap.trade_notifications import Outbox
from sector_heatmap import notification_controls as controls
from sector_heatmap.handoff_cards import summary

class UserEmailTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.now=100
        self.store=WorkspaceStore(self.root/".private/dashboard-login/registry.sqlite3",clock=lambda:self.now)
        with self.store.db() as db:
            db.execute("INSERT INTO users VALUES(?,?,?,?,?)",("admin-id","admin","synthetic","synthetic",1))
            db.execute("INSERT INTO users VALUES(?,?,?,?,?)",("one-id","one","synthetic","synthetic",0))
            db.execute("INSERT INTO users VALUES(?,?,?,?,?)",("two-id","two","synthetic","synthetic",0))
        self.admin={"id":"admin-id"}
    def tearDown(self):self.tmp.cleanup()

    def test_address_alone_does_not_opt_in(self):
        self.store.set_notification_email(self.admin,"one","one@example.com")
        one=next(u for u in self.store.users(self.admin) if u["username"]=="one")
        self.assertEqual(one["notification_email"],"one@example.com")
        self.assertFalse(one["notification_email_enabled"])

    def test_checkbox_requires_valid_address(self):
        for value in ("","one@example.com,two@example.com","bad\r\nBcc: other@example.com","bad","a@-bad.com"):
            with self.assertRaises(ValueError):self.store.set_notification_email(self.admin,"one",value,True)
        self.store.set_notification_email(self.admin,"one","one+alerts@EXAMPLE.COM",True)
        row=next(u for u in self.store.users(self.admin) if u["username"]=="one")
        self.assertTrue(row["notification_email_enabled"])
        self.assertEqual(row["notification_email"],"one+alerts@example.com")

    def test_only_admin_can_edit_or_list(self):
        with self.assertRaises(PermissionError):self.store.set_notification_email({"id":"one-id"},"two","two@example.com",True)
        with self.assertRaises(PermissionError):self.store.users({"id":"one-id"})
        with self.assertRaises(ValueError):self.store.set_notification_email(self.admin,"unknown","a@example.com",True)

    def test_flags_and_addresses_survive_reopen_without_feature_changes(self):
        self.store.set_features(self.admin,"one",["sectors","handoff"])
        self.store.set_notification_email(self.admin,"one","one@example.com",True)
        reopened=WorkspaceStore(self.store.path)
        one=next(u for u in reopened.users(self.admin) if u["username"]=="one")
        self.assertEqual(one["features"],["handoff","sectors"])
        self.assertTrue(one["notification_email_enabled"])

    def test_subscriber_list_checked_only_and_deduplicated(self):
        self.store.set_notification_email(self.admin,"one","same@example.com",True)
        self.store.set_notification_email(self.admin,"two","same@example.com",True)
        self.store.set_notification_email(self.admin,"admin","admin@example.com",False)
        result=subscribers({"email_recipient_mode":"USER_MASTER_ENABLED"},self.root)
        self.assertEqual(len(result),1);self.assertEqual(result[0]["email"],"same@example.com")

    def test_disable_then_resume_sets_new_start_without_backfill(self):
        self.store.set_notification_email(self.admin,"one","one@example.com",True)
        self.now=120;self.store.set_notification_email(self.admin,"one","one@example.com",False)
        self.now=130;self.store.set_notification_email(self.admin,"one","one@example.com",True)
        self.now=140;self.store.set_notification_email(self.admin,"one","one@example.com",True)
        self.assertEqual(subscribers({"email_recipient_mode":"USER_MASTER_ENABLED"},self.root)[0]["enabled_at"],130)


class FanoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=100
        self.prefs=patch.object(controls,"PREFERENCES",self.root/"preferences.json");self.prefs.start()
        self.box=Outbox(self.root/"outbox.sqlite3",lambda:self.now)
        self.config={"email_recipient_mode":"USER_MASTER_ENABLED","email":{"recipient":"configured@example.com"}}
        event={"id":"event","kind":"SECTOR_CARD"}
        with self.box.db:
            self.box.db.execute("INSERT INTO events VALUES(?,?,?)",("event",json.dumps(event),100))
            self.box.db.execute("INSERT INTO delivery(event,channel,state) VALUES('event','email','PENDING')")
        self.targets=[{"id":"one","email":"one@example.com","enabled_at":0},{"id":"two","email":"two@example.com","enabled_at":0},{"id":"new","email":"new@example.com","enabled_at":200}]
    def tearDown(self):
        self.box.db.close();self.prefs.stop();self.tmp.cleanup()

    def test_independent_recipient_retry_without_replaying_sent(self):
        calls=[]
        def sender(channel,config,event):
            address=config["email"]["recipient"];calls.append(address)
            return ("RETRY","temporary") if address=="two@example.com" else ("SENT",None)
        with patch("sector_heatmap.notification_recipients.subscribers",side_effect=lambda config:self.targets):
            self.box.deliver(self.config,sender=sender)
            self.assertCountEqual(calls,["one@example.com","two@example.com"])
            self.assertEqual(self.box.status()["deliveries"],{"RETRY":1,"ROUTED":1,"SENT":1})
            self.now=131
            self.box.deliver(self.config,sender=lambda c,cfg,e:(calls.append(cfg["email"]["recipient"]) or ("SENT",None)))
        self.assertEqual(calls.count("one@example.com"),1);self.assertEqual(calls.count("two@example.com"),2)

    def test_unsubscribe_cancels_queued_recipient(self):
        controls.set_paused("all","email",True,clock=lambda:90)
        with patch("sector_heatmap.notification_recipients.subscribers",side_effect=lambda config:self.targets):
            self.box.deliver(self.config,sender=lambda *args:self.fail("Paused email sent"))
            self.targets=self.targets[:1]
            controls.set_paused("all","email",False,clock=lambda:110)
            self.box.deliver(self.config,sender=lambda *args:self.fail("Paused backlog sent"))
        states=dict(self.box.db.execute("SELECT channel,state FROM delivery"))
        self.assertEqual(states["email:two"],"SKIPPED")

    def test_no_enabled_users_never_uses_default_recipient(self):
        with patch("sector_heatmap.notification_recipients.subscribers",return_value=[]):
            self.box.deliver(self.config,sender=lambda *args:self.fail("Unsubscribed email sent"))
        self.assertEqual(self.box.status()["deliveries"],{"SKIPPED":1})


class NoOutcomeTest(unittest.TestCase):
    def test_no_recommendation_email_suppressed_but_telegram_allowed(self):
        event={"kind":"HANDOFF_CARD","snapshot":{"recommendation_count":0,"rows":[]}}
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(controls.gate("email",event,100,path=Path(folder)/"preferences.json")[0],"SKIPPED")
            self.assertEqual(controls.gate("telegram",event,100,path=Path(folder)/"preferences.json"),(None,None))

    def test_wait_only_market_result_has_zero_recommendations(self):
        result={"kind":"MARKET_HANDOFF","broker":"FYERS","completed_at":100,"instruments":[{"symbol":"TEST","recommendation":{"decision":"WAIT"}}]}
        self.assertEqual(summary(result,"FYERS",100)["recommendation_count"],0)
        result["instruments"][0]["recommendation"]["decision"]="BULLISH"
        self.assertEqual(summary(result,"FYERS",100)["recommendation_count"],1)



class OwnAccountIsolationTest(unittest.TestCase):
    def test_owned_subscriber_resolution_cannot_broadcast_to_other_checked_users(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=WorkspaceStore(root/".private/dashboard-login/registry.sqlite3",clock=lambda:100)
            with store.db() as db:
                for uid,name,admin in [("a","admin",1),("b","other",0)]:
                    db.execute("INSERT INTO users VALUES(?,?,?,?,?)",(uid,name,"synthetic","synthetic",admin))
                    db.execute("INSERT INTO user_notification_emails VALUES(?,?,1,0)",(uid,name+"@example.com"))
            cfg={"email_recipient_mode":"USER_MASTER_ENABLED","email_recipient_scope":"OWN_ACCOUNT_ONLY","owner_username":"other"}
            result=subscribers(cfg,root)
            self.assertEqual([r["email"] for r in result],["other@example.com"])

    def test_private_other_user_trade_never_sent_to_admin_telegram(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(controls,"PREFERENCES",root/"prefs.json"):
                box=Outbox(root/"outbox.sqlite3",lambda:100)
                cfg={"email_recipient_mode":"USER_MASTER_ENABLED","email_recipient_scope":"OWN_ACCOUNT_ONLY","owner_username":"admin",
                     "email":{"recipient":"admin@example.com"}}
                event={"id":"private-other","owner_username":"other","time":100}
                with box.db:
                    box.db.execute("INSERT INTO events VALUES(?,?,?)",("private-other",json.dumps(event),100))
                    for c in ("email","telegram"):box.db.execute("INSERT INTO delivery(event,channel,state) VALUES(?,?,'PENDING')",("private-other",c))
                observed=[]
                def targets(config):
                    self.assertEqual(config["owner_username"],"other")
                    return [{"id":"other-id","email":"other@example.com","enabled_at":0}]
                with patch("sector_heatmap.notification_recipients.subscribers",side_effect=targets):
                    box.deliver(cfg,sender=lambda channel,config,event:(observed.append((channel,config["email"]["recipient"])) or ("SENT",None)))
                self.assertEqual(observed,[("email","other@example.com")])
                self.assertEqual(box.db.execute("SELECT state FROM delivery WHERE channel='telegram'").fetchone()[0],"SKIPPED")
                box.db.close()

if __name__=="__main__":unittest.main()

