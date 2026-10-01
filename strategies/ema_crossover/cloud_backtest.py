"""EMA Cloud diagnostic on underlying prices, not an option execution backtest."""
import argparse,csv,json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from signals import series,exit_on_close

def run(path):
    with open(path) as f:
        candles=series([dict(timestamp=datetime.fromisoformat(r['epoch']).timestamp(),**{k:float(r[k]) for k in ['open','high','low','close','volume']}) for r in csv.DictReader(f)])
    position=None;trades=[]
    for i,c in enumerate(candles[1:],1):
        prev=candles[i-1]
        if c['timestamp']-prev['timestamp']!=300:continue
        if position:
            if prev['timestamp']>position['signal_bar'] and exit_on_close(prev,position['direction']):
                points=(c['open']-position['entry'])*(1 if position['direction']=='BULLISH' else -1)-5
                trades.append(dict(**position,exit=c['open'],net_points=points,exit_bar=c['timestamp']))
                position=None
            continue
        if prev['direction']:
            position=dict(direction=prev['direction'],entry=c['open'],signal_bar=prev['timestamp'])
    profits=[t['net_points'] for t in trades];wins=sum(max(0,p) for p in profits);losses=-sum(min(0,p) for p in profits)
    return dict(label='EMA Cloud underlying-only diagnostic; no option-price or live-fill validation',bars=len(candles),closed_trades=len(trades),net_points=round(sum(profits),2),profit_factor=round(wins/losses,3) if losses else None,round_trip_cost_points=5,open_position_at_end=position,quantstats='Unavailable; no tear sheet generated'),trades

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    summary,trades=run(a.input);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    (out/'cloud-backtest-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
