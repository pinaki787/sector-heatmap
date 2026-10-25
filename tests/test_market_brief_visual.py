import unittest,tempfile,json,urllib.error
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from sector_heatmap import market_brief_visual as v,combined_reports as c
from sector_heatmap.market_calendar import IST
from sector_heatmap.sectors import SECTOR_DEFINITIONS
NOW=datetime(2026,10,23,12,0,tzinfo=IST)

def report():
 return {"generated_at":NOW.isoformat(),"positions":[{"symbol":"PRIVATE_HOLDING"}],"capital":987654321,"account_id":"PRIVATE_ACCOUNT","cards":[{"candidate":{"symbol":"NSE:VOLTAS-EQ","timeframe_states":{"15m":{"last_updated":NOW.isoformat(),"data_quality":"DELAYED"}}},"analysis":{"kind":"LONG_OPTION","direction":"BEARISH","status":"REQUIRES_INVALIDATION_ACCEPTANCE","entry":950,"recommended_invalidation":{"price":981},"thesis":"PRIVATE_PNL","proposed_sizing":{"quantity":123456},"proposal":{"entry_points":8.8,"target_exit_points":17.6,"premium_stop_estimate":{"stop_loss_price":.55},"legs":[{"symbol":"NSE:VOLTAS26OCT940PE"}]}}}]}
def snapshot():
 return {"generated":NOW.isoformat(),"sector_visual":{"rows":[],"known":0,"total":14,"status":"UNAVAILABLE","regime":"Evidence unavailable"},"handoff_visual":v.handoff_public(report(),NOW)}
