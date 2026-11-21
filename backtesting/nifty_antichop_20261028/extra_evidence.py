from pathlib import Path
import pandas as pd,numpy as np,json,vectorbt as vbt
P=Path('/home/trading/sector-heatmap/backtesting/nifty_antichop_20261028')
s=pd.read_csv(P/'bar_evidence.csv');s.index=pd.to_datetime(s.timestamp_ist,utc=True).dt.tz_convert('Asia/Kolkata');initial=s.open.iloc[0]*2
pf=vbt.Portfolio.from_holding(s.close,price=s.open,size=1,size_type='amount',init_cash=initial,fees=0,freq='5min')
daily=pf.value().resample('1D').last().dropna().pct_change().dropna()
r=pd.read_csv(P/'strategy_comparison.csv');main=r[(r.variant=='main')&(r.roundtrip_cost_points==2)].iloc[0]
comp=pd.DataFrame([{'series':'Main example','normalized_return_percent':main.return_percent_on_2x_index_initial,'daily_sharpe':main.daily_sharpe_proxy,'daily_sortino':main.daily_sortino_proxy,'max_drawdown_points':main.max_drawdown_points,'win_rate_percent':main.win_rate_percent,'trades':main.trades,'profit_factor':main.profit_factor},{'series':'Nifty spot buy and hold','normalized_return_percent':pf.total_return()*100,'daily_sharpe':daily.mean()/daily.std()*np.sqrt(252),'daily_sortino':daily.mean()/np.sqrt(np.mean(np.minimum(daily,0)**2))*np.sqrt(252),'max_drawdown_points':(pf.value().cummax()-pf.value()).max(),'win_rate_percent':pf.trades.win_rate()*100,'trades':pf.trades.count(),'profit_factor':pf.trades.profit_factor()}]);comp.to_csv(P/'benchmark_comparison.csv',index=False)
# Prefix invariance checks for indicator warmup and causality.
from openalgo import ta
a=pd.read_csv('/home/trading/sector-heatmap/data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_5m.csv');a.index=pd.to_datetime(a.timestamp_ist,utc=True).dt.tz_convert('Asia/Kolkata');m=a.index.hour*60+a.index.minute;a=a[(m>=555)&(m<930)];counts=a.groupby(a.index.date).size();a=a[[counts[x]==75 for x in a.index.date]]
checks=[]
for t in s.index[::max(1,len(s)//8)]:
 prefix=a.loc[:t]
 for key,calc in [('ema20',ta.ema(prefix.close,20)),('ema50',ta.ema(prefix.close,50)),('atr',ta.atr(prefix.high,prefix.low,prefix.close,14))]:
  err=abs(float(np.asarray(calc)[-1])-s.loc[t,key]);assert err<1e-7;checks.append({'at':str(t),'indicator':key,'absolute_error':err})
(P/'prefix_invariance.json').write_text(json.dumps(checks,indent=2))
print(comp.to_string(index=False));print('Prefix checks passed:',len(checks))
