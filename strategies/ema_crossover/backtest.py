"""Diagnostic underlying-point backtest, not an option-price profitability study."""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from signals import series


def run(path, friction=5):
    rows=[]
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(dict(timestamp=datetime.fromisoformat(r['epoch']).timestamp(),**{k:float(r[k]) for k in ('open','high','low','close','volume')}))
    candles=series(rows)
    sessions={}
    for c in candles:
        dt=datetime.fromtimestamp(c['timestamp'],ZoneInfo('Asia/Kolkata'))
        sessions.setdefault(dt.date(),set()).add(dt.hour*60+dt.minute)
    expected=set(range(9*60+15,15*60+30,5))
    good={day for day,minutes in sessions.items() if minutes==expected}
    omitted=[str(day) for day in sessions if day not in good]
    candles=[c for c in candles if datetime.fromtimestamp(c['timestamp'],ZoneInfo('Asia/Kolkata')).date() in good]
    trades=[];position=None;last_day=None
    for i,c in enumerate(candles):
        dt=datetime.fromtimestamp(c['timestamp'],ZoneInfo('Asia/Kolkata'))
        if position and last_day!=dt.date():
            raise ValueError('Missing prior-day square-off candle; refuses overnight backtest.')
        last_day=dt.date()
        prev=candles[i-1] if i else None
        contiguous=prev and c['timestamp']-prev['timestamp']==300
        direction=(1 if prev['direction']=='BULLISH' else -1 if prev['direction']=='BEARISH' else 0) if contiguous else 0
        cutoff=dt.hour*60+dt.minute>=15*60+20
        if position and (cutoff or direction and direction!=position['side']):
            pnl=(c['open']-position['entry'])*position['side']-friction
            trades.append({**position,'exit':c['open'],'exit_time':dt.isoformat(),'net_points':round(pnl,4)})
            position=None
        if direction and not cutoff and not position and dt.weekday()<5:
            position=dict(side=direction,entry=c['open'],entry_time=dt.isoformat())
    if position:
        raise ValueError('Incomplete final session; cannot mark an open position as closed.')
    values=[t['net_points'] for t in trades];gains=sum(max(0,v) for v in values);losses=-sum(min(0,v) for v in values)
    equity=peak=dd=0
    for v in values:
        equity+=v;peak=max(peak,equity);dd=max(dd,peak-equity)
    return dict(label='Underlying only; not option execution validation',source=str(path),omitted_incomplete_sessions=omitted,bars=len(candles),first=datetime.fromtimestamp(candles[0]['timestamp'],ZoneInfo('Asia/Kolkata')).isoformat(),last=datetime.fromtimestamp(candles[-1]['timestamp'],ZoneInfo('Asia/Kolkata')).isoformat(),round_trip_cost_points=friction,trades=len(trades),net_points=round(sum(values),2),profit_factor=round(gains/losses,3) if losses else None,max_closed_trade_drawdown_points=round(dd,2),win_rate_pct=round(100*sum(v>0 for v in values)/len(values),2) if values else None,quantstats='Not installed; no tear sheet generated'),trades

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    summary,trades=run(Path(args.input));out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'backtest-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'backtest-trades.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['side','entry','entry_time','exit','exit_time','net_points']);writer.writeheader();writer.writerows(trades)
    print(json.dumps(summary,indent=2))
