"""Read-only fill observer and durable outbound notifications. Never imports brokers."""
import argparse
import fcntl
import hashlib
import json
import math
import os
import smtplib
import socket
import sqlite3
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".private/notifications"


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def identity(account, row):
    tag = row.get("tag") or row.get("paper_order_id") or row.get("order_id")
    if not tag or row.get("mode") not in ("PAPER", "LIVE"):
        return None
    return hashlib.sha256(json.dumps([account, row["mode"], str(tag)], separators=(",", ":")).encode()).hexdigest()


def ledger_rows(data, filename):
    rows = data.get("order_history", [])
    if isinstance(rows, list):
        yield from (r for r in rows if isinstance(r, dict))
    if filename == "delta-india-paper.json":
        for trade in data.get("trades", []):
            key = trade.get("lifecycle_id")
            if not key:
                continue
            base = dict(mode="PAPER", symbol=trade.get("symbol"), strategy=trade.get("strategy"),
                        lifecycle_id=key, quantity_multiplier=float(trade.get("contract_value") or 0),
                        quote_currency=trade.get("quote_currency"),
                        entry_side=1 if trade.get("side") == "LONG" else -1)
            yield dict(base, tag=key + ":entry", is_entry=True,
                       side="BUY" if base["entry_side"] == 1 else "SELL",
                       filled=trade.get("contracts"), requested=trade.get("contracts"),
                       average_price=trade.get("entry_price"), filled_at=trade.get("entry_time"))
            for i, fill in enumerate(trade.get("exit_fills", [])):
                yield dict(base, tag=key + ":exit:" + str(i), is_entry=False,
                           side="SELL" if base["entry_side"] == 1 else "BUY",
                           filled=fill.get("contracts"), requested=fill.get("contracts"),
                           average_price=fill.get("price"), filled_at=fill.get("time"),
                           reason=fill.get("reason"), recorded_realized_pnl=fill.get("pnl"))
    if filename == "delta-india-live.json":
        for key, order in data.get("orders", {}).items():
            request = order.get("request") or {}
            yield dict(tag=key, order_id=order.get("order_id"), mode="LIVE",
                       symbol=order.get("symbol"), is_entry=not request.get("reduce_only", False),
                       side=str(request.get("side", "")).upper(),
                       filled=order.get("filled_contracts"), requested=order.get("contracts", request.get("size")),
                       average_price=order.get("average_fill_price"), filled_at=order.get("updated_at"),
                       strategy=order.get("strategy"), reason=order.get("execution_reason"))


def sources(root, accounts):
    # Live owning directories, never backup copies or other users' accounts.
    for account in accounts:
        folder = root / ".private/dashboard-login/accounts" / account["id"]
        locations = [(folder / "source/.private", [
            "*-state.json", "renko-instances/*/state.json",
            "renko-delta-instances/*/renko-delta-state.json",
            "renko-engine/**/state.json", "delta-india-paper.json", "delta-india-live.json",
            "ema-band-runner-paper.jsonl", "kama-runner-paper.jsonl"]),
            (folder, ["dhan-strategies/**/state.json", "motilal-strategies/**/state.json", "renko-engine/state.json"])]
        seen = set()
        for base, patterns in locations:
            for pattern in patterns:
                for path in base.glob(pattern):
                    if path.is_symlink() or path in seen:
                        continue
                    seen.add(path)
                    yield account, path


