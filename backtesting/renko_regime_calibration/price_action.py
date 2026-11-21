"""Causal confirmed price-structure checks; no new indicator entry gates."""
import json,time
from concurrent.futures import ProcessPoolExecutor,as_completed
import run as calibration
from grid import RULES
HERE=calibration.HERE
NEW={'PA_HHHL2':dict(family='price_structure',pivot=2,mode='structure'),
 'PA_HHHL3':dict(family='price_structure',pivot=3,mode='structure'),
 'PA_BREAK2':dict(family='price_structure',pivot=2,mode='breakout'),
 'PA_BREAK3':dict(family='price_structure',pivot=3,mode='breakout'),
 'PA_OVERLAP04':dict(family='price_overlap',lookback=6,maximum=.4)}
RULES.update(NEW)
def gate(history,name,direction):
 from review import day
 if not history:return False
 c=NEW[name]
 if name=='PA_OVERLAP04':
  if len(history)<7 or len({day(x) for x in history[-7:]})!=1:return False
  w=history[-7:]
  overlaps=[max(0,min(a['high'],b['high'])-max(a['low'],b['low']))/max(a['high']-a['low'],b['high']-b['low'],.05) for a,b in zip(w,w[1:])]
  return sum(overlaps)/6<=.4
 today=day(history[-1]);w=[x for x in history[-80:] if day(x)==today];n=c['pivot']
 highs=[];lows=[]
 for i in range(n,len(w)-n):
  neighbors=w[i-n:i]+w[i+1:i+n+1]
  if all(w[i]['high']>x['high'] for x in neighbors):highs.append(w[i]['high'])
  if all(w[i]['low']<x['low'] for x in neighbors):lows.append(w[i]['low'])
 if len(highs)<2 or len(lows)<2:return False
 bullish=direction=='BULLISH'
 if c['mode']=='structure':
  return highs[-1]>highs[-2] and lows[-1]>lows[-2] if bullish else highs[-1]<highs[-2] and lows[-1]<lows[-2]
 return w[-1]['close']>highs[-1] and lows[-1]>lows[-2] if bullish else w[-1]['close']<lows[-1] and highs[-1]<highs[-2]
def initialize():
 calibration.initialize()
 calibration.lifecycle.filter_entry=gate
def main():
 requests=[(n,b) for n in NEW for b in (20.,27.71,35.)];results={}
 with ProcessPoolExecutor(max_workers=2,initializer=initialize) as pool:
  futures={pool.submit(calibration.run_trial,n,b): (n,b) for n,b in requests}
  for f in as_completed(futures):
   request=futures[f];r=f.result();key=f'{request[0]}_brick{request[1]}'
   (HERE/'trials'/f'{key}.json').write_text(json.dumps(r));results[key]={k:v for k,v in r.items() if k!='trades'}
   (HERE/'price-action-results.json').write_text(json.dumps(results,indent=2))
   calibration.checkpoint('RUNNING',phase='PRICE_ACTION',completed=len(results),total=len(requests))
 calibration.checkpoint('COMPLETED',phase='PRICE_ACTION',completed=len(results),total=len(requests))
 for key,r in results.items():
  if r['brick']==27.71:print(key,{p:{k:round(v,2) if isinstance(v,float) else v for k,v in q['2'].items()} for p,q in r['splits'].items() if p!='all'})
if __name__=='__main__':
 try:main()
 except Exception as e:
  calibration.checkpoint('FAILED',error=str(e));raise
