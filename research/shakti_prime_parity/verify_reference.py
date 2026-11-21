"""Compare independently aggregated candle evidence against exported reference plots."""
import csv,json,math
from pathlib import Path
root=Path(__file__).parent
r5=list(csv.DictReader((root/"btcusd_5m_diagnostic_20261104.csv").open()))[:-1]
r2=list(csv.DictReader((root/"btcusd_2m_diagnostic_20261104.csv").open()))[:-1]
# Crypto reset 02:30 IST; 30m source. Evaluate only sessions whose reset is in fixture.
groups={}
for r in r5:groups.setdefault(int(r["time"])//1800*1800,[]).append(r)
reset=next(i for i,r in enumerate(r5) if (int(r["time"])+19800)%86400==9000)
first=int(r5[reset]["time"]);hi=lo=None;expected={}
# Historical HTF values publish on the closing chart bar; until then carry prior output.
published_hi=float(r5[reset-1]["LOCKED RED BAR HIGH"])
published_lo=float(r5[reset-1]["LOCKED RED BAR LOW"])
for t,g in sorted(groups.items()):
 if t<first:continue
 complete=len(g)==6 and int(g[-1]["time"])==t+1500
 if hi is None and t>first and complete and float(g[-1]["close"])<float(g[0]["open"]):
  hi=max(float(r["high"]) for r in g);lo=min(float(r["low"]) for r in g)
 for j,r in enumerate(g):
  if complete and j==5:published_hi,published_lo=hi,lo
  expected[int(r["time"])]=(published_hi,published_lo)
errors=[];n=0
for r in r5[reset:]:
 hi,lo=expected[int(r["time"])]
 for k,v in [("LOCKED RED BAR HIGH",hi),("LOCKED RED BAR LOW",lo),("44%",None if hi is None else lo+(hi-lo)*.44),("50%",None if hi is None else lo+(hi-lo)*.50),("56%",None if hi is None else lo+(hi-lo)*.56)]:
  actual=float(r[k]) if r[k] else None;n+=1
  if (v is None)!=(actual is None) or (v is not None and abs(v-actual)>1e-8):errors.append(dict(time=r["time"],column=k,expected=v,actual=actual))
sma_errors=[];sma_count=0
for i in range(199,len(r2)):
 for price,k in [("high","200 SMA High — 2m"),("low","200 SMA Low — 2m")]:
  expected_value=sum(float(r[price]) for r in r2[i-199:i+1])/200
  actual=float(r2[i][k]);sma_count+=1
  if abs(expected_value-actual)>1e-8:sma_errors.append(dict(time=r2[i]["time"],column=k,error=actual-expected_value))
mapping_errors=[];mapping_count=0
for r in r5:
 t=int(r["time"]);source=[s for s in r2 if t<int(s["time"])+120<=t+300]
 if not source:continue
 for k in ["200 SMA High — 2m","200 SMA Low — 2m"]:
  mapping_count+=1
  if abs(float(source[-1][k])-float(r[k]))>1e-8:mapping_errors.append(dict(time=r["time"],column=k))
result=dict(reference_values_compared=n,reference_mismatches=errors,sma_values_compared=sma_count,sma_mismatches=sma_errors,mapping_values_compared=mapping_count,mapping_mismatches=mapping_errors,limitation="Single BTC session. Recalculated historical 30m values publish on source close. Earlier cached export differs; real-time/reload stability remains unverified. Initial partial session excluded; no inferred Shakti/Supertrend parity.")
(root/"reference_validation.json").write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
assert not errors and not sma_errors and not mapping_errors
