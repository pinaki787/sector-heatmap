import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from sector_heatmap import sector_cards as cards


class SectorCardsTest(unittest.TestCase):
    def history(self,asof="2026-10-21T09:15:00+05:30",observed="2026-10-21T09:31:00+05:30"):
        return {"modes":{"intraday":{s.sector_id:[dict(overall_score=65,
            relative_strength_score=60,rotation_state="IMPROVING",last_updated=asof,
            timestamp=observed)] for s in cards.SECTOR_DEFINITIONS}}}

    def test_schedule_only_session_slots_and_holidays(self):
        moment=lambda s:datetime.fromisoformat(s+"+05:30")
        self.assertIsNone(cards.schedule_slot(moment("2026-10-20T10:00:00")))
        self.assertIsNone(cards.schedule_slot(moment("2026-10-24T10:00:00")))
        self.assertIsNone(cards.schedule_slot(moment("2026-10-21T09:14:00")))
        self.assertTrue(cards.schedule_slot(moment("2026-10-21T09:44:00")).startswith("2026-10-21T09:15"))
        self.assertTrue(cards.schedule_slot(moment("2026-10-21T09:45:00")).startswith("2026-10-21T09:45"))
        self.assertIsNone(cards.schedule_slot(moment("2026-10-21T15:30:00")))

    def test_open_requires_fresh_market_bars_and_capture(self):
        now=cards.parse_time("2026-10-21T09:45:00+05:30")
        result=cards.snapshot_from_history(self.history(),now)
        self.assertEqual(len(result["rows"]),14)
        self.assertIn("not percentage",result["score_basis"])
        for hist in [self.history(asof="2026-10-19T15:15:00+05:30"),
                     self.history(observed="2026-10-21T08:00:00+05:30"),
                     self.history(asof="2026-10-21T10:15:00+05:30")]:
            with self.assertRaises(ValueError):cards.snapshot_from_history(hist,now)

    def test_closed_initial_explicit_and_last_session_only(self):
        now=cards.parse_time("2026-10-20T10:00:00+05:30")
        history=self.history("2026-10-19T15:15:00+05:30","2026-10-20T03:00:00+05:30")
        with self.assertRaises(ValueError):cards.snapshot_from_history(history,now)
        self.assertEqual(cards.snapshot_from_history(history,now,initial=True)["freshness"],"LAST COMPLETED SESSION")
        with self.assertRaises(ValueError):cards.snapshot_from_history(self.history("2026-10-16T15:15:00+05:30"),now,initial=True)

    def test_no_data_never_fabricated(self):
        with self.assertRaises(ValueError):cards.snapshot_from_history({},cards.parse_time("2026-10-21T10:00:00+05:30"))

    def test_render_and_email_inline_plus_attachment(self):
        snapshot=cards.snapshot_from_history(self.history(),cards.parse_time("2026-10-21T09:45:00+05:30"))
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"card.png"
            cards.render_card(snapshot,target)
            data=target.read_bytes()
            self.assertEqual(data[:8],b"\x89PNG\r\n\x1a\n")
            event=dict(id="synthetic-test",snapshot=snapshot)
            message=cards.email_message({"email":{"sender":"owner@example.com","recipient":"owner@example.com"}},event,data)
            parts=list(message.walk())
            self.assertEqual(sum(p.get_content_type()=="image/png" for p in parts),2)
            self.assertTrue(any(p.get("Content-ID")=="<sector-card>" for p in parts))
            self.assertEqual(len(list(message.iter_attachments())),1)
            self.assertIn("not percentage returns",cards.caption(event))

    def test_owner_only_fyers_source_resolution(self):
        config={"accounts":[{"broker":"FYERS","id":"owned"},{"broker":"DHAN","id":"other"}]}
        path=cards.history_path(config,Path("/synthetic"))
        self.assertIn("/owned/",str(path))
        with self.assertRaises(ValueError):cards.history_path({"accounts":[]})

    def test_job_dedup_retention_and_expiry(self):
        now=cards.parse_time("2026-10-21T09:45:00+05:30")
        clock=[now.timestamp()]
        with tempfile.TemporaryDirectory() as folder:
            private=Path(folder)
            source=private/"history.json";source.write_text(json.dumps(self.history()))
            config={"owner_username":"pinaki87"}
            with patch.object(cards,"PRIVATE",private),patch.object(cards,"history_path",return_value=source):
                box=cards.SectorOutbox(private/"outbox.sqlite3",lambda:clock[0])
                key=box.enqueue(config,now)
                self.assertIsNotNone(key)
                self.assertEqual(box.enqueue(config,now),key)
                self.assertEqual(box.status()["events"],1)
                self.assertEqual(len(list((private/"sector-cards").glob("*.png"))),1)
                clock[0]+=1801
                box.settle()
                self.assertEqual(box.status()["deliveries"],{"EXPIRED":2})
                self.assertEqual(box.db.execute("SELECT state FROM jobs").fetchone()[0],"EXPIRED")
                box.db.close()

    def test_delayed_card_keeps_thirty_minute_spacing(self):
        now=cards.parse_time("2026-10-21T09:35:00+05:30")
        clock=[now.timestamp()]
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"history.json";source.write_text(json.dumps(self.history()))
            with patch.object(cards,"PRIVATE",Path(folder)),patch.object(cards,"history_path",return_value=source):
                box=cards.SectorOutbox(Path(folder)/"outbox.sqlite3",lambda:clock[0])
                self.assertIsNotNone(box.enqueue({"owner_username":"pinaki87"},now))
                later=cards.parse_time("2026-10-21T09:45:00+05:30");clock[0]=later.timestamp()
                self.assertIsNone(box.enqueue({"owner_username":"pinaki87"},later))
                self.assertEqual(box.status()["events"],1)
                box.db.close()

    def test_stale_job_audit_without_delivery(self):
        now=cards.parse_time("2026-10-21T09:45:00+05:30")
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"history.json";source.write_text("{}")
            with patch.object(cards,"history_path",return_value=source):
                box=cards.SectorOutbox(Path(folder)/"outbox.sqlite3")
                self.assertIsNone(box.enqueue({"owner_username":"pinaki87"},now))
                self.assertEqual(box.status()["events"],0)
                self.assertEqual(box.db.execute("SELECT state FROM jobs").fetchone()[0],"WITHHELD")
                box.db.close()




    def test_handoff_caption_names_findings_and_direction(self):
        event={"id":"synthetic","kind":"HANDOFF_CARD","snapshot":{"mode":"intraday","freshness":"COMPLETED ANALYSIS","asof":"2026-10-21T10:45:00+05:30","source":"FYERS",
            "rows":[dict(name="Example Bearish Stock",direction="BEARISH",conviction_out_of_ten=10),dict(name="Example Bullish Stock",direction="BULLISH",conviction_out_of_ten=9)]}}
        text=cards.caption(event)
        self.assertIn("🔴 Example Bearish Stock · BEARISH · 10.00/10",text)
        self.assertIn("🟢 Example Bullish Stock · BULLISH · 9.00/10",text)
        self.assertLessEqual(len(text.encode("utf-16-le"))//2,1024)

    def test_handoff_empty_caption_says_no_eligible_recommendations(self):
        event={"id":"synthetic","kind":"HANDOFF_CARD","snapshot":{"mode":"intraday","freshness":"COMPLETED ANALYSIS","asof":"2026-10-21T10:45:00+05:30","source":"FYERS","rows":[]}}
        self.assertIn("No eligible recommendations",cards.caption(event))

if __name__=="__main__":unittest.main()
