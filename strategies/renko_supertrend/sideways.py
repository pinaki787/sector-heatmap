"""Quick losing-position range lock; no swing history, entry signal or order route."""
import math
from copy import deepcopy


def settings(payload):
    enabled=payload.get('sideways_enabled',False)
    if not isinstance(enabled,bool):raise ValueError('Sideways filter enable must be a boolean.')
    raw=payload.get('sideways_max_candles',3)
    try:n=float(raw)
    except (TypeError,ValueError):raise ValueError('Quick-loss window must be 1–10 whole host candles.')
    if isinstance(raw,bool) or not math.isfinite(n) or not n.is_integer() or not 1<=n<=10:
        raise ValueError('Quick-loss window must be 1–10 whole host candles.')
    return dict(sideways_enabled=enabled,sideways_max_candles=int(n))


def observe(exposure,entry_at,price,stamp,now,exit_at=None):
    result=deepcopy(exposure) if exposure else dict(entry_at=entry_at,high=None,low=None,first_tick_at=None,last_tick_at=None,ticks=0,basis='Underlying websocket LTP ticks strictly within actual position exposure; no pre-entry OHLC or swing levels.')
    # Exchange timestamps may have one-second precision. Never borrow a pre-fill tick.
    if not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0 or not isinstance(stamp,(int,float)) or not entry_at<=stamp<=now or now-stamp>15 or exit_at is not None and stamp>exit_at:
        return result
    result['high']=price if result['high'] is None else max(result['high'],price)
    result['low']=price if result['low'] is None else min(result['low'],price)
    if result['last_tick_at']!=stamp:result['ticks']+=1
    result['first_tick_at']=stamp if result['first_tick_at'] is None else min(result['first_tick_at'],stamp)
    result['last_tick_at']=stamp
    return result


def candle_count(entry_at,exit_at,seconds):
    if exit_at<entry_at:raise ValueError('Exit precedes actual entry.')
    return int(exit_at//seconds-entry_at//seconds)+1


def freeze(exposure,exit_at,realized,seconds,config,trade_id,underlying,cost_evidence=None):
    if not config.get('sideways_enabled') or not exposure:return None
    entry=exposure.get('entry_at')
    timing_known=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (entry,exit_at)) and exit_at>=entry
    count=candle_count(entry,exit_at,seconds) if timing_known else None
    if count is not None and count>config.get('sideways_max_candles',3):return None
    known=isinstance(realized,(int,float)) and not isinstance(realized,bool) and math.isfinite(realized)
    if known and realized>=0:return None
    high,low=exposure.get('high'),exposure.get('low')
    complete=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in (high,low)) and high>=low
    return dict(active=True,high=high if complete else None,low=low if complete else None,
                entry_at=entry,exit_at=exit_at,triggered_at=exit_at,host_candles=count,
                realized_pnl=realized if known else None,trade_id=trade_id,underlying=underlying,
                reason='QUICK_LOSING_POSITION_RANGE' if known else 'QUICK_CLOSE_NET_UNAVAILABLE',
                loss_confirmed=known,net_result_available=known,range_complete=complete,
                cost_evidence=deepcopy(cost_evidence),
                protection_basis='AFTER_ESTIMATED_COSTS' if known else 'CONSERVATIVE_UNKNOWN_NET',
                review_required=not complete or not timing_known,exposure=deepcopy(exposure),released_at=None,release_reason=None)


def breakout(lock,price,stamp,now):
    if not lock or not lock.get('active') or lock.get('review_required'):return None
    if not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0 or not isinstance(stamp,(int,float)) or not lock['triggered_at']<stamp<=now or now-stamp>15:return None
    if any(not isinstance(lock.get(k),(int,float)) or isinstance(lock.get(k),bool) or not math.isfinite(lock[k]) or lock[k]<=0 for k in ('high','low')):return None
    return 'BREAK_ABOVE_POSITION_HIGH' if price>lock['high'] else 'BREAK_BELOW_POSITION_LOW' if price<lock['low'] else None
