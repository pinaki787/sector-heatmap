"""Bounded exact-provider gap reconciliation; never fabricate empty candles."""
from copy import deepcopy
import time

def missing_events(confirmed,engine,assembler,symbol,kind,frame,stamp,price,now,max_bars=30):
    step=frame*60;bucket=int(stamp//step)*step
    previous=engine.last_time.get(kind)
    skipped=assembler.bucket is not None and bucket-assembler.bucket>step
    if previous is None:return []
    startup=assembler.bucket is None and bucket-previous>step
    if not skipped and not startup:return []
    count=int((bucket-previous)//step)-1
    if count<1:return []
    if count>max_bars:raise ValueError('Delta source gap exceeds bounded recovery; history reconciliation required')
    events=[]
    for at in range(int(previous+step),bucket,step):
        event=confirmed.confirm(dict(kind=kind,timestamp=at,close=price,symbol=symbol),symbol,frame,now=now,previous=previous)
        # Availability is when this REST confirmation was actually received.
        event=dict(event,available_at=max(now,time.time()))
        events.append(event);previous=at
    return events

def apply_recovered(events,engine,chart_source,submit,record):
    """Apply all validated history causally; historical entries are never submitted."""
    for event in events:
        prior=deepcopy(engine.position)
        chart_source.append(event,engine.config['timeframe'])
        actions=chart_source.decide(engine,event)
        entries={'BUY','OPEN_LONG','OPEN_SHORT'}
        if any(a['action'] in entries for a in actions):engine.position=prior
        for action in actions:
            if action['action'] in ('SELL','CLOSE_LONG','CLOSE_SHORT'):
                submit(action)  # Only an existing owned exit, never reverse entry.
        chart_source.append_bands(engine,event)
        record(dict(event=event,history_recovery=True,historical_entries_suppressed=True))
    if events:
        engine.entry_confirmation.clear();engine.pending_direction=None
        engine.band.consume_entry();engine.band.retest=None
        engine.entry_reset_at=events[-1]['available_at']
