"""Optional monotonic full-position trailing exit; no partial profit targets."""
import math


def settings(payload):
    enabled=payload.get('trailing_enabled',False)
    basis=payload.get('trailing_basis','OPTION_PREMIUM_PERCENT')
    raw=payload.get('trailing_distance',10)
    try:distance=float(raw)
    except (ValueError,TypeError):raise ValueError('Trailing distance must be positive.')
    if not isinstance(enabled,bool) or isinstance(raw,bool) or not math.isfinite(distance) or distance<=0:
        raise ValueError('Choose a checkbox trailing enable and positive distance.')
    if basis not in ('OPTION_PREMIUM_PERCENT','UNDERLYING_POINTS'):
        raise ValueError('Choose option premium percentage or underlying points.')
    if basis=='OPTION_PREMIUM_PERCENT' and distance>=100:
        raise ValueError('Premium trailing percentage must be below100.')
    return dict(trailing_enabled=enabled,trailing_basis=basis,trailing_distance=distance)


def advance(state,config,direction,price,exchange_at,received_at,now,opened_at):
    """Reject stale/future/pre-exposure data; never loosen an established stop."""
    if not config.get('trailing_enabled'):return state,False
    if direction not in ('BULLISH','BEARISH'):raise ValueError('Unknown trailing direction.')
    for value in (price,exchange_at,received_at,now,opened_at):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Trailing requires finite fresh timestamped prices.')
    if price<=0 or not 0<=now-exchange_at<=15 or not 0<=now-received_at<=15 or exchange_at<opened_at:
        raise ValueError('Trailing requires fresh post-fill prices; no stale exit.')
    c=settings(config)
    bullish=(c['trailing_basis']=='OPTION_PREMIUM_PERCENT' and config.get('execution_route')!='CASH_EQUITY') or direction=='BULLISH'
    if state:
        if state['basis']!=c['trailing_basis'] or state['distance']!=c['trailing_distance']:
            raise ValueError('Open-position trailing settings cannot change silently.')
        if exchange_at<state['exchange_at'] or received_at<=state['received_at']:
            return state,False
    best=price if not state else max(state['best'],price) if bullish else min(state['best'],price)
    distance=best*c['trailing_distance']/100 if c['trailing_basis']=='OPTION_PREMIUM_PERCENT' else c['trailing_distance']
    stop=best-distance if bullish else best+distance
    if state:stop=max(stop,state['stop']) if bullish else min(stop,state['stop'])
    result=dict(basis=c['trailing_basis'],distance=c['trailing_distance'],best=best,stop=stop,
                exchange_at=exchange_at,received_at=received_at,observed_at=now,direction=direction)
    return result,price<=stop if bullish else price>=stop
