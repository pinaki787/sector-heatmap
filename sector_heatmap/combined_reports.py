"""Shared sector + Handoff + screener digest. Read-only sources, Telegram only."""
import argparse,fcntl,hashlib,json,math,os,sqlite3,subprocess,time
from datetime import datetime,timedelta
from pathlib import Path
from .market_calendar import IST,market_session,REGULAR_OPEN
from .sector_cards import snapshot_from_history,history_path,parse_time,SectorOutbox,send_card
from .trade_notifications import ROOT,PRIVATE
from .handoff_cards import completed_jobs
from .workspaces import WorkspaceStore,isolated_environment,private_write
ACCOUNT="bf46fc364b610a0dfd338419e133cb41"
def number(value):
 return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def grade(row):
 c=row.get("conviction") or {}
 return round(c["score"]/c["maximum_score"]*10,2) if number(c.get("score")) and number(c.get("maximum_score")) and c["maximum_score"]>0 else None
def slot(now):
 if market_session(now)["status"]!="OPEN":return None
 start=now.replace(hour=REGULAR_OPEN.hour,minute=REGULAR_OPEN.minute,second=0,microsecond=0)
 return (start+timedelta(minutes=15*int((now-start).total_seconds()//900))).isoformat()
def freshness(value,now,max_age=1800):
 try:
  stamp=parse_time(value);age=(now-stamp).total_seconds()
  return "CURRENT" if 0<=age<=max_age else "LATEST AVAILABLE / STALE"
 except (TypeError,ValueError):return "TIMESTAMP UNAVAILABLE"
def stamp(value):
 try:return parse_time(value).strftime("%d %b %Y %H:%M IST")
 except (TypeError,ValueError):return "Unavailable"
def level(value):return f"{value:,.2f}" if number(value) and value>0 else "Unavailable"
def scope(config):
 rows=[a for a in config["accounts"] if a.get("id")==ACCOUNT and a.get("broker")=="FYERS"]
 if len(rows)!=1:raise ValueError("Configured FYERS report owner unavailable")
 return rows[0]
def screener_source(root=ROOT):
 path=root/".private/dashboard-login/accounts"/ACCOUNT/"source/.private/persistent-jobs.sqlite3"
 with sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True) as db:
  for updated,request,output in db.execute("SELECT updated,request,output FROM jobs WHERE feature='screener' AND kind='ANALYSIS' AND status='COMPLETED' ORDER BY updated DESC"):
   req=json.loads(request or "{}");payload=req.get("payload") or {}
   if req.get("account_id")!=ACCOUNT or not isinstance(payload.get("symbols"),list):continue
   symbols=list(dict.fromkeys(str(s).upper() for s in payload["symbols"]))
   if not 0<len(symbols)<=150:raise ValueError("Saved screener universe exceeds the bounded report scan")
   result=json.loads(output or "{}")
   return {"account_id":ACCOUNT,"broker":"FYERS","symbols":symbols,"universe_asof":datetime.fromtimestamp(updated,IST).isoformat()},result
 raise ValueError("No explicitly submitted FYERS screener universe")
def intraday_asof(rows):
 times=[]
 for row in rows:
  frame=(row.get("timeframe_states") or {}).get("15m") or {}
  if frame.get("last_updated"):times.append(frame["last_updated"])
 return min(times,key=lambda value:parse_time(value)) if times else None
def screen_section(value,now):
 if value.get("account_id") not in (None,ACCOUNT) or value.get("broker") not in (None,"FYERS"):
  return {"status":"UNAVAILABLE","asof":None,"lines":["Account scope mismatch; report withheld."]}
 checked=value.get("generated_at")
 asof=intraday_asof(value.get("results",[]))
 status=value.get("status","UNAVAILABLE")
 lines=["Analysis checked "+stamp(checked),f"Coverage: {value.get('analyzed',0)} / {value.get('total',0)} saved-universe stocks"]
 ready=[r for r in value.get("results",[]) if r.get("decision")=="PASS"]
 ready.sort(key=lambda r:-(grade(r) or 0))
 for row in ready[:5]:
  lines.append(f"{row.get('symbol','Instrument')} | {row.get('direction','Unavailable')} | conviction {grade(row) or 'Unavailable'}/10")
  lines.append(f"Underlying entry {level(row.get('entry'))} | stop {level(row.get('stop'))} | target {level(row.get('target'))}")
 if not ready:lines.append("No eligible findings in the examined rows." if status in ("COMPLETED","READY") else "Fresh analysis unavailable or still running; no current recommendation claimed.")
 if value.get("universe_asof"):lines.append("Universe selected "+stamp(value["universe_asof"])+"; membership is fixed.")
 qualities={str(frame.get("data_quality") or "UNAVAILABLE").upper() for row in value.get("results",[]) for frame in (row.get("timeframe_states") or {}).values()}
 evidence="BROKER EVIDENCE DELAYED" if "DELAYED" in qualities else freshness(asof,now)
 if "UNAVAILABLE" in qualities or "STALE" in qualities:evidence+=" / SOME EVIDENCE UNAVAILABLE OR STALE"
 return {"status":status+" | "+evidence,"asof":asof,"lines":lines}
def handoff_section(report,completed,now):
 checked=report.get("generated_at") or datetime.fromtimestamp(completed,IST).isoformat()
 asof=intraday_asof([c.get("candidate") or {} for c in report.get("cards",[])])
 lines=["Analysis checked "+stamp(checked)]
 for card in sorted(report.get("cards",[]),key=lambda c:-(grade(c.get("analysis") or {}) or 0))[:5]:
  candidate=card.get("candidate") or {};a=card.get("analysis") or {};proposed=a.get("proposed_sizing") or {}
  active=a.get("active_invalidation") or {};recommended=a.get("recommended_invalidation") or {};proposal=a.get("proposal") or {}
  entry=active.get("entry") or proposed.get("entry") or a.get("entry")
  stop=active.get("price") or proposed.get("price") or recommended.get("price")
  lines.append(f"{candidate.get('symbol') or candidate.get('name') or 'Instrument'} | {a.get('direction') or candidate.get('direction') or 'Unavailable'} | conviction {grade(a) or 'Unavailable'}/10")
  if a.get("kind")=="LONG_OPTION":
   lines.append(f"Underlying entry {level(entry)} | proposed invalidation {level(stop)} | option-premium target {level(proposal.get('target_exit_points'))}")
  else:lines.append(f"Underlying entry {level(entry)} | proposed stop {level(stop)} | target {level(active.get('target') or proposed.get('target') or a.get('target'))}")
 if len(lines)==1:lines+=["No new eligible recommendations." if not report.get("scheduled_status") else report["scheduled_status"]["message"]]
 return {"status":freshness(asof,now),"asof":asof,"lines":lines}
def collect(config,now,screener=None,root=ROOT,mtf=None):
 scope(config)
 sections=[];sector_visual={};handoff_visual={}
 try:
  history=json.loads(history_path(config,root).read_text())
  snap=snapshot_from_history(history,now,initial=market_session(now)["status"]!="OPEN")
  from .market_brief_visual import sector_public
  if mtf is None:
   try:mtf=json.loads((root/".private/notifications/combined-reports/sector-mtf-latest.json").read_text())
   except (OSError,ValueError):mtf={}
  sector_visual=sector_public(snap,history,mtf,now)
  lines=[f"{r['name']} | score {r['score']:.1f}/100 | {r['rotation']}" for r in snap["rows"] if number(r.get("score"))][:5]
  sector={"status":snap["freshness"],"asof":snap["asof"],"lines":lines}
 except Exception:sector={"status":"UNAVAILABLE","asof":None,"lines":["Fresh sector snapshot could not be verified; no stale scores presented as current."]}
 sections.append(("SECTOR ROTATION",sector))
 try:
  matches=[r for r in completed_jobs(config,root) if r[0]["id"]==ACCOUNT]
  latest=max(matches,key=lambda r:r[2])
  handoff=handoff_section(latest[3],latest[2],now)
  from .market_brief_visual import handoff_public
  handoff_visual=handoff_public(latest[3],now)
 except Exception:handoff={"status":"UNAVAILABLE","asof":None,"lines":["No readable owned Handoff outcome."]}
 sections.append(("ANALYSIS HANDOFF",handoff))
 if screener is None:
  try:
   request,screener=screener_source(root)
   screener={**screener,"generated_at":request["universe_asof"],"universe_asof":request["universe_asof"],"account_id":ACCOUNT,"broker":"FYERS"}
  except Exception:screener={"status":"UNAVAILABLE"}
 sections.append(("SCREENER",screen_section(screener,now)))
 return {"generated":now.isoformat(),"account_id":ACCOUNT,"broker":"FYERS","sections":sections,"order_authority":"NONE","sector_visual":sector_visual,"handoff_visual":handoff_visual,"screener_visual":{"coverage":str(screener.get("analyzed",0))+" / "+str(screener.get("total",0))+" examined","status":screen_section(screener,now)["status"],"asof":intraday_asof(screener.get("results",[]))}}
def render(snapshot,target):
 from .market_brief_visual import render as render_visual
 return render_visual(snapshot,target)
class CombinedOutbox(SectorOutbox):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  from .market_brief_delivery import initialize
  initialize(self,kwargs.get("recover",True))
 def deliver(self,config,sender=None,only_event=None):
  if sender is None or sender is deliver_card:
   from .market_brief_delivery import deliver_panels
   def selected(channel,cfg,event):
    return deliver_panels(self,channel,cfg,event,deliver_card) if event.get("panels") else deliver_card(channel,cfg,event)
   sender=selected
  return super().deliver(config,sender=sender,only_event=only_event)
 def settle(self):
  with self.db:self.db.execute("UPDATE delivery SET state='EXPIRED',error='Combined report slot expired' WHERE state IN ('PENDING','RETRY','PAUSED') AND event IN (SELECT id FROM events WHERE created<?)",(self.clock()-900,))
  super().settle()
def enqueue(box,config,snapshot,key):
 ident="combined-"+hashlib.sha256((config["owner_username"]+":"+ACCOUNT+":"+key).encode()).hexdigest()[:24]
 if box.db.execute("SELECT 1 FROM events WHERE id=?",(ident,)).fetchone():return ident
 image=PRIVATE/"combined-reports"/(ident+".png")
 image_ok=True
 panels=[]
 try:
  from .market_brief_panels import render_panels
  panels=render_panels(snapshot,image)
  if not panels:raise ValueError("No report panels")
 except Exception:image_ok=False  # No network send has occurred; retain text-only event.
 from .market_brief_visual import caption,fallback_text
 from .market_brief_panels import REVISION
 private_write(image.with_suffix(".json"),json.dumps(snapshot,allow_nan=False))
 event={"id":ident,"kind":"COMBINED_CARD","owner_username":config["owner_username"],"image":panels[0]["image"] if image_ok else str(image),
  "image_sha256":panels[0]["image_sha256"] if image_ok else None,"panels":panels if image_ok else [],"snapshot":snapshot,"text_only":not image_ok,"visual_revision":REVISION,"delivery_slot":key[5:] if key.startswith("slot-") else None,"public_text":fallback_text(snapshot),
  "public_caption":caption(snapshot)}
 with box.db:
  box.db.execute("INSERT INTO events VALUES(?,?,?)",(ident,json.dumps(event),box.clock()))
  box.db.execute("INSERT INTO delivery(event,channel,state,updated) VALUES(?,'telegram','PENDING',?)",(ident,box.clock()))
 return ident
def deliver_card(channel,config,event):
 if channel!="telegram":return "REVIEW","Combined brief is Telegram-only"
 def receipt(result):
  message=result.get("result") or {}
  private_write(PRIVATE/"combined-reports"/(event["id"]+".receipt.json"),json.dumps({
   "event_id":event["id"],"accepted":result.get("ok") is True,"message_id":message.get("message_id"),
   "chat_id":(message.get("chat") or {}).get("id"),"date":message.get("date")}))
 # Enforce the verified shared route even if upstream routing configuration is absent.
 routes=config.get("telegram_destinations") or {};shared=routes.get("shared_market") or {};private=routes.get("private_trades") or {}
 if not routes.get("enabled") or not shared.get("enabled") or config.get("telegram",{}).get("chat_id")!=shared.get("chat_id") or shared.get("chat_id")==private.get("chat_id"):
  return "REVIEW","Verified distinct shared-market destination required"
 if event.get("text_only"):return send_text(config,event,receipt)
 from .sector_cards import media_bytes
 try:media_bytes(event)
 except FileNotFoundError:return send_text(config,event,receipt)
 except Exception:return "REVIEW","Retained image failed integrity check"
 outcome,error=send_card(channel,config,event,audit=receipt)
 # Only an authoritative HTTP 400 rejection permits a second transport attempt.
 # A timeout/disconnect/5xx may have accepted the photo: never send a duplicate text.
 if outcome=="RETRY" and error=="Telegram HTTP 400":return send_text(config,event,receipt)
 if outcome=="RETRY" and error and error.startswith("Telegram HTTP 5"):return "REVIEW","Photo outcome uncertain; no fallback sent"
 return outcome,error

def send_text(config,event,audit):
 import urllib.request,urllib.error,ssl
 text=event.get("public_text")
 if not isinstance(text,str) or not 0<len(text)<=3900:return "REVIEW","Public fallback unavailable"
 data=json.dumps({"chat_id":config["telegram"]["chat_id"],"text":text,"disable_web_page_preview":True}).encode()
 req=urllib.request.Request("https://api.telegram.org/bot"+config["telegram"]["token"]+"/sendMessage",data=data,headers={"Content-Type":"application/json"},method="POST")
 try:
  with urllib.request.urlopen(req,timeout=30,context=ssl.create_default_context()) as response:result=json.load(response)
  if result.get("ok"):
   audit(result);return "SENT",None
  return "RETRY","Telegram rejected compact brief"
 except urllib.error.HTTPError as error:
  return ("RETRY","Telegram text rejected") if error.code in (400,401,403,429) else ("REVIEW","Text outcome uncertain")
 except Exception:return "REVIEW","Text outcome unknown; no automatic duplicate"

def launch(config,request,output,worker_module="sector_heatmap.combined_screener_worker"):
 if worker_module not in {"sector_heatmap.combined_screener_worker","sector_heatmap.combined_sector_worker"}:raise ValueError("Unsupported report worker")
 scope(config);folder=ROOT/".private/dashboard-login/accounts"/ACCOUNT
 registry=ROOT/".private/dashboard-login/registry.sqlite3"
 with sqlite3.connect(registry.resolve().as_uri()+"?mode=ro",uri=True) as db:
  db.row_factory=sqlite3.Row
  row=db.execute("SELECT a.*,u.username FROM accounts a JOIN users u ON a.user_id=u.id WHERE a.id=?",(ACCOUNT,)).fetchone()
  if not row or row["broker"]!="FYERS" or row["username"]!=config["owner_username"]:raise ValueError("Owned screener account unavailable")
  account=dict(row)
 env=isolated_environment(account,folder,registry,8079)
 # This worker is analysis-only, even when the account permits live trading.
 for key in list(env):
  if "ENABLE" in key and "LIVE" in key:env[key]="0"
 path=output.with_suffix(".request.json");private_write(path,json.dumps(request))
 with open(PRIVATE/"combined-screener.log","a") as log:
  return subprocess.Popen([str(ROOT/".venv/bin/python"),"-B","-m",worker_module,"--request",str(path),"--output",str(output)],cwd=folder/"source",env=env,stdout=log,stderr=log,start_new_session=True)
def read_sector_mtf(config,output,timeout=210):
 """Isolated market-data worker; never uses an Auto/session submission path."""
 try:
  proc=launch(config,dict(account_id=ACCOUNT,broker="FYERS"),output,worker_module="sector_heatmap.combined_sector_worker")
  try:proc.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   proc.terminate();proc.wait(timeout=10);raise ValueError("Sector MTF report deadline")
  value=json.loads(output.read_text())
  if value.get("status")!="COMPLETED":raise ValueError("Sector MTF report unavailable")
  private_write(PRIVATE/"combined-reports/sector-mtf-latest.json",json.dumps(value,allow_nan=False))
  return value
 except Exception:return dict(status="UNAVAILABLE",sectors=[])

def main():
 parser=argparse.ArgumentParser();parser.add_argument("action",choices=["initial","preview","run","probe"]);args=parser.parse_args()
 os.umask(0o077);PRIVATE.mkdir(parents=True,exist_ok=True)
 lock=(PRIVATE/("combined-"+args.action+".lock" if args.action in {"probe","preview"} else "combined-worker.lock")).open("a");fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 config=json.loads((PRIVATE/"config.json").read_text())
 if not config.get("combined_reports",{}).get("enabled") and args.action!="preview":raise SystemExit("Combined reports disabled")
 if args.action=="probe":
  request,_=screener_source();request["symbols"]=request["symbols"][:2]
  output=PRIVATE/"combined-reports/service-probe.json"
  proc=launch(config,request,output);proc.wait(timeout=90)
  result=json.loads(output.read_text())
  print(json.dumps({key:result.get(key) for key in ["status","analyzed","total","generated_at"]}),flush=True)
  if result.get("status")!="COMPLETED":raise SystemExit("Read-only screener probe failed")
  return
 if args.action=="preview":
  snapshot=collect(config,datetime.now(IST));path=PRIVATE/"combined-reports/preview.png"
  from .market_brief_panels import render_panels
  panels=render_panels(snapshot,path);private_write(path.with_name("preview-panels.json"),json.dumps(panels,indent=2))
  print(json.dumps({"panels":[p["image"] for p in panels],"sections":[[t,s["status"]] for t,s in snapshot["sections"]]}));return
 box=CombinedOutbox(PRIVATE/"combined-outbox.sqlite3",recover=True)
 def publish(snapshot,key):
  event=enqueue(box,config,snapshot,key);box.deliver(config,sender=deliver_card,only_event=event);box.settle()
  states=box.db.execute("SELECT channel,state FROM delivery WHERE event=?",(event,)).fetchall()
  print(json.dumps({"event_id":event,"delivery":states}),flush=True);return event
 if args.action=="initial":
  snapshot=collect(config,datetime.now(IST))
  publish(snapshot,"initial-"+datetime.now(IST).date().isoformat())
  with box.db:box.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)",("initial_slot",slot(datetime.now(IST))))
  return
 while True:
  config=json.loads((PRIVATE/"config.json").read_text())
  now=datetime.now(IST);current=slot(now)
  with box.db:box.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)",("heartbeat",time.time()))
  initial=box.db.execute("SELECT value FROM meta WHERE key=?",("initial_slot",)).fetchone()
  if current and current!=(initial[0] if initial else None) and config.get("combined_reports",{}).get("enabled"):
   key="slot-"+current
   ident="combined-"+hashlib.sha256((config["owner_username"]+":"+ACCOUNT+":"+key).encode()).hexdigest()[:24]
   if not box.db.execute("SELECT 1 FROM events WHERE id=?",(ident,)).fetchone():
    deadline=time.monotonic()+820
    mtf_output=PRIVATE/"combined-reports"/("sector-mtf-"+hashlib.sha256(key.encode()).hexdigest()[:16]+".json")
    mtf=read_sector_mtf(config,mtf_output,timeout=210)
    output=PRIVATE/"combined-reports"/("screener-"+hashlib.sha256(key.encode()).hexdigest()[:16]+".json")
    try:
     request,_=screener_source();proc=launch(config,request,output)
     try:proc.wait(timeout=max(1,deadline-time.monotonic()))
     except subprocess.TimeoutExpired:
      proc.terminate();proc.wait(timeout=10)
      raise ValueError("Screener scan deadline")
     screener=json.loads(output.read_text()) if output.exists() else {"status":"UNAVAILABLE"}
    except Exception as error:
     with box.db:box.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)",("last_worker_error",type(error).__name__))
     screener={"status":"UNAVAILABLE","generated_at":datetime.now(IST).isoformat()}
    # Never deliver the prior slot late or after market close.
    finished=datetime.now(IST)
    if slot(finished)==current:publish(collect(config,finished,screener,mtf=mtf),key)
  box.deliver(config,sender=deliver_card);box.settle();time.sleep(15)
if __name__=="__main__":main()
