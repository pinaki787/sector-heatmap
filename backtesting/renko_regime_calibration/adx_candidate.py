"""Frozen primary paper-research gate. Does not authorize or submit trades."""
from datetime import datetime
from zoneinfo import ZoneInfo
import math
PROFILE=dict(name='Rising ADX with adequate volatility',adx_period=14,adx_minimum=15.,
 rise_lookback=3,atr_period=5,atr_reference=60,atr_minimum_ratio=.8,host_seconds=300,scope='PAPER_RESEARCH_ONLY')
def assess(rows,direction,now):
 if direction not in ('BULLISH','BEARISH'):raise ValueError('An existing directional entry setup is required.')
 def result(allowed,reason,**evidence):return dict(allowed=allowed,reason=reason,profile=dict(PROFILE),**evidence)
 completed=[];previous=None
 for r in rows:
  t=r.get('timestamp')
  if not isinstance(t,(int,float)) or isinstance(t,bool) or not math.isfinite(t):raise ValueError('Finite chronological timestamps required.')
  if previous is not None and t<=previous:raise ValueError('Feed each completed host bar once in order.')
  previous=t
  if r.get('is_forming') or t+300>now:continue
  completed.append(r)
 if len(completed)<61:return result(False,'WARMUP')
 window=completed[-4:]
 if any(b['timestamp']-a['timestamp']!=300 for a,b in zip(window,window[1:])):return result(False,'MISSING_HOST_BAR')
 zone=ZoneInfo('Asia/Kolkata')
 if len({datetime.fromtimestamp(r['timestamp'],zone).date() for r in window})!=1:return result(False,'SESSION_WARMUP')
 valid=lambda x:isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
 atr=[r.get('host_atr') for r in completed[-61:]]
 current=window[-1].get('adx');old=window[0].get('adx')
 if any(not valid(x) or x<=0 for x in atr):return result(False,'ATR_UNAVAILABLE')
 if not valid(current) or not valid(old):return result(False,'ADX_UNAVAILABLE')
 reference=sorted(atr[:-1])[30];ratio=atr[-1]/reference
 evidence=dict(adx=current,adx_three_bars_ago=old,atr_ratio=ratio,atr_reference=reference,decision_at=window[-1]['timestamp']+300)
 if ratio<.8:return result(False,'VOLATILITY_BELOW_REFERENCE',**evidence)
 if current<15:return result(False,'WEAK_TREND_STRENGTH',**evidence)
 if current<=old:return result(False,'TREND_STRENGTH_NOT_RISING',**evidence)
 return result(True,'REGIME_ELIGIBLE',**evidence)
