"""Authenticated read-only sector-detail compatibility bridge.

Preserves ranks, attribution and explanations from the selected account's served
snapshot. Adds only completed price/EMA series from that same broker account.
It cannot create, change, adopt or reconcile an order or runner position.
"""
from copy import deepcopy
from datetime import datetime
import json
import math
from pathlib import Path
import subprocess
import sys
from threading import Lock
import time
from urllib.parse import urlencode
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError
from .workspaces import COOKIE,isolated_environment
from .sectors import SECTOR_BY_ID
from .analysis_config import MINIMUM_CANDLES
from .indicators import ema

_CACHE={}
_LOCK=Lock()
_CACHE_SECONDS=300

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise PermissionError("Sector requests cannot follow redirects.")

def _authorized(store,user,account_id,token):
    current=store.session(token)
    if current["id"]!=user["id"]:
        raise PermissionError("The signed-in sector account changed.")
    if not current.get("admin") and "sectors" not in current.get("features",[]):
        raise PermissionError("Sector rotation is not assigned to this user.")
    account=store.account(current,account_id)
    if account["broker"] not in {"FYERS","DHAN","MOTILAL_OSWAL"}:
        raise ValueError("This broker does not provide Sector Rotation.")
    folder=store.folder(account)
    if (folder/"disconnected.json").exists():
        raise PermissionError("Broker account is disconnected.")
    return account,folder

def _get(account,token,path):
    host="127.0.0.1:"+str(account["port"])
    request=Request("http://"+host+path,headers={"Cookie":COOKIE+"="+token,"Accept":"application/json"})
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=8) as response:
            value=json.load(response)
    except HTTPError as error:
        if error.code in {401,403}:raise PermissionError("Sign in to the selected sector account again.") from None
        raise ValueError("The selected account sector snapshot is unavailable.") from None
    except Exception:
        raise ValueError("The selected account sector snapshot is unavailable.") from None
    if not isinstance(value,dict):raise ValueError("Invalid selected account sector response.")
    return value

def chart_series(candles,asof):
    """Align chart samples with the exact snapshot bar; never mix newer bars."""
    if not isinstance(asof,str):raise ValueError("Completed snapshot timestamp required for sector charts.")
    try:target=datetime.fromisoformat(asof).timestamp()
    except (TypeError,ValueError):raise ValueError("Invalid completed snapshot timestamp.") from None
    rows=[row for row in candles if float(row["timestamp"])<=target]
    if not rows or int(rows[-1]["timestamp"])!=int(target):
        raise ValueError("Broker history does not match the selected snapshot bar.")
    if len(rows)<MINIMUM_CANDLES:
        raise ValueError("Insufficient completed candles for the sector EMA chart.")
    closes=[float(row["close"]) for row in rows]
    if not all(math.isfinite(value) and value>0 for value in closes):
        raise ValueError("Invalid broker candle price; chart withheld.")
    values={str(length):ema(closes,length) for length in (20,50,200)}
    return [dict(timestamp=int(rows[index]["timestamp"]),close=round(closes[index],2),
        **{"ema"+key:round(series[index],2) for key,series in values.items()})
        for index in range(max(0,len(rows)-60),len(rows))]

def completed_series(payload):
    """Isolated worker: FYERS completed history only, using its owned config."""
    from .config import load_config
    from .sector_service import SectorAnalysisService
    import os
    if os.environ.get("SECTOR_PULSE_WORKSPACE_BROKER")!="FYERS":
        raise ValueError("This compatibility worker requires its owned FYERS account.")
    sector=SECTOR_BY_ID.get(payload.get("sector"))
    if sector is None:raise ValueError("Unknown sector.")
    token=load_config().get("FYERS_ACCESS_TOKEN","")
    if ":" not in token:raise ValueError("FYERS authentication is required for sector candles.")
    # No refresh/start/save: no ranking calculation, persistent-state write or runner.
    service=SectorAnalysisService(token)
    candles=service._timeframe_candles(sector.symbol)
    # This compatibility chart must reproduce the still-running dashboard's
    # exact historical anchor, including its legacy partial-week projection.
    # The independent Handoff engine uses completed_weekly and never consumes
    # chart series as trading evidence.
    from .indicators import resample_weekly
    candles["weekly"]=resample_weekly(candles.get("daily",[]))
    result={}
    for frame,asof in payload["asof"].items():
        result[frame]=chart_series(candles.get(frame,[]),asof)
    return result

