import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sector_heatmap.trade_notifications import Outbox, ledger_rows, sources, render, send, paper_journal_rows


class NotificationsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "outbox.sqlite3"
        self.now = 100
        self.box = Outbox(self.path, lambda: self.now)
        self.account = dict(id="owned", broker="FYERS")
        self.config = dict(modes=["PAPER", "LIVE"], fill_policy="EACH",telegram=dict(chat_id=-12345,token="synthetic-test-token"))
        self.entry = dict(tag="entry", mode="PAPER", strategy="Renko", lifecycle_id="life",
                          symbol="TEST", side="BUY", entry_side=1, is_entry=True,
                          filled=0, requested=10, average_price=20, quantity_multiplier=1, filled_at=101)

    def tearDown(self):
        self.box.db.close()
        self.temp.cleanup()

    def ingest(self, *rows, **kwargs):
        self.box.ingest(self.account, list(rows), self.config, **kwargs)

    def events(self):
        return [json.loads(r[0]) for r in self.box.db.execute("SELECT payload FROM events ORDER BY created,rowid")]

    def test_accepted_order_does_not_notify_and_partial_deltas_dedupe(self):
        self.ingest(self.entry)
        self.assertEqual(self.events(), [])
        self.entry["filled"] = 4
        self.ingest(self.entry)
        self.ingest(self.entry)
        self.entry.update(filled=10, average_price=23)
        self.ingest(self.entry)
        events = self.events()
        self.assertEqual([e["quantity"] for e in events], [4, 6])
        self.assertEqual([e["price"] for e in events], [20, 25])
        self.box.db.close()
        self.box = Outbox(self.path, lambda: self.now)
        self.ingest(self.entry)
        self.assertEqual(len(self.events()), 2)

    def test_baseline_and_historical_new_file_no_replay(self):
        self.entry.update(filled=4)
        self.ingest(self.entry, baseline=True)
        self.entry.update(filled=10)
        self.ingest(self.entry)
        self.assertEqual(self.events()[0]["quantity"], 6)
        self.entry.update(tag="old-other-file", filled_at=1)
        self.ingest(self.entry)
        self.assertEqual(len(self.events()), 1)

    def test_exit_reason_and_matched_pnl(self):
        self.entry.update(filled=10)
        self.ingest(self.entry, baseline=True)
        exit_row = dict(self.entry, tag="exit", filled=3, average_price=25,
                        side="SELL", is_entry=False, reason="TARGET", filled_at=102)
        self.ingest(self.entry, exit_row)
        event = self.events()[0]
        self.assertEqual((event["action"], event["quantity"], event["realized_pnl"]), ("EXIT", 3, 15))
        self.assertIn("TARGET", render(event))
        self.assertIn("PAPER simulation", render(event))
        exit_row.update(tag="unlinked", lifecycle_id=None)
        self.ingest(exit_row)
        self.assertIsNone(self.events()[-1]["realized_pnl"])

    def test_short_exit_pnl(self):
        self.entry.update(filled=10, side="SELL", entry_side=-1)
        self.ingest(self.entry, baseline=True)
        self.ingest(self.entry, dict(self.entry, tag="exit", is_entry=False, side="BUY", average_price=18))
        self.assertEqual(self.events()[0]["realized_pnl"], 20)

    def test_mode_and_missing_price_guards(self):
        self.config["modes"] = ["LIVE"]
        self.entry["filled"] = 10
        self.ingest(self.entry)
        self.assertEqual(self.events(), [])
        self.entry.update(mode="LIVE", average_price=None)
        self.ingest(self.entry)
        self.assertEqual(self.events(), [])
        self.entry["average_price"] = 20
        self.ingest(self.entry)
        self.assertEqual(self.events()[0]["mode"], "LIVE")

    def test_complete_policy(self):
        self.config["fill_policy"] = "COMPLETE"
        self.entry["filled"] = 4
        self.ingest(self.entry)
        self.assertEqual(self.events(), [])
        self.entry["filled"] = 10
        self.ingest(self.entry)
        self.assertEqual(self.events()[0]["quantity"], 10)

    def test_independent_channels_retry_persist_and_ambiguous_crash(self):
        self.entry["filled"] = 10
        self.ingest(self.entry)
        calls = []
        def sender(channel, config, event):
            calls.append(channel)
            return ("SENT", None) if channel == "email" else ("RETRY", "temporary")
        self.box.deliver(self.config, sender)
        self.assertEqual(self.box.status()["deliveries"], {"RETRY": 1, "SENT": 1})
        self.now += 31
        self.box.deliver(self.config, lambda *a: ("SENT", None))
        self.assertEqual(self.box.status()["deliveries"], {"SENT": 2})
        self.assertEqual(calls, ["email", "telegram"])
        with self.box.db:
            self.box.db.execute("UPDATE delivery SET state='SENDING' WHERE channel='telegram'")
        self.box.db.close()
        self.box = Outbox(self.path, lambda: self.now)
        self.assertEqual(self.box.status()["deliveries"], {"REVIEW": 1, "SENT": 1})

    def test_delta_paper_adapter(self):
        rows = list(ledger_rows(dict(trades=[dict(lifecycle_id="x", symbol="BTCUSD", contracts=5,
            entry_price=100, entry_time=101, side="LONG", contract_value="0.001",
            exit_fills=[dict(contracts=2, price=110, time=102, reason="STOP", pnl=.02)])]), "delta-india-paper.json"))
        self.assertEqual(len(rows), 2)
        self.ingest(*rows)
        self.assertEqual(self.events()[1]["realized_pnl"], .02)

    def test_source_scope_excludes_other_accounts_and_backups(self):
        root = Path(self.temp.name)
        good = root / ".private/dashboard-login/accounts/owned/source/.private/renko-instances/a/state.json"
        backup = root / ".private/dashboard-login/accounts/owned/source/.private/backup/renko-instances/b/state.json"
        other = root / ".private/dashboard-login/accounts/other/source/.private/renko-instances/c/state.json"
        for p in [good, backup, other]:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}")
        self.assertEqual([p for a, p in sources(root, [self.account])], [good])

    def test_paper_journal_ignores_live_submission_and_maps_paper(self):
        events = [
            dict(at="2026-10-20T10:00:00+05:30", lifecycle="LIVE_ENTRY_SUBMITTED",
                 ticket=dict(symbol="TEST", quantity=2, limit_price=20)),
            dict(at="2026-10-20T10:00:01+05:30", lifecycle="PAPER_ENTRY",
                 position=dict(symbol="TEST", quantity=2, entry_price=20, side=-1)),
            dict(at="2026-10-20T10:00:02+05:30", lifecycle="PAPER_EXIT", exit_price=18,
                 exit_reason="TARGET", realized_pnl_rupees=4,
                 position=dict(symbol="TEST", quantity=2, entry_price=20, side=-1))]
        rows = list(paper_journal_rows(events, "kama-runner-paper.jsonl"))
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["side"] for r in rows], ["SELL", "BUY"])
        self.ingest(*rows)
        self.assertEqual(self.events()[1]["realized_pnl"], 4)

    def test_status_reader_does_not_recover_active_send(self):
        self.entry["filled"] = 10
        self.ingest(self.entry)
        with self.box.db:
            self.box.db.execute("UPDATE delivery SET state='SENDING'")
        reader = Outbox(self.path, lambda: self.now, recover=False)
        self.assertEqual(reader.status()["deliveries"], {"SENDING": 2})
        reader.db.close()

    def test_transport_exception_does_not_expose_token(self):
        event = dict(id="test", mode="TEST", broker="NONE", action="TEST", symbol="NONE",
                     side="NONE", quantity=0, price=0, cumulative_quantity=0, cumulative_average=0)
        config = dict(telegram=dict(token="synthetic-secret", chat_id=123))
        with patch("urllib.request.urlopen", side_effect=TimeoutError("synthetic-secret")):
            state, error = send("telegram", config, event)
        self.assertEqual(state, "REVIEW")
        self.assertNotIn("synthetic-secret", error)


if __name__ == "__main__":
    unittest.main()

