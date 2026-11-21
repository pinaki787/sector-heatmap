"""Independent OHLC black-box hypotheses. No protected code or hardcoded levels."""
import csv,json,math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
BASE=Path(__file__).parent
IST=ZoneInfo('Asia/Kolkata')
def load(path):
 out=[]
 for r in csv.DictReader(path.open()):
  out.append(dict(t=int(float(r['time'])),o=float(r['open']),h=float(r['high']),l=float(r['low']),c=float(r['close'])))
 return out

def detect(bars,strength=5,threshold=.8,consume_weak=True,score_mode='displacement',range_mode='full',atr_previous=False):
 tr=[];atr=None;ph=pl=None;hb=lb=False;zones=[];last={1:-10000,-1:-10000};prior=None
 step=min((bars[j]["t"]-bars[j-1]["t"] for j in range(1,len(bars))),default=300)
 for i,b in enumerate(bars):
  r=max(b['h']-b['l'],abs(b['h']-prior),abs(b['l']-prior)) if prior is not None else b['h']-b['l'];prior=b['c'];tr.append(r);oldatr=atr
  atr=sum(tr[:14])/14 if i==13 else ((atr*13+r)/14 if atr is not None else None)
  if atr is None:continue
  zones=[z for z in zones if b['t']+step-z['origin']<=15*86400]
  for z in zones:
   if z['state']!=0:continue
   bad=b['c']>z['hi'] if z['side']==-1 else b['c']<z['lo']
   touch=z['lo']<=b['c']<=z['hi']
   if bad:z['state']=2;z['invalid']=b['t']
   elif touch and z['state']==0:z['state']=1;z['finish']=b['t']+step
  if i>=strength*2:
   k=i-strength;v=bars[k];left=bars[k-strength:k];right=bars[k+1:i+1]
   if all(v['h']>=x['h'] for x in left) and all(v['h']>x['h'] for x in right):ph=v['h'];hb=False
   if all(v['l']<=x['l'] for x in left) and all(v['l']<x['l'] for x in right):pl=v['l'];lb=False
  up=ph is not None and not hb and b['c']>ph;down=pl is not None and not lb and b['c']<pl
  body=abs(b['c']-b['o'])/((oldatr if atr_previous and oldatr else atr) or 1)
  if consume_weak or body>=threshold:
   hb=hb or up;lb=lb or down
  side=1 if up else -1 if down else 0
  if not side or body<threshold or i-last[side]<3:continue
  # Score hypotheses are explicit experimental candidates, not recovered private scores.
  score=50+min(30,body*20) if score_mode=='displacement' else 100
  if score<65:continue
  origin=next((j for j in range(i-1,max(-1,i-13),-1) if (bars[j]['c']<bars[j]['o'] if side==1 else bars[j]['c']>bars[j]['o'])),None)
  if origin is None:continue
  v=bars[origin];hi=v['h'];lo=v['l']
  if range_mode=='bodywick':hi=v['o'] if side==1 else hi;lo=v['o'] if side==-1 else lo
  if any(z['side']==side and (z['origin']==v['t'] or (z['state']==0 and abs((hi+lo-z['hi']-z['lo'])/2)<=atr*.35)) for z in zones):continue
  zones.append(dict(side=side,hi=hi,lo=lo,origin=v['t'],born=b['t']+step,state=0,finish=b['t']+step,score=score));last[side]=i
 return zones

def caption(z):return {**z,'origin':datetime.fromtimestamp(z['origin'],IST).isoformat(),'born':datetime.fromtimestamp(z['born'],IST).isoformat(),'finish':datetime.fromtimestamp(z['finish'],IST).isoformat()}
if __name__=='__main__':
 bars=load(BASE/'hcl_tradingview_5m.csv');results={}
 for consume in [True,False]:
  for range_mode in ['full','bodywick']:
   for previous in [False,True]:
    key=f'consume={consume};bounds={range_mode};atr_previous={previous}'
    zs=detect(bars,consume_weak=consume,range_mode=range_mode,atr_previous=previous)
    results[key]=dict(total=len(zs),fresh=[caption(z) for z in zs if z['state']==0],touched=[caption(z) for z in zs if z['state']==1])
 (BASE/'zone_hypotheses.json').write_text(json.dumps(results,indent=2))
 for k,v in results.items():
  print(k,'total',v['total'],'fresh',v['fresh'])
