import json,csv,html,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(n):return json.loads((HERE/n).read_text())
def main():
 primary=read("results.json");audit=read("audit-results.json");assert len(primary)==18 and len(audit)==11
 names=("calibrated_control","zone_target_added","filter_only_rearm_1ATR","zone_added_rearm_1ATR")
 baseline=read("trials/calibrated_control.json");candidate=read("trials/zone_added_rearm_1ATR.json")
 days=sorted({x["day"] for x in baseline["curve"]});confidence=[]
 for drag in (2,4):
  def daily(r):
   v=dict.fromkeys(days,0.)
   for t in r["trades"]:v[t["entry_day"]]+=t["gross_points"]-drag
   return v
  a=daily(baseline);b=daily(candidate);delta=np.array([b[d]-a[d] for d in days]);rng=np.random.default_rng(261026);samples=[]
  for i in range(5000):
   starts=rng.integers(0,len(days),size=(len(days)+4)//5);idx=((starts[:,None]+np.arange(5))%len(days)).flatten()[:len(days)];samples.append(float(delta[idx].sum()))
  confidence.append(dict(friction_points=drag,observed_net_improvement_points=float(delta.sum()),interval_95_points=np.quantile(samples,[.025,.975]).tolist(),replications=5000,session_block=5))
 summary=dict(scope="Underlying NIFTY index-point proxy, not actual option profits. Scored 4 Nov 2024–23 Oct 2026.",comparisons=29,
 conclusion="Promising risk-first candidate: retain calibrated fixed ATR protection and add current zone rejection exit plus 1ATR opposing-zone entry buffer with rejected-setup rearming. Benefits are historical; streak and profit gains are threshold-dependent.",
 rule=dict(entry="Long: skip inside active supply or <1 completed ATR below its near edge; short: mirror for demand. No opposing zone does not block. Rejected qualifications may rearm later.",
 exit="Existing completed-five-minute zone rejection/not-broken rule added alongside fixed 3ATR stop, 1.5ATR target and selected exits."),
 headline={n:primary[n]["splits"]["all"]["2"] for n in names},
 years={y:{n:primary[n]["splits"][y]["2"] for n in names} for y in ("earlier","latest")},
 higher_friction={n:primary[n]["splits"]["all"]["4"] for n in names},
 minute_close_drawdown={n:primary[n]["minute_close_drawdown_by_year"] for n in names},
 confidence=confidence,zone_age=read("zone-age-audit.json"),control_exact_parity=primary["calibrated_control"]["exact_control_parity"],
 caveats=["Archive already repeatedly used, no fresh holdout.","Most primary net profit uplift comes from latest year; earlier year is nearly unchanged.",
 "0.75ATR buffer removes net-profit uplift; 1.25/1.5ATR buffers do not shorten the maximum loss streak.",
 "Removing fixed ATR target worsens loss streak/drawdown for combined setup.","No production settings or runners modified."])
 b=summary["headline"][names[0]];c=summary["headline"][names[-1]]
 summary["primary_changes"]=dict(net_pct=100*(c["net_points"]/b["net_points"]-1),drawdown_reduction_pct=100*(1-c["realized_drawdown_points"]/b["realized_drawdown_points"]),loss_streak_from=b["max_loss_streak"],loss_streak_to=c["max_loss_streak"])
 summary["caveats"] += ["At 4-point friction the longest losing streak is 7 for both control and combined candidate.","Exploratory bootstrap interval includes no net-profit improvement."]
 (HERE/"conclusion.json").write_text(json.dumps(summary,indent=2))
 rows=[]
 for group,data in (("Primary",primary),("Robustness",audit)):
  for n,r in data.items():
   for year,costs in r["splits"].items():
    for drag,s in costs.items():rows.append(dict(group=group,name=n,year=year,drag=drag,**s))
 with (HERE/"all-metrics.csv").open("w") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 for n in names:
  trades=read("trials/"+n+".json")["trades"]
  with (HERE/(n+"-trades.csv")).open("w") as f:
   keys=["entry_at","entry_day","entry_price","direction","exit_at","exit_price","reason","gross_points"]
   w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore");w.writeheader();w.writerows(trades)
 text=(HERE/"template.html").read_text().replace("@@RECORDS@@",json.dumps(rows).replace("<","\\u003c")).replace("@@SUMMARY@@",html.escape(json.dumps(summary,indent=2)))
 (HERE/"report.html").write_text(text)
 spec=read("specification.json")
 spec["source_checksums"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/"strategies/renko_supertrend/zone_target.py",ROOT/"strategies/renko_supertrend/signals.py",ROOT/"strategies/renko_supertrend/calibrated.py",HERE/"study.py",HERE/"replay.py",HERE/"zones.py",HERE/"audit.py"]}
 (HERE/"specification.json").write_text(json.dumps(spec,indent=2))
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
