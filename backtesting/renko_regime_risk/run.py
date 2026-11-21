import json,csv,os,time,sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor,as_completed
HERE=Path(__file__).parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'backtesting/renko_regime_calibration'))
import importlib.util
spec=importlib.util.spec_from_file_location('calibration_core',ROOT/'backtesting/renko_regime_calibration/run.py')
calibration=importlib.util.module_from_spec(spec);sys.modules[spec.name]=calibration;spec.loader.exec_module(calibration)
from model import EXITS,simulate
HOSTS=None;MINUTES=None;CONFIG=None;START=None
def initialize():
 global HOSTS,MINUTES,CONFIG,START
 calibration.initialize();HOSTS=calibration.RAW;CONFIG=dict(calibration.CONFIG,manual_brick=27.71);START=calibration.SCORE_START
 valid={calibration.lifecycle.day(r) for r in HOSTS};MINUTES=[]
 with (calibration.lifecycle.ARCHIVE/'nifty50_1m.csv').open() as f:
  for x in csv.DictReader(f):
   t=datetime.fromtimestamp(int(x['epoch']),calibration.lifecycle.IST)
   if t.date().isoformat() not in valid or not 555<=t.hour*60+t.minute<930:continue
   MINUTES.append(dict(timestamp=int(x['epoch']),**{k:float(x[k]) for k in ('open','high','low','close','volume')}))
def trial(entry,exit_name):return simulate(HOSTS,MINUTES,CONFIG,entry,exit_name,START)
def checkpoint(status,**fields):
 (HERE/'job.json').write_text(json.dumps(dict(status=status,pid=os.getpid(),heartbeat=time.time(),**fields)))
def main():
 HERE.mkdir(exist_ok=True);(HERE/'trials').mkdir(exist_ok=True)
 entries=('Baseline','adx_60','efficiency_36','overlap_130')
 spec=dict(entries=entries,exits=EXITS,primary_cost=2,stop_tick=.05,stop_rounding='Long floor, short ceiling',
 scope='Underlying index one-minute OHLC stop proxy; no option fills, fees or guaranteed stops.',
 data='Only complete aligned 375-minute/75-host-bar regular-clock sessions. First five observed sessions warm-up.',
 chronology='Existing stop checked before current minute favorable high/low updates. New trail/breakeven level applies next minute. Gaps exit at observed open; touched levels assume fills without latency or liquidity evidence.',
 objective='Reduce realized and minute-close drawdown plus longest nonpositive/losing streak, subject to positive net at 4-point drag and PF>=1.05 in both years; no resetting streaks at day boundaries.')
 (HERE/'specification.json').write_text(json.dumps(spec,indent=2))
 requests=[(entry,name) for entry in entries for name in EXITS];results={}
 checkpoint('RUNNING',completed=0,total=len(requests))
 with ProcessPoolExecutor(max_workers=2,initializer=initialize) as pool:
  futures={pool.submit(trial,*request):request for request in requests}
  for future in as_completed(futures):
   request=futures[future];result=future.result();name=request[0]+'_'+request[1]
   (HERE/'trials'/f'{name}.json').write_text(json.dumps(result))
   results[name]={k:v for k,v in result.items() if k not in ('trades','curve')}
   (HERE/'results.json').write_text(json.dumps(results,indent=2));checkpoint('RUNNING',completed=len(results),total=len(requests),latest=name)
 checkpoint('COMPLETED',completed=len(results),total=len(requests))
 print('Completed',len(results),'entry/exit comparisons.')
if __name__=='__main__':
 try:main()
 except Exception as error:
  checkpoint('FAILED',error=str(error));raise
