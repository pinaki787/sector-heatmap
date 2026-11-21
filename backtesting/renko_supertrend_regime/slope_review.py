"""Supertrend line slope only; other indicators are not added as regime gates."""
from pathlib import Path
import json
import review as study
BASE=Path(__file__).parent
RULES=[('Baseline',)]+[(f'Slope{n}_{threshold}',n,threshold) for n in (6,12) for threshold in (.02,.05,.1)]
def assess(rows,rule):
 if rule[0]=='Baseline':return dict(allowed=True,state='BASELINE')
 _,n,threshold=rule
 if len(rows)<n+1:return dict(allowed=False,state='WARMUP')
 w=rows[-n-1:]
 if len({study.day(x) for x in w})!=1:return dict(allowed=False,state='SESSION_WARMUP')
 # Never interpolate across a Supertrend band switch: that jump is not trend slope.
 if len({x['pine_direction'] for x in w})!=1:return dict(allowed=False,state='BAND_SWITCH')
 sign=1 if w[-1]['pine_direction']<0 else -1
 box=w[-1]['box']
 signed=sign*(w[-1]['supertrend']-w[0]['supertrend'])/(n*box)
 return dict(allowed=signed>=threshold,state='TRENDING' if signed>=threshold else 'FLAT_OR_WEAK',slope_boxes_per_bar=signed)
def main():
 study.OUT=BASE/'supertrend_slope';study.OUT.mkdir(exist_ok=True)
 study.RULES=RULES;study.assess=assess;study.main()
 p=study.OUT/'results.json';r=json.loads(p.read_text())
 r['research_status']='Exploratory Supertrend slope-only comparison; all latest-year periods previously inspected.'
 r['validation_selected_rule']=None;p.write_text(json.dumps(r,indent=2))
 print('SLOPE SUMMARY')
 for name,s in r['results'].items():
  print(name,{p:{k:round(v,2) if isinstance(v,float) else v for k,v in v.items() if k in ('samples','profit_factor','mean_points','positive_pct')} for p,v in s.items() if p in ('validation','holdout','all')})
if __name__=='__main__':main()
