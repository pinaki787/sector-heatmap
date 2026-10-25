"""Private persistent stdin/stdout client. A timed-out submission is never replayed."""
import json,select,secrets,subprocess,time
from threading import Lock
from .workspaces import isolated_environment

class TicketClient:
    def __init__(self,root,store,account):
        self.root,self.store,self.account=root,store,account
        self.folder=store.folder(account);self.lock=Lock();self.process=None;self.unresponsive=False
    def call(self,operation,payload):
        with self.lock:
            if self.unresponsive:raise ValueError("Ticket worker needs reconciliation; no automatic retry.")
            if self.process is None:
                self.process=subprocess.Popen([str(self.root/".venv/bin/python"),"-B","-m","sector_heatmap.handoff_execution_worker"],
                    cwd=self.folder/"source",env=isolated_environment(self.account,self.folder,self.store.path,8079),
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1)
            if self.process.poll() is not None:raise ValueError("Ticket worker exited; bind a fresh account schedule after reconciliation.")
            ident=secrets.token_hex(12)
            request=dict(id=ident,operation=operation,payload=payload)
            try:
                self.process.stdin.write(json.dumps(request,allow_nan=False)+"\n");self.process.stdin.flush()
                ready=select.select([self.process.stdout],[],[],1800 if operation=="analysis" else 120)[0]
                if not ready:raise TimeoutError()
                response=json.loads(self.process.stdout.readline())
                if response.get("id")!=ident:raise ValueError("Ticket response identity mismatch.")
            except Exception:
                self.unresponsive=True
                raise ValueError("Ticket response uncertain; no automatic order retry.") from None
            if response.get("ok") is not True:raise ValueError(response.get("error") or "Owned ticket action rejected.")
            return response["result"]
