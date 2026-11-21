"""User-selected parent durations are strategy inputs, never exchange session hours."""
PARENT_HOURS={'NSE_BSE':6,'CRYPTO':23,'GOLD':22,'COMMODITY':14}
def parent_hours(market,asset=None,tokenized_gold=False,explicit_category=None):
    if explicit_category:
        if explicit_category not in PARENT_HOURS:raise ValueError('Unknown explicit sizing category')
        return PARENT_HOURS[explicit_category]
    if tokenized_gold:raise ValueError('Tokenized gold needs explicit GOLD or CRYPTO sizing category')
    if str(asset or '').upper()=='GOLD':return 22
    market=str(market).upper()
    if market in ('NSE','BSE'):return 6
    if market in ('CRYPTO','DELTA_INDIA'):return 23
    if market in ('MCX','COMMODITY','NCDEX'):return 14
    raise ValueError('Explicit market sizing category required')
def reference_window(market,completed_session=None,completed_parent_end=None):
    if str(market).upper() in ('CRYPTO','DELTA_INDIA'):
        if not completed_parent_end:raise ValueError('Continuous market requires explicit completed parent-window end and anchoring policy')
        return dict(kind='COMPLETED_PARENT_WINDOW',end=completed_parent_end)
    if not completed_session:raise ValueError('Previous completed trading session required')
    return dict(kind='PREVIOUS_COMPLETED_TRADING_SESSION',session=completed_session)

def scale_reference(reference,market,asset=None,*,delta=None,tokenized_gold=False,explicit_category=None):
    """Thirty-minute sizing baseline, independent of 1/5/30 execution source."""
    import math
    if isinstance(reference,bool) or not isinstance(reference,(int,float)) or not math.isfinite(reference) or reference<=0:raise ValueError('Positive verified native parent reference required')
    hours=parent_hours(market,asset,tokenized_gold,explicit_category)
    divisor=hours*60/30
    base=reference/divisor
    if delta is not None:
        if isinstance(delta,bool) or not isinstance(delta,(float,int)) or not math.isfinite(delta) or not 0<abs(delta)<=1:raise ValueError('Valid provider option delta required')
    return dict(parent_hours=hours,atr_length=5,baseline_minutes=30,divisor=divisor,base_brick=base,premium_brick=base*abs(delta) if delta is not None else None)

def size_instrument(instrument,reference,*,delta=None):
    """Same identity-bound rule for stocks, index/stock options and direct futures.

    A measured native reference must name the selected underlying and parent.
    This validates/scales evidence; it does not pretend to fetch native TV boxes.
    """
    market=instrument.get('market');asset=instrument.get('asset')
    hours=parent_hours(market,asset,instrument.get('tokenized_gold',False),instrument.get('sizing_category'))
    if not instrument.get('underlying') or reference.get('symbol')!=instrument['underlying']:raise ValueError('Reference belongs to another underlying')
    if reference.get('parent_hours')!=hours or reference.get('atr_length')!=5:raise ValueError('Native reference parent/ATR length mismatch')
    if str(market).upper() in ('NSE','BSE') and reference.get('chart_session')!='Regular trading hours':raise ValueError('Regular-session native reference required')
    product=instrument.get('product_type')
    if product=='OPTION':
        if delta is None:raise ValueError('Option premium sizing requires provider delta')
    elif product in ('FUTURE','PERPETUAL','STOCK','FOREX'):
        if delta is not None:raise ValueError('Direct instruments do not use option delta')
    else:raise ValueError('Explicit supported product type required')
    result=scale_reference(reference.get('native_box'),market,asset,delta=delta,tokenized_gold=instrument.get('tokenized_gold',False),explicit_category=instrument.get('sizing_category'))
    return dict(result,symbol=instrument['underlying'],product_type=product,brick=result['premium_brick'] if product=='OPTION' else result['base_brick'],reference_session=reference.get('reference_session'))
