"""Owner-only notification preferences and Telegram controls. Never changes trading."""
import argparse
import fcntl
import json
import os
import sqlite3
import ssl
import tempfile
import time
import urllib.request
from pathlib import Path
from .trade_notifications import PRIVATE

SCOPES={"all":"All notifications","trades":"Trade alerts","sector":"Sector images","handoff":"Analysis Handoff","combined":"Combined market brief"}
CHANNELS={"telegram":"Telegram","email":"Gmail"}
PREFERENCES=PRIVATE/"preferences.json"


def preferences(path=None):
    path=Path(path or PREFERENCES)
    if not path.exists():
        return {"version":1,"scopes":{}}
    result=json.loads(path.read_text())
    if result.get("version")!=1 or not isinstance(result.get("scopes"),dict):
        raise ValueError("Notification preferences unreadable")
    return result


def set_paused(scope,channel,paused,path=None,clock=time.time):
    if scope not in SCOPES or channel not in CHANNELS or type(paused) is not bool:
        raise ValueError("Invalid notification preference")
    path=Path(path or PREFERENCES)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        os.chmod(path.with_suffix(".lock"),0o600)
        fcntl.flock(lock,fcntl.LOCK_EX)
        data=preferences(path)
        current=data["scopes"].setdefault(scope,{}).get(channel,{})
        if current.get("paused",False)==paused:
            return data
        row={"paused":paused,"changed_at":clock(),"resumed_at":current.get("resumed_at",0)}
        if not paused:
            row["resumed_at"]=clock()
        data["scopes"][scope][channel]=row
        fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".preferences-")
        try:
            with os.fdopen(fd,"w") as handle:
                os.fchmod(handle.fileno(),0o600);json.dump(data,handle);handle.flush();os.fsync(handle.fileno())
            os.replace(tmp,path)
        finally:
            if Path(tmp).exists():os.unlink(tmp)
        return data


def gate(channel,event,created,path=None):
    if channel=="email" and event.get("kind")=="HANDOFF_CARD":
        snapshot=event.get("snapshot") or {}
        count=snapshot.get("recommendation_count")
        if count is None and "rows" in snapshot:count=len(snapshot["rows"])
        if count==0:
            return "SKIPPED","No recommendation; email suppressed"
    scope={"SECTOR_CARD":"sector","HANDOFF_CARD":"handoff","COMBINED_CARD":"combined"}.get(event.get("kind"),"trades")
    try:
        data=preferences(path)
        policies=[data["scopes"].get(s,{}).get(channel,{}) for s in ("all",scope)]
        if any(p.get("paused",False) for p in policies):
            return "PAUSED","Paused by owner"
        occurred=event.get("time") if scope=="trades" else created
        occurred=occurred if isinstance(occurred,(int,float)) else created
        if any(p.get("resumed_at",0)>=occurred for p in policies):
            return "SKIPPED","Paused backlog not replayed after resume"
        return None,None
    except Exception:
        return "PAUSED","Notification preferences unavailable; delivery held"


def menu(data=None):
    data=data or preferences()
    lines=["Sector Pulse notification controls",""]
    keyboard=[]
    for scope,label in SCOPES.items():
        rows=data["scopes"].get(scope,{})
        line=label+": "
        line+=" | ".join(CHANNELS[c]+" "+("paused" if rows.get(c,{}).get("paused",False) else "on") for c in CHANNELS)
        lines.append(line)
        buttons=[]
        for channel,name in CHANNELS.items():
            paused=rows.get(channel,{}).get("paused",False)
            buttons.append({"text":("Resume " if paused else "Pause ")+name+" · "+label,
                            "callback_data":"set:"+scope+":"+channel+":"+("0" if paused else "1")})
        keyboard.append(buttons)
    lines+=["","Global pause overrides category settings.","Resume sends NEW updates only; paused backlog is not replayed.",
            "These controls never stop or start trading runners.","Use /notifications to reopen this panel."]
    return "\n".join(lines),{"inline_keyboard":keyboard}


