"""Sequential port of source.pine, including Pine-style missing-value warm-up."""
from copy import deepcopy
from .retest import evaluate as retest_evaluate
from .rsi_slope import observe as rsi_observe, apply as rsi_apply
import math
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULTS = dict(atr_length=5, factor=3.0, brick_mode='Auto', manual_brick=12.8,
                use_adx=False, adx_threshold=20.0, adx_length=14, adx_smoothing=14, widening_window=2, rsi_slope_enabled=True, retest_enabled=False,retest_engulfing=True,retest_harami=True,retest_star=True)


def settings(payload):
    c = {key: payload.get(key, default) for key, default in DEFAULTS.items()}
    for key in ('atr_length', 'adx_length', 'adx_smoothing', 'widening_window'):
        raw = c[key]
        try:
            value = int(raw)
            if isinstance(raw, bool) or float(raw) != value or value < 1:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f'{key} must be a positive whole number.') from None
        c[key] = value
    for key, minimum in (('factor', 0.1), ('manual_brick', 0.00000001), ('adx_threshold', 0.0)):
        raw = c[key]
        try:
            value = float(raw)
            if isinstance(raw, bool) or not math.isfinite(value) or value < minimum:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f'{key} is outside the supplied Pine input range.') from None
        c[key] = value
    if c['adx_threshold'] > 100 or c['brick_mode'] not in ('Auto', 'Manual') or not isinstance(c['use_adx'], bool):
        raise ValueError('Choose Auto/Manual, a boolean ADX gate and an ADX threshold from 0 to 100.')
    if any(not isinstance(c[k],bool) for k in ('rsi_slope_enabled','retest_enabled','retest_engulfing','retest_harami','retest_star')):raise ValueError('Retest and pattern choices must be boolean checkboxes.')
    if c['retest_enabled'] and not any(c[k] for k in ('retest_engulfing','retest_harami','retest_star')):raise ValueError('Select at least one retest candlestick pattern.')
    if not 2 <= c['widening_window'] <= 100:
        raise ValueError('Widening window must be from 2 to 100 completed candles.')
    return c


def completed(candles):
    unique = {}
    for row in candles:
        if row.get('is_forming'):
            continue
        c = {key: row.get(key) for key in ('timestamp', 'open', 'high', 'low', 'close', 'volume')}
        if not all(isinstance(c[k], (int, float)) and not isinstance(c[k], bool) and math.isfinite(c[k]) for k in ('timestamp', 'open', 'high', 'low', 'close')):
            raise ValueError('Renko host candles must have finite timestamps and OHLC.')
        if min(c[k] for k in ('open', 'high', 'low', 'close')) <= 0 or c['low'] > min(c['open'], c['close']) or c['high'] < max(c['open'], c['close']):
            raise ValueError('Invalid Renko host candle OHLC.')
        if c['timestamp'] in unique and unique[c['timestamp']] != c:
            raise ValueError('Conflicting duplicate Renko host candles.')
        unique[c['timestamp']] = c
    return sorted(unique.values(), key=lambda c: c['timestamp'])


def rma(state, key, value, length):
    """ta.rma: skip na; seed with an SMA of length non-na observations."""
    s = state.setdefault(key, dict(count=0, total=0.0, value=None))
    if value is None:
        return s['value']
    if s['value'] is None:
        s['count'] += 1
        s['total'] += value
        if s['count'] == length:
            s['value'] = s['total'] / length
    else:
        alpha = 1.0 / length
        s['value'] = alpha * value + (1 - alpha) * s['value']
    return s['value']


def ema_setup(state, close, direction, allowed, window):
    # Pine ta.ema seeds with the first non-na source, then alpha=2/(length+1).
    for length in (10, 30):
        key = f'ema{length}'
        old = state.get(key)
        state[key] = close if old is None else (2.0 / (length + 1)) * close + (1 - 2.0 / (length + 1)) * old
    gap = state['ema10'] - state['ema30']
    gaps = (state.get('ema_gaps', []) + [gap])[-window:]
    state['ema_gaps'] = gaps
    bullish = direction < 0
    signed = gaps if bullish else [-g for g in gaps]
    aligned = gap > 0 if bullish else gap < 0
    price_ok = close > state['ema10'] if bullish else close < state['ema10']
    widening = len(signed) == window and all(g > 0 for g in signed) and all(a < b for a, b in zip(signed, signed[1:]))
    qualified = aligned and price_ok and widening and allowed
    setup = 'BULLISH' if bullish else 'BEARISH'
    entry = setup if qualified and state.get('ema_qualified') != setup else None
    # Re-arm only after the completed-candle setup ceases to qualify.
    state['ema_qualified'] = setup if qualified else None
    reason = 'QUALIFIED' if qualified else 'WAITING_ADX' if not allowed else 'WAITING_EMA_ALIGNMENT' if not aligned else 'WAITING_CLOSE' if not price_ok else 'WAITING_WIDENING'
    return dict(ema10=state['ema10'], ema30=state['ema30'], ema_gap=gap, ema_widening=widening,
                entry_qualified=qualified, entry_diagnostic=reason, entry_direction=entry,
                entry_buy_signal=entry == 'BULLISH', entry_sell_signal=entry == 'BEARISH')


