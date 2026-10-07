"""Paired option-candle exit study. Research only; contains no broker/order code."""
import json,math,csv,statistics,hashlib,bisect
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from source_snapshot.signals import rma
OUT=Path(__file__).resolve().parent;IST=ZoneInfo('Asia/Kolkata')
def date(t):return str(datetime.fromtimestamp(t,IST).date())
def write_csv(name,rows):
 if not rows:return
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def valid(c):return len(c)>=6 and all(isinstance(x,(float,int)) and math.isfinite(x) for x in c[:6]) and 0<c[3]<=min(c[1],c[4])<=max(c[1],c[4])<=c[2]
def features(rows,seconds):
 groups={}
 for r in rows:groups.setdefault(int(r['timestamp']//seconds)*seconds,[]).append(r)
 bars=[]
 for t,g in sorted(groups.items()):
  # Strictly contiguous complete bars. Missing bars never get interpolated.
  if [r['timestamp'] for r in g]!=list(range(t,t+seconds,60)):continue
  bars.append(dict(t=t,open=g[0]['open'],high=max(r['high'] for r in g),low=min(r['low'] for r in g),close=g[-1]['close']))
 output={};state={};pl=ph=None;prev=None
 for i,b in enumerate(bars):
  tr=max(b['high']-b['low'],abs(b['high']-prev['close']),abs(b['low']-prev['close'])) if prev else b['high']-b['low']
  atr=rma(state,'atr',tr,14)
  if i>=4 and bars[i]['t']-bars[i-4]['t']==4*seconds:
   window=bars[i-4:i+1];pivot=window[2]
   if pivot['low']<min(x['low'] for x in window if x is not pivot):pl=pivot['low']
   if pivot['high']>max(x['high'] for x in window if x is not pivot):ph=pivot['high']
  output[b['t']+seconds]=(atr,pl,ph);prev=b
 keys=sorted(output);result=[]
 for r in rows:
  k=bisect.bisect_right(keys,r['timestamp']+60)-1
  # Structure persists, but ATR updates only on fully completed bars.
  result.append(output[keys[k]] if k>=0 else (None,None,None))
 return result

def variants():
 result=[dict(name='baseline',family='baseline',frame=0,k=0,buffer=0,activation=0,distance=0,retain=0)]
 for d in (.06,.08,.10,.12,.15):result.append(dict(name=f'current_{d}',family='current',frame=0,k=0,buffer=0,activation=0,distance=d,retain=0))
 for frame in (1,5):
  for k in (2,3,4):
   for buffer in (.25,.5,1):result.append(dict(name=f'structure_{frame}_{k}_{buffer}',family='structure',frame=frame,k=k,buffer=buffer,activation=0,distance=0,retain=0))
 for activation in (.20,.25,.30,.025,.05,.10):
  for k in (2,3,4):
   for buffer in (.25,.5,1):
    for retain in (.4,.6,.8):result.append(dict(name=f'hybrid_{activation}_{k}_{buffer}_{retain}',family='hybrid',frame=5,k=k,buffer=buffer,activation=activation,distance=0,retain=retain))
 return result

def replay(t,rows,f1,f5,quotes,v,slip=.01,ema=True,path_model='close'):
 start=t['i'];end=t['end_i'];n=len(rows);
 if end<=start:return None
 sign=t['sign'];entry=quotes.get(rows[start]['timestamp'])
 if entry is None or entry[5]<=0:return None
 paid=entry[1]*(1+slip);best=None;uextreme=None;ustop=None;pstop=None;armed=False;reason='BASELINE';exit_i=end;trigger=None
 # Keep entries fixed; replacement arm ends before next frozen entry/session.
 limit=end if ema else t['replacement_end_i']
 for j in range(start,limit):
  r=rows[j];q=quotes.get(r['timestamp'])
  uextreme=r['close'] if uextreme is None else max(uextreme,r['close']) if sign==1 else min(uextreme,r['close'])
  if q is None or q[5]<=0:return None
  price=q[4]*(1-slip);event_hit=False
  path=[q[4]] if path_model=='close' else [q[1],q[2],q[3],q[4]] if path_model=='high_low' else [q[1],q[3],q[2],q[4]]
  for observed in path:
   executable=observed*(1-slip);best=executable if best is None else max(best,executable)
   if v['family']=='current':pstop=max(pstop or -math.inf,best*(1-v['distance']))
   if v['family']=='hybrid' and best>=paid*(1+v['activation']):
    armed=True;pstop=max(pstop or -math.inf,paid+v['retain']*(best-paid))
   if pstop is not None and executable<=pstop:event_hit=True;break
  if v['family'] in ('structure','hybrid'):
   atr,pl,ph=(f1 if v['frame']==1 else f5)[j]
   if atr is not None:
    pivot=pl if sign==1 else ph
    extreme=uextreme
    candidate=extreme-sign*v['k']*atr
    if pivot is not None:candidate=max(candidate,pivot-v['buffer']*atr) if sign==1 else min(candidate,pivot+v['buffer']*atr)
    ustop=candidate if ustop is None else max(ustop,candidate) if sign==1 else min(ustop,candidate)
  hit_p=event_hit
  hit_u=ustop is not None and sign*(r['close']-ustop)<=0
  if hit_p or hit_u:
   exit_i=j+1;trigger=j;reason='PREMIUM' if hit_p else 'STRUCTURE';break
  if not ema and j>=end-1:
   opposite=r['cross_direction']==('BEARISH' if sign==1 else 'BULLISH')
   if opposite:exit_i=j+1;reason='REVERSAL';break
 x=quotes.get(rows[exit_i]['timestamp'])
 if x is None or x[5]<=0:return None
 sold=x[1]*(1-slip)
 # Fixed fee and turnover costs are sensitivities, not verified MCX invoices.
 net=sold-paid-(paid+sold)*.001-40/200
 peak=max(quotes[rows[j]['timestamp']][4]*(1-slip) for j in range(start,exit_i) if rows[j]['timestamp'] in quotes)
 giveback=max(0,max(0,peak-paid)-max(0,sold-paid))
 future=[quotes.get(rows[j]['timestamp']) for j in range(exit_i+1,min(n,exit_i+31)) if date(rows[j]['timestamp'])==date(t['at'])]
 future=[q for q in future if q and q[5]>0]
 continued=exit_i<end and reason in ('STRUCTURE','PREMIUM') and bool(future) and max(q[4]*(1-slip) for q in future)>=peak+paid*.05
 continued2=exit_i<end and reason in ('STRUCTURE','PREMIUM') and bool(future) and max(q[4]*(1-slip) for q in future)>=peak+paid*.02
 return dict(at=t['at'],day=date(t['at']),symbol=t['contract']['symbol'],paid=paid,sold=sold,net_points=net,net_pct=100*net/paid,giveback_pct=100*giveback/paid,profit_giveback_pct=100*giveback/(peak-paid) if peak>paid else None,reason=reason,exit_i=exit_i,baseline_end=end,activated=armed,continuation=continued,continuation2=continued2,trigger=trigger)

def metrics(trades):
 eq=peak=dd=0
 for t in sorted(trades,key=lambda t:t['at']):
  eq+=t['net_points'];peak=max(peak,eq);dd=max(dd,peak-eq)
 g=[t['profit_giveback_pct'] for t in trades if t['profit_giveback_pct'] is not None]
 return dict(mean_profit_giveback_pct=round(statistics.mean(g),3) if g else None,continuations_2pct=sum(t['continuation2'] for t in trades),trades=len(trades),net_points=round(eq,3),mean_net_pct=round(statistics.mean(t['net_pct'] for t in trades),3) if trades else None,drawdown_points=round(dd,3),mean_giveback_pct=round(statistics.mean(t['giveback_pct'] for t in trades),3) if trades else None,early_exits=sum(t['exit_i']<t['baseline_end'] for t in trades),baseline_preempted=sum(t['reason']=='BASELINE' for t in trades),activated=sum(t['activated'] for t in trades),continuations=sum(t['continuation'] for t in trades))

def main():
 rows=json.loads((OUT/'analyzed.json').read_text());entries=json.loads((OUT/'selected_entries.json').read_text());f1=features(rows,60);f5=features(rows,300);quotes={};coverage=[]
 for p in (OUT/'selected_history').glob('*.json'):
  d=json.loads(p.read_text());raw=d['response'].get('candles',[]);q={int(c[0]):c for c in raw if valid(c)};quotes[d['request']['symbol']]=q
  coverage.append(dict(symbol=d['request']['symbol'],raw=len(raw),valid=len(q),first=date(min(q)) if q else None,last=date(max(q)) if q else None,zero_volume=sum(c[5]<=0 for c in q.values())))
 for i,t in enumerate(entries):
  next_i=entries[i+1]['i'] if i+1<len(entries) else len(rows)-1
  t['replacement_end_i']=next_i
  for j in range(t['end_i'],next_i):
   dt=datetime.fromtimestamp(rows[j]['timestamp'],IST)
   if date(rows[j]['timestamp'])!=date(t['at']) or dt.hour*60+dt.minute>=1409:t['replacement_end_i']=j;break
 vs=variants();results=[];details=[];eligible=[];preserve_eligible=[]
 # Strict common support: every arm must have nonzero-volume candle observations
 # through the replacement horizon. No stale-price filling or selective arm samples.
 for t in entries:
  if t['end_i']<=t['i']:continue
  q=quotes.get(t['contract']['symbol'],{})
  if all(rows[j]['timestamp'] in q and q[rows[j]['timestamp']][5]>0 and (j==t['i'] or rows[j]['timestamp']==rows[j-1]['timestamp']+60) for j in range(t['i'],t['end_i']+1)):preserve_eligible.append(t)
  if all(rows[j]['timestamp'] in q and q[rows[j]['timestamp']][5]>0 and (j==t['i'] or rows[j]['timestamp']==rows[j-1]['timestamp']+60) for j in range(t['i'],t['replacement_end_i']+1)):eligible.append(t)
 days=sorted({date(t['at']) for t in preserve_eligible});cut=max(1,int(len(days)*.6));dev=set(days[:cut]);test=set(days[cut:]);print('eligible',len(eligible),'days',len(days),'cut',days[cut] if cut<len(days) else None,flush=True)
 for ema in (True,False):
  arm_entries=preserve_eligible if ema else eligible
  for slip in (0,.005,.01,.02):
   for v in vs:
    trades=[replay(t,rows,f1,f5,quotes[t['contract']['symbol']],v,slip,ema) for t in arm_entries]
    for label,selected in [('development',dev),('heldout',test)]+[(month,{d for d in days if d.startswith(month)}) for month in sorted({d[:7] for d in days})]:
     ts=[t for t in trades if t and t['day'] in selected]
     results.append(dict(arm='preserve_exits' if ema else 'replace_EMA_research_only',slippage=slip,variant=v['name'],family=v['family'],activation=v['activation'],k=v['k'],buffer=v['buffer'],retain=v['retain'],split=label,**metrics(ts)))
    if ema and slip==.01 and (v['name'] in ('baseline','current_0.1','structure_1_3_0.5','structure_5_3_0.5','hybrid_0.25_3_0.5_0.6','hybrid_0.05_3_0.5_0.6')):
     details.extend(dict(variant=v['name'],split='development' if t['day'] in dev else 'heldout',**t) for t in trades if t)
 path_results=[]
 for model in ('high_low','low_high'):
  for slip in (0,.005,.01,.02):
   for v in vs:
    if v['name'] not in ('baseline','current_0.1','structure_1_3_0.5','structure_5_3_0.5','hybrid_0.25_3_0.5_0.6','hybrid_0.05_3_0.5_0.6'):continue
    ts=[replay(t,rows,f1,f5,quotes[t['contract']['symbol']],v,slip,True,model) for t in preserve_eligible]
    for label,selected in [('development',dev),('heldout',test)]:
     path_results.append(dict(path_model=model,slippage=slip,variant=v['name'],split=label,**metrics([t for t in ts if t and t['day'] in selected])))
 write_csv('path_sensitivity_final.csv',path_results)
 write_csv('results_final.csv',results);write_csv('trade_details_final.csv',details);write_csv('option_coverage_final.csv',coverage)
 (OUT/'sample_final.json').write_text(json.dumps(dict(entries=len(entries),eligible=len(preserve_eligible),replacement_eligible=len(eligible),excluded=len(entries)-len(preserve_eligible),days=days,development_days=sorted(dev),heldout_days=sorted(test),variants=len(vs),runs=len(vs)*8,eligibility='Preserve arms: exact entry and contiguous nonzero-volume option observations through baseline exit. Replacement arms: longer common next-entry/session horizon. Compare only within the same arm.',missing_metadata='Historical listing timestamps, verified historical lot multiplier and executable bid/ask unavailable.'),indent=2))
 print('runs',len(vs)*8,'result rows',len(results),flush=True)
if __name__=='__main__':main()
