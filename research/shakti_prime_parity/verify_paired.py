"""Compare independently exported indicator plots, retaining stale-cache diagnostics separately."""
import csv,json
from pathlib import Path
root=Path(__file__).parent
plots=["LOCKED RED BAR HIGH","LOCKED RED BAR LOW","44%","50%","56%","200 SMA High — 2m","200 SMA Low — 2m"]
samples=[
 ("btcusd_2m_paired_20261104.csv",plots),
 ("btcusd_5m_paired_20261104.csv",plots),
 ("btcusd_5m_visual_paired_reload_20261104.csv",plots),
 ("btcusd_30m_visual_paired_20261104.csv",plots+["5 SMA Close — 30m+"]),
 ("nifty_5m_visual_paired_20261104.csv",plots),
]
def compare(name,keys):
 with (root/name).open() as f:
  r=csv.reader(f);headers=next(r);rows=list(r)[:-1]
 result=[]
 for key in keys:
  ix=[i for i,v in enumerate(headers) if v==key]
  assert len(ix)==2,(name,key,ix)
  errors=[]
  for row in rows:
   a,b=[row[i] for i in ix]
   if a!=b and (not a or not b or abs(float(a)-float(b))>1e-8):
    errors.append(dict(time=row[0],first_plot=a,second_plot=b))
  result.append(dict(plot=key,compared=len(rows),mismatches=errors))
 return dict(sample=name,plots=result)
validated=[compare(*s) for s in samples]
diagnostics=[compare(n,plots) for n in [
 "btcusd_5m_visual_paired_wide_20261104.csv",
 "btcusd_5m_visual_paired_recalc_20261104.csv",
]]
report=dict(validated_historical_samples=validated,pre_reload_diagnostics=diagnostics,
 limitations=["Excludes final row as potentially forming.","Pre-reload exports retained four recent SMA differences; full tab reload removed these in the fresh overlapping sample.","Does not certify realtime state, colors, objects, signals, Renko, Shakti, order blocks or dashboards."])
(root/"paired_validation.json").write_text(json.dumps(report,indent=2))
for group,items in [("historical",validated),("pre-reload diagnostic",diagnostics)]:
 for r in items:
  count=sum(p["compared"] for p in r["plots"]);errors=sum(len(p["mismatches"]) for p in r["plots"])
  print(group,r["sample"],count,"compared",errors,"mismatches")
assert not any(p["mismatches"] for r in validated for p in r["plots"])
