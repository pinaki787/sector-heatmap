"""Opt-in completed-candle exit criteria independent of entry selections."""
DEFAULTS = dict(supertrend_exit_enabled=True, ema_slow_exit_enabled=False,
                rsi_exit_enabled=False, ema_widening_exit_enabled=False,
                adx_exit_enabled=False, market_structure_exit_enabled=False)

def settings(payload):
    result={key:payload.get(key,value) for key,value in DEFAULTS.items()}
    if any(not isinstance(value,bool) for value in result.values()):
        raise ValueError('Exit indicator switches must be booleans.')
    return result

def reason(config,sig,direction):
    # Any selected exit can close a position; unselected entry rules cannot.
    opposite='BEARISH' if direction=='BULLISH' else 'BULLISH'
    if sig.get('is_forming'):return None
    if config.get('supertrend_exit_enabled',True) and sig.get('supertrend_cross_direction')==opposite:
        return 'RENKO_ST_EXIT'
    close=sig.get('close');slow=sig.get('ema30')
    if config.get('ema_slow_exit_enabled',False) and close is not None and slow is not None and (close<slow if direction=='BULLISH' else close>slow):
        return 'EMA'+str(config.get('ema_slow_length',30))+'_CONFIRMED_BREACH'
    slope=sig.get('rsi14_slope')
    if config.get('rsi_exit_enabled',False) and slope is not None and (slope<0 if direction=='BULLISH' else slope>0):
        return 'RSI_OPPOSING_SLOPE'
    gap=sig.get('ema_gap');previous=sig.get('exit_previous_ema_gap')
    if config.get('ema_widening_exit_enabled',False) and gap is not None and previous is not None and abs(gap)<abs(previous):
        return 'EMA_GAP_CONTRACTION'
    adx=sig.get('adx')
    if config.get('adx_exit_enabled',False) and adx is not None and adx<config.get('adx_threshold',25):
        return 'ADX_BELOW_THRESHOLD'
    structure=sig.get('exit_market_structure') or {}
    if config.get('market_structure_exit_enabled',False) and structure.get('state')==('BEARISH_LH_LL' if direction=='BULLISH' else 'BULLISH_HH_HL'):
        return 'OPPOSING_CONFIRMED_SWINGS'
    return None
