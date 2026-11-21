"""Frozen exploratory EMA slope / volatility comparisons; no execution imports."""
from pathlib import Path
import json
import review as study
BASE=Path(__file__).parent
RULES=[('Baseline',),('EMA10_3',),('EMA30_3',),('EMA30_6',),('Both_EMAs',),('Both_ATR_stable',),('Both_efficiency',)]
SPEC={
 'EMA10_3':'Direction-adjusted EMA10 change over 3 bars / (3*ATR5) >= .05',
 'EMA30_3':'Direction-adjusted EMA30 change over 3 bars / (3*ATR5) >= .02',
 'EMA30_6':'Direction-adjusted EMA30 change over 6 bars / (6*ATR5) >= .02',
 'Both_EMAs':'EMA10_3 and EMA30_3',
 'Both_ATR_stable':'Both_EMAs; ATR5 / mean preceding 20 ATR5 values between .8 and 1.5',
 'Both_efficiency':'Both_EMAs; direction-adjusted 12-bar close displacement / sum absolute close moves >= .3'}
def assess(rows,rule):
 name=rule[0]
 if name=='Baseline':return dict(allowed=True,state='BASELINE')
 n=12 if name=='Both_efficiency' else 6 if name=='EMA30_6' else 3
 if len(rows)<max(n+1,22 if name=='Both_ATR_stable' else 0):return dict(allowed=False,state='WARMUP')
 if len({study.day(x) for x in rows[-n-1:]})!=1:return dict(allowed=False,state='SESSION_WARMUP')
 r=rows[-1];atr=r.get('host_atr')
 if not atr:return dict(allowed=False,state='WARMUP')
 sign=1 if r['pine_direction']<0 else -1
 fast=sign*(r['ema10']-rows[-4]['ema10'])/(3*atr)
 slow=sign*(r['ema30']-rows[-4]['ema30'])/(3*atr)
 slow6=sign*(r['ema30']-rows[-7]['ema30'])/(6*atr) if len(rows)>=7 else None
 both=fast>=.05 and slow>=.02
 ratio=None;eff=None
 if name=='Both_ATR_stable':
  prev=[x.get('host_atr') for x in rows[-21:-1]]
  if any(x is None for x in prev):return dict(allowed=False,state='WARMUP')
  ratio=atr/(sum(prev)/20)
 if name=='Both_efficiency':
  close=[x['close'] for x in rows[-13:]]
  travel=sum(abs(b-a) for a,b in zip(close,close[1:]))
  eff=sign*(close[-1]-close[0])/travel if travel else 0
 allowed={'EMA10_3':fast>=.05,'EMA30_3':slow>=.02,
 'EMA30_6':slow6 is not None and slow6>=.02,'Both_EMAs':both,
 'Both_ATR_stable':both and ratio is not None and .8<=ratio<=1.5,
 'Both_efficiency':both and eff is not None and eff>=.3}[name]
 return dict(allowed=allowed,state='DIRECTIONAL_SLOPE' if allowed else 'SLOPE_OR_VOLATILITY_BLOCKED',
  ema10_atr_per_bar=fast,ema30_atr_per_bar=slow,atr_ratio=ratio,efficiency=eff)
def run(prior=False):
 out=BASE/('ema_slope_prior_year' if prior else 'ema_slope_latest_year');out.mkdir(exist_ok=True)
 (out/'specification.json').write_text(json.dumps(SPEC,indent=2))
 if prior:
  source=(BASE/'review.py').read_text()
  for a,b in [('2025-09-01','2024-10-25'),('2025-10-25','2024-10-25'),('2026-10-23','2025-10-24'),('2026-04-25','2025-04-25'),('2026-07-25','2025-07-25')]:source=source.replace(a,b)
  scope=dict(__name__='earlier_ema_study',__file__=str(BASE/'review.py'))
  exec(compile(source,str(BASE/'review.py'),'exec'),scope)
 else:scope=study.__dict__
 scope.update(OUT=out,RULES=RULES,assess=assess)
 scope['main']()
 p=out/'results.json';r=json.loads(p.read_text());r['validation_selected_rule']=None
 r['research_status']='EXPLORATORY, already-inspected historical data; not independent confirmation or option P&L.'
 p.write_text(json.dumps(r,indent=2))
 return r
if __name__=='__main__':
 latest=run();prior=run(True)
 print('EMA SUMMARY')
 for name in latest['results']:
  print(name,{label:{k:round(v,2) if isinstance(v,float) else v for k,v in result['results'][name]['all'].items() if k in ('samples','profit_factor','mean_points','positive_pct')} for label,result in [('earlier',prior),('latest',latest)]})
