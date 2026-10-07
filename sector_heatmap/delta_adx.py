"""Wilder ADX(14) on completed candles only; optional runner entry gate."""
import math

def series(candles, period=14):
 rows=[r for r in candles if not r.get('is_forming')]
 result={r['timestamp']:None for r in rows};tr=[];plus=[];minus=[];dx=[];adx=None
 for previous,row in zip(rows,rows[1:]):
  up=row['high']-previous['high'];down=previous['low']-row['low']
  tr.append(max(row['high']-row['low'],abs(row['high']-previous['close']),abs(row['low']-previous['close'])))
  plus.append(up if up>down and up>0 else 0.0);minus.append(down if down>up and down>0 else 0.0)
  if len(tr)<period:continue
  if len(tr)==period:t,p,m=sum(tr),sum(plus),sum(minus)
  else:t,p,m=t-t/period+tr[-1],p-p/period+plus[-1],m-m/period+minus[-1]
  total=p+m;current=100*abs(p-m)/total if total else 0.0;dx.append(current)
  if len(dx)==period:adx=sum(dx)/period
  elif len(dx)>period:adx=(adx*(period-1)+current)/period
  result[row['timestamp']]=adx
 return result

def settings(payload):
 enabled=payload.get('adx_enabled',False);threshold=payload.get('adx_threshold',25)
 if not isinstance(enabled,bool):raise ValueError('ADX enabled must be true or false.')
 if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or not 0<threshold<100:raise ValueError('Minimum ADX must be a number above 0 and below 100.')
 return dict(adx_enabled=enabled,adx_threshold=float(threshold),adx_period=14)

def allows(cfg,value):
 return not cfg.get('adx_enabled',False) or isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>cfg.get('adx_threshold',25)
