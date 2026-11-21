#!/usr/bin/env python3
"""Validate an owned Handoff policy; --activate-live enables already-authorized Auto.

The default is read-only. This never submits a test order or starts a strategy
runner. Use only after the human authorized this specific recurring live policy
and bound their real account session in the hosted schedule controls.
"""
import argparse,json,sqlite3,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.handoff_schedule import Schedule
from sector_heatmap.handoff_ticket_client import TicketClient
from sector_heatmap.config import _atomic_private_write

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account",required=True)
    parser.add_argument("--owner",required=True)
    parser.add_argument("--activate-live",action="store_true")
    args=parser.parse_args()
    store=WorkspaceStore(ROOT/".private/dashboard-login/registry.sqlite3")
    with store.db() as db:
        row=db.execute("SELECT a.* FROM accounts a JOIN users u ON u.id=a.user_id WHERE a.id=? AND u.username=?",
            (args.account,args.owner)).fetchone()
    if row is None:raise PermissionError("Exact owned account is required.")
    account=dict(row);folder=store.folder(account)
    if account["broker"] not in {"FYERS","DHAN"} or not account["live_enabled"]:
        raise ValueError("Native protected Live integration is unavailable.")
    with store.db() as db:
        others=[dict(r) for r in db.execute("SELECT * FROM accounts WHERE user_id=? AND id<>?",(account["user_id"],account["id"]))]
    for other in others:
        other_path=store.folder(other)/"handoff-schedule.sqlite3"
        if other_path.exists():
            with sqlite3.connect(other_path) as db:
                row=db.execute("SELECT body FROM policy WHERE id=1").fetchone()
            if row and json.loads(row[0]).get("enabled"):
                raise ValueError("Another owned broker already has an enabled shared-pool schedule.")
    path=folder/"handoff-schedule.sqlite3"
    with sqlite3.connect(path) as db:
        if db.execute("SELECT 1 FROM runs WHERE state='RUNNING'").fetchone():
            raise ValueError("Wait for the current analysis run; no interruption.")
        policy=json.loads(db.execute("SELECT body FROM policy WHERE id=1").fetchone()[0])
    if not policy.get("enabled") or policy.get("entries_halted") or policy.get("daily_loss_limit")!=10000 or policy.get("capital")!=100000:
        raise ValueError("The enabled shared-lakh policy and Rs10000 cutoff must be intact.")
    result=subprocess.run([str(ROOT/".venv/bin/python"),"-B",str(ROOT/"scripts/verify_handoff_automation.py"),"--account",args.account],
        text=True,capture_output=True,timeout=90,check=True)
    evidence=json.loads(result.stdout)
    if not evidence["positions_verified"] or not evidence["orders_verified"] or evidence["daily_loss"]>=10000 or evidence["live_submission_enabled"] is not True:
        raise ValueError("Fresh account evidence or daily-loss gate blocks activation.")
    tickets=TicketClient(ROOT,store,account)
    try:
        schedule=Schedule(path,args.account,account["broker"],collect=None,exposure=None,
            execute=True,auto_ready=lambda:tickets.call("capabilities",{}).get("live_submission_enabled") is True,
            recover_interrupted=False)
        if schedule.claims.unsettled(args.account):
            raise ValueError("Unsettled Handoff receipt requires reconciliation.")
        output=dict(ready=True,activated=False,broker=account["broker"],capital=100000,daily_loss_limit=10000,
            used_capital=evidence["used_capital"],orders_submitted=0)
        if args.activate_live:
            # Recheck the slot before changing the policy; never mark it interrupted.
            with schedule.db() as db:
                if db.execute("SELECT 1 FROM runs WHERE state='RUNNING'").fetchone():
                    raise ValueError("Analysis began during verification; retry after it completes.")
            p=schedule.configure(dict(enabled=True,mode="AUTO",live_authorized=True))
            _atomic_private_write(folder/"handoff-live-activation.json",json.dumps(dict(owner=args.owner,
                account_id=args.account,created=time.time(),policy_revision=p["revision"],mode="AUTO",
                capital=100000,daily_loss_limit=10000,orders_submitted_by_activation=0)))
            output.update(activated=True,mode=p["mode"])
        print(json.dumps(output))
    finally:
        if tickets.process and tickets.process.poll() is None:
            tickets.process.stdin.close()
            tickets.process.wait(timeout=10)
if __name__=="__main__":main()
