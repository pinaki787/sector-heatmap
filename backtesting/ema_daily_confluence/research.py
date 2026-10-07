"""Daily-frequency confluence research. Immutable baseline; no live order path.
Both-direction Nifty spot proxy with contemporaneous NIFTYBEES volume only.
All indicators evaluated on completed bars, entry/exit at next open.
"""
from pathlib import Path
import json,itertools
import numpy as np
import pandas as pd
import vectorbt as vbt
from openalgo import ta
from tqdm import tqdm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

OUT=Path(__file__).resolve().parent
BASE=OUT.parent/'ema_crossover_10_30'

def read(path):
    d=pd.read_csv(path,index_col=0);d.index=pd.to_datetime(d.index,utc=True).tz_convert('Asia/Kolkata')
    return d.sort_index().between_time('09:15','15:25')

def prepare():
    d=read(BASE/'candles.csv');d=d[(d.index.dayofweek<5)&(d.index.date<=pd.Timestamp('2026-09-28').date())]
    e=read(OUT/'niftybees_5m.csv');e=e[e.index.dayofweek<5]
    # Prior same-clock-slot observations only: no future values, no backfill.
    e['slot']=e.index.strftime('%H:%M')
    typical=e.groupby('slot').volume.transform(lambda x:x.shift().rolling(20,min_periods=10).median())
    rvol=(e.volume/typical.replace(0,np.nan)).reindex(d.index)
    d['rvol']=rvol;d['proxy_volume']=e.volume.reindex(d.index)
    d['ema10']=ta.ema(d.close,10);d['ema30']=ta.ema(d.close,30)
    d['rsi']=ta.rsi(d.close,14);d['atr']=ta.atr(d.high,d.low,d.close,14)
    d['mom']=ta.mom(d.close,3)
    d['trend']=np.where(d.ema10>d.ema30,1,np.where(d.ema10<d.ema30,-1,0))
    counts=d.groupby(d.index.date).size();good=counts[counts==75].index
    d=d[(d.index.date>=pd.Timestamp('2025-09-29').date())&np.isin(d.index.date,good)]
    assert len(d)==18375 and len(set(d.index.date))==245
    assert not d.index.duplicated().any()
    audit=dict(sessions=245,bars=len(d),missing_volume_bars=int(d.proxy_volume.isna().sum()),
        missing_rvol_bars=int(d.rvol.isna().sum()),volume_source='FYERS NSE:NIFTYBEES-EQ',
        volume_definition='Current ETF candle volume / median of same clock slot in prior 20 sessions, minimum 10',
        exclusions='Weekends and non-75-bar sessions; missing volume blocks entries, does not remove session denominator')
    (OUT/'aligned_data_audit.json').write_text(json.dumps(audit,indent=2))
    d.to_csv(OUT/'features.csv');return d

def events(d,cfg):
    """Sequential state controls repetition, daily cap, cooldown, risk and exit timing."""
    n=len(d);le=np.zeros(n,bool);se=le.copy();lx=le.copy();sx=le.copy();evidence=[]
    o,h,l,c=(d[x].to_numpy() for x in ['open','high','low','close'])
    trend,rsi,mom,atr,rv=(d[x].to_numpy() for x in ['trend','rsi','mom','atr','rvol'])
    dates=d.index.date;minutes=d.index.hour*60+d.index.minute
    position=0;entry=0.;risk=0.;entry_i=0;daily_count=0;last_exit=-100
    for i in range(3,n):
        if dates[i]!=dates[i-1]:
            assert position==0
            daily_count=0;last_exit=i-100
        j=i-1
        if position:
            earned=position*(c[j]-entry)
            reason=None
            if minutes[i]>=920:reason='15:20 square-off'
            elif trend[j]==-position:reason='Opposite EMA trend'
            elif earned<=-risk:reason='Completed-close ATR stop'
            elif earned>=risk*cfg['rr']:reason='Completed-close ATR target'
            elif i-entry_i>=12:reason='60-minute time exit'
            if reason:
                (lx if position==1 else sx)[i]=True
                evidence[-1]['exit_reason']=reason
                evidence[-1]['exit_index']=i
                position=0;last_exit=i
            continue
        # 09:30 through 14:45 next-open entries; max 3 trades/day; 10-min cooldown.
        if dates[j]!=dates[i] or not 570<=minutes[i]<=885 or daily_count>=cfg.get('daily_cap',3) or i-last_exit<2:continue
        if not np.isfinite(rv[j]) or not np.isfinite(atr[j]) or atr[j]<=0:continue
        side=int(trend[j])
        if side==0:continue
        if cfg['pa']=='breakout':
            price_action=c[j]>h[j-1] if side==1 else c[j]<l[j-1]
        elif cfg['pa']=='continuation':
            price_action=(c[j]>o[j] and c[j]>c[j-1] and c[j]>(h[j]+l[j])/2) if side==1 else (c[j]<o[j] and c[j]<c[j-1] and c[j]<(h[j]+l[j])/2)
        else:
            price_action=(min(l[j-2:j+1])<=d.ema10.iloc[j] and c[j]>h[j-1]) if side==1 else (max(h[j-2:j+1])>=d.ema10.iloc[j] and c[j]<l[j-1])
        if not price_action:continue
        volume_ok=rv[j]>=cfg['rvol']
        momentum_ok=side*mom[j]>0
        oscillator_ok=(cfg['rsi']<=rsi[j]<=75) if side==1 else (25<=rsi[j]<=100-cfg['rsi'])
        score=2+int(volume_ok)+int(momentum_ok)+int(oscillator_ok)
        if score<cfg['score']:continue
        position=side;entry=o[i];risk=atr[j]*1.5;entry_i=i;daily_count+=1
        (le if side==1 else se)[i]=True
        evidence.append(dict(entry_index=i,signal_timestamp=str(d.index[j]),entry_timestamp=str(d.index[i]),
            side=side,score=score,volume_ok=bool(volume_ok),momentum_ok=bool(momentum_ok),oscillator_ok=bool(oscillator_ok),
            rvol=float(rv[j]),rsi=float(rsi[j]),mom=float(mom[j]),atr=float(atr[j]),risk_points=float(risk)))
    assert position==0
    return le,se,lx,sx,pd.DataFrame(evidence)

