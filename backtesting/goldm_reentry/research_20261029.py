"""Frozen GOLDM underlying proxy experiment. Never imports runner or broker."""
import json,hashlib,math,csv
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from strategies.renko_supertrend.signals import Engine
ROOT=Path('/home/trading/sector-heatmap')
SRC=ROOT/'.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/source/.private/renko-instances/07acc5dc41afde1fbb2a'
OUT=ROOT/'output/goldm-reentry-20261029'
OUT.mkdir(parents=True,exist_ok=True)
snap=SRC/'state.json'; hist=SRC/'chart-history/6f7420a9759ac97e79faf3d4b23849ac6d62e16ad8056ddab22a18e4651baee2.json'
raw=hist.read_bytes(); cfg=json.loads(snap.read_text())['config']; refs=cfg['_session_auto_references']
tz=ZoneInfo('Asia/Kolkata')
rows=json.loads(raw)['rows']; unique={}
for r in rows:
 if r[0] in unique and unique[r[0]]!=r:raise ValueError('Conflicting timestamps')
 if not 0<r[3]<=min(r[1],r[4])<=max(r[1],r[4])<=r[2]:raise ValueError('Invalid OHLC')
 unique[r[0]]=r
rows=[unique[k] for k in sorted(unique)]
def day(t):return datetime.fromtimestamp(t,tz).strftime('%Y-%m-%d')
days=sorted({day(r[0]) for r in rows}); warm=days[:5]; testdays=days[5:]; cut=int(len(testdays)*.7); dev=testdays[:cut]; hold=testdays[cut:]
# Freeze input before computing candidates.
manifest={'source':str(hist),'sha256':hashlib.sha256(raw).hexdigest(),'candles':len(rows),'dates':days,'warmup':warm,'development':dev,'chronological_comparison':hold,'note':'Later historical comparison, not prospective untouched holdout. The current session motivated hypothesis.',
'policies':['reversal','next_aligned_brick','pullback_only','reversal_plus_pullback'],'box_multipliers':[.75,1,1.25],
'fill':'Next contiguous one-minute open after confirming close. At most one entry/exit decision per observation. Session close liquidation at last observed close. No synthetic brick-price fills.',
'scope':'Underlying directional points only; no option returns, spreads or fees. Flat overnight. Five-minute session-scaled box sampled using one-minute completed closes; no invented OHLC tick ordering.',
'daily_entry_cap':12,'delayed_execution_sensitivity':'One additional minute; pending fills suppress intervening decisions.','config':{k:v for k,v in cfg.items() if not k.startswith('_')}}
(OUT/'input-candles.json').write_bytes(raw)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
def generate(mult):
 innercfg={**cfg,'strategy_basis':'CANDLESTICK','brick_mode':'Manual','manual_brick':1,'_brick_input':True,'chart_entry_guards':False,'session_deadline':None}
 engine=Engine(innercfg,1)
 result=[]; current=None; level=None; direction=0
 for i,r in enumerate(rows):
  date=day(r[0]); dt=datetime.fromtimestamp(r[0],tz); start=dt.replace(hour=9,minute=0,second=0,microsecond=0).timestamp()
  ref=refs.get(str(int(start)))
  if not ref or ref['available_at']>start:continue
  box=ref['session_reference']*300/(ref['session_end']-ref['session_start'])*mult
  box=max(1,box)
  if date!=current:current=date;level=math.floor(r[4]/box);direction=0
  events=[]
  while True:
   up=r[4]/box-level >= (2 if direction<0 else 1)-1e-10
   down=level-r[4]/box >= (2 if direction>0 else 1)-1e-10
   if not up and not down:break
   side=1 if up else -1;opening=level+(side if direction and direction!=side else 0);level=opening+side;direction=side
   a,b=opening*box,level*box
   stamp=r[0]+(len(events)+1)*.000001
   s=engine.update(dict(timestamp=stamp,open=a,close=b,high=max(a,b),low=min(a,b),volume=None))
   events.append({'st':s['direction'],'brick':'BULLISH' if side>0 else 'BEARISH','cross':s.get('raw_supertrend_cross_direction'),'qualified':s.get('entry_qualified',False)})
  result.append({'i':i,'day':date,'events':events,'box':box})
 return result
