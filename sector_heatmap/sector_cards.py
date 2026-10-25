"""Scheduled sector cards from the owner's persisted dashboard analysis; read-only source."""
import argparse
import fcntl
import hashlib
import html
import json
import math
import os
import secrets
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from .market_calendar import IST, market_session, REGULAR_OPEN
from .sectors import SECTOR_DEFINITIONS
from .trade_notifications import Outbox, PRIVATE, ROOT, number

sys.path.insert(0, str(PRIVATE / "render-libs"))


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("Source timestamp unavailable")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Source timestamp requires timezone")
    return result.astimezone(IST)


def schedule_slot(now):
    session = market_session(now)
    if session["status"] != "OPEN":
        return None
    start = now.replace(hour=REGULAR_OPEN.hour, minute=REGULAR_OPEN.minute, second=0, microsecond=0)
    index = int((now - start).total_seconds()) // 1800
    return (start + timedelta(minutes=30 * index)).isoformat()


def history_path(config, root=ROOT):
    accounts = [a for a in config["accounts"] if a["broker"] == "FYERS"]
    if len(accounts) != 1:
        raise ValueError("Exactly one configured owner FYERS workspace is required")
    return root / ".private/dashboard-login/accounts" / accounts[0]["id"] / "home/.fyers/sector-heatmap/analysis-history.json"


def snapshot_from_history(history, now, mode="intraday", initial=False):
    stored = history.get("modes", {}).get(mode, {})
    rows = []
    for definition in SECTOR_DEFINITIONS:
        series = stored.get(definition.sector_id, [])
        latest = series[-1] if series else {}
        score = latest.get("overall_score")
        if score is not None and (not number(score) or not 0 <= score <= 100):
            raise ValueError("Invalid sector score")
        rows.append(dict(sector_id=definition.sector_id, name=definition.name,
                         score=score, rs=latest.get("relative_strength_score"),
                         rotation=latest.get("rotation_state") or "UNAVAILABLE",
                         asof=latest.get("last_updated"), observed=latest.get("timestamp")))
    known = [r for r in rows if r["score"] is not None]
    if not known:
        raise ValueError("Sector analysis unavailable; nothing sent")
    times = [parse_time(r["asof"]) for r in known]
    observations = [parse_time(r["observed"]) for r in known]
    session = market_session(now)
    if session["status"] == "OPEN":
        if any(t.date() != now.date() or not 0 <= (now-t).total_seconds() <= 2700 for t in times):
            raise ValueError("Dashboard market bars stale; scheduled image withheld")
        if any(not 0 <= (now-t).total_seconds() <= 2400 for t in observations):
            raise ValueError("Dashboard analysis refresh stale; scheduled image withheld")
        freshness = "COMPLETED-CANDLE SNAPSHOT"
    else:
        if not initial:
            raise ValueError("Market closed; scheduled image withheld")
        if any(t.date().isoformat() != session["last_completed_session"] for t in times):
            raise ValueError("Saved market data is older than the last completed session")
        freshness = "LAST COMPLETED SESSION"
    known.sort(key=lambda r: (-r["score"], r["name"]))
    missing = [r for r in rows if r["score"] is None]
    return dict(mode=mode, source="FYERS dashboard analysis", benchmark="NIFTY 50",
                freshness=freshness, market_reason=session["reason"], asof=min(times).isoformat(),
                newest_asof=max(times).isoformat(), observed=min(observations).isoformat(),
                generated=now.isoformat(), rows=known+missing,
                score_basis="Dashboard composite score (0-100); not percentage returns.")


