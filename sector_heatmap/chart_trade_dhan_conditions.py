"""Durable conditional-entry state in the private chart preview database.

No network calls. A claimed entry is never automatically claimed again after a
crash; its native outcome must be reconciled by stable correlation identity.
"""
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import secrets
import sqlite3
import time
from decimal import Decimal
from .chart_trade_plan import ChartTradePlan
from .chart_trade_dhan_trigger import DhanTriggerState, arm_trigger, evaluate_trigger, _tick


class DhanChartConditions:
    def __init__(self,path,*,clock=time.time):
        self.path=Path(path);self.clock=clock
        if not self.path.is_file() or self.path.resolve()!=self.path.absolute():
            raise ValueError("An existing private chart preview database is required.")
        with closing(self.connection()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS dhan_chart_conditions (
                preview_id TEXT PRIMARY KEY, owner TEXT NOT NULL, plan TEXT NOT NULL,
                snapshot TEXT NOT NULL, claim_token TEXT, version INTEGER NOT NULL DEFAULT 0)""")
            db.commit()

    def connection(self):
        return sqlite3.connect(self.path,timeout=15)

    def _row(self,db,owner,preview_id):
        row=db.execute("SELECT owner,plan,snapshot,claim_token,version FROM dhan_chart_conditions WHERE preview_id=?",
                       (preview_id,)).fetchone()
        if not row or row[0]!=owner:
            raise PermissionError("The conditional chart entry belongs to another owner or is unavailable.")
        return row

    def inspect(self,owner,preview_id):
        with closing(self.connection()) as db:row=self._row(db,owner,preview_id)
        return dict(preview_id=preview_id,plan=json.loads(row[1]),state=json.loads(row[2]),
                    claimed=row[3] is not None,version=row[4])

    @staticmethod
    def _result(preview_id,plan,state):
        return dict(preview_id=preview_id,account_id=plan.account_id,broker="DHAN",symbol=plan.symbol,
            status=state.status,retry_allowed=False,protection_confirmed=False,
            message=state.reason or "Waiting for a fresh broker tick to reach the marked entry.")

    def arm(self,owner,preview_id,confirmation,*,tick,expires_at,mode,enabled=False):
        if mode!="LIVE" or enabled is not True or confirmation!="CONFIRM "+preview_id:
            raise PermissionError("Explicit confirmation of this enabled LIVE conditional entry is required.")
        with closing(self.connection()) as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT owner,plan,expires,state FROM previews WHERE id=?",(preview_id,)).fetchone()
            if not row or row[0]!=owner:raise PermissionError("The chart preview belongs to a different owner.")
            existing=db.execute("SELECT owner FROM dhan_chart_conditions WHERE preview_id=?",(preview_id,)).fetchone()
            if existing:
                db.rollback();return self.inspect(owner,preview_id)
            if row[3]!="PREVIEW" or self.clock()>=row[2]:
                raise ValueError("Prepare a fresh, unconsumed conditional chart preview.")
            plan=ChartTradePlan(**json.loads(row[1]))
            state=arm_trigger(plan,tick,now=self.clock(),expires_at=expires_at)
            raw=json.dumps(state.terms(),allow_nan=False)
            db.execute("INSERT INTO dhan_chart_conditions(preview_id,owner,plan,snapshot) VALUES(?,?,?,?)",
                       (preview_id,owner,row[1],raw))
            db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=?",
                (state.status,json.dumps(self._result(preview_id,plan,state)),preview_id,owner))
            db.commit()
        return self.inspect(owner,preview_id)

    def observe(self,owner,preview_id,tick):
        with closing(self.connection()) as db:
            db.execute("BEGIN IMMEDIATE")
            row=self._row(db,owner,preview_id)
            if row[3] is not None:
                db.rollback();return self.inspect(owner,preview_id)
            plan=ChartTradePlan(**json.loads(row[1]))
            state=DhanTriggerState(**json.loads(row[2]))
            updated=evaluate_trigger(state,plan,tick,now=self.clock())
            if updated!=state:
                db.execute("UPDATE dhan_chart_conditions SET snapshot=?,version=version+1 WHERE preview_id=?",
                    (json.dumps(updated.terms(),allow_nan=False),preview_id))
                db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=?",
                    (updated.status,json.dumps(self._result(preview_id,plan,updated)),preview_id,owner))
            db.commit()
        return self.inspect(owner,preview_id)

    def claim(self,owner,preview_id,*,tick):
        """Return a one-time internal token only after durable native intent."""
        with closing(self.connection()) as db:
            db.execute("BEGIN IMMEDIATE")
            row=self._row(db,owner,preview_id)
            if row[3] is not None:
                db.rollback();return None
            plan=ChartTradePlan(**json.loads(row[1]))
            state=DhanTriggerState(**json.loads(row[2]))
            if state.status!="TRIGGERED":
                db.rollback();return None
            now=self.clock()
            def invalidate(message,status="REVIEW_REQUIRED"):
                updated=replace(state,status=status,reason=message)
                db.execute("UPDATE dhan_chart_conditions SET snapshot=?,version=version+1 WHERE preview_id=?",
                    (json.dumps(updated.terms(),allow_nan=False),preview_id))
                db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=?",
                    (status,json.dumps(self._result(preview_id,plan,updated)),preview_id,owner))
                db.commit()
                raise ValueError(message)
            if now>=state.expires_at:
                invalidate("The conditional entry expired before its native claim.","EXPIRED")
            try:price,provider,received=_tick(plan,tick,now)
            except (ValueError,TypeError) as error:invalidate(str(error))
            valid=(now<state.expires_at and now-state.received_at<=2
                and tick["stream_id"]==state.stream_id and tick["connection_revision"]==state.connection_revision
                and tick["sequence"]>=state.sequence and provider>=state.provider_at and received>=state.received_at
                and (price>=Decimal(plan.entry) if plan.side=="BUY" else price<=Decimal(plan.entry)))
            if not valid:
                invalidate("The triggered entry needs a fresh review; no submission was claimed.")
            token=secrets.token_hex(16)
            result=self._result(preview_id,plan,state)
            result.update(status="SUBMISSION_UNCERTAIN",message="Conditional entry intent recorded; native acceptance is unconfirmed.",
                conditional_trigger=dict(fingerprint=plan.fingerprint(),stream_id=state.stream_id,
                    connection_revision=state.connection_revision,sequence=tick["sequence"],
                    provider_at=provider,received_at=received,price=str(price),claimed_at=now,claim_token=token))
            db.execute("UPDATE dhan_chart_conditions SET claim_token=?,version=version+1 WHERE preview_id=?",(token,preview_id))
            db.execute("UPDATE previews SET state='SUBMISSION_UNCERTAIN',result=? WHERE id=? AND owner=?",
                (json.dumps(result,allow_nan=False),preview_id,owner))
            db.commit()
        return dict(preview_id=preview_id,claim_token=token,plan=plan.terms(),trigger=result["conditional_trigger"])

    def cancel_unclaimed(self,owner,preview_id):
        """Owner-authorized local cancellation only; never cancel a native order."""
        with closing(self.connection()) as db:
            db.execute("BEGIN IMMEDIATE")
            row=self._row(db,owner,preview_id)
            if row[3] is not None:raise ValueError("This entry has a native submission claim; reconcile broker state.")
            plan=ChartTradePlan(**json.loads(row[1]));state=json.loads(row[2])
            state.update(status="CANCELLED",reason="Conditional chart entry cancelled before any native submission claim.")
            db.execute("UPDATE dhan_chart_conditions SET snapshot=?,version=version+1 WHERE preview_id=?",(json.dumps(state),preview_id))
            result=self._result(preview_id,plan,DhanTriggerState(**state))
            result["order_submitted"]=False
            db.execute("UPDATE previews SET state='CANCELLED',result=? WHERE id=? AND owner=?",
                       (json.dumps(result),preview_id,owner))
            db.commit()
        return self.inspect(owner,preview_id)

    def pending(self,account_id):
        with closing(self.connection()) as db:
            rows=db.execute("SELECT preview_id,owner,plan,snapshot FROM dhan_chart_conditions WHERE claim_token IS NULL").fetchall()
        result=[]
        for key,owner,raw,snapshot in rows:
            plan=ChartTradePlan(**json.loads(raw))
            if plan.account_id!=account_id or plan.broker!="DHAN":
                raise PermissionError("Conditional chart state belongs to another account.")
            if json.loads(snapshot).get("status") in {"WAITING_FOR_TRIGGER","TRIGGERED"}:
                result.append((owner,key,plan))
        return result

    def require_review(self,owner,preview_id,reason):
        with closing(self.connection()) as db:
            db.execute("BEGIN IMMEDIATE")
            row=self._row(db,owner,preview_id)
            if row[3] is not None:
                db.rollback();return self.inspect(owner,preview_id)
            plan=ChartTradePlan(**json.loads(row[1]));state=DhanTriggerState(**json.loads(row[2]))
            if state.status not in {"WAITING_FOR_TRIGGER","TRIGGERED"}:
                db.rollback();return self.inspect(owner,preview_id)
            updated=replace(state,status="REVIEW_REQUIRED",reason=reason)
            db.execute("UPDATE dhan_chart_conditions SET snapshot=?,version=version+1 WHERE preview_id=?",
                (json.dumps(updated.terms()),preview_id))
            db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=?",
                (updated.status,json.dumps(self._result(preview_id,plan,updated)),preview_id,owner))
            db.commit()
        return self.inspect(owner,preview_id)

    def outcome(self,owner,preview_id,claim_token,result):
        """Persist one claimed response without overwriting newer native proof."""
        with closing(self.connection()) as db:
            db.execute("BEGIN IMMEDIATE")
            row=self._row(db,owner,preview_id)
            if not row[3] or not secrets.compare_digest(row[3],str(claim_token)):
                raise PermissionError("The Dhan conditional submission claim differs.")
            plan=ChartTradePlan(**json.loads(row[1]))
            current=db.execute("SELECT state,result FROM previews WHERE id=? AND owner=?",(preview_id,owner)).fetchone()
            if not current:raise ValueError("The owned chart intent is unavailable.")
            latest=json.loads(current[1] or "{}")
            if latest.get("entry_order_id") or latest.get("filled_quantity") or current[0] in {"CLOSED","CANCELLED","REJECTED","EXPIRED"}:
                db.rollback();return latest
            if not isinstance(result,dict):result={}
            updated=dict(latest)
            if result.get("status")=="REJECTED":
                updated.update(status="REJECTED",protection_confirmed=False,
                    message="Dhan chart entry rejected. No entry fill is confirmed.")
                if result.get("order_submitted") is False:updated["order_submitted"]=False
            elif result.get("entry_order_id"):
                if result.get("account_id")!=plan.account_id or result.get("symbol")!=plan.symbol or result.get("broker")!="DHAN":
                    raise PermissionError("Dhan conditional receipt belongs to another account or contract.")
                updated.update(entry_order_id=str(result["entry_order_id"]),protection_confirmed=False)
                # A status read may have run while the placement was in flight.
                # Preserve its status; retain the newly returned stable order ID.
                if current[0]=="SUBMISSION_UNCERTAIN":
                    updated.update(status="BROKER_ACCEPTED",message="Dhan accepted the conditional entry. Entry fills and exits require native reconciliation.")
            else:
                db.rollback();return latest
            updated["retry_allowed"]=False
            db.execute("UPDATE previews SET state=?,result=? WHERE id=? AND owner=?",
                (updated["status"],json.dumps(updated,allow_nan=False),preview_id,owner))
            db.commit()
        return updated
