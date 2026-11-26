"""Conditional chart controller, installed only by an explicit service factory."""
from .chart_trade_admission import entry_lock
from .chart_trade_plan import ChartTradePlan, confirm_plan
from .chart_trade_dhan_conditions import DhanChartConditions
from .chart_trade_dhan_worker import DhanConditionalWorker


class DhanConditionalController:
    def __init__(self,service,*,tick_reader,expiry_resolver,enabled,worker_factory=DhanConditionalWorker):
        if service.account.get("broker")!="DHAN":
            raise PermissionError("Dhan conditional controller requires a Dhan account.")
        self.service=service;self.tick_reader=tick_reader;self.expiry_resolver=expiry_resolver
        self.enabled=enabled
        self.conditions=DhanChartConditions(service.previews.path,clock=service.previews.clock)
        self.worker=worker_factory(service.account,self.conditions,
            adapter_factory=lambda:service.adapter_factory(service.account),
            tick_reader=tick_reader,enabled=lambda:bool(service.account.get("live_enabled") and enabled() is True))

    def arm(self,owner,payload,adapter):
        key=payload.get("preview_id")
        if (payload.get("mode")!="LIVE" or payload.get("confirmation")!="CONFIRM "+str(key)
                or self.enabled() is not True or not self.service.account.get("live_enabled")
                or adapter.live_enabled() is not True):
            raise PermissionError("Confirm this enabled LIVE Dhan conditional entry.")
        with adapter.execution.lock:
            with entry_lock("DHAN",folder=adapter.execution.folder):
                record=self.service.previews.inspect(owner,key)
                if record["status"]!="PREVIEW":
                    return record["result"] or record
                plan=ChartTradePlan(**record["plan"])
                if plan.broker!="DHAN" or plan.entry_type!="STOP_LIMIT":
                    raise ValueError("This conditional route requires a Dhan stop-limit preview.")
                refreshed=adapter.refresh(plan)
                confirm_plan(plan,refreshed,"CONFIRM "+plan.fingerprint(),
                    expires_at=record["expires_at"],now=self.service.previews.clock())
                if self.enabled() is not True or adapter.live_enabled() is not True:
                    raise PermissionError("Dhan execution was disabled during confirmation.")
                tick=self.tick_reader(plan.symbol)
                expires=self.expiry_resolver(plan,adapter.last_preflight,self.service.previews.clock())
                self.conditions.arm(owner,key,payload["confirmation"],tick=tick,
                    expires_at=expires,mode="LIVE",enabled=True)
        # Starting is a consequence only of this explicit confirmed arm.
        # Construction and ordinary previews/status reads never start it.
        try:self.worker.start()
        except Exception:
            self.conditions.require_review(owner,key,"Conditional monitoring is unavailable; check order status and review before arming again.")
            raise ValueError("Conditional monitoring could not start. Check chart order status before another action.") from None
        return self.service.previews.inspect(owner,key)["result"]

    def cancel(self,owner,preview_id):
        self.conditions.cancel_unclaimed(owner,preview_id)
        return self.service.previews.inspect(owner,preview_id)["result"]

    def recover_waiting(self):
        for owner,key,_ in self.conditions.pending(self.service.account["id"]):
            self.conditions.require_review(owner,key,"Chart service restarted. Review this unsubmitted conditional entry before arming again.")

    def close(self):
        self.worker.close()
