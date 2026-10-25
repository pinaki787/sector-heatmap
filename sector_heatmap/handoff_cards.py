"""Images for newly completed owner-scoped Analysis Handoff jobs; no analysis execution."""
import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .sector_cards import PRIVATE, ROOT, SectorOutbox, send_card, parse_time
from .market_calendar import IST


def owner_id(config,root=ROOT):
    registry=root/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        row=db.execute("SELECT id FROM users WHERE username=?",(config["owner_username"],)).fetchone()
    if not row:raise ValueError("Notification owner unavailable")
    return row[0]


def scheduled_report(account,state,updated,saved,error=None):
    """Public analysis status only; never expose private capital or orders."""
    if saved and (saved.get("account_id")!=account["id"] or saved.get("broker")!=account["broker"]):
        return None
    report=dict((saved or {}).get("report") or {})
    if report.get("cards"):
        return report
    reasons=" ".join(str(row.get("reason") or "") for row in report.get("exclusions",[]) if isinstance(row,dict))
    evidence=(str(error or "")+" "+reasons).lower()
    limited=any(word in evidence for word in ("api request limit","rate-limit","rate limit","too many requests"))
    unavailable=state!="COMPLETED" or limited or any(word in evidence for word in ("unavailable","authentication","expired","timeout","timed out","connection"))
    code="RATE_LIMITED" if limited else "DATA_UNAVAILABLE" if unavailable else "NO_NEW_SIGNALS"
    message={"RATE_LIMITED":"Analysis unavailable: broker API request limit reached.",
        "DATA_UNAVAILABLE":"Analysis unavailable: fresh broker evidence could not be verified.",
        "NO_NEW_SIGNALS":"Analysis completed: no new eligible recommendations."}[code]
    report.update(schema="sector-pulse-auto-analysis/v1",
        generated_at=datetime.fromtimestamp(updated,IST).isoformat(),
        source={"broker":account["broker"],"mode":"intraday"},cards=[],candidates=[],
        scheduled_status={"code":code,"message":message},order_authority="NONE",decision_support_only=True)
    # Raw exclusions may describe personal account state; status posts omit them.
    report["exclusions"]=[]
    return report

def completed_jobs(config,root=ROOT):
    uid=owner_id(config,root)
    for account in config["accounts"]:
        folder=root/".private/dashboard-login/accounts"/account["id"]
        for path in (folder/"source/.private/persistent-jobs.sqlite3",folder/"persistent-jobs.sqlite3"):
            if not path.exists():continue
            with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as db:
                rows=db.execute("SELECT id,updated,output,request FROM jobs WHERE owner=? AND feature=? AND kind=? AND status=? ORDER BY updated",
                                (uid+":"+account["id"],"handoff","ANALYSIS","COMPLETED")).fetchall()
            for jobid,updated,output,request in rows:
                source=json.loads(request or "{}")
                if source.get("payload",{}).get("handoff_automation_intermediate") is True:
                    continue
                yield account,jobid,updated,json.loads(output) if output else None
        schedule=folder/"handoff-schedule.sqlite3"
        if schedule.exists():
            with sqlite3.connect(schedule.as_uri()+"?mode=ro",uri=True) as db:
                reports=db.execute("SELECT slot,state,updated,output,error FROM runs WHERE state IN ('COMPLETED','REVIEW') ORDER BY updated").fetchall()
            for slot,state,updated,output,error in reports:
                saved=json.loads(output) if output else {}
                report=scheduled_report(account,state,updated,saved,error)
                if report is not None:
                    yield account,"scheduled-"+slot,updated,report


