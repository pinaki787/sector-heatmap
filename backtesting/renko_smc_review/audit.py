import sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backtesting/renko_regime_risk'))
import run as risk
import sensitivity_replay as replay
from smc import build_facts,allows
def main():
 risk.initialize();replay.EXITS["Fixed3_1_5"]=dict(hard=3.,target=1.5)
 facts={k:build_facts(risk.HOSTS,k) for k in (2,3)};results={}
 jobs=[(mode,name,k,bars) for mode in ("parity","quick_loss","rearm","quick_loss_rearm") for name,k,bars in (("none",2,0),("sweep",2,3))]
 jobs += [("neighbor","sweep_k3",3,3),("neighbor","sweep2",2,2),("neighbor","sweep4",2,4)]
 for mode,name,k,bars in jobs:
  rule=dict(sweep=bars)
  f=None if name=="none" else lambda sig,price:allows(facts[k][sig["timestamp"]],sig["entry_direction"],price,sig["host_atr"],rule)
  r=replay.simulate(risk.HOSTS,risk.MINUTES,risk.CONFIG,"overlap_130","Fixed3_1_5",risk.START,entry_filter=f,
   recovery="quick_loss" in mode,rearm="rearm" in mode)
  key=mode+"__"+name;r.update(mode=mode,name=name,k=k,sweep_bars=bars)
  (HERE/"trials"/f"audit__{key}.json").write_text(json.dumps(r));results[key]={a:b for a,b in r.items() if a not in ("trades","curve")}
  (HERE/"audit-results.json").write_text(json.dumps(results,indent=2))
  (HERE/"audit-job.json").write_text(json.dumps(dict(status="RUNNING",completed=len(results),total=len(jobs),heartbeat=time.time())))
  if mode=="parity":
   old=json.loads((HERE/"trials"/f"calibrated__{name}.json").read_text())
   keys=("entry_at","exit_at","entry_price","exit_price","direction","gross_points")
   assert [{k:t[k] for k in keys}for t in r["trades"]]==[{k:t[k]for k in keys}for t in old["trades"]]
  s=r["splits"]["all"]["2"];print(key,s,flush=True)
 (HERE/"audit-job.json").write_text(json.dumps(dict(status="COMPLETED",completed=len(results),total=len(jobs),heartbeat=time.time())))
if __name__=="__main__":main()