def render_card(snapshot, target):
    from PIL import Image, ImageDraw, ImageFont
    rows = snapshot["rows"]
    grid_rows = (len(rows)+2)//3
    height = 1085 + grid_rows*145
    image = Image.new("RGB", (1200, height), "#EDF2F8")
    draw = ImageDraw.Draw(image)
    folder = "/usr/share/fonts/truetype/dejavu/"
    def font(size, bold=False):
        return ImageFont.truetype(folder+("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),size)
    def text(x,y,value,size=27,color="#203B55",bold=False):
        draw.text((x,y),str(value),font=font(size,bold),fill=color)
    def right(x,y,value,size=27,color="#203B55",bold=False):
        value=str(value); f=font(size,bold)
        draw.text((x-draw.textlength(value,font=f),y),value,font=f,fill=color)
    def box(rect,fill,r=20):
        draw.rounded_rectangle(rect,radius=r,fill=fill)
    def label(value,width,size):
        f=font(size,True)
        if draw.textlength(value,font=f)<=width:
            return [value]
        words=value.split(); lines=[""]
        for word in words:
            if draw.textlength((lines[-1]+" "+word).strip(),font=f)>width:
                lines.append(word)
            else:
                lines[-1]=(lines[-1]+" "+word).strip()
        return lines[:2]
    box((36,36,1164,height-36),"#FFFFFF",30)
    box((36,36,1164,268),"#203B55",30)
    draw.rectangle((36,220,1164,268),fill="#203B55")
    text(77,70,"SECTOR PULSE",25,"#FFFFFF",True)
    right(1120,70,snapshot["mode"].upper(),23,"#C9D9E9",True)
    text(77,123,"Sector rotation",62,"#FFFFFF",True)
    text(79,209,"Strength, leadership and rotation at a glance.",26,"#C9D9E9")
    text(77,301,snapshot["freshness"],24,"#8A5B1F",True)
    asof=parse_time(snapshot["asof"]).strftime("%d %b %Y  /  %I:%M %p IST")
    text(77,347,"Market bars: "+asof,25)
    text(77,388,"Source: "+snapshot["source"]+"  |  Completed candles",23,"#596E82")
    draw.line((77,437,1120,437),fill="#DFE7EF",width=2)
    known=[r for r in rows if r["score"] is not None]
    leader=known[0]
    text(77,464,str(sum(r["rotation"]=="LEADING" for r in known))+" / "+str(len(rows)),42,"#167A71",True)
    text(77,520,"classified LEADING",22,"#596E82")
    for i,line in enumerate(label(leader["name"],350,33)):
        text(430,464+i*38,line,33,"#203B55",True)
    text(430,548,"highest overall score",22,"#596E82")
    text(840,464,format(leader["score"],".1f"),42,"#203B55",True)
    text(840,520,"leader score / 100",22,"#596E82")
    text(77,604,"Sector strength",32,"#203B55",True)
    right(1120,614,"Composite score / 100",22,"#596E82")
    for i,row in enumerate(rows):
        x=77+(i%3)*356; y=665+(i//3)*145
        score=row["score"]
        fill,ink=("#EEF1F5","#596E82") if score is None else ("#167A71","#FFFFFF") if score>=70 else ("#D5EDE6","#203B55") if score>=55 else ("#F5EAD4","#624D2A") if score>=35 else ("#B85860","#FFFFFF")
        box((x,y,x+332,y+128),fill,15)
        for j,line in enumerate(label(row["name"].upper(),292,20)):
            text(x+18,y+10+j*23,line,20,ink,True)
        text(x+18,y+57,"N/A" if score is None else format(score,".1f"),34,ink,True)
        right(x+312,y+104,row["rotation"].replace("_"," "),15,ink,True)
    y=695+grid_rows*145
    text(77,y,"Relative strength",31,"#203B55",True)
    right(1120,y+8,"vs NIFTY 50  |  Score / 100",21,"#596E82")
    rs=[r for r in rows if number(r["rs"])]
    rs.sort(key=lambda r:-r["rs"])
    box((77,y+60,583,y+229),"#F1F7F6",18)
    box((607,y+60,1120,y+229),"#FCF3F2",18)
    text(99,y+73,"HIGHEST RS SCORES",19,"#167A71",True)
    text(630,y+73,"LOWEST RS SCORES",19,"#A24751",True)
    for j,row in enumerate(rs[:3]):
        text(99,y+109+j*34,row["name"],21)
        right(558,y+109+j*34,format(row["rs"],".1f"),22,"#167A71",True)
    for j,row in enumerate(reversed(rs[-3:])):
        text(630,y+109+j*34,row["name"],21)
        right(1093,y+109+j*34,format(row["rs"],".1f"),22,"#A24751",True)
    text(77,y+258,"Scores are model measures, not price returns or trade signals.",21,"#596E82")
    text(77,y+292,"Generated "+parse_time(snapshot["generated"]).strftime("%d %b %Y, %I:%M %p IST"),21,"#596E82")
    target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    image.save(target,optimize=True)
    os.chmod(target,0o600)


def media_bytes(event):
    path=Path(event["image"])
    path.resolve().relative_to((PRIVATE/("combined-reports" if event.get("kind")=="COMBINED_CARD" else "sector-cards")).resolve())
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=event["image_sha256"]:
        raise ValueError("Retained image hash mismatch")
    return data


def caption(event):
    if event.get("kind")=="COMBINED_CARD":return event["public_caption"]
    s=event["snapshot"]
    handoff=event.get("kind")=="HANDOFF_CARD"
    title="Analysis Handoff" if handoff else "Sector rotation"
    basis="Decision support only; no order authority." if handoff else "Composite scores, not percentage returns."
    findings=""
    if handoff:
        rows=[r for r in s.get("rows",[]) if str(r.get("direction","")).upper() in {"BULLISH","BEARISH"}]
        lines=[]
        for row in rows[:5]:
            direction=str(row["direction"]).upper();icon="🔴" if direction=="BEARISH" else "🟢"
            name=" ".join(str(row.get("name") or row.get("symbol") or "Instrument").split())[:45]
            try:score=float(row.get("conviction_out_of_ten"));grade=f" · {score:.2f}/10" if math.isfinite(score) and 0<=score<=10 else ""
            except (TypeError,ValueError):grade=""
            lines.append(icon+" "+name+" · "+direction+grade)
        public_status=s.get("scheduled_status") or {}
        findings=("\n"+"\n".join(lines)) if lines else "\n"+(public_status.get("message") or "No eligible recommendations in this report.")
    return ("Sector Pulse | "+title+" | "+s["mode"].upper()+"\n"+
            s["freshness"]+("\nCheck time: " if s.get("scheduled_status") else "\nData as of: ")+parse_time(s["asof"]).strftime("%d %b %Y, %I:%M %p IST")+"\n"+
            s["source"]+" | "+basis+findings+"\n"+
            "Snapshot ID: "+event["id"]+"\nControls: /notifications in this bot.")



def email_message(config,event,data):
    message=EmailMessage()
    settings=config["email"]
    message["From"],message["To"]=settings["sender"],settings["recipient"]
    title="Analysis Handoff" if event.get("kind")=="HANDOFF_CARD" else "Sector rotation"
    filename="analysis-handoff.png" if event.get("kind")=="HANDOFF_CARD" else "sector-rotation.png"
    message["Subject"]="[Sector Pulse] "+title+" | "+event["snapshot"]["freshness"]
    message["Message-ID"]="<"+event["id"]+"@sector-pulse.local>"
    message.set_content(caption(event)+"\nManage delivery: https://t.me/SectorPulsePinakiAlertsBot (send /notifications).")
    message.add_alternative("<html><body><p>"+html.escape(caption(event)).replace("\n","<br>")+
                            '</p><img src="cid:sector-card" alt="Sector rotation snapshot" style="width:100%;max-width:720px"><p>Pause or resume each channel in <a href="https://t.me/SectorPulsePinakiAlertsBot">your Telegram bot</a>: send /notifications.</p></body></html>',subtype="html")
    message.get_payload()[-1].add_related(data,maintype="image",subtype="png",cid="<sector-card>",disposition="inline",filename=filename)
    message.add_attachment(data,maintype="image",subtype="png",filename=filename)
    return message


def send_card(channel,config,event,audit=None):
    try:
        data=media_bytes(event)
    except Exception:
        return "REVIEW","Retained image unavailable or changed"
    if channel=="telegram":
        settings=config["telegram"]
        boundary="SectorCard"+secrets.token_hex(16)
        parts=[]
        for key,value in (("chat_id",str(settings["chat_id"])),("caption",caption(event))):
            parts.append(("--"+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+value+"\r\n").encode())
        parts.append(("--"+boundary+'\r\nContent-Disposition: form-data; name="photo"; filename="sector-rotation.png"\r\nContent-Type: image/png\r\n\r\n').encode()+data+b"\r\n")
        parts.append(("--"+boundary+"--\r\n").encode())
        request=urllib.request.Request("https://api.telegram.org/bot"+settings["token"]+"/sendPhoto",
                 data=b"".join(parts),headers={"Content-Type":"multipart/form-data; boundary="+boundary},method="POST")
        try:
            with urllib.request.urlopen(request,timeout=30,context=ssl.create_default_context()) as response:
                result=json.load(response)
            if result.get("ok") and audit is not None:audit(result)
            return ("SENT",None) if result.get("ok") else ("RETRY","Telegram rejected photo")
        except urllib.error.HTTPError as error:
            return "RETRY","Telegram HTTP "+str(error.code)
        except Exception:
            return "REVIEW","Telegram image outcome unknown"
    sending=False
    try:
        message=email_message(config,event,data)
        settings=config["email"]
        with smtplib.SMTP_SSL(settings["smtp_host"],settings["smtp_port"],timeout=30,context=ssl.create_default_context()) as smtp:
            smtp.login(settings["sender"],settings["app_password"])
            sending=True
            refused=smtp.send_message(message)
            if refused:
                return "RETRY","Gmail recipient refused"
        return "SENT",None
    except (smtplib.SMTPDataError,smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPAuthenticationError):
        return "RETRY","SMTP rejected image message or authorization"
    except Exception:
        return ("REVIEW","SMTP image outcome unknown") if sending else ("RETRY","SMTP image connection unavailable")


class SectorOutbox(Outbox):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,state TEXT,reason TEXT,event_id TEXT,updated REAL)")
        self.db.commit()

    def settle(self):
        with self.db:
            self.db.execute("UPDATE delivery SET state='EXPIRED',error='Snapshot delivery window elapsed' WHERE state IN ('PENDING','RETRY','PAUSED') AND event IN (SELECT id FROM events WHERE created<?)",(self.clock()-1800,))
            for key,event_id in self.db.execute("SELECT id,event_id FROM jobs WHERE event_id IS NOT NULL").fetchall():
                states={r[0] for r in self.db.execute("SELECT state FROM delivery WHERE event=? AND state<>'ROUTED'",(event_id,))}
                state="DELIVERED" if states=={"SENT"} else "REVIEW" if "REVIEW" in states else "EXPIRED" if "EXPIRED" in states else "PAUSED" if "PAUSED" in states else "SKIPPED" if "SKIPPED" in states else "RETRY" if "RETRY" in states else "QUEUED"
                self.db.execute("UPDATE jobs SET state=? WHERE id=?",(state,key))

    def enqueue(self,config,now,initial=False):
        slot="initial-"+now.date().isoformat() if initial else schedule_slot(now)
        if slot is None:
            return None
        key="sector-"+hashlib.sha256((config["owner_username"]+":intraday:"+slot).encode()).hexdigest()[:24]
        previous=self.db.execute("SELECT event_id FROM jobs WHERE id=?",(key,)).fetchone()
        if previous and previous[0]:
            return previous[0]
        latest = self.db.execute("SELECT max(created) FROM events WHERE json_extract(payload,'$.owner_username')=?",(config["owner_username"],)).fetchone()[0]
        if not initial and latest is not None and now.timestamp() - latest < 1800:
            return None  # A delayed first snapshot must not cause a second card less than 30 minutes later.
        try:
            source=history_path(config)
            snapshot=snapshot_from_history(json.loads(source.read_text()),now,initial=initial)
            target=PRIVATE/"sector-cards"/(key+".png")
            render_card(snapshot,target)
            evidence=target.with_suffix(".json")
            evidence.write_text(json.dumps(snapshot,indent=2))
            os.chmod(evidence,0o600)
            event=dict(id=key,kind="SECTOR_CARD",owner_username=config["owner_username"],image=str(target),
                       image_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),snapshot=snapshot)
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?)",(key,json.dumps(event),self.clock()))
                for channel in ("email","telegram"):
                    self.db.execute("INSERT OR IGNORE INTO delivery(event,channel,state,updated) VALUES(?,?,'PENDING',?)",(key,channel,self.clock()))
                self.db.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?)",(key,"QUEUED",None,key,self.clock()))
            return key
        except Exception as error:
            safe=str(error) if type(error) is ValueError else "Sector source/render unavailable; retry without sending"
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?)",(key,"WITHHELD",safe,None,self.clock()))
            return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["preview","initial","run","status"])
    args=parser.parse_args()
    os.umask(0o077)
    config=json.loads((PRIVATE/"config.json").read_text())
    policy=config.get("sector_cards",{})
    if args.action=="preview":
        snapshot=snapshot_from_history(json.loads(history_path(config).read_text()),datetime.now(IST),initial=True)
        target=PRIVATE/"sector-cards/preview-real.png"
        render_card(snapshot,target)
        print(json.dumps(dict(image=str(target),market_asof=snapshot["asof"],freshness=snapshot["freshness"],sectors=len(snapshot["rows"]))))
        return
    lock=(PRIVATE/"sector-worker.lock").open("a")
    if args.action!="status":
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit("Sector image worker already running")
    box=SectorOutbox(PRIVATE/"sector-outbox.sqlite3",recover=args.action!="status")
    if args.action=="status":
        print(json.dumps(dict(enabled=policy.get("enabled",False),schedule="Every 30 minutes during NSE regular market hours",
                              **box.status(),jobs=[dict(id=r[0],state=r[1],reason=r[2]) for r in box.db.execute("SELECT id,state,reason FROM jobs ORDER BY updated DESC LIMIT 3")])))
        return
    if args.action=="initial":
        event_id=box.enqueue(config,datetime.now(IST),initial=True)
        if event_id:
            box.deliver(config,sender=send_card,only_event=event_id)
        box.settle()
        print(json.dumps(dict(event_id=event_id,**box.status())))
        return
    if not policy.get("enabled"):
        raise SystemExit("Sector image schedule disabled")
    while True:
        now=datetime.now(IST)
        box.settle()
        from .notification_recipients import publisher_configs
        for publisher in publisher_configs(config):
            box.enqueue(publisher,now)
        if schedule_slot(now) is not None:
            box.deliver(config,sender=send_card)
        box.settle()
        with box.db:box.db.execute("INSERT OR REPLACE INTO meta VALUES('heartbeat',?)",(time.time(),))
        time.sleep(30)


if __name__=="__main__":
    try:main()
    except KeyboardInterrupt:pass
    except Exception:raise SystemExit("Sector image operation failed; sensitive details suppressed")

