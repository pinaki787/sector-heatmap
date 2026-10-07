"""Optional completed-candle EMA10 retest with matching pattern confirmation."""
from .candle_patterns import matches

def evaluate(state,candle,previous,previous_emas,previous_direction,direction,entry,allowed,config=None):
    bullish=direction<0;side='BULLISH' if bullish else 'BEARISH'
    before10,before30=previous_emas
    aligned=entry['ema10']>entry['ema30'] if bullish else entry['ema10']<entry['ema30']
    established=previous is not None and previous_direction==direction and before10 is not None and before30 is not None and (before10>before30 if bullish else before10<before30)
    seconds=(config or {}).get('host_seconds')
    if previous and seconds and candle['timestamp']-previous['timestamp']!=seconds:
        state.update(retest_ready=False,retest_touch=None,retest_bars=[])
    ready=state.get('retest_direction')==side and state.get('retest_ready',False)
    pending=state.get('retest_touch') if state.get('retest_direction')==side and established and aligned else None
    touched=established and candle['low']<=before10<=candle['high']
    if pending:
        pending={**pending,'age':pending['age']+1}
        if pending['age']>2:pending=None
    if established and aligned and ready and touched:
        pending=dict(timestamp=candle['timestamp'],reference_ema10=before10,age=0)
        ready=False
    pattern_rows=(state.get('retest_bars',[])+[dict(candle)])[-3:]
    patterns=matches(pattern_rows,bullish,config or {})
    if pending:patterns=[p for p in patterns if pending['age']<(3 if 'STAR' in p else 2)]
    bounce=(candle['close']>entry['ema10'] and candle['close']>candle['open']) if bullish else (candle['close']<entry['ema10'] and candle['close']<candle['open'])
    qualifies=bool(established and aligned and pending and bounce and patterns and allowed)
    evidence=dict(pending) if pending else None
    # A matching but gated pattern is consumed, not replayed after ADX changes.
    if pending and bounce and patterns:pending=None
    separated=candle['low']>max(before10,entry['ema10']) if bullish and before10 is not None else candle['high']<min(before10,entry['ema10']) if before10 is not None else False
    if not aligned or not established:pending=None
    state.update(retest_direction=side if aligned else None,retest_touch=pending,retest_bars=pattern_rows,
                 retest_ready=bool(aligned and separated and not pending) if touched or not established or qualifies else bool(aligned and not pending and (ready or separated)))
    return dict(retest_signal=qualifies,retest_ready=state['retest_ready'],retest_touched=bool(touched),
                retest_reference_ema10=evidence['reference_ema10'] if evidence else before10,retest_touch_evidence=evidence,
                retest_bounce=bool(bounce),retest_patterns=patterns,retest_pattern_bars=pattern_rows if qualifies else [],retest_direction=side if qualifies else None)
