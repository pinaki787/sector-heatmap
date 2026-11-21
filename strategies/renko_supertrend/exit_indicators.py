"""Opt-in completed-candle exit criteria independent of entry selections."""
DEFAULTS = dict(renko_brick_exit_enabled=False, supertrend_exit_enabled=True, ema_slow_exit_enabled=False,
                rsi_exit_enabled=False, ema_widening_exit_enabled=False,
                adx_exit_enabled=False, market_structure_exit_enabled=False)

def settings(payload):
    result={key:payload.get(key,value) for key,value in DEFAULTS.items()}
    if any(not isinstance(value,bool) for value in result.values()):
        raise ValueError('Exit indicator switches must be booleans.')
    return result

def sma_reason(config, event, direction):
    length = config.get('sma_length', 5)
    close, average = event.get('close'), event.get('sma')
    if not config.get('sma_exit_enabled') or event.get('sma_length') != length or close is None or average is None:
        return None
    adverse = close < average if direction == 'BULLISH' else close > average
    return f'SMA{length}_CONFIRMED_BREACH' if adverse else None


def reason(config,sig,direction):
    from .indicator_families import apply
    config=apply(config)
    # Any selected exit can close a position; unselected entry rules cannot.
    opposite='BEARISH' if direction=='BULLISH' else 'BULLISH'
    if sig.get('is_forming') or sig.get('provisional'):return None
    if config.get('sma_exit_enabled'):
        if config.get('strategy_basis') == 'RENKO' and not sig.get('has_completed_brick'):
            return None
        for event in sig.get('brick_exit_events') or [sig]:
            exit_reason = sma_reason(config, event, direction)
            if exit_reason:
                return exit_reason
        if config.get('strategy_mode') == 'SIMPLE_BRICK':
            return None
    if config.get('strategy_mode')=='SIMPLE_BRICK':
        if not sig.get('has_completed_brick'):return None
        events=sig.get('brick_exit_events') or [sig]
        return 'OPPOSITE_RENKO_BRICK_CLOSE' if any(e.get('brick_direction')==opposite for e in events) else None
    if config.get('strategy_basis')=='RENKO':
        for event in sig.get('brick_exit_events',[]):
            if config.get('supertrend_exit_enabled',True) and event.get('raw_supertrend_cross_direction')==opposite:return 'RENKO_ST_EXIT'
            if config.get('renko_brick_exit_enabled') and event.get('brick_direction')==opposite:return 'OPPOSITE_RENKO_BRICK_CLOSE'
        if not sig.get('has_completed_brick'):return None
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
