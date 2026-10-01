"""EMA Cloud completed-close conditions; identical warm-up and deduplication to the dashboard."""
import math


def series(candles, fast=10, slow=30, exit_period=None):
    if isinstance(fast, bool) or isinstance(slow, bool) or not isinstance(fast, int) or not isinstance(slow, int) or not 1 <= fast < slow <= 100:
        raise ValueError('Use integer periods: 1 <= fast < slow <= 100.')
    exit_period = fast if exit_period is None else exit_period
    if isinstance(exit_period, bool) or not isinstance(exit_period, int) or not 1 <= exit_period <= 100:
        raise ValueError("Exit EMA must be a whole number from 1 to 100.")
    unique = {}
    for candle in candles:
        if candle.get('is_forming'):
            continue
        c = dict(candle)
        if not all(isinstance(c.get(k), (int, float)) and math.isfinite(c[k]) for k in ('timestamp', 'open', 'high', 'low', 'close')):
            raise ValueError('Non-finite or missing candle data.')
        if min(c[k] for k in ('open', 'high', 'low', 'close')) <= 0 or c['low'] > min(c['open'], c['close']) or c['high'] < max(c['open'], c['close']):
            raise ValueError('Invalid candle OHLC.')
        previous = unique.get(c['timestamp'])
        if previous and any(previous.get(k) != c.get(k) for k in ('open', 'high', 'low', 'close', 'volume')):
            raise ValueError('Conflicting duplicate broker candles.')
        unique[c['timestamp']] = c
    result, f, s, e = [], None, None, None
    for i, c in enumerate(sorted(unique.values(), key=lambda c: c['timestamp'])):
        f = c['close'] if f is None else f + 2 / (fast + 1) * (c['close'] - f)
        s = c['close'] if s is None else s + 2 / (slow + 1) * (c['close'] - s)
        e = c["close"] if e is None else e + 2 / (exit_period + 1) * (c["close"] - e)
        direction = None
        if i >= max(slow, exit_period) * 3:
            if c['close'] > f:
                direction = 'BULLISH'
            elif c['close'] < f:
                direction = 'BEARISH'
        result.append({**c, 'fast': f, 'slow': s, 'exit': e, 'direction': direction})
    return result


def exit_on_close(candle, direction):
    """Equality and wicks do not exit: only completed close versus signal EMA."""
    if candle.get('is_forming'):
        return False
    return candle['close'] < candle.get('exit', candle['fast']) if direction == 'BULLISH' else candle['close'] > candle.get('exit', candle['fast'])


def rsi_sma_series(candles, rsi_length=14, sma_length=14, ma_type="SMA"):
    """Wilder RSI and a simple moving average of RSI; completed bars only."""
    for period in (rsi_length, sma_length):
        if isinstance(period, bool) or not isinstance(period, int) or not 1 <= period <= 100:
            raise ValueError('Use integer RSI and SMA periods from 1 to 100.')
    if ma_type not in ('SMA','EMA'):
        raise ValueError('Choose SMA or EMA for RSI smoothing.')
    ema_value = None
    rows = series(candles)  # Retain the existing OHLC/duplicate/forming validation.
    gain = loss = 0.0
    values = []
    result = []
    for i, candle in enumerate(rows):
        rsi = sma = None
        if i:
            delta = candle['close'] - rows[i-1]['close']
            up, down = max(delta, 0.0), max(-delta, 0.0)
            if i <= rsi_length:
                gain += up / rsi_length
                loss += down / rsi_length
            else:
                gain = (gain * (rsi_length-1) + up) / rsi_length
                loss = (loss * (rsi_length-1) + down) / rsi_length
            if i >= rsi_length:
                rsi = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
                values.append(rsi)
                if ma_type == 'EMA':
                    ema_value = rsi if ema_value is None else ema_value + 2/(sma_length+1)*(rsi-ema_value)
                    sma = ema_value
                elif len(values) >= sma_length:
                    sma = sum(values[-sma_length:]) / sma_length
        direction = None
        if sma is not None:
            direction = 'BULLISH' if rsi > sma else 'BEARISH' if rsi < sma else None
        prior = result[-1] if result else {}
        cross = rsi_cross(prior.get('rsi'),prior.get('rsi_ma'),rsi,sma)
        result.append({**candle, 'rsi': rsi, 'rsi_sma': sma, 'rsi_ma': sma, 'ma_type':ma_type, 'direction': direction, 'cross_direction':cross})
    return result


def rsi_cross(previous_rsi,previous_ma,rsi,ma):
    if any(v is None for v in (previous_rsi,previous_ma,rsi,ma)):
        return None
    if previous_rsi <= previous_ma and rsi > ma:return 'BULLISH'
    if previous_rsi >= previous_ma and rsi < ma:return 'BEARISH'
    return None


def rsi_exit_on_close(candle, direction):
    if candle.get('is_forming') or candle.get('rsi') is None or candle.get('rsi_sma') is None:
        return False
    return candle.get('cross_direction') == ('BEARISH' if direction == 'BULLISH' else 'BULLISH')
