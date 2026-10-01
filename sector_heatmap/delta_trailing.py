"""Fixed entry-based steps on executable Delta bids (long) or asks (short)."""
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
import math
from strategies.ema_crossover.trailing import allocation

def settings(payload):
    enabled=payload.get('trailing_enabled',False);mode=payload.get('trailing_mode','PERCENTAGE');raw=payload.get('trailing_step',10 if mode=='PERCENTAGE' else None)
    if not isinstance(enabled,bool) or mode not in ('PERCENTAGE','POINTS'):raise ValueError('Choose optional trailing checkbox and percentage/price-points mode.')
    try:step=None if raw in (None,'') else float(raw)
    except Exception:raise ValueError('Trailing step must be a positive number.') from None
    if isinstance(raw,bool) or step is not None and (not math.isfinite(step) or step<=0) or enabled and step is None:raise ValueError('Enabled trailing needs a positive price step.')
    if enabled and mode=='PERCENTAGE' and step>=100:raise ValueError('Delta trailing percentage must be below 100%.')
    return dict(trailing_enabled=enabled,trailing_mode=mode,trailing_step=step)

def initial(entry,tick,quantity,side,config):
    if not config.get('trailing_enabled'):return None
    e,t=Decimal(str(entry)),Decimal(str(tick));d=Decimal(str(config['trailing_step']))
    if config['trailing_mode']=='PERCENTAGE':d=e*d/100
    if not e.is_finite() or not t.is_finite() or e<=0 or t<=0 or d<=0 or side not in ('buy','sell'):raise ValueError('Trailing needs verified entry, tick and side.')
    if side=='sell' and d>=e:raise ValueError('Short trailing step must be smaller than the filled entry price.')
    return dict(enabled=True,mode=config['trailing_mode'],configured_step=config['trailing_step'],entry=str(e),increment=str(d),tick=str(t),side=side,original_contracts=quantity,allocation=allocation(quantity),target_filled={},extreme=str(e),level=0,armed=False,stop=None,next_trigger=str(e+d if side=='buy' else e-d),last_received=None,last_exchange=None,exit_latched=False)

def advance(state,quote,now):
    if not state:return state,False
    field='bid' if state['side']=='buy' else 'ask';price,received,exchange=(quote.get(k) for k in (field,'received_at','exchange_at'))
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (price,received,exchange)) or price<=0 or not -2<=now-received<=15 or not -2<=now-exchange<=15:raise ValueError('Delta trailing needs a fresh executable '+field+'.')
    if state['last_received'] is not None and received<=state['last_received'] or state['last_exchange'] is not None and exchange<state['last_exchange']:return state,False
    e,d,t,p=map(lambda v:Decimal(str(v)),(state['entry'],state['increment'],state['tick'],price));long=state['side']=='buy';extreme=max(Decimal(state['extreme']),p) if long else min(Decimal(state['extreme']),p)
    level=max(state['level'],int(((extreme-e if long else e-extreme)/d).to_integral_value(rounding=ROUND_FLOOR)))
    stop=None
    if level>=1:
        raw=e+(level-1)*d if long else e-(level-1)*d
        stop=(raw/t).to_integral_value(rounding=ROUND_FLOOR if long else ROUND_CEILING)*t
        if state['stop'] is not None:stop=max(stop,Decimal(state['stop'])) if long else min(stop,Decimal(state['stop']))
    trigger=e+(level+1)*d if long else e-(level+1)*d
    result={**state,'extreme':str(extreme),'level':level,'armed':level>=1,'stop':str(stop) if stop is not None else None,'next_trigger':str(trigger) if trigger>0 else None,'last_received':received,'last_exchange':exchange}
    hit=stop is not None and (p<=stop if long else p>=stop)
    return result,hit

def target(state,remaining):
    for stage in (1,2):
        quantity=state['allocation'][stage-1]-state['target_filled'].get(str(stage),0)
        if state['level']>=stage and quantity>0:
            if quantity>=remaining:raise ValueError('Trailing target would consume the reserved runner contract.')
            return stage,quantity
    return None
