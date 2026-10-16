"""In-memory bounded read-only work queue; never wraps order operations."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import secrets
from contextvars import copy_context

class AdvisoryJobs:
    def __init__(self, capacity=4, ttl=600):
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix="advisory")
        self.lock=threading.Lock()
        self.jobs={}
        self.capacity=capacity
        self.ttl=ttl

    def request(self, payload, calculate):
        with self.lock:
            now=time.monotonic()
            for key,(future,created) in list(self.jobs.items()):
                if future.done() and now-created>self.ttl:
                    del self.jobs[key]
            key=payload.get("analysis_job")
            if key:
                if key not in self.jobs:
                    raise ValueError("Analysis job expired or belongs to another workspace. Start a fresh analysis.")
                future,_=self.jobs[key]
            else:
                if len(self.jobs)>=self.capacity:
                    completed=[k for k,(f,t) in self.jobs.items() if f.done()]
                    if completed:del self.jobs[completed[0]]
                    else:raise ValueError("This workspace already has analysis in progress. Wait for it to finish.")
                key=secrets.token_urlsafe(24)
                future=self.pool.submit(copy_context().run,calculate,dict(payload))
                self.jobs[key]=(future,now)
        if future.done():
            return future.result()
        return {"status":"ANALYZING","analysis_job":key,"message":"Fetching completed-candle evidence; analysis remains active."}