class VisualTests(unittest.TestCase):
 def test_public_projection_excludes_personal_payload(self):
  result=v.handoff_public(report(),NOW);body=json.dumps(result)+v.caption(snapshot())+v.fallback_text(snapshot())
  for secret in ("PRIVATE_HOLDING","987654321","PRIVATE_ACCOUNT","PRIVATE_PNL","123456"):self.assertNotIn(secret,body)
  self.assertNotIn("quantity",body);self.assertNotIn("capital",body)
 def test_legacy_underlying_and_premium_remain_separate(self):
  row=v.handoff_public(report(),NOW)["rows"][0];h=row["horizons"][0]
  self.assertEqual(h["name"],"shared plan");self.assertEqual(h["underlying"]["stop_loss"],981);self.assertEqual(h["premium"]["stop_loss"],.55)
  self.assertEqual(row["contract"],"NSE:VOLTAS26OCT940PE")
 def test_new_horizons_are_never_recalculated_or_used_as_orders(self):
  r=report();r["cards"][0]["analysis"]["report_levels"]={"horizons":{"intraday":{"underlying":{"entry":950,"stop_loss":952.3,"target":947.7},"premium":{"entry":8.8,"stop_loss":7.5,"target":10.25}}}}
  rows=v.handoff_public(r,NOW)["rows"][0]["horizons"]
  self.assertEqual(rows[0]["underlying"]["stop_loss"],952.3);self.assertIsNone(rows[1]["underlying"]["entry"])
 def test_delayed_and_old_data_never_claim_current(self):
  h=v.handoff_public(report(),datetime(2026,10,25,12,0,tzinfo=IST));self.assertIn("DELAYED",h["status"]);self.assertIn("STALE",h["status"])
 def test_score_delta_uses_distinct_completed_candle_not_repeat_observation(self):
  sid=SECTOR_DEFINITIONS[0].sector_id
  history={"modes":{"intraday":{sid:[{"last_updated":"2026-10-23T11:30:00+05:30","overall_score":50},{"last_updated":"2026-10-23T11:45:00+05:30","overall_score":55}]}}}
  snap={"rows":[{"sector_id":sid,"score":56,"asof":"2026-10-23T11:45:00+05:30","rotation":"IMPROVING"}]}
  self.assertEqual(v.sector_public(snap,history)["rows"][0]["delta"],6)
  snap["rows"][0]["asof"]="2026-10-24T11:45:00+05:30"
  self.assertIsNone(v.sector_public(snap,history)["rows"][0]["delta"])
 def test_caption_and_fallback_limits_and_disclaimer(self):
  s=snapshot();s["handoff_visual"]["rows"]*=2
  body=v.caption(s);self.assertLessEqual(len(body.encode("utf-16-le"))//2,1024)
  self.assertIn("No order or fill confirmation",body);self.assertLessEqual(len(v.fallback_text(s)),3900)
 def test_render_empty_and_realistic_missing_values(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder:
   for i,s in enumerate(({},snapshot())):
    p=Path(folder)/f"{i}.png";result=v.render(s,p);im=Image.open(p)
    self.assertEqual(im.width,960);self.assertLess(im.width+im.height,10000);self.assertLess(result["bytes"],9_000_000);im.close()
 def test_free_text_status_and_invalid_numbers_are_withheld(self):
  r=report();a=r["cards"][0]["analysis"];a["status"]="SECRET_ACCOUNT";a["entry"]=float("inf");a["proposal"]["entry_points"]=float("nan")
  body=v.handoff_public(r,NOW);self.assertNotIn("SECRET_ACCOUNT",json.dumps(body));self.assertIsNone(body["rows"][0]["horizons"][0]["premium"]["entry"])

class DeliveryTests(unittest.TestCase):
 def config(self):return {"telegram":{"chat_id":-111,"token":"TEST"},"telegram_destinations":{"enabled":True,"shared_market":{"enabled":True,"chat_id":-111},"private_trades":{"enabled":True,"chat_id":-222}}}
 def event(self):return {"id":"test","kind":"COMBINED_CARD","public_text":"Public analysis only"}
 def test_image_render_failure_retains_one_text_event(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);box=c.CombinedOutbox(root/"box.sqlite3",recover=False)
   with patch.object(c,"PRIVATE",root),patch("sector_heatmap.market_brief_panels.render_panels",side_effect=RuntimeError("renderer failed")):
    first=c.enqueue(box,{"owner_username":"test"},snapshot(),"slot");self.assertEqual(first,c.enqueue(box,{"owner_username":"test"},snapshot(),"slot"))
   payload=json.loads(box.db.execute("SELECT payload FROM events").fetchone()[0]);self.assertTrue(payload["text_only"]);self.assertIsNone(payload["image_sha256"])
   self.assertEqual(box.db.execute("SELECT count(*) FROM delivery").fetchone()[0],1)
 def test_only_authoritative_photo_rejection_falls_back(self):
  with patch("sector_heatmap.sector_cards.media_bytes",return_value=b"ok"),patch.object(c,"send_card",return_value=("RETRY","Telegram HTTP 400")),patch.object(c,"send_text",return_value=("SENT",None)) as send:
   self.assertEqual(c.deliver_card("telegram",self.config(),self.event())[0],"SENT");send.assert_called_once()
 def test_unknown_photo_outcome_never_sends_fallback(self):
  for result in (("REVIEW","Telegram image outcome unknown"),("RETRY","Telegram HTTP 500"),("SENT",None)):
   with patch("sector_heatmap.sector_cards.media_bytes",return_value=b"ok"),patch.object(c,"send_card",return_value=result),patch.object(c,"send_text") as send:
    c.deliver_card("telegram",self.config(),self.event());send.assert_not_called()
 def test_private_and_unverified_routes_never_send(self):
  for config in ({"telegram":{}},self.config()):
   if config.get("telegram_destinations"):config["telegram"]["chat_id"]=-222
   with patch.object(c,"send_card") as photo,patch.object(c,"send_text") as text:
    self.assertEqual(c.deliver_card("telegram",config,self.event())[0],"REVIEW");photo.assert_not_called();text.assert_not_called()
 def test_missing_file_falls_back_before_any_photo_request(self):
  with patch("sector_heatmap.sector_cards.media_bytes",side_effect=FileNotFoundError),patch.object(c,"send_card") as photo,patch.object(c,"send_text",return_value=("SENT",None)) as text:
   self.assertEqual(c.deliver_card("telegram",self.config(),self.event())[0],"SENT");photo.assert_not_called();text.assert_called_once()
 def test_hash_mismatch_does_not_transmit_changed_image(self):
  with patch("sector_heatmap.sector_cards.media_bytes",side_effect=ValueError),patch.object(c,"send_card") as photo,patch.object(c,"send_text") as text:
   self.assertEqual(c.deliver_card("telegram",self.config(),self.event())[0],"REVIEW");photo.assert_not_called();text.assert_not_called()
 def test_text_transport_unknown_does_not_auto_retry(self):
  with patch("urllib.request.urlopen",side_effect=TimeoutError):self.assertEqual(c.send_text(self.config(),self.event(),lambda _:None)[0],"REVIEW")
 def test_text_transport_uses_only_public_body(self):
  import io
  response=io.BytesIO(b'{"ok":true,"result":{"message_id":10}}')
  event={**self.event(),"snapshot":{"capital":987654,"positions":["SECRET"]}}
  with patch("urllib.request.urlopen",return_value=response) as url:
   self.assertEqual(c.send_text(self.config(),event,lambda _:None)[0],"SENT")
   body=json.loads(url.call_args[0][0].data);self.assertEqual(body["text"],"Public analysis only");self.assertNotIn("SECRET",str(body));self.assertEqual(body["chat_id"],-111)
if __name__=="__main__":unittest.main()
