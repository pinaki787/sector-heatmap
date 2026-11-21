"""Read-only admission guard for durable chart-order ownership."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing

TERMINAL = {"PREVIEW","CLOSED","CANCELLED","REJECTED","EXPIRED"}


def assert_no_chart_entry_conflict(path, account_id, broker, *, client_order_id=None):
    """Block new entries, including unknown intents; never block exits/cancels."""
    path=Path(path)
    if not path.exists():
        return
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=5)) as db:
            rows=db.execute("SELECT id,plan,state FROM previews").fetchall()
        for preview_id,raw,status in rows:
            if status in TERMINAL:
                continue
            plan=json.loads(raw)
            if plan.get("account_id")!=account_id or plan.get("broker")!=broker:
                raise ValueError("Chart order ownership differs from this broker workspace.")
            expected="CH"+hashlib.sha256(str(preview_id).encode()).hexdigest()[:24]
            if client_order_id == expected:
                continue  # This is the exact chart intent, persisted before its native request.
            raise ValueError("A pending or unreconciled chart order owns this broker account. Reconcile it before another entry.")
    except (sqlite3.Error, OSError, json.JSONDecodeError,TypeError) as error:
        raise ValueError("Chart order ownership is unavailable; new entries are blocked until reconciliation.") from error


def assert_workspace_chart_entry_allowed(broker, *, client_order_id=None):
    account_id=os.environ.get("SECTOR_PULSE_WORKSPACE_ID")
    registry=os.environ.get("SECTOR_PULSE_WORKSPACE_REGISTRY")
    if not account_id or not registry:
        return  # Main/non-workspace services cannot create these private chart orders.
    # Account ids are registry-generated hex, never a client-supplied path.
    if len(account_id)!=32 or any(c not in "0123456789abcdef" for c in account_id):
        raise ValueError("The private chart account binding is invalid.")
    path=Path(registry).parent/"accounts"/account_id/"chart-trading.sqlite3"
    assert_no_chart_entry_conflict(path,account_id,broker,client_order_id=client_order_id)
