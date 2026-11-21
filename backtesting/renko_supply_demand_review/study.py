"""Offline supply/demand tests. No broker, credentials or trading-setting writes."""
import sys,json,time,os,hashlib
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"backtesting/renko_regime_risk"))
import run as risk
import replay
from zones import contexts,allowed
def checkpoint(status,**kw):
 d=dict(status=status,pid=os.getpid(),heartbeat=time.time(),**kw);tmp=HERE/"job.tmp";tmp.write_text(json.dumps(d));tmp.replace(HERE/"job.json")
def requests():
 jobs=[dict(name="calibrated_control",target=False,minimum=None,replace=False,rearm=False)]
 for threshold in (.5,1.,1.5,2.):
  jobs.append(dict(name=f"filter_{threshold:g}ATR",target=False,minimum=threshold,replace=False,rearm=False))
 jobs.append(dict(name="zone_target_added",target=True,minimum=None,replace=False,rearm=False))
 for threshold in (.5,1.,1.5,2.):
  jobs.append(dict(name=f"zone_target_added_filter_{threshold:g}ATR",target=True,minimum=threshold,replace=False,rearm=False))
 jobs.append(dict(name="zone_target_replaces_ATR",target=True,minimum=None,replace=True,rearm=False))
 for threshold in (.5,1.,1.5,2.):
  jobs.append(dict(name=f"zone_target_replaces_ATR_filter_{threshold:g}ATR",target=True,minimum=threshold,replace=True,rearm=False))
 for target,replace in ((False,False),(True,False),(True,True)):
  name=("zone_replaces" if replace else "zone_added" if target else "filter_only")+"_rearm_1ATR"
  jobs.append(dict(name=name,target=target,minimum=1.,replace=replace,rearm=True))
 return jobs
def main():
 jobs=requests();checkpoint("RUNNING",phase="LOAD",completed=0,total=len(jobs));risk.initialize()
 known=contexts(risk.HOSTS);replay.EXITS["Fixed3_1_5"]=dict(hard=3.,target=1.5)
 base={**risk.CONFIG,"calibrated_enabled":True,"calibrated_overlap_pairs":6,"calibrated_overlap_max":.4,"calibrated_stop_atr":3.,"calibrated_target_atr":1.5}
 spec=json.loads((HERE/"specification.json").read_text())
 spec.update(jobs=jobs,scoring_start=risk.START,scoring_end=replay.day(risk.HOSTS[-1]["timestamp"]),
  sessions=len({replay.day(x["timestamp"]) for x in risk.HOSTS}),base_config=base,
  data_sha256={x:hashlib.sha256((ROOT/"data/backtesting/nifty50-fyers-2024-10-25_2026-10-24"/x).read_bytes()).hexdigest() for x in ("nifty50_1m.csv","nifty50_5m.csv")},
  source_sha256={x:hashlib.sha256((HERE/x).read_bytes()).hexdigest() for x in ("zones.py","replay.py","study.py")})
 (HERE/"specification.json").write_text(json.dumps(spec,indent=2));(HERE/"trials").mkdir(exist_ok=True);results={}
 for job in jobs:
  if (HERE/"CANCEL").exists():raise InterruptedError("Cancelled")
  start=time.time();minimum=job["minimum"]
  filter_fn=None if minimum is None else lambda sig,price:allowed(known[sig["timestamp"]]["after"],sig["entry_direction"],price,sig["host_atr"],minimum)
  cfg={**base,"zones_family_enabled":job["target"],"zone_target_enabled":job["target"]}
  r=replay.simulate(risk.HOSTS,risk.MINUTES,cfg,"Baseline","Fixed3_1_5",risk.START,entry_filter=filter_fn,recovery=True,rearm=job["rearm"],zone_context=known,zone_exits=job["target"],remove_atr_target=job["replace"])
  r.update(job=job,seconds=time.time()-start,exit_reasons=dict(Counter(t["reason"] for t in r["trades"])))
  r["quarters"]={str(q):replay.stats([t for t in r["trades"] if risk.calibration.block(t["entry_day"])==q],2) for q in range(8)}
  if job["name"]=="calibrated_control":
   old=json.loads((ROOT/"backtesting/renko_smc_review/trials/engine__none.json").read_text())
   keys=("entry_at","exit_at","entry_price","exit_price","direction","gross_points")
   assert [{k:t[k] for k in keys}for t in r["trades"]]==[{k:t[k] for k in keys}for t in old["trades"]],"Control trade parity failed"
   r["exact_control_parity"]=True
  (HERE/"trials"/(job["name"]+".json")).write_text(json.dumps(r))
  results[job["name"]]={k:v for k,v in r.items() if k not in ("trades","curve")}
  (HERE/"results.json").write_text(json.dumps(results,indent=2));checkpoint("RUNNING",phase="REPLAY",completed=len(results),total=len(jobs),latest=job["name"])
  print(job["name"],r["splits"]["all"]["2"],"zone exits",sum(v for k,v in r["exit_reasons"].items() if k.startswith("SD_")),flush=True)
 checkpoint("COMPLETED",completed=len(results),total=len(jobs))
if __name__=="__main__":
 try:main()
 except BaseException as e:
  checkpoint("CANCELLED" if isinstance(e,(InterruptedError,KeyboardInterrupt)) else "FAILED",error=str(e));raise
