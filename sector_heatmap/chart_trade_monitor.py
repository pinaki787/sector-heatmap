"""Account-owned background broker reads; never places, modifies or cancels orders."""
import logging
import threading
import time

LOGGER=logging.getLogger(__name__)


class ChartTradeMonitor:
    def __init__(self,service,*,clock=time.monotonic):
        self.service=service
        self.clock=clock
        self.stop_event=threading.Event()
        self.thread=None
        self.next_due={}

    def run_once(self):
        if self.stop_event.is_set() or not self.service.reconciliation_lock.acquire(blocking=False):
            return 0
        try:
            account=self.service.account
            pending=self.service.previews.pending(account["id"],account["broker"])
            keys={key for _,key in pending}
            self.next_due={key:value for key,value in self.next_due.items() if key in keys}
            due=[(owner,key) for owner,key in pending if self.next_due.get(key,0)<=self.clock()]
            if not due:return 0
            batch_error=False;adapter=None
            try:
                adapter=self.service.adapter_factory(account)
                begin=getattr(adapter,"begin_reconciliation_batch",None)
                if begin:begin()
            except Exception:batch_error=True
            checked=0
            for owner,key in due:
                if self.stop_event.is_set():break
                try:
                    if batch_error:raise ValueError("Native account snapshot unavailable.")
                    self.service.previews.reconcile(owner,key,adapter)
                except Exception:
                    self.service.previews.record_read_failure(owner,key)
                    self.next_due[key]=self.clock()+30
                else:self.next_due[key]=self.clock()+15
                checked+=1
            return checked
        finally:self.service.reconciliation_lock.release()

    def _run(self):
        while not self.stop_event.is_set():
            try:self.run_once()
            except Exception as error:
                # Never log broker payloads, credentials or raw native exceptions.
                LOGGER.warning("Chart broker reconciliation unavailable: %s",type(error).__name__)
            self.stop_event.wait(5)

    def start(self):
        if self.thread and self.thread.is_alive():return
        if self.stop_event.is_set():return
        self.thread=threading.Thread(target=self._run,name="chart-order-reconcile-"+self.service.account["id"],daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=1)
