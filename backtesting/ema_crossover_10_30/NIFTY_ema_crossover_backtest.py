"""EMA 10/30, Nifty spot proxy; read-only history, no broker order calls.
Adapted from the EMA crossover VectorBT skill template.
Run with a Python environment containing openalgo, vectorbt, pandas, plotly, fyers_apiv3.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import vectorbt as vbt
from openalgo import ta
from dotenv import load_dotenv, find_dotenv
from fyers_apiv3 import fyersModel
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from sector_heatmap.web import load_config
load_dotenv(find_dotenv(), override=False)
IST = ZoneInfo('Asia/Kolkata')

def main():
    now = datetime.now(IST)
    end = now.date() - timedelta(days=1)
    start = end - timedelta(days=364)
    cache = OUT / 'candles.csv'
    if cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(IST)
    else:
        app, token = load_config()['FYERS_ACCESS_TOKEN'].split(':', 1)
        client = fyersModel.FyersModel(client_id=app, token=token)
        rows, cursor = [], start - timedelta(days=10)
        while cursor <= end:
            until = min(cursor + timedelta(days=89), end)
            r = client.history(dict(symbol='NSE:NIFTY50-INDEX', resolution='5', date_format=1,
                                    range_from=str(cursor), range_to=str(until), cont_flag=1))
            if r.get('s') != 'ok':
                raise RuntimeError(r.get('message', 'History unavailable'))
            rows.extend(r['candles'])
            cursor = until + timedelta(days=1)
        df = pd.DataFrame(rows, columns=['epoch','open','high','low','close','volume'])
        df = df.drop_duplicates()
        assert not df.epoch.duplicated().any(), 'Conflicting duplicate candles'
        df.index = pd.to_datetime(df.pop('epoch'), unit='s', utc=True).dt.tz_convert(IST)
        df = df.sort_index()
        assert not df.index.duplicated().any(), 'Duplicate candles'
        df.to_csv(cache)
    df = df.between_time('09:15','15:25')
    df = df[(df.index.dayofweek < 5) & (df.index.date <= end)]
    assert (df.high >= df[['open','close','low']].max(axis=1)).all()
    assert (df.low <= df[['open','close','high']].min(axis=1)).all()
    counts = df.groupby(df.index.date).size()
    good = counts[counts == 75].index
    omitted = {str(k):int(v) for k,v in counts.items() if v != 75}
    fast, slow = ta.ema(df.close,10), ta.ema(df.close,30)
    up = ((fast>slow)&(fast.shift()<=slow.shift())).fillna(False)
    down = ((fast<slow)&(fast.shift()>=slow.shift())).fillna(False)
    up, down = pd.Series(ta.exrem(up,down), index=df.index), pd.Series(ta.exrem(down,up),index=df.index)
    same_day = pd.Series(df.index.date,index=df.index).eq(pd.Series(df.index.date,index=df.index).shift())
    contiguous = df.index.to_series().diff().eq(pd.Timedelta(minutes=5))
    buy = up.shift(fill_value=False)&same_day&contiguous
    sell = down.shift(fill_value=False)&same_day&contiguous
    mask = (df.index.date>=start)&df.index.isin(df[df.index.map(lambda t:t.date() in good)].index)
    df, buy, sell = df[mask], buy[mask], sell[mask]
    allowed = (df.index.strftime('%H:%M')<'15:20')
    flat = pd.Series(df.index.strftime('%H:%M')=='15:20',index=df.index)
    buy, sell = buy&allowed, sell&allowed
    capital = float(df.open.iloc[0])
    results, curves = [], {}
    for mode in ['Long','Short','Both']:
        for cost in [0,2,5,10]:
            pf = vbt.Portfolio.from_signals(df.close,
                entries=buy if mode!='Short' else False, exits=sell|flat,
                short_entries=sell if mode!='Long' else False, short_exits=buy|flat,
                price=df.open, size=1, size_type='amount', min_size=1,size_granularity=1,
                init_cash=capital*10, fixed_fees=0, fees=(cost/2)/df.open,
                upon_opposite_entry='reverse',freq='5min')
            trades = pf.trades.records_readable
            assert (trades['Status']=='Closed').all()
            assert (pd.to_datetime(trades['Entry Timestamp']).dt.date.values == pd.to_datetime(trades['Exit Timestamp']).dt.date.values).all()
            pnl = trades.PnL
            direction = trades.Direction.map({'Long':1,'Short':-1})
            expected = direction*(trades['Avg Exit Price']-trades['Avg Entry Price'])-cost
            assert np.allclose(pnl,expected), 'Trade cost reconciliation failed'
            equity = capital + pf.value()-capital*10
            daily = equity.groupby(equity.index.date).last()
            ret = daily.pct_change().dropna()
            dd = equity/equity.cummax()-1
            downside = np.sqrt(np.mean(np.minimum(ret,0)**2))
            row = dict(mode=mode,roundtrip_cost_points=cost,trades=len(pnl),net_points=float(pnl.sum()),
                       return_pct=float(pnl.sum()/capital*100),win_rate_pct=float((pnl>0).mean()*100),
                       profit_factor=float(pnl[pnl>0].sum()/-pnl[pnl<0].sum()),
                       average_points=float(pnl.mean()),max_drawdown_points=float((equity.cummax()-equity).max()),
                       max_drawdown_pct=float(-dd.min()*100),sharpe=float(ret.mean()/ret.std()*np.sqrt(252)),
                       sortino=float(ret.mean()/downside*np.sqrt(252)))
            results.append(row)
            if cost==5:
                trades.to_csv(OUT/f'{mode.lower()}_trades.csv',index=False)
                (OUT/f'{mode.lower()}_stats.txt').write_text(str(pf.stats()))
                curves[mode]=equity
                monthly = trades.assign(month=pd.to_datetime(trades['Exit Timestamp']).dt.strftime('%Y-%m')).groupby('month').PnL.agg(['sum','count'])
                monthly.to_csv(OUT/f'{mode.lower()}_monthly.csv')
                split = sorted(set(df.index.date))[int(len(set(df.index.date))*.7)]
                row['chronological_split'] = str(split)
                row['first_70pct_points'] = float(trades.loc[pd.to_datetime(trades['Exit Timestamp']).dt.date<split,'PnL'].sum())
                row['last_30pct_points'] = float(trades.loc[pd.to_datetime(trades['Exit Timestamp']).dt.date>=split,'PnL'].sum())
    benchmark = df.close-df.open.iloc[0]+capital
    curves['Nifty buy and hold (gross)']=benchmark
    bret = benchmark.groupby(benchmark.index.date).last().pct_change().dropna()
    meta = dict(source='FYERS NSE:NIFTY50-INDEX',start=str(df.index[0]),end=str(df.index[-1]),
                sessions=len(set(df.index.date)),bars=len(df),omitted_incomplete_sessions=omitted,
                benchmark_return_pct=float((benchmark.iloc[-1]/capital-1)*100),
                benchmark_max_dd_pct=float(-(benchmark/benchmark.cummax()-1).min()*100),
                benchmark_sharpe=float(bret.mean()/bret.std()*np.sqrt(252)),
                benchmark_sortino=float(bret.mean()/np.sqrt(np.mean(np.minimum(bret,0)**2))*np.sqrt(252)),
                note='One index unit, constant size. Return denominator is initial index value, not margin. Costs are illustrative all-in roundtrip points, not verified contract charges. EMA carries across sessions. No SL or target; opposite crossover or 15:20 exit. Incomplete sessions excluded. No overnight trades.')
    (OUT/'results.json').write_text(json.dumps(dict(metadata=meta,results=results),indent=2))
    pd.DataFrame(results).to_csv(OUT/'comparison.csv',index=False)
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,subplot_titles=['Cumulative P&L, index points (5-point roundtrip cost)','Drawdown, index points'])
    for name,eq in curves.items():
        fig.add_trace(go.Scatter(x=eq.index,y=eq-capital,name=name),row=1,col=1)
        fig.add_trace(go.Scatter(x=eq.index,y=eq-eq.cummax(),name=name,showlegend=False),row=2,col=1)
    fig.update_layout(template='plotly_dark',title='Nifty 5-minute EMA 10/30 — index proxy',height=850)
    fig.write_html(OUT/'report.html',include_plotlyjs=True)
    pd.DataFrame(curves).to_csv(OUT/'equity.csv')
    print(json.dumps(dict(metadata=meta,results=results),indent=2))

if __name__=='__main__':
    main()
