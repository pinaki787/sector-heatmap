"""Read-only catalog membership audit against the current broker master."""
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
from sector_heatmap.dhan_execution import DhanMaster
from sector_heatmap.chart_workspace import search_dhan_chart_symbols

now=datetime.now(ZoneInfo("Asia/Kolkata"))
master=DhanMaster()
raw=master.load(now)
# Dhan v2 published Exchange Segment annexure; unknown segments stay explicit.
mapping={("NSE","E"):"NSE_EQ",("BSE","E"):"BSE_EQ",
 ("NSE","I"):"IDX_I",("BSE","I"):"IDX_I",
 ("NSE","D"):"NSE_FNO",("BSE","D"):"BSE_FNO",
 ("NSE","C"):"NSE_CURRENCY",("BSE","C"):"BSE_CURRENCY",
 ("MCX","M"):"MCX_COMM"}
expected=set();excluded=Counter();counts=Counter()
for row in raw:
 exchange=row.get("SEM_EXM_EXCH_ID")
 segment=row.get("SEM_SEGMENT")
 native=mapping.get((exchange,segment))
 if native is None:
  excluded[f"unmapped:{exchange}:{segment}"]+=1;continue
 identity=row.get("SEM_SMST_SECURITY_ID","")
 if not identity.isdecimal() or not row.get("SEM_TRADING_SYMBOL"):
  excluded["missing_identity"]+=1;continue
 if segment in {"D","C","M"} and row.get("SEM_EXPIRY_DATE","")[:10]<now.date().isoformat():
  excluded["expired_derivative"]+=1;continue
 expected.add(native+":"+identity)
 counts[native]+=1
result=search_dhan_chart_symbols(master,"",now,limit=len(raw)+1)
actual={r["id"] for r in result["symbols"]}
missing=sorted(expected-actual);extra=sorted(actual-expected)
report={"status":"PASS" if not missing and not extra and len(actual)==result["total"] else "FAIL",
 "scope":"Complete membership in the chart search function for all current rows in the nine published exchange/segment mappings; eight unique API segments.",
 "as_of":now.isoformat(),"raw_rows":len(raw),"unique_expected":len(expected),"unique_actual":len(actual),
 "segment_row_counts":dict(counts),"excluded_rows":dict(excluded),"missing":missing[:20],"extra":extra[:20],
 "limitations":["Does not establish broker OHLC or live entitlement for every symbol.","Unmapped NSE commodity and G segments remain excluded; their native chart data mapping is unverified.","Hosted pagination and user permission matrices are separate requirements."]}
out=Path(".private/chart-order-rollouts/dhan-catalog-coverage-20261119/audit.json")
out.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
if report["status"]!="PASS":raise SystemExit(1)
