from pathlib import Path
import pandas as pd,numpy as np,json
P=Path(__file__).resolve().parent
r=pd.read_csv(P/'observations.csv');r['month']=r.date.str[:7];rng=np.random.default_rng(20261101)
out={}
for split in ['development','heldout']:
 d=r[r.split==split];months=d.month.unique();blocks={m:d[d.month==m] for m in months};diff=[];hit=[]
 for _ in range(2000):
  x=pd.concat([blocks[m] for m in rng.choice(months,len(months),replace=True)])
  y=x[x.confirmed]
  diff.append(y.ret_pct.mean()-x.ret_pct.mean())
  hit.append(100*((y.ret_pct>0).mean()-(x.ret_pct>0).mean()))
 out[split]={'months':len(months),'mean_lift_95pct':np.percentile(diff,[2.5,97.5]).tolist(),'hit_lift_95pct':np.percentile(hit,[2.5,97.5]).tolist()}
g=r.groupby(['split','symbol','confirmed']).ret_pct.agg(['size','mean']).reset_index()
g.to_csv(P/'per_stock.csv',index=False)
(P/'uncertainty.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
# Structural causal audit: perturb every future bar after each chosen cutoff.
import importlib.util,ast
src=(P/'research.py').read_text();tree=ast.parse(src)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='structures')
ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'structure','exec'),ns)
j=json.loads((P/'RELIANCE.json').read_text())['chart']['result'][0]
d=pd.DataFrame(j['indicators']['quote'][0])
checks=0
for k in [250,500,1000,1500,2000]:
 a=ns['structures'](d.iloc[:k+1]);b=d.copy();b.loc[k+1:,['high','low']]*=10
 assert ns['structures'](b)[:k+1]==a
 checks+=1
print('Future-perturbation causal checks:',checks)
print('Heldout dates',r[r.split=='heldout'].date.min(),r[r.split=='heldout'].date.max())
