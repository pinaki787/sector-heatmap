"""Chart evidence from the exact validated completed rows used by review."""
from datetime import datetime
from .holdings_analysis import IST, indicators

def chart_evidence(rows):
    candles=[dict(time=datetime.fromtimestamp(r['timestamp'],IST).date().isoformat(),
                  **{k:r[k] for k in ('open','high','low','close')}) for r in rows]
    series={k:[] for k in ('ema20','ema50','weekly_ema20','rsi14','atr14','support20','resistance20','low5','high5')}
    # Reuse the rule implementation, including seeds and prior-week exclusion.
    for end in range(110,len(rows)+1):
        try:info=indicators(rows[:end])
        except ValueError:continue
        for key in series:series[key].append(dict(time=candles[end-1]['time'],value=info[key]))
    weeks={}
    latest=datetime.fromtimestamp(rows[-1]['timestamp'],IST).date().isocalendar()[:2]
    for row,candle in zip(rows,candles):
        week=datetime.fromtimestamp(row['timestamp'],IST).date().isocalendar()[:2]
        if week==latest:continue
        if week not in weeks:weeks[week]=dict(candle)
        else:
            weeks[week]['high']=max(weeks[week]['high'],candle['high'])
            weeks[week]['low']=min(weeks[week]['low'],candle['low'])
            weeks[week]['close']=candle['close']
    weekly=list(weeks.values());weekly_ema=[]
    from .holdings_analysis import ema
    for end in range(20,len(weekly)+1):
        weekly_ema.append(dict(time=weekly[end-1]['time'],value=ema([r['close'] for r in weekly[:end]],20)))
    return dict(candles=candles,series=series,weekly_candles=weekly,weekly_ema20=weekly_ema,
                basis='Exact completed daily review candles; prior-week series excludes the latest calendar week.',
                last_session=candles[-1]['time'])