def details(root,store,user,account_id,token,sector_id,mode="intraday"):
    if mode not in {"intraday","swing"}:raise ValueError("Choose Intraday or Swing.")
    if sector_id not in SECTOR_BY_ID:raise ValueError("Unknown sector.")
    account,folder=_authorized(store,user,account_id,token)
    prefix={"FYERS":"/api/","DHAN":"/api/dhan/","MOTILAL_OSWAL":"/api/motilal/"}[account["broker"]]
    query=urlencode(dict(mode=mode,sector=sector_id,account_id=account_id))
    if account["broker"]!="FYERS":
        # Native routes do not suffer the FYERS closure-name collision.
        result=_get(account,token,prefix+"sector-analysis/detail?"+query)
        if not isinstance(result.get("sector"),dict):raise ValueError("Selected native broker sector detail unavailable.")
        return result
    base=_get(account,token,prefix+"sector-analysis?"+query)
    sector=next((row for row in base.get("sectors",[]) if row.get("sector_id")==sector_id),None)
    if sector is None:raise ValueError("This sector has no completed selected-account snapshot.")
    sector=deepcopy(sector)
    asof={frame:state.get("last_updated") for frame,state in sector.get("timeframe_states",{}).items()
        if state.get("last_updated") and state.get("data_quality") not in {"UNAVAILABLE","INSUFFICIENT DATA"}}
    if not asof:raise ValueError("No completed sector bars are available for price charts.")
    key=(account_id,sector_id,json.dumps(asof,sort_keys=True))
    with _LOCK:
        cached=_CACHE.get(key)
        charts=deepcopy(cached[1]) if cached and time.monotonic()-cached[0]<_CACHE_SECONDS else None
    if charts is None:
        _authorized(store,user,account_id,token)
        root=Path(root)
        env=isolated_environment(account,folder,store.path,8079)
        try:
            worker=subprocess.run([str(root/".venv/bin/python"),"-B","-m","sector_heatmap.sector_detail_bridge","worker"],
                input=json.dumps(dict(sector=sector_id,asof=asof)),cwd=folder/"source",env=env,
                capture_output=True,text=True,timeout=23)
        except subprocess.TimeoutExpired:
            raise ValueError("Completed sector candles timed out; retry this sector shortly.") from None
        try:value=json.loads(worker.stdout)
        except (ValueError,TypeError):raise ValueError("Read-only sector candle response unavailable.") from None
        if worker.returncode or value.get("ok") is not True:
            raise ValueError(value.get("error") or "Read-only sector candle request failed.")
        charts=value["series"]
        with _LOCK:
            if len(_CACHE)>128:_CACHE.clear()
            _CACHE[key]=(time.monotonic(),deepcopy(charts))
    _authorized(store,user,account_id,token)
    for frame,series in charts.items():
        sector["timeframe_states"][frame]["series"]=series
    return {key:deepcopy(base.get(key)) for key in ("status","mode","benchmark","updated_at","market_session","weight_source","error")} | dict(
        sector=sector,provider="FYERS",read_only=True,
        detail_source="OWNED_ACCOUNT_SNAPSHOT_AND_MATCHED_COMPLETED_CANDLES")

def main():
    try:
        if sys.argv[1:]!=["worker"]:raise ValueError("Unsupported sector detail operation.")
        payload=json.load(sys.stdin)
        print(json.dumps(dict(ok=True,series=completed_series(payload)),allow_nan=False))
    except Exception as error:
        # Provider errors and diagnostics remain private; credentials never print.
        message=str(error) if type(error) is ValueError else "Read-only sector candles unavailable; retry after the selected broker recovers."
        print(json.dumps(dict(ok=False,error=message)))

if __name__=="__main__":main()
