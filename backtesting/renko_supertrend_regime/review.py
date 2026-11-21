"""Read-only index signal study. No broker execution or runner modifications."""
import csv,json,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from strategies.renko_supertrend.signals import Engine
IST=ZoneInfo('Asia/Kolkata');ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
DATA=ROOT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_5m.csv'
SETTINGS=ROOT/'.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/source/.private/renko-instances/9abcfe9c2d417c1e7efe/renko-supertrend-settings.json'
RULES=[('Baseline',0,0,0,99)]+[(f'ST{n}_move{m}',n,m,2,3) for n in (6,12) for m in (.25,.5,1.)]+[('ST12_persistent',12,.5,3,2)]
def day(r):return datetime.fromtimestamp(r['timestamp'],IST).date().isoformat()
def assess(rows,rule):
 _,n,move,advances,maxflat=rule
 if not n:return dict(allowed=True,state='BASELINE')
 if len(rows)<n+1:return dict(allowed=False,state='WARMUP')
 w=rows[-n-1:]
 if len({day(r) for r in w})!=1:return dict(allowed=False,state='SESSION_WARMUP')
 sign=1 if w[-1]['pine_direction']<0 else -1
 flips=sum(a['pine_direction']!=b['pine_direction'] for a,b in zip(w,w[1:]))
 ds=[sign*(b['supertrend']-a['supertrend']) for a,b in zip(w,w[1:])]
 count=sum(d>.025 for d in ds);flat=0
 for d in reversed(ds):
  if abs(d)<=.025:flat+=1
  else:break
 displacement=sign*(w[-1]['supertrend']-w[0]['supertrend'])/w[-1]['box']
 allowed=flips==0 and displacement>=move and count>=advances and flat<=maxflat and min(ds)>=-.025
 return dict(allowed=allowed,state='TRENDING' if allowed else 'FLAT' if displacement<.25 and not flips else 'TRANSITION',move_boxes=displacement,advances=count,flat_bars=flat,flips=flips)
def summary(rows):
 v=[r['points'] for r in rows];wins=[x for x in v if x>0];loss=[x for x in v if x<0]
 return dict(samples=len(v),mean_points=sum(v)/len(v) if v else None,positive_pct=100*len(wins)/len(v) if v else None,
 profit_factor=sum(wins)/-sum(loss) if loss else None,mean_after_2_point_drag=sum(v)/len(v)-2 if v else None,
 flip_next_30m_pct=100*sum(r['future_flip'] for r in rows)/len(v) if v else None)
def main():
 saved=json.loads(SETTINGS.read_text())['settings'];c={k.replace('-','_'):v for k,v in saved.items()}
 for k in ('atr_length','factor','manual_brick','adx_threshold','adx_length','adx_smoothing','widening_window','ema_fast_length','ema_slow_length','ema_third_length','ema_exit_length'):
  if k in c:c[k]=float(c[k]) if k in ('factor','manual_brick','adx_threshold') else int(c[k])
 c.update(underlying=saved['symbol'],session_deadline='15:10')
 raw=[];excluded=0
 with DATA.open() as f:
  for x in csv.DictReader(f):
   t=datetime.fromtimestamp(int(x['epoch']),IST)
   if t.date().isoformat()<'2025-09-01':continue
   if t.weekday()>4 or not 555<=t.hour*60+t.minute<930:excluded+=1;continue
   raw.append(dict(timestamp=int(x['epoch']),**{k:float(x[k]) for k in ('open','high','low','close','volume')}))
 e=Engine(c,.05);rows=[e.update(r) for r in raw];features=[]
 for i,r in enumerate(rows):
  d=day(r)
  if not '2025-10-25'<=d<='2026-10-23' or not r.get('entry_direction') or i+7>=len(rows):continue
  future=rows[i+1:i+8]
  if any(day(x)!=d for x in future) or any(b['timestamp']-a['timestamp']!=300 for a,b in zip([r]+future,future)):continue
  sign=1 if r['entry_direction']=='BULLISH' else -1
  item=dict(timestamp=r['timestamp'],day=d,period='development' if d<'2026-04-25' else 'validation' if d<'2026-07-25' else 'holdout',
   direction=r['entry_direction'],points=sign*(future[-1]['open']-future[0]['open']),
   future_flip=any(x['pine_direction']!=r['pine_direction'] for x in future[:-1]))
  for rule in RULES:features.append(dict(rule=rule[0],**item,**assess(rows[max(0,i-30):i+1],rule)))
 results={rule[0]:{p:summary([x for x in features if x['rule']==rule[0] and x['allowed'] and (p=='all' or x['period']==p)]) for p in ('development','validation','holdout','all')} for rule in RULES}
 base=results['Baseline']['validation'];eligible=[]
 for rule in RULES[1:]:
  s=results[rule[0]]['validation']
  if s['samples']>=30 and s['mean_points']>base['mean_points'] and s['flip_next_30m_pct']<base['flip_next_30m_pct']:eligible.append((s['mean_points'],rule[0]))
 result=dict(scope='NIFTY index forward signal quality; not option P&L',window=['2025-10-25','2026-10-23'],
 source_sha256=hashlib.sha256(DATA.read_bytes()).hexdigest(),settings=c,excluded_off_hours=excluded,host_bars=len(rows),
 year_sessions=len({day(r) for r in rows if '2025-10-25'<=day(r)<='2026-10-23'}),rules=RULES,results=results,
 validation_selected_rule=max(eligible)[1] if eligible else None)
 (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False))
 with (OUT/'signal_features.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=sorted(set().union(*(x.keys() for x in features))));w.writeheader();w.writerows(features)
 print(json.dumps(dict(sessions=result['year_sessions'],selected=result['validation_selected_rule'],results=results),indent=2))
if __name__=='__main__':main()
