"""Notification-sidecar coordinator; unrelated dashboards and runners stay owned.

Saved owner grants survive dashboard logout/expiry. Broker credentials and all
execution gates remain required; browser sessions are never created or extended.
"""
from datetime import datetime
from pathlib import Path
import time
from threading import Event,Lock,Thread
from .handoff_bridge import OwnedBridge
from .handoff_schedule import Schedule
from .market_calendar import IST

class Runtime:
    def __init__(self,store,root,bridge_factory=OwnedBridge):
        self.store,self.root,self.bridge_factory=store,Path(root),bridge_factory
        self.entries={};self.lock=Lock();self.stopping=Event()
        from .handoff_manual import Manual
        self.manual=Manual(self)

    @staticmethod
    def now():
        return datetime.now(IST)

    def owned(self,user,aid):
        if "handoff" not in user.get("features",[]):
            raise PermissionError("Analysis Handoff is not assigned to this user.")
        account=self.store.account(user,aid)
        if account["broker"] not in {"FYERS","DHAN","MOTILAL_OSWAL"}:
            raise ValueError("Choose your FYERS, Dhan or Motilal account.")
        return account

    def entry(self,user,aid):
        account=self.owned(user,aid)
        with self.lock:
            item=self.entries.get(aid)
            if item is not None:
                if item["user_id"]!=user["id"]:raise PermissionError("Schedule owner mismatch.")
                return item
            item=dict(user_id=user["id"],bridge=None,thread=None,error=None,observer_thread=None,observer_error=None)
            def bridge():
                value=item["bridge"]
                if value is None:raise PermissionError("Sign in and save the schedule to bind this account session.")
                value.identity()
                return value
            item["schedule"]=Schedule(self.store.folder(account)/"handoff-schedule.sqlite3",aid,account["broker"],
                collect=lambda p:bridge().collect(p),exposure=lambda p:bridge().exposure(p),
                execute=lambda plan,p:bridge().execute(plan,p),auto_ready=lambda:bridge().auto_ready())
            self.entries[aid]=item
            return item

    def status(self,user,aid):
        item=self.entry(user,aid)
        value=item["schedule"].status()
        try:
            if item["bridge"] is None:raise PermissionError()
            item["bridge"].identity()
            bound=True
        except PermissionError:bound=False
        scheduler_running=bool(item["thread"] and item["thread"].is_alive())
        observer_running=bool(item["observer_thread"] and item["observer_thread"].is_alive())
        value.update(authorization_basis="BROKER_SESSION_AND_SAVED_OWNER_GRANT" if getattr(item["bridge"],"background",False) else "DASHBOARD_SESSION",session_bound=bound,scheduler_running=scheduler_running,observer_running=observer_running,runtime_error=item["error"],
                     observer_error=item["observer_error"],
                     activation="READY" if bound and scheduler_running else "NOT_RUNNING" if bound else "AUTH_REQUIRED",
                     automatic_broker_supported=value["broker"] in {"FYERS","DHAN"},
                     amo_status="NEXT_OPEN_FRESH_ANALYSIS_REGULAR_ORDERS_ONLY_NO_BROKER_AMO")
        with item["schedule"].db() as db:
            row=db.execute("SELECT output FROM runs WHERE output IS NOT NULL ORDER BY created DESC LIMIT 1").fetchone()
        import json
        output=json.loads(row[0]) if row else {}
        recommendations=output.get("recommendations",[])
        value["allocation"]={k:output.get(k) for k in ("available","allocated","unallocated","blocked")}
        value["executions"]=output.get("executions",[])
        value["analysis_scopes"]=(output.get("report") or {}).get("analysis_scopes",[])
        value["diagnostic"]=item.get("diagnostic")
        value["recommendations"]=[{k:r.get(k) for k in ("fingerprint","symbol","underlying","kind","direction","entry","stop","target","conviction","score_fraction","source_rank","provenance")} for r in recommendations]
        return value

    def diagnose(self,user,aid,token):
        account=self.owned(user,aid);item=self.entry(user,aid)
        current=item.get("diagnostic") or {}
        if current.get("state")=="RUNNING":return current
        bridge=self.bridge_factory(self.root,self.store,user,account,token)
        bridge.identity()
        diagnostic=dict(state="RUNNING",started=time.time(),orders_submitted=0,published=False)
        item["diagnostic"]=diagnostic
        def check():
            try:
                rows,report=bridge.collect(item["schedule"].policy())
                diagnostic.update(state="COMPLETED",finished=time.time(),eligible=len(rows),
                    analysis_scopes=report.get("analysis_scopes",[]),exclusions=report.get("exclusions",[]),
                    plans=[{k:r.get(k) for k in ("underlying","symbol","kind","direction","entry","stop","target","conviction")} for r in rows])
            except Exception as error:
                diagnostic.update(state="FAILED",finished=time.time(),
                    error=str(error) if isinstance(error,(ValueError,PermissionError)) else "Owned read-only analysis check failed.")
            finally:
                tickets=getattr(bridge,"tickets",None);process=getattr(tickets,"process",None)
                if process is not None and process.poll() is None:
                    process.stdin.close()
                    try:process.wait(timeout=10)
                    except Exception:pass
        Thread(target=check,daemon=True,name="handoff-readonly-diagnostic").start()
        return diagnostic

    def configure(self,user,aid,token,payload):
        account=self.owned(user,aid);item=self.entry(user,aid)
        bridge=self.bridge_factory(self.root,self.store,user,account,token)
        bridge.identity()
        old=item["bridge"];item["bridge"]=bridge
        try:result=item["schedule"].configure(payload)
        except Exception:item["bridge"]=old;raise
        # Only the selected owned broker owns the shared configured pool.
        if result["enabled"]:
            for other in self.store.accounts(user):
                if other["id"]==aid or other["broker"] not in {"FYERS","DHAN","MOTILAL_OSWAL"}:continue
                path=self.store.folder(other)/"handoff-schedule.sqlite3"
                if not path.exists():continue
                self.entry(user,other["id"])["schedule"].configure({"enabled":False})
        from .handoff_authorization import save
        if self.bridge_factory is OwnedBridge:
            save(self.store,account,user,result["enabled"])
            bridge.background=bool(result["enabled"])
            if bridge.background:bridge.token=None
        self.start(item,account)
        return self.status(user,aid)

    def start(self,item,account):
        item["error"]=None
        with self.lock:
            if item["thread"] is None or not item["thread"].is_alive():
                item["thread"]=Thread(target=self.watch,args=(item,),daemon=True,name="owned-handoff-schedule")
                item["thread"].start()
            if item["observer_thread"] is None or not item["observer_thread"].is_alive():
                item["observer_thread"]=Thread(target=self.observe,args=(item,account),daemon=True,name="owned-handoff-observer")
                item["observer_thread"].start()
    def restore(self):
        """Restore only explicit enabled grants; Schedule recovers interrupted work without replay."""
        import json,sqlite3
        with self.store.db() as db:accounts=[dict(r) for r in db.execute("SELECT * FROM accounts")]
        for account in accounts:
            folder=self.store.folder(account);path=folder/"handoff-schedule.sqlite3"
            if not path.exists():continue
            try:
                with sqlite3.connect(path) as db:
                    row=db.execute("SELECT body FROM service_authorization WHERE singleton=1").fetchone()
                grant=json.loads(row[0]) if row else {}
                if not grant.get("enabled"):continue
                from .handoff_authorization import identity
                user=identity(self.store,account,folder,grant["user_id"])
                item=self.entry(user,account["id"])
                if not item["schedule"].policy().get("enabled"):continue
                bridge=self.bridge_factory(self.root,self.store,user,account,None)
                bridge.background=True
                bridge.identity()
                item["bridge"]=bridge
                self.start(item,account)
            except (PermissionError,ValueError,KeyError,sqlite3.Error):
                continue

    def watch(self,item):
        while not self.stopping.is_set():
            try:
                bridge=item["bridge"]
                if bridge is None:raise PermissionError("Signed-in account session is required.")
                bridge.identity()
                schedule=item["schedule"]
                if hasattr(bridge,"process_entry_triggers"):bridge.process_entry_triggers(schedule)
                schedule.reconcile_receipts(lambda preview,plan:bridge.reconcile_intent(preview,plan))
                result=schedule.step(datetime.now(IST))
                if result.get("state") not in {"ALREADY_PROCESSED","BUSY","OUTSIDE_MARKET_SESSION","WAITING_NEXT_OPEN_REVALIDATION"}:
                    item["error"]=result.get("error")
            except PermissionError:
                item["error"]="Auto authorization or account access was revoked; no new entry."
            except Exception:
                item["error"]="Owned scheduling integration unavailable; no automatic order retry."
            self.stopping.wait(10)

    def observe(self,item,account):
        from .handoff_observer import Observer
        observer=Observer(self.store.folder(account),account)
        while not self.stopping.is_set():
            try:
                bridge=item["bridge"]
                if bridge is None:raise PermissionError()
                bridge.identity()
                state=bridge.read_worker()
                item["schedule"].loss_halted(state,datetime.now(IST),10000)
                observer.update(state)
                item["observer_error"]=None
            except Exception:
                item["observer_error"]="Fresh private position/fill evidence unavailable; no execution update inferred."
            self.stopping.wait(60)

    def close(self):
        self.stopping.set()