def paper_journal_rows(records, filename):
    strategy = "KAMA" if filename.startswith("kama") else "EMA Band"
    for i, event in enumerate(records):
        lifecycle = event.get("lifecycle") or event.get("status")
        entry = lifecycle in ("PAPER_ENTRY", "PAPER_ENTRY_RECORDED")
        if not entry and lifecycle not in ("PAPER_EXIT", "PAPER_EXIT_RECORDED"):
            continue  # LIVE_*_SUBMITTED is deliberately never a confirmed fill.
        position = event.get("position") or {}
        ticket = event.get("ticket") or event.get("selected_instrument") or {}
        details = position or ticket
        side = position.get("side", ticket.get("side", 1))
        buy = side not in (-1, "SELL", "SHORT")
        try:
            stamp = datetime.fromisoformat(event["at"].replace("Z", "+00:00")).timestamp()
        except (KeyError, TypeError, ValueError):
            continue
        qty = details.get("quantity")
        price = (event.get("entry_price") or details.get("entry_price") or details.get("limit_price")) if entry else event.get("exit_price", event.get("exit_ltp"))
        if not details.get("symbol"):
            continue
        yield dict(tag=strategy + ":" + str(i) + ":" + event["at"], mode="PAPER",
                   symbol=details["symbol"], strategy=strategy, is_entry=entry,
                   side=("BUY" if buy else "SELL") if entry else ("SELL" if buy else "BUY"),
                   filled=qty, requested=qty, average_price=price, filled_at=stamp,
                   reason=event.get("exit_reason"), quote_currency="INR",
                   recorded_realized_pnl=event.get("realized_pnl_rupees"))


def pnl_for(row, rows, quantity, price):
    recorded = row.get("recorded_realized_pnl")
    if number(recorded):
        return recorded
    if row.get("is_entry") or not row.get("lifecycle_id"):
        return None
    entries = [r for r in rows if r.get("is_entry") is True and
               all(r.get(k) == row.get(k) for k in ("lifecycle_id", "mode", "symbol")) and
               number(r.get("filled")) and r["filled"] > 0]
    if not entries or any(not number(r.get("average_price")) for r in entries):
        return None
    mult = row.get("quantity_multiplier")
    if not number(mult) or mult <= 0 or any(r.get("quantity_multiplier") != mult for r in entries):
        return None
    total = sum(r["filled"] for r in entries)
    exits = sum(r.get("filled", 0) or 0 for r in rows if r.get("is_entry") is False and
                all(r.get(k) == row.get(k) for k in ("lifecycle_id", "mode", "symbol")))
    if exits > total:
        return None
    side = entries[0].get("entry_side")
    if side not in (1, -1) or any(r.get("entry_side") != side for r in entries):
        return None
    average = sum(r["filled"] * r["average_price"] for r in entries) / total
    return quantity * (price - average) * mult * side


def render(event):
    stamp = event.get("time")
    when = datetime.fromtimestamp(stamp, ZoneInfo("Asia/Kolkata")).isoformat() if number(stamp) else "Unavailable"
    if event.get("kind")=="POSITION_SUMMARY":
        lines=["Sector Pulse | PRIVATE POSITION UPDATE",event["broker"]+" | "+str(event.get("strategy") or "Account positions"),
               "Broker snapshot: "+when+" (Asia/Kolkata)"]
        positions=event.get("positions") or []
        if not positions:lines.append("No open broker positions in this fresh snapshot.")
        for row in positions[:20]:
            lines.append(str(row["symbol"])+" | net quantity "+str(row["netQty"])+" | P&L ₹"+str(row.get("pnl","Unavailable")))
        if len(positions)>20:lines.append(str(len(positions)-20)+" more positions remain in the dashboard.")
        if event.get("daily_pnl") is not None:lines.append("Current-day realized + unrealized P&L: ₹"+str(event["daily_pnl"]))
        lines.append("A position snapshot does not itself confirm an exit fill.")
        return "\n".join(lines)
    lines = ["Sector Pulse | " + event["mode"] + " | " + event["action"],
             event["broker"] + " | " + str(event.get("strategy") or "Strategy unavailable"),
             str(event["symbol"]) + " | " + event["side"],
             "Executed quantity (this update): " + str(event["quantity"]),
             "Fill price (this update): " + str(event["price"]),
             "Order cumulative quantity / average: " + str(event["cumulative_quantity"]) + " / " + str(event["cumulative_average"]),
             "Recorded fill confirmation: " + when + " (Asia/Kolkata)",
             "Time basis: persisted local confirmation; exact exchange execution time unavailable."]
    if event["mode"] == "PAPER":
        lines.append("PAPER simulation; no broker execution.")
    if event["action"] == "EXIT":
        lines.extend(["Exit reason: " + str(event.get("reason") or "Unavailable"),
                      "Realized P&L (this update, before fees): " +
                      (str(event["realized_pnl"]) if event.get("realized_pnl") is not None else "Unavailable") +
                      " | currency: " + str(event.get("currency") or "broker-native; unspecified")])
    lines.append("Event ID: " + event["id"])
    return "\n".join(lines)


