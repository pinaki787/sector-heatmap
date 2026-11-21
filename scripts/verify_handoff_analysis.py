#!/usr/bin/env python3
"""Read-only native Dhan/Motilal Handoff integration verification; no reports or orders."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.handoff_ticket_client import TicketClient

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account",required=True)
    parser.add_argument("--owner",required=True)
    parser.add_argument("--size",action="store_true",help="Verify fresh structural sizing for the first card of each route; never prepare or submit an order.")
    args=parser.parse_args()
    store=WorkspaceStore(ROOT/".private/dashboard-login/registry.sqlite3")
    with store.db() as db:
        row=db.execute("SELECT a.* FROM accounts a JOIN users u ON u.id=a.user_id WHERE a.id=? AND u.username=?",
            (args.account,args.owner)).fetchone()
    if row is None or row["broker"] not in {"DHAN","MOTILAL_OSWAL"}:
        raise PermissionError("Exact owned Dhan or Motilal account required.")
    account=dict(row);client=TicketClient(ROOT,store,account)
    result=dict(broker=account["broker"],orders_submitted=0,reports_published=0,routes=[])
    try:
        for route in ("cash_equity","stock_options"):
            payload=dict(broker=account["broker"],account_id=args.account,mode="intraday",recipient="codex",
                ai_provider="RULES_ONLY",instrument_route=route,handoff_automation_intermediate=True,
                risk_policy=dict(planning_capital=100000,daily_loss_limit=10000,enforce_risk_controls=False,
                    enforce_minimum_reward_to_risk=True,minimum_reward_to_risk=1,stop_basis="price",order_type="LIMIT"))
            report=client.call("analysis",payload)
            if report.get("source",{}).get("broker")!=account["broker"]:
                raise ValueError("Native analysis broker mismatch.")
            sized=0
            if args.size and report.get("cards"):
                first=report["cards"][0]
                sizing=client.call("size",dict(broker=account["broker"],account_id=args.account,
                    analysis_id=report["analysis_id"],card_id=first["card_id"],selection={"method":"structure"},risk_policy=report["risk_policy"]))
                if sizing.get("status")!="ACCEPTED_AND_SIZED" or not sizing.get("active_invalidation"):
                    raise ValueError("Fresh native structural sizing failed.")
                sized=1
            result["routes"].append(dict(route=route,cards=len(report.get("cards",[])),sized=sized,
                exclusions=len(report.get("exclusions",[])),scope=report.get("analysis_scope",report.get("scope",{}))))
        print(json.dumps(result,allow_nan=False))
    finally:
        if client.process and client.process.poll() is None:
            client.process.stdin.close()
            client.process.wait(timeout=15)
if __name__=="__main__":main()
