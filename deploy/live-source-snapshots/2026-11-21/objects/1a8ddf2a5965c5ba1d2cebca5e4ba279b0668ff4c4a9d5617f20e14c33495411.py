import unittest,tempfile,json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.combined_reports import slot,screen_section,handoff_section,enqueue,CombinedOutbox,ACCOUNT
from sector_heatmap.notification_destinations import telegram_destination
from sector_heatmap.market_calendar import IST
class CombinedTests(unittest.TestCase):
 def test_market_slots_and_closed_session(self):
  now=datetime(2026,10,23,10,34,tzinfo=IST)
  self.assertEqual(slot(now),"2026-10-23T10:30:00+05:30")
  self.assertIsNone(slot(datetime(2026,10,24,10,0,tzinfo=IST)))
  self.assertIsNone(slot(datetime(2026,10,20,10,0,tzinfo=IST)))
  self.assertIsNone(slot(datetime(2026,10,23,9,0,tzinfo=IST)))
  self.assertIsNone(slot(datetime(2026,10,23,16,0,tzinfo=IST)))
 def test_recent_timestamp_never_overrides_broker_delayed_quality(self):
  now=datetime(2026,10,23,12,23,tzinfo=IST)
  report={"status":"COMPLETED","generated_at":now.isoformat(),"results":[{"symbol":"TEST","decision":"WATCHLIST","timeframe_states":{"15m":{"last_updated":"2026-10-23T12:00:00+05:30","data_quality":"DELAYED"}}}]}
  section=screen_section(report,now)
  self.assertIn("DELAYED",section["status"]);self.assertNotIn("CURRENT",section["status"])
 def test_scope_and_unavailable_are_explicit(self):
  now=datetime(2026,10,23,11,0,tzinfo=IST)
  self.assertEqual(screen_section({"account_id":"foreign"},now)["status"],"UNAVAILABLE")
  s=screen_section({"status":"UNAVAILABLE"},now)
  self.assertIn("no current recommendation",s["lines"][-1])
 def test_options_never_confuse_underlying_and_premium(self):
  result={"generated_at":"2026-10-23T11:00:00+05:30","cards":[{"candidate":{"symbol":"NSE:VBL-EQ","timeframe_states":{"15m":{"last_updated":"2026-10-23T10:45:00+05:30"}}},"analysis":{"kind":"LONG_OPTION","direction":"BEARISH","entry":389.25,"recommended_invalidation":{"price":411.74},"proposal":{"target_exit_points":10}}}]}
  section=handoff_section(result,0,datetime(2026,10,23,11,0,tzinfo=IST))
  self.assertIn("proposed invalidation 411.74",section["lines"][-1])
  self.assertIn("option-premium target 10.00",section["lines"][-1])
 def test_public_summary_omits_private_account_fields(self):
  result={"cards":[],"positions":[{"symbol":"PRIVATE"}],"risk_policy":{"capital":987654}}
  section=handoff_section(result,1792733400,datetime(2026,10,23,11,0,tzinfo=IST))
  self.assertNotIn("PRIVATE",json.dumps(section));self.assertNotIn("987654",json.dumps(section))
 def test_combined_route_and_separate_post_suppression(self):
  config={"owner_username":"owner","combined_reports":{"enabled":True},"telegram":{},"telegram_destinations":{"enabled":True,"shared_market":{"enabled":True,"chat_id":-111,"activated_at":1},"private_trades":{"enabled":True,"chat_id":-222,"activated_at":1}}}
  routed,error=telegram_destination(config,{"kind":"COMBINED_CARD","owner_username":"owner"},2)
  self.assertIsNone(error);self.assertEqual(routed["telegram"]["chat_id"],-111)
  for kind in ("SECTOR_CARD","HANDOFF_CARD"):
   self.assertIsNone(telegram_destination(config,{"kind":kind,"owner_username":"owner"},2)[0])
  private,_=telegram_destination(config,{"kind":"POSITION_SUMMARY","owner_username":"owner"},2)
  self.assertEqual(private["telegram"]["chat_id"],-222)
 def test_one_event_per_slot_telegram_only_and_expiry(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);now=[100]
   box=CombinedOutbox(root/"box.sqlite3",clock=lambda:now[0],recover=False)
   snapshot={"generated":"2026-10-23T11:00:00+05:30"}
   def image(snapshot,path):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"verified")
    return [dict(index=0,image=str(path),image_sha256="test",public_caption="Public",kind="sectors")]
   with patch("sector_heatmap.combined_reports.PRIVATE",root),patch("sector_heatmap.market_brief_panels.render_panels",image):
    first=enqueue(box,{"owner_username":"owner"},snapshot,"slot")
    self.assertEqual(first,enqueue(box,{"owner_username":"owner"},snapshot,"slot"))
   self.assertEqual(box.db.execute("select channel from delivery").fetchall(),[("telegram",)])
   now[0]=1001;box.settle()
   self.assertEqual(box.db.execute("select state from delivery").fetchone()[0],"EXPIRED")


