"""Validated per-user email destinations; never changes sender authorization."""
import re
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def validate_email(value,allow_empty=False):
    if not isinstance(value,str):
        raise ValueError("Enter one email address.")
    address=value.strip()
    if not address and allow_empty:
        return ""
    if len(address)>254 or address.count("@")!=1 or not address.isascii():
        raise ValueError("Enter one valid email address.")
    local,domain=address.rsplit("@",1)
    if not local or len(local)>64 or local.startswith(".") or local.endswith(".") or ".." in local:
        raise ValueError("Enter one valid email address.")
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_{}|~\-]+",local):
        raise ValueError("Enter one valid email address.")
    labels=domain.split(".")
    if len(labels)<2 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?",label) for label in labels):
        raise ValueError("Enter one valid email address.")
    return local+"@"+domain.lower()


def recipient(config,root=ROOT):
    fallback=validate_email(config["email"]["recipient"])
    username=config.get("owner_username")
    if not username:
        return fallback
    registry=root/".private/dashboard-login/registry.sqlite3"
    if not registry.exists():
        raise ValueError("Notification recipient registry unavailable.")
    try:
        with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_notification_emails'").fetchone()
            if not exists:
                return fallback
            row=db.execute("SELECT n.email FROM user_notification_emails n JOIN users u ON n.user_id=u.id WHERE u.username=?",(username,)).fetchone()
    except sqlite3.Error:
        raise ValueError("Notification recipient registry unavailable.") from None
    return validate_email(row[0]) if row and row[0] else fallback


def subscribers(config,root=ROOT):
    if config.get("email_recipient_mode")!="USER_MASTER_ENABLED":
        return [{"id":"configured","email":validate_email(config["email"]["recipient"]),"enabled_at":0}]
    registry=root/".private/dashboard-login/registry.sqlite3"
    try:
        with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
            pending=bool(config.get("recipient_scope_confirmation_pending")) or config.get("email_recipient_scope")=="OWN_ACCOUNT_ONLY"
            rows=db.execute("SELECT u.id,n.email,n.enabled_at FROM user_notification_emails n JOIN users u ON n.user_id=u.id WHERE n.enabled=1 AND n.email<>'' AND (?=0 OR u.username=?) ORDER BY u.username",
                            (int(pending),config.get("owner_username",""))).fetchall()
    except sqlite3.Error:
        raise ValueError("Notification subscriber registry unavailable.") from None
    # Distinct selected users may share a mailbox: deliver each event only once per address.
    unique={}
    for uid,address,enabled_at in rows:
        address=validate_email(address)
        key=address.casefold()
        if key not in unique or enabled_at<unique[key]["enabled_at"]:
            unique[key]={"id":uid,"email":address,"enabled_at":enabled_at}
    return list(unique.values())

def notification_accounts(config,root=ROOT):
    if config.get("email_recipient_scope")!="OWN_ACCOUNT_ONLY":
        return [{**a,"owner_username":config["owner_username"]} for a in config["accounts"]]
    registry=root/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        rows=db.execute("SELECT a.id,a.broker,u.username FROM accounts a JOIN users u ON a.user_id=u.id LEFT JOIN user_notification_emails n ON n.user_id=u.id WHERE u.username=? OR (n.enabled=1 AND n.email<>'') ORDER BY u.username,a.id",(config["owner_username"],)).fetchall()
    return [{"id":aid,"broker":broker,"owner_username":username} for aid,broker,username in rows]


def publisher_configs(config,root=ROOT):
    groups={}
    for account in notification_accounts(config,root):
        groups.setdefault(account["owner_username"],[]).append(account)
    return [{**config,"owner_username":name,"primary_owner_username":config["owner_username"],"accounts":accounts}
            for name,accounts in groups.items()]
