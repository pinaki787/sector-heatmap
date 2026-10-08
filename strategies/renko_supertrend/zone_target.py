"""Optional completed-5m opposing-zone exit. Pure OHLC evidence; no execution."""
import math
from copy import deepcopy

REVISION = 'strong-5m-zone-target-v1'
SECONDS = 300


def settings(payload):
    enabled = payload.get('zone_target_enabled', False)
    if not isinstance(enabled, bool):
        raise ValueError('Zone target enabled must be a boolean.')
    return {'zone_target_enabled': enabled}


def validate(rows):
    previous = None
    for c in rows:
        if any(isinstance(c.get(k), bool) or not isinstance(c.get(k), (float, int)) or not math.isfinite(c[k]) for k in ('timestamp', 'open', 'high', 'low', 'close')):
            raise ValueError('Invalid five-minute zone OHLC.')
        if c['low'] > min(c['open'], c['close']) or c['high'] < max(c['open'], c['close']) or previous is not None and c['timestamp'] <= previous:
            raise ValueError('Invalid or unordered five-minute zone OHLC.')
        previous = c['timestamp']


def zones(rows, timeline=None):
    """Same strict pivot and SMA-TR14 departure criterion as chart hostZones."""
    validate(rows)
    result = {'supply': None, 'demand': None}
    for i, c in enumerate(rows):
        for side, z in result.items():
            if z and z['broken_at'] is None and (c['close'] > z['upper'] if side == 'supply' else c['close'] < z['lower']):
                z['broken_at'] = c['timestamp'] + SECONDS
        if i < 15:
            if timeline is not None:timeline.append(deepcopy(result))
            continue
        p = i - 2
        pivot = rows[p]
        neighbors = [rows[i-4], rows[i-3], rows[i-1], c]
        atr = sum(max(rows[j]['high'] - rows[j]['low'], abs(rows[j]['high'] - rows[j-1]['close']) if j else 0, abs(rows[j]['low'] - rows[j-1]['close']) if j else 0) for j in range(p-13, p+1)) / 14
        if atr <= 0:
            if timeline is not None:timeline.append(deepcopy(result))
            continue
        low_close = min(rows[i-1]['close'], c['close'])
        high_close = max(rows[i-1]['close'], c['close'])
        supply_near = max(pivot['open'], pivot['close'])
        demand_near = min(pivot['open'], pivot['close'])
        common = dict(pivot_at=pivot['timestamp'], confirmed_at=c['timestamp']+SECONDS, broken_at=None, atr=atr)
        if all(pivot['high'] > n['high'] for n in neighbors) and low_close < pivot['low'] and supply_near-low_close >= atr:
            result['supply'] = dict(common, lower=supply_near, upper=pivot['high'], departure=supply_near-low_close)
        if all(pivot['low'] < n['low'] for n in neighbors) and high_close > pivot['high'] and high_close-demand_near >= atr:
            result['demand'] = dict(common, lower=pivot['low'], upper=demand_near, departure=high_close-demand_near)
        if timeline is not None:timeline.append(deepcopy(result))
    return result


def assess(rows, position, now):
    """Touch and outcome use one wholly post-fill closed 5m candle.

    Only zones known before the decision candle opened may be targeted. A
    close beyond the outer boundary continues; every other touched close
    requests exit. OHLC ordering inside that candle is never invented.
    """
    validate(rows)
    closed = [c for c in rows if not c.get('is_forming') and c['timestamp']+SECONDS <= now]
    if not closed:
        raise ValueError('Completed five-minute source unavailable.')
    c = closed[-1]
    event_at = c['timestamp'] + SECONDS
    if not 0 <= now-event_at < SECONDS:
        raise ValueError('Five-minute target source is stale.')
    direction = position.get('direction')
    if direction not in ('BULLISH', 'BEARISH'):
        raise ValueError('Owned underlying direction required.')
    opened = (position.get('exposure_range') or {}).get('entry_at', position.get('opened_at'))
    result = dict(revision=REVISION, candle_at=c['timestamp'], event_at=event_at, observed_at=now, reason=None, state='NO_TARGET', zone=None, close=c['close'])
    if opened is None or c['timestamp'] < opened:
        return dict(result, state='WAIT_FOR_WHOLE_POST_FILL_CANDLE')
    if len(closed) < 2 or closed[-2]['timestamp'] + SECONDS != c['timestamp']:
        raise ValueError('Consecutive five-minute evidence required for target assessment.')
    # c's own range/close cannot create the zone that exits this position.
    known = zones(closed[:-1])
    side = 'supply' if direction == 'BULLISH' else 'demand'
    z = known[side]
    previous_close = closed[-2]['close']
    if not z or z['broken_at'] is not None or (previous_close > z['upper'] if side == 'supply' else previous_close < z['lower']):
        return result
    result.update(zone=deepcopy(z), side=side, state='UNTOUCHED')
    touch = c['high'] >= z['lower'] if side == 'supply' else c['low'] <= z['upper']
    if not touch:
        return result
    result['touched'] = True
    broken = c['close'] > z['upper'] if side == 'supply' else c['close'] < z['lower']
    if broken:
        return dict(result, state='CONFIRMED_BREAK_CONTINUE')
    rejected = c['close'] < z['lower'] if side == 'supply' else c['close'] > z['upper']
    return dict(result, state='EXIT_REQUESTED', reason='SD_5M_ZONE_REJECTION' if rejected else 'SD_5M_ZONE_NOT_BROKEN')
