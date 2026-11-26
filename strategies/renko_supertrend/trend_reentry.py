"""Promote a fresh completed trend brick after Start or an actual exit."""
def apply(state, signal, *, allow_pending_entry=False):
    config=state.get('config') or {}
    if config.get('strategy_basis')!='RENKO' or not config.get('trend_reentry_enabled',True) or state.get('position') or (state.get('pending') and not allow_pending_entry):
        return signal
    if signal.get('provisional') or not signal.get('has_completed_brick') or not signal.get('trend_reentry_direction'):
        return signal
    side=signal['trend_reentry_direction']
    if signal.get('direction')!=side or signal.get('brick_direction')!=side:
        return signal
    if not signal.get('timestamp',0)>state.get('last_exit_bar',0):
        return signal
    event=signal.get('market_event_at',signal.get('source_timestamp',signal.get('timestamp',0)))
    exits=[x.get('filled_at',x.get('updated_at',0)) for x in state.get('order_history',[])
           if x.get('run_id')==state.get('run_id') and x.get('side')=='SELL' and x.get('status')=='FILLED' and not x.get('is_entry')]
    recorded=state.get('trend_reentry_after',0) if state.get('trend_reentry_run_id')==state.get('run_id') else 0
    boundary=max([recorded,state.get('eligible_since',0),state.get('started_at',0),*exits])
    # No invented chronology when exit timing is unavailable.
    if not boundary or event<=boundary:
        return signal
    return {**signal,'entry_qualified':True,'entry_direction':side,'cross_direction':side,
            'entry_buy_signal':side=='BULLISH','entry_sell_signal':side=='BEARISH',
            'entry_diagnostic':'FRESH_TREND_BRICK_REENTRY','trend_reentry':True}
