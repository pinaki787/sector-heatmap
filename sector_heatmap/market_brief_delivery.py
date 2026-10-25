"""Durable ordered panel delivery. Unknown sends stop; accepted panels never replay."""
import hashlib,json
from .sector_cards import media_bytes,send_card
from .trade_notifications import PRIVATE
from .workspaces import private_write

def initialize(box,recover):
 box.db.executescript("""CREATE TABLE IF NOT EXISTS brief_panels(event TEXT,part INTEGER,payload TEXT,state TEXT,message_id INTEGER,error TEXT,destination TEXT,updated REAL,PRIMARY KEY(event,part));
 CREATE TABLE IF NOT EXISTS brief_modes(event TEXT PRIMARY KEY,mode TEXT);""")
 if recover:
  box.db.execute("UPDATE brief_panels SET state='REVIEW',error='Interrupted panel; outcome unknown' WHERE state='SENDING'")
 box.db.commit()

def deliver_panels(box,channel,config,event,legacy_sender):
 if channel!="telegram":return "REVIEW","Market panels are Telegram-only"
 routes=config.get("telegram_destinations") or {};shared=routes.get("shared_market") or {};private=routes.get("private_trades") or {}
 if not routes.get("enabled") or not shared.get("enabled") or config.get("telegram",{}).get("chat_id")!=shared.get("chat_id") or shared.get("chat_id")==private.get("chat_id"):
  return "REVIEW","Verified distinct shared-market destination required"
 if event.get("delivery_slot"):
  from .sector_cards import parse_time
  try:
   start=parse_time(event["delivery_slot"]).timestamp();safe=start<=box.clock()<=start+900-31
  except (ValueError,TypeError):safe=False
  if not safe:return "REVIEW","Delivery slot elapsed; panel or fallback transmission withheld"
 destination=hashlib.sha256(str(shared["chat_id"]).encode()).hexdigest();panels=event.get("panels") or []
 if not 1<=len(panels)<=7 or [p.get("index") for p in panels]!=list(range(len(panels))):return "REVIEW","Invalid ordered panel manifest"
 saved=box.db.execute("SELECT part,payload,state,message_id,destination FROM brief_panels WHERE event=? ORDER BY part",(event["id"],)).fetchall()
 if not saved:
  with box.db:
   for p in panels:box.db.execute("INSERT INTO brief_panels VALUES(?,?,?,'PENDING',NULL,NULL,?,?)",(event["id"],p["index"],json.dumps(p,sort_keys=True),destination,box.clock()))
  saved=box.db.execute("SELECT part,payload,state,message_id,destination FROM brief_panels WHERE event=? ORDER BY part",(event["id"],)).fetchall()
 if len(saved)!=len(panels) or any(row[1]!=json.dumps(panels[row[0]],sort_keys=True) or row[4]!=destination for row in saved):return "REVIEW","Panel content or destination changed; no automatic replay"
 if any(row[2] in {"REVIEW","SENDING"} for row in saved):return "REVIEW","Panel outcome uncertain; remaining panels withheld"
 accepted=any(row[2]=="SENT" for row in saved)
 def fallback():
  if accepted:return "REVIEW","Partial panel set delivered; no full-text duplicate"
  with box.db:box.db.execute("INSERT OR REPLACE INTO brief_modes VALUES(?,'TEXT')",(event["id"],))
  return legacy_sender(channel,config,{**event,"text_only":True})
 mode=box.db.execute("SELECT mode FROM brief_modes WHERE event=?",(event["id"],)).fetchone()
 if mode and mode[0]=="TEXT":return fallback()
 # Validate the complete retained set before transmitting the first unsent panel.
 try:
  for p in panels:media_bytes({**event,**p,"kind":"COMBINED_CARD"})
 except FileNotFoundError:return fallback()
 except Exception:return "REVIEW","Panel integrity check failed"
 for index,payload,state,message_id,_ in saved:
  if state=="SENT":continue
  if event.get("delivery_slot"):
   from .sector_cards import parse_time
   try:
    start=parse_time(event["delivery_slot"]).timestamp();remaining=sum(r[2]!="SENT" for r in saved if r[0]>=index)
    # Reserve the transport timeout for every remaining panel, avoiding a
    # partial set started immediately before the slot/session closes.
    safe=start<=box.clock()<=start+900-remaining*31
   except (ValueError,TypeError):safe=False
   if not safe:return "REVIEW","Delivery slot ended or insufficient time; remaining panels withheld"
  p=panels[index];response=[]
  with box.db:box.db.execute("UPDATE brief_panels SET state='SENDING',updated=? WHERE event=? AND part=?",(box.clock(),event["id"],index))
  def receipt(result):
   message=result.get("result") or {}
   response.append(message)
   private_write(PRIVATE/"combined-reports"/(event["id"]+f".p{index+1}.receipt.json"),json.dumps(dict(event_id=event["id"],part=index,accepted=result.get("ok") is True,message_id=message.get("message_id"),chat_id=(message.get("chat") or {}).get("id"),date=message.get("date"))))
  try:outcome,error=send_card(channel,config,{**event,**p,"kind":"COMBINED_CARD","panel_index":index},audit=receipt)
  except Exception:outcome,error="REVIEW","Panel send outcome unknown"
  if outcome=="SENT":
   if len(response)!=1 or not isinstance(response[0].get("message_id"),int) or (response[0].get("chat") or {}).get("id")!=shared["chat_id"]:outcome,error="REVIEW","Panel acceptance receipt invalid; no replay"
  if outcome=="RETRY" and error and error.startswith("Telegram HTTP 5"):outcome,error="REVIEW","Panel server outcome uncertain; no replay"
  if outcome not in {"SENT","RETRY","REVIEW"}:outcome,error="REVIEW","Panel outcome unsupported"
  mid=response[0].get("message_id") if response else None
  with box.db:box.db.execute("UPDATE brief_panels SET state=?,message_id=?,error=?,updated=? WHERE event=? AND part=?",(outcome,mid,error,box.clock(),event["id"],index))
  if outcome=="SENT":accepted=True;continue
  if outcome=="RETRY" and error=="Telegram HTTP 400":
   if not accepted:return fallback()
   with box.db:box.db.execute("UPDATE brief_panels SET state='REVIEW',error='Rejected panel after partial acceptance; review required' WHERE event=? AND part=?",(event["id"],index))
   return "REVIEW","Partial panel set; rejected panel withheld, no duplicate summary"
  return outcome,error
 ids=[r[0] for r in box.db.execute("SELECT message_id FROM brief_panels WHERE event=? ORDER BY part",(event["id"],))]
 private_write(PRIVATE/"combined-reports"/(event["id"]+".receipt.json"),json.dumps(dict(event_id=event["id"],accepted=True,message_ids=ids,chat_id=shared["chat_id"],panel_count=len(ids))))
 return "SENT",None
