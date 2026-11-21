"""Bounded, declared sideways-regime calibration; completed information only."""
import math
RULES={'Baseline':dict(family='baseline')}
def add(family,**params):
 name=family+'_'+str(len(RULES));RULES[name]=dict(family=family,**params)
for n in (6,12,18):
 for threshold in (.15,.25,.35,.45):
  for floor in (0,.6,.8,1.):add('efficiency',n=n,threshold=threshold,floor=floor)
for threshold in (45,50,55,60):
 for floor in (0,.8):add('choppiness',n=14,threshold=threshold,floor=floor)
for threshold in (15,20,25,30):
 for rising in (False,True):
  for floor in (0,.8):add('adx',n=3,threshold=threshold,rising=rising,floor=floor)
for family in ('ema_slope','st_slope'):
 for n in (3,6,12):
  for threshold in (0,.02,.05,.1):
   for floor in (0,.8):add(family,n=n,threshold=threshold,floor=floor)
for n in (6,12,24):
 for offset in (0,.1,.25):add('breakout',n=n,offset=offset)
for threshold in (.4,.6,.8):add('overlap',n=6,threshold=threshold)
for low in (.6,.8,1.):
 for high in (1.2,1.5,2.):add('atr_band',n=1,low=low,high=high)
for er in (.15,.25,.35):
 for chop in (50,55,60):add('efficiency_chop',n=14,threshold=er,chop=chop,floor=.8)
for n in (6,12,18):add('not_flat',n=n)
for threshold in (52,55,60):
 for adx in (0,20):add('rsi_strength',n=1,threshold=threshold,adx=adx)
for n in (3,6,12,14,18,24):add('warmup_control',n=n)
def gate(history,name,direction):
 from datetime import datetime
 from zoneinfo import ZoneInfo
 c=RULES[name];family=c['family']
 if family=='baseline':return True
 n=c.get('n',1)
 if len(history)<n+1:return False
 w=history[-n-1:];r=w[-1];sign=1 if direction=='BULLISH' else -1
 if len({datetime.fromtimestamp(x['timestamp'],ZoneInfo('Asia/Kolkata')).date() for x in w})!=1:return False
 if family=='warmup_control':return True
 atr=r.get('host_atr')
 if not atr or atr<=0:return False
 ratio=None
 if c.get('floor') or family=='atr_band':
  prev=[x.get('host_atr') for x in history[-61:-1]]
  if len(prev)!=60 or any(x is None for x in prev):return False
  median=sorted(prev)[30]
  if median<=0:return False
  ratio=atr/median
  if ratio<c.get('floor',0):return False
 if family in ('efficiency','efficiency_chop'):
  selected=w if family=='efficiency' else w[-13:]
  close=[x['close'] for x in selected]
  travel=sum(abs(b-a) for a,b in zip(close,close[1:]))
  efficiency=sign*(close[-1]-close[0])/travel if travel else 0
  if efficiency<c['threshold']:return False
  if family=='efficiency':return True
 if family in ('choppiness','efficiency_chop'):
  tr=[max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close'])) for a,b in zip(w,w[1:])]
  width=max(x['high'] for x in w[1:])-min(x['low'] for x in w[1:])
  chop=100*math.log10(max(1,sum(tr)/width))/math.log10(n) if width else 100
  return chop<=c.get('chop',c['threshold'])
 if family=='adx':
  adx=r.get('adx');old=w[0].get('adx')
  return adx is not None and adx>=c['threshold'] and (not c['rising'] or old is not None and adx>old)
 if family in ('ema_slope','st_slope'):
  if family=='st_slope':
   if len({x['pine_direction'] for x in w})!=1:return False
   slope=sign*(r['supertrend']-w[0]['supertrend'])/(n*r['box'])
  else:slope=sign*(r['ema30']-w[0]['ema30'])/(n*atr)
  return slope>0 if c['threshold']==0 else slope>=c['threshold']
 if family=='breakout':
  return r['close']>max(x['high'] for x in w[:-1])+c['offset']*atr if sign>0 else r['close']<min(x['low'] for x in w[:-1])-c['offset']*atr
 if family=='overlap':
  ratios=[max(0,min(a['high'],b['high'])-max(a['low'],b['low']))/max(a['high']-a['low'],b['high']-b['low'],.05) for a,b in zip(w,w[1:])]
  return sum(ratios)/len(ratios)<=c['threshold']
 if family=='atr_band':return c['low']<=ratio<=c['high']
 if family=='not_flat':return len({x['pine_direction'] for x in w})!=1 or max(x['supertrend'] for x in w)-min(x['supertrend'] for x in w)>.025
 if family=='rsi_strength':
  rsi=r.get('rsi14');adx=r.get('adx')
  return rsi is not None and (rsi>=c['threshold'] if sign>0 else rsi<=100-c['threshold']) and (not c['adx'] or adx is not None and adx>=c['adx'])
 raise ValueError('Unknown declared filter')
