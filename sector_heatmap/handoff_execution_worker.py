"""Private owned-account ticket worker; no network listener and no runner startup.

Only a durable reserved Handoff intent under an enabled, explicitly authorized
Auto policy can pass the submit gate. Previews themselves are read-only.
"""
import contextlib
from datetime import datetime
import json,os,sqlite3,sys
from pathlib import Path
from .market_calendar import IST
from .workspaces import WorkspaceStore

class Worker:
    def __init__(self):
        self.registry=Path(os.environ["SECTOR_PULSE_WORKSPACE_REGISTRY"])
        self.store=WorkspaceStore(self.registry)
        self.aid=os.environ["SECTOR_PULSE_WORKSPACE_ID"]
        with self.store.db() as db:
            row=db.execute("SELECT * FROM accounts WHERE id=?",(self.aid,)).fetchone()
        if not row:raise PermissionError("Owned account unavailable.")
        self.account=dict(row);self.folder=self.store.folder(self.account)
        if Path.cwd().resolve()!=self.folder.resolve()/"source":
            raise PermissionError("Ticket worker must use its owned source.")
        self.schedule=self.folder/"handoff-schedule.sqlite3"
        self.active_claim=None
        from .automation import AutomationPolicyService
        self.legacy_policy=AutomationPolicyService()
        if self.account["broker"]=="FYERS":
            from .fyers_execution import FyersExecutionService
            self.service=FyersExecutionService(live_gate=self.live_gate,execution_halt=self.halt)
        elif self.account["broker"]=="DHAN":
            from .dhan_execution import DhanExecutionService
            self.service=DhanExecutionService(self.account,self.folder,execution_allowed=self.live_gate,execution_halt=self.halt)
        elif self.account["broker"]=="MOTILAL_OSWAL":
            from .motilal_service import Service
            self.service=Service(self.folder,self.account,execution_allowed=lambda:False)
        else:
            raise ValueError("Selected native protected execution worker is not integrated.")

    def policy(self):
        with sqlite3.connect(self.schedule) as db:
            return json.loads(db.execute("SELECT body FROM policy WHERE id=1").fetchone()[0])

    def live_gate(self):
        with self.store.db() as db:
            account=db.execute("SELECT * FROM accounts WHERE id=?",(self.aid,)).fetchone()
        if not account or not account["live_enabled"]:return False
        legacy=self.legacy_policy.current()
        if legacy.get("configured") and (not legacy.get("profile_digest_valid") or (legacy.get("profile") or {}).get("kill_switch_engaged")):
            return False
        return True

    def halt(self,reference,reason):
        # Stop this workflow's future entries, without altering another runner.
        with sqlite3.connect(self.schedule) as db:
            p=json.loads(db.execute("SELECT body FROM policy WHERE id=1").fetchone()[0])
            p.update(entries_halted=True,halt_reason="Broker outcome requires reconciliation; analysis continues.")
            db.execute("UPDATE policy SET body=? WHERE id=1",(json.dumps(p),))

    def submit_gate(self,preview_id,fingerprint):
        p=self.policy()
        if p.get("enabled") is not True or p.get("mode") not in {"AUTO","MANUAL"} or (p.get("mode")=="AUTO" and p.get("live_authorized") is not True) or p.get("broker")!=self.account["broker"]:
            raise PermissionError("This owned Handoff Auto policy is not authorized and enabled.")
        if p.get("entries_halted"):raise PermissionError("New Handoff entries are halted pending reconciliation.")
        if not self.live_gate():raise PermissionError("Broker Live capability or application halt blocks execution.")
        if self.account['broker']=='FYERS' and p.get('mode')=='AUTO':
            from .handoff_exit_monitor import Store
            Store(self.folder).guard_new_entry()
        if not isinstance(fingerprint,str) or len(fingerprint)!=64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise ValueError("Exact durable Handoff reservation required.")
        with sqlite3.connect(self.schedule.with_suffix(".claims.sqlite3")) as db:
            claim=db.execute("SELECT * FROM claims WHERE account=? AND fingerprint=? AND state=?",(self.aid,fingerprint,"RESERVED")).fetchone()
        if not claim:raise PermissionError("No unconsumed owned entry reservation.")
        with sqlite3.connect(self.schedule) as db:
            row=db.execute("SELECT body FROM receipts WHERE fingerprint=? AND state=?",(fingerprint,"SUBMITTING")).fetchone()
        if not row:raise PermissionError("No durable pending submission receipt.")
        receipt=json.loads(row[0]);plan=receipt["plan"]
        if self.account['broker']=='FYERS' and p['mode']=='AUTO':
            from .handoff_screener import guard_entry_source
            guard_entry_source(plan.get('report_card',{}).get('candidate',{}),self.folder)
        if p["mode"]=="MANUAL":
            auth=receipt.get("authorization") or {}
            if auth.get("mode")!="MANUAL" or auth.get("user_id")!=self.account.get("user_id") or auth.get("preview_id")!=preview_id or auth.get("policy_revision")!=p.get("revision") or datetime.now(IST).timestamp()>=auth.get("expires_at",0):
                raise PermissionError("Exact owner-reviewed Manual authorization is unavailable.")
        from .handoff_broker_read import read
        state=read()
        from .handoff_schedule import verified_daily_loss
        day=datetime.now(IST).date().isoformat()
        with sqlite3.connect(self.schedule) as db:
            halted=db.execute("SELECT 1 FROM loss_halts WHERE day=?",(day,)).fetchone()
            if verified_daily_loss(state)>=10000:
                db.execute("INSERT OR IGNORE INTO loss_halts VALUES(?,?,?)",(day,state["daily_loss"],datetime.now(IST).timestamp()))
                halted=True
        if halted:raise PermissionError("Daily loss cutoff reached; no new entry.")
        if self.account['broker']=='FYERS' and plan.get('ticket_payload',{}).get('handoff_auto') is True:
            from .handoff_entry_conditions import reached
            from .fyers_execution import _fresh_depth_quote,_current_client
            condition=plan.get('entry_condition')
            quote=_fresh_depth_quote(_current_client(),plan['underlying'],datetime.now(IST))
            provider=quote.get('provider_timestamp');provider=float(provider)/1000 if float(provider)>1e10 else float(provider)
            met,reason=reached(condition,dict(symbol=plan['underlying'],price=(quote['bid']+quote['ask'])/2,provider_at=provider,received_at=datetime.now(IST).timestamp(),connected=True),datetime.now(IST).timestamp())
            if plan.get('ticket_payload',{}).get('execution_entry_order',{}).get('type')=='STOP_LIMIT':
                from .handoff_entry_conditions import stop_limit_before_trigger
                pp=plan.get('ticket_payload',{});action='BUY' if plan['direction']=='BULLISH' else 'SELL'
                valid_stop=pp.get('execution_entry_order',{}).get('type')=='STOP_LIMIT' and plan.get('kind')=='EQUITY' and stop_limit_before_trigger(condition,dict(price=(quote['bid']+quote['ask'])/2),plan['symbol'],action,plan.get('tick_size'),plan['entry'])
                if not valid_stop:raise PermissionError('The resting stop-limit trigger has crossed or is invalid; prepare fresh bounded terms.')
            elif not met:raise PermissionError(reason)
        stored=self.service.previews.get(preview_id)
        if not stored:raise ValueError("Owned ticket preview unavailable.")
        preview=stored["preview"]
        leg=preview["instrument"]["contracts"][0]
        intent=json.loads((self.folder/"handoff-intents"/(fingerprint+".json")).read_text())
        if intent.get("preview_id")!=preview_id or intent.get("account_id")!=self.aid:
            raise PermissionError("Prepared identity differs from the durable reserved intent.")
        from .handoff_allocation import amount
        underlying=preview.get("underlying") or stored.get("payload",{}).get("underlying")
        if underlying!=claim[2]:
            raise ValueError("Prepared underlying differs from the reserved recommendation.")
        if leg["symbol"]!=plan["symbol"] or leg["quantity"]!=plan["quantity"] or preview["instrument"]["kind"]!=plan["kind"]:
            raise ValueError("Prepared contract or quantity differs from the reserved recommendation.")
        tick=amount(leg["tick_size"])
        for actual,key in ((preview["protection"]["stop_loss_price"],"stop"),(preview["protection"]["target_price"],"target")):
            if abs(amount(actual)-amount(plan[key]))>tick/2:
                raise ValueError("Prepared exits changed; new analysis is required.")
        if amount(leg["limit_price"])*leg["quantity"]>amount(claim[3]):
            raise ValueError("Prepared notional exceeds the reserved allocation.")
        if underlying in state["exposed_underlyings"]:
            raise ValueError("Underlying already exposed; no duplicate entry.")
        if float(state["used_capital"])+float(claim[3])>float(p["capital"]):
            raise ValueError("Shared capital exhausted before submission.")
        if not preview.get("protection") or not preview.get("submission_eligible"):
            raise ValueError("Validated entry, stop and target are required.")

    def analyze(self,payload):
        if not hasattr(self,"analysis_provider"):
            from .sector_service import AnalysisHistoryStore
            if self.account["broker"]=="FYERS":
                from .handoff_fyers_analysis import Provider
                self.analysis_provider=Provider(self.account,self.folder)
            elif self.account["broker"]=="DHAN":
                from .dhan_sector_analysis import DhanSectorAnalysisService
                from .dhan_handoff import DhanHandoff
                sectors=DhanSectorAnalysisService(self.service)
                sectors.store=AnalysisHistoryStore(self.folder/"source/.private/handoff-analysis-history.json")
                self.analysis_provider=DhanHandoff(self.service,sectors)
                self.analysis_refreshed=0
            elif self.account["broker"]=="MOTILAL_OSWAL":
                from .motilal_analysis import Sectors,Handoff
                sectors=Sectors(self.service)
                sectors.store=AnalysisHistoryStore(self.folder/"source/.private/handoff-analysis-history.json")
                self.analysis_provider=Handoff(self.service,sectors)
                self.analysis_refreshed=0
            else:raise ValueError("Native isolated analysis provider unavailable.")
            self.analysis_runs={}
        if self.account["broker"]!="FYERS":
            import time
            if time.monotonic()-self.analysis_refreshed>=300:
                self.analysis_provider.sectors.refresh()
                self.analysis_refreshed=time.monotonic()
        from .handoff_analysis import opportunities
        result=opportunities(payload,self.analysis_provider,self.analysis_runs)
        from .handoff_ai import review_stock_handoff
        result=review_stock_handoff(result,payload,self.folder/'source')
        return result

    def call(self,operation,payload):
        if getattr(self,"account",{}).get("broker")=="MOTILAL_OSWAL":
            if operation=="capabilities":
                return dict(selected_broker="MOTILAL_OSWAL",native_analysis_available=True,
                    live_submission_enabled=False,protected_submission_supported=False,
                    message="Native captured-candle analysis only; linked broker stop/target integration is not verified.")
            if operation not in {"analysis","size"}:
                raise ValueError("Motilal protected Handoff execution is not integrated; no unprotected order or alternate broker is used.")
        if operation=="analysis":return self.analyze(payload)
        if operation=="size":
            from .handoff_analysis import size
            return size(payload,getattr(self,"analysis_runs",{}))
        if operation=="prepare":return self.service.prepare(payload)
        if operation=="submit":
            self.submit_gate(payload["preview_id"],payload["fingerprint"])
            self.service.handoff_owned_submission=True
            try:return self.service.submit(payload["preview_id"],payload["confirmation"])
            finally:self.service.handoff_owned_submission=False
        if operation=="reconcile":return self.service.reconcile_protection(payload["preview_id"])
        if operation=="capabilities":return self.service.capabilities()
        raise ValueError("Unsupported private ticket operation.")

def main():
    os.umask(0o077)
    with contextlib.redirect_stdout(sys.stderr):worker=Worker()
    for line in sys.stdin:
        request=None
        try:
            request=json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                result=worker.call(request["operation"],request.get("payload") or {})
            response=dict(id=request["id"],ok=True,result=result)
        except Exception as error:
            from .fyers_execution import FyersExecutionUnavailable,PreviewChanged
            safe=isinstance(error,(ValueError,PermissionError,FyersExecutionUnavailable,PreviewChanged))
            response=dict(id=request.get("id") if isinstance(request,dict) else None,ok=False,
                error=str(error) if safe else "Owned ticket operation failed ("+type(error).__name__+"); no automatic entry retry.")
        sys.stdout.write(json.dumps(response,allow_nan=False)+"\n");sys.stdout.flush()
if __name__=="__main__":main()
