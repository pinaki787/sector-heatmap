"""Persistent two-process calibration. No credentials, live settings or order calls."""
import os,time,json,csv,hashlib,statistics
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor,as_completed
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'backtesting/renko_regime_lifecycle'))
import review as lifecycle
from grid import RULES,gate
RAW=None;CONFIG=None;SCORE_START=None
def initialize():
 global RAW,CONFIG,SCORE_START
 os.nice(10)
 lifecycle.filter_entry=gate
 lifecycle.OUT=HERE
 CONFIG=json.loads((ROOT/'backtesting/renko_regime_lifecycle/specification.json').read_text())['base_config']
 RAW=[]
 with (lifecycle.ARCHIVE/'nifty50_5m.csv').open() as f:
  for x in csv.DictReader(f):
   t=datetime.fromtimestamp(int(x['epoch']),lifecycle.IST)
   if t.weekday()>4 or not 555<=t.hour*60+t.minute<930:continue
   RAW.append(dict(timestamp=int(x['epoch']),**{k:float(x[k]) for k in ('open','high','low','close','volume')}))
 from collections import Counter
 host_counts=Counter(lifecycle.day(r) for r in RAW);minute_counts=Counter()
 with (lifecycle.ARCHIVE/'nifty50_1m.csv').open() as f:
  for x in csv.DictReader(f):
   t=datetime.fromtimestamp(int(x['epoch']),lifecycle.IST)
   if t.weekday()<5 and 555<=t.hour*60+t.minute<930:minute_counts[t.date().isoformat()]+=1
 valid={d for d,n in host_counts.items() if n==75 and minute_counts[d]==375}
 RAW=[r for r in RAW if lifecycle.day(r) in valid]
 SCORE_START=sorted({lifecycle.day(r) for r in RAW})[5]
def block(d):
 bounds=['2025-01-25','2025-04-25','2025-07-25','2025-10-25','2026-01-25','2026-04-25','2026-07-25']
 return next((i for i,end in enumerate(bounds) if d<end),7)
def run_trial(name,brick=27.71,cap=2,recovery=False):
 replay=lifecycle.simulate(RAW,dict(CONFIG,manual_brick=brick),name,cap=cap,recovery=recovery)
 trades=[t for t in replay['trades'] if t['entry_day']>=SCORE_START]
 splits={}
 for label,chosen in [('earlier',[t for t in trades if t['entry_day']<'2025-10-25']),('latest',[t for t in trades if t['entry_day']>='2025-10-25']),('all',trades)]:
  splits[label]={str(d):lifecycle.stats(chosen,d) for d in (0,2,4)}
 quarters={str(q):lifecycle.stats([t for t in trades if block(t['entry_day'])==q],2) for q in range(8)}
 result=dict(name=name,rule=RULES[name],brick=brick,cap=cap,recovery=recovery,splits=splits,quarters=quarters,
  skipped=replay['skipped'],gaps=replay['gaps'],scoring_start=SCORE_START,trades=trades)
 return result
def checkpoint(status,**fields):
 (HERE/'job.json').write_text(json.dumps(dict(status=status,pid=os.getpid(),heartbeat=time.time(),**fields)))
def main():
 HERE.mkdir(exist_ok=True);(HERE/'trials').mkdir(exist_ok=True)
 specification=dict(rules=RULES,primary_brick=27.71,workers=2,
  data='FYERS NIFTY two-year archive; full aligned 375-minute/75-host-bar regular-clock sessions only; first five observed sessions excluded from scoring',
  source_sha256=hashlib.sha256(Path(__file__).read_bytes()+(HERE/'grid.py').read_bytes()+(ROOT/'backtesting/renko_regime_lifecycle/review.py').read_bytes()).hexdigest(),
  selection='First-year ranking only: >=80 trades, >=8 per quarter, PF>=1.05, DD<=90% baseline; rank positive quarters, worst-quarter PF, overall PF, lower DD. At most two shortlisted rules per family. Latest year already inspected historically: not a fresh holdout.',
  costs='0,2,4 underlying-point drag per closed trade; no option cost inference')
 (HERE/'specification.json').write_text(json.dumps(specification,indent=2))
 results={}
 checkpoint('RUNNING',phase='PRIMARY',completed=0,total=len(RULES))
 with ProcessPoolExecutor(max_workers=2,initializer=initialize) as pool:
  futures={pool.submit(run_trial,name):name for name in RULES}
  for future in as_completed(futures):
   if (HERE/'CANCEL').exists():
    for f in futures:f.cancel()
    raise InterruptedError('Calibration cancellation requested.')
   name=futures[future];result=future.result()
   (HERE/'trials'/f'{name}.json').write_text(json.dumps(result))
   results[name]={k:v for k,v in result.items() if k!='trades'}
   (HERE/'primary-results.json').write_text(json.dumps(results,indent=2))
   checkpoint('RUNNING',phase='PRIMARY',completed=len(results),total=len(RULES))
 baseline=results['Baseline']['splits']['earlier']['2']
 ranked=[]
 for name,r in results.items():
  if r['rule']['family'] in ('baseline','warmup_control'):continue
  s=r['splits']['earlier']['2'];qs=[r['quarters'][str(q)] for q in range(4)]
  if s['trades']<80 or any(q['trades']<8 for q in qs) or s['profit_factor'] is None or s['profit_factor']<1.05 or s['realized_drawdown_points']>.9*baseline['realized_drawdown_points']:continue
  key=(sum(q['net_points']>0 for q in qs),min(q['profit_factor'] or 0 for q in qs),s['profit_factor'],-s['realized_drawdown_points'])
  ranked.append((key,name))
 ranked.sort(reverse=True);shortlist=[];families={}
 for key,name in ranked:
  family=results[name]['rule']['family']
  if families.get(family,0)>=2:continue
  shortlist.append(name);families[family]=families.get(family,0)+1
  if len(shortlist)==12:break
 (HERE/'training-shortlist.json').write_text(json.dumps(dict(selection_year='earlier',ranked=[dict(name=n,score=k) for k,n in ranked],shortlist=shortlist),indent=2))
 checkpoint('COMPLETED',phase='PRIMARY',completed=len(results),total=len(RULES),shortlist=shortlist)
 print('Completed',len(results),'primary scenarios; shortlist',shortlist)
if __name__=='__main__':
 try:main()
 except Exception as e:
  checkpoint('CANCELLED' if isinstance(e,InterruptedError) else 'FAILED',error=str(e))
  raise
