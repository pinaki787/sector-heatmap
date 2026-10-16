"""Durable, run-bound reporting from execution evidence; never creates a fill."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math


def timestamp(value):
    if isinstance(value,(int,float)) and math.isfinite(value):return float(value)
    if isinstance(value,str):
        try:return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
        except ValueError:pass
    return None


def identity(state):return state.get('run_id') or state.get('run_started_at') or state.get('started_at')


def audit(snapshot,previous=None,observed_at=None):
    """Merge evidence for one exact run, retaining rows omitted by later snapshots."""
    state=snapshot.get('runner',snapshot);run=identity(state)
    old=previous or {}
    if old.get('run_id')!=run:old={}
    start=timestamp(state.get('run_started_at') or state.get('started_at'))
    rows=state.get('trade_history') or state.get('position_history') or []
    if not rows and state.get('order_history'):
        from strategies.ema_crossover.history import position_history
        rows=position_history(state['order_history'])
    trades={r['audit_id']:deepcopy(r) for r in old.get('trades',[])}
    unassigned=0
    for row in rows:
        owners={r.get('run_id') for r in row.get('orders',[]) if r.get('run_id')}
        if row.get('run_id'):owners.add(row['run_id'])
        entered=timestamp(row.get('entry_time') or row.get('opened_at'))
        if owners:
            belongs=run is not None and owners=={run}
        else:
            # Legacy attribution requires a recorded start and confirmed fill time;
            # undated or unfilled rows are retained by the native journal only.
            belongs=start is not None and entered is not None and entered>=start
        if not belongs:unassigned+=1;continue
        key=row.get('trade_id') or row.get('lifecycle_id')
        if not key:
            key=hashlib.sha256(json.dumps([row.get('contract'),row.get('entry_order_ids'),entered],sort_keys=True).encode()).hexdigest()
        trades[str(key)]={**deepcopy(row),'audit_id':str(key)}
    events={r['audit_id']:deepcopy(r) for r in old.get('events',[])}
    for event in state.get('events',[]):
        at=timestamp(event.get('at') or event.get('timestamp'))
        if event.get('run_id'):
            if event['run_id']!=run:continue
        elif start is None or at is None or at<start:continue
        key=hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
        events[key]={**deepcopy(event),'audit_id':key}
    return dict(schema_version=1,run_id=run,started_at=start,observed_at=observed_at,
                trades=list(trades.values()),events=list(events.values()),unassigned_rows=unassigned,
                attribution='Explicit run ownership, or confirmed fill time after the recorded legacy run start. Missing evidence remains unknown.')


def attach(snapshot,previous=None,observed_at=None):
    """Keep the native output intact and add the job's isolated audit view."""
    output=deepcopy(snapshot)
    states=output.get('runner_outputs')
    if states is not None:
        prior={r.get('run_id'):r for r in (previous or {}).get('job_audits',[])}
        output['job_audits']=[audit(s,prior.get(identity(s)),observed_at) for s in states]
    else:output['job_audit']=audit(output,(previous or {}).get('job_audit'),observed_at)
    return output
