import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
from datetime import datetime
from sector_heatmap import market_brief_panels as p,market_brief_delivery as d,combined_reports as c
from sector_heatmap.market_calendar import IST
from sector_heatmap.sectors import SECTOR_DEFINITIONS
from tests.test_market_brief_mtf import payload,NOW
from sector_heatmap.market_brief_visual import sector_public,handoff_public
from tests.test_market_brief_visual import report

def snapshot():
 mtf=payload((-2,-2,-2,-2));template=mtf["sectors"][0]
 mtf["sectors"]=[{**template,"sector_id":x.sector_id} for x in SECTOR_DEFINITIONS]
 sec=sector_public({"rows":[dict(sector_id=x.sector_id,score=40,rotation="LAGGING",asof="2026-10-23T15:15:00+05:30") for x in SECTOR_DEFINITIONS]}, {},mtf,NOW)
 return dict(generated=NOW.isoformat(),sector_visual=sec,handoff_visual=handoff_public(report(),NOW),positions=["PRIVATE_HOLDING"],capital=987654321)
class PanelRenderTests(unittest.TestCase):
 def test_complete_ordered_sectors_then_handoff_and_phone_text(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as f:
   panels=p.render_panels(snapshot(),Path(f)/"report.png")
   names=[name for panel in panels for name in panel["sector_names"]]
   self.assertEqual(len(names),14);self.assertEqual(len(set(names)),14);self.assertEqual(len(panels),6)
   self.assertEqual([x["kind"] for x in panels],["sectors"]*5+["handoff"])
   self.assertEqual([len(x["sector_names"]) for x in panels[:5]],[3,3,3,3,2])
   for i,x in enumerate(panels):
    self.assertEqual(x["index"],i);self.assertLessEqual(len(x["public_caption"].encode("utf-16-le"))//2,1024)
    with Image.open(x["image"]) as im:
     scale=min(360/im.width,500/im.height)
     self.assertGreaterEqual(p.MIN_BODY_FONT*scale,14)
     self.assertLessEqual(im.height,1000);self.assertEqual(im.width,720)
 def test_stale_missing_and_empty_inputs_render_without_clipping(self):
  with tempfile.TemporaryDirectory() as f:
   s=snapshot();s["sector_visual"]["rows"][0]["mtf"]={"alignment":"UNAVAILABLE","frames":{},"evidence":"INCOMPLETE"}
   self.assertEqual(len(p.render_panels(s,Path(f)/"s.png")),6)
   panels=p.render_panels({},Path(f)/"empty.png");self.assertEqual(len(panels),2)
 def test_only_public_market_fields_in_captions_and_manifest(self):
  with tempfile.TemporaryDirectory() as f:
   panels=p.render_panels(snapshot(),Path(f)/"s.png");body=json.dumps(panels)
   self.assertNotIn("PRIVATE_HOLDING",body);self.assertNotIn("987654321",body)
   self.assertIn("15m",panels[0]["public_caption"]);self.assertIn("Weekly",panels[0]["public_caption"])
 def test_at_most_two_handoff_findings_keep_set_bounded(self):
  with tempfile.TemporaryDirectory() as f:
   s=snapshot();s["handoff_visual"]["rows"]*=5
   panels=p.render_panels(s,Path(f)/"s.png");self.assertEqual(len(panels),7)
 def test_captured_ai_wait_is_preserved(self):
  r=report();r["ai_provider"]="CODEX_CHATGPT";r["ai_review"]={"recommendations":[{"symbol":"NSE:VOLTAS-EQ","decision":"WAIT"}]}
  self.assertEqual(handoff_public(r,NOW)["rows"][0]["review_decision"],"WAIT")

class PanelDeliveryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.box=c.CombinedOutbox(Path(self.temp.name)/"box.sqlite3",clock=lambda:100,recover=False)
  self.config={"owner_username":"owner","telegram":{"chat_id":-111},"combined_reports":{"enabled":True},"telegram_destinations":{"enabled":True,"shared_market":{"enabled":True,"chat_id":-111,"activated_at":1},"private_trades":{"enabled":True,"chat_id":-222,"activated_at":1}}}
  self.event=dict(id="test",owner_username="owner",kind="COMBINED_CARD",public_text="Public fallback",panels=[dict(index=i,image="p"+str(i),image_sha256="hash",public_caption="Public "+str(i)) for i in range(3)])
  self.legacy=Mock(return_value=("SENT",None));self.calls=[]
  self.addCleanup(self.box.db.close)
 def send(self,channel,config,event,audit):
  self.assertEqual(event["kind"],"COMBINED_CARD");i=event["panel_index"];self.calls.append(i);audit({"ok":True,"result":{"message_id":1000+i,"chat":{"id":-111},"date":100}});return "SENT",None
 def deliver(self,sender=None):
  with patch.object(d,"media_bytes",return_value=b"verified"),patch.object(d,"send_card",side_effect=sender or self.send),patch.object(d,"private_write"):
   return d.deliver_panels(self.box,"telegram",self.config,self.event,self.legacy)
 def test_one_ordered_set_and_repeat_never_resends_accepted_panels(self):
  self.assertEqual(self.deliver()[0],"SENT");self.assertEqual(self.calls,[0,1,2])
  self.assertEqual(self.deliver()[0],"SENT");self.assertEqual(self.calls,[0,1,2]);self.legacy.assert_not_called()
 def test_partial_rejection_retries_only_unaccepted_panels(self):
  first=True
  def sender(channel,config,event,audit):
   nonlocal first
   if event["panel_index"]==1 and first:first=False;return "RETRY","Telegram HTTP 429"
   return self.send(channel,config,event,audit)
  self.assertEqual(self.deliver(sender)[0],"RETRY");self.assertEqual(self.calls,[0])
  self.assertEqual(self.deliver(sender)[0],"SENT");self.assertEqual(self.calls,[0,1,2]);self.legacy.assert_not_called()
 def test_unknown_second_panel_stops_remaining_and_never_replays(self):
  def sender(channel,config,event,audit):
   return ("REVIEW","Timeout unknown") if event["panel_index"]==1 else self.send(channel,config,event,audit)
  self.assertEqual(self.deliver(sender)[0],"REVIEW");self.assertEqual(self.calls,[0]);self.legacy.assert_not_called()
  self.assertEqual(self.deliver()[0],"REVIEW");self.assertEqual(self.calls,[0])
 def test_crash_after_send_started_requires_review(self):
  with self.box.db:
   self.box.db.execute("INSERT INTO brief_panels VALUES(?,?,?,'SENDING',NULL,NULL,?,100)",(self.event["id"],0,json.dumps(self.event["panels"][0],sort_keys=True),hashlib.sha256(b"-111").hexdigest()))
  d.initialize(self.box,True)
  self.assertEqual(self.box.db.execute("SELECT state FROM brief_panels").fetchone()[0],"REVIEW")
  self.assertEqual(self.deliver()[0],"REVIEW");self.assertEqual(self.calls,[])
 def test_first_authoritative_photo_rejection_uses_one_persistent_text_mode(self):
  sender=Mock(return_value=("RETRY","Telegram HTTP 400"))
  self.assertEqual(self.deliver(sender)[0],"SENT");sender.assert_called_once();self.legacy.assert_called_once()
  self.assertEqual(self.box.db.execute("SELECT mode FROM brief_modes").fetchone()[0],"TEXT")
 def test_definitive_rejection_after_partial_set_does_not_duplicate_whole_text(self):
  def sender(channel,config,event,audit):return ("RETRY","Telegram HTTP 400") if event["panel_index"]==1 else self.send(channel,config,event,audit)
  self.assertEqual(self.deliver(sender)[0],"REVIEW");self.assertEqual(self.calls,[0]);self.legacy.assert_not_called()
 def test_server_error_is_uncertain_not_a_retry_or_fallback(self):
  self.assertEqual(self.deliver(Mock(return_value=("RETRY","Telegram HTTP 500")))[0],"REVIEW");self.legacy.assert_not_called()
 def test_destination_change_blocks_remaining_panels(self):
  self.assertEqual(self.deliver()[0],"SENT");self.config["telegram"]["chat_id"]=-333;self.config["telegram_destinations"]["shared_market"]["chat_id"]=-333
  self.assertEqual(self.deliver()[0],"REVIEW");self.assertEqual(self.calls,[0,1,2])
 def test_missing_panel_before_send_falls_back_without_any_photos(self):
  with patch.object(d,"media_bytes",side_effect=FileNotFoundError),patch.object(d,"send_card") as photo:
   self.assertEqual(d.deliver_panels(self.box,"telegram",self.config,self.event,self.legacy)[0],"SENT");photo.assert_not_called();self.legacy.assert_called_once()
 def test_changed_retained_image_is_withheld(self):
  with patch.object(d,"media_bytes",side_effect=ValueError),patch.object(d,"send_card") as photo:
   self.assertEqual(d.deliver_panels(self.box,"telegram",self.config,self.event,self.legacy)[0],"REVIEW");photo.assert_not_called();self.legacy.assert_not_called()
 def test_shared_route_enforced(self):
  self.config["telegram"]["chat_id"]=-222;self.assertEqual(self.deliver()[0],"REVIEW");self.assertEqual(self.calls,[])
 def test_real_retained_files_keep_combined_route_and_public_caption(self):
  from sector_heatmap import sector_cards
  root=Path(self.temp.name);folder=root/"combined-reports";folder.mkdir()
  for panel in self.event["panels"]:
   path=folder/(str(panel["index"])+".png");path.write_bytes(b"verified")
   panel.update(image=str(path),image_sha256=hashlib.sha256(b"verified").hexdigest(),kind="sectors")
  def real_check(channel,config,event,audit):
   self.assertEqual(sector_cards.media_bytes(event),b"verified");self.assertTrue(sector_cards.caption(event).startswith("Public"))
   return self.send(channel,config,event,audit)
  with patch.object(sector_cards,"PRIVATE",root),patch.object(d,"send_card",side_effect=real_check),patch.object(d,"private_write"):
   self.assertEqual(d.deliver_panels(self.box,"telegram",self.config,self.event,self.legacy)[0],"SENT")
 def test_expired_slot_sends_no_panels(self):
  self.event["delivery_slot"]="1970-01-01T05:15:00+05:30"
  self.assertEqual(self.deliver()[0],"REVIEW");self.assertEqual(self.calls,[])
 def test_slot_change_after_partial_delivery_withholds_remainder(self):
  clock=[100];self.box.clock=lambda:clock[0];self.event["delivery_slot"]="1970-01-01T05:30:00+05:30"
  def sender(channel,config,event,audit):
   outcome=self.send(channel,config,event,audit);clock[0]=1000;return outcome
  self.assertEqual(self.deliver(sender)[0],"REVIEW");self.assertEqual(self.calls,[0]);self.legacy.assert_not_called()
 def test_parent_slot_delivery_becomes_sent_without_a_second_set(self):
  with self.box.db:
   self.box.db.execute("INSERT INTO events VALUES(?,?,100)",(self.event["id"],json.dumps(self.event)))
   self.box.db.execute("INSERT INTO delivery(event,channel,state,updated) VALUES(?,'telegram','PENDING',100)",(self.event["id"],))
  with patch.object(d,"media_bytes",return_value=b"ok"),patch.object(d,"send_card",side_effect=self.send),patch.object(d,"private_write"),patch("sector_heatmap.notification_controls.gate",return_value=(None,None)):
   self.box.deliver(self.config);self.box.deliver(self.config)
  self.assertEqual(self.calls,[0,1,2]);self.assertEqual(self.box.db.execute("SELECT state FROM delivery").fetchone()[0],"SENT")
if __name__=="__main__":unittest.main()
