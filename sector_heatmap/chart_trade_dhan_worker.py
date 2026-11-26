"""Explicitly started Dhan conditional worker; no automatic restart submissions."""
import logging
import threading
from .chart_trade_admission import entry_lock, ChartOrderNotSent

LOGGER=logging.getLogger(__name__)


class DhanConditionalWorker:
    def __init__(self,account,conditions,*,adapter_factory,tick_reader,enabled):
        if account.get("broker")!="DHAN":
            raise PermissionError("A selected Dhan account is required.")
        self.account=dict(account);self.conditions=conditions
        self.adapter_factory=adapter_factory;self.tick_reader=tick_reader;self.enabled=enabled
        self.stop_event=threading.Event();self.lock=threading.Lock();self.thread=None

    def run_once(self):
        if self.stop_event.is_set() or not self.lock.acquire(blocking=False):return 0
        try:
            handled=0
            for owner,key,plan in self.conditions.pending(self.account["id"]):
                if self.stop_event.is_set():break
                try:allowed=self.enabled() is True
                except Exception:allowed=False
                if not allowed:
                    self.conditions.require_review(owner,key,"Dhan conditional execution was disabled; review before arming again.")
                    handled+=1;continue
                try:tick=self.tick_reader(plan.symbol)
                except Exception:
                    self.conditions.require_review(owner,key,"Fresh Dhan broker ticks are unavailable; review before arming again.")
                    handled+=1;continue
                state=self.conditions.observe(owner,key,tick)
                handled+=1
                if state["state"]["status"]!="TRIGGERED":continue
                try:
                    adapter=self.adapter_factory()
                    if adapter.account_id!=self.account["id"] or adapter.broker!="DHAN":
                        raise PermissionError("Dhan conditional adapter differs from this account.")
                    allowed=adapter.live_enabled() is True
                except Exception:
                    self.conditions.require_review(owner,key,"The selected Dhan execution account is unavailable; review before arming again.")
                    continue
                if not allowed:
                    self.conditions.require_review(owner,key,"Dhan account execution permission changed; review before arming again.")
                    continue
                # Match native/manual lock order, and hold admission through
                # claim, final preflight and one native invocation.
                with adapter.execution.lock:
                    with entry_lock("DHAN",folder=adapter.execution.folder):
                        if self.stop_event.is_set():break
                        try:tick=self.tick_reader(plan.symbol)
                        except Exception:
                            self.conditions.require_review(owner,key,"Fresh Dhan broker ticks became unavailable before submission.")
                            continue
                        try:claim=self.conditions.claim(owner,key,tick=tick)
                        except ValueError:
                            local=self.conditions.inspect(owner,key)["state"]["status"]
                            if local in {"REVIEW_REQUIRED","EXPIRED"}:continue
                            raise
                        if claim is None:continue
                        try:
                            if self.enabled() is not True or adapter.live_enabled() is not True:
                                raise ChartOrderNotSent("Dhan conditional execution was disabled before placement.")
                            refreshed=adapter.refresh_triggered(plan,preview_id=key)
                        except Exception:
                            # Refresh is read-only: no native placement was invoked.
                            result=dict(status="REJECTED",order_submitted=False)
                        else:
                            try:
                                if self.stop_event.is_set() or self.enabled() is not True:
                                    raise ChartOrderNotSent("Dhan conditional worker stopped before placement.")
                                result=adapter.submit_bracket(refreshed,idempotency_key=key)
                            except ChartOrderNotSent:
                                result=dict(status="REJECTED",order_submitted=False)
                            except Exception:
                                # Once native invocation might have started, no
                                # retry; the existing broker monitor owns recovery.
                                result=dict(status="SUBMISSION_UNCERTAIN")
                        self.conditions.outcome(owner,key,claim["claim_token"],result)
            return handled
        finally:self.lock.release()

    def _run(self):
        while not self.stop_event.is_set():
            try:self.run_once()
            except Exception as error:
                LOGGER.warning("Dhan conditional worker unavailable: %s",type(error).__name__)
            self.stop_event.wait(.25)

    def start(self):
        if self.stop_event.is_set() or self.thread and self.thread.is_alive():return
        self.thread=threading.Thread(target=self._run,name="dhan-chart-conditions-"+self.account["id"],daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=1)
