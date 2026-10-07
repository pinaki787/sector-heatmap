"""Finite INR wallet for legacy simulation lifecycles; no broker API access."""
import math

def capital(value=100000):
    if isinstance(value,bool):raise ValueError('Virtual Paper capital must be positive INR.')
    try:value=float(value)
    except (ValueError,TypeError):raise ValueError('Virtual Paper capital must be positive INR.') from None
    if not math.isfinite(value) or not 0<value<=1e9:raise ValueError('Virtual Paper capital must be positive INR, up to 1 billion.')
    return value

def wallet(initial=100000,realized=0,fees=0,reserved=0):
    initial=capital(initial)
    if not all(math.isfinite(x) for x in (realized,fees,reserved)) or fees<0 or reserved<0:raise ValueError('Verified virtual Paper ledger values required.')
    return dict(initial_inr=initial,realized_gross_inr=realized,fee_provision_inr=fees,reserved_inr=reserved,available_inr=initial+realized-fees-reserved,
                basis='Virtual INR capital; full premium/notional reservation; conservative fee provision; no leverage or live balance.')

def reserve(current,notional,fee_rate=.005):
    if not math.isfinite(notional) or notional<=0:raise ValueError('Verified positive Paper commitment required.')
    needed=notional*(1+fee_rate+.01)
    if needed>current['available_inr']:raise ValueError(f"Virtual Paper capital insufficient: required INR {needed:.2f}, available INR {current['available_inr']:.2f}. Requested quantity unchanged.")
    return wallet(current['initial_inr'],current['realized_gross_inr'],current['fee_provision_inr']+notional*fee_rate,current['reserved_inr']+notional)

def release(current,notional,realized,fee_rate=.005):
    return wallet(current['initial_inr'],current['realized_gross_inr']+realized,current['fee_provision_inr']+notional*fee_rate,0)
