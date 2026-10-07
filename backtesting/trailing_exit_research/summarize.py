import csv,json,statistics,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
r=list(csv.DictReader((OUT/'results_final.csv').open()));output=[]
for arm in ('preserve_exits','replace_EMA_research_only'):
 for slip in ('0','0.005','0.01','0.02'):
  for split in ('development','heldout','2026-07','2026-08','2026-09','2026-10'):
   subset=[x for x in r if x['arm']==arm and x['slippage']==slip and x['split']==split]
   baseline=next(x for x in subset if x['variant']=='baseline')
   for family in ('current','structure_1','structure_5','hybrid_20_30','hybrid_2.5_10'):
    if family=='current':f=[x for x in subset if x['family']=='current']
    elif family.startswith('structure_'):f=[x for x in subset if x['variant'].startswith(family+'_')]
    elif family=='hybrid_20_30':f=[x for x in subset if x['family']=='hybrid' and float(x['activation'])>=.2]
    else:f=[x for x in subset if x['family']=='hybrid' and float(x['activation'])<.2]
    diffs=[float(x['net_points'])-float(baseline['net_points']) for x in f]
    output.append(dict(arm=arm,slippage=slip,split=split,family=family,variants=len(f),baseline_net=float(baseline['net_points']),min_delta=min(diffs),median_delta=statistics.median(diffs),max_delta=max(diffs),positive_count=sum(d>0 for d in diffs),negative_count=sum(d<0 for d in diffs),max_activation=max(int(x['activated']) for x in f),max_early=max(int(x['early_exits']) for x in f)))
with (OUT/'plateaus.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
# Development-selected candidates only. No selection by heldout ranking.
selected=[]
for arm in ('preserve_exits','replace_EMA_research_only'):
 for family in ('current','structure','hybrid'):
  dev=[x for x in r if x['arm']==arm and x['family']==family and x['slippage']=='0.01' and x['split']=='development' and (family!='hybrid' or float(x['activation'])>=.2)]
  best=max(dev,key=lambda x:float(x['net_points']));test=next(x for x in r if x['arm']==arm and x['variant']==best['variant'] and x['slippage']=='0.01' and x['split']=='heldout')
  selected.append(dict(arm=arm,family=family,development=best,heldout=test))
(OUT/'development_selection.json').write_text(json.dumps(selected,indent=2))
manifest={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.csv') and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
for x in output:
 if x['arm']=='preserve_exits' and x['slippage']=='0.01' and x['split']=='heldout':print(x)
