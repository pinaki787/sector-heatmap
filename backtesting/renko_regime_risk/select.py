"""Risk-first shortlist: no rewarding zero-trade or breakeven streak tricks."""
import json
from pathlib import Path
HERE=Path(__file__).parent
def main():
 results=json.loads((HERE/'results.json').read_text());baseline=results['Baseline_SelectedExits'];ranked=[];evaluated=[]
 for name,r in results.items():
  reasons=[];ratios=[]
  for year in ('earlier','latest'):
   s=r['splits'][year]['2'];b=baseline['splits'][year]['2']
   if s['trades']<60:reasons.append(year+': fewer than 60 trades')
   if s['profit_factor'] is None or s['profit_factor']<1.05:reasons.append(year+': PF below 1.05')
   if r['splits'][year]['4']['net_points']<=0:reasons.append(year+': loses under four-point drag')
   if s['max_loss_streak']>=b['max_loss_streak']:reasons.append(year+': losing streak not shorter')
   if s['max_nonpositive_streak']>=b['max_nonpositive_streak']:reasons.append(year+': non-winning streak not shorter')
   if s['realized_drawdown_points']>=b['realized_drawdown_points']:reasons.append(year+': realized drawdown not lower')
   mtm=r['minute_close_drawdown_by_year'][year];base_mtm=baseline['minute_close_drawdown_by_year'][year]
   if mtm>=base_mtm:reasons.append(year+': minute-close drawdown not lower')
   ratios.append(mtm/base_mtm)
  row=dict(name=name,reasons=reasons)
  if not reasons:
   longest=max(r['splits'][y]['2']['max_nonpositive_streak'] for y in ('earlier','latest'))
   weakest=min(r['splits'][y]['2']['profit_factor'] for y in ('earlier','latest'))
   score=(max(ratios),longest,-weakest)
   ranked.append((score,name));row['risk_score']=score
  evaluated.append(row)
 ranked.sort()
 output=dict(selection=ranked[0][1] if ranked else None,scope='Risk-first historical proxy shortlist, not live readiness',
 ranked=[dict(name=n,score=s) for s,n in ranked],evaluated=evaluated)
 (HERE/'selection.json').write_text(json.dumps(output,indent=2));print(json.dumps({k:v for k,v in output.items() if k!='evaluated'},indent=2))
if __name__=='__main__':main()
