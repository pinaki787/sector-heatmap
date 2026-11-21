import sys,json,time,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"backtesting/renko_regime_risk"))
import run as risk
import replay
from zones import contexts,allowed
def main():
 risk.initialize();known=contexts(risk.HOSTS);replay.EXITS["Fixed3_1_5"]=dict(hard=3.,target=1.5)
 base={**risk.CONFIG,"calibrated_enabled":True,"calibrated_overlap_pairs":6,"calibrated_overlap_max":.4,"calibrated_stop_atr":3.,"calibrated_target_atr":1.5}
 jobs=[dict(name=f"near_{x:g}",brick=27.71,minimum=x,target=True) for x in (.5,.75,1.25,1.5,2.)]
 jobs += [dict(name=f"brick_{b:g}_{label}",brick=b,minimum=t,target=z) for b in (20.,35.) for label,t,z in (("control",None,False),("filter",1.,False),("both",1.,True))]
 results={};ages=[]
 for at,c in known.items():
  for z in c["after"].values():
   if z and z["broken_at"] is None:ages.append((at+300-z["pivot_at"])/86400)
 (HERE/"zone-age-audit.json").write_text(json.dumps(dict(maximum_active_zone_age_days=max(ages),observations=sum(x>40 for x in ages),note="FYERS cold-start 5m history normally requests 45 calendar days; a zone younger than 40 days has ample pre-pivot ATR14 warmup."),indent=2))
 for job in jobs:
  cfg={**base,"manual_brick":job["brick"],"zone_target_enabled":job["target"],"zones_family_enabled":job["target"]}
  minimum=job["minimum"];f=None if minimum is None else lambda sig,price:allowed(known[sig["timestamp"]]["after"],sig["entry_direction"],price,sig["host_atr"],minimum)
  r=replay.simulate(risk.HOSTS,risk.MINUTES,cfg,"Baseline","Fixed3_1_5",risk.START,entry_filter=f,recovery=True,rearm=True,zone_context=known,zone_exits=job["target"])
  r["job"]=job
  (HERE/"trials"/("audit__"+job["name"]+".json")).write_text(json.dumps(r))
  results[job["name"]]={k:v for k,v in r.items() if k not in ("trades","curve")}
  (HERE/"audit-results.json").write_text(json.dumps(results,indent=2))
  (HERE/"audit-job.json").write_text(json.dumps(dict(status="RUNNING",pid=os.getpid(),heartbeat=time.time(),completed=len(results),total=len(jobs))))
  print(job["name"],r["splits"]["all"]["2"],flush=True)
 (HERE/"audit-job.json").write_text(json.dumps(dict(status="COMPLETED",pid=os.getpid(),heartbeat=time.time(),completed=len(results),total=len(jobs))))
if __name__=="__main__":main()