def project_lifecycle(state, timestamp, entry_direction, reversal_direction, seconds=300, close=None, ema10=None, deadline='15:15'):
    """Historical signal projection, never evidence of an actual broker fill."""
    position = state.get('projected_position')
    event = None
    reason = None
    clock = datetime.fromtimestamp(timestamp, ZoneInfo('Asia/Kolkata'))
    closes = datetime.fromtimestamp(timestamp+seconds, ZoneInfo('Asia/Kolkata'))
    deadline_parts=tuple(map(int,deadline.split(':'))) if deadline else (24,0)
    cutoff = (clock.hour,clock.minute) >= deadline_parts
    deadline_at = clock.replace(hour=deadline_parts[0],minute=deadline_parts[1],second=0,microsecond=0).timestamp() if deadline else float('inf')
    overdue = deadline and position and datetime.fromtimestamp(position['entry_timestamp'],ZoneInfo('Asia/Kolkata')).date()<clock.date()
    if position and (timestamp+seconds >= deadline_at or overdue):
        event = 'BUY EXIT' if position['direction'] == 'BULLISH' else 'SELL EXIT'
        reason = 'TIMED_SQUARE_OFF_'+deadline.replace(':','')
        position = None
    elif position:
        adverse = close is not None and ema10 is not None and (close < ema10 if position['direction'] == 'BULLISH' else close > ema10)
        opposite = 'BEARISH' if position['direction'] == 'BULLISH' else 'BULLISH'
        if adverse or reversal_direction == opposite:
            event = 'BUY EXIT' if position['direction'] == 'BULLISH' else 'SELL EXIT'
            reason = 'EMA10_CONFIRMED_BREACH' if adverse else 'OPPOSITE_CONFIRMED_SUPERTREND'
            position = None
        # An exit consumes the candle; an active position ignores entry onsets.
    elif entry_direction and not cutoff and (closes.hour,closes.minute) < deadline_parts:
        position = dict(direction=entry_direction, entry_timestamp=timestamp)
        event = 'BUY' if entry_direction == 'BULLISH' else 'SELL'
        reason = 'CONFIRMED_EMA_QUALIFICATION'
    if event and event.endswith('EXIT'):
        state['ema_qualified'] = None  # Exit consumes this bar; a later flat-state setup can re-arm.
    state['projected_position'] = position
    return dict(lifecycle_event=event, lifecycle_reason=reason, lifecycle_event_at=(deadline_at if reason and reason.startswith('TIMED_') and not overdue else timestamp+seconds) if event else None, projected_position=deepcopy(position),
                lifecycle_scope='Historical completed-candle signal simulation; not broker fills.')


