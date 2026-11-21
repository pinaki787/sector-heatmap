"""Real chart-handler pagination against saved native catalogs; no broker traffic."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace
import json,time,hashlib,sys
from sector_heatmap.motilal_server import handler_factory
root=Path.cwd();folder=root/".private/dashboard-login/accounts/08823c4c2082f03de07634a51e39f9fb/motilal-master"
out=root/".private/chart-order-rollouts/motilal-catalog-coverage-20261119";out.mkdir(exist_ok=True)
saved={p.stem:json.loads(p.read_text())for p in folder.glob("*.json")}
now=time.time();today=datetime.fromtimestamp(now,ZoneInfo("Asia/Kolkata")).date().isoformat()
class SavedMaster:
 def rows(self,exchange,**kwargs):
  if exchange not in saved:raise ValueError("No saved native master")
  return saved[exchange]["rows"]
 def indices(self,exchange):raise ValueError("No saved index master")
service=SimpleNamespace(ready=lambda:None,clock=lambda:now,master=SavedMaster())
guard=SimpleNamespace(store=SimpleNamespace(sidebar_visibility=lambda:{"chart-workspace":True}))
Handler=handler_factory(guard,service)
handler=Handler.__new__(Handler)
handler.identity=lambda:({"admin":True},{"broker":"MOTILAL_OSWAL"})
def page(segment,offset):
 handler.path="/api/chart-workspace/symbols?segment="+segment+"&offset="+str(offset)
 replies=[];handler.send_json=lambda code,value:replies.append((code,value))
 captured=[]
 def observe(frame,event,arg):
  if event=="return" and frame.f_code.co_name=="do_GET" and "ordered" in frame.f_locals:
   captured.extend(dict(row) for row in frame.f_locals["ordered"])
 previous=sys.getprofile();sys.setprofile(observe)
 try:handler.do_GET()
 finally:sys.setprofile(previous)
 handler.last_complete_catalog=captured
 assert len(replies)==1
 code,payload=replies[0];assert code==200,(segment,code)
 return payload
report={"scope":"Saved normalized native master snapshots; actual Motilal chart handler; not current native entitlement or authenticated hosted verification","broker_requests":0,"orders_submitted":0,"segments":{}}
def save(): (out/"saved-membership-boundaries.json").write_text(json.dumps(report,indent=2)+"\n")
for segment,data in sorted(saved.items()):
 rows=data["rows"];eligible=[r for r in rows if not r.get("suspended")and not(r.get("expiry")and r["expiry"]<today)]
 expected={r["symbol"]for r in eligible};start=time.monotonic()
 first=page(segment,0)
 ordered=handler.last_complete_catalog
 ordered_ids=[r["id"]for r in ordered]
 missing=expected-set(ordered_ids);extra=set(ordered_ids)-expected
 assert not missing and not extra and len(ordered_ids)==len(set(ordered_ids))
 assert first["total"]==len(expected)
 offsets=sorted({0,100,len(expected)//2,max(0,len(expected)-100),len(expected)})
 for offset in offsets:
  payload=page(segment,offset)
  assert payload["total"]==len(expected)
  assert payload["symbols"]==ordered[offset:offset+100]
 report["segments"][segment]={"snapshot_observed_at":data["observed_at"],"raw_normalized_rows":len(rows),"eligible_rows":len(expected),"excluded_suspended_or_expired":len(rows)-len(eligible),"complete_handler_catalog_checked":True,"boundary_pages":len(offsets),"missing":len(missing),"extra":len(extra),"duplicates":len(ordered_ids)-len(set(ordered_ids)),"seconds":round(time.monotonic()-start,2)}
 save();print(segment,json.dumps(report["segments"][segment]),flush=True)
expected=set().union(*({r["symbol"]for r in d["rows"]if not r.get("suspended")and not(r.get("expiry")and r["expiry"]<today)}for d in saved.values()))
for offset in [0,len(expected)//2,max(0,len(expected)-100),len(expected)]:
 payload=page("",offset)
 assert payload["total"]==len(expected)
 assert set(r["id"]for r in payload["symbols"])<=expected
 assert {"INDEX_NSE","INDEX_BSE"}<=set(payload["unavailable_segments"])
report.update(status="PASS_SAVED_CATALOG_ONLY",eligible_symbols=len(expected),all_segment_boundary_pages=4,index_catalogs="NOT_AUDITED_NO_SAVED_MASTER",source_sha256=hashlib.sha256(Path("sector_heatmap/motilal_server.py").read_bytes()).hexdigest())
save();print("PASS",len(expected),flush=True)
