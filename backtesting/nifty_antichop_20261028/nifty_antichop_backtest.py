"""Read-only NIFTY spot-index filter study and explicitly hypothetical strategy.
Run with the isolated research environment; no broker API, orders or runners.
"""
from pathlib import Path
import json,hashlib,sys,platform
import numpy as np
import pandas as pd
from dotenv import load_dotenv,find_dotenv
from openalgo import ta
import vectorbt as vbt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import openstatz as ostz
load_dotenv(find_dotenv(),override=False)
ROOT=Path('/home/trading/sector-heatmap')
ARCHIVE=ROOT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24'
OUT=Path(__file__).resolve().parent
START='2025-10-24'; END='2026-10-23'

def read_frame(name):
 d=pd.read_csv(ARCHIVE/name);d.index=pd.to_datetime(d.timestamp_ist,utc=True).dt.tz_convert('Asia/Kolkata');return d.sort_index()
raw=read_frame('nifty50_5m.csv');one=read_frame('nifty50_1m.csv')
def regular(d):
 m=d.index.hour*60+d.index.minute
 return d[(m>=555)&(m<930)].copy()
d=regular(raw);one=regular(one)
assert not d.index.has_duplicates and not one.index.has_duplicates
valid=(d[['open','high','low','close']]>0).all(axis=1)&(d.high>=d[['open','close','low']].max(axis=1))&(d.low<=d[['open','close','high']].min(axis=1))
assert valid.all()
# Exclude incomplete sessions rather than filling bars.
counts=d.groupby(d.index.date).size();full_days={k for k,n in counts.items() if n==75}
minute_counts=one.groupby(one.index.date).size();full_days&={k for k,n in minute_counts.items() if n==375}
d=d[[date in full_days for date in d.index.date]].copy()
agg=one.resample('5min',origin='start_day',offset='9h15min').agg({'open':'first','high':'max','low':'min','close':'last','epoch':'count'});agg=agg[agg.epoch==5]
common=d.index.intersection(agg.index)
diff=(d.loc[common,['open','high','low','close']]-agg.loc[common,['open','high','low','close']]).abs()
mismatch=diff.max(axis=1)>.10
bad_dates=set(common[mismatch].date)
# Provider timeframes must agree to within 0.10 index point for this study.
d=d[[date not in bad_dates for date in d.index.date]].copy()
assert len(d)>1000
for period in [20,50]:d['ema'+str(period)]=np.asarray(ta.ema(d.close,period))
d['atr']=np.asarray(ta.atr(d.high,d.low,d.close,14));d['atr_avg']=np.asarray(ta.sma(d.atr,20))
d['slope']=(d.ema20-d.ema20.shift(3))/d.atr
d['gap']=(d.ema20-d.ema50).abs()/d.atr
d['direction']=np.where(d.ema20>d.ema50,1,-1)
cross=pd.Series(d.direction,index=d.index).ne(pd.Series(d.direction,index=d.index).shift()).astype(int)
d['no_cross']=cross.rolling(6).sum()==0
d['atr_gate']=d.atr>d.atr_avg
day=pd.Series(d.index.date,index=d.index)
ph=d.high.groupby(day).shift();pl=d.low.groupby(day).shift()
intersection=(np.minimum(d.high,ph)-np.maximum(d.low,pl)).clip(lower=0)
width=np.minimum(d.high-d.low,ph-pl).replace(0,np.nan)
d['overlap']=intersection/width
hh=(d.high>ph)&(d.low>pl);ll=(d.high<ph)&(d.low<pl)
variants={'loose':(.10,.10,.65,1),'main':(.15,.20,.50,2),'strict':(.25,.30,.35,2),'zero_overlap':(.15,.20,0.0,2)}
for name,(slope,gap,overlap,pairs) in variants.items():
 structup=hh.groupby(day).transform(lambda x:x.rolling(pairs).sum()==pairs)
 structdn=ll.groupby(day).transform(lambda x:x.rolling(pairs).sum()==pairs)
 ov=d.overlap.groupby(day).transform(lambda x:x.rolling(pairs).mean())<=overlap
 d[name+'_slope_gate']=((d.slope>=slope)&(d.direction==1))|((d.slope<=-slope)&(d.direction==-1))
 d[name+'_gap_gate']=(d.gap>=gap)&d.no_cross
 d[name+'_structure_gate']=ov&(((d.direction==1)&structup)|((d.direction==-1)&structdn))
 d[name+'_all']=d.atr_gate&d[name+'_slope_gate']&d[name+'_gap_gate']&d[name+'_structure_gate']