def owner_update(update,chat_id):
    callback=update.get("callback_query")
    if callback:
        message=callback.get("message") or {}
        source=callback.get("from") or {}
    else:
        message=update.get("message") or {}
        source=message.get("from") or {}
    chat=message.get("chat") or {}
    return source.get("id")==chat_id and chat.get("id")==chat_id and chat.get("type")=="private"


def api(config,method,body):
    request=urllib.request.Request("https://api.telegram.org/bot"+config["telegram"]["token"]+"/"+method,
          data=json.dumps(body).encode(),headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(request,timeout=25,context=ssl.create_default_context()) as response:
            data=json.load(response)
        if not data.get("ok"):raise RuntimeError()
        return data["result"]
    except Exception:
        raise RuntimeError("Telegram control request failed; secrets suppressed") from None


def handle_update(update,config,request=api,path=None,minimum_date=0):
    chat_id=config["telegram"]["chat_id"]
    if not owner_update(update,chat_id):
        return "IGNORED"
    callback=update.get("callback_query")
    if callback:
        pieces=str(callback.get("data","")).split(":")
        if len(pieces)!=4 or pieces[0]!="set" or pieces[1] not in SCOPES or pieces[2] not in CHANNELS or pieces[3] not in ("0","1"):
            return "IGNORED"
        scope,channel,flag=pieces[1:]
        data=set_paused(scope,channel,flag=="1",path=path)
        request(config,"answerCallbackQuery",{"callback_query_id":callback["id"],"text":("Paused " if flag=="1" else "Resumed ")+CHANNELS[channel]+": "+SCOPES[scope]})
        text,markup=menu(data)
        request(config,"editMessageText",{"chat_id":chat_id,"message_id":callback["message"]["message_id"],"text":text,"reply_markup":markup})
        return "UPDATED"
    message=update["message"]
    if message.get("date",0)<minimum_date:return "IGNORED"
    text=message.get("text","").strip().split("@")[0]
    commands={"/pause_telegram":("telegram",True),"/resume_telegram":("telegram",False),
              "/pause_email":("email",True),"/resume_email":("email",False)}
    if text in commands:
        channel,paused=commands[text]
        set_paused("all",channel,paused,path=path)
    elif text not in ("/notifications","/start","/help"):
        return "IGNORED"
    content,markup=menu(preferences(path))
    request(config,"sendMessage",{"chat_id":chat_id,"text":content,"reply_markup":markup})
    return "PANEL"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["publish","run","status"])
    args=parser.parse_args()
    os.umask(0o077)
    config=json.loads((PRIVATE/"config.json").read_text())
    if args.action=="publish":
        text,markup=menu()
        api(config,"sendMessage",{"chat_id":config["telegram"]["chat_id"],"text":text,"reply_markup":markup})
        print("Notification control panel sent to the owner private bot chat.")
        return
    if args.action=="status":
        print(json.dumps(preferences()))
        return
    with (PRIVATE/"controls-worker.lock").open("a") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit("Notification control worker already running")
        db=sqlite3.connect(PRIVATE/"controls.sqlite3")
        db.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value REAL)")
        db.execute("INSERT OR IGNORE INTO meta VALUES('created',?)",(time.time(),));db.commit()
        start=db.execute("SELECT value FROM meta WHERE key='created'").fetchone()[0]
        while True:
            row=db.execute("SELECT value FROM meta WHERE key='offset'").fetchone()
            try:
                updates=api(config,"getUpdates",{"offset":int(row[0]) if row else 0,"timeout":15,"allowed_updates":["message","callback_query"]})
                for update in updates:
                    try:
                        handle_update(update,config,minimum_date=start)
                    except Exception:
                        with db:db.execute("INSERT OR REPLACE INTO meta VALUES('last_control_error',?)",(time.time(),))
                    finally:
                        with db:db.execute("INSERT OR REPLACE INTO meta VALUES('offset',?)",(update["update_id"]+1,))
                with db:db.execute("INSERT OR REPLACE INTO meta VALUES('heartbeat',?)",(time.time(),))
            except Exception:
                # Never log API exception URLs or credentials. Preferences remain retained.
                time.sleep(5)


if __name__=="__main__":
    try:main()
    except KeyboardInterrupt:pass
    except Exception:raise SystemExit("Notification controls unavailable; sensitive details suppressed")

