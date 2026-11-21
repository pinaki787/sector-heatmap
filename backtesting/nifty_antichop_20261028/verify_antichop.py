from pathlib import Path
import json,numpy as np,pandas as pd
from openalgo import ta
P=Path('/home/trading/sector-heatmap/backtesting/nifty_antichop_20261028')
s=pd.read_csv(P/'bar_evidence.csv');s.index=pd.to_datetime(s.timestamp_ist,utc=True).dt.tz_convert('Asia/Kolkata')
checked=0;maxerr=0;breakdown=[]
for name in ['baseline','loose','main','strict']:
 t=pd.read_csv(P/(name+'_trades.csv'))
 for _,r in t.iterrows():
  ent=pd.Timestamp(r['Entry Timestamp']);ex=pd.Timestamp(r['Exit Timestamp']);j=s.index.get_loc(ent);k=s.index.get_loc(ex)
  assert j>0 and k>j and ent.date()==ex.date()
  assert abs(r['Avg Entry Price']-s.open.iloc[j])<1e-7 and abs(r['Avg Exit Price']-s.open.iloc[k])<1e-7
  direction=1 if r.Direction=='Long' else -1
  assert s.direction.iloc[j-1]==direction
  if name!='baseline':assert s[name+'_all'].iloc[j-1]
  calc=(s.open.iloc[k]-s.open.iloc[j])*direction-2
  err=abs(calc-r.PnL);assert err<1e-7;maxerr=max(maxerr,err);checked+=1
 t['date']=pd.to_datetime(t['Exit Timestamp'],utc=True).dt.tz_convert('Asia/Kolkata')
 for direction,g in t.groupby('Direction'):breakdown.append({'variant':name,'group':direction,'trades':len(g),'net_points':float(g.PnL.sum())})
 for label,keep in [('first_half',t.date<pd.Timestamp('2026-04-24',tz='Asia/Kolkata')),('second_half',t.date>=pd.Timestamp('2026-04-24',tz='Asia/Kolkata'))]:
  g=t[keep];breakdown.append({'variant':name,'group':label,'trades':len(g),'net_points':float(g.PnL.sum())})
# Compare accepted bars with a baseline matched by calendar month, half-hour slot,
# and EMA trend direction, to reduce time-of-day/direction composition bias.
matched=[]
for h in [3,6,12]:
 same=pd.Series(s.index.date,index=s.index).eq(pd.Series(s.index.date,index=s.index).shift(-h))
 ret=(s.close.shift(-h)-s.open.shift(-1))*s.direction
 f=pd.DataFrame({'ret':ret,'pass':s.main_all,'month':s.index.strftime('%Y-%m'),'slot':(s.index.hour*60+s.index.minute)//30,'direction':s.direction},index=s.index)[same].dropna()
 means=f.groupby(['month','slot','direction']).ret.mean()
 chosen=f[f['pass']].copy();chosen['matched_control']=[means.loc[(r.month,r.slot,r.direction)] for _,r in chosen.iterrows()]
 matched.append({'horizon_minutes':h*5,'samples':len(chosen),'filtered_mean_points':float(chosen.ret.mean()),'matched_baseline_mean_points':float(chosen.matched_control.mean()),'difference_points':float((chosen.ret-chosen.matched_control).mean())})
pd.DataFrame(breakdown).to_csv(P/'breakdown.csv',index=False);pd.DataFrame(matched).to_csv(P/'matched_forward.csv',index=False)
(P/'verification.json').write_text(json.dumps({'closed_trades_reconciled':checked,'max_pnl_reconciliation_error_points':maxerr,'checks':['Entries follow completed signal candle at next open','Entry direction and filter eligibility match prior candle','Every exit and entry price equals archived broker open','Every trade closes same day','Per-trade profit reconciles exactly after hypothetical two-point roundtrip deduction'],'matched_forward':matched},indent=2))
print(json.dumps({'trades_checked':checked,'matched_forward':matched,'breakdown':breakdown},indent=2))
