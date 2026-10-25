"""Separate personal executions from shared market reports."""
from copy import deepcopy
import math

MARKET_KINDS={"SECTOR_CARD","HANDOFF_CARD","COMBINED_CARD"}

def telegram_destination(config,event,created):
    routes=config.get("telegram_destinations") or {}
    if not routes.get("enabled"):
        return config,None
    primary=config.get("primary_owner_username",config.get("owner_username"))
    if event.get("owner_username")!=primary:
        return None,"Telegram owner mapping unavailable or not primary owner"
    kind=event.get("kind")
    if config.get("combined_reports",{}).get("enabled") and kind in {"SECTOR_CARD","HANDOFF_CARD"}:
        return None,"Included in combined market brief; separate shared post suppressed"
    if kind in MARKET_KINDS:
        route=routes.get("shared_market")
        if not route:
            return config,None
    elif kind=="POSITION_SUMMARY" or not kind and event.get("action") in ("ENTRY","EXIT"):
        route=routes.get("private_trades")
    else:
        return None,"Unsupported event type for Telegram destination"
    if not isinstance(route,dict) or not route.get("enabled"):
        return None,"Telegram destination not enabled"
    chat_id=route.get("chat_id")
    if not isinstance(chat_id,int) or isinstance(chat_id,bool) or chat_id>=0:
        return None,"Verified channel destination required"
    other=routes.get("private_trades" if kind in MARKET_KINDS else "shared_market") or {}
    if chat_id==other.get("chat_id"):
        return None,"Private and shared destinations must differ"
    activated=route.get("activated_at")
    occurred=event.get("time",created) if kind not in MARKET_KINDS else created
    if not isinstance(occurred,(int,float)) or isinstance(occurred,bool) or not math.isfinite(occurred):
        return None,"Event timestamp unavailable"
    if not isinstance(activated,(int,float)) or isinstance(activated,bool) or not math.isfinite(activated) or occurred<activated:
        return None,"Destination activation does not replay older updates"
    result=deepcopy(config)
    result["telegram"]["chat_id"]=chat_id
    return result,None
