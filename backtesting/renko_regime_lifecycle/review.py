"""Isolated two-year completed-candle underlying lifecycle research, never a live runner."""
import csv,json,math,os,time,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from strategies.renko_supertrend.signals import Engine
from strategies.renko_supertrend import exit_indicators,ema_proximity
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent;IST=ZoneInfo('Asia/Kolkata')
ARCHIVE=ROOT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24'
SETTINGS=ROOT/'.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/source/.private/renko-instances/9abcfe9c2d417c1e7efe/renko-supertrend-settings.json'
RULES=['Baseline','Efficiency025','Efficiency040','Chop55','Efficiency_ATR','Breakout12','Overlap060']
BRICKS=[20.,27.71,35.]
def day(r):return datetime.fromtimestamp(r['timestamp'],IST).date().isoformat()
def stats(trades,drag=2):
 v=[t['gross_points']-drag for t in trades];gain=sum(x for x in v if x>0);loss=-sum(x for x in v if x<0)
 total=peak=dd=0;wins=losses=best=worst=0
 for x in v:
  total+=x;peak=max(peak,total);dd=max(dd,peak-total)
  wins=wins+1 if x>0 else 0;losses=losses+1 if x<0 else 0;best=max(best,wins);worst=max(worst,losses)
 return dict(trades=len(v),profit_factor=gain/loss if loss else None,positive_pct=100*sum(x>0 for x in v)/len(v) if v else None,
 net_points=total,mean_points=total/len(v) if v else None,realized_drawdown_points=dd,max_win_streak=best,max_loss_streak=worst)
