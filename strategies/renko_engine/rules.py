"""Independent Renko Engine rules shared by execution and historical replay."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import math

IST=ZoneInfo('Asia/Kolkata')
STRATEGY='RENKO_ENGINE_V1'
DEFAULTS=dict(mode='Percentage',percent=.66,fixedBox=50,basis='Current close',stepping='Whole bricks',reversalBricks=1,roundBrick=False,anchorTime='2026-09-01T09:15',seedLevel=0,seedTrend=0,rule='EMA cross + Renko direction',direction='Both',sessionOnly=True,session='0915-1505',flatHour=15,flatMinute=10,endTime='2026-12-31T23:59',showCPR=True,showRange=True,rangeSession='1245-1300',showFR=True)
def epoch(value):return datetime.fromisoformat(value).replace(tzinfo=IST).timestamp()
def minute(t):
 d=datetime.fromtimestamp(t,IST);return d.hour*60+d.minute
def inside(t,session):
 a,b=[int(x[:2])*60+int(x[2:]) for x in session.split('-')]
 m=minute(t);return a<=m<b if a<=b else m>=a or m<b
def settings(raw):
 if not isinstance(raw,dict) or set(raw)-set(DEFAULTS):raise ValueError('Unknown Renko Engine settings.')
 c={**DEFAULTS,**raw}
 for k,choices in dict(mode=['Percentage','Fixed'],basis=['Current close','Previous close','Previous daily close'],stepping=['Whole bricks','One brick per bar','Price minus brick'],rule=['EMA cross + Renko direction','EMA crossing Renko','Aligned state transition','Renko reversal'],direction=['Both','Long only','Short only']).items():
  if c[k] not in choices:raise ValueError('Invalid '+k)
 for k in ['roundBrick','sessionOnly','showCPR','showRange','showFR']:
  if type(c[k]) is not bool:raise ValueError('Invalid boolean '+k)
 for k in ['percent','fixedBox','seedLevel','reversalBricks','seedTrend','flatHour','flatMinute']:
  if isinstance(c[k],bool):raise ValueError('Invalid numeric '+k)
  try:c[k]=float(c[k])
  except (ValueError,TypeError):raise ValueError('Invalid numeric '+k) from None
  if not math.isfinite(c[k]):raise ValueError('Invalid numeric '+k)
 for k,lo,hi in [('reversalBricks',1,3),('seedTrend',-1,1),('flatHour',0,23),('flatMinute',0,59)]:
  if not c[k].is_integer() or not lo<=c[k]<=hi:raise ValueError('Invalid '+k)
  c[k]=int(c[k])
 if c['percent']<=0 or c['fixedBox']<=0 or c['seedLevel']<0:raise ValueError('Invalid brick or seed level.')
 import re
 for k in ['session','rangeSession']:
  if not isinstance(c[k],str) or not re.fullmatch(r'([01]\d|2[0-3])[0-5]\d-([01]\d|2[0-3])[0-5]\d',c[k]):raise ValueError('Invalid session.')
 if epoch(c['anchorTime'])>epoch(c['endTime']):raise ValueError('Anchor must precede research end.')
 return c

def replay(candles,raw=None,tick=.05,seconds=300,commission=.0003,slippage_ticks=2,capital=1000000):
 c=settings(raw or {})
 if not math.isfinite(tick) or tick<=0 or seconds<=0:raise ValueError('Verified positive tick and timeframe required.')
 if any(not math.isfinite(x) or x<0 for x in [commission,slippage_ticks,capital]) or capital<=0:raise ValueError('Invalid research costs or capital.')
 level=None;trend=0;fast=slow=None;previous=None;aligned_l=aligned_s=False
 pos=pending=None;equity=capital;daily=prior_day=None;rows=[];events=[]
 def fill(side,price,t,reason):
  nonlocal pos,equity
  if pos:
   gross=(price-pos['price'])*pos['side'];cost=(abs(price)+abs(pos['price']))*commission
   equity+=gross-cost;events.append(dict(time=t,action='EXIT',side=pos['side'],price=price,reason=reason,gross=gross,net=gross-cost));pos=None
  if side:
   pos=dict(side=side,price=price);events.append(dict(time=t,action='BUY' if side>0 else 'SELL',side=side,price=price,reason=reason))
 for b in candles:
  if b.get('is_forming'):continue
  t=b['timestamp']
  if any(isinstance(b.get(k),bool) or not isinstance(b.get(k),(int,float)) or not math.isfinite(b[k]) for k in ['timestamp','open','high','low','close']):raise ValueError('Invalid OHLC history.')
  if b['high']<max(b['open'],b['close'],b['low']) or b['low']>min(b['open'],b['close']) or previous and t<=previous['timestamp']:raise ValueError('OHLC must be valid, ordered and unique.')
  if pending:
   side=pending['side'];slip=(side or -(pos['side'] if pos else 0))*slippage_ticks*tick;fill(side,b['open']+slip,t,pending['reason']);pending=None
  key=datetime.fromtimestamp(t,IST).date().isoformat()
  if daily is None or daily['key']!=key:prior_day=daily;daily=dict(key=key,high=b['high'],low=b['low'],close=b['close'])
  else:daily.update(high=max(daily['high'],b['high']),low=min(daily['low'],b['low']),close=b['close'])
  old_fast,old_slow,old_level,old_trend=fast,slow,level,trend
  fast=b['close'] if fast is None else fast+2/11*(b['close']-fast)
  slow=b['close'] if slow is None else slow+2/31*(b['close']-slow)
  base=(prior_day or {}).get('close') if c['basis']=='Previous daily close' else (previous or {}).get('close') if c['basis']=='Previous close' else b['close']
  raw_brick=c['fixedBox'] if c['mode']=='Fixed' else base*c['percent']/100 if base is not None else None
  brick=max(tick,math.floor(raw_brick/tick+.5)*tick if c['roundBrick'] else raw_brick) if raw_brick is not None else None
  if t>=epoch(c['anchorTime']) and brick is not None:
   if level is None:level=c['seedLevel'] if c['seedLevel']>0 else b['close'];trend=c['seedTrend']
   else:
    delta=b['close']-level;candidate=(delta>0)-(delta<0);threshold=brick*(c['reversalBricks'] if trend and candidate!=trend else 1)
    if abs(delta)>=threshold:
     advance=brick if c['stepping']=='One brick per bar' else math.floor(abs(delta)/brick)*brick
     level=b['close']-candidate*brick if c['stepping']=='Price minus brick' else level+candidate*advance;trend=candidate
  al=trend==1 and fast>slow and b['close']>level
  ash=trend==-1 and fast<slow and b['close']<level
  if c['rule']=='EMA cross + Renko direction':long=old_fast is not None and old_fast<=old_slow and fast>slow and trend==1;short=old_fast is not None and old_fast>=old_slow and fast<slow and trend==-1
  elif c['rule']=='EMA crossing Renko':long=old_level is not None and old_fast<=old_level and fast>level and fast>slow;short=old_level is not None and old_fast>=old_level and fast<level and fast<slow
  elif c['rule']=='Aligned state transition':long=al and not aligned_l;short=ash and not aligned_s
  else:long=trend==1 and old_trend!=1;short=trend==-1 and old_trend!=-1
  active=epoch(c['anchorTime'])<=t<=epoch(c['endTime'])
  square=c['sessionOnly'] and minute(t+seconds)>=c['flatHour']*60+c['flatMinute']
  eligible=active and (not c['sessionOnly'] or inside(t,c['session'])) and not square
  if square or t>epoch(c['endTime']):
   pending=None
   if pos:fill(0,b['close']-pos['side']*slippage_ticks*tick,t+seconds,'Research session/end')
  elif active and (long or short):
   side=1 if long else -1;allowed=eligible and (c['direction']!='Short only' if side>0 else c['direction']!='Long only')
   if allowed and (pos or {}).get('side')!=side:pending=dict(side=side,reason='Hypothesis '+('long' if side>0 else 'short'))
   elif pos and pos['side']!=side:pending=dict(side=0,reason='Opposite signal')
  direction='BULLISH' if trend==1 else 'BEARISH' if trend==-1 else None
  raw_direction='BULLISH' if long else 'BEARISH' if short else None
  entry=raw_direction if eligible and (c['direction']!='Short only' if long else c['direction']!='Long only') else None
  rows.append(dict(b,time=t,level=level,trend=trend,brick=brick,fast=fast,slow=slow,long=bool(eligible and long),short=bool(eligible and short),direction=direction,cross_direction=raw_direction,entry_direction=entry,entry_qualified=bool(entry),signal_allowed=bool(eligible),squareoff=bool(square or t>epoch(c['endTime']))))
  previous=b;aligned_l=al;aligned_s=ash
 return dict(rows=rows,events=events,equity=equity,position=pos,pending=pending)