class Outbox:
    def __init__(self, path, clock=time.time, recover=True):
        path = Path(path)
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.db = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.clock = clock
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value REAL);
            CREATE TABLE IF NOT EXISTS fills(id TEXT PRIMARY KEY,quantity REAL,notional REAL);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,payload TEXT NOT NULL,created REAL);
            CREATE TABLE IF NOT EXISTS delivery(event TEXT,channel TEXT,state TEXT,attempts INTEGER DEFAULT 0,
              due REAL DEFAULT 0,error TEXT,updated REAL,PRIMARY KEY(event,channel));
            CREATE TABLE IF NOT EXISTS scans(source TEXT PRIMARY KEY,scanned REAL,error TEXT);
            CREATE TABLE IF NOT EXISTS telegram_parts(event TEXT,part INTEGER,body TEXT,state TEXT,error TEXT,updated REAL,destination TEXT,PRIMARY KEY(event,part));
            CREATE TABLE IF NOT EXISTS email_targets(event TEXT,channel TEXT,recipient TEXT,subscriber TEXT,PRIMARY KEY(event,channel));
        """)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('cutoff',?)", (clock(),))
        # A crash after send began has an unknown outcome. Never blindly duplicate it.
        if recover:
            self.db.execute("UPDATE delivery SET state='REVIEW',error='Interrupted send; remote outcome unknown' WHERE state='SENDING'")
            self.db.execute("UPDATE telegram_parts SET state='REVIEW',error='Interrupted part; remote outcome unknown' WHERE state='SENDING'")
        self.db.commit()

    def ingest(self, account, rows, config, baseline=False):
        with self.db:
            for row in rows:
                key = identity(account["id"], row)
                if not key or row.get("mode") not in config["modes"]:
                    continue
                qty, avg = row.get("filled"), row.get("average_price")
                if not number(qty) or qty <= 0 or not number(avg) or avg <= 0:
                    continue
                if row.get("is_entry") not in (True, False) or row.get("side") not in ("BUY", "SELL"):
                    continue
                old = self.db.execute("SELECT quantity,notional FROM fills WHERE id=?", (key,)).fetchone()
                previous, notional = old or (0, 0)
                if qty <= previous:
                    continue
                stamp = row.get("filled_at") or row.get("updated_at")
                cutoff = self.db.execute("SELECT value FROM meta WHERE key='cutoff'").fetchone()[0]
                historical = number(stamp) and stamp < cutoff
                if config["fill_policy"] == "COMPLETE" and qty < (row.get("requested") or qty) and not baseline and not historical:
                    continue
                delta = qty - previous
                price = (qty * avg - notional) / delta
                if not number(price) or price <= 0:
                    continue
                # Unknown timestamps on a newly discovered ledger cannot prove a new fill.
                suppress = baseline or historical or (not old and not number(stamp))
                self.db.execute("INSERT OR REPLACE INTO fills VALUES(?,?,?)", (key, qty, qty * avg))
                if suppress:
                    continue
                event_id = hashlib.sha256((key + ":" + str(float(qty))).encode()).hexdigest()[:24]
                event = dict(id=event_id, owner_username=account.get("owner_username",config.get("owner_username")), account_id=account["id"], mode=row["mode"], broker=account["broker"],
                             strategy=row.get("strategy"), action="ENTRY" if row["is_entry"] else "EXIT",
                             symbol=row.get("symbol"), side=row["side"], quantity=delta, price=price,
                             cumulative_quantity=qty, cumulative_average=avg, time=stamp,
                             reason=row.get("reason"), currency=row.get("quote_currency"),
                             realized_pnl=pnl_for(row, rows, delta, price))
                self.db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?)", (event_id, json.dumps(event), self.clock()))
                for channel in ("email", "telegram"):
                    self.db.execute("INSERT OR IGNORE INTO delivery(event,channel,state,updated) VALUES(?,?,'PENDING',?)",
                                    (event_id, channel, self.clock()))

    def ingest_summaries(self,account,summaries,config,baseline=False):
        if baseline or "LIVE" not in config["modes"]:return
        cutoff=self.db.execute("SELECT value FROM meta WHERE key='cutoff'").fetchone()[0]
        for row in summaries:
            stamp=row.get("time")
            if row.get("verified") is not True or not number(stamp) or stamp<cutoff or not 0<=self.clock()-stamp<=900:
                continue
            positions=row.get("positions")
            if not isinstance(positions,list) or any(not isinstance(p,dict) or not p.get("symbol") or not number(p.get("netQty")) for p in positions):
                continue
            key=hashlib.sha256(("private-positions:"+account["id"]+":"+str(row.get("slot"))).encode()).hexdigest()[:24]
            event=dict(id=key,kind="POSITION_SUMMARY",mode="LIVE",action="POSITION UPDATE",symbol="Account positions",
                broker=account["broker"],account_id=account["id"],owner_username=account.get("owner_username",config.get("owner_username")),
                strategy="Broker-confirmed account snapshot",time=stamp,positions=positions,daily_pnl=row.get("daily_pnl"))
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?)",(key,json.dumps(event),stamp))
                self.db.execute("INSERT OR IGNORE INTO delivery(event,channel,state,updated) VALUES(?,?,'PENDING',?)",(key,"telegram",self.clock()))

    def scan(self, root, config, baseline=False):
        count = 0
        accounts=config["accounts"]
        if config.get("email_recipient_scope")=="OWN_ACCOUNT_ONLY":
            from .notification_recipients import notification_accounts
            accounts=notification_accounts(config,root)
        for account, path in sources(root, accounts):
            error = None
            try:
                if path.suffix == ".jsonl":
                    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                    rows = list(paper_journal_rows(records, path.name))
                else:
                    data = json.loads(path.read_text())
                    rows = list(ledger_rows(data, path.name))
                    if path.name=="handoff-observer-state.json":
                        self.ingest_summaries(account,data.get("position_summaries",[]),config,baseline)
                self.ingest(account, rows, config, baseline)
                count += 1
            except Exception:
                error = "Unreadable or unsupported ledger; retry next scan"
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO scans VALUES(?,?,?)", (str(path), self.clock(), error))
        return count

    def test_event(self):
        event = dict(id="setup-test-" + str(int(self.clock())), mode="TEST", broker="NOTIFICATION SETUP",
                     action="DELIVERY TEST", strategy="No trade or order", symbol="TEST ONLY", side="NONE",
                     quantity=0, price=0, cumulative_quantity=0, cumulative_average=0, time=self.clock())
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?)", (event["id"], json.dumps(event), self.clock()))
            for channel in ("email", "telegram"):
                self.db.execute("INSERT OR IGNORE INTO delivery(event,channel,state,updated) VALUES(?,?,'PENDING',?)",
                                (event["id"], channel, self.clock()))
        return event["id"]

    def route_emails(self,config,only_event=None):
        if config.get("email_recipient_mode")!="USER_MASTER_ENABLED":
            return
        from .notification_recipients import subscribers
        sql="SELECT d.event,e.created,e.payload FROM delivery d JOIN events e ON d.event=e.id WHERE d.channel='email' AND d.state IN ('PENDING','RETRY','PAUSED')"
        params=[]
        if only_event:
            sql+=" AND d.event=?";params.append(only_event)
        for event_id,created,payload in self.db.execute(sql,params).fetchall():
            try:
                event=json.loads(payload)
                publisher_config={**config,"owner_username":event.get("owner_username") or config.get("owner_username")}
                targets=subscribers(publisher_config)
                occurred=event.get("time",created) if not event.get("kind") else created
                occurred=occurred if number(occurred) else created
                targets=[t for t in targets if t["enabled_at"]<=occurred]
            except Exception:
                with self.db:self.db.execute("UPDATE delivery SET state='RETRY',error='Subscriber settings unavailable',due=? WHERE event=? AND channel='email'",(self.clock()+30,event_id))
                continue
            with self.db:
                for target in targets:
                    channel="email:"+target["id"]
                    self.db.execute("INSERT OR IGNORE INTO email_targets VALUES(?,?,?,?)",(event_id,channel,target["email"],target["id"]))
                    self.db.execute("INSERT OR IGNORE INTO delivery(event,channel,state,updated) VALUES(?,?,'PENDING',?)",(event_id,channel,self.clock()))
                self.db.execute("UPDATE delivery SET state=?,error=?,updated=? WHERE event=? AND channel='email'",
                    ("ROUTED" if targets else "SKIPPED",None if targets else "No opted-in subscriber for this new event",self.clock(),event_id))

    def deliver_telegram(self,config,event,sender):
        # Image cards are already a single retained transport payload; the
        # private trade-text formatter must never rewrite or split them.
        if event.get("kind") in {"SECTOR_CARD","HANDOFF_CARD","COMBINED_CARD"}:
            return sender("telegram",config,event)
        from .telegram_trade_format import parts
        destination=hashlib.sha256(str(config["telegram"]["chat_id"]).encode()).hexdigest()
        saved=self.db.execute("SELECT part,body,state,destination FROM telegram_parts WHERE event=? ORDER BY part",(event["id"],)).fetchall()
        if not saved:
            with self.db:
                for index,body in enumerate(parts(event)):
                    self.db.execute("INSERT INTO telegram_parts VALUES(?,?,?,'PENDING',NULL,?,?)",
                        (event["id"],index,body,self.clock(),destination))
            saved=self.db.execute("SELECT part,body,state,destination FROM telegram_parts WHERE event=? ORDER BY part",(event["id"],)).fetchall()
        if any(row[3]!=destination for row in saved):
            return "REVIEW","Telegram destination changed during delivery; review prior parts."
        for index,body,state,_ in saved:
            if state=="SENT":continue
            if state in {"SENDING","REVIEW"}:return "REVIEW","Telegram part outcome requires reconciliation."
            with self.db:self.db.execute("UPDATE telegram_parts SET state='SENDING',updated=? WHERE event=? AND part=?",(self.clock(),event["id"],index))
            try:outcome,error=sender("telegram",config,{**event,"_telegram_html":body})
            except Exception:outcome,error="REVIEW","Unexpected Telegram part failure; outcome unknown."
            if outcome not in {"SENT","RETRY","REVIEW"}:outcome,error="REVIEW","Unsupported Telegram outcome."
            with self.db:self.db.execute("UPDATE telegram_parts SET state=?,error=?,updated=? WHERE event=? AND part=?",
                (outcome,error,self.clock(),event["id"],index))
            if outcome!="SENT":return outcome,error
        return "SENT",None

    def deliver(self, config, sender=None, only_event=None):
        sender = sender or send
        self.route_emails(config,only_event)
        query = """SELECT d.event,d.channel,d.attempts,e.payload,e.created FROM delivery d JOIN events e ON e.id=d.event
                   WHERE d.state IN ('PENDING','RETRY','PAUSED') AND d.due<=?"""
        args = [self.clock()]
        if only_event:
            query += " AND d.event=?"
            args.append(only_event)
        for event_id, channel, attempts, payload, created in self.db.execute(query, args).fetchall():
            event = json.loads(payload)
            delivery_config=config
            base_channel=channel.split(":",1)[0]
            if channel.startswith("email:"):
                from .notification_recipients import subscribers
                target=self.db.execute("SELECT recipient,subscriber FROM email_targets WHERE event=? AND channel=?",(event_id,channel)).fetchone()
                try:
                    publisher_config={**config,"owner_username":event.get("owner_username") or config.get("owner_username")}
                    eligible={t["id"]:t for t in subscribers(publisher_config)}
                    current=eligible.get(target[1]) if target else None
                    occurred=event.get("time",created) if not event.get("kind") else created
                    occurred=occurred if number(occurred) else created
                    valid=current and current["email"]==target[0] and current["enabled_at"]<=occurred
                except Exception:
                    continue  # Retry later without exposing or guessing recipients.
                if not valid:
                    with self.db:self.db.execute("UPDATE delivery SET state='SKIPPED',error='Subscriber disabled or destination changed' WHERE event=? AND channel=?",(event_id,channel))
                    continue
                delivery_config={**config,"email":{**config["email"],"recipient":target[0]}}
            owner=event.get("owner_username") or config.get("owner_username")
            primary=config.get("primary_owner_username",config.get("owner_username"))
            if base_channel=="telegram" and owner!=primary:
                with self.db:self.db.execute("UPDATE delivery SET state='SKIPPED',error='No private Telegram destination configured for this owner' WHERE event=? AND channel=?",(event_id,channel))
                continue
            if base_channel=="telegram":
                from .notification_destinations import telegram_destination
                delivery_config,blocked=telegram_destination(config,event,created)
                if blocked:
                    with self.db:self.db.execute("UPDATE delivery SET state='SKIPPED',error=? WHERE event=? AND channel=?",(blocked,event_id,channel))
                    continue
            from .notification_controls import gate
            preference_path=None if owner==primary else PRIVATE/"user-preferences"/(hashlib.sha256(str(owner).encode()).hexdigest()+".json")
            held, reason = gate(base_channel, event, created,path=preference_path)
            if held:
                with self.db:
                    self.db.execute("UPDATE delivery SET state=?,error=?,updated=? WHERE event=? AND channel=?",
                                    (held, reason, self.clock(), event_id, channel))
                continue
            with self.db:
                self.db.execute("UPDATE delivery SET state='SENDING',updated=? WHERE event=? AND channel=?",
                                (self.clock(), event_id, channel))
            try:
                state, error = (self.deliver_telegram(delivery_config,event,sender) if base_channel=="telegram"
                                else sender(base_channel, delivery_config, json.loads(payload)))
            except Exception:
                state, error = "REVIEW", "Unexpected send failure; remote outcome unknown"
            if state not in ("SENT", "RETRY", "REVIEW"):
                state, error = "REVIEW", "Unsupported transport outcome"
            delay = min(3600, 30 * 2 ** min(attempts, 7))
            with self.db:
                self.db.execute("UPDATE delivery SET state=?,attempts=?,due=?,error=?,updated=? WHERE event=? AND channel=?",
                                (state, attempts + 1, self.clock() + delay, error, self.clock(), event_id, channel))

    def status(self):
        return dict(deliveries=dict(self.db.execute("SELECT state,count(*) FROM delivery GROUP BY state").fetchall()),
                    ledger_count=self.db.execute("SELECT count(*) FROM scans").fetchone()[0],
                    ledger_errors=self.db.execute("SELECT count(*) FROM scans WHERE error IS NOT NULL").fetchone()[0],
                    heartbeat=self.db.execute("SELECT value FROM meta WHERE key='heartbeat'").fetchone(),
                    events=self.db.execute("SELECT count(*) FROM events").fetchone()[0])


def send(channel, config, event):
    text = render(event)
    if channel == "telegram":
        settings = config["telegram"]
        from .telegram_trade_format import parts,units
        formatted=event.get("_telegram_html")
        if formatted is None:
            fragments=parts(event)
            if len(fragments)!=1:return "REVIEW","Multipart Telegram notification requires durable outbox delivery."
            formatted=fragments[0]
        if units(formatted)>4096:return "REVIEW","Telegram notification exceeds its validated length."
        req = urllib.request.Request("https://api.telegram.org/bot" + settings["token"] + "/sendMessage",
              data=json.dumps(dict(chat_id=settings["chat_id"], text=formatted,parse_mode="HTML")).encode(),
              headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as response:
                result = json.load(response)
            return ("SENT", None) if result.get("ok") else ("RETRY", "Telegram rejected message")
        except urllib.error.HTTPError as exc:
            return "RETRY", "Telegram HTTP " + str(exc.code)
        except Exception:
            return "REVIEW", "Telegram outcome unknown; manual reconciliation required"
    settings = config["email"]
    message = EmailMessage()
    message["From"], message["To"] = settings["sender"], settings["recipient"]
    message["Subject"] = "[Sector Pulse][" + event["mode"] + "] " + event["action"] + " " + str(event["symbol"])
    message["Message-ID"] = "<" + event["id"] + "@sector-pulse.local>"
    message.set_content(text)
    sending = False
    try:
        with smtplib.SMTP_SSL(settings["smtp_host"], settings["smtp_port"], timeout=20,
                              context=ssl.create_default_context()) as smtp:
            smtp.login(settings["sender"], settings["app_password"])
            sending = True
            refused = smtp.send_message(message)
            if refused:
                return "RETRY", "Email recipient refused"
        return "SENT", None
    except (smtplib.SMTPDataError, smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPAuthenticationError):
        return "RETRY", "SMTP rejected authorization or message"
    except Exception:
        return ("REVIEW", "SMTP outcome unknown; manual reconciliation required") if sending else ("RETRY", "SMTP connection unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["baseline", "status", "test", "once", "run"])
    args = parser.parse_args()
    os.umask(0o077)
    config_path = PRIVATE / "config.json"
    if config_path.stat().st_mode & 0o077:
        raise SystemExit("Credential file must have owner-only permissions.")
    config = json.loads(config_path.read_text())
    if config["owner_username"] != "pinaki87":
        raise SystemExit("Unsupported owner")
    lock = (PRIVATE / "worker.lock").open("a")
    try:
        if args.action != "status":
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Notification worker already running; no second sender started.")
    outbox = Outbox(PRIVATE / "outbox.sqlite3", recover=args.action != "status")
    if args.action == "status":
        print(json.dumps(dict(enabled=config["enabled"], **outbox.status())))
    elif args.action == "baseline":
        if outbox.db.execute("SELECT 1 FROM meta WHERE key='baselined'").fetchone():
            raise SystemExit("Baseline already prepared; refusing to suppress newer fills.")
        count = outbox.scan(ROOT, config, baseline=True)
        with outbox.db:
            outbox.db.execute("INSERT INTO meta VALUES('baselined',?)", (time.time(),))
        print(json.dumps(dict(baselined_ledgers=count, **outbox.status())))
    elif args.action == "test":
        event_id = outbox.test_event()
        outbox.deliver(config, only_event=event_id)
        print(json.dumps(dict(test_event_id=event_id, outcomes=dict(outbox.db.execute(
            "SELECT channel,state FROM delivery WHERE event=?", (event_id,)).fetchall()))))
    else:
        if not outbox.db.execute("SELECT 1 FROM meta WHERE key='baselined'").fetchone():
            raise SystemExit("Prepare the historical baseline before activation.")
        if not config.get("enabled"):
            raise SystemExit("Continuous notifications disabled; activation is pending.")
        while True:
            outbox.scan(ROOT, config)
            outbox.deliver(config)
            with outbox.db:
                outbox.db.execute("INSERT OR REPLACE INTO meta VALUES('heartbeat',?)", (time.time(),))
            if args.action == "once":
                break
            time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        raise SystemExit("Notification operation failed; secrets suppressed. Check protected configuration and outbox status.")