class ScreenerWorkerTests(unittest.TestCase):
 def test_full_universe_is_scanned_without_execution_or_silent_truncation(self):
  from sector_heatmap import combined_screener_worker as worker
  import os
  with tempfile.TemporaryDirectory() as folder:
   req=Path(folder)/"request.json";out=Path(folder)/"output.json"
   req.write_text(json.dumps({"account_id":ACCOUNT,"broker":"FYERS","symbols":["TEST"+str(i) for i in range(134)],"universe_asof":"2026-10-23T10:00:00+05:30"}))
   seen=[]
   def analyze(payload,service):
    seen.extend(payload["symbols"])
    return {"results":[{"symbol":payload["symbols"][0],"decision":"WATCHLIST","timeframe_states":{"15m":{"data_quality":"READY"}}}]}
   with patch.dict(os.environ,{"SECTOR_PULSE_WORKSPACE_ID":ACCOUNT}),patch.object(worker,"owned_token",return_value="PRIVATE"),patch.object(worker,"build_service"),patch.object(worker,"analyze",side_effect=analyze):
    worker.run(req,out,pace=0)
   result=json.loads(out.read_text())
   self.assertEqual(result["analyzed"],134);self.assertEqual(result["total"],134)
   self.assertEqual(len(set(seen)),134);self.assertEqual(result["status"],"COMPLETED");self.assertEqual(result["order_authority"],"NONE")
 def test_unavailable_data_stops_bounded_scan_and_never_claims_complete(self):
  from sector_heatmap import combined_screener_worker as worker
  import os
  with tempfile.TemporaryDirectory() as folder:
   req=Path(folder)/"r.json";out=Path(folder)/"o.json"
   req.write_text(json.dumps({"account_id":ACCOUNT,"broker":"FYERS","symbols":["X"+str(i) for i in range(50)],"universe_asof":"2026-10-23T10:00:00+05:30"}))
   with patch.dict(os.environ,{"SECTOR_PULSE_WORKSPACE_ID":ACCOUNT}),patch.object(worker,"owned_token",return_value="PRIVATE"),patch.object(worker,"build_service"),patch.object(worker,"analyze",return_value={"results":[{"decision":"REJECT","timeframe_states":{}}]}):
    worker.run(req,out,pace=0)
   result=json.loads(out.read_text());self.assertEqual(result["status"],"UNAVAILABLE");self.assertEqual(result["analyzed"],3);self.assertEqual(result["total"],50)
 def test_foreign_worker_scope_fails_before_provider_or_token_read(self):
  from sector_heatmap import combined_screener_worker as worker
  import os
  with tempfile.TemporaryDirectory() as folder:
   req=Path(folder)/"r.json";req.write_text(json.dumps({"account_id":"foreign","broker":"FYERS"}))
   with patch.dict(os.environ,{"SECTOR_PULSE_WORKSPACE_ID":ACCOUNT}),patch.object(worker,"owned_token") as token:
    with self.assertRaisesRegex(ValueError,"account mismatch"):worker.run(req,Path(folder)/"o.json")
    token.assert_not_called()
if __name__=="__main__":unittest.main()
