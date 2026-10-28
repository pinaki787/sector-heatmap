"""Completed-five-minute opposing-zone entry clearance; no execution calls."""
import math
from . import zone_target
REVISION='opposing-zone-entry-v1'
DEFAULTS=dict(zone_entry_enabled=False,zone_entry_min_atr=1.,zone_entry_rearm=True)
def settings(payload):
 c={k:payload.get(k,v) for k,v in DEFAULTS.items()}
 for k in ('zone_entry_enabled','zone_entry_rearm'):
  if type(c[k]) is not bool:raise ValueError('Zone entry switches must be booleans.')
 raw=c['zone_entry_min_atr']
 try:v=float(raw)
 except (ValueError,TypeError,OverflowError):raise ValueError('Zone clearance must be a finite ATR multiple.') from None
 if isinstance(raw,bool) or not math.isfinite(v) or not .1<=v<=10:raise ValueError('Zone clearance must be from 0.1 to 10 ATR.')
 c['zone_entry_min_atr']=v
 return c
def compatible(c):
 if not c.get('zone_entry_enabled'):return
 if c.get('underlying')!='NSE:NIFTY50-INDEX' or c.get('timeframe')!='5 minutes':
  raise ValueError('The tested zone entry filter requires NIFTY 50 five-minute candles.')
 if c.get('intrabar_entries'):raise ValueError('Zone entry filtering requires completed candles.')
def check_known(known,config,direction,price,atr):
 c=settings(config);base=dict(enabled=c['zone_entry_enabled'],revision=REVISION,minimum_atr=c['zone_entry_min_atr'],rearm=c['zone_entry_rearm'])
 if not c['zone_entry_enabled']:return dict(base,allowed=True,reason='OFF')
 if direction not in ('BULLISH','BEARISH'):return dict(base,allowed=False,reason='WAITING_ZONE_DIRECTION')
 if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in (price,atr)):
  return dict(base,allowed=False,reason='WAITING_ZONE_ENTRY_EVIDENCE')
 side='supply' if direction=='BULLISH' else 'demand';z=known.get(side)
 base.update(side=side,price=price,completed_atr=atr)
 if not z or z.get('broken_at') is not None:return dict(base,allowed=True,reason='NO_ACTIVE_OPPOSING_ZONE',zone=None)
 if (price>z['upper'] if direction=='BULLISH' else price<z['lower']):
  return dict(base,allowed=True,reason='OPPOSING_ZONE_BEHIND_PRICE',zone=z)
 distance=max(0.,z['lower']-price if direction=='BULLISH' else price-z['upper'])
 ratio=distance/atr;allowed=ratio>=c['zone_entry_min_atr']
 return dict(base,allowed=allowed,reason='PASS' if allowed else 'WAITING_OPPOSING_ZONE_CLEARANCE',zone=z,distance_points=distance,distance_atr=ratio)
def assess(rows,config,direction,price,atr,now,signal_at=None):
 c=settings(config)
 if not c['zone_entry_enabled']:return check_known({},c,direction,price,atr)
 closed=[r for r in rows if not r.get('is_forming') and r['timestamp']+300<=now]
 zone_target.validate(closed)
 if len(closed)<16:raise ValueError('Completed five-minute zone warmup is unavailable.')
 last=closed[-1]
 if not 0<=now-last['timestamp']-300<300:raise ValueError('Completed five-minute zone source is stale.')
 if signal_at is not None and last['timestamp']!=signal_at:raise ValueError('Zone source and completed entry signal no longer match.')
 return dict(check_known(zone_target.zones(closed),c,direction,price,atr),source_at=last['timestamp'],observed_at=now)
