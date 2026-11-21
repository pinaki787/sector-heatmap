"""Exploratory prolonged-flatness entry filter, with optional completed-price breakout."""
from pathlib import Path
import json
import review as study
BASE=Path(__file__).parent
RULES=[('Baseline',)]+[(f'Flat{n}',n,False) for n in (3,6,9,12)]+[(f'Flat{n}_breakout',n,True) for n in (6,12)]
def assess(rows,rule):
 if rule[0]=='Baseline':return dict(allowed=True,state='BASELINE')
 _,n,override=rule
 if len(rows)<n+1:return dict(allowed=False,state='WARMUP')
 w=rows[-n-1:];r=w[-1]
 if len({study.day(x) for x in w})!=1:return dict(allowed=False,state='SESSION_WARMUP')
 # A band change is a transition, not evidence of flatness.
 same_band=len({x['pine_direction'] for x in w})==1
 flat=same_band and max(x['supertrend'] for x in w)-min(x['supertrend'] for x in w)<=.025
 bullish=r['pine_direction']<0
 breakout=r['close']>max(x['high'] for x in w[:-1]) if bullish else r['close']<min(x['low'] for x in w[:-1])
 allowed=not flat or override and breakout
 return dict(allowed=allowed,state='FLAT_BREAKOUT' if flat and allowed else 'PROLONGED_FLAT' if flat else 'NOT_PROLONGED_FLAT',
             flat=flat,breakout=breakout)
def main():
 study.OUT=BASE/'prolonged_flatness';study.OUT.mkdir(exist_ok=True)
 study.RULES=RULES;study.assess=assess;study.main()
 p=study.OUT/'results.json';r=json.loads(p.read_text());r['validation_selected_rule']=None
 r['research_status']='Exploratory; historical periods already inspected. Index signal quality only.'
 p.write_text(json.dumps(r,indent=2))
 print('FLATNESS SUMMARY')
 for name,s in r['results'].items():
  print(name,{p:{k:round(v,2) if isinstance(v,float) else v for k,v in v.items() if k in ('samples','profit_factor','mean_points','positive_pct')} for p,v in s.items() if p in ('development','validation','holdout','all')})
if __name__=='__main__':main()
