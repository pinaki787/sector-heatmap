"""Fresh, account-isolated Handoff reporting. No ticket preparation or submission."""
import argparse,json,os,sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime
from .market_calendar import IST
from .workspaces import private_write

def run(request_path,output_path):
 request=json.loads(Path(request_path).read_text())
 source=Path(__file__).resolve().parents[1];folder=source.parent
 if request.get("broker")!="FYERS" or folder.name!=request.get("account_id") or source.name!="source" or os.environ.get("SECTOR_PULSE_WORKSPACE_ID")!=folder.name:
  raise PermissionError("Owned FYERS report workspace required.")
 registry=Path(os.environ["SECTOR_PULSE_WORKSPACE_REGISTRY"]).resolve()
 with closing(sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True)) as db:
  db.row_factory=sqlite3.Row
  row=db.execute("SELECT * FROM accounts WHERE id=? AND broker='FYERS'",(folder.name,)).fetchone()
 if row is None:raise PermissionError("Owned FYERS report account unavailable.")
 account=dict(row)
 from .handoff_fyers_analysis import Provider
 from .handoff_analysis import opportunities
 state_dir=source/".private"/"combined-handoff"
 state_dir.mkdir(mode=0o700,exist_ok=True)
 provider=Provider(account,folder,state_dir=state_dir);reports=[]
 for route in ("cash_equity","stock_options"):
  payload=dict(recipient="codex",instrument_route=route,mode="intraday",handoff_schedule_mode="MANUAL",
   risk_policy=dict(planning_capital=100000,daily_loss_limit=10000,enforce_risk_controls=False,
   enforce_minimum_reward_to_risk=True,minimum_reward_to_risk=1,stop_basis="price",order_type="LIMIT"))
  reports.append(opportunities(payload,provider,{}))
 report=dict(schema="sector-pulse-auto-analysis/v1",generated_at=datetime.now(IST).isoformat(),source=dict(broker="FYERS",mode="intraday"),
  cards=[c for r in reports for c in r.get("cards",[])],candidates=[c for r in reports for c in r.get("candidates",[])],
  exclusions=[e for r in reports for e in r.get("exclusions",[])],analysis_scopes=[dict(route=r.get("instrument_route"),scope=r.get("scope")) for r in reports],
  decision_support_only=True,order_authority="NONE")
 incomplete=any(((r.get("scope") or {}).get("screener") or {}).get("status") not in (None,"COMPLETED","DISABLED") for r in reports)
 if incomplete:report["scheduled_status"]=dict(code="PARTIAL_ANALYSIS",message="Partial analysis: Screener coverage incomplete; available findings retained.")
 private_write(output_path,json.dumps(report,allow_nan=False))
def main():
 p=argparse.ArgumentParser();p.add_argument("--request",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 try:run(a.request,a.output)
 except Exception as error:
  import logging
  logging.getLogger(__name__).exception("Fresh Handoff reporting worker failed")
  private_write(a.output,json.dumps(dict(cards=[],source=dict(broker="FYERS"),generated_at=datetime.now(IST).isoformat(),
   scheduled_status=dict(code="DATA_UNAVAILABLE",message="Fresh Handoff analysis failed ("+type(error).__name__+"); check the account connection and report diagnostics."),decision_support_only=True,order_authority="NONE")))
if __name__=="__main__":main()
