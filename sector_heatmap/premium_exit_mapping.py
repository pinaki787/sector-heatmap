"""Instantaneous constant-IV premium scenarios; no predicted fill or time horizon."""
from datetime import datetime, time
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math


def premium_exits(*, spot, stop, target, premium, strike, expiry, option_type, tick, now):
    values=[spot,stop,target,premium,strike,tick]
    if any(not math.isfinite(float(v)) or float(v)<=0 for v in values):
        raise ValueError('Premium mapping requires finite positive prices and tick.')
    spot,stop,target,premium,strike,tick=map(float,values)
    if option_type not in ('CE','PE'):raise ValueError('Premium mapping needs an exact Call or Put.')
    if not (stop<spot<target if option_type=='CE' else target<spot<stop):
        raise ValueError('Underlying stop and target no longer bracket the fresh entry in the option direction.')
    end=datetime.combine(datetime.strptime(expiry,'%Y-%m-%d').date(),time(15,30),tzinfo=now.tzinfo)
    years=(end-now).total_seconds()/(365*86400)
    if years<=0:raise ValueError('Option has expired; premium exits cannot be mapped.')
    def price(s,vol):
        # Zero-rate model: IV is calibrated to the selected executable entry quote.
        d1=(math.log(s/strike)+vol*vol*years/2)/(vol*math.sqrt(years));d2=d1-vol*math.sqrt(years)
        n=lambda x:(1+math.erf(x/math.sqrt(2)))/2
        return s*n(d1)-strike*n(d2) if option_type=='CE' else strike*n(-d2)-s*n(-d1)
    low,high=.000001,10.
    if not price(spot,low)<premium<price(spot,high):
        raise ValueError('Fresh premium cannot be calibrated to a valid volatility scenario.')
    for _ in range(90):
        mid=(low+high)/2
        if price(spot,mid)<premium:low=mid
        else:high=mid
    iv=(low+high)/2
    unit=Decimal(str(tick))
    stop_price=float((Decimal(str(price(stop,iv)))/unit).to_integral_value(rounding=ROUND_CEILING)*unit)
    target_price=float((Decimal(str(price(target,iv)))/unit).to_integral_value(rounding=ROUND_FLOOR)*unit)
    if not 0<stop_price<premium<target_price:
        raise ValueError('Mapped premium stop/target cannot form valid tick-aligned exit legs.')
    return dict(basis='UNDERLYING_LEVELS_MAPPED_TO_PREMIUM',underlying_entry=spot,underlying_stop=stop,underlying_target=target,
                premium_entry=premium,stop_loss_price=stop_price,target_price=target_price,
                implied_volatility=iv,model='BLACK_SCHOLES_ZERO_RATE_CALIBRATED_TO_ENTRY',
                assumptions='Instantaneous move at unchanged time and implied volatility; mapped prices are estimates, not guaranteed underlying-level exits.',
                calculated_at=now.isoformat(),expiry=expiry)


def cash_exits(*, entry, stop, target, action, tick):
    """Tick-aligned absolute exits; never widen the requested stop."""
    values = [entry, stop, target, tick]
    if action not in ('BUY', 'SELL') or any(v is None or not math.isfinite(float(v)) or float(v) <= 0 for v in values):
        raise ValueError('Protected entry requires a valid side and positive entry, stop, target and tick.')
    entry, stop, target, tick = map(lambda v: Decimal(str(v)), values)
    stop = (stop/tick).to_integral_value(rounding=ROUND_CEILING if action == 'BUY' else ROUND_FLOOR)*tick
    target = (target/tick).to_integral_value(rounding=ROUND_FLOOR if action == 'BUY' else ROUND_CEILING)*tick
    if not (stop < entry < target if action == 'BUY' else target < entry < stop):
        raise ValueError('Stop and target must bracket the fresh entry after tick rounding.')
    return dict(basis='DIRECT_PRICE_LEVELS', entry_price=float(entry), stop_loss_price=float(stop), target_price=float(target),
                assumptions='Linked exit triggers are requested with entry; execution prices are not guaranteed.')


