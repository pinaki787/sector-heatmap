"""Compare adapter calendar OHLC against independently grouped broker daily rows."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict
import json,math
from sector_heatmap.dhan_execution import DhanClient
from sector_heatmap.chart_workspace import fetch_dhan_history
zone=ZoneInfo("Asia/Kolkata");now=datetime.now(zone)
folder=Path(".private/chart-order-rollouts/dhan-calendar-parity-20261119")
client=DhanClient(json.loads(Path(".private/dashboard-login/accounts/fd46b26f73022af571be11b1027c5291/credentials.json").read_text()))
class Capture:
 def __init__(self):self.raw=None;self.payload=None
 def request(self,method,path,payload):
  assert path=="/charts/historical"
  if self.raw is None:
   self.raw=client.request(method,path,payload);self.payload=payload
  else:assert self.payload==payload
  return self.raw
capture=Capture();checks=[]
for interval in ["1W","1M","12M"]:
 result=fetch_dhan_history(capture,interval,now=now,security_id="1333",exchange_segment="NSE_EQ",instrument="EQUITY")
 actual=result["rows"] if isinstance(result,dict) else result
 raw=capture.raw;groups=defaultdict(list)
 for i,stamp in enumerate(raw["timestamp"]):
  local=datetime.fromtimestamp(stamp,zone);day=local.replace(hour=0,minute=0,second=0,microsecond=0)
  start=day-timedelta(days=day.weekday()) if interval=="1W" else day.replace(day=1) if interval=="1M" else day.replace(month=1,day=1)
  groups[int(start.timestamp())].append([stamp,*[raw[k][i] for k in ["open","high","low","close","volume"]]])
 differences=[]
 for row in actual:
  parts=sorted(groups[row[0]])
  expected=[row[0],parts[0][1],max(p[2] for p in parts),min(p[3] for p in parts),parts[-1][4],sum(p[5] for p in parts)]
  if any(not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-8) for a,b in zip(row,expected)):
   differences.append({"time":row[0],"actual":row,"expected":expected})
 checks.append({"interval":interval,"bars":len(actual),"first":actual[0][0] if actual else None,"last":actual[-1][0] if actual else None,"differences":differences[:3],"status":"PASS" if actual and not differences else "FAIL"})
report={"status":"PASS" if all(x["status"]=="PASS" for x in checks) else "FAIL","as_of":now.isoformat(),"symbol":"NSE_EQ:1333","daily_bars":len(capture.raw["timestamp"]),"checks":checks,"scope":"Returned completed calendar candles versus independent aggregation of the same broker daily OHLCV. Missing native sessions, external feed parity, forming/live updates and hosted worker load not certified."}
(folder/"result.json").write_text(json.dumps(report,indent=2)+"\n")
(folder/"native-daily.json").write_text(json.dumps(capture.raw)+"\n")
print(json.dumps(report,indent=2))
if report["status"]!="PASS":raise SystemExit(1)
