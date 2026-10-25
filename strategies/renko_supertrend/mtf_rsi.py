"""Optional completed-bar RSI confirmations, with independent slot levels."""
from bisect import bisect_right
from datetime import datetime
from zoneinfo import ZoneInfo
import math
from strategies.ema_crossover.runner import TIMEFRAMES
from .rsi_slope import observe

REVISION = 'optional-three-htf-rsi-v2'
SLOTS = (1, 2, 3)
DEFAULT_FRAMES = ('15 minutes', '30 minutes', '1 hour')
LEVEL_DEFAULTS = dict(rsi_level_mode='THRESHOLD', rsi_bullish_above=50.0, rsi_bearish_below=40.0,
                      rsi_bullish_min=60.0, rsi_bullish_max=80.0, rsi_bearish_min=35.0, rsi_bearish_max=40.0)


def enabled(config):
    return any(config.get(f'rsi_htf_{slot}_enabled', False) for slot in SLOTS)


def settings(payload):
    result = {}
    for slot, default in zip(SLOTS, DEFAULT_FRAMES):
        on = payload.get(f'rsi_htf_{slot}_enabled', False)
        frame = payload.get(f'rsi_htf_{slot}_timeframe', default)
        if not isinstance(on, bool) or frame not in TIMEFRAMES:
            raise ValueError(f'RSI HTF {slot}: choose a supported timeframe and boolean switch.')
        if on:
            host = payload.get('timeframe', '5 minutes')
            if host not in TIMEFRAMES or TIMEFRAMES[frame] <= TIMEFRAMES[host]:
                raise ValueError(f'RSI HTF {slot} must be higher than the host timeframe.')
            if payload.get('broker') == 'DELTA_INDIA':
                from .delta_contracts import RESOLUTIONS
                if frame not in RESOLUTIONS:
                    raise ValueError(f'RSI HTF {slot} timeframe is unavailable on Delta India.')
        result.update({f'rsi_htf_{slot}_enabled': on and payload.get('rsi_family_enabled',True) is not False, f'rsi_htf_{slot}_timeframe': frame})
    if not enabled(result) and not any(key.startswith('rsi_htf_') and key.endswith(tuple(k[4:] for k in LEVEL_DEFAULTS)) for key in payload):
        return result
    from .signals import settings as host_settings
    host = host_settings({})
    levels = {key: payload.get(key, host.get(key, default)) for key, default in LEVEL_DEFAULTS.items()}
    validate_levels(levels, 'Main RSI')
    result.update(levels)
    for slot in SLOTS:
        own = slot_levels({**levels, **payload}, slot)
        validate_levels(own, f'RSI HTF {slot}')
        result.update({f'rsi_htf_{slot}_{key[4:]}': value for key, value in own.items()})
    return result


def validate_levels(levels, label):
    if levels['rsi_level_mode'] not in ('THRESHOLD', 'BETWEEN'):
        raise ValueError(f'{label}: choose threshold or range mode.')
    for key in LEVEL_DEFAULTS:
        if key == 'rsi_level_mode':
            continue
        raw = levels[key]
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f'{label}: levels must be finite numbers from 0 to 100.') from None
        if isinstance(raw, bool) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f'{label}: levels must be finite numbers from 0 to 100.')
        levels[key] = value
    if levels['rsi_bullish_min'] > levels['rsi_bullish_max'] or levels['rsi_bearish_min'] > levels['rsi_bearish_max']:
        raise ValueError(f'{label}: range minimum must not exceed maximum.')


def slot_levels(config, slot):
    return {key: config.get(f'rsi_htf_{slot}_{key[4:]}', config.get(key, default)) for key, default in LEVEL_DEFAULTS.items()}


def query_settings(query):
    raw = {key: values[0] for key, values in query.items() if values}
    for slot in SLOTS:
        key = f'rsi_htf_{slot}_enabled'
        if key in raw:
            if raw[key] not in ('true', 'false'):
                raise ValueError('RSI HTF switches must be true or false.')
            raw[key] = raw[key] == 'true'
    return settings(raw)


