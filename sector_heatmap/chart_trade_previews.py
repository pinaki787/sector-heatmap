"""Durable, account-bound confirmation of chart order previews.

An adapter is responsible for verified native bracket submission and subsequent
broker reconciliation. No chart/browser price loop submits financial orders.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from .chart_trade_plan import ChartTradePlan, confirm_plan
from .chart_trade_admission import serialized_chart_entry,ChartOrderNotSent


class ChartTradePreviews:
    def __init__(self, path, *, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connection()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS previews (id TEXT PRIMARY KEY, owner TEXT NOT NULL, plan TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL, result TEXT)")
            db.commit()
        os.chmod(self.path, 0o600)

    def connection(self):
        return sqlite3.connect(self.path, timeout=15)

    def prepare(self, owner, plan):
        if not owner or not isinstance(plan, ChartTradePlan):
            raise PermissionError("A signed-in owner and verified chart plan are required.")
        key = "CHART-" + secrets.token_hex(12).upper()
        expires = self.clock() + 120
        with closing(self.connection()) as db:
            db.execute("INSERT INTO previews VALUES (?,?,?,?,?,NULL)",
                       (key, owner, json.dumps(plan.terms(), allow_nan=False), expires, "PREVIEW"))
            db.commit()
        return {"preview_id": key, "status": "PREVIEW_ONLY", "expires_at": expires,
                "plan": plan.terms(), "fingerprint": plan.fingerprint(),
                "confirmation_phrase": "CONFIRM " + key, "order_submitted": False}

    def inspect(self, owner, preview_id):
        with closing(self.connection()) as db:
            row = db.execute("SELECT owner,plan,expires,state,result FROM previews WHERE id=?", (preview_id,)).fetchone()
        if not row or row[0] != owner:
            raise PermissionError("The chart order belongs to a different signed-in owner or is unavailable.")
        return {"preview_id": preview_id, "plan": json.loads(row[1]), "expires_at": row[2],
                "status": row[3], "result": json.loads(row[4]) if row[4] else None}

    @serialized_chart_entry
    def arm(self, owner, preview_id, confirmation, *, mode, adapter, enabled=False):
        if mode != "LIVE" or enabled is not True:
            raise PermissionError("Explicit LIVE confirmation and the broker execution gate are required.")
        if confirmation != "CONFIRM " + str(preview_id):
            raise PermissionError("Confirm the exact current chart order preview.")
        with closing(self.connection()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner,plan,expires,state,result FROM previews WHERE id=?", (preview_id,)).fetchone()
            if not row or row[0] != owner:
                db.rollback()
                raise PermissionError("The chart preview belongs to a different signed-in owner or is unavailable.")
            plan = ChartTradePlan(**json.loads(row[1]))
            if adapter.account_id != plan.account_id or adapter.broker != plan.broker:
                db.rollback()
                raise PermissionError("The execution adapter differs from the reviewed broker account.")
            if row[3] != "PREVIEW":
                db.rollback()
                return json.loads(row[4]) if row[4] else {
                    "preview_id": preview_id, "status": row[3], "retry_allowed": False,
                    "message": "An entry submission is already recorded. Reconcile its broker status."}
            # Adapter refresh resolves the same native master, quote, funds,
            # margin, positions and pending orders without side effects.
            refreshed = adapter.refresh(plan)
            confirm_plan(plan, refreshed, "CONFIRM " + plan.fingerprint(),
                         expires_at=row[2], now=self.clock())
            intent = {"preview_id": preview_id, "account_id": plan.account_id,
                      "broker": plan.broker, "symbol": plan.symbol,
                      "status": "SUBMISSION_UNCERTAIN", "retry_allowed": False,
                      "protection_confirmed": False,
                      "message": "Entry intent recorded; broker acceptance and linked exits remain unconfirmed."}
            db.execute("UPDATE previews SET state=?,result=? WHERE id=?",
                       ("SUBMISSION_UNCERTAIN", json.dumps(intent), preview_id))
            db.commit()  # Never repeat a submission after process/network failure.
        submitted_intent = json.dumps(intent)
        try:
            result = adapter.submit_bracket(refreshed, idempotency_key=preview_id)
        except ChartOrderNotSent:
            with closing(self.connection()) as db:
                db.execute("BEGIN IMMEDIATE")
                current=db.execute("SELECT result FROM previews WHERE id=? AND owner=?",(preview_id,owner)).fetchone()
                latest=json.loads(current[0]) if current and current[0] else intent
                if not latest.get("entry_order_id") and not latest.get("filled_quantity"):
                    latest.update(status="REJECTED",order_submitted=False,protection_confirmed=False,
                                  message="A final pre-submission check rejected this entry. No broker placement was invoked; review a fresh order.")
                    db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=?",
                               ("REJECTED",json.dumps(latest),preview_id,owner))
                db.commit()
            return latest
        except Exception:
            return self.inspect(owner,preview_id)["result"] or intent
        if not isinstance(result, dict):
            return intent
        if result.get("status") == "REJECTED":
            intent.update(status="REJECTED", message="The broker rejected the chart order. No entry fill is confirmed.")
        elif result.get("entry_order_id") and result.get("account_id") == plan.account_id and result.get("symbol") == plan.symbol:
            intent.update(status="BROKER_ACCEPTED", entry_order_id=str(result["entry_order_id"]),
                          message="The broker accepted the entry. Fill and linked-exit registration require reconciliation.")
        else:
            return intent
        with closing(self.connection()) as db:
            db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND state=? AND result=?",
                       (intent["status"], json.dumps(intent), preview_id,"SUBMISSION_UNCERTAIN",submitted_intent))
            db.commit()
        return self.inspect(owner,preview_id)["result"] or intent


    def _unclaimed_condition(self,owner,preview_id):
        with closing(self.connection()) as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='dhan_chart_conditions'").fetchone()
            if not exists:return False
            row=db.execute("SELECT owner,claim_token FROM dhan_chart_conditions WHERE preview_id=?",(preview_id,)).fetchone()
        if not row:return False
        if row[0]!=owner:raise PermissionError("Conditional chart ownership differs from this preview.")
        return row[1] is None

    def reconcile(self, owner, preview_id, adapter):
        record = self.inspect(owner, preview_id)
        if record["status"] == "PREVIEW" or self._unclaimed_condition(owner,preview_id):
            return record
        plan = ChartTradePlan(**record["plan"])
        if adapter.account_id != plan.account_id or adapter.broker != plan.broker:
            raise PermissionError("The execution adapter differs from this chart order.")
        original = record["result"] or {}
        reconcile_record=getattr(adapter,"reconcile_record",None)
        result = (reconcile_record(plan,record=record) if reconcile_record else
                  adapter.reconcile(plan,preview_id=preview_id,entry_order_id=original.get("entry_order_id")))
        if result.get("account_id") != plan.account_id or result.get("symbol") != plan.symbol or result.get("broker") != plan.broker:
            raise PermissionError("Broker reconciliation returned a different account or instrument.")
        merged = dict(original)
        merged.update(result)
        merged.update(preview_id=preview_id,retry_allowed=False)
        # A concurrent submit/reconcile must not be overwritten by an older read.
        with closing(self.connection()) as db:
            db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=? AND state=? AND result IS ?",
                       (merged["status"],json.dumps(merged,allow_nan=False),preview_id,owner,record["status"],
                        json.dumps(original) if record["result"] is not None else None))
            db.commit()
        return self.inspect(owner,preview_id)

    def pending(self,account_id,broker):
        from .chart_trade_ownership import TERMINAL
        with closing(self.connection()) as db:
            rows=db.execute("SELECT id,owner,plan,state FROM previews ORDER BY rowid").fetchall()
        records=[]
        for preview_id,owner,raw,status in rows:
            if status in TERMINAL:continue
            plan=ChartTradePlan(**json.loads(raw))
            if plan.account_id!=account_id or plan.broker!=broker:
                raise PermissionError("Persisted chart order belongs to another account.")
            if not self._unclaimed_condition(owner,preview_id):
                records.append((owner,preview_id))
        return records

    def record_read_failure(self,owner,preview_id):
        record=self.inspect(owner,preview_id)
        from .chart_trade_ownership import TERMINAL
        if record["status"] in TERMINAL or self._unclaimed_condition(owner,preview_id):return record
        original=record["result"] or {}
        result=dict(original,status="BROKER_STATUS_UNAVAILABLE",protection_confirmed=False,retry_allowed=False,
                    read_failed_at=self.clock(),message="Fresh broker status is unavailable. Reconciliation will retry; no order will be resent.")
        with closing(self.connection()) as db:
            db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=? AND state=? AND result IS ?",
                       (result["status"],json.dumps(result),preview_id,owner,record["status"],
                        json.dumps(original) if record["result"] is not None else None))
            db.commit()
        return self.inspect(owner,preview_id)
