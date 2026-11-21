import unittest,subprocess
from sector_heatmap.report_wait import wait_for_report
class Waiting(unittest.TestCase):
 def test_long_running_worker_is_not_terminated_and_progress_continues(self):
  class Process:
   calls=0
   def wait(self,timeout):
    self.calls+=1
    if self.calls<101:raise subprocess.TimeoutExpired("analysis",timeout)
    return 0
  p=Process();notices=[];clock=[0]
  def now():clock[0]+=15;return clock[0]
  wait_for_report(p,notices.append,clock=now)
  self.assertEqual(p.calls,101);self.assertGreater(len(notices),3);self.assertGreater(notices[-1],900)
 def test_explicit_failure_is_reported(self):
  class Process:
   def wait(self,timeout):return 1
  with self.assertRaises(RuntimeError):wait_for_report(Process(),lambda elapsed:None)

class FinishedReports(unittest.TestCase):
 def test_completed_reporting_run_can_publish_after_close(self):
  from sector_heatmap.notification_sessions import gate
  self.assertEqual(gate(dict(kind="COMBINED_CARD",completed_run=True),0,now=0),(None,None))
 def test_trade_events_do_not_inherit_report_exception(self):
  from sector_heatmap.notification_sessions import gate
  self.assertEqual(gate(dict(kind="POSITION_SUMMARY",completed_run=True),0,now=0)[0],"SKIPPED")

 def test_completed_report_is_not_expired_by_parent_outbox(self):
  import tempfile,json
  from pathlib import Path
  from sector_heatmap.combined_reports import CombinedOutbox
  with tempfile.TemporaryDirectory() as folder:
   box=CombinedOutbox(Path(folder)/"box.db",clock=lambda:4000,recover=False)
   with box.db:
    box.db.execute("INSERT INTO events VALUES(?,?,0)",("completed",json.dumps(dict(kind="COMBINED_CARD",completed_run=True))))
    box.db.execute("INSERT INTO delivery(event,channel,state,updated) VALUES('completed','telegram','PENDING',0)")
   box.settle()
   self.assertEqual(box.db.execute("SELECT state FROM delivery").fetchone()[0],"PENDING")
   box.db.close()
