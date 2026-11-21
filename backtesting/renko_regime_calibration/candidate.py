"""Frozen paper-research assessment only. Never imports or calls an order adapter."""
from datetime import datetime
from zoneinfo import ZoneInfo
import math
PROFILE=dict(name='Directional efficiency and volatility',lookback=18,minimum_efficiency=.15,
 minimum_atr_ratio=1.,atr_reference=60,host_seconds=300,scope='PAPER_RESEARCH_ONLY')
def assess(rows,direction,now):
 if direction not in ('BULLISH','BEARISH'):raise ValueError('Explicit directional setup required.')
 def result(allowed,reason,**evidence):return dict(allowed=allowed,reason=reason,profile=PROFILE,**evidence)
 completed=[]
 last=None
 for row in rows:
  stamp=row.get('timestamp')
  if not isinstance(stamp,(int,float)) or isinstance(stamp,bool) or not math.isfinite(stamp):raise ValueError('Finite chronological timestamps required.')
  if last is not None and stamp<=last:raise ValueError('Feed each host candle once in chronological order.')
  last=stamp
  if row.get('is_forming') or stamp+300>now:continue
  completed.append(row)
 if len(completed)<61:return result(False,'WARMUP')
 window=completed[-19:]
 if any(b['timestamp']-a['timestamp']!=300 for a,b in zip(window,window[1:])):return result(False,'MISSING_HOST_BAR')
 zone=ZoneInfo('Asia/Kolkata')
 if len({datetime.fromtimestamp(r['timestamp'],zone).date() for r in window})!=1:return result(False,'SESSION_WARMUP')
 values=[r.get('host_atr') for r in completed[-61:]]
 if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in values):return result(False,'ATR_UNAVAILABLE')
 closes=[r.get('close') for r in window]
 if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in closes):return result(False,'PRICE_UNAVAILABLE')
 sign=1 if direction=='BULLISH' else -1
 travel=sum(abs(b-a) for a,b in zip(closes,closes[1:]))
 efficiency=sign*(closes[-1]-closes[0])/travel if travel else 0
 # Higher quantile convention matches the frozen calibration exactly.
 reference=sorted(values[:-1])[30];ratio=values[-1]/reference
 evidence=dict(directional_efficiency=efficiency,atr_ratio=ratio,atr_reference=reference,current_atr=values[-1],decision_at=completed[-1]['timestamp']+300)
 if efficiency<.15:return result(False,'INSUFFICIENT_DIRECTIONAL_PROGRESS',**evidence)
 if ratio<1:return result(False,'VOLATILITY_BELOW_REFERENCE',**evidence)
 return result(True,'REGIME_ELIGIBLE',**evidence)
