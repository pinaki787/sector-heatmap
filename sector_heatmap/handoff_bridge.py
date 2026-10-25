"""Owned loopback adapter. Analysis and previews are separate from submissions.

Interactive requests require dashboard authentication. Background schedules use
a revocable owner grant and existing broker credentials; no session is minted.
"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError
from .workspaces import isolated_environment,COOKIE
from .market_calendar import IST
from .handoff_allocation import amount
from .handoff_errors import PreflightRejected

def bounded_preview(bridge,payload,card,quantity,limit):
    """Refresh a ticket read-only; cash shares may shrink to fit their budget."""
    from decimal import ROUND_FLOOR
    limit=amount(limit)
    for _ in range(3):
        payload["quantity"]=quantity;payload["proposal"]["quantity"]=quantity
        preview=bridge.request("prepare",payload)
        current=bridge.normalized(preview,card,payload)
        if amount(current["entry"])*quantity<=limit:return preview,current,quantity
        if current["kind"]!="EQUITY":
            raise ValueError("One option lot exceeds its reserved capital after the quote refresh; no order submitted.")
        smaller=int((limit/amount(current["entry"])).to_integral_value(rounding=ROUND_FLOOR))
        if smaller<1 or smaller>=quantity:
            raise ValueError("Current quote cannot fit the assigned cash budget.")
        quantity=smaller
    raise ValueError("Quotes kept moving beyond the assigned budget; no order submitted.")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise PermissionError("Account requests cannot follow redirects.")

class OwnedBridge:
    def __init__(self,root,store,user,account,token,clock=time.time):
        self.root,self.store=Path(root),store
        self.user_id,self.account_id=user["id"],account["id"]
        self.token,self.clock=token,clock
        self.folder=store.folder(account)
        self.account=account
        self.opener=build_opener(ProxyHandler({}),NoRedirect())
        from .handoff_ticket_client import TicketClient
        self.tickets=TicketClient(self.root,store,account)

    def identity(self):
        if getattr(self,"background",False):
            from .handoff_authorization import identity
            user=identity(self.store,self.account,self.folder,self.user_id)
        else:
            user=self.store.session(self.token)
        if user["id"]!=self.user_id or "handoff" not in user.get("features",[]):
            raise PermissionError("Analysis Handoff is not assigned to this signed-in user.")
        account=self.store.account(user,self.account_id)
        if account["broker"]!=self.account["broker"] or account["port"]!=self.account["port"]:
            raise PermissionError("Broker identity changed; bind the schedule again.")
        return user,account

    def request(self,operation,payload=None):
        user,account=self.identity()
        if (account["broker"] in {"FYERS","DHAN","MOTILAL_OSWAL"} and operation in {"prepare","submit","capabilities","size"}):
            return self.tickets.call(operation,payload or {})
        routes={"analysis":"analysis-handoff/analyze","size":"analysis-handoff/size",
                "prepare":"trade-ticket/prepare","submit":"trade-ticket/submit",
                "capabilities":"trade-ticket/capabilities"}
        if operation=="job":
            ident=str(payload)
            if len(ident)!=32 or any(c not in "0123456789abcdef" for c in ident):
                raise ValueError("Invalid owned analysis job.")
            path="/api/jobs?job_id="+ident
            payload=None
        else:
            if operation not in routes:raise ValueError("Unsupported Handoff operation.")
            prefix={"FYERS":"/api/","DHAN":"/api/dhan/","MOTILAL_OSWAL":"/api/motilal/"}[account["broker"]]
            # Dhan shared ticket methods are served by its own workspace.
            if account["broker"]=="DHAN" and operation in {"prepare","submit","capabilities"}:prefix="/api/"
            path=prefix+routes[operation]
        host="127.0.0.1:"+str(account["port"])
        headers={"Cookie":COOKIE+"="+self.token,"Origin":"http://"+host,
                 "X-CSRF-Token":user["csrf"],"Content-Type":"application/json"}
        data=json.dumps(payload,allow_nan=False).encode() if isinstance(payload,dict) else None
        req=Request("http://"+host+path,data=data,headers=headers)
        try:
            with self.opener.open(req,timeout=30) as response:result=json.load(response)
        except HTTPError as error:
            try:message=json.load(error).get("error")
            except Exception:message=None
            raise ValueError(message or "Owned account action was rejected; no automatic retry.") from None
        if not isinstance(result,dict):raise ValueError("Invalid owned account response.")
        return result

    def read_worker(self,action="state",preview_id=None):
        self.identity()
        command=[str(self.root/".venv/bin/python"),"-B","-m","sector_heatmap.handoff_broker_read",action]
        if preview_id:command.append(preview_id)
        env=isolated_environment(self.account,self.folder,self.store.path,8079)
        result=subprocess.run(command,cwd=self.folder/"source",env=env,capture_output=True,text=True,timeout=65)
        if result.returncode:raise ValueError("Owned broker evidence worker failed; no order retry.")
        try:value=json.loads(result.stdout)
        except (ValueError,TypeError):raise ValueError("Owned broker evidence unavailable.") from None
        if value.get("ok") is not True:raise ValueError(value.get("error") or "Fresh broker evidence unavailable.")
        return value["state"]

    def exposure(self,policy):
        return self.read_worker()

    def auto_ready(self):
        # Every prepare also proves the running backend includes native exits.
        return (self.account["broker"] in {"FYERS","DHAN"} and bool(self.identity()[1]["live_enabled"])
                and self.tickets.call("capabilities",{}).get("live_submission_enabled") is True)

    def analysis(self,route,policy):
        payload=dict(broker=self.account["broker"],account_id=self.account_id,mode="intraday",
            recipient="codex",ai_provider=policy["ai_provider"],instrument_route=route,
            handoff_automation_intermediate=True,handoff_schedule_mode=policy.get('mode','MANUAL'),
            risk_policy=dict(planning_capital=policy["capital"],daily_loss_limit=10000,
                enforce_risk_controls=False,enforce_minimum_reward_to_risk=True,
                minimum_reward_to_risk=1,stop_basis="price",order_type="LIMIT"))
        if self.account["broker"] in {"DHAN","MOTILAL_OSWAL"}:
            self.identity()
            return self.tickets.call("analysis",payload)
        if self.account["broker"]=="FYERS":
            self.identity()
            return self.tickets.call("analysis",payload)
        accepted=self.request("analysis",payload)
        if not accepted.get("job_id"):raise ValueError("Durable account analysis job was not accepted.")
        deadline=self.clock()+600
        while self.clock()<deadline:
            job=self.request("job",accepted["job_id"])
            if job.get("terminal"):
                if job.get("status")!="COMPLETED":raise ValueError(job.get("error") or "Owned analysis failed.")
                output=job.get("output")
                if not isinstance(output,dict):raise ValueError("Analysis output unavailable.")
                return output
            time.sleep(2)
        raise ValueError("Analysis is still running; this schedule slot will not be replayed.")

    def collect(self,policy):
        reports=[self.analysis(route,policy) for route in ("cash_equity","stock_options")]
        rows=[];excluded=[]
        for report in reports:
            source_scope=(report.get('scope') or {}).get('screener') or {}
            if policy.get('mode')=='AUTO' and source_scope.get('enabled') and source_scope.get('auto_enabled') and source_scope.get('status') not in {'COMPLETED','DISABLED'}:
                raise ValueError('Fresh Screener collection is incomplete; combined priority ranking cannot submit new Auto entries.')
            if report.get("source",{}).get("broker")!=self.account["broker"]:
                raise ValueError("Analysis returned a different broker; no report or entry.")
            excluded.extend(report.get("exclusions",[]))
            from .handoff_priority import priority_key
            for source in sorted(report.get("cards",[]),key=priority_key):
                card=deepcopy(source);plan=card["analysis"];candidate=card["candidate"]
                if str((plan.get("conviction") or {}).get("rating","")).upper()!="HIGH":continue
                if policy.get('ai_provider')=='CODEX_CHATGPT':
                    reviewed=next((r for r in (report.get('ai_review') or {}).get('recommendations',[]) if r.get('symbol')==candidate['symbol']),None)
                    if (report.get('ai_review') or {}).get('status')!='COMPLETED' or not reviewed or reviewed.get('decision')!=candidate['direction']:
                        excluded.append(dict(symbol=candidate['symbol'],reason='Selected AI mode does not affirm the directional plan; no Auto entry.'));continue
                try:
                    sized=self.request("size",dict(broker=self.account["broker"],account_id=self.account_id,
                        analysis_id=report["analysis_id"],card_id=card["card_id"],
                        selection={"method":"structure"},risk_policy=report["risk_policy"]))
                    invalidation=sized["active_invalidation"]
                    underlying_entry=float((sized.get("fresh_quote") or {}).get("price") or 0)
                    import math
                    if not math.isfinite(underlying_entry) or underlying_entry<=0:
                        raise ValueError("Fresh underlying entry is unavailable after structural sizing.")
                    plan["entry"]=underlying_entry
                    plan["active_invalidation"]=invalidation
                    option=plan["kind"]=="LONG_OPTION"
                    payload=dict(broker=self.account["broker"],account_id=self.account_id,
                        underlying=candidate["symbol"],
                        underlying_exit_plan=dict(entry=underlying_entry,stop=invalidation["price"],target=invalidation["target"]),
                        analysis_evidence=dict(source="ANALYSIS_HANDOFF",candidate=candidate,recommendation=plan,conviction=plan["conviction"]),
                        proposal={**plan["proposal"],"kind":"LONG_OPTION","source":"ANALYSIS_HANDOFF"} if option else
                            dict(kind="EQUITY",direction=candidate["direction"],quantity=1,entry=plan["entry"],target=invalidation["target"]),
                        invalidation=invalidation["price"],quantity=1,lots=1,
                        cash_product=('INTRADAY' if candidate['direction']=='BEARISH' else policy['cash_product']),enforce_risk_controls=False,
                        enforce_minimum_reward_to_risk=True,minimum_reward_to_risk=1,
                        daily_loss_limit=10000,order_type="LIMIT",require_market_open=True)
                    payload['recommended_entry_limit']=plan['proposal']['entry_points'] if option else (plan.get('entry_condition') or {}).get('level')
                    if option:payload["expiry"]=plan["proposal"]["expiry_iso"]
                    preview=self.request("prepare",payload)
                    payload['accepted_execution_protection']=deepcopy(preview.get('protection'))
                    row=self.normalized(preview,card,payload)
                    rows.append(row)
                except (ValueError,KeyError) as error:
                    excluded.append(dict(symbol=candidate.get("symbol"),reason=str(error)))
        from .handoff_priority import priority_key
        rows.sort(key=priority_key)
        return rows,dict(schema="sector-pulse-auto-analysis/v1",generated_at=datetime.now(IST).isoformat(),
            source=dict(broker=self.account["broker"],mode="intraday"),cards=[],candidates=[],
            analysis_scopes=[dict(route=report.get("instrument_route"),scope=report.get("scope") or {}) for report in reports],
            exclusions=excluded,order_authority="NONE",decision_support_only=True)

    @staticmethod
    def normalized(preview,card,payload):
        instrument=preview.get("instrument") or {}
        contracts=instrument.get("contracts") or []
        protection=preview.get("protection") or {}
        if len(contracts)!=1 or not protection:
            raise ValueError("Running account backend has no validated single-contract native exit plan.")
        leg=contracts[0];plan=card["analysis"]
        if instrument.get("kind") not in {"EQUITY","LONG_OPTION"} or not preview.get("submission_eligible"):
            raise ValueError("Recommendation is not an eligible protected ticket.")
        expected="BUY" if instrument["kind"]=="LONG_OPTION" or card["candidate"]["direction"]=="BULLISH" else "SELL"
        if leg.get("action")!=expected:
            raise ValueError("Prepared action differs from the recommendation; only bought options are authorized.")
        return dict(underlying=payload["underlying"],symbol=leg["symbol"],kind=instrument["kind"],
            source_rank=card['candidate'].get('source_rank'),provenance=deepcopy(card['candidate'].get('provenance',[])),
            direction=card["candidate"]["direction"],entry=leg["limit_price"],
            stop=protection["stop_loss_price"],target=protection["target_price"],
            lot_size=leg["lot_size"] if instrument["kind"]=="LONG_OPTION" else 1,
            conviction=deepcopy(plan["conviction"]),validated=True,report_card=card,
            security_id=leg.get("security_id"),exchange_segment=leg.get("exchange_segment"),
            tick_size=leg.get('tick_size'),ticket_payload=payload,entry_condition=deepcopy(plan.get("entry_condition")))

    def execute(self,plan,policy):
        if getattr(self,'account',{}).get('broker')=='FYERS' and (self.folder/'handoff-exits.sqlite3').exists():
            from .handoff_exit_monitor import Store
            if not Store(self.folder).policy().get('authorized'):return self._execute_now(plan,policy)
            from .handoff_entry_queue import Queue
            return Queue(self.folder).enqueue(plan,policy)
        return self._execute_now(plan,policy)

    def process_entry_triggers(self,schedule):
        if self.account['broker']=='FYERS':
            from .handoff_entry_queue import Queue
            Queue(self.folder).process(self,schedule)

    def _execute_now(self,plan,policy):
        try:
            if getattr(self,'account',{}).get('broker')=='FYERS':
                from .handoff_screener import guard_entry_source
                guard_entry_source(plan.get('report_card',{}).get('candidate',{}),self.folder)
            if not self.auto_ready():raise ValueError("Owned broker Live integration is unavailable.")
            payload=deepcopy(plan["ticket_payload"])
            payload["quantity"]=plan["quantity"];payload["proposal"]["quantity"]=plan["quantity"]
            fresh,normalized,quantity=bounded_preview(self,payload,plan["report_card"],plan["quantity"],plan.get("allocation_limit",plan["allocation"]))
            plan["quantity"]=quantity
            if normalized["symbol"]!=plan["symbol"] or normalized["kind"]!=plan["kind"]:
                raise ValueError("Execution contract changed; fresh analysis required.")
            # Never exceed the exact bounded allocation, even after quote movement.
            if amount(normalized["entry"])*plan["quantity"]>amount(plan.get("allocation_limit",plan["allocation"])):
                raise ValueError("Fresh price exceeds allocated capital; no entry submitted.")
            if fresh.get("live_submission_enabled") is not True:
                raise ValueError("Owned account Live gate is disabled.")
            # Bind the exact fresh ticket to the reserved budget before submit.
            import sqlite3
            with sqlite3.connect(self.folder/"handoff-schedule.sqlite3") as db:
                record=db.execute("SELECT body FROM receipts WHERE fingerprint=? AND state='SUBMITTING'",(plan["fingerprint"],)).fetchone()
                if not record:raise ValueError("Durable owned receipt unavailable before submission.")
                saved=json.loads(record[0]);bound=saved["plan"]
                if bound["symbol"]!=normalized["symbol"] or (bound["quantity"]!=plan["quantity"] and not (bound["kind"]=="EQUITY" and 1<=plan["quantity"]<=bound["quantity"])):
                    raise ValueError("Reserved contract or quantity differs from the fresh ticket.")
                bound.update(ticket_payload=deepcopy(payload),entry_condition=deepcopy(plan.get('entry_condition')),quantity=plan["quantity"],entry=normalized["entry"],stop=normalized["stop"],target=normalized["target"],
                    allocation=str(amount(normalized["entry"])*plan["quantity"]))
                saved["prepared_preview_id"]=fresh["preview_id"]
                db.execute("UPDATE receipts SET body=? WHERE fingerprint=? AND state='SUBMITTING'",(json.dumps(saved),plan["fingerprint"]))
            # Persist the prepared identity before the one allowed mutation. A
            # response timeout can then be reconciled without repeating the entry.
            from .config import _atomic_private_write
            intent=self.folder/"handoff-intents"/(plan["fingerprint"]+".json")
            _atomic_private_write(intent,json.dumps(dict(preview_id=fresh["preview_id"],
                account_id=self.account_id,fingerprint=plan["fingerprint"],created=self.clock())))
        except Exception as error:
            reason=str(error) if isinstance(error,(ValueError,PermissionError)) else "Pre-submit guard failed ("+type(error).__name__+"); no broker order was requested."
            raise PreflightRejected(reason) from None
        result=self.request("submit",dict(broker=self.account["broker"],account_id=self.account_id,
            preview_id=fresh["preview_id"],confirmation=fresh["confirmation_phrase"],fingerprint=plan["fingerprint"]))
        # Read-only reconciliation works independently of the dashboard process.
        try:audited=self.read_worker("reconcile",result.get("preview_id",fresh["preview_id"]))
        except Exception:audited=dict(protection_confirmed=False,protection_state="AWAITING_BROKER_CONFIRMATION")
        return {**result,**audited,"preview_id":fresh["preview_id"]}

    def submit_prepared(self,plan,preview):
        """Use the exact preview explicitly reviewed in the Manual API."""
        try:
            self.identity()
            from .config import _atomic_private_write
            _atomic_private_write(self.folder/"handoff-intents"/(plan["fingerprint"]+".json"),
                json.dumps(dict(preview_id=preview["preview_id"],account_id=self.account_id,
                    fingerprint=plan["fingerprint"],created=self.clock())))
        except Exception as error:
            reason=str(error) if isinstance(error,(ValueError,PermissionError)) else "Manual pre-submit guard failed before any order request."
            raise PreflightRejected(reason) from None
        result=self.request("submit",dict(broker=self.account["broker"],account_id=self.account_id,
            preview_id=preview["preview_id"],confirmation=preview["confirmation_phrase"],fingerprint=plan["fingerprint"]))
        try:audited=self.read_worker("reconcile",preview["preview_id"])
        except Exception:audited=dict(protection_confirmed=False,protection_state="AWAITING_BROKER_CONFIRMATION")
        return {**result,**audited,"preview_id":preview["preview_id"]}

    def reconcile_intent(self,preview_id,plan):
        if not preview_id:
            fingerprint=plan.get("fingerprint","")
            if len(fingerprint)!=64 or any(c not in "0123456789abcdef" for c in fingerprint):
                raise ValueError("Invalid owned recommendation identity.")
            saved=json.loads((self.folder/"handoff-intents"/(fingerprint+".json")).read_text())
            if saved.get("account_id")!=self.account_id or saved.get("fingerprint")!=fingerprint:
                raise PermissionError("Submitted intent belongs to a different account.")
            preview_id=saved["preview_id"]
        return self.read_worker("reconcile",preview_id)
