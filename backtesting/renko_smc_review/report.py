import json,csv,html
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def main():
 engine=read("engine-audit-results.json");assert len(engine)==16
 spec=read("specification.json");baseline=read("trials/engine__none.json");candidate=read("trials/engine__sweep.json")
 days=sorted({x["day"] for x in baseline["curve"]});uncertainty=[]
 for drag in (2,4):
  def daily(r):
   a=dict.fromkeys(days,0.)
   for t in r["trades"]:a[t["entry_day"]]+=t["gross_points"]-drag
   return a
  a=daily(baseline);b=daily(candidate);v=np.array([b[d]-a[d] for d in days]);rng=np.random.default_rng(2601026);sims=[]
  for i in range(5000):
   starts=rng.integers(0,len(v),size=(len(v)+4)//5);idx=((starts[:,None]+np.arange(5))%len(v)).flatten()[:len(v)];sims.append(float(v[idx].sum()))
  uncertainty.append(dict(drag=drag,observed_delta_points=float(v.sum()),block_sessions=5,replications=5000,interval_95_points=np.quantile(sims,[.025,.975]).tolist()))
 eligible=[]
 for name,r in engine.items():
  if name in ("none","rearm_none","delay12"):continue
  good=True
  for y in ("earlier","latest"):
   s=r["splits"][y]["2"];b=engine["none"]["splits"][y]["2"]
   good &= s["trades"]>=40 and s["net_points"]>b["net_points"] and s["realized_drawdown_points"]<b["realized_drawdown_points"] and r["splits"][y]["4"]["net_points"]>0
  a=r["splits"]["all"]["2"];b=engine["none"]["splits"]["all"]["2"]
  good &= a["max_loss_streak"]<b["max_loss_streak"] and a["max_nonpositive_streak"]<b["max_nonpositive_streak"]
  if good:eligible.append(name)
 summary=dict(conclusion="No SMC variant established joint improvement in profit, drawdown and losing streaks.",eligible=eligible,
  comparisons=dict(archived_compatible=34,lifecycle_sensitivity=11,current_engine=16),confidence=uncertainty,
  headline={k:engine[k]["splits"]["all"]["2"] for k in ("none","sweep","structure")})
 (HERE/"conclusion.json").write_text(json.dumps(summary,indent=2))
 records=[]
 for group,data in (("Current engine",engine),("Archived-compatible",read("results.json")),("Lifecycle sensitivity",read("audit-results.json"))):
  for name,r in data.items():
   for year,costs in r["splits"].items():
    for drag,s in costs.items():records.append(dict(group=group,name=name,year=year,drag=drag,**s))
 with (HERE/"all-metrics.csv").open("w") as f:
  w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
 for name in ("none","sweep","structure"):
  r=read(f"trials/engine__{name}.json")
  with (HERE/f"{name}-trades.csv").open("w") as f:
   keys=["entry_at","entry_day","entry_price","direction","exit_at","exit_price","reason","gross_points"]
   w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore");w.writeheader();w.writerows(r["trades"])
 template=(HERE/"template.html").read_text()
 for marker,value in (("RECORDS",json.dumps(records).replace("<","\\u003c")),("SUMMARY",html.escape(json.dumps(summary,indent=2))),("HASHES",html.escape(json.dumps(spec["data_sha256"],indent=2)))):
  template=template.replace("@@"+marker+"@@",value)
 (HERE/"report.html").write_text(template)
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
