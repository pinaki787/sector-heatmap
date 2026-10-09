"""Optional selected host/higher-timeframe Supertrend agreement; no order routing."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from .signals import Engine, completed

REVISION = 'optional-selected-htf-supertrend-v2'
from strategies.ema_crossover.runner import TIMEFRAMES

def settings(payload):
    enabled=payload.get('higher_timeframe_enabled',False);frame=payload.get('supertrend_timeframe','5 minutes')
    if not isinstance(enabled,bool) or frame not in TIMEFRAMES:raise ValueError('Choose a supported Supertrend timeframe and boolean higher-timeframe check.')
    host=payload.get('timeframe','1 minute')
    if enabled and (host not in TIMEFRAMES or TIMEFRAMES[frame]<=TIMEFRAMES[host]):raise ValueError('Supertrend confirmation timeframe must be higher than the selected host timeframe.')
    if enabled and payload.get('broker')=='DELTA_INDIA':
        from .delta_contracts import RESOLUTIONS
        if frame not in RESOLUTIONS:raise ValueError('Selected higher timeframe is unavailable on Delta.')
    return dict(higher_timeframe_enabled=enabled,supertrend_timeframe=frame)


def latest(candles, config, tick_size, seconds, at):
    rows = completed([c for c in candles if not c.get('is_forming') and c['timestamp'] + seconds <= at])
    if len(rows) < max(30,int(config.get('atr_length',5))) or not 0 <= at - rows[-1]['timestamp'] - seconds < seconds:
        raise ValueError('Completed Supertrend source is missing or stale.')
    def gap_ok(a,b):
        if b['timestamp']-a['timestamp']==seconds:return True
        session=config.get('master_regular_session')
        if config.get('seven_day_session') or not session:return False
        x=datetime.fromtimestamp(a['timestamp'],ZoneInfo('Asia/Kolkata'));y=datetime.fromtimestamp(b['timestamp'],ZoneInfo('Asia/Kolkata'))
        close=int(session[5:7])*60+int(session[7:9]);end=x.hour*60+x.minute+seconds/60
        return x.date()<y.date() and close<=end<close+seconds/60 and y.strftime('%H%M')==session[:4]
    if any(not gap_ok(a,b) for a,b in zip(rows[-30:],rows[-29:])):
        raise ValueError('Incomplete recent Supertrend history.')
    frame=next(name for name,value in TIMEFRAMES.items() if value==seconds)
    engine = Engine({**config, 'timeframe':frame}, tick_size)
    result = None
    for row in rows:
        result = engine.update(row)
    if result['supertrend'] is None or not math.isfinite(result['supertrend']):
        raise ValueError('Supertrend is still warming up.')
    return {key: result[key] for key in ('timestamp', 'supertrend', 'direction')}


def agreement(one, five, direction):
    return direction in ('BULLISH', 'BEARISH') and one['direction'] == five['direction'] == direction


def check(one_rows, five_rows, config, tick_size, direction, at):
    result = dict(revision=REVISION, allowed=False, observed_at=at, one_minute=None, five_minute=None)
    try:
        result['host_timeframe']=config.get('timeframe','1 minute');result['higher_timeframe']=config.get('supertrend_timeframe','5 minutes')
        result['one_minute'] = latest(one_rows, config, tick_size, TIMEFRAMES[result['host_timeframe']], at)
        result['five_minute'] = latest(five_rows, config, tick_size, TIMEFRAMES[result['higher_timeframe']], at)
        result['allowed'] = agreement(result['one_minute'], result['five_minute'], direction)
        result['reason'] = result['host_timeframe']+' and '+result['higher_timeframe']+' Supertrend agree.' if result['allowed'] else result['host_timeframe']+' and '+result['higher_timeframe']+' Supertrend do not agree with the requested side; entry blocked.'
    except (ValueError, KeyError, TypeError) as error:
        result['reason'] = 'Supertrend agreement unavailable; entry blocked: ' + str(error)
    return result
