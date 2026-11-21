"""High-hit-rate target/stop calibration with strict joint acceptance thresholds."""
import json,sys,os
from concurrent.futures import ProcessPoolExecutor,as_completed
from run import initialize,checkpoint,HERE
import run as core
from model import simulate,EXITS
PROFILES={}
for stop in (1.,1.5,2.,3.):
 for target in (.25,.5,.75,1.,1.5):
  name=f'HighWin_stop{stop}_target{target}';PROFILES[name]=dict(hard=stop,target=target)
EXITS.update(PROFILES)
def trial(entry,exit_name):return simulate(core.HOSTS,core.MINUTES,core.CONFIG,entry,exit_name,core.START)
def main():
 spec=dict(entries=['Baseline','adx_60','efficiency_36','overlap_130'],exits=PROFILES,
 goals=dict(minimum_win_rate_each_year=65,minimum_pf_each_year=1.3,maximum_all_loss_and_nonpositive_streak=3,
 maximum_drawdown_fraction_baseline=.5,minimum_trades_each_year=60,positive_under_4_point_drag=True),
 chronology='Existing stops precede targets if both levels touch within the same minute: adverse ordering. Conservative target fill at level. Stops/targets fixed from completed entry ATR.',
 scope='Exploratory NIFTY underlying proxy, not option returns or future guarantees')
 (HERE/'high-win-specification.json').write_text(json.dumps(spec,indent=2))
 requests=[(entry,name) for entry in spec['entries'] for name in PROFILES];results={}
 with ProcessPoolExecutor(max_workers=2,initializer=initialize) as pool:
  futures={pool.submit(trial,*request):request for request in requests}
  for f in as_completed(futures):
   req=futures[f];r=f.result();name=req[0]+'_'+req[1]
   (HERE/'trials'/f'{name}.json').write_text(json.dumps(r));results[name]={k:v for k,v in r.items() if k not in ('trades','curve')}
   (HERE/'high-win-results.json').write_text(json.dumps(results,indent=2));checkpoint('RUNNING',phase='HIGH_WIN_JOINT_GOALS',completed=len(results),total=len(requests))
 baseline=json.loads((HERE/'results.json').read_text())['Baseline_SelectedExits'];eligible=[];evaluated=[]
 for name,r in results.items():
  reasons=[]
  for year in ('earlier','latest'):
   s=r['splits'][year]['2'];b=baseline['splits'][year]['2']
   if s['trades']<60:reasons.append(year+': trade count')
   if (s['positive_pct'] or 0)<65:reasons.append(year+': win rate')
   if (s['profit_factor'] or 0)<1.3:reasons.append(year+': PF')
   if r['splits'][year]['4']['net_points']<=0:reasons.append(year+': friction')
   if s['realized_drawdown_points']>.5*b['realized_drawdown_points']:reasons.append(year+': drawdown')
   if r['minute_close_drawdown_by_year'][year]>.5*baseline['minute_close_drawdown_by_year'][year]:reasons.append(year+': minute-close drawdown')
  s=r['splits']['all']['2']
  if max(s['max_loss_streak'],s['max_nonpositive_streak'])>3:reasons.append('losing/non-winning streak')
  if not reasons:eligible.append(name)
  evaluated.append(dict(name=name,reasons=reasons))
 output=dict(eligible=eligible,evaluated=evaluated)
 (HERE/'high-win-selection.json').write_text(json.dumps(output,indent=2))
 checkpoint('COMPLETED',phase='HIGH_WIN_JOINT_GOALS',completed=len(results),total=len(requests),eligible=eligible)
 print('Eligible:',eligible)
if __name__=='__main__':
 try:main()
 except Exception as e:
  checkpoint('FAILED',error=str(e));raise