def premium_stop_from_greeks(*, spot, stop, premium, strike, expiry, option_type, tick, greeks, now, level_kind="STOP"):
    """Quote-anchored constant-IV scenario, not an executable protective order.

    Full repricing avoids a fixed Delta/Gamma Taylor extrapolation over a large
    underlying move. The model price ratio anchors the scenario to the quoted
    entry while retaining positive, monotonic option values.
    """
    from zoneinfo import ZoneInfo
    values=[spot,stop,premium,strike,tick]
    if any(isinstance(v,bool) or v is None or not math.isfinite(float(v)) or float(v)<=0 for v in values):raise ValueError('Positive spot, underlying stop, premium, strike and tick are required.')
    spot,stop,premium,strike,tick=map(float,values)
    if level_kind not in ('STOP','TARGET'):raise ValueError('Unknown premium scenario level kind.')
    adverse=(stop<spot if option_type=='CE' else stop>spot)
    if option_type not in ('CE','PE') or (not adverse if level_kind=='STOP' else adverse or stop==spot):raise ValueError('Underlying scenario level is on the wrong side of the option direction.')
    required=('delta','gamma','theta','vega','iv')
    if any(isinstance(greeks.get(k),bool) or not isinstance(greeks.get(k),(float,int)) or not math.isfinite(greeks[k]) for k in required):raise ValueError('Finite option Greeks (Delta/Gamma/Theta/Vega/IV) are required for a premium-level estimate.')
    delta,gamma,iv=greeks['delta'],greeks['gamma'],greeks['iv']
    if not (0<delta<=1 if option_type=='CE' else -1<=delta<0) or gamma<0 or not 0<iv<=1000:raise ValueError('Option Greeks are inconsistent with the selected contract.')
    zone=ZoneInfo('Asia/Kolkata');clock=now.astimezone(zone);end=datetime.combine(datetime.strptime(expiry,'%Y-%m-%d').date(),time(15,30),tzinfo=zone);years=(end-clock).total_seconds()/(365*86400)
    if years<=0:raise ValueError('Expired option cannot supply a premium-level estimate.')
    vol=iv/100
    def value(s):
        d1=(math.log(s/strike)+vol*vol*years/2)/(vol*math.sqrt(years));d2=d1-vol*math.sqrt(years);n=lambda x:.5*math.erfc(-x/math.sqrt(2))
        return s*n(d1)-strike*n(d2) if option_type=='CE' else strike*n(-d2)-s*n(-d1)
    base,scenario=value(spot),value(stop)
    if not base>0 or not (0<scenario<base if level_kind=='STOP' else scenario>base):raise ValueError('IV repricing cannot establish a bounded directional premium level.')
    raw=premium*scenario/base;unit=Decimal(str(tick));price=float((Decimal(str(raw))/unit).to_integral_value(rounding=ROUND_CEILING if level_kind=='STOP' else ROUND_FLOOR)*unit)
    if not (0<price<premium if level_kind=='STOP' else price>premium):raise ValueError('Premium-stop estimate cannot form a positive tick-aligned level below entry.')
    result=dict(status='ESTIMATED',stop_loss_price=price,raw_stop_loss_price=raw,premium_entry=premium,underlying_entry=spot,underlying_stop=stop,strike=strike,expiry=expiry,option_type=option_type,tick_size=tick,greeks={k:greeks[k] for k in required},model='QUOTE_ANCHORED_BLACK_SCHOLES_BROKER_IV_ZERO_RATE',model_entry_value=base,model_stop_value=scenario,quote_anchor_ratio=premium/base,delta_gamma_local_estimate=premium+delta*(stop-spot)+.5*gamma*(stop-spot)**2,calculated_at=clock.isoformat(),assumptions='Estimated premium at the underlying invalidation, anchored to the entry ask using full IV repricing. Time and IV held unchanged; zero interest/dividend rates. Delta/Gamma are local supporting evidence, not a fixed-distance extrapolation. Quote freshness is not established by this estimate. Fresh ticket review recalculates protection; no order is placed.')
    if level_kind=='TARGET':
        for old,new in [('stop_loss_price','target_price'),('raw_stop_loss_price','raw_target_price'),('underlying_stop','underlying_target'),('model_stop_value','model_target_value')]:result[new]=result.pop(old)
        result['assumptions']=result['assumptions'].replace('underlying invalidation','underlying target')
    return result

def premium_target_from_greeks(*,target,**kwargs):
    return premium_stop_from_greeks(stop=target,level_kind='TARGET',**kwargs)