def summary(result,broker,completed,historical=False):
    if not isinstance(result,dict) or not ("cards" in result or result.get("kind")=="MARKET_HANDOFF"):
        raise ValueError("Unsupported Handoff output; not published")
    native=result.get("broker") or result.get("source",{}).get("broker")
    if native and native!=broker:raise ValueError("Analysis broker mismatch")
    rows=[]
    for card in result.get("cards",[]):
        candidate=card.get("candidate") or {}
        analysis=card.get("analysis") or {}
        proposal=analysis.get("proposal") or {}
        active=analysis.get("active_invalidation") or analysis.get("proposed_sizing") or {}
        stop=active.get("price") or analysis.get("stop_invalidation")
        if isinstance(stop,dict):stop=stop.get("price")
        conviction=analysis.get("conviction") or {}
        try:
            score=float(conviction["score"])/float(conviction["maximum_score"])*10
            if not 0<=score<=10:score=None
        except (KeyError,ValueError,TypeError,ZeroDivisionError):score=None
        rows.append(dict(name=candidate.get("name") or analysis.get("name") or candidate.get("symbol") or "Instrument",
             symbol=candidate.get("symbol") or analysis.get("symbol"),
             direction=analysis.get("direction") or candidate.get("direction") or "UNAVAILABLE",
             status=analysis.get("status") or "UNAVAILABLE",
             kind=analysis.get("kind") or "UNAVAILABLE",
             entry=active.get("entry") or analysis.get("entry"),stop=stop,
             target=active.get("target") or analysis.get("target"),rr=analysis.get("reward_to_risk"),
             conviction_out_of_ten=score,
             units="Underlying price levels" if analysis.get("kind")!="LONG_OPTION" else "Underlying entry; option plan requires review",
             selected_invalidation=analysis.get("active_invalidation"),
             data_quality=analysis.get("data_quality") or candidate.get("data_quality") or "UNAVAILABLE",review_required=True))
    for instrument in result.get("instruments",[]):
        recommendation=instrument.get("recommendation") or {}
        plan=instrument.get("recommended_plan") or {}
        rows.append(dict(name=instrument.get("symbol") or "Instrument",
             symbol=plan.get("symbol") or instrument.get("symbol"),
             direction=recommendation.get("decision") or "WAIT",
             status="SAVED ANALYSIS — VERIFY FRESH QUOTES",kind="MARKET_HANDOFF",
             entry=plan.get("entry"),stop=plan.get("stop_loss"),target=plan.get("target"),
             rr=plan.get("reward_to_risk"),units="Option premium points" if plan else "No eligible premium plan",
             selected_invalidation=None,data_quality="SAVED BROKER EVIDENCE",review_required=True))
    no_action={"WAIT","NO_TRADE","NO TRADE","REJECTED","UNAVAILABLE","BLOCKED","NONE"}
    recommendations=sum(str(r["direction"]).upper() not in no_action and str(r["status"]).upper() not in no_action for r in rows)
    generated=result.get("generated_at")
    if generated:
        asof=parse_time(generated).isoformat()
    else:
        asof=datetime.fromtimestamp(result.get("completed_at") or completed,IST).isoformat()
    return dict(mode=(result.get("source") or {}).get("mode","analysis"),
                source=broker+" Analysis Handoff",asof=asof,generated=datetime.now(IST).isoformat(),
                freshness="SAVED REPORT — NOT CURRENT" if historical else "ANALYSIS UNAVAILABLE — NO NEW SIGNAL" if (result.get("scheduled_status") or {}).get("code") in {"RATE_LIMITED","DATA_UNAVAILABLE"} else "ANALYSIS COMPLETED — NO NEW SIGNAL" if result.get("scheduled_status") else "COMPLETED ANALYSIS — REVIEW REQUIRED",
                rows=rows,recommendation_count=recommendations,excluded_count=len(result.get("exclusions",[])),
                candidate_count=len(result.get("candidates",result.get("instruments",[]))),
                scheduled_status=result.get("scheduled_status"),no_order_authority=True)


def direction_palette(direction):
    value = str(direction or "").strip().upper()
    if value in {"BEARISH", "SELL", "SHORT", "BEAR", "PUT", "PE"}:
        return "#B4233A", "#FFF0F2"
    if value in {"BULLISH", "BUY", "LONG", "BULL", "CALL", "CE"}:
        return "#167A51", "#EDF8F1"
    return "#735C24", "#FFF8E7"


