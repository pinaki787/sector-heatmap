"""Optional entry-only price-marker confirmation on completed host candles."""
import math
DEFAULTS=dict(manual_trend_enabled=False,manual_trend_bullish=None,manual_trend_bearish=None,manual_trend_closes=2)
REVISION='manual-price-marker-consecutive-v1'
def settings(payload):
 c={k:payload.get(k,v) for k,v in DEFAULTS.items()}
 if not isinstance(c['manual_trend_enabled'],bool):raise ValueError('Manual trend switch must be boolean.')
 raw=c['manual_trend_closes']
 try:
  n=int(raw)
  if isinstance(raw,bool) or float(raw)!=n or not 1<=n<=100:raise ValueError
 except (ValueError,TypeError,OverflowError):raise ValueError('Manual trend consecutive closes must be a whole number from 1 to 100.') from None
 c['manual_trend_closes']=n
 for key in ('manual_trend_bullish','manual_trend_bearish'):
  raw=c[key]
  if raw in (None,''):
   c[key]=None
   if c['manual_trend_enabled']:raise ValueError('Both manual trend price markers are required when enabled.')
  else:
   try:value=float(raw)
   except (TypeError,ValueError,OverflowError):raise ValueError('Manual trend markers must be positive prices.') from None
   if isinstance(raw,bool) or not math.isfinite(value) or value<=0:raise ValueError('Manual trend markers must be positive prices.')
   c[key]=value
 if c['manual_trend_enabled'] and c['manual_trend_bullish']<c['manual_trend_bearish']:raise ValueError('Bullish marker must be above or equal to bearish marker.')
 return c

def check(rows,config,direction,seconds):
 c=settings(config);counts={'BULLISH':0,'BEARISH':0};last=None
 if not c['manual_trend_enabled']:return dict(enabled=False,allowed=True,counts=counts,required=c['manual_trend_closes'],revision=REVISION)
 # Only completed rows participate. Duplicate polling cannot increase a count.
 unique={r['timestamp']:r for r in rows if not r.get('is_forming') and not r.get('provisional')}
 for stamp,row in sorted(unique.items()):
  price=float(row['close'])
  if not math.isfinite(price):counts={'BULLISH':0,'BEARISH':0};last=stamp;continue
  if last is not None and stamp-last!=seconds:counts={'BULLISH':0,'BEARISH':0}
  counts['BULLISH']=min(c['manual_trend_closes'],counts['BULLISH']+1) if price>c['manual_trend_bullish'] else 0
  counts['BEARISH']=min(c['manual_trend_closes'],counts['BEARISH']+1) if price<c['manual_trend_bearish'] else 0
  last=stamp
 allowed=direction in counts and counts[direction]>=c['manual_trend_closes']
 return dict(enabled=True,allowed=allowed,counts=counts,required=c['manual_trend_closes'],bullish_marker=c['manual_trend_bullish'],bearish_marker=c['manual_trend_bearish'],last_completed_at=last,revision=REVISION,reason='Manual trend confirmed.' if allowed else 'Waiting for consecutive completed closes beyond the selected manual trend marker.')

def apply(entry,gate):
 entry['manual_trend']=gate
 if not gate['allowed']:
  entry.update(entry_qualified=False,entry_direction=None,entry_buy_signal=False,entry_sell_signal=False,entry_diagnostic='WAITING_MANUAL_TREND_CONFIRMATION')
