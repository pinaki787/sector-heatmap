"""Transient pre-submission quote recovery; never retries an uncertain order."""
import copy
try:from .manual_entry import restore_unsubmitted,clear_entry_signal
except ImportError:from manual_entry import restore_unsubmitted,clear_entry_signal

QUOTE_UNAVAILABLE='Fresh executable Delta backend quote required.'

def clear_entries(engine):
    clear_entry_signal(engine)

def defer_quote(engine,executor,action,error,now):
    if str(error)!=QUOTE_UNAVAILABLE:raise error
    restore_unsubmitted(engine,executor,action)
    closing=action.get('action') in ('SELL','CLOSE_LONG','CLOSE_SHORT')
    owned=executor.state.get('position')
    if closing and owned and owned.get('symbol')==(action.get('position') or {}).get('symbol'):
        engine.quote_exit_pending=copy.deepcopy(action)
    status=dict(state='WAITING_FOR_FRESH_QUOTE',entries_blocked=True,at=now,
                symbol=(action.get('position') or {}).get('symbol'),
                retained_exit=bool(getattr(engine,'quote_exit_pending',None)),orders_submitted=0)
    executor.state['quote_recovery']=status
    if closing and getattr(engine,'quote_exit_pending',None):
        executor.state['quote_recovery_exit']=copy.deepcopy(engine.quote_exit_pending)
    executor.save()
    return dict(deferred=True,reason=status['state'],orders_submitted=0)

def quote_recovered(executor,now):
    previous=executor.state.get('quote_recovery')
    if previous and previous.get('entries_blocked'):
        executor.state['quote_recovery']=dict(previous,state='FEED_RECOVERED',entries_blocked=False,recovered_at=now)
        executor.save()

def clear_retained_exit(engine,executor):
    engine.quote_exit_pending=None
    if executor.state.pop('quote_recovery_exit',None) is not None:executor.save()

def retry_exit(engine,executor,submit):
    action=getattr(engine,'quote_exit_pending',None)
    if not action or executor.state.get('pending'):return None
    owned=executor.state.get('position')
    expected=action.get('position') or {}
    if not owned or owned.get('symbol')!=expected.get('symbol') or owned.get('side')!=expected.get('side'):
        clear_retained_exit(engine,executor);return None
    action=copy.deepcopy(action);action['position']=dict(owned)
    result=submit(action)
    if result and not result.get('deferred'):clear_retained_exit(engine,executor)
    return result

def refresh_quote(executor,broker,symbol,now):
    status=executor.state.get('quote_recovery') or {}
    if not status.get('entries_blocked'):return True
    try:broker.quote(symbol)
    except ValueError as error:
        if str(error)!=QUOTE_UNAVAILABLE:raise
        if now>=status.get('next_retry',0):
            broker.subscribe_all()
            attempts=status.get('attempts',0)+1
            status.update(attempts=attempts,next_retry=now+min(60,10*attempts))
            executor.state['quote_recovery']=status;executor.save()
        return False
    quote_recovered(executor,now)
    return True
