"""Bounded read-only profile/master/history probe; never constructs an order."""
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import json,sqlite3,re,requests,argparse
from collections import Counter
from sector_heatmap.dhan_execution import DhanClient,DhanMaster
from sector_heatmap.chart_workspace import require_dhan_data
parser=argparse.ArgumentParser()
parser.add_argument("--account-id",default="fd46b26f73022af571be11b1027c5291")
parser.add_argument("--evidence-name",default="dhan-nse-commodity-native-20261119")
args=parser.parse_args()
assert re.fullmatch(r"[a-f0-9]{32}",args.account_id),"Invalid registered workspace ID"
assert re.fullmatch(r"[a-z0-9-]+",args.evidence_name),"Invalid evidence directory name"
root=Path.cwd();account_id=args.account_id
out=root/".private/chart-order-rollouts"/args.evidence_name;out.mkdir(exist_ok=True)
report={"read_only":True,"orders_submitted":0,"account_binding_verified":False,"probes":[]}
def save(): (out/"result.json").write_text(json.dumps(report,indent=2)+"\n")
try:
 registry=root/".private/dashboard-login/registry.sqlite3"
 with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True,timeout=3)as db:
  row=db.execute("SELECT broker,account_ref FROM accounts WHERE id=?",(account_id,)).fetchone()
 values=json.loads((registry.parent/"accounts"/account_id/"credentials.json").read_text())
 assert row and row[0]=="DHAN" and row[1]==values.get("DHAN_CLIENT_ID")
 report["registered_binding_verified"]=True
 original_request=requests.request
 def observed_request(method,url,**kwargs):
  response=original_request(method,url,**kwargs)
  if method=="GET"and url.endswith("/profile"):
   report["native_profile_http_status"]=response.status_code
   try:
    body=response.json()
    message=body.get("errorMessage","")if isinstance(body,dict)else""
    if isinstance(message,str)and message:
     message=message.replace(values.get("DHAN_CLIENT_ID",""),"[client]").replace(values.get("DHAN_ACCESS_TOKEN",""),"[token]")
     message=re.sub(r"\b\d{5,}\b","[number]",message)
     report["native_error_message_redacted"]=message[:300]
    for field in ("errorCode","errorType"):
     value=body.get(field)if isinstance(body,dict)else None
     if value is not None and re.fullmatch(r"[A-Za-z0-9_-]{1,32}",str(value)):report["native_"+field]=str(value)
   except ValueError:pass
  return response
 requests.request=observed_request
 client=DhanClient(values);require_dhan_data(client);report["account_binding_verified"]=True;report["data_plan"]="Active";save()
 print("Selected account profile and active data plan verified.",flush=True)
 now=datetime.now(ZoneInfo("Asia/Kolkata"));master=DhanMaster();raw=master.load(now)
 rows=[r for r in raw if r.get("SEM_EXM_EXCH_ID")=="NSE" and r.get("SEM_SEGMENT")=="M" and r.get("SEM_EXPIRY_DATE","")[:10]>=now.date().isoformat()]
 report["commodity_instrument_names"]=dict(Counter(r.get("SEM_INSTRUMENT_NAME","")for r in rows))
 report["sample_public_master_rows"]=rows[:2]
 futures=sorted([r for r in rows if r.get("SEM_INSTRUMENT_NAME")=="FUTCOM"],key=lambda r:(r.get("SEM_EXPIRY_DATE",""),r.get("SEM_TRADING_SYMBOL","")))
 preferred=[r for r in futures if any(k in r.get("SEM_TRADING_SYMBOL","").upper() for k in ("GOLD","SILVER"))]
 targets=[];underlyings=set()
 candidates=preferred+futures if futures else sorted(rows,key=lambda r:(r.get("SEM_EXPIRY_DATE",""),r.get("SEM_TRADING_SYMBOL","")))
 for r in candidates:
  name=r.get("SEM_UNDERLYING_SYMBOL")or r.get("SEM_TRADING_SYMBOL","").split("-")[0]
  if name in underlyings:continue
  underlyings.add(name);targets.append(r)
  if len(targets)==2:break
 report.update(as_of=now.isoformat(),master_rows=len(raw),current_nse_commodity_rows=len(rows),current_nse_commodity_futures=len(futures))
 save();print("Fresh commodity master selected "+str(len(targets))+" distinct commodity contracts.",flush=True)
 for r in targets:
  item={"symbol":r["SEM_TRADING_SYMBOL"],"security_id":r["SEM_SMST_SECURITY_ID"],"instrument":r["SEM_INSTRUMENT_NAME"],"segment":"NSE_COMM"}
  try:
   response=client.request("POST","/charts/intraday",{"securityId":item["security_id"],"exchangeSegment":"NSE_COMM","instrument":item["instrument"],"interval":"30","oi":False,"fromDate":(now-timedelta(days=5)).strftime("%Y-%m-%d 00:00:00"),"toDate":(now+timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")})
   payload=response.get("data",response)if isinstance(response,dict)else{}
   timestamps=payload.get("timestamp",[])if isinstance(payload,dict)else[]
   item.update(status="DATA"if timestamps else"EMPTY",candles=len(timestamps))
  except Exception as error:item.update(status="REJECTED_OR_UNAVAILABLE",error_type=type(error).__name__,reauthentication_required=bool(getattr(error,"reauthentication_required",False)))
  report["probes"].append(item);save();print(json.dumps(item),flush=True)
 report["status"]="NATIVE_DATA_AVAILABLE"if any(p.get("candles",0)>0 for p in report["probes"])else"MAPPING_NOT_PROVEN"
except Exception as error:
 report.update(status="UNVERIFIED",error_type=type(error).__name__,reauthentication_required=bool(getattr(error,"reauthentication_required",False)))
finally:save()
print(json.dumps({k:v for k,v in report.items()if k!="probes"}))