class Engine:
    def __init__(self, config=None, tick_size=0.05, state=None):
        self.config = settings(config or {})
        self.deadline = (config or {}).get('session_deadline','15:15')
        self.host_seconds = {'1 minute':60,'2 minutes':120,'3 minutes':180,'5 minutes':300,'10 minutes':600,'15 minutes':900,'30 minutes':1800,'1 hour':3600}.get((config or {}).get('timeframe'),300)
        if isinstance(tick_size, bool) or not math.isfinite(float(tick_size)) or float(tick_size) <= 0:
            raise ValueError('A positive verified host-symbol tick size is required.')
        self.tick_size = float(tick_size)
        self.state = deepcopy(state) if state is not None else dict(rc=None, ro=None, synthetic_atr=None, upper=None, lower=None, st=None, direction=1, previous=None, count=0)

    def update(self, candle):
        rows = completed([candle])
        if not rows:
            return None
        c = rows[0]
        s, cfg = self.state, self.config
        previous = s['previous']
        if previous and c['timestamp'] <= previous['timestamp']:
            raise ValueError('Feed each completed host candle exactly once in chronological order.')
        tr = max(c['high'] - c['low'], abs(c['high'] - previous['close']), abs(c['low'] - previous['close'])) if previous else c['high'] - c['low']
        host_atr = rma(s, 'host', tr, cfg['atr_length'])
        regime_atr = rma(s, 'regime', tr, 15)
        low_atr = rma(s, 'low_atr', tr, 9)
        ratio = host_atr / regime_atr if regime_atr is not None and regime_atr > 0 and host_atr is not None else None if regime_atr is not None and regime_atr > 0 else 1.0
        high_regime, low_regime = ratio is not None and ratio > 1.2, ratio is not None and ratio < 0.8
        effective = cfg['factor'] + (1.0 if high_regime else -0.5 if low_regime else 0.0)
        auto = host_atr * 1.5 if high_regime else low_atr * 0.7 if low_regime else host_atr
        auto = max(self.tick_size, auto) if auto is not None else None
        box = cfg['manual_brick'] if cfg['brick_mode'] == 'Manual' else auto
        if s['rc'] is None:
            s['rc'] = s['ro'] = c['close']
        previous_rc = s['rc']
        delta = c['close'] - previous_rc
        steps = math.floor(abs(delta) / box) if box is not None and box > 0 else 0
        if steps >= 1:
            s['ro'] = previous_rc
            s['rc'] += (1 if delta > 0 else -1 if delta < 0 else 0) * steps * box
        rh, rl = max(s['ro'], s['rc']), min(s['ro'], s['rc'])
        synthetic_tr = max(rh - rl, abs(rh - previous_rc), abs(rl - previous_rc))
        atr = synthetic_tr if s['synthetic_atr'] is None else s['synthetic_atr'] + (synthetic_tr - s['synthetic_atr']) / cfg['atr_length']
        midpoint = (rh + rl) / 2
        basic_upper, basic_lower = midpoint + effective * atr, midpoint - effective * atr
        pu, pl, pst, pd = s['upper'], s['lower'], s['st'], s['direction']
        upper = basic_upper if pu is None or basic_upper < pu or previous_rc > pu else pu
        lower = basic_lower if pl is None or basic_lower > pl or previous_rc < pl else pl
        direction = 1 if pst is None else (-1 if s['rc'] > upper else 1) if pst == pu else (1 if s['rc'] < lower else -1)
        st = lower if direction < 0 else upper
        # Chart-bar DMI, not synthetic-brick DMI. The first directional change is na.
        up = c['high'] - previous['high'] if previous else None
        down = previous['low'] - c['low'] if previous else None
        plus = up if up is not None and up > down and up > 0 else 0.0 if previous else None
        minus = down if down is not None and down > up and down > 0 else 0.0 if previous else None
        dtr = rma(s, 'dmi_tr', tr if previous else None, cfg['adx_length'])
        dp = rma(s, 'dmi_plus', plus, cfg['adx_length'])
        dm = rma(s, 'dmi_minus', minus, cfg['adx_length'])
        pdi = 100 * dp / dtr if dtr not in (None, 0) and dp is not None else s.get('plus_di')
        mdi = 100 * dm / dtr if dtr not in (None, 0) and dm is not None else s.get('minus_di')
        s.update(plus_di=pdi, minus_di=mdi)
        total = pdi + mdi if pdi is not None and mdi is not None else None
        dx = abs(pdi - mdi) / (1 if total == 0 else total) if total is not None else None
        adx_rma = rma(s, 'adx', dx, cfg['adx_smoothing'])
        adx = adx_rma * 100 if adx_rma is not None else None
        allowed = not cfg['use_adx'] or adx is not None and adx > cfg['adx_threshold']
        buy = allowed and direction < 0 and pd > 0
        sell = allowed and direction > 0 and pd < 0
        s.update(rc=s['rc'], ro=s['ro'], synthetic_atr=atr, upper=upper, lower=lower, st=st, direction=direction, previous=c, count=s['count'] + 1)
        previous_emas=(s.get('ema10'),s.get('ema30'))
        entry = ema_setup(s, c['close'], direction, allowed, cfg['widening_window'])
        if cfg['retest_enabled']:
            retest=retest_evaluate(s,c,previous,previous_emas,pd,direction,entry,allowed,{**cfg,'host_seconds':self.host_seconds})
            entry.update(retest)
            if retest['retest_signal']:
                entry.update(entry_direction=retest['retest_direction'],entry_qualified=True,entry_diagnostic='EMA10_RETEST_BOUNCE',entry_buy_signal=direction<0,entry_sell_signal=direction>0)
        rsi_apply(entry,s,rsi_observe(s,c['close']),'BULLISH' if direction<0 else 'BEARISH',cfg['rsi_slope_enabled'])
        projection = project_lifecycle(s, c['timestamp'], entry['entry_direction'], 'BULLISH' if buy else 'BEARISH' if sell else None, self.host_seconds,c['close'],entry['ema10'],self.deadline)
        if entry.get('retest_signal') and projection.get('lifecycle_event') in ('BUY','SELL'):projection['lifecycle_reason']='EMA10_RETEST_BOUNCE'
        return {**c, **entry, **projection, 'host_atr': host_atr, 'regime_atr': regime_atr, 'low_atr': low_atr, 'volatility_ratio': ratio, 'effective_factor': effective,
                'auto_box': auto, 'box': box, 'steps': steps, 'synthetic_open': s['ro'], 'synthetic_close': s['rc'], 'synthetic_tr': synthetic_tr,
                'synthetic_atr': atr, 'upper': upper, 'lower': lower, 'supertrend': st, 'pine_direction': direction,
                'direction': 'BULLISH' if direction < 0 else 'BEARISH', 'adx': adx, 'signal_allowed': allowed,
                'buy_signal': buy, 'sell_signal': sell, 'cross_direction': 'BULLISH' if buy else 'BEARISH' if sell else None}


def series(candles, config=None, tick_size=0.05):
    engine = Engine(config, tick_size)
    return [engine.update(c) for c in completed(candles)]
