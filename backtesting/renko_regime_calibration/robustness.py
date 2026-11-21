"""Audit first-year shortlist without adjusting filter thresholds."""
import json,time,os
from concurrent.futures import ProcessPoolExecutor,as_completed
from run import HERE,initialize,run_trial,checkpoint
from grid import RULES
def main():
 selection=json.loads((HERE/'training-shortlist.json').read_text());shortlist=list(selection['shortlist'])
 reference=next(n for n,c in RULES.items() if c==dict(family='efficiency',n=12,threshold=.25,floor=.8))
 if reference not in shortlist:shortlist.append(reference)
 requests=[(n,b,2,False) for n in shortlist+['Baseline'] for b in (20.,35.)]
 requests += [(n,27.71,10000,False) for n in selection['shortlist'][:3]+['Baseline']]
 requests += [(n,27.71,2,True) for n in selection['shortlist'][:3]+['Baseline',reference]]
 requests=list(dict.fromkeys(requests));results={}
 with ProcessPoolExecutor(max_workers=2,initializer=initialize) as pool:
  futures={pool.submit(run_trial,*request):request for request in requests}
  for future in as_completed(futures):
   if (HERE/'CANCEL').exists():
    for f in futures:f.cancel()
    raise InterruptedError('Calibration cancellation requested.')
   request=futures[future];r=future.result();key=f'{request[0]}_brick{request[1]}_cap{request[2]}_lock{request[3]}'
   results[key]={k:v for k,v in r.items() if k!='trades'}
   (HERE/'trials'/f'{key}.json').write_text(json.dumps(r))
   (HERE/'robustness-results.json').write_text(json.dumps(results,indent=2))
   checkpoint('RUNNING',phase='SHORTLIST_ROBUSTNESS',completed=len(results),total=len(requests),reference=reference)
 checkpoint('COMPLETED',phase='SHORTLIST_ROBUSTNESS',completed=len(results),total=len(requests),reference=reference)
 print('Audited',len(requests),'scenarios, reference',reference)
if __name__=='__main__':
 try:main()
 except Exception as e:
  checkpoint('CANCELLED' if isinstance(e,InterruptedError) else 'FAILED',error=str(e))
  raise