def simulate(d,ev,cost=5):
    le,se,lx,sx,_=ev;capital=float(d.open.iloc[0])
    pf=vbt.Portfolio.from_signals(d.close,entries=le,exits=lx,short_entries=se,short_exits=sx,
        price=d.open,size=1,min_size=1,size_granularity=1,init_cash=capital*10,
        fees=(cost/2)/d.open,upon_opposite_entry='close',freq='5min')
    t=pf.trades.records_readable
    assert len(t)==int(le.sum()+se.sum())
    assert (t.Status=='Closed').all()
    assert np.allclose(t.PnL,t.Direction.map({'Long':1,'Short':-1})*(t['Avg Exit Price']-t['Avg Entry Price'])-cost)
    assert (pd.to_datetime(t['Entry Timestamp']).dt.date.values==pd.to_datetime(t['Exit Timestamp']).dt.date.values).all()
    return t, pf.value()-capital*10

def metrics(d,t,curve,days):
    idx=np.isin(d.index.date,days);timestamps=d.index[idx]
    selected=t[np.isin(pd.to_datetime(t['Entry Timestamp']).dt.date,days)]
    pnl=selected.PnL
    values=curve.loc[timestamps];values=values-values.iloc[0]
    drawdown=np.maximum.accumulate(np.r_[0,values])[1:]-values
    daily=selected.groupby(pd.to_datetime(selected['Entry Timestamp']).dt.date).size().reindex(days,fill_value=0)
    daily_pnl=selected.groupby(pd.to_datetime(selected['Exit Timestamp']).dt.date).PnL.sum().reindex(days,fill_value=0)
    capital=float(d.open.iloc[0]);returns=daily_pnl/capital
    return dict(trades=len(selected),sessions=len(days),trades_per_day=float(len(selected)/len(days)),
        traded_days=int((daily>0).sum()),zero_days=int((daily==0).sum()),coverage_pct=float((daily>0).mean()*100),
        min_trades_per_day=int(daily.min()),win_rate=float((pnl>0).mean()*100),net_points=float(pnl.sum()),
        profit_factor=float(pnl[pnl>0].sum()/-pnl[pnl<0].sum()) if (pnl<0).any() else None,
        expectancy=float(pnl.mean()),max_dd=float(drawdown.max()),return_pct=float(pnl.sum()/capital*100),
        sharpe=float(returns.mean()/returns.std()*np.sqrt(252)) if returns.std()>0 else 0,
        positive_days_pct=float((daily_pnl>0).mean()*100))

