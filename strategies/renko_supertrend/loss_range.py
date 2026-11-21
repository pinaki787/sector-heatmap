"""Post-loss entry lock using completed Renko bodies, never forming prices."""
import math
from copy import deepcopy

REVISION = 'completed-renko-loss-range-v1'

def settings(payload):
    enabled=payload.get('renko_loss_range_enabled',True)
    if not isinstance(enabled,bool):raise ValueError('Renko loss-range protection must be a boolean.')
    raw=payload.get('renko_loss_range_buffer',0)
    try:value=float(raw)
    except (ValueError,TypeError):raise ValueError('Renko breakout buffer must be 0–5 whole bricks.')
    if isinstance(raw,bool) or not math.isfinite(value) or not value.is_integer() or not 0<=value<=5:
        raise ValueError('Renko breakout buffer must be 0–5 whole bricks.')
    return dict(renko_loss_range_enabled=enabled,renko_loss_range_buffer=int(value))

def enabled(config):
    return config.get('strategy_basis')=='RENKO' and config.get('renko_loss_range_enabled',False)

def finite(value):
    return isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value)

def bricks(signal,seconds):
    if not signal or signal.get('provisional') or signal.get('is_forming') or not signal.get('has_completed_brick'):return []
    rows=signal.get('brick_events') or [signal]
    result=[]
    for row in rows:
        opened,closed=row.get('open'),row.get('close')
        stamp=row.get('market_event_at',signal.get('market_event_at'))
        if stamp is None:stamp=signal.get('timestamp',0)+seconds
        logical=row.get('timestamp',signal.get('timestamp'))
        if not all(finite(v) for v in (opened,closed,stamp,logical)) or min(opened,closed)<=0 or opened==closed:continue
        result.append(dict(open=opened,close=closed,high=max(opened,closed),low=min(opened,closed),
                           event_at=stamp,timestamp=logical,direction='BULLISH' if closed>opened else 'BEARISH',
                           box=row.get('box',signal.get('box',abs(closed-opened)))))
    return result

def observe(position,signal,config,now,seconds,seed=False):
    if not position or not enabled(config):return
    exposure=deepcopy(position.get('renko_brick_range')) or dict(high=None,low=None,count=0,last_key=None,opposite=False)
    boundary=position.get('first_fill_confirmed_at',position.get('opened_at',now))
    rows=bricks(signal,seconds)
    if seed:rows=rows[-1:]
    for row in rows:
        key=[row['event_at'],row['timestamp'],row['open'],row['close']]
        if key==exposure.get('last_key') or row['event_at']>now:continue
        if not seed and (row['event_at']<boundary or row['timestamp']<=exposure.get('last_timestamp',-1)):continue
        exposure.update(high=max(exposure['high'],row['high']) if exposure['high'] is not None else row['high'],
                        low=min(exposure['low'],row['low']) if exposure['low'] is not None else row['low'],
                        count=exposure['count']+1,last_key=key,last_timestamp=row['timestamp'],
                        last_event_at=row['event_at'],box=row['box'],
                        opposite=exposure['opposite'] or (not seed and row['direction']!=position.get('direction')))
    position['renko_brick_range']=exposure

def freeze(position,signal,config,net,now,seconds,run_id,trade_id):
    if not enabled(config):return None
    observe(position,signal,config,now,seconds)
    evidence=position.get('renko_brick_range') or {}
    if not evidence.get('opposite') or not evidence.get('count'):return None
    known=finite(net)
    if known and net>=0:return None
    return dict(active=True,revision=REVISION,underlying=config['underlying'],run_id=run_id,trade_id=trade_id,
                high=evidence['high'],low=evidence['low'],box=evidence['box'],buffer_bricks=config.get('renko_loss_range_buffer',0),
                brick_count=evidence['count'],triggered_at=now,exit_brick_at=evidence['last_timestamp'],
                loss_confirmed=known,net_result_available=known,realized_net=net if known else None,
                reason='REVERSAL_LOSS' if known else 'REVERSAL_NET_UNAVAILABLE',
                evidence=deepcopy(evidence))

def breakout(lock,signal,direction,now,seconds):
    if not lock or not lock.get('active') or direction not in ('BULLISH','BEARISH'):return None
    # Require the latest completed brick itself, with matching entry direction.
    rows=bricks(signal,seconds)
    if not rows:return None
    row=rows[-1]
    if row['direction']!=direction or row['event_at']<=lock['triggered_at'] or row['timestamp']<=lock['exit_brick_at']:return None
    freshness=15 if signal.get('confirmation_basis')=='ORDERED_LIVE_PRICE' else seconds
    if not 0<=now-row['event_at']<=freshness:return None
    box=lock.get('box');buffer=lock.get('buffer_bricks',0)
    if not finite(box) or box<=0:return None
    if direction=='BULLISH' and row['close']>lock['high']+buffer*box:return dict(reason='COMPLETED_BRICK_ABOVE_RANGE',**row)
    if direction=='BEARISH' and row['close']<lock['low']-buffer*box:return dict(reason='COMPLETED_BRICK_BELOW_RANGE',**row)
    return None