mask=(d.index.date>=pd.Timestamp(START).date())&(d.index.date<=pd.Timestamp(END).date())
s=d[mask].copy();assert len(s)>10000
s.to_csv(OUT/'bar_evidence.csv',index_label='timestamp_ist')
audit={'requested_start':START,'requested_end':END,'actual_first':str(s.index[0]),'actual_last':str(s.index[-1]),'bars':len(s),'sessions':len(set(s.index.date)),'excluded_incomplete_dates':[str(k) for k,n in counts.items() if START<=str(k)<=END and k not in full_days],'cross_timeframe_compared_bars':len(common),'cross_timeframe_max_ohlc_difference':float(diff.max().max()),'cross_timeframe_mismatch_bars':int(mismatch.sum()),'excluded_mismatch_dates':[str(x) for x in sorted(bad_dates) if START<=str(x)<=END],'source_sha256':{f:hashlib.sha256((ARCHIVE/f).read_bytes()).hexdigest() for f in ['nifty50_5m.csv','nifty50_1m.csv']},'calendar_limitation':'Regular-session integrity checked; authoritative exchange holiday calendar not independently reconciled. Off-hours and incomplete special sessions excluded.'}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2))
# Forward study: next-bar open to close after 15/30/60 minutes, never overnight.
forward=[]
for horizon in [3,6,12]:
 entry=s.open.shift(-1);finish=s.close.shift(-horizon);same=pd.Series(s.index.date,index=s.index).eq(pd.Series(s.index.date,index=s.index).shift(-horizon))
 pnl=(finish-entry)*s.direction
 for name in ['baseline',*variants]:
  sel=same&s.atr.notna()&(s[name+'_all'] if name!='baseline' else True)
  v=pnl[sel].dropna();norm=(pnl/s.atr)[sel].dropna()
  forward.append(dict(variant=name,horizon_minutes=horizon*5,samples=len(v),mean_directional_points=v.mean(),median_directional_points=v.median(),positive_percent=(v>0).mean()*100,mean_directional_atr=norm.mean()))
pd.DataFrame(forward).to_csv(OUT/'forward_study.csv',index=False)
coverage=[]
for name in variants:
 coverage.append({'variant':name,'pass_bars':int(s[name+'_all'].sum()),'pass_percent':s[name+'_all'].mean()*100,'long_bars':int((s[name+'_all']&(s.direction==1)).sum()),'short_bars':int((s[name+'_all']&(s.direction==-1)).sum())})
stages=[]
keep=pd.Series(True,index=s.index)
for label,col in [('ATR14 > SMA20(ATR14)','atr_gate'),('EMA20 slope direction','main_slope_gate'),('EMA separation and no recent cross','main_gap_gate'),('Structure and overlap','main_structure_gate')]:
 keep&=s[col];stages.append({'stage':label,'standalone_pass_percent':s[col].mean()*100,'cumulative_pass_bars':int(keep.sum()),'cumulative_pass_percent':keep.mean()*100})
# Example strategy: pass episode, next open execution, leave when a gate fails.
# One spot-index point unit, long/short. Index is not directly tradeable.
# Costs are hypothetical index-point deductions, NOT exchange fees or option P&L.
minutes=s.index.hour*60+s.index.minute
entrytime=(minutes>=565)&(minutes<=910)
exitnow=minutes>=920
results=[];portfolios={};tradeframes=[]
initial=float(s.open.iloc[0])*2
benchmark=vbt.Portfolio.from_holding(s.close,price=s.open,size=1,size_type='amount',init_cash=initial,fees=0,freq='5min')
for name in ['baseline',*variants]:
 eligible=pd.Series(True,index=s.index) if name=='baseline' else s[name+'_all']
 longraw=eligible&(s.direction==1)&entrytime
 shortraw=eligible&(s.direction==-1)&entrytime
 lexit=(~eligible)|(s.direction!=1)|exitnow
 sexit=(~eligible)|(s.direction!=-1)|exitnow
 longclean=pd.Series(np.asarray(ta.exrem(longraw.fillna(False),lexit.fillna(False))),index=s.index).fillna(False).astype(bool)
 shortclean=pd.Series(np.asarray(ta.exrem(shortraw.fillna(False),sexit.fillna(False))),index=s.index).fillna(False).astype(bool)
 same_prev=pd.Series(s.index.date,index=s.index).eq(pd.Series(s.index.date,index=s.index).shift())
 entries=longclean.shift(fill_value=False)&same_prev;short_entries=shortclean.shift(fill_value=False)&same_prev
 exits=lexit.shift(fill_value=False)&same_prev;short_exits=sexit.shift(fill_value=False)&same_prev
 for rt_cost in [0,2,5]:
  pf=vbt.Portfolio.from_signals(s.close,entries=entries,exits=exits,short_entries=short_entries,short_exits=short_exits,price=s.open,size=1,size_type='amount',min_size=1,size_granularity=1,init_cash=initial,fees=0,fixed_fees=rt_cost/2,upon_opposite_entry='close',accumulate=False,freq='5min')
  t=pf.trades.records_readable.copy();assert not (t.Status=='Open').any()
  assert all(pd.to_datetime(t['Entry Timestamp']).dt.date==pd.to_datetime(t['Exit Timestamp']).dt.date)
  daily=pf.value().resample('1D').last().dropna().pct_change().dropna()
  r={'variant':name,'roundtrip_cost_points':rt_cost,'trades':int(pf.trades.count()),'net_points':float(pf.total_profit()),'win_rate_percent':float(pf.trades.win_rate()*100),'profit_factor':float(pf.trades.profit_factor()),'max_drawdown_points':float((pf.value().cummax()-pf.value()).max()),'mean_trade_points':float(pf.trades.pnl.mean()),'return_percent_on_2x_index_initial':float(pf.total_return()*100),'daily_sharpe_proxy':float(daily.mean()/daily.std()*np.sqrt(252)),'daily_sortino_proxy':float(daily.mean()/np.sqrt(np.mean(np.minimum(daily,0)**2))*np.sqrt(252))}
  results.append(r)
  if rt_cost==2:
   portfolios[name]=pf;t['variant']=name;tradeframes.append(t);t.to_csv(OUT/(name+'_trades.csv'),index=False)
