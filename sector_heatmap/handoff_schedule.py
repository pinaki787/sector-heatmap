"""Account-owned 15-minute Handoff coordinator with injected owned broker adapters.

No implicit activation. Analysis/reporting is independent of Manual/Auto execution.
An interrupted or uncertain submission is retained and never automatically replayed.
"""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from threading import Lock
import time
from .handoff_allocation import allocate, rank, Claims
from .handoff_errors import PreflightRejected
from .market_calendar import market_session, IST, REGULAR_OPEN

DEFAULTS = dict(enabled=False, mode="MANUAL", interval_minutes=15, capital=100000,
                top=5, option_lots=1, broker="FYERS", ai_provider="RULES_ONLY",
                daily_loss_limit=10000, cash_product="INTRADAY", amo=False, entries_halted=False, allow_duplicate_reports=False)

def confirmed_notional(result):
    from .handoff_allocation import amount
    if result.get("entry_fill_price") is None or result.get("protected_quantity") is None:return None
    return amount(result["entry_fill_price"])*amount(result["protected_quantity"])

def verified_daily_loss(state):
    value=state.get("daily_loss")
    if isinstance(value,bool):
        raise ValueError("Broker daily loss evidence invalid; new Live entries withheld.")
    try:loss=float(value)
    except (TypeError,ValueError):
        raise ValueError("Broker daily loss evidence unavailable; new Live entries withheld.") from None
    if not math.isfinite(loss) or loss<0:
        raise ValueError("Broker daily loss evidence invalid; new Live entries withheld.")
    return loss

