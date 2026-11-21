import json,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from strategies.renko_supertrend.signals import series
root=Path(__file__).resolve().parents[2]
folder=root/'.private/dashboard-login/accounts/b0041912d9d6f68d352814cbd24bf6da'
state=json.loads((folder/'dhan-strategies/renko/da57c2570f5e34888b97c3c4/state.json').read_text())
config=state['config']
key=hashlib.sha256(json.dumps((config['underlying'],60,None)).encode()).hexdigest()
tz=ZoneInfo('Asia/Kolkata')
rows=json.loads((folder/'dhan-strategy-history'/f'{key}.json').read_text())['rows']
rows=[r for r in rows if datetime.fromtimestamp(r['timestamp'],tz).date().isoformat()<'2026-10-13']
signals=series(rows,config)
pairs=[];position=None;last_exit_day=None
for i,s in enumerate(signals[:-1]):
 current=datetime.fromtimestamp(s['timestamp'],tz)
 nextrow=signals[i+1]
 same_day=datetime.fromtimestamp(nextrow['timestamp'],tz).date()==current.date()
 if position:
  direction=position['direction'];sign=1 if direction=='BULLISH' else -1
  ema_breach=s['close']<s['ema10'] if sign==1 else s['close']>s['ema10']
  cutoff=current.strftime('%H:%M')>='15:09'
  prior=signals[i-1]['ema_gap'] if i else None
  contraction=prior is not None and abs(s['ema_gap'])<abs(prior)
  if position['early'] is None and contraction:
   position['early']=sign*((nextrow['open'] if same_day else s['close'])-position['price'])
  if ema_breach or cutoff or not same_day:
   gross=sign*((nextrow['open'] if same_day and not cutoff else s['close'])-position['price'])
   pairs.append(dict(day=position['day'],baseline=gross,contraction=position['early'] if position['early'] is not None else gross,earlier=position['early'] is not None))
   position=None
  continue
 if s.get('entry_direction') and s.get('entry_qualified') and same_day and '09:15'<=current.strftime('%H:%M')<'15:09':
  position=dict(direction=s['entry_direction'],price=nextrow['open'],day=current.date().isoformat(),early=None)
days=sorted({p['day'] for p in pairs})
def stats(data):
 return dict(paired_trades=len(data),baseline_points=round(sum(p['baseline'] for p in data),2),contraction_points=round(sum(p['contraction'] for p in data),2),improved=sum(p['contraction']>p['baseline'] for p in data),worsened=sum(p['contraction']<p['baseline'] for p in data),unchanged=sum(p['contraction']==p['baseline'] for p in data),earlier_exits=sum(p['earlier'] for p in data))
result=dict(scope='Retrospective underlying-price paired exit screening; NOT executable options backtest. Fixed baseline entry schedule, completed-close signals and next-open exits; current manual brick backcast, no parameter search. Intrabar EMA exits, option premium, spread, fees, quick-loss reentry interaction and path-dependent extra entries are not reproduced.',settings={k:config[k] for k in ('underlying','timeframe','manual_brick','ema_fast_length','ema_slow_length','rsi_bullish_min','rsi_bullish_max','rsi_bearish_min','rsi_bearish_max')},from_day=days[0] if days else None,to_day=days[-1] if days else None,all=stats(pairs),last_seven_days=stats([p for p in pairs if p['day'] in days[-7:]]),trades=pairs)
(root/'backtesting/ema_gap_contraction_review/result.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='trades'},indent=2))
