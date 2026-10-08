"""Offline candidate comparison. No broker, runner activation, or option P&L claims."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .signals import Engine
from .research_replay import replay

IST = ZoneInfo('Asia/Kolkata')


def strict_onset(rows):
    """Separate candidate: completed entries, re-arm only on failed qualification.

    Keep the original signal engine and confirmed exit/deadline rules. An exit
    cannot itself reset entry qualification, unlike the reference projection.
    """
    result=[];position=None;qualified_before=False
    for original in rows:
        row=dict(original);row['lifecycle_event']=None;row['lifecycle_reason']=None
        qualified=row['entry_qualified'];onset=qualified and not qualified_before
        qualified_before=qualified
        if position:
            opposite='BEARISH' if position=='BULLISH' else 'BULLISH'
            adverse=row['close']<row['ema10'] if position=='BULLISH' else row['close']>row['ema10']
            at=datetime.fromtimestamp(row['timestamp']+60,IST)
            if (at.hour,at.minute)>=(15,15) or adverse or row['cross_direction']==opposite:
                row['lifecycle_event']='BUY EXIT' if position=='BULLISH' else 'SELL EXIT'
                row['lifecycle_reason']='TIMED_SQUARE_OFF_1515' if (at.hour,at.minute)>=(15,15) else 'EMA10_CONFIRMED_BREACH' if adverse else 'OPPOSITE_CONFIRMED_SUPERTREND'
                position=None
        elif onset:
            at=datetime.fromtimestamp(row['timestamp']+60,IST)
            if (at.hour,at.minute)<(15,15):
                position=row['direction'];row['lifecycle_event']='BUY' if position=='BULLISH' else 'SELL'
                row['lifecycle_reason']='STRICT_COMPLETED_QUALIFICATION_ONSET'
        result.append(row)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--state',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    cache=json.loads(args.cache.read_text());state=json.loads(args.state.read_text())
    config={**state['config'],'intrabar_entries':False}
    engine=Engine(config,.05)
    rows=[engine.update(dict(zip(('timestamp','open','high','low','close','volume'),r))) for r in cache['rows']]
    days=sorted({datetime.fromtimestamp(r['timestamp'],IST).date().isoformat() for r in rows})
    # Exclude the partial current session and reserve the previous five sessions.
    complete_days=days[:-1];heldout=complete_days[-5:];development=complete_days[:-5]
    report=dict(scope='Underlying OHLC proxy. Cannot reconstruct intrabar fills, historical option spreads, slippage or option net P&L. No promotion evidence.',
                symbol=config['underlying'],bars=len(rows),warmup_sessions=5,config=config,
                cache_complete=cache.get('complete'),cache_error=cache.get('error'),
                reference='Original completed-candle projection; current tick strategy cannot be reconstructed from OHLC.',
                candidate='Completed-candle entry onset; exit does not re-arm continuing qualification. Original EMA and Supertrend rules retained.',
                heldout_sessions=heldout,results={})
    for name,source in [('reference',rows),('strict_onset_candidate',strict_onset(rows))]:
        result={}
        for split,selected in [('development',development[5:]),('heldout',heldout)]:
            result[split]={}
            for bps in [0,1,2,5]:
                summary=replay(source,bps)
                trades=[t for t in summary['trades'] if datetime.fromtimestamp(t['entry_time'],IST).date().isoformat() in selected and datetime.fromtimestamp(t['exit_time'],IST).date().isoformat() in selected]
                equity=peak=dd=0
                for t in trades:equity+=t['net_points'];peak=max(peak,equity);dd=max(dd,peak-equity)
                result[split][str(bps)]=dict(cost_bps_per_side=bps,closed_trades=len(trades),gross_points=sum(t['gross_points'] for t in trades),net_points=sum(t['net_points'] for t in trades),max_drawdown_points=dd,win_rate=sum(t['net_points']>0 for t in trades)/len(trades) if trades else None)
        report['results'][name]=result
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report['results'],indent=2))


if __name__=='__main__':main()