def matches(value, direction, config):
    from .rsi_level import matches as host_matches
    return host_matches(value, direction, {**LEVEL_DEFAULTS, **config})


def frames(config):
    return list(dict.fromkeys(config[f'rsi_htf_{i}_timeframe'] for i in SLOTS if config.get(f'rsi_htf_{i}_enabled')))


def _continuous(previous, current, seconds, config):
    if current - previous == seconds:
        return True
    session = config.get('master_regular_session')
    if config.get('seven_day_session') or not session:
        return False
    x = datetime.fromtimestamp(previous, ZoneInfo('Asia/Kolkata'))
    y = datetime.fromtimestamp(current, ZoneInfo('Asia/Kolkata'))
    close = int(session[5:7]) * 60 + int(session[7:9])
    return x.date() < y.date() and close <= x.hour * 60 + x.minute + seconds / 60 < close + seconds / 60 and y.strftime('%H%M') == session[:4]


def prepare(sources, config):
    """Build RSI once per timeframe, for efficient historical as-of lookups."""
    from .signals import completed
    result = {}
    for frame in frames(config):
        seconds = TIMEFRAMES[frame]
        try:
            rows = completed(sources.get(frame, []))
            state = {}; points = []; previous = None
            for row in rows:
                if previous is not None and not _continuous(previous, row['timestamp'], seconds, config):
                    state = {}  # Missing native candles require a fresh Wilder warmup.
                observation = observe(state, row['close'], int(config.get('rsi_slope_length', 14)))
                points.append(dict(timestamp=row['timestamp'], closed_at=row['timestamp'] + seconds, **observation))
                previous = row['timestamp']
            result[frame] = dict(points=points, times=[p['closed_at'] for p in points], seconds=seconds)
        except (ValueError, KeyError, TypeError) as error:
            result[frame] = dict(error=str(error), points=[], times=[], seconds=seconds)
    return result


def assess(prepared, config, direction, at):
    slots = []
    for slot in SLOTS:
        if not config.get(f'rsi_htf_{slot}_enabled'):
            continue
        frame = config[f'rsi_htf_{slot}_timeframe']; source = prepared.get(frame, {})
        index = bisect_right(source.get('times', []), at) - 1
        point = source['points'][index] if index >= 0 else {}
        fresh = bool(point) and 0 <= at - point['closed_at'] < TIMEFRAMES[frame]
        value = point.get('rsi14')
        ready = isinstance(value, (int, float)) and math.isfinite(value)
        passed = fresh and ready and matches(value, direction, slot_levels(config, slot))
        reason = ('PASS' if passed else 'WARMUP' if fresh and not ready else 'RSI_LEVEL' if fresh else 'MISSING_OR_STALE')
        slots.append(dict(slot=slot, timeframe=frame, enabled=True, allowed=passed, fresh=fresh,
                          rsi=value, levels=slot_levels(config, slot), length=int(config.get('rsi_slope_length', 14)),
                          candle_at=point.get('timestamp'), closed_at=point.get('closed_at'),
                          age_seconds=at - point['closed_at'] if point else None,
                          reason=reason, source_error=source.get('error')))
    allowed = all(s['allowed'] for s in slots)
    return dict(revision=REVISION, enabled=bool(slots), allowed=allowed, observed_at=at,
                direction=direction, slots=slots, shared_levels={key: config.get(key, default) for key, default in LEVEL_DEFAULTS.items()},
                reason='Higher-timeframe RSI checks passed.' if allowed and slots else 'Higher-timeframe RSI checks OFF.' if not slots else 'Higher-timeframe RSI does not qualify or completed native history is unavailable; entry blocked.')


def check(sources, config, direction, at):
    # Cut before validation/calculation: no forming or future candles affect a decision.
    filtered = {frame: [r for r in rows if not r.get('is_forming') and r.get('timestamp', float('inf')) + TIMEFRAMES[frame] <= at]
                for frame, rows in sources.items() if frame in TIMEFRAMES}
    return assess(prepare(filtered, config), config, direction, at)
