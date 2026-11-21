"""Exploratory follow-up; prior quarter results have already been inspected."""
from pathlib import Path
import json
import review as study
OUT=Path(__file__).parent/'atr_rsi_followup'
RULES=[('Baseline',),('ATR_expansion',),('ADX_strength_rising',),('Directional_efficiency',),('RSI_and_ADX',),('Combined',)]
def assess(rows,rule):
 name=rule[0]
 if name=='Baseline':return dict(allowed=True,state='BASELINE')
 if len(rows)<22:return dict(allowed=False,state='WARMUP')
 r=rows[-1];w=rows[-13:]
 if len({study.day(x) for x in w})!=1:return dict(allowed=False,state='SESSION_WARMUP')
 sign=1 if r['pine_direction']<0 else -1
 close=[x['close'] for x in w]
 travel=sum(abs(b-a) for a,b in zip(close,close[1:]))
 net=sign*(close[-1]-close[0]);eff=net/travel if travel else 0
 atr=r.get('host_atr');previous=[x.get('host_atr') for x in rows[-21:-1]]
 if not atr or any(x is None for x in previous):return dict(allowed=False,state='WARMUP')
 ratio=atr/(sum(previous)/len(previous))
 rsi=r.get('rsi14');adx=r.get('adx');old_adx=rows[-4].get('adx')
 rsi_ok=rsi is not None and (rsi>=55 if sign>0 else rsi<=45)
 adx_ok=adx is not None and adx>=20
 rising=adx_ok and old_adx is not None and adx>old_adx
 efficiency=eff>=.3 and net>=atr
 allowed={'ATR_expansion':ratio>=1.05,'ADX_strength_rising':rising,
  'Directional_efficiency':efficiency,'RSI_and_ADX':rsi_ok and rising,
  'Combined':efficiency and ratio>=1.05 and rsi_ok and adx_ok}[name]
 return dict(allowed=allowed,state='TRENDING' if allowed else 'SIDEWAYS_OR_TRANSITION',
  atr_expansion=ratio,directional_efficiency=eff,net_atr=net/atr,rsi=rsi,adx=adx)
def main():
 OUT.mkdir(exist_ok=True);study.OUT=OUT;study.RULES=RULES;study.assess=assess
 study.main()
 p=OUT/'results.json';r=json.loads(p.read_text())
 r['validation_selected_rule']=None
 r['research_status']='EXPLORATORY: final-quarter results were already inspected during earlier Supertrend study; no untouched holdout remains.'
 r['rules_explanation']={
 'ATR_expansion':'Current ATR5 >= 1.05 times the preceding 20 ATR5 observations.',
 'ADX_strength_rising':'ADX14 >= 20 and above its value three completed bars earlier.',
 'Directional_efficiency':'Direction-adjusted 12-bar close change / sum absolute close changes >= 0.30; net move >= ATR5.',
 'RSI_and_ADX':'RSI14 >=55 bullish / <=45 bearish, with ADX14 >=20 and rising over three bars.',
 'Combined':'Directional efficiency and net ATR displacement, ATR expansion, RSI directional level and ADX >=20.'}
 p.write_text(json.dumps(r,indent=2))
 print('EXPLORATORY SUMMARY')
 for name,periods in r['results'].items():
  print(name,{phase:{k:round(v,2) if isinstance(v,float) else v for k,v in s.items()} for phase,s in periods.items() if phase in ('validation','holdout','all')})
if __name__=='__main__':main()
