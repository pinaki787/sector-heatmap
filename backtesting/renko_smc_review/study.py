"""Offline SMC comparison. Cancel with a CANCEL file in this folder."""
import sys,json,time,os,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backtesting/renko_regime_risk'))
import run as risk
import replay
from smc import build_facts,allows
VARIANTS={
 "none":{},"structure":dict(structure=True),"bos":dict(bos=True),"sweep":dict(sweep=3),"room":dict(room=1.5),
 "structure_sweep_room":dict(structure=True,sweep=3,room=1.5),
 "bos_sweep_room":dict(bos=True,sweep=3,room=1.5),"delay12":dict(delay=12)}
NEIGHBORS={
 "structure_k3":dict(structure=True,k=3),"bos_k3":dict(bos=True,k=3),
 "structure_sweep_room_k3":dict(structure=True,sweep=3,room=1.5,k=3),
 "bos_sweep_room_k3":dict(bos=True,sweep=3,room=1.5,k=3),
 "room_k3":dict(room=1.5,k=3),"room_1ATR":dict(room=1.),"room_2ATR":dict(room=2.),
 "sweep_1bar":dict(sweep=1),"sweep_5bars":dict(sweep=5)}
PROFILES={"existing":("Baseline","SelectedExits"),"calibrated":("overlap_130","Fixed3_1_5")}
def checkpoint(status,**kw):
 data=dict(status=status,pid=os.getpid(),heartbeat=time.time(),**kw)
 tmp=HERE/"job.tmp";tmp.write_text(json.dumps(data));tmp.replace(HERE/"job.json")
def main():
 checkpoint("RUNNING",phase="LOAD",completed=0,total=34)
 risk.initialize();replay.EXITS["Fixed3_1_5"]=dict(hard=3.,target=1.5)
 facts={k:build_facts(risk.HOSTS,k) for k in (2,3)}
 spec=json.loads((HERE/"specification.json").read_text());spec.update(variants=VARIANTS,neighbors=NEIGHBORS,
  scored_from=risk.START,scored_through=risk.day(risk.HOSTS[-1]["timestamp"]) if hasattr(risk,"day") else "2026-10-23",
  complete_sessions=len({x["timestamp"]//86400 for x in risk.HOSTS}),config=risk.CONFIG,
  source_sha256={x:hashlib.sha256((HERE/x).read_bytes()).hexdigest() for x in ("smc.py","replay.py","study.py")})
 (HERE/"specification.json").write_text(json.dumps(spec,indent=2))
 (HERE/"trials").mkdir(exist_ok=True);results={}
 for phase,variants in (("PRIMARY",VARIANTS),("NEIGHBORS",NEIGHBORS)):
  for profile,(entry,exit_name) in PROFILES.items():
   for name,rule in variants.items():
    if (HERE/"CANCEL").exists():raise InterruptedError("Cancelled by file")
    key=profile+"__"+name;start=time.time();k=rule.get("k",2)
    gate=None if name=="none" else lambda sig,price:allows(facts[k][sig["timestamp"]],sig["entry_direction"],price,sig.get("host_atr"),rule)
    r=replay.simulate(risk.HOSTS,risk.MINUTES,risk.CONFIG,entry,exit_name,risk.START,entry_filter=gate)
    r.update(profile=profile,variant=name,rule=rule,phase=phase,seconds=time.time()-start)
    r["quarters"]={str(q):replay.stats([t for t in r["trades"] if risk.calibration.block(t["entry_day"])==q],2) for q in range(8)}
    if name=="none":
     old=json.loads((HERE/f"{profile}-control.json").read_text())
     assert r["trades"]==old["trades"],"Copied lifecycle failed exact trade parity"
    (HERE/"trials"/f"{key}.json").write_text(json.dumps(r))
    results[key]={x:y for x,y in r.items() if x not in ("trades","curve")}
    (HERE/"results.json").write_text(json.dumps(results,indent=2))
    checkpoint("RUNNING",phase=phase,completed=len(results),total=34,latest=key)
    s=r["splits"]["all"]["2"];print(key,"trades",s["trades"],"PF",round(s["profit_factor"] or 0,3),"net",round(s["net_points"],2),"DD",round(s["realized_drawdown_points"],2),"loss streak",s["max_loss_streak"],flush=True)
 checkpoint("COMPLETED",phase="ALL",completed=len(results),total=34)
if __name__=="__main__":
 try:main()
 except BaseException as e:
  checkpoint("CANCELLED" if isinstance(e,(InterruptedError,KeyboardInterrupt)) else "FAILED",error=str(e));raise
