"""Resolve only a receipt proven to have stopped before the durable submit intent."""
import argparse,json,sqlite3,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sector_heatmap.workspaces import WorkspaceStore,isolated_environment
from sector_heatmap.handoff_schedule import Schedule
from sector_heatmap.config import _atomic_private_write

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--account",required=True);p.add_argument("--owner",required=True);p.add_argument("--resolve-proven",action="store_true");a=p.parse_args()
 store=WorkspaceStore(ROOT/".private/dashboard-login/registry.sqlite3")
 with store.db() as db:r=db.execute("SELECT a.* FROM accounts a JOIN users u ON u.id=a.user_id WHERE a.id=? AND u.username=?",(a.account,a.owner)).fetchone()
 if r is None:raise PermissionError("Exact owned account required.")
 account=dict(r);folder=store.folder(account);path=folder/"handoff-schedule.sqlite3"
 if account["broker"]!="FYERS":raise ValueError("This audit requires the native FYERS adapter.")
 with sqlite3.connect(path) as db:
  if db.execute("SELECT 1 FROM runs WHERE state='RUNNING'").fetchone():raise ValueError("An analysis run is active; do not interrupt it.")
  rows=db.execute("SELECT fingerprint,state,body FROM receipts WHERE state='SUBMITTING'").fetchall()
 if len(rows)!=1:raise ValueError("Exactly one unacknowledged receipt is required.")
 fingerprint,state,body=rows[0];saved=json.loads(body);plan=saved["plan"]
 intent=folder/"handoff-intents"/(fingerprint+".json")
 if intent.exists() or saved.get("result"):raise ValueError("A submit intent/result exists; broker reconciliation is required.")
 # No submit-capable object is created. Both reports must succeed freshly.
 probe="""import json
from sector_heatmap.fyers_execution import _current_client
c=_current_client();p=c.positions();o=c.orderbook()
if p.get("s")!="ok" or o.get("s")!="ok":raise ValueError()
print(json.dumps(dict(positions=p["netPositions"],orders=o["orderBook"])))
"""
 check=subprocess.run([str(ROOT/".venv/bin/python"),"-B","-c",probe],cwd=folder/"source",env=isolated_environment(account,folder,store.path,8079),capture_output=True,text=True,timeout=65,check=True)
 evidence=json.loads(check.stdout)
 if any(r.get("symbol")==plan["symbol"] for r in evidence["orders"]):raise ValueError("A matching native broker order exists; retain the hold.")
 if any(r.get("symbol")==plan["symbol"] and float(r.get("netQty") or 0) for r in evidence["positions"]):raise ValueError("Matching broker exposure exists; retain the hold.")
 audit=dict(account_id=a.account,owner=a.owner,fingerprint=fingerprint,symbol=plan["symbol"],verified_at=time.time(),intent_absent=True,matching_broker_orders=0,matching_broker_positions=0,
  basis="Owned adapter persists the intent before its first submit call; no cleanup path removes it. Fresh native reports also exclude a matching order/exposure.",original_error="Submission outcome uncertain; original pre-submit cause was not retained.",orders_submitted=0)
 if not a.resolve_proven:print(json.dumps(dict(proven_unsubmitted=True,resolved=False,symbol=plan["symbol"])));return
 schedule=Schedule(path,a.account,"FYERS",collect=None,exposure=None,recover_interrupted=False)
 with schedule.db() as db:
  if db.execute("SELECT 1 FROM runs WHERE state='RUNNING'").fetchone():raise ValueError("Analysis began; wait for its terminal state.")
 # Temporary Manual mode preserves analysis while the corrected adapter is loaded.
 schedule.configure(dict(mode="MANUAL",live_authorized=False))
 if intent.exists():raise ValueError("Submit boundary changed during audit; retain the hold.")
 _atomic_private_write(folder/"handoff-receipt-audits"/(fingerprint+".json"),json.dumps(audit))
 saved["result"]=dict(status="NOT_SUBMITTED",orders_submitted=0,reason="Proven before durable submit boundary; fresh broker reports contain no matching order or position.",audit="handoff-receipt-audits/"+fingerprint+".json")
 with sqlite3.connect(path) as db:
  db.execute("UPDATE receipts SET state='NOT_SUBMITTED',body=?,updated=? WHERE fingerprint=? AND state='SUBMITTING'",(json.dumps(saved),time.time(),fingerprint))
 with schedule.claims.db() as db:
  db.execute("UPDATE claims SET state='CLOSED' WHERE account=? AND fingerprint=? AND state='UNCERTAIN'",(a.account,fingerprint))
 print(json.dumps(dict(proven_unsubmitted=True,resolved=True,symbol=plan["symbol"],mode="MANUAL",replayed=False,orders_submitted=0)))
if __name__=="__main__":main()
