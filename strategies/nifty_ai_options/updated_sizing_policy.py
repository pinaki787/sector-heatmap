"""Selected-market sizing with explicit ATM/OTM option factors. Pure conversion, not a data provider.

Used by strategy conversion. Native acquisition remains separate; no candle ATR or TradingView fallback.
"""
import math
SETTINGS={
    "INDEX":(6,5),"EQUITY":(6,5),"STOCK_OPTION":(6,5),
    "MCX_COMMODITY":(14,5),"CRYPTO":(23,7),
    "GLOBAL_COMMODITY":(22,7),"FOREX":(22,7),
}
def option_factor(moneyness='OTM'):
    if moneyness not in ('OTM','ATM'):raise ValueError('Select OTM or ATM option classification')
    return 0.25 if moneyness=='OTM' else 0.5

def parent_contract(*,segment,is_option=False,option_moneyness='OTM'):
    if segment not in SETTINGS:raise ValueError("Explicit supported segment required")
    if type(is_option) is not bool:raise ValueError("Explicit option flag required")
    if segment=="STOCK_OPTION" and not is_option:raise ValueError("Stock option requires option division")
    factor=option_factor(option_moneyness) if is_option else 1
    hours,length=SETTINGS[segment]
    return dict(segment=segment,parent_hours=hours,parent_minutes=hours*60,atr_length=length,
                atr_period_basis="PARENT_CANDLES",chart_type="Renko",session="Regular trading hours",
                completed_parent_only=True,baseline_minutes=30,divisor=hours*2,
                option_divisor=int(1/factor),option_multiplier=factor,option_moneyness=option_moneyness if is_option else None)

def convert(reference,*,segment,is_option=False,option_moneyness='OTM'):
    if segment not in SETTINGS:raise ValueError("Explicit supported segment required")
    if type(is_option) is not bool:raise ValueError("Explicit option flag required")
    if segment=="STOCK_OPTION" and not is_option:
        raise ValueError("Stock option requires option division")
    if isinstance(reference,bool) or not isinstance(reference,(int,float)) or not math.isfinite(reference) or reference<=0:
        raise ValueError("Positive finite Renko parent brick size required")
    factor=option_factor(option_moneyness) if is_option else 1
    hours,atr=SETTINGS[segment]
    divisor=hours*60/30
    base=reference/divisor
    return dict(parent_hours=hours,atr_length=atr,session="Regular trading hours",
                parent_brick=reference,baseline_minutes=30,divisor=divisor,
                option_divisor=int(1/factor),option_multiplier=factor,option_moneyness=option_moneyness if is_option else None,
                brick=base*factor)

def from_selected_broker(reference,*,selected_broker,selected_account,selected_symbol,segment,is_option=False,option_moneyness='OTM'):
    hours,atr=SETTINGS.get(segment,(None,None))
    if not all(isinstance(s,str) and s for s in (selected_broker,selected_account,selected_symbol)):
        raise ValueError("Selected broker/account/symbol required")
    expected=dict(broker=selected_broker,account=selected_account,symbol=selected_symbol,
                  chart_type="Renko",session="Regular trading hours",
                  parent_hours=hours,atr_length=atr)
    if any(reference.get(k)!=v for k,v in expected.items()):
        raise ValueError("Selected-source Renko context mismatch")
    if reference.get("verified_native_size") is not True or reference.get("completed_parent") is not True:
        raise ValueError("Verified completed selected-broker Renko size unavailable")
    if not reference.get("as_of"):
        raise ValueError("Dated parent reference required")
    result=convert(reference.get("brick"),segment=segment,is_option=is_option,option_moneyness=option_moneyness)
    return dict(result,**expected,as_of=reference["as_of"])