# Chronological half-year and monthly checks with parameters fixed throughout.
monthly=[]
for name,pf in portfolios.items():
 t=pd.read_csv(OUT/(name+'_trades.csv'));t['month']=pd.to_datetime(t['Exit Timestamp'],utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%Y-%m')
 for month,g in t.groupby('month'):monthly.append({'variant':name,'month':month,'trades':len(g),'net_points':g.PnL.sum(),'win_rate_percent':(g.PnL>0).mean()*100})
pd.DataFrame(monthly).to_csv(OUT/'monthly.csv',index=False)
pd.DataFrame(results).to_csv(OUT/'strategy_comparison.csv',index=False)
pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False);pd.DataFrame(stages).to_csv(OUT/'gate_funnel.csv',index=False)
summary={'audit':audit,'coverage':coverage,'gate_funnel':stages,'forward_study':forward,'strategy':results,'benchmark':{'name':'Nifty spot buy and hold, one index point unit, overnight exposure','net_points':float(benchmark.total_profit()),'return_percent_on_same_initial':float(benchmark.total_return()*100),'max_drawdown_points':float((benchmark.value().cummax()-benchmark.value()).max())},'parameters':variants,'notes':['Preselected illustrative thresholds, no optimization. Entire year descriptive; half-year/monthly stability does not establish untouched out-of-sample validation.','Forward samples overlap, so sample counts are not independent; no significance claim.','All bar decisions use completed data and execute at next open. No same-close fills.','ATR and EMAs use continuous regular-session history with warmup; structure comparisons remain within day.','Main: three-candle HH+HL or LL+LH and two-pair mean overlap divided by smaller candle range <=50%.','Point-unit spot proxy only. No futures basis, expiry rolls, lot sizes, margin, actual fees, bid/ask or options IV/theta.','Two-point and five-point roundtrip deductions are hypothetical sensitivity scenarios.']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,default=str))
fig=make_subplots(rows=2,cols=1,shared_xaxes=True,subplot_titles=['Cumulative net index points (2-point hypothetical roundtrip cost)','Drawdown in index points'])
for name,pf in portfolios.items():
 value=pf.value();fig.add_trace(go.Scatter(x=s.index,y=value-initial,name=name),row=1,col=1);fig.add_trace(go.Scatter(x=s.index,y=value-value.cummax(),name=name,showlegend=False),row=2,col=1)
fig.update_layout(template='plotly_dark',height=760,title='Nifty 5-minute anti-chop: illustrative spot-index proxy')
fig.write_html(OUT/'equity.html',include_plotlyjs=True)
returns=portfolios['main'].value().resample('1D').last().dropna().pct_change().dropna();returns.index=returns.index.tz_localize(None);returns.name='Nifty anti-chop example (spot proxy)'
bench=benchmark.value().resample('1D').last().dropna().pct_change().dropna();bench.index=bench.index.tz_localize(None);bench.name='Nifty spot buy and hold (same initial notional)'
try:ostz.dashboard(returns,benchmark=bench,output=str(OUT/'tearsheet.html'),title='Illustrative index proxy; no executable futures or option P&L',open_browser=False)
except Exception as e:(OUT/'tearsheet_error.txt').write_text(str(e))
print(json.dumps({'audit':audit,'coverage':coverage,'main_2pt':[r for r in results if r['variant']=='main' and r['roundtrip_cost_points']==2],'baseline_2pt':[r for r in results if r['variant']=='baseline' and r['roundtrip_cost_points']==2],'benchmark':summary['benchmark']},indent=2))
