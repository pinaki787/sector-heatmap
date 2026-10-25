"""Private, bounded transport/pipeline lifecycle evidence. No credentials or posts."""
import json,os,tempfile,time,threading
from pathlib import Path
from copy import deepcopy

def synchronized(method):
 def call(self,*args,**kwargs):
  with self.lock:return method(self,*args,**kwargs)
 return call

class Lifecycle:
 def __init__(self,path,clock=time.time):
  self.path=Path(path);self.clock=clock;self.lock=threading.RLock()
  self.data=json.loads(self.path.read_text()) if self.path.exists() else {"state":"STOPPED","reason":"NOT_STARTED","message":"Explicit start required.","heartbeat":None,"events":[]}
  if self.data.get("state")=="RUNNING":self.record("STOPPED","PROCESS_RESTART","Process restarted; explicit start required. No replay.")
 @synchronized
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix=".lifecycle-")
  try:
   with os.fdopen(fd,"w") as out:os.fchmod(out.fileno(),0o600);json.dump(self.data,out);out.flush();os.fsync(out.fileno())
   os.replace(tmp,self.path)
  finally:
   if Path(tmp).exists():os.unlink(tmp)
 @synchronized
 def record(self,state,reason,message):
  now=self.clock();self.data.update(state=state,reason=reason,message=message,changed_at=now)
  self.data["events"]=(self.data.get("events",[])+[{"at":now,"state":state,"reason":reason,"message":message}])[-30:]
  self.save()
 @synchronized
 def heartbeat(self):
  self.data["heartbeat"]=self.clock();self.save()
 @synchronized
 def status(self):return deepcopy(self.data)
