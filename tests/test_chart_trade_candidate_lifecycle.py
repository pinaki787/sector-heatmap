"""Execute the actual candidate's startup/cleanup try block with mocked services only."""
import ast,os,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
SOURCE=Path(os.environ.get("CHART_ORDER_CANDIDATE_WEB","/unavailable"))
@unittest.skipUnless(SOURCE.is_file(),"Set explicit candidate web source")
class CandidateLifecycle(unittest.TestCase):
 def run_lifecycle(self,guard=True,recovery_error=None,serve_error=None):
  tree=ast.parse(SOURCE.read_text())
  nodes=[n for n in ast.walk(tree) if isinstance(n,ast.Try) and any(isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=="serve_forever" for body in n.body for c in ast.walk(body))]
  self.assertEqual(len(nodes),1)
  block=nodes[0]
  resume=Mock(side_effect=recovery_error);close=Mock();server=Mock();server.serve_forever.side_effect=serve_error
  monitor=Mock();jobs=Mock();dhan=Mock();delta_stream=Mock();delta=Mock();telegram=Mock();sensex=Mock();nifty=Mock();ema=Mock();feed=Mock()
  sector=SimpleNamespace(running=True);analysis=SimpleNamespace(running=True)
  scope=dict(workspace_guard=object() if guard else None,resume_chart_orders=resume,close_chart_orders=close,server=server,port=0,
   fyers_execution=object(),delta_india=delta,handoff_exit_monitor=monitor,persistent_jobs=jobs,dhan_chart_stream=dhan,delta_workspace_stream=delta_stream,
   telegram_polling=telegram,dhan_sector_services={"test":sector},state={"sector_analysis":analysis,"feed":feed},sensex_straddle=sensex,nifty_straddle=nifty,ema_chart_stream=ema,print=Mock())
  caught=None
  try:exec(compile(ast.fix_missing_locations(ast.Module(body=[block],type_ignores=[])),str(SOURCE),"exec"),scope)
  except Exception as error:caught=error
  close.assert_called_once_with(server);server.server_close.assert_called_once()
  monitor.close.assert_called_once();jobs.close.assert_called_once_with(wait=False);dhan.stop.assert_called_once();delta_stream.stop.assert_called_once()
  telegram.stop.assert_called_once();sensex.stop.assert_called_once();nifty.stop.assert_called_once();ema.stop.assert_called_once();feed.stop.assert_called_once()
  self.assertFalse(sector.running);self.assertFalse(analysis.running)
  delta.monitoring_stop.set.assert_called_once();delta.stop_event.set.assert_called_once()
  return resume,server,caught
 def test_normal_private_recovery_and_shutdown(self):
  resume,server,error=self.run_lifecycle()
  resume.assert_called_once();server.serve_forever.assert_called_once();self.assertIsNone(error)
 def test_no_private_guard_does_not_recover(self):
  resume,server,error=self.run_lifecycle(guard=False)
  resume.assert_not_called();server.serve_forever.assert_called_once();self.assertIsNone(error)
 def test_recovery_failure_still_closes_every_resource(self):
  error=ValueError("simulated unreadable journal")
  resume,server,caught=self.run_lifecycle(recovery_error=error)
  resume.assert_called_once();server.serve_forever.assert_not_called();self.assertIs(caught,error)
 def test_serve_failure_still_closes_every_resource(self):
  error=RuntimeError("simulated server failure")
  resume,server,caught=self.run_lifecycle(serve_error=error)
  self.assertIs(caught,error)
 def test_keyboard_shutdown_closes_resources(self):
  resume,server,error=self.run_lifecycle(serve_error=KeyboardInterrupt())
  self.assertIsNone(error)