def filter_entry(history,name,direction):
 if name=='Baseline':return True
 n=14
 if len(history)<n+1:return False
 w=history[-n-1:]
 if len({day(r) for r in w})!=1:return False
 sign=1 if direction=='BULLISH' else -1
 close=[r['close'] for r in w[-13:]];travel=sum(abs(b-a) for a,b in zip(close,close[1:]))
 er=sign*(close[-1]-close[0])/travel if travel else 0
 tr=[max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close'])) for a,b in zip(w,w[1:])]
 width=max(r['high'] for r in w[1:])-min(r['low'] for r in w[1:])
 chop=100*math.log10(max(1,sum(tr)/width))/math.log10(14) if width else 100
 r=w[-1];prev=w[-13:-1]
 breakout=r['close']>max(x['high'] for x in prev) if sign>0 else r['close']<min(x['low'] for x in prev)
 ratios=[max(0,min(a['high'],b['high'])-max(a['low'],b['low']))/max(a['high']-a['low'],b['high']-b['low'],.05) for a,b in zip(w[-7:],w[-6:])]
 atrs=[x.get('host_atr') for x in history[-61:-1]]
 atr_ok=len(atrs)==60 and all(x is not None for x in atrs) and r['host_atr']>=.8*sorted(atrs)[30]
 return {'Efficiency025':er>=.25,'Efficiency040':er>=.4,'Chop55':chop<=55,
 'Efficiency_ATR':er>=.25 and atr_ok,'Breakout12':breakout,'Overlap060':sum(ratios)/len(ratios)<=.6}[name]
def simulate(raw,config,rule,cap=2,drag=2,recovery=False):
 engine=Engine(config,.05);history=[];trades=[];position=None;pending=None;used={};skipped=0;gaps=0;previous=None;lock=None
 def close(price,at,reason):
  nonlocal position,lock
  sign=1 if position['direction']=='BULLISH' else -1
  trades.append(dict(position,exit_at=at,exit_price=price,reason=reason,gross_points=sign*(price-position['entry_price'])))
  if recovery and sign*(price-position['entry_price'])-drag<0 and int(at//300-position['entry_at']//300)+1<=2:
   lock=dict(high=position['high'],low=position['low'],at=at)
  position=None;engine.state['ema_qualified']=None
 for i,bar in enumerate(raw):
  if i%2000==0:
   if (OUT/'CANCEL').exists():raise InterruptedError('Research cancellation requested.')
  at=bar['timestamp'];d=day(bar);clock=datetime.fromtimestamp(at,IST);minute=clock.hour*60+clock.minute
  if previous and at-previous['timestamp']!=300 and day(previous)==d:gaps+=1
  if pending:
   p=pending;pending=None
   if p['action']=='EXIT' and position:close(bar['open'],at,p['reason'] if at==p['at'] else 'DATA_GAP_EXIT')
   elif p['action']=='ENTRY' and at==p['at'] and minute<910 and used.get(d,0)<cap:
    try:ema_proximity.check(config,bar['open'],p['signal']['ema10'],p['signal']['host_atr'],p['signal'],p['signal']['entry_direction'])
    except ValueError:skipped+=1
    else:
     position=dict(entry_at=at,entry_price=bar['open'],direction=p['signal']['entry_direction'],entry_day=d,high=bar['open'],low=bar['open'])
     used[d]=used.get(d,0)+1
   elif p['action']=='ENTRY':skipped+=1
  if position and (minute>=910 or position['entry_day']!=d):close(bar['open'],at,'SESSION_CUTOFF_OR_GAP')
  if position:
   position['high']=max(position['high'],bar['high']);position['low']=min(position['low'],bar['low'])
  sig=engine.update(bar);history.append(sig)
  if lock and at+300>lock['at'] and (bar['close']>lock['high'] or bar['close']<lock['low']):lock=None
  if len(history)>100:history.pop(0)
  if position:
   check=dict(sig,supertrend_cross_direction=sig.get('raw_supertrend_cross_direction'))
   reason=exit_indicators.reason(config,check,position['direction'])
   length=int(config.get('ema_exit_length',30))
   # Current selected length is EMA30, already computed by the shared engine.
   if config.get('ema_exit_enabled') and length==30 and (bar['close']<sig['ema30'] if position['direction']=='BULLISH' else bar['close']>sig['ema30']):reason=reason or 'EMA30_BREACH'
   if reason:pending=dict(action='EXIT',at=at+300,reason=reason)
  elif sig.get('entry_direction') and minute<905 and used.get(d,0)<cap:
   if not lock and filter_entry(history,rule,sig['entry_direction']):pending=dict(action='ENTRY',at=at+300,signal=sig)
   else:skipped+=1
  previous=bar
 if position:close(raw[-1]['close'],raw[-1]['timestamp']+300,'END_OF_DATA')
 return dict(trades=trades,summary=stats(trades,drag),skipped=skipped,gaps=gaps)
def main():
 OUT.mkdir(exist_ok=True)
 (OUT/'job.json').write_text(json.dumps(dict(status='RUNNING',pid=os.getpid(),started=time.time(),phase='LOAD')))
 saved=json.loads(SETTINGS.read_text())['settings'];config={k.replace('-','_'):v for k,v in saved.items()}
 for k in ('atr_length','adx_length','adx_smoothing','widening_window','ema_fast_length','ema_slow_length','ema_third_length','ema_exit_length'):
  config[k]=int(config[k])
 for k in ('factor','manual_brick','ema_proximity_distance','adx_threshold'):config[k]=float(config[k])
 config.update(underlying=saved['symbol'],session_deadline='15:10')
 raw=[]
 with (ARCHIVE/'nifty50_5m.csv').open() as f:
  for x in csv.DictReader(f):
   t=datetime.fromtimestamp(int(x['epoch']),IST)
   if t.weekday()>4 or not 555<=t.hour*60+t.minute<930:continue
   raw.append(dict(timestamp=int(x['epoch']),**{k:float(x[k]) for k in ('open','high','low','close','volume')}))
 specification=dict(rules=RULES,brick_sizes=BRICKS,base_config=config,trade_cap='2 entries per trading day, explicit research assumption; runtime quota semantics not reproduced',cost_drag_points=[0,2,4],scope='Sequential underlying-index lifecycle proxy; no historical option premiums/fills')
 (OUT/'specification.json').write_text(json.dumps(specification,indent=2))
 results={}
 for brick in BRICKS:
  for rule in RULES:
   name=f'{brick}_{rule}';start=time.time()
   (OUT/'job.json').write_text(json.dumps(dict(status='RUNNING',pid=os.getpid(),phase=name,completed=len(results),total=len(BRICKS)*len(RULES),heartbeat=time.time())))
   result=simulate(raw,dict(config,manual_brick=brick),rule)
   splits={}
   for label,predicate in [('earlier',lambda t:t['entry_day']<'2025-10-25'),('latest',lambda t:t['entry_day']>='2025-10-25'),('all',lambda t:True)]:
    chosen=[t for t in result['trades'] if predicate(t)]
    splits[label]={str(d):stats(chosen,d) for d in (0,2,4)}
   result['splits']=splits;results[name]=result
   (OUT/'results.json').write_text(json.dumps(dict(specification=specification,results=results,completed=False),indent=2))
 (OUT/'results.json').write_text(json.dumps(dict(specification=specification,results=results,completed=True),indent=2))
 (OUT/'job.json').write_text(json.dumps(dict(status='COMPLETED',pid=os.getpid(),completed=len(results),heartbeat=time.time())))
 print('Completed',len(results),'scenarios.')
if __name__=='__main__':
 try:main()
 except Exception as e:
  (OUT/'job.json').write_text(json.dumps(dict(status='CANCELLED' if isinstance(e,InterruptedError) else 'FAILED',error=str(e),heartbeat=time.time())))
  raise
