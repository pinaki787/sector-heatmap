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
    momentum=payload.get('ema_momentum_enabled',False)
    if not isinstance(momentum,bool):raise ValueError('Momentum allowance must be a boolean.')
    if momentum and (not enabled or mode!='ATR' or distance!=.5):
        raise ValueError('Momentum allowance requires EMA proximity ON with the baseline 0.5 ATR limit.')
    if momentum and payload.get('intrabar_entries',False):raise ValueError('Momentum allowance requires completed-candle entries; disable intrabar entries.')
    return dict(ema_proximity_enabled=enabled,ema_proximity_mode=mode,ema_proximity_distance=distance,ema_momentum_enabled=momentum)


def check(config,price,ema10,confirmed_atr,signal=None,direction=None):
    if not config.get('ema_proximity_enabled'):return None
    c=settings(config)
    values=(price,ema10,confirmed_atr) if c['ema_proximity_mode']=='ATR' else (price,ema10)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values):
        raise ValueError('Valid EMA10 and completed host ATR required for proximity.')
    maximum=c['ema_proximity_distance']*(confirmed_atr if c['ema_proximity_mode']=='ATR' else 1)
    path='BASELINE'
    if c['ema_momentum_enabled']:
        # All automatic entries require a completed event in this policy. A
        # continuation/rearm is not the first qualification of a new episode.
        sig=signal or {}
        if sig.get('provisional') or sig.get('is_forming'):
            raise ValueError('Momentum policy requires a completed candle; intrabar entry blocked.')
        if sig.get('retest_signal'):
            path='RETEST'
        else:
            momentum_signal(sig,direction)
            slow=sig.get('preflight_ema30',sig['ema30'])
            aligned=price>ema10>slow if direction=='BULLISH' else price<ema10<slow
            if not aligned:raise ValueError('Fresh momentum price/EMAs no longer retain directional alignment.')
            advance=(price-sig['close'])*(1 if direction=='BULLISH' else -1)
            if advance>.25*confirmed_atr and not math.isclose(advance,.25*confirmed_atr,rel_tol=1e-12,abs_tol=1e-12):
                raise ValueError('Momentum entry chased beyond signal close: maximum 0.25 completed ATR.')
            maximum=1.5*confirmed_atr
            path='MOMENTUM_FIRST_QUALIFICATION'
    distance=abs(price-ema10)
    distance_atr=distance/confirmed_atr if isinstance(confirmed_atr,(int,float)) and not isinstance(confirmed_atr,bool) and math.isfinite(confirmed_atr) and confirmed_atr>0 else None
    # Permit only floating-point roundoff at the inclusive configured boundary.
    if distance>maximum and not math.isclose(distance,maximum,rel_tol=1e-12,abs_tol=1e-12):
        normalized=f' ({distance_atr:.2f} completed ATR; limit {maximum/confirmed_atr:g} ATR)' if c['ema_proximity_mode']=='ATR' else ''
        raise ValueError(f'Entry too far from EMA{config.get("ema_fast_length",10)}: {distance:.2f} underlying points; maximum {maximum:.2f}.'+normalized)
    return dict(entry_path=path,momentum_revision=REVISION,signal_timestamp=(signal or {}).get('timestamp'),signal_close=(signal or {}).get('close'),max_advance_atr=.25 if path=='MOMENTUM_FIRST_QUALIFICATION' else None,price=price,ema10=ema10,distance_points=distance,max_points=maximum,
                mode=c['ema_proximity_mode'],confirmed_atr=confirmed_atr,distance_atr=distance_atr,
                configured_limit=maximum/confirmed_atr if c['ema_proximity_mode']=='ATR' else c['ema_proximity_distance'],scope='NEW_ENTRY_ONLY',
                formula='abs(fresh underlying price - live host EMA10) / completed host ATR')


REVISION='split-proximity-momentum-v1'

def momentum_signal(sig,direction):
    """Confirm the first directional qualification; no mutable retry allowance."""
    if direction not in ('BULLISH','BEARISH') or sig.get('entry_direction')!=direction:
        raise ValueError('Momentum entry requires a new completed qualification episode or valid retest.')
    if not sig.get('entry_qualified') or not sig.get('ema_widening') or not sig.get('signal_allowed') or sig.get('direction')!=direction:
        raise ValueError('Momentum entry requires Supertrend agreement and EMA widening qualification.')
    keys=('open','high','low','close','ema10','ema30','rsi14_slope')
    if any(isinstance(sig.get(k),bool) or not isinstance(sig.get(k),(int,float)) or not math.isfinite(sig[k]) for k in keys):
        raise ValueError('Complete momentum candle, EMA and RSI evidence required.')
    o,h,l,close=(sig[k] for k in ('open','high','low','close'))
    if not 0<l<=min(o,close)<=max(o,close)<=h or h==l:
        raise ValueError('Valid non-flat completed momentum candle required.')
    bullish=direction=='BULLISH'
    aligned=close>sig['ema10']>sig['ema30'] if bullish else close<sig['ema10']<sig['ema30']
    slope=sig['rsi14_slope']>0 if bullish else sig['rsi14_slope']<0
    body=close>o if bullish else close<o
    outer=close>=h-(h-l)/3 if bullish else close<=l+(h-l)/3
    if not (aligned and slope and body and outer):
        raise ValueError('Momentum entry requires aligned EMAs, directional RSI/body and close in the outer third.')


PROFILE='all-broker-flexible-atr-v1'

def new_entry_defaults(payload):
    """New preview/Start only; never normalize a loaded run or held position."""
    result=dict(payload)
    if 'ema_momentum_enabled' not in result:
        result.update(ema_momentum_enabled=True,ema_proximity_enabled=True,
                      ema_proximity_mode='ATR',ema_proximity_distance=.5)
        result.setdefault('intrabar_entries',False)
    result.setdefault('ema_policy_profile',PROFILE)
    return result

def migrate_preferences(fields):
    """One-time upgrade of legacy drafts; explicit later baseline edits survive."""
    result=dict(fields)
    if result.get('ema-policy-profile')!=PROFILE:
        result.update({'ema-policy-profile':PROFILE,'ema-momentum-enabled':True,
            'ema-proximity-enabled':True,'ema-proximity-mode':'ATR',
            'ema-proximity-distance':'0.5','intrabar-entries':False})
    return result
