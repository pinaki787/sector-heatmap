import json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.handoff_cards import scheduled_report,completed_jobs,summary,HandoffOutbox
from sector_heatmap.sector_cards import caption

class ScheduledStatusTests(unittest.TestCase):
 account={"id":"owned","broker":"FYERS","owner_username":"owner"}
 def saved(self):
  return {"account_id":"owned","broker":"FYERS","report":{"cards":[],"exclusions":[]}}
 def test_completed_empty_status_is_public_and_not_a_new_recommendation(self):
  r=scheduled_report(self.account,"COMPLETED",time.time(),self.saved())
  self.assertEqual(r["scheduled_status"]["code"],"NO_NEW_SIGNALS")
  self.assertFalse(r["cards"]);self.assertEqual(r["order_authority"],"NONE")
 def test_rate_limit_is_not_claimed_as_a_healthy_empty_scan(self):
  saved=self.saved();saved["report"]["exclusions"]=[{"reason":"You've reached your API request limit. Please retry."}]
  r=scheduled_report(self.account,"COMPLETED",time.time(),saved)
  self.assertEqual(r["scheduled_status"]["code"],"RATE_LIMITED")
  snap=summary(r,"FYERS",time.time())
  text=caption({"kind":"HANDOFF_CARD","id":"synthetic","snapshot":snap})
  self.assertIn("request limit",text);self.assertIn("Check time:",text)
  self.assertNotIn("Data as of:",text);self.assertIn("UNAVAILABLE",snap["freshness"])
 def test_failed_scan_suppresses_private_raw_error_and_account_state(self):
  r=scheduled_report(self.account,"REVIEW",time.time(),{},'account private funds 123456 internal-cookie')
  text=json.dumps(r)
  self.assertEqual(r["scheduled_status"]["code"],"DATA_UNAVAILABLE")
  self.assertNotIn("123456",text);self.assertNotIn("cookie",text)
 def test_scope_mismatch_is_never_published(self):
  saved=self.saved();saved["account_id"]="other"
  self.assertIsNone(scheduled_report(self.account,"COMPLETED",time.time(),saved))
 def test_real_findings_are_preserved(self):
  saved=self.saved();saved["report"]["cards"]=[{"candidate":{"name":"Synthetic"}}]
  self.assertEqual(scheduled_report(self.account,"COMPLETED",time.time(),saved),saved["report"])
 def test_completed_and_failed_slots_both_surface_but_running_does_not(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/".private/dashboard-login/accounts/owned";folder.mkdir(parents=True)
   with sqlite3.connect(folder/"handoff-schedule.sqlite3") as db:
    db.execute("CREATE TABLE runs(slot TEXT,state TEXT,updated REAL,output TEXT,error TEXT)")
    for i,state in enumerate(["COMPLETED","REVIEW","RUNNING"]):
     db.execute("INSERT INTO runs VALUES(?,?,?,?,?)",(str(i),state,time.time(),json.dumps(self.saved()) if state=="COMPLETED" else None,"private error" if state=="REVIEW" else None))
   with patch("sector_heatmap.handoff_cards.owner_id",return_value="owner"):
    rows=list(completed_jobs({"accounts":[self.account]},root))
   self.assertEqual(len(rows),2)
   self.assertEqual({r[3]["scheduled_status"]["code"] for r in rows},{"NO_NEW_SIGNALS","DATA_UNAVAILABLE"})
 def test_slot_status_is_deduplicated_and_empty_email_stays_suppressed(self):
  with tempfile.TemporaryDirectory() as tmp:
   now=time.time();root=Path(tmp)
   with patch("sector_heatmap.handoff_cards.PRIVATE",root):
    box=HandoffOutbox(root/"outbox.sqlite3",clock=lambda:now)
    r=scheduled_report(self.account,"COMPLETED",now,self.saved())
    first=box.enqueue_job(self.account,"scheduled-slot",now,r)
    self.assertTrue(first);self.assertEqual(box.enqueue_job(self.account,"scheduled-slot",now,r),first)
    self.assertEqual(box.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],1)
    self.assertEqual(dict(box.db.execute("SELECT channel,state FROM delivery")),{"email":"SKIPPED","telegram":"PENDING"})
    box.db.close()
