"""Paired five-observed-session block resampling; descriptive uncertainty only."""
import json,math
from pathlib import Path
import numpy as np
HERE=Path(__file__).parent
def run(name):
 primary=json.loads((HERE/'primary-results.json').read_text())
 a=json.loads((HERE/'trials/Baseline.json').read_text())['trades']
 b=json.loads((HERE/'trials'/f'{name}.json').read_text())['trades']
 output={}
 for period in ('earlier','latest','all'):
  check=lambda t:period=='all' or (t['entry_day']<'2025-10-25')==(period=='earlier')
  aa=[t for t in a if check(t)];bb=[t for t in b if check(t)]
  days=sorted({t['entry_day'] for t in aa+bb})
  lookup={d:i for i,d in enumerate(days)};data=np.zeros((len(days),4))
  for trades,offset in ((aa,0),(bb,2)):
   for t in trades:
    net=t['gross_points']-2;data[lookup[t['entry_day']],offset+(net<0)]+=abs(net)
  rng=np.random.default_rng(20261025);samples=3000;block=5;n=len(days)
  starts=rng.integers(0,max(1,n-block+1),size=(samples,math.ceil(n/block)))
  indices=(starts[:,:,None]+np.arange(block)[None,None,:]).reshape(samples,-1)[:,:n]
  indices=np.minimum(indices,n-1);totals=data[indices].sum(axis=1)
  valid=(totals[:,1]>0)&(totals[:,3]>0)
  diff=totals[valid,2]/totals[valid,3]-totals[valid,0]/totals[valid,1]
  lo,median,hi=np.quantile(diff,[.025,.5,.975])
  output[period]=dict(observed_sessions_with_any_trade=n,replications=samples,block_sessions=block,
   candidate_minus_baseline_pf_interval95=[float(lo),float(hi)],median_difference=float(median),
   fraction_resamples_positive=float((diff>0).mean()))
 result=dict(candidate=name,caution='Descriptive resampling after adaptive historical exploration; does not correct multiple testing or supply unseen validation. Sessions with no trades in either strategy are omitted.',results=output)
 (HERE/'uncertainty.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':
 selected=json.loads((HERE/'selection.json').read_text())['selection']
 if selected:run(selected)
 else:print('No candidate passed; no winner interval manufactured.')
