"""Optional calibrated entry overlap and frozen per-position underlying ATR plan."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
REVISION='overlap-atr-profile-v1'
DEFAULTS=dict(calibrated_enabled=False,calibrated_overlap_pairs=6,calibrated_overlap_max=.4,
 calibrated_stop_atr=3.,calibrated_target_atr=1.5)
def settings(payload):
 result={k:payload.get(k,v) for k,v in DEFAULTS.items()}
 if type(result['calibrated_enabled']) is not bool:raise ValueError('Calibrated profile must be enabled or disabled explicitly.')
 raw=result['calibrated_overlap_pairs']
 try:n=int(raw)
 except (ValueError,TypeError,OverflowError):raise ValueError('Overlap window must be 2–30 whole candles.') from None
 if isinstance(raw,bool) or float(raw)!=n or not 2<=n<=30:raise ValueError('Overlap window must be 2–30 whole candles.')
 result['calibrated_overlap_pairs']=n
 for k in ('calibrated_overlap_max','calibrated_stop_atr','calibrated_target_atr'):
  raw=result[k]
  try:v=float(raw)
  except (ValueError,TypeError,OverflowError):raise ValueError('Calibrated parameters must be finite numbers.') from None
  if isinstance(raw,bool) or not math.isfinite(v) or (not 0<=v<=1 if k=='calibrated_overlap_max' else not 0<v<=20):raise ValueError('Calibrated parameter outside its allowed range.')
  result[k]=v
 return result
def compatible(config):
 if not config.get('calibrated_enabled'):return
 if config.get('underlying')!='NSE:NIFTY50-INDEX' or config.get('timeframe')!='5 minutes':
  raise ValueError('This calibrated profile is scoped to NIFTY 50 on five-minute host candles; disable it for other instruments/timeframes.')
 if config.get('intrabar_entries'):raise ValueError('Calibrated overlap requires completed-candle entries.')
 if any(config.get(k) not in (None,'') for k in ('spot_target','spot_stop')):
  raise ValueError('Clear absolute underlying stop/target when using the calibrated ATR plan.')
def check(rows,config,seconds=300):
 c=settings(config)
 if not c['calibrated_enabled']:return dict(enabled=False,allowed=True,reason='OFF')
 n=c['calibrated_overlap_pairs']
 base=dict(enabled=True,revision=REVISION,pairs=n,maximum=c['calibrated_overlap_max'])
 if len(rows)<n+1:return dict(base,allowed=False,reason='WAITING_CALIBRATED_WARMUP')
 w=rows[-n-1:]
 if len({datetime.fromtimestamp(r['timestamp'],ZoneInfo('Asia/Kolkata')).date() for r in w})!=1:
  return dict(base,allowed=False,reason='WAITING_CALIBRATED_SESSION')
 if any(b['timestamp']-a['timestamp']!=seconds for a,b in zip(w,w[1:])):
  return dict(base,allowed=False,reason='WAITING_CALIBRATED_HISTORY')
 ratios=[]
 for a,b in zip(w,w[1:]):
  if any(not isinstance(r.get(k),(float,int)) or isinstance(r[k],bool) or not math.isfinite(r[k]) for r in (a,b) for k in ('high','low')):
   return dict(base,allowed=False,reason='WAITING_CALIBRATED_HISTORY')
  if any(r['high']<r['low'] or r['low']<=0 for r in (a,b)):return dict(base,allowed=False,reason='WAITING_CALIBRATED_HISTORY')
  ratios.append(max(0,min(a['high'],b['high'])-max(a['low'],b['low']))/max(a['high']-a['low'],b['high']-b['low'],.05))
 average=sum(ratios)/n;allowed=average<=c['calibrated_overlap_max']
 return dict(base,allowed=allowed,average_overlap=average,reason='PASS' if allowed else 'WAITING_CALIBRATED_OVERLAP')
def plan(config,price,atr,direction,tick=.05,signal_at=None):
 c=settings(config)
 if not c['calibrated_enabled']:return None
 if direction not in ('BULLISH','BEARISH'):raise ValueError('ATR plan requires a directional entry.')
 if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in (price,atr,tick)):raise ValueError('Fresh underlying price, completed ATR and tick size are required.')
 sign=1 if direction=='BULLISH' else -1
 def round_level(value,up):
  return float((Decimal(str(value))/Decimal(str(tick))).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)*Decimal(str(tick)))
 stop=round_level(price-sign*c['calibrated_stop_atr']*atr,sign<0)
 target=round_level(price+sign*c['calibrated_target_atr']*atr,sign>0)
 if min(stop,target)<=0:raise ValueError('Calibrated underlying levels must be positive.')
 return dict(revision=REVISION,spot_stop=stop,spot_target=target,anchor_price=price,completed_atr=atr,
  signal_at=signal_at,stop_atr=c['calibrated_stop_atr'],target_atr=c['calibrated_target_atr'],
  basis='UNDERLYING_PRICE',scope='Frozen new-position levels; not option-premium prices.')
def effective(config,position):
 levels=(position or {}).get('calibrated_levels') or {}
 return dict(config,**{k:levels[k] for k in ('spot_stop','spot_target') if k in levels})
