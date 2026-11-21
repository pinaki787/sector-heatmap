#!/usr/bin/env python3
"""Read-only account verification. Never starts a runner or submits an order."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sector_heatmap.workspaces import WorkspaceStore,isolated_environment

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account",required=True)
    parser.add_argument("--completed-candles",action="store_true")
    args=parser.parse_args()
    store=WorkspaceStore(ROOT/".private/dashboard-login/registry.sqlite3")
    with store.db() as db:
        row=db.execute("SELECT * FROM accounts WHERE id=?",(args.account,)).fetchone()
    if row is None:raise ValueError("Account unavailable.")
    account=dict(row);folder=store.folder(account)
    # The child inherits only this registered account's established environment.
    probe="""import json
from datetime import datetime
from sector_heatmap.handoff_broker_read import read
from sector_heatmap.handoff_execution_worker import Worker
state=read();worker=Worker();caps=worker.call("capabilities",{})
result=dict(positions_verified=state["positions_verified"],orders_verified=state["orders_verified"],
    available_funds=state["available_funds"],used_capital=state["used_capital"],daily_loss=state["daily_loss"],
    exposed_underlyings=state["exposed_underlyings"],live_submission_enabled=caps.get("live_submission_enabled"),
    orders_submitted=0)
"""
    if args.completed_candles:
        probe+="""
from sector_heatmap.handoff_fyers_analysis import Provider
from sector_heatmap.market_calendar import IST
provider=Provider(worker.account,worker.folder)
candles=provider.sectors._timeframe_candles("NSE:NIFTYFMCG-INDEX")
result["completed_candles"]={frame:dict(count=len(rows),last=datetime.fromtimestamp(rows[-1]["timestamp"],IST).isoformat() if rows else None,
    quality=provider.sectors._quality(frame,rows)) for frame,rows in candles.items()}
"""
    probe+='print(json.dumps(result,allow_nan=False))'
    response=subprocess.run([str(ROOT/".venv/bin/python"),"-B","-c",probe],
        cwd=folder/"source",env=isolated_environment(account,folder,store.path,8079),
        text=True,capture_output=True,timeout=240)
    if response.returncode:raise ValueError("Read-only verification failed; no order submitted.")
    print(response.stdout.strip())
if __name__=="__main__":main()
