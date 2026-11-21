"""Post exactly one authorized latest sector card to the existing shared channel."""
import argparse,fcntl,hashlib,json,os,sqlite3,sys,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sector_heatmap.sector_cards import PRIVATE,IST,history_path,snapshot_from_history,render_card,send_card
from sector_heatmap.notification_destinations import telegram_destination
from sector_heatmap.notification_controls import gate
from sector_heatmap.config import _atomic_private_write

def identity(snapshot):
    return hashlib.sha256(json.dumps(dict(asof=snapshot["asof"],rows=[{k:r.get(k) for k in ("sector_id","name","score","rs","rotation","asof")} for r in snapshot["rows"]]),sort_keys=True).encode()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-authorized",action="store_true")
    args=parser.parse_args();os.umask(0o077)
    config=json.loads((PRIVATE/"config.json").read_text());now=datetime.now(IST)
    snapshot=snapshot_from_history(json.loads(history_path(config).read_text()),now,initial=True)
    result=dict(channel="Sector Pulse Trade Alerts",market_asof=snapshot["asof"],newest_asof=snapshot["newest_asof"],sectors=len(snapshot["rows"]),sent=False)
    if not args.send_authorized:print(json.dumps(result));return
    lock=(PRIVATE/"manual-sector-post.lock").open("a");fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=sqlite3.connect(PRIVATE/"sector-outbox.sqlite3",timeout=15)
    fingerprint=identity(snapshot);key="sector-manual-"+fingerprint[:24]
    route=(config.get("telegram_destinations") or {}).get("shared_market") or {}
    for payload,created in db.execute("SELECT e.payload,e.created FROM events e JOIN delivery d ON d.event=e.id WHERE d.channel='telegram' AND d.state='SENT'"):
        event=json.loads(payload)
        if event.get("kind")=="SECTOR_CARD" and event.get("owner_username")==config["owner_username"] and created>=route.get("activated_at",float("inf")) and identity(event["snapshot"])==fingerprint:
            result.update(already_delivered=True);print(json.dumps(result));return
    prior=db.execute("SELECT state FROM delivery WHERE event=? AND channel='telegram'",(key,)).fetchone()
    if prior:raise ValueError("This one-off post already has an outcome; no automatic replay.")
    target=PRIVATE/"sector-cards"/(key+".png");render_card(snapshot,target)
    event=dict(id=key,kind="SECTOR_CARD",owner_username=config["owner_username"],snapshot=snapshot,image=str(target),
        image_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    delivery_config,blocked=telegram_destination(config,event,now.timestamp())
    if blocked:raise ValueError(blocked)
    held,reason=gate("telegram",event,now.timestamp())
    if held:raise ValueError(reason or "Telegram delivery is paused.")
    with db:
        db.execute("INSERT INTO events VALUES(?,?,?)",(key,json.dumps(event),now.timestamp()))
        db.execute("INSERT INTO delivery(event,channel,state,updated) VALUES(?,'telegram','SENDING',?)",(key,time.time()))
    evidence_path=PRIVATE/"sector-cards"/(key+"-telegram.json")
    def audit(response):
        message=response.get("result") or {};chat=message.get("chat") or {}
        if chat.get("id")!=delivery_config["telegram"]["chat_id"] or not isinstance(message.get("message_id"),int):
            raise ValueError("Telegram acknowledgement destination is unverified.")
        evidence=dict(event_id=key,channel_title=chat.get("title"),chat_id=chat["id"],message_id=message["message_id"],
            telegram_date=message.get("date"),market_asof=snapshot["asof"],image_sha256=event["image_sha256"])
        _atomic_private_write(evidence_path,json.dumps(evidence))
        result.update(sent=True,message_id=message["message_id"],channel=chat.get("title") or result["channel"])
    state,error=send_card("telegram",delivery_config,event,audit=audit)
    with db:db.execute("UPDATE delivery SET state=?,attempts=1,error=?,updated=? WHERE event=? AND channel='telegram'",(state,error,time.time(),key))
    result.update(state=state,error=error)
    print(json.dumps(result))

if __name__=="__main__":main()
