"""Explicit owner-reviewed scheduled Handoff tickets; no submit on selection."""
from .handoff_errors import PreflightRejected
from copy import deepcopy
import hashlib,json,secrets,time
from threading import Lock
from .handoff_allocation import allocate,amount
from .config import _atomic_private_write

class Manual:
    def __init__(self,runtime,clock=time.time):
        self.runtime,self.clock=runtime,clock;self.groups={};self.lock=Lock()

    def prepare(self,user,aid,token,selected):
        item=self.runtime.entry(user,aid);schedule=item["schedule"];policy=schedule.policy()
        if policy["mode"]!="MANUAL" or policy["enabled"] is not True:
            raise PermissionError("Enable Manual scheduling before reviewing these recommendations.")
        if policy.get("entries_halted"):raise PermissionError("New entries are halted pending broker reconciliation.")
        if not isinstance(selected,list) or not 1<=len(selected)<=5 or len(set(selected))!=len(selected):
            raise ValueError("Select one to five distinct high-conviction recommendations.")
        with schedule.db() as db:
            latest=db.execute("SELECT slot,updated,output FROM runs WHERE output IS NOT NULL ORDER BY created DESC LIMIT 1").fetchone()
        if not latest or not 0<=self.clock()-latest[1]<=900:raise ValueError("Scheduled evidence expired; wait for a fresh analysis.")
        rows=json.loads(latest[2]).get("recommendations",[])
        wanted={r["fingerprint"]:r for r in rows}
        if any(key not in wanted for key in selected):raise ValueError("Selection differs from the latest scheduled recommendations.")
        account=self.runtime.owned(user,aid)
        bridge=self.runtime.bridge_factory(self.runtime.root,self.runtime.store,user,account,token)
        bridge.identity();state=bridge.exposure(policy)
        if schedule.loss_halted(state,self.runtime.now(),10000):raise PermissionError("Daily loss cutoff reached; no new entry.")
        schedule.claims.settle_confirmed(aid,state["exposed_underlyings"])
        if schedule.claims.unsettled(aid):raise ValueError("An earlier entry awaits broker reconciliation.")
        fresh=[];excluded=[]
        for key in selected:
            old=wanted[key]
            if old["underlying"] in state["exposed_underlyings"]:
                excluded.append(dict(symbol=old["symbol"],reason="Existing broker position or pending order; excluded before review."));continue
            payload=deepcopy(old["ticket_payload"])
            payload["quantity"]=1;payload["proposal"]["quantity"]=1;payload["lots"]=1
            preview=bridge.request("prepare",payload)
            row=bridge.normalized(preview,old["report_card"],payload)
            if row["symbol"]!=old["symbol"] or row["kind"]!=old["kind"]:
                raise ValueError("Execution contract changed; wait for fresh analysis.")
            row["recommendation_fingerprint"]=key
            fresh.append(row)
        if not fresh:raise ValueError("All selected instruments now have existing exposure; no ticket prepared.")
        allocation=allocate(fresh,capital=policy["capital"],used=state["used_capital"],
            funds=state["available_funds"],exposed=state["exposed_underlyings"])
        if allocation.get("blocked") or len(allocation["plans"])!=len(fresh):
            raise ValueError(allocation.get("blocked") or "The shared pool cannot fund every selected idea.")
        items=[]
        from decimal import Decimal,ROUND_FLOOR
        ordered=sorted(allocation["plans"],key=lambda row:row["kind"]!="LONG_OPTION")
        remaining_cash=sum(row["kind"]=="EQUITY" for row in ordered)
        capacity=Decimal(allocation["available"])
        option_cost=Decimal(0)
        for plan in ordered:
            plan["fingerprint"]=plan.pop("recommendation_fingerprint")
            if plan["kind"]=="EQUITY":
                budget=((capacity-option_cost)/remaining_cash).quantize(Decimal(".01"),rounding=ROUND_FLOOR)
                quantity=int((budget/amount(plan["entry"])).to_integral_value(rounding=ROUND_FLOOR))
                if quantity<1:raise ValueError("Remaining shared cash cannot fund an equity share.")
                plan.update(quantity=quantity,allocation_limit=str(budget))
            payload=deepcopy(plan["ticket_payload"])
            payload["quantity"]=plan["quantity"];payload["proposal"]["quantity"]=plan["quantity"]
            from .handoff_bridge import bounded_preview
            preview,current,quantity=bounded_preview(bridge,payload,plan["report_card"],plan["quantity"],plan.get("allocation_limit",plan["allocation"]))
            if current["symbol"]!=plan["symbol"] or current["kind"]!=plan["kind"]:
                raise ValueError("Execution contract changed; prepare fresh analysis.")
            plan.update(quantity=quantity,entry=current["entry"],stop=current["stop"],target=current["target"],allocation=str(amount(current["entry"])*quantity))
            if plan["kind"]=="LONG_OPTION":option_cost+=amount(plan["allocation"])
            # Human review freezes this exact limit and quantity, so the durable
            # reservation needs only its exact notional, not preview headroom.
            plan["allocation_limit"]=plan["allocation"]
            items.append(dict(plan=plan,preview=preview))
        if sum((amount(v["plan"]["allocation"]) for v in items),Decimal(0))>capacity:
            raise ValueError("Fresh selected-ticket total exceeds the shared pool.")
        ident="HMAN-"+secrets.token_hex(8).upper();expires=self.clock()+120
        group=dict(user_id=user["id"],account_id=aid,bridge=bridge,revision=policy.get("revision"),expires=expires,items=items)
        with self.lock:
            self.groups={k:v for k,v in self.groups.items() if v["expires"]>self.clock()}
            self.groups[ident]=group
        return dict(preview_id=ident,confirmation_phrase="CONFIRM "+ident,expires_at=expires,
            mode="MANUAL",broker=account["broker"],excluded=excluded,allocated=str(sum((amount(v["plan"]["allocation"]) for v in items))),
            live_submission_enabled=all(v["preview"].get("live_submission_enabled") is True for v in items),
            items=[dict(symbol=v["plan"]["symbol"],direction=v["plan"]["direction"],kind=v["plan"]["kind"],
                action=v["preview"]["instrument"]["contracts"][0]["action"],
                quantity=v["plan"]["quantity"],entry=v["plan"]["entry"],stop=v["plan"]["stop"],target=v["plan"]["target"]) for v in items])

    def submit(self,user,aid,ident,confirmation):
        item=self.runtime.entry(user,aid);schedule=item["schedule"]
        with self.lock:
            group=self.groups.get(ident)
            if not group or group["user_id"]!=user["id"] or group["account_id"]!=aid:
                raise PermissionError("Owned Manual preview is unavailable.")
            if confirmation!="CONFIRM "+ident:raise PermissionError("Enter the exact reviewed confirmation.")
            if self.clock()>=group["expires"]:raise ValueError("Manual preview expired; prepare fresh tickets.")
            policy=schedule.policy()
            if policy["mode"]!="MANUAL" or not policy["enabled"] or policy.get("revision")!=group["revision"]:
                raise PermissionError("Schedule changed; prepare a fresh Manual review.")
            del self.groups[ident] # consume before the first possible broker action
        bridge=group["bridge"];bridge.identity();results=[]
        for value in group["items"]:
            plan,preview=value["plan"],value["preview"]
            state=bridge.exposure(policy)
            if schedule.loss_halted(state,self.runtime.now(),10000):raise PermissionError("Daily loss cutoff reached.")
            if schedule.claims.unsettled(aid):raise ValueError("An earlier submission requires reconciliation.")
            if plan["underlying"] in state["exposed_underlyings"] or float(state["used_capital"])+float(plan.get("allocation_limit",plan["allocation"]))>policy["capital"]:
                raise ValueError("Fresh exposure or shared pool changed; remaining entries withheld.")
            if amount(plan.get("allocation_limit",plan["allocation"]))>amount(state["available_funds"]):raise ValueError("Fresh funds are insufficient.")
            schedule.claims.reserve(aid,plan,cap=policy["capital"])
            auth=dict(mode="MANUAL",user_id=user["id"],preview_id=preview["preview_id"],expires_at=group["expires"],policy_revision=group["revision"])
            saved=dict(plan=plan,result=dict(preview_id=preview["preview_id"]),authorization=auth)
            with schedule.db() as db:
                db.execute("INSERT INTO receipts VALUES(?,?,?,?,?)",(plan["fingerprint"],"manual:"+ident,"SUBMITTING",json.dumps(saved),self.clock()))
            try:result=bridge.submit_prepared(plan,preview)
            except PreflightRejected as error:
                saved["result"]=dict(status="NOT_SUBMITTED",reason=str(error),orders_submitted=0)
                with schedule.db() as db:
                    db.execute("UPDATE receipts SET state=?,body=?,updated=? WHERE fingerprint=?",
                        ("NOT_SUBMITTED",json.dumps(saved),self.clock(),plan["fingerprint"]))
                schedule.claims.not_submitted(aid,plan["fingerprint"])
                raise ValueError("No order submitted: "+str(error)) from None
            except Exception:
                schedule.claims.uncertain(aid,plan["fingerprint"])
                raise ValueError("Submission outcome requires reconciliation; this Manual group will not be replayed.") from None
            saved["result"]=result;confirmed=result.get("protection_confirmed") is True
            with schedule.db() as db:
                db.execute("UPDATE receipts SET state=?,body=?,updated=? WHERE fingerprint=?",
                    ("PROTECTED" if confirmed else str(result.get("status") or "UNCERTAIN"),json.dumps(saved),self.clock(),plan["fingerprint"]))
            if confirmed:
                from .handoff_schedule import confirmed_notional
                schedule.claims.confirmed(aid,plan["fingerprint"],confirmed_notional(result))
            else:schedule.claims.uncertain(aid,plan["fingerprint"])
            results.append(result)
            if not confirmed:break
        return dict(status="SUBMITTED_AWAITING_RECONCILIATION" if len(results)<len(group["items"]) or not all(r.get("protection_confirmed") for r in results) else "BROKER_REGISTERED",
            results=results,unsubmitted=len(group["items"])-len(results),automatic_retry=False)