def simulate(obs,policy,delay=0):
 trades=[];pos=None;episode=None;pull=False;wait=None;entries=0;daily_entries=0
 def close(price,t,reason):
  nonlocal pos
  if pos:
   trades.append({**pos,'exit_price':price,'exit_at':t,'reason':reason,'points':(price-pos['price'])*(1 if pos['side']=='BULLISH' else -1)})
   pos=None
 prior=None;busy_until=0
 for o in obs:
  i=o['i'];r=rows[i];date=o['day']
  if prior and date!=prior['day']:
   z=rows[prior['i']];close(z[4],z[0]+60,'SESSION_END');episode=None;pull=False;wait=None;entries=0;daily_entries=0
  prior=o
  if r[0]<busy_until:continue
  if not o['events']:continue
  j=i+1+delay
  contiguous=j<len(rows) and all(rows[k+1][0]==rows[k][0]+60 for k in range(i,j)) and day(rows[j][0])==date
  if not contiguous:continue
  ex=rows[j][1];at=rows[j][0];candidate=None;exit_side=None
  for e in o['events']:
   if e['st']!=episode:episode=e['st'];entries=0;pull=False;wait=None
   if pos and e['st']!=pos['side']:exit_side=e['st']
   if e['brick']!=e['st']:pull=True
   aligned=e['brick']==e['st']
   if policy=='reversal' and e['qualified'] and e['cross']:candidate=e['st']
   if policy=='next_aligned_brick':
    if wait and aligned and wait==e['st']:candidate=e['st'];wait=None
    if e['cross']:wait=e['st']
   if policy in ('pullback_only','reversal_plus_pullback') and aligned and pull and entries<2:candidate=e['st'];pull=False
   if policy=='reversal_plus_pullback' and e['qualified'] and e['cross']:candidate=e['st']
  # Reject a signal reversed again within the same observed minute.
  if candidate!=o['events'][-1]['st']:candidate=None
  if exit_side:close(ex,at,'ST_REVERSAL');busy_until=at;continue
  if not pos and candidate and date not in warm and daily_entries<12:
   pos={'day':date,'side':candidate,'price':ex,'entry_at':at};entries+=1;daily_entries+=1;busy_until=at
 if prior:
  z=rows[prior['i']];close(z[4],z[0]+60,'END_OF_DATA')
 return trades
def stats(ts,selected):
 t=[x for x in ts if x['day'] in selected];v=[x['points'] for x in t];eq=peak=dd=0;streak=worst=0
 for x in v:
  eq+=x;peak=max(peak,eq);dd=max(dd,peak-eq);streak=streak+1 if x<0 else 0;worst=max(worst,streak)
 gains=sum(max(x,0) for x in v);loss=-sum(min(x,0) for x in v)
 return {'trades':len(v),'points':round(sum(v),2),'win_pct':round(100*sum(x>0 for x in v)/len(v),2) if v else None,'expectancy':round(sum(v)/len(v),2) if v else None,'profit_factor':round(gains/loss,3) if loss else None,'closed_trade_drawdown':round(dd,2),'max_losing_streak':worst}
results=[]
for mult in [.75,1,1.25]:
 obs=generate(mult)
 for policy in manifest['policies']:
  ts=simulate(obs,policy);delayed=simulate(obs,policy,1);item={'box_multiplier':mult,'policy':policy,'development':stats(ts,dev),'comparison':stats(ts,hold),'all':stats(ts,testdays),'delayed_comparison':stats(delayed,hold)}
  results.append(item)
  (OUT/(str(mult)+'-'+policy+'-trades.json')).write_text(json.dumps(ts,indent=2))
 print('completed box',mult,flush=True)
(OUT/'results.json').write_text(json.dumps(results,indent=2))
lines=['# GOLDM Renko entry research','',manifest['scope'],'',manifest['fill'],'','Source: '+str(len(rows))+' one-minute candles, '+days[0]+' through '+days[-1]+'. Five sessions warmup; '+str(len(dev))+' development sessions; '+str(len(hold))+' later comparison sessions.','', 'Drawdown below uses closed trades only; intratrade drawdown is not measured. No option P&L inference.','', '| Box | Policy | Dev points | Later points | Later trades | Later PF | Later DD |','|---|---|---:|---:|---:|---:|---:|']
for x in results:
 a=x['comparison'];lines.append(f"| {x['box_multiplier']} | {x['policy']} | {x['development']['points']} | {a['points']} | {a['trades']} | {a['profit_factor']} | {a['closed_trade_drawdown']} |")
(OUT/'report.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(results,indent=2))

