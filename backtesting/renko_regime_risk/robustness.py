"""Neighboring entry thresholds, stop distances and brick sizes; fixed existing exits."""
import json,os,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from run import initialize as base_initialize,checkpoint,HERE
import run as risk_run
from model import simulate,EXITS
from grid import RULES
for level in (.3,.4,.5):
 RULES[f'RISK_overlap{level}']=dict(family='overlap',n=6,threshold=level)
for distance in (1.,1.5,2.):
 EXITS[f'FixedInitial_Trail{distance}']=dict(hard=2.,trail=distance,activation=1.)
def trial(entry,exit_name,brick):
 return simulate(risk_run.HOSTS,risk_run.MINUTES,dict(risk_run.CONFIG,manual_brick=brick),entry,exit_name,risk_run.START)
def main():
 requests=[(f'RISK_overlap{level}',f'FixedInitial_Trail{trail}',brick) for level in (.3,.4,.5) for trail in (1.,1.5,2.) for brick in (20.,27.71,35.)]
 requests += [('efficiency_36','Hard1_5ATR',brick) for brick in (20.,35.)]
 results={}
 with ProcessPoolExecutor(max_workers=2,initializer=base_initialize) as pool:
  futures={pool.submit(trial,*request):request for request in requests}
  for f in as_completed(futures):
   request=futures[f];result=f.result();key='_'.join(map(str,request))
   (HERE/'trials'/f'{key}.json').write_text(json.dumps(result))
   results[key]={k:v for k,v in result.items() if k not in ('trades','curve')}
   (HERE/'robustness.json').write_text(json.dumps(results,indent=2))
   checkpoint('RUNNING',phase='RISK_ROBUSTNESS',completed=len(results),total=len(requests))
 checkpoint('COMPLETED',phase='RISK_ROBUSTNESS',completed=len(results),total=len(requests))
 print('Completed',len(requests),'risk robustness scenarios.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  checkpoint('FAILED',error=str(e));raise