def render_handoff(snapshot,target):
    from PIL import Image,ImageDraw,ImageFont
    plans=snapshot["rows"][:6]
    height=760+max(1,len(plans))*250
    im=Image.new("RGB",(1200,height),"#EDF2F8");d=ImageDraw.Draw(im)
    fonts="/usr/share/fonts/truetype/dejavu/"
    def f(size,bold=False):return ImageFont.truetype(fonts+("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),size)
    def txt(x,y,value,size=26,color="#203B55",bold=False):
        value=str(value);font=f(size,bold)
        while d.textlength(value,font=font)>1030 and len(value)>5:value=value[:-5]+"…"
        d.text((x,y),value,font=font,fill=color)
    def box(rect,color,r=20):d.rounded_rectangle(rect,radius=r,fill=color)
    def value(v):
        return format(v,".2f") if isinstance(v,(int,float)) and not isinstance(v,bool) else "Not available"
    box((36,36,1164,height-36),"#FFFFFF",30)
    box((36,36,1164,268),"#203B55",30);d.rectangle((36,220,1164,268),fill="#203B55")
    txt(77,70,"SECTOR PULSE",25,"#FFFFFF",True)
    txt(77,125,"Analysis Handoff",58,"#FFFFFF",True)
    txt(79,211,"Saved evidence. Clear plans. Review before action.",25,"#C9D9E9")
    txt(77,302,snapshot["freshness"],25,"#8A5B1F",True)
    txt(77,350,("Check time: " if snapshot.get("scheduled_status") else "Analysis as of: ")+parse_time(snapshot["asof"]).strftime("%d %b %Y, %I:%M %p IST"),25)
    txt(77,391,"Source: "+snapshot["source"],24,"#596E82")
    d.line((77,438,1120,438),fill="#DFE7EF",width=2)
    txt(77,465,str(len(snapshot["rows"]))+" saved plans",34,"#167A71",True)
    txt(485,465,str(snapshot["excluded_count"])+" exclusions",34,"#203B55",True)
    txt(77,518,"ANALYSIS ONLY  •  NO ORDER AUTHORITY",24,"#A24751",True)
    if not plans:
        box((77,580,1120,790),"#F1F5F9")
        status=snapshot.get("scheduled_status") or {}
        unavailable=status.get("code") in {"RATE_LIMITED","DATA_UNAVAILABLE"}
        txt(105,615,"Analysis temporarily unavailable" if unavailable else "No new eligible recommendations",32,"#8A5B1F" if unavailable else "#203B55",True)
        txt(105,676,"Broker API request limit reached." if status.get("code")=="RATE_LIMITED" else "Fresh broker evidence could not be verified." if unavailable else "No duplicate signals or orders were replayed.",26,"#596E82")
        txt(105,720,"Open Analysis Handoff to review the exclusions.",24,"#596E82")
    for i,row in enumerate(plans):
        y=580+i*250
        tone,background=direction_palette(row["direction"])
        box((77,y,1120,y+229),background)
        d.rounded_rectangle((77,y,84,y+229),radius=3,fill=tone)
        txt(101,y+17,row["name"],30,"#203B55",True)
        txt(101,y+62,str(row["direction"])+"  |  "+str(row["kind"]),22,tone,True)
        txt(101,y+100,"Entry: "+value(row["entry"])+"     Stop: "+value(row["stop"])+"     Target: "+value(row["target"]),24)
        txt(101,y+139,("Conviction: "+value(row.get("conviction_out_of_ten"))+"/10  |  " if row.get("conviction_out_of_ten") is not None else "R:R: "+value(row["rr"])+"  |  ")+row["units"],22,"#596E82")
        txt(101,y+179,(str(row["status"])+" | "+str(row.get("data_quality","UNAVAILABLE"))).replace("_"," "),19,"#8A5B1F",True)
    y=610+max(1,len(plans))*250
    txt(77,y,"Review the original dashboard report and refresh quotes.",23,"#596E82")
    txt(77,y+38,"Saved proposals are not confirmed entries or permission to trade.",22,"#596E82")
    if len(snapshot["rows"])>6:txt(77,y+76,"Showing first six plans; full result retained in the dashboard.",21,"#596E82")
    target.parent.mkdir(mode=0o700,parents=True,exist_ok=True);im.save(target,optimize=True);os.chmod(target,0o600)


class HandoffOutbox(SectorOutbox):
    def enqueue_job(self,account,jobid,completed,result,historical=False):
        cutoff=self.db.execute("SELECT value FROM meta WHERE key='cutoff'").fetchone()[0]
        if not historical and completed<cutoff:return None
        key="handoff-"+hashlib.sha256((account["id"]+":"+jobid).encode()).hexdigest()[:24]
        previous=self.db.execute("SELECT event_id FROM jobs WHERE id=?",(key,)).fetchone()
        if previous and previous[0]:return previous[0]
        try:
            if not historical and self.clock()-completed>900:
                raise ValueError("Completed analysis too old for a new alert")
            snap=summary(result,account["broker"],completed,historical)
            if not historical and abs(completed-parse_time(snap["asof"]).timestamp())>3600:
                raise ValueError("Analysis generation timestamp is stale")
            target=PRIVATE/"sector-cards"/(key+".png");render_handoff(snap,target)
            evidence=target.with_suffix(".json");evidence.write_text(json.dumps(snap,indent=2));os.chmod(evidence,0o600)
            event=dict(id=key,kind="HANDOFF_CARD",owner_username=account.get("owner_username"),snapshot=snap,image=str(target),
                       image_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?)",(key,json.dumps(event),completed if not historical else self.clock()))
                for channel in ("email","telegram"):
                    empty_email=channel=="email" and snap["recommendation_count"]==0
                    self.db.execute("INSERT OR IGNORE INTO delivery(event,channel,state,error,updated) VALUES(?,?,?,?,?)",
                                    (key,channel,"SKIPPED" if empty_email else "PENDING","No recommendation; email suppressed" if empty_email else None,self.clock()))
                self.db.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?)",(key,"QUEUED",None,key,self.clock()))
            return key
        except Exception as error:
            safe=str(error) if type(error) is ValueError else "Handoff source/render unavailable"
            with self.db:self.db.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?)",(key,"WITHHELD",safe,None,self.clock()))
            return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["run","status","initial","preview"])
    args=parser.parse_args();os.umask(0o077)
    config=json.loads((PRIVATE/"config.json").read_text())
    lock=(PRIVATE/"handoff-worker.lock").open("a")
    if args.action!="status":
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit("Handoff image worker already running")
    box=HandoffOutbox(PRIVATE/"handoff-outbox.sqlite3",recover=args.action!="status")
    if args.action=="status":
        print(json.dumps(dict(enabled=config.get("handoff_cards",{}).get("enabled",False),**box.status(),
             jobs=[dict(id=r[0],state=r[1],reason=r[2]) for r in box.db.execute("SELECT id,state,reason FROM jobs ORDER BY updated DESC LIMIT 3")])))
        return
    if args.action in ("initial","preview"):
        jobs=list(completed_jobs(config))
        if not jobs:raise SystemExit("No completed owner Analysis Handoff result available")
        account,jobid,completed,result=max(jobs,key=lambda j:j[2])
        if args.action=="preview":
            target=PRIVATE/"sector-cards/handoff-preview-real.png"
            render_handoff(summary(result,account["broker"],completed,historical=True),target)
            print(json.dumps(dict(image=str(target),historical=True)))
            return
        key=box.enqueue_job(account,jobid,completed,result,historical=True)
        if key:box.deliver(config,sender=send_card,only_event=key)
        box.settle();print(json.dumps(box.status()));return
    if not config.get("handoff_cards",{}).get("enabled"):
        raise SystemExit("Handoff image delivery disabled")
    while True:
        try:
            from .notification_recipients import publisher_configs
            for publisher in publisher_configs(config):
                for account,jobid,completed,result in completed_jobs(publisher):
                    box.enqueue_job(account,jobid,completed,result)
            box.settle();box.deliver(config,sender=send_card);box.settle()
            with box.db:box.db.execute("INSERT OR REPLACE INTO meta VALUES('heartbeat',?)",(time.time(),))
        except Exception:
            with box.db:box.db.execute("INSERT OR REPLACE INTO meta VALUES('last_scan_error',?)",(time.time(),))
        time.sleep(10)


if __name__=="__main__":
    try:main()
    except KeyboardInterrupt:pass
    except Exception:raise SystemExit("Handoff image operation failed; sensitive details suppressed")

