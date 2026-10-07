"""Read-only underlying proxy replay, not a historical ATM-option backtest."""
import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def replay(rows, cost_bps):
    trades=[];position=None
    for row,next_row in zip(rows,rows[1:]):
        event=row.get('lifecycle_event')
        if not event:continue
        execution=row['open'] if row.get('lifecycle_reason')=='TIMED_SQUARE_OFF_1515' else next_row['open']
        execution_time=row['timestamp'] if row.get('lifecycle_reason')=='TIMED_SQUARE_OFF_1515' else next_row['timestamp']
        if event.endswith('EXIT'):
            if position:
                sign=1 if position['direction']=='BULLISH' else -1
                gross=sign*(execution-position['price'])
                costs=(execution+position['price'])*cost_bps/10000
                trades.append({**position,'exit_time':execution_time,'exit_price':execution,'exit_reason':row['lifecycle_reason'],'gross_points':gross,'modeled_cost_points':costs,'net_points':gross-costs})
                position=None
            continue
        if position:continue
        position=dict(direction='BULLISH' if event=='BUY' else 'BEARISH',price=execution,entry_time=execution_time)
    gains=sum(max(0,t['net_points']) for t in trades);losses=sum(max(0,-t['net_points']) for t in trades)
    return dict(closed_trades=len(trades),win_rate=sum(t['net_points']>0 for t in trades)/len(trades) if trades else None,
                gross_points=sum(t['gross_points'] for t in trades),net_points=sum(t['net_points'] for t in trades),
                profit_factor=gains/losses if losses else None,open_position=position,trades=trades)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--symbol',default='NSE:NIFTY50-INDEX');p.add_argument('--timeframe',default='5 minutes');p.add_argument('--cost-bps',type=float,default=10)
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'output/renko-supertrend-replay.json')
    args=p.parse_args()
    if args.cost_bps<0:p.error('Costs must be nonnegative.')
    query=urlencode(dict(symbol=args.symbol,timeframe=args.timeframe))
    with urlopen('http://127.0.0.1:8080/api/renko-supertrend/chart?'+query,timeout=30) as response:data=json.load(response)
    result=dict(scope='Closed-candle underlying-price proxy only; not intrabar tick fills, ATM-option performance or promotion evidence.',
                symbol=args.symbol,timeframe=args.timeframe,host_bars=len(data['rows']),initialization_anchor=data['initialization_anchor'],
                settings=data['settings'],execution='Confirmed historical lifecycle at next host-bar open; timed cutoff at deadline bar open; no same-candle re-entry. Does not simulate intrabar tick execution.',
                modeled_cost_bps_per_side=args.cost_bps,summary=replay(data['rows'],args.cost_bps))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2))
    report=args.output.with_suffix('.html');report.write_text('<!doctype html><meta charset="utf-8"><title>Renko research replay</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;color:#172536}pre{white-space:pre-wrap;background:#eef3f7;padding:20px}</style><h1>Renko Supertrend research replay</h1><p>'+html.escape(result['scope'])+'</p><pre>'+html.escape(json.dumps({k:v for k,v in result.items() if k!='summary'}|{'summary':{k:v for k,v in result['summary'].items() if k!='trades'}},indent=2))+'</pre>')
    print(json.dumps({k:v for k,v in result['summary'].items() if k!='trades'},indent=2));print('Saved',args.output,report)


if __name__=='__main__':main()
