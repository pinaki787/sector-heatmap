"""Independent entry indicators; defaults preserve the existing combined setup."""
DEFAULTS = dict(supertrend_enabled=True, ema_fast_enabled=True, ema_slow_enabled=True,
                ema_widening_enabled=True, ema_fast_length=10, ema_slow_length=30, rsi_slope_length=14)

def validate(c):
    for key in ('supertrend_enabled','ema_fast_enabled','ema_slow_enabled','ema_widening_enabled'):
        if not isinstance(c[key],bool):raise ValueError('Indicator switches must be booleans.')
    for key in ('ema_fast_length','ema_slow_length','rsi_slope_length'):
        raw=c[key]
        try:value=int(raw)
        except (ValueError,TypeError,OverflowError):raise ValueError('EMA periods must be whole numbers from 1 to 1000.')
        if isinstance(raw,bool) or float(raw)!=value or not 1<=value<=1000:raise ValueError('EMA periods must be whole numbers from 1 to 1000.')
        c[key]=value
    if c['ema_widening_enabled'] and c['ema_fast_length']>=c['ema_slow_length']:raise ValueError('EMA widening requires the first EMA period to be shorter than the second.')
    if c.get('retest_enabled') and (not c['ema_fast_enabled'] or c['ema_fast_length']!=10 or not c['supertrend_enabled']):raise ValueError('EMA10 retest requires EMA period 10 and Supertrend.')

def qualify(c, close, fast, slow, direction, allowed, widening, reversal, rsi):
    # Every selected entry indicator must agree. Disabled values never gate entry.
    if not c['supertrend_enabled']:
        selected=[v for enabled,v in ((c['ema_fast_enabled'],fast),(c['ema_slow_enabled'],slow)) if enabled]
        if selected:
            direction=-1 if all(close>v for v in selected) else 1 if all(close<v for v in selected) else 0
        elif c['ema_widening_enabled']:
            direction=-1 if fast>slow else 1 if fast<slow else 0
        else:
            slope=(rsi or {}).get('rsi14_slope')
            direction=-1 if slope is not None and slope>0 else 1 if slope is not None and slope<0 else 0
    if not any(c[k] for k in ('supertrend_enabled','ema_fast_enabled','ema_slow_enabled','ema_widening_enabled','rsi_slope_enabled')):return 0,False,'NO_DIRECTIONAL_INDICATOR'
    if not allowed:return direction,False,'WAITING_ADX'
    if direction==0:return direction,False,'WAITING_SELECTED_ALIGNMENT'
    bullish=direction<0
    if c['ema_fast_enabled'] and not (close>fast if bullish else close<fast):return direction,False,'WAITING_CLOSE'
    if c['ema_slow_enabled'] and not (close>slow if bullish else close<slow):return direction,False,'WAITING_EMA_ALIGNMENT'
    if c['ema_fast_enabled'] and c['ema_slow_enabled'] and not (fast>slow if bullish else fast<slow):return direction,False,'WAITING_EMA_ALIGNMENT'
    if c['ema_widening_enabled'] and not widening:return direction,False,'WAITING_WIDENING'
    if c['supertrend_enabled'] and not c['ema_fast_enabled'] and not c['ema_slow_enabled'] and not c['ema_widening_enabled']:
        if reversal != ('BULLISH' if bullish else 'BEARISH'):return direction,False,'WAITING_SUPERTREND_REVERSAL'
    return direction,True,'QUALIFIED'
