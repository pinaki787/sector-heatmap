"""Explicit historical stability ranking, not selection on highest full-sample PF."""
import json,math
from pathlib import Path
HERE=Path(__file__).parent
def main():
 primary=json.loads((HERE/'primary-results.json').read_text())
 robust=json.loads((HERE/'robustness-results.json').read_text())
 shortlist=json.loads((HERE/'training-shortlist.json').read_text())['shortlist']
 base=primary['Baseline'];evaluated=[]
 for name in shortlist:
  r=primary[name];reasons=[]
  for year in ('earlier','latest'):
   s=r['splits'][year]['2'];b=base['splits'][year]['2']
   if s['trades']<60:reasons.append(year+': fewer than 60 trades')
   if s['profit_factor'] is None or s['profit_factor']<1.05:reasons.append(year+': PF below 1.05')
   if s['realized_drawdown_points']>b['realized_drawdown_points']:reasons.append(year+': drawdown above baseline')
   if r['splits'][year]['4']['net_points']<=0:reasons.append(year+': loses under 4-point drag')
  for brick in (20.,35.):
   key=f'{name}_brick{brick}_cap2_lockFalse'
   if key not in robust:reasons.append('missing neighbor audit');continue
   for year in ('earlier','latest'):
    s=robust[key]['splits'][year]['2']
    if s['profit_factor'] is None or s['profit_factor']<1:reasons.append(f'{year}: brick {brick} PF below 1')
  eligible=not reasons
  evaluated.append(dict(name=name,rule=r['rule'],eligible_for_paper=eligible,reasons=reasons))
 selected=next((r['name'] for r in evaluated if r['eligible_for_paper']),None)
 result=dict(selection=selected,scope='First-year-ranked candidate passing declared two-year historical stability checks; not independent validation',evaluated=evaluated)
 (HERE/'selection.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
