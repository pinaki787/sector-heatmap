"""Paired day-block bootstrap and observed entry-volatility slices."""
import csv,json,random,statistics
from pathlib import Path
OUT=Path(__file__).resolve().parent
rows=list(csv.DictReader((OUT/'trade_details_final.csv').open()));baseline={r['at']:r for r in rows if r['variant']=='baseline'}
rng=random.Random(20261007);output=[]
for variant in sorted({r['variant'] for r in rows}-{'baseline'}):
 for split in ('development','heldout'):
  ts=[r for r in rows if r['variant']==variant and r['split']==split];days={}
  for r in ts:days[r['day']]=days.get(r['day'],0)+float(r['net_points'])-float(baseline[r['at']]['net_points'])
  values=list(days.values());samples=sorted(sum(rng.choice(values) for _ in values) for _ in range(2000)) if values else []
  output.append(dict(variant=variant,split=split,paired_trades=len(ts),days=len(values),delta_total=round(sum(values),3),bootstrap_p025=round(samples[49],3) if samples else None,bootstrap_p975=round(samples[1949],3) if samples else None))
with (OUT/'paired_uncertainty.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
analyzed=json.loads((OUT/'analyzed.json').read_text());bytime={str(int(r['timestamp'])):r for r in analyzed};regimes=[]
for variant in sorted({r['variant'] for r in rows}):
 for regime in ('low_volatility','normal_volatility','high_volatility'):
  ts=[]
  for r in rows:
   if r['variant']!=variant or r['split']!='heldout':continue
   source=bytime.get(str(int(float(r['at']))-60),{});ratio=source.get('volatility_ratio')
   label='low_volatility' if ratio is not None and ratio<.8 else 'high_volatility' if ratio is not None and ratio>1.2 else 'normal_volatility'
   if label==regime:ts.append(r)
  regimes.append(dict(variant=variant,regime=regime,trades=len(ts),net_points=round(sum(float(r['net_points']) for r in ts),3),early_exits=sum(int(r['exit_i'])<int(r['baseline_end']) for r in ts)))
with (OUT/'regimes.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(regimes[0]));w.writeheader();w.writerows(regimes)
print('paired uncertainty and volatility slices saved')
