"""Read-only native master and real chart-handler membership audit. No login renewal or orders."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace
import json,sqlite3,time,hashlib,sys
from sector_heatmap.motilal_api import Client,MotilalError
from sector_heatmap.motilal_master import Master,contract
from sector_heatmap.motilal_server import handler_factory
root=Path.cwd();aid="08823c4c2082f03de07634a51e39f9fb"
folder=root/".private/dashboard-login/accounts"/aid
out=root/".private/chart-order-rollouts/motilal-catalog-coverage-20261119";out.mkdir(exist_ok=True)
report={"read_only":True,"orders_submitted":0,"status":"UNVERIFIED","segments":{}}
def save(): (out/"audit.json").write_text(json.dumps(report,indent=2)+"\n")
try:
 with sqlite3.connect((root/".private/dashboard-login/registry.sqlite3").as_uri()+"?mode=ro",uri=True)as db:
  row=db.execute("select broker,account_ref from accounts where id=?",(aid,)).fetchone()
 values=json.loads((folder/"credentials.json").read_text())
 assert row and row[0]=="MOTILAL_OSWAL"and row[1]==str(values.get("MO_CLIENT_ID","")).upper()
 assert not (folder/"disconnected.json").exists()
 values.update(json.loads((folder/"motilal-session.json").read_text()))
 client=Client(values);client.profile()
 report["native_profile_binding_verified"]=True;save();print("Native account profile verified.",flush=True)
 now=time.time();today=datetime.fromtimestamp(now,ZoneInfo("Asia/Kolkata")).date().isoformat()
 native={}
 for segment in ("INDEX_NSE","INDEX_BSE","NSE","BSE","NSEFO","BSEFO","NSECD","MCX","NCDEX"):
  try:
   operation="index_master"if segment.startswith("INDEX_")else"instruments"
   reply=client.request(operation,{"exchangename":segment.removeprefix("INDEX_")})
   rows=reply.get("data")
   if not isinstance(rows,list):raise ValueError("Native master is not a list")
   (out/(segment+"-native.json")).write_text(json.dumps(rows))
   if segment.startswith("INDEX_"):
    master=Master(out/"isolated-master",SimpleNamespace(request=lambda *a,**k:reply))
    normalized=master.indices(segment[6:])
   else:
    normalized=[];invalid=0
    for r in rows:
     try:normalized.append(contract(r,segment))
     except (ValueError,TypeError,KeyError):invalid+=1
   native[segment]=normalized
   report["segments"][segment]={"raw_rows":len(rows),"normalized_rows":len(normalized),"invalid_rows":len(rows)-len(normalized),"current_rows":sum(not r.get("suspended")and not(r.get("expiry")and r["expiry"]<today)for r in normalized)}
  except Exception as error:
   report["segments"][segment]={"error_type":type(error).__name__,"auth_required":bool(getattr(error,"auth_required",False))}
  save();print(segment,json.dumps(report["segments"][segment]),flush=True)
 report["native_master_saved"]=True
except Exception as error:
 report.update(error_type=type(error).__name__,auth_required=bool(getattr(error,"auth_required",False)))
 save();print(json.dumps(report));sys.exit(1)
save()
