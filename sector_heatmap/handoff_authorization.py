"""Revocable account-owned schedule grants, independent of browser sessions."""
import json
import time

def save(store,account,user,enabled):
    path=store.folder(account)/"handoff-schedule.sqlite3"
    import sqlite3
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS service_authorization (singleton INTEGER PRIMARY KEY CHECK(singleton=1), body TEXT NOT NULL)")
        body=dict(user_id=user["id"],account_id=account["id"],broker=account["broker"],
                  port=account["port"],enabled=bool(enabled),granted_at=time.time())
        db.execute("INSERT OR REPLACE INTO service_authorization VALUES(1,?)",(json.dumps(body),))

def identity(store,account,folder,user_id):
    import sqlite3
    with sqlite3.connect(folder/"handoff-schedule.sqlite3") as db:
        try:row=db.execute("SELECT body FROM service_authorization WHERE singleton=1").fetchone()
        except sqlite3.OperationalError:row=None
    grant=json.loads(row[0]) if row else {}
    if not grant.get("enabled") or any(grant.get(k)!=v for k,v in
        (("user_id",user_id),("account_id",account["id"]),("broker",account["broker"]),("port",account["port"]))):
        raise PermissionError("Auto authorization is absent or revoked; save the authorized schedule.")
    with store.db() as db:
        row=db.execute("SELECT id,username,admin FROM users WHERE id=?",(user_id,)).fetchone()
        if not row:raise PermissionError("Schedule owner no longer exists.")
        user=dict(row)
        from .section_permissions import FEATURES
        user["features"]=list(FEATURES) if user["admin"] else [r[0] for r in db.execute(
            "SELECT feature FROM user_features WHERE user_id=?",(user_id,))]
    if "handoff" not in user["features"]:raise PermissionError("Schedule permission was revoked.")
    current=store.account(user,account["id"])
    if any(current[k]!=account[k] for k in ("broker","port")):
        raise PermissionError("Broker identity changed; authorize the schedule again.")
    return user
