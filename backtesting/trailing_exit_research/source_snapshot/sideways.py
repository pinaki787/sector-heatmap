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


def freeze(exposure,exit_at,realized,seconds,config,trade_id,underlying):
    if not exposure:return None
    count=candle_count(exposure['entry_at'],exit_at,seconds)
    if not config.get('sideways_enabled') or not isinstance(realized,(int,float)) or not math.isfinite(realized) or realized>=0 or count>config.get('sideways_max_candles',3) or exposure.get('high') is None or exposure.get('low') is None:return None
    return dict(active=True,high=exposure['high'],low=exposure['low'],entry_at=exposure['entry_at'],exit_at=exit_at,triggered_at=exit_at,host_candles=count,realized_pnl=realized,trade_id=trade_id,underlying=underlying,reason='QUICK_LOSING_POSITION_RANGE',exposure=deepcopy(exposure),released_at=None,release_reason=None)


def breakout(lock,price,stamp,now):
    if not lock or not lock.get('active'):return None
    if not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0 or not isinstance(stamp,(int,float)) or not lock['triggered_at']<stamp<=now or now-stamp>15:return None
    return 'BREAK_ABOVE_POSITION_HIGH' if price>lock['high'] else 'BREAK_BELOW_POSITION_LOW' if price<lock['low'] else None
