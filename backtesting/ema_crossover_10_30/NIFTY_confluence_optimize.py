"""Predefined confluence comparison. Cached FYERS spot data; no order route.
Selection: first 60% train, next 20% validation, last 20% held out from
filter selection. Baseline holdout results were already observed previously.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import vectorbt as vbt
from openalgo import ta
from tqdm import tqdm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

HERE=Path(__file__).resolve().parent
OUT=HERE/'confluence'
OUT.mkdir(exist_ok=True)
d=pd.read_csv(HERE/'candles.csv',index_col=0)
d.index=pd.to_datetime(d.index,utc=True).tz_convert('Asia/Kolkata')
d=d.between_time('09:15','15:25')
d=d[(d.index.dayofweek<5)&(d.index.date<=pd.Timestamp('2026-09-28').date())]
f,s=ta.ema(d.close,10),ta.ema(d.close,30)
up=((f>s)&(f.shift()<=s.shift())).fillna(False)
dn=((f<s)&(f.shift()>=s.shift())).fillna(False)
up,dn=pd.Series(ta.exrem(up,dn),index=d.index),pd.Series(ta.exrem(dn,up),index=d.index)
rsi=pd.Series(ta.rsi(d.close,14),index=d.index)
di_p,di_m,adx=ta.adx(d.high,d.low,d.close,14)
adx=pd.Series(adx,index=d.index)
ema={n:ta.ema(d.close,n) for n in [100,200]}
alltrue=pd.Series(True,index=d.index)
filters={'Baseline':(alltrue,alltrue)}
for n in [50,55,60]:
    filters[f'RSI {n}/{100-n}']=(rsi>=n,rsi<=100-n)
for n in [18,22,25]:
    filters[f'ADX >= {n}']=(adx>=n,adx>=n)
for n in [100,200]:
    filters[f'EMA {n}']=(d.close>ema[n],d.close<ema[n])
for n in [18,22,25]:
    filters[f'RSI 55/45 + ADX {n}']=((rsi>=55)&(adx>=n),(rsi<=45)&(adx>=n))
for n in [100,200]:
    filters[f'EMA {n} + RSI 55/45']=((d.close>ema[n])&(rsi>=55),(d.close<ema[n])&(rsi<=45))
    for threshold in [18,22]:
        filters[f'EMA {n} + ADX {threshold}']=((d.close>ema[n])&(adx>=threshold),(d.close<ema[n])&(adx>=threshold))
filters['ADX rising >=18']=((adx>=18)&(adx>adx.shift()),(adx>=18)&(adx>adx.shift()))
counts=d.groupby(d.index.date).size()
good=counts[counts==75].index
eligible=(d.index.date>=pd.Timestamp('2025-09-29').date())&np.isin(d.index.date,good)
same=d.index.to_series().diff().eq(pd.Timedelta(minutes=5))
allowed=pd.Series(d.index.strftime('%H:%M')<'15:20',index=d.index)&same
buy=up.shift(fill_value=False)&allowed
sell=dn.shift(fill_value=False)&allowed
flat=pd.Series(d.index.strftime('%H:%M')=='15:20',index=d.index)
frame=d[eligible]
days=sorted(set(frame.index.date));vstart=days[int(len(days)*.6)];tstart=days[int(len(days)*.8)]
periods={'train':frame.index.date<vstart,'validation':(frame.index.date>=vstart)&(frame.index.date<tstart),
         'test':frame.index.date>=tstart,'full':np.ones(len(frame),dtype=bool)}
capital=float(frame.open.iloc[0])

def run(name,period,cost=5):
    index=frame.index[periods[period]]
    z=d.loc[index];longfilter,shortfilter=filters[name]
    le=(buy&longfilter.shift(fill_value=False)).loc[index]
    se=(sell&shortfilter.shift(fill_value=False)).loc[index]
    pf=vbt.Portfolio.from_signals(z.close,entries=le,exits=(sell|flat).loc[index],
        short_entries=se,short_exits=(buy|flat).loc[index],price=z.open,size=1,size_type='amount',
        min_size=1,size_granularity=1,init_cash=capital*10,fees=(cost/2)/z.open,
        upon_opposite_entry='reverse',freq='5min')
    trades=pf.trades.records_readable
    assert (trades.Status=='Closed').all()
    assert (pd.to_datetime(trades['Entry Timestamp']).dt.date.values==pd.to_datetime(trades['Exit Timestamp']).dt.date.values).all()
    pnl=trades.PnL
    expected=trades.Direction.map({'Long':1,'Short':-1})*(trades['Avg Exit Price']-trades['Avg Entry Price'])-cost
    assert np.allclose(pnl,expected)
    eq=capital+pf.value()-capital*10
    peak=np.maximum.accumulate(np.r_[capital,eq.values])[1:]
    daily=eq.groupby(eq.index.date).last()
    dr=daily.pct_change().dropna()
    metrics=dict(name=name,period=period,cost=cost,trades=len(trades),win_rate=float((pnl>0).mean()*100),
        net_points=float(pnl.sum()),profit_factor=float(pnl[pnl>0].sum()/-pnl[pnl<0].sum()) if (pnl<0).any() else None,
        max_dd=float((peak-eq.values).max()),max_dd_pct=float(((peak-eq.values)/peak).max()*100),
        return_pct=float(pnl.sum()/capital*100),sharpe=float(dr.mean()/dr.std()*np.sqrt(252)),
        expectancy=float(pnl.mean()))
    return metrics,trades,eq

dev=[]
for name in tqdm(filters,desc='Development only'):
    for period in ['train','validation']:
        dev.append(run(name,period)[0])
development=pd.DataFrame(dev)
development.to_csv(OUT/'development.csv',index=False)
rank=[]
for name in filters:
    if name=='Baseline':continue
    rows=development[development.name==name].set_index('period')
    bases=development[development.name=='Baseline'].set_index('period')
    enough=rows.loc['train','trades']>=60 and rows.loc['validation','trades']>=20
    improved=bool((rows.win_rate>bases.win_rate).all() and (rows.max_dd<bases.max_dd).all())
    positive=bool((rows.profit_factor>=1.2).all() and (rows.net_points>0).all())
    score=float(((rows.win_rate-bases.win_rate)/100 + (1-rows.max_dd/bases.max_dd)).mean())
    rank.append(dict(name=name,enough=bool(enough),improved=improved,positive=positive,qualified=bool(enough and improved and positive),score=score))
ranking=pd.DataFrame(rank).sort_values(['qualified','enough','improved','score'],ascending=False)
ranking.to_csv(OUT/'selection.csv',index=False)
chosen=ranking.iloc[0]['name']
# Freeze selection before evaluating any confluence candidate on holdout.
selection=dict(chosen=chosen,qualified_on_development=bool(ranking.iloc[0]['qualified']),
    train_start=str(days[0]),validation_start=str(vstart),test_start=str(tstart),test_end=str(days[-1]),
    candidates=len(filters)-1,selection_rule='At least 60 train/20 validation trades; higher win rate and lower bar-close DD than baseline in both; PF >=1.2 and positive PnL in both. Rank qualified first, then trade count gate, joint improvement, mean normalized win/DD gain. If none qualifies, selected result is exploratory only.',
    baseline_holdout_previously_seen=True,volume_nonzero_bars=int((frame.volume>0).sum()))
(OUT/'frozen_selection.json').write_text(json.dumps(selection,indent=2))
final=[];curves={}
for name in ['Baseline',chosen]:
    for period in ['train','validation','test','full']:
        for cost in ([5,10] if period in ['test','full'] else [5]):
            metrics,trades,eq=run(name,period,cost)
            final.append(metrics)
            if cost==5 and period in ['full','test']:
                label='baseline' if name=='Baseline' else 'selected'
                trades.to_csv(OUT/f'{label}_{period}_trades.csv',index=False)
                if period=='full':curves[name]=eq
    if name=='Baseline':
        old=pd.read_csv(HERE/'both_trades.csv')
        new=run(name,'full')[1]
        assert len(old)==len(new) and np.allclose(old.PnL,new.PnL), 'Baseline drift'
summary=pd.DataFrame(final);summary.to_csv(OUT/'comparison.csv',index=False)
pd.DataFrame(curves).to_csv(OUT/'equity.csv')
fig=make_subplots(rows=2,cols=1,shared_xaxes=True,subplot_titles=['Net cumulative index points, 5-point roundtrip cost','Bar-close drawdown, points'])
for name,eq in curves.items():
    fig.add_trace(go.Scatter(x=eq.index,y=eq-capital,name=name),row=1,col=1)
    fig.add_trace(go.Scatter(x=eq.index,y=eq-eq.cummax(),name=name,showlegend=False),row=2,col=1)
fig.update_layout(template='plotly_dark',height=800,title=f'EMA 10/30 confluence: {chosen}')
fig.write_html(OUT/'report.html',include_plotlyjs=True)
heat=development.pivot(index='name',columns='period',values='win_rate')
go.Figure(go.Heatmap(z=heat.values,x=heat.columns,y=heat.index,colorbar_title='Win %')).update_layout(template='plotly_dark',height=800,title='Development win rates — holdout excluded').write_html(OUT/'development_heatmap.html',include_plotlyjs=True)
print(json.dumps(selection,indent=2));print(summary.to_string(index=False))
