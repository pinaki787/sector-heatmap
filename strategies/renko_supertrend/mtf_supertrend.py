"""Completed one/five-minute Supertrend agreement; no order routing."""
import math
from .signals import Engine, completed

REVISION = 'completed-1m-5m-supertrend-v1'


def latest(candles, config, tick_size, seconds, at):
    rows = completed([c for c in candles if not c.get('is_forming') and c['timestamp'] + seconds <= at])
    if len(rows) < 2 or not 0 <= at - rows[-1]['timestamp'] - seconds < seconds:
        raise ValueError('Completed Supertrend source is missing or stale.')
    if rows[-2]['timestamp'] + seconds != rows[-1]['timestamp']:
        raise ValueError('Consecutive completed Supertrend candles required.')
    engine = Engine({**config, 'timeframe': '1 minute' if seconds == 60 else '5 minutes'}, tick_size)
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
        result['one_minute'] = latest(one_rows, config, tick_size, 60, at)
        result['five_minute'] = latest(five_rows, config, tick_size, 300, at)
        result['allowed'] = agreement(result['one_minute'], result['five_minute'], direction)
        result['reason'] = 'One-minute and five-minute Supertrend agree.' if result['allowed'] else 'One-minute and five-minute Supertrend do not agree with the requested side; entry blocked.'
    except (ValueError, KeyError, TypeError) as error:
        result['reason'] = 'Supertrend agreement unavailable; entry blocked: ' + str(error)
    return result