def main():
    d=prepare();days=np.array(sorted(set(d.index.date)))
    periods={'train':days[:147],'validation':days[147:196],'test':days[196:],'full':days}
    # Freeze modest grid and ranking before running it. No holdout-driven iteration.
    configs={}
    for pa,rv,rs,score,rr in itertools.product(['breakout','continuation','pullback'],[1.,1.2],[50,55],[4,5],[1.,1.5]):
        name=f'{pa}_vol{rv}_rsi{rs}_score{score}_RR{rr}'
        configs[name]=dict(pa=pa,rvol=rv,rsi=rs,score=score,rr=rr)
    (OUT/'search_plan.json').write_text(json.dumps(dict(configs=configs,train_sessions=147,validation_sessions=49,test_sessions=49,
        entry_limit='09:30–14:45; max 3/day; minimum 10-minute cooldown; one position',
        exits='1.5 ATR completed-close stop, 1.0R or 1.5R completed-close target, opposite EMA state, 60-minute maximum, 15:20 flat',
        selection='Qualify only if every train/validation day traded, both PF >=1.2, win rate > baseline and DD < baseline. Fallback ranks enough trades and positive train+validation PnL, then minimum daily coverage, then minimum PF. Holdout does not select.',
        holdout_previously_seen=True),indent=2))
    bt=pd.read_csv(BASE/'both_trades.csv');bt['Entry Timestamp']=pd.to_datetime(bt['Entry Timestamp']);bt['Exit Timestamp']=pd.to_datetime(bt['Exit Timestamp'])
    be=read(BASE/'equity.csv')['Both'];be=be-be.iloc[0]
    baseline={p:metrics(d,bt,be,ds) for p,ds in periods.items()}
    dev=[];cache={}
    # Signals are causal. Holdout performance is not computed during selection.
    for name,cfg in tqdm(configs.items(),desc='Development comparison'):
        ev=events(d,cfg);t,eq=simulate(d,ev);cache[name]=(ev,t,eq)
        for p in ['train','validation']:dev.append(dict(name=name,period=p,**metrics(d,t,eq,periods[p])))
    table=pd.DataFrame(dev);table.to_csv(OUT/'development.csv',index=False)
    rank=[]
    for name in configs:
        z=table[table.name==name].set_index('period')
        coverage=bool((z.zero_days==0).all());positive=bool((z.net_points>0).all())
        improvement=all(z.loc[p,'win_rate']>baseline[p]['win_rate'] and z.loc[p,'max_dd']<baseline[p]['max_dd'] for p in ['train','validation'])
        qualified=coverage and positive and improvement and bool((z.profit_factor>=1.2).all())
        rank.append(dict(name=name,qualified=qualified,daily_goal=coverage,positive_both=positive,improved_both=improvement,
            min_coverage=float(z.coverage_pct.min()),min_pf=float(z.profit_factor.min()),min_win=float(z.win_rate.min())))
    ranking=pd.DataFrame(rank).sort_values(['qualified','positive_both','min_coverage','min_pf'],ascending=False)
    ranking.to_csv(OUT/'ranking.csv',index=False);chosen=ranking.iloc[0]['name']
    frozen=dict(chosen=chosen,config=configs[chosen],qualified_candidates=int(ranking.qualified.sum()),
        daily_coverage_candidates=int(ranking.daily_goal.sum()),selection=ranking.iloc[0].to_dict(),
        period_dates={p:[str(ds[0]),str(ds[-1])] for p,ds in periods.items()})
    (OUT/'frozen_selection.json').write_text(json.dumps(frozen,indent=2))
    ev,t,eq=cache[chosen];ev[-1].to_csv(OUT/'selected_signal_evidence.csv',index=False)
    t.to_csv(OUT/'selected_trades.csv',index=False)
    out=[]
    for p,ds in periods.items():
        out.append(dict(name='Original EMA crossover',period=p,cost=5,**baseline[p]))
        out.append(dict(name=chosen,period=p,cost=5,**metrics(d,t,eq,ds)))
    t10,eq10=simulate(d,ev,10)
    for p in ['test','full']:out.append(dict(name=chosen,period=p,cost=10,**metrics(d,t10,eq10,periods[p])))
    pd.DataFrame(out).to_csv(OUT/'comparison.csv',index=False)
    daily=t.groupby(pd.to_datetime(t['Entry Timestamp']).dt.date).agg(trades=('PnL','size'),pnl=('PnL','sum')).reindex(days,fill_value=0)
    daily.to_csv(OUT/'daily_coverage.csv')
    pd.DataFrame({'Original EMA crossover':be,'Selected confluence':eq}).to_csv(OUT/'equity.csv')
    fig=make_subplots(rows=3,cols=1,shared_xaxes=True,subplot_titles=['Net index points at 5-point roundtrip cost','Drawdown at candle closes','Trades each session'])
    for name,series in [('Original EMA crossover',be),('Selected confluence',eq)]:
        fig.add_trace(go.Scatter(x=series.index,y=series,name=name),row=1,col=1)
        fig.add_trace(go.Scatter(x=series.index,y=series-series.cummax(),name=name,showlegend=False),row=2,col=1)
    fig.add_trace(go.Bar(x=daily.index,y=daily.trades,name='Trades/day'),row=3,col=1)
    fig.update_layout(template='plotly_dark',height=1000,title=chosen)
    fig.write_html(OUT/'report.html',include_plotlyjs=True)
    print(json.dumps(frozen,indent=2));print(pd.DataFrame(out).to_string(index=False))

if __name__=='__main__':main()