def slot_at(now):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware schedule time required.")
    now=now.astimezone(IST)
    if market_session(now)["status"]!="OPEN":
        return None
    start=now.replace(hour=REGULAR_OPEN.hour,minute=REGULAR_OPEN.minute,second=0,microsecond=0)
    return (start+timedelta(minutes=15*(int((now-start).total_seconds())//900))).isoformat()

class Schedule:
    def __init__(self,path,account_id,broker,collect,exposure,execute=None,auto_ready=None,clock=time.time,recover_interrupted=True):
        if broker not in {"FYERS","DHAN","MOTILAL_OSWAL"} or not account_id:
            raise ValueError("An owned supported broker account is required.")
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.account_id,self.broker=account_id,broker
        self.collect,self.exposure,self.execute,self.auto_ready=collect,exposure,execute,auto_ready
        self.clock=clock;self.lock=Lock();self.claims=Claims(self.path.with_suffix(".claims.sqlite3"))
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS runs(slot TEXT PRIMARY KEY,state TEXT,created REAL,updated REAL,output TEXT,error TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS reported(fingerprint TEXT PRIMARY KEY,slot TEXT,created REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS deferred_sessions(next_open TEXT PRIMARY KEY,created REAL,revision TEXT,state TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS loss_halts(day TEXT PRIMARY KEY,observed REAL,created REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS receipts(fingerprint TEXT PRIMARY KEY,slot TEXT,state TEXT,body TEXT,updated REAL)")
            if recover_interrupted:
                db.execute("UPDATE runs SET state=?,error=? WHERE state=?",("INTERRUPTED","Process restarted; no slot or order replay.","RUNNING"))
            if not db.execute("SELECT 1 FROM policy").fetchone():
                db.execute("INSERT INTO policy VALUES(1,?)",(json.dumps({**DEFAULTS,"broker":broker}),))
        self.path.chmod(0o600)
    def db(self):
        return sqlite3.connect(self.path,timeout=15)
    def policy(self):
        with self.db() as db:return json.loads(db.execute("SELECT body FROM policy WHERE id=1").fetchone()[0])
    def configure(self,payload):
        allowed={"enabled","mode","capital","ai_provider","cash_product","live_authorized","amo","resume_entries","allow_duplicate_reports"}
        if set(payload)-allowed:
            raise ValueError("Unsupported scheduler setting.")
        p={**self.policy(),**payload,"broker":self.broker}
        if type(p.get("allow_duplicate_reports",False)) is not bool:
            raise ValueError("Allow duplicate reports must be an explicit checkbox value.")
        if "resume_entries" in payload and type(payload["resume_entries"]) is not bool:
            raise ValueError("Explicit entry-resume flag required.")
        resume=p.pop("resume_entries",False)
        if resume:
            if self.claims.unsettled(self.account_id):
                raise ValueError("Broker reconciliation is required before resuming new entries.")
            state=self.exposure(deepcopy(p))
            if state.get("positions_verified") is not True or state.get("orders_verified") is not True:
                raise ValueError("Fresh owned broker evidence required before resuming.")
            p["entries_halted"]=False;p.pop("halt_reason",None)
        if type(p["enabled"]) is not bool or p["mode"] not in {"MANUAL","AUTO"}:
            raise ValueError("Choose Manual or Auto and explicit schedule enablement.")
        if isinstance(p["capital"],bool) or not isinstance(p["capital"],(int,float)) or not 1<=p["capital"]<=100000:
            raise ValueError("The authorized shared pool is at most Rs100000.")
        if p["ai_provider"] not in {"RULES_ONLY","CODEX_CHATGPT"} or p["cash_product"] not in {"INTRADAY","CNC"}:
            raise ValueError("Choose a supported saved analysis path and cash product.")
        if p.get("amo"):
            raise ValueError("Automatic AMO is not enabled on an unverified broker API path. No AMO was sent.")
        if p["mode"]=="AUTO" and payload.get("enabled") is not False:
            if p.get("live_authorized") is not True:
                raise ValueError("Explicit Live automation authorization is required.")
            if not self.execute or not self.auto_ready or self.auto_ready() is not True:
                raise ValueError("Owned broker protected execution integration is not ready.")
        p["revision"]=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
        with self.db() as db:db.execute("UPDATE policy SET body=? WHERE id=1",(json.dumps(p),))
        return p
    def status(self):
        with self.db() as db:
            latest=db.execute("SELECT slot,state,updated,error FROM runs ORDER BY created DESC LIMIT 1").fetchone()
            deferred=db.execute("SELECT next_open,state FROM deferred_sessions ORDER BY created DESC LIMIT 1").fetchone()
        return dict(account_id=self.account_id,broker=self.broker,policy=self.policy(),
                    deferred=dict(zip(("next_open","state"),deferred)) if deferred else None,latest=dict(zip(("slot","state","updated","error"),latest)) if latest else None)
    def loss_halted(self,state,now,limit):
        day=now.astimezone(IST).date().isoformat()
        with self.db() as db:
            if db.execute("SELECT 1 FROM loss_halts WHERE day=?",(day,)).fetchone():
                return True
            loss=verified_daily_loss(state)
            if loss>=limit:
                db.execute("INSERT OR IGNORE INTO loss_halts VALUES(?,?,?)",(day,loss,self.clock()))
                return True
        return False

    def reconcile_receipts(self,reader):
        """Refresh previously submitted tickets only; this path never submits."""
        with self.db() as db:
            rows=db.execute("SELECT fingerprint,body FROM receipts WHERE state NOT IN (?,?)",("PROTECTED","NOT_SUBMITTED"),).fetchall()
        for fingerprint,body in rows:
            saved=json.loads(body);result=saved.get("result") or {}
            preview=result.get("preview_id")
            try:updated=reader(preview,saved["plan"])
            except Exception:continue
            if updated.get("protection_confirmed") is not True:continue
            saved["result"]={**result,**updated}
            self.claims.confirmed(self.account_id,fingerprint,confirmed_notional(updated))
            with self.db() as db:
                db.execute("UPDATE receipts SET state=?,body=?,updated=? WHERE fingerprint=?",
                           ("PROTECTED",json.dumps(saved),self.clock(),fingerprint))

    def step(self,now):
        p=self.policy()
        if not p["enabled"]:return {"state":"DISABLED"}
        slot=slot_at(now)
        if slot is None:
            session=market_session(now.astimezone(IST))
            opening=session.get("next_open")
            if opening:
                with self.db() as db:
                    db.execute("INSERT OR IGNORE INTO deferred_sessions VALUES(?,?,?,?)",
                        (opening,self.clock(),p.get("revision"),"WAITING_FRESH_ANALYSIS"))
            return {"state":"WAITING_NEXT_OPEN_REVALIDATION","next_open":opening,"broker_amo_submitted":False}
        if not self.lock.acquire(blocking=False):return {"state":"BUSY"}
        try:
            with self.db() as db:
                if db.execute("SELECT 1 FROM runs WHERE slot=?",(slot,)).fetchone():return {"state":"ALREADY_PROCESSED"}
                db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)",(slot,"RUNNING",self.clock(),self.clock(),None,None))
                db.execute("UPDATE deferred_sessions SET state=? WHERE substr(next_open,1,10)=? AND state=?",
                    ("REVALIDATING",slot[:10],"WAITING_FRESH_ANALYSIS"))
            try:
                # A missing/failed broker read cannot masquerade as an empty account.
                state=self.exposure(deepcopy(p))
                if state.get("positions_verified") is not True or state.get("orders_verified") is not True:
                    raise ValueError("Fresh broker positions and orders are required; analysis and entries withheld.")
                self.claims.settle_confirmed(self.account_id,state["exposed_underlyings"])
                started=self.clock()
                rows,report=self.collect(deepcopy(p))
                if slot_at(now+timedelta(seconds=max(0,self.clock()-started)))!=slot:
                    with self.db() as db:db.execute('UPDATE runs SET output=? WHERE slot=?',(json.dumps(dict(report=report,orders_submitted=0)),slot))
                    raise ValueError('Analysis exceeded its fresh schedule slot; no historical result submitted.')
                with self.db() as db:
                    seen={r[0] for r in db.execute("SELECT fingerprint FROM reported")}
                newly_reported,ranking_exclusions=rank(rows,exposed=state["exposed_underlyings"],seen=set() if p.get("allow_duplicate_reports",False) else seen,top=5)
                with self.claims.db() as db:
                    claimed={r[0] for r in db.execute("SELECT fingerprint FROM claims WHERE account=?",(self.account_id,))}
                ranked,execution_exclusions=rank(rows,exposed=state["exposed_underlyings"],seen=claimed,top=5)
                output=allocate(ranked,capital=p["capital"],used=state["used_capital"],
                                funds=state["available_funds"],exposed=state["exposed_underlyings"],seen=claimed,top=5)
                output["execution_exclusions"]=execution_exclusions
                output.update(report=report,mode=p["mode"],account_id=self.account_id,broker=self.broker)
                # Publish analysis independently of execution outcome, including a
                # later rejected/uncertain order. Only unseen ranked plans publish.
                chosen={plan["fingerprint"] for plan in newly_reported}
                report["cards"]=[plan["report_card"] for plan in newly_reported if plan.get("report_card")]
                report.setdefault("exclusions",[]).extend(ranking_exclusions)
                output["recommendations"]=ranked
                report["automation_selection"]=dict(top=5,mode=p["mode"],new_recommendations=len(chosen),allow_duplicate_reports=p.get("allow_duplicate_reports",False))
                with self.db() as db:
                    for fingerprint in chosen:
                        db.execute("INSERT OR IGNORE INTO reported VALUES(?,?,?)",(fingerprint,slot,self.clock()))
                    db.execute("UPDATE runs SET output=?,updated=? WHERE slot=?",(json.dumps(output),self.clock(),slot))
                executions=[]
                if p["mode"]=="AUTO" and self.claims.unsettled(self.account_id):
                    raise ValueError("An earlier entry awaits broker reconciliation; no additional Live entries.")
                from .handoff_priority import priority_key
                execution_plans=sorted(output['plans'],key=priority_key)
                for plan_index,original in enumerate(execution_plans):
                    plan=deepcopy(original)
                    current=self.policy()
                    if not current["enabled"] or current.get("revision")!=p.get("revision"):
                        raise ValueError("Schedule settings changed; remaining entries stopped.")
                    if p["mode"]=="AUTO":
                        if p.get("entries_halted"):
                            executions.append({"symbol":plan["symbol"],"status":"ENTRY_HALT_REVIEW_REQUIRED"})
                            continue
                        if self.loss_halted(state,now,p["daily_loss_limit"]):
                            executions.append({"symbol":plan["symbol"],"status":"DAILY_LOSS_CUTOFF"})
                            continue
                        fresh=self.exposure(deepcopy(p))
                        if fresh.get("positions_verified") is not True or fresh.get("orders_verified") is not True:
                            raise ValueError("Fresh exposure unavailable before entry.")
                        if self.loss_halted(fresh,now,p["daily_loss_limit"]):
                            raise ValueError("Daily loss cutoff reached or unavailable; existing exits remain managed.")
                        if plan["underlying"] in fresh["exposed_underlyings"]:
                            executions.append({"symbol":plan["symbol"],"status":"SKIPPED_EXISTING_EXPOSURE"})
                            continue
                        if not self.auto_ready() or not self.execute:
                            raise ValueError("Protected broker adapter became unavailable.")
                        if plan["kind"]=="EQUITY":
                            from decimal import Decimal,ROUND_FLOOR
                            from .handoff_allocation import amount
                            remaining=[r for r in execution_plans[plan_index:] if r["kind"]=="EQUITY" and r["underlying"] not in fresh["exposed_underlyings"]]
                            capacity=min(Decimal(str(p["capital"]))-Decimal(str(fresh["used_capital"])),Decimal(str(fresh["available_funds"])))
                            pending_options=[r for r in execution_plans[plan_index:] if r['kind']=='LONG_OPTION' and r['underlying'] not in fresh['exposed_underlyings']]
                            capacity=max(Decimal(0),capacity-sum((Decimal(str(r.get('allocation_limit',r['allocation']))) for r in pending_options),Decimal(0)))
                            budget=(capacity/len(remaining)).quantize(Decimal(".01"),rounding=ROUND_FLOOR)
                            quantity=int((budget/amount(plan["entry"])).to_integral_value(rounding=ROUND_FLOOR))
                            if quantity<1:
                                executions.append(dict(symbol=plan["symbol"],status="SKIPPED_INSUFFICIENT_CASH"));continue
                            plan.update(quantity=quantity,allocation_limit=str(budget),allocation=str(amount(plan["entry"])*quantity))
                        if float(plan.get("allocation_limit",plan["allocation"]))+float(fresh["used_capital"])>p["capital"]:
                            raise ValueError("Shared pool changed before submission; no new entry.")
                        from .handoff_allocation import amount
                        if amount(plan.get("allocation_limit",plan["allocation"]))>amount(fresh["available_funds"]):
                            raise ValueError("Fresh funds do not cover the allocation; no new entry.")
                        self.claims.reserve(self.account_id,plan,cap=p["capital"])
                        with self.db() as db:
                            db.execute("INSERT INTO receipts VALUES(?,?,?,?,?)",(plan["fingerprint"],slot,"SUBMITTING",json.dumps({"plan":plan}),self.clock()))
                        try:
                            result=self.execute(deepcopy(plan),deepcopy(p))
                        except PreflightRejected as error:
                            result=dict(symbol=plan["symbol"],status="NOT_SUBMITTED",reason=str(error),orders_submitted=0)
                            with self.db() as db:
                                db.execute("UPDATE receipts SET state=?,body=?,updated=? WHERE fingerprint=?",
                                    ("NOT_SUBMITTED",json.dumps({"plan":plan,"result":result}),self.clock(),plan["fingerprint"]))
                            self.claims.not_submitted(self.account_id,plan["fingerprint"])
                            executions.append(result)
                            continue
                        except Exception:
                            self.claims.uncertain(self.account_id,plan["fingerprint"])
                            raise ValueError("Submission outcome uncertain; no automatic replay.") from None
                        executions.append(result)
                        with self.db() as db:
                            saved=json.loads(db.execute("SELECT body FROM receipts WHERE fingerprint=?",(plan["fingerprint"],)).fetchone()[0])
                            saved["result"]=result
                            db.execute("UPDATE receipts SET state=?,body=?,updated=? WHERE fingerprint=?",
                                       (str(result.get("status") or "UNKNOWN"),json.dumps(saved),self.clock(),plan["fingerprint"]))
                        if result.get('status')=='WAITING_ENTRY_TRIGGER' and result.get('entry_requested') is False:
                            continue
                        if result.get("protection_confirmed") is not True:
                            self.claims.uncertain(self.account_id,plan["fingerprint"])
                            raise ValueError("Await broker fill and exit registration before another automatic entry.")
                        self.claims.confirmed(self.account_id,plan["fingerprint"],confirmed_notional(result))
                        with self.db() as db:db.execute("UPDATE receipts SET state=? WHERE fingerprint=?",("PROTECTED",plan["fingerprint"]))
                output.update(executions=executions,report=report,mode=p["mode"],account_id=self.account_id,broker=self.broker)
                # Completion makes new analysis available to the independent publisher.
                with self.db() as db:
                    db.execute("UPDATE runs SET state=?,updated=?,output=? WHERE slot=?",("COMPLETED",self.clock(),json.dumps(output),slot))
                    db.execute("UPDATE deferred_sessions SET state=? WHERE substr(next_open,1,10)=? AND state=?",
                        ("FRESH_ANALYSIS_COMPLETED",slot[:10],"REVALIDATING"))
                return {"state":"COMPLETED",**output}
            except Exception as error:
                message=str(error) if isinstance(error,ValueError) else "Analysis or broker integration unavailable; no automatic retry."
                with self.db() as db:
                    db.execute("UPDATE runs SET state=?,updated=?,error=? WHERE slot=?",("REVIEW",self.clock(),message,slot))
                    db.execute("UPDATE deferred_sessions SET state=? WHERE substr(next_open,1,10)=? AND state=?",
                        ("WITHHELD_NO_REPLAY",slot[:10],"REVALIDATING"))
                return {"state":"REVIEW","error":message}
        finally:self.lock.release()
