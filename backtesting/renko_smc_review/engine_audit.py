"""Use the currently installed Engine calibrated gate, including its rearming."""
import sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backtesting/renko_regime_risk'))
import run as risk
import sensitivity_replay as replay
from smc import build_facts,allows
def main():
 risk.initialize();replay.EXITS["Fixed3_1_5"]=dict(hard=3.,target=1.5)
 config={**risk.CONFIG,"calibrated_enabled":True,"calibrated_overlap_pairs":6,"calibrated_overlap_max":.4,"calibrated_stop_atr":3.,"calibrated_target_atr":1.5}
 facts={k:build_facts(risk.HOSTS,k) for k in (2,3)}
 results=json.loads((HERE/"engine-audit-results.json").read_text()) if (HERE/"engine-audit-results.json").exists() else {}
 rules={"none":{},"sweep":dict(sweep=3),"structure":dict(structure=True),"bos":dict(bos=True),"room":dict(room=1.5),"structure_sweep_room":dict(structure=True,sweep=3,room=1.5),"bos_sweep_room":dict(bos=True,sweep=3,room=1.5),"delay12":dict(delay=12),"room1":dict(room=1.),"room2":dict(room=2.),"sweep2":dict(sweep=2),"sweep4":dict(sweep=4),"sweep5":dict(sweep=5),"sweep_k3":dict(sweep=3,k=3)}
 for rearm in (False,True):
  for variant,rule in rules.items():
   if rearm and variant not in ("none","sweep"):continue
   key=("rearm_" if rearm else "")+variant
   if key in results:continue
   k=rule.get("k",2)
   f=None if variant=="none" else lambda sig,price:allows(facts[k][sig["timestamp"]],sig["entry_direction"],price,sig["host_atr"],rule)
   r=replay.simulate(risk.HOSTS,risk.MINUTES,config,"Baseline","Fixed3_1_5",risk.START,entry_filter=f,recovery=True,rearm=rearm)
   key=("rearm_" if rearm else "")+variant
   (HERE/"trials"/f"engine__{key}.json").write_text(json.dumps(r))
   results[key]={a:b for a,b in r.items() if a not in ("trades","curve")}
   (HERE/"engine-audit-results.json").write_text(json.dumps(results,indent=2))
   print(key,r["splits"]["all"]["2"],flush=True)
if __name__=="__main__":main()
