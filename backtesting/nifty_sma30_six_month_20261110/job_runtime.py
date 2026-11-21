import json,os,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
state={'job_id':'nifty-sma30-5m-six-month-20261110','pid':os.getpid(),'status':'RUNNING','stage':'initializing','started_epoch':time.time()}
lock=threading.Lock();stop=threading.Event()
def write():
 with lock:
  obj=dict(state);obj['heartbeat_epoch']=time.time();obj['elapsed_seconds']=round(time.time()-obj['started_epoch'],2)
 dest=ROOT/'job_status.json';tmp=ROOT/'job_status.tmp';tmp.write_text(json.dumps(obj,indent=2));tmp.replace(dest)
def progress(stage=None,**items):
 with lock:
  if stage is not None:state['stage']=stage
  state.update(items)
def heartbeats():
 while not stop.wait(5):
  write()
threading.Thread(target=heartbeats,daemon=True).start()
write()
