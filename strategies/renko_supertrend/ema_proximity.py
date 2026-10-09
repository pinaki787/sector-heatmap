"""New entries only: absolute underlying distance from EMA10, scaled by completed ATR."""
import math


def settings(payload):
    enabled=payload.get('ema_proximity_enabled',False)
    mode=payload.get('ema_proximity_mode','ATR')
    raw=payload.get('ema_proximity_distance',.5)
    try:distance=float(raw)
    except (TypeError,ValueError):raise ValueError('EMA proximity distance must be positive.')
    if not isinstance(enabled,bool) or mode not in ('ATR','POINTS') or isinstance(raw,bool) or not math.isfinite(distance) or distance<=0:
        raise ValueError('Choose an EMA proximity checkbox, ATR/points basis and positive distance.')
    return dict(ema_proximity_enabled=enabled,ema_proximity_mode=mode,ema_proximity_distance=distance)


def check(config,price,ema10,confirmed_atr):
    if not config.get('ema_proximity_enabled'):return None
    c=settings(config)
    values=(price,ema10,confirmed_atr) if c['ema_proximity_mode']=='ATR' else (price,ema10)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values):
        raise ValueError('Valid EMA10 and completed host ATR required for proximity.')
    maximum=c['ema_proximity_distance']*(confirmed_atr if c['ema_proximity_mode']=='ATR' else 1)
    distance=abs(price-ema10)
    distance_atr=distance/confirmed_atr if isinstance(confirmed_atr,(int,float)) and not isinstance(confirmed_atr,bool) and math.isfinite(confirmed_atr) and confirmed_atr>0 else None
    # Permit only floating-point roundoff at the inclusive configured boundary.
    if distance>maximum and not math.isclose(distance,maximum,rel_tol=1e-12,abs_tol=1e-12):
        normalized=f' ({distance_atr:.3f} completed ATR; limit {c["ema_proximity_distance"]:g} ATR)' if c['ema_proximity_mode']=='ATR' else ''
        raise ValueError(f'Entry too far from EMA{config.get("ema_fast_length",10)}: {distance:.2f} underlying points; maximum {maximum:.2f}.'+normalized)
    return dict(price=price,ema10=ema10,distance_points=distance,max_points=maximum,
                mode=c['ema_proximity_mode'],confirmed_atr=confirmed_atr,distance_atr=distance_atr,
                configured_limit=c['ema_proximity_distance'],scope='NEW_ENTRY_ONLY',
                formula='abs(fresh underlying price - live host EMA10) / completed host ATR')
