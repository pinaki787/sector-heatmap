"""Optional fixed-distance steps on fresh executable long-option bids."""
from decimal import Decimal, ROUND_FLOOR
import math


def settings(payload):
    enabled=payload.get('trailing_enabled',False)
    if not isinstance(enabled,bool):raise ValueError('Trailing enable must be a checkbox boolean.')
    mode=str(payload.get('trailing_mode','PERCENTAGE')).upper()
    if mode not in ('PERCENTAGE','POINTS'):raise ValueError('Choose percentage or points trailing.')
    raw=payload.get('trailing_step',10 if mode=='PERCENTAGE' else None)
    step=None if raw in (None,'') else float(raw)
    if enabled and (isinstance(raw,bool) or step is None or not math.isfinite(step) or step<=0):
        raise ValueError('Enabled trailing requires a positive premium step.')
    if step is not None and (not math.isfinite(step) or step<=0):raise ValueError('Trailing step must be positive or blank while disabled.')
    return dict(trailing_enabled=enabled,trailing_mode=mode,trailing_step=step)


def initial(entry,tick,config,quantity=None,lot_unit=None):
    if not config.get('trailing_enabled'):return None
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in (entry,tick)):
        raise ValueError('Trailing requires verified entry premium and tick size.')
    d=Decimal(str(config['trailing_step']))
    if config['trailing_mode']=='PERCENTAGE':d=Decimal(str(entry))*d/100
    split=None
    if quantity is not None and lot_unit and quantity%lot_unit==0:split=allocation(int(quantity//lot_unit))
    return dict(allocation=split,lot_unit=lot_unit,original_quantity=quantity,target_filled={},enabled=True,mode=config['trailing_mode'],configured_step=config['trailing_step'],entry=entry,tick=tick,increment=float(d),high_water=entry,level=0,armed=False,stop=None,next_trigger=float(Decimal(str(entry))+d),last_quote_received=None)


def advance(state,quote,now):
    """No mutation on stale, repeated, reversed or future quotes; fixed entry-based step."""
    if not state:return state,False
    bid,received,exchange=(quote.get(k) for k in ('bid','received_at','exchange_at'))
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (bid,received,exchange)) or bid<=0:
        raise ValueError('Trailing requires fresh timestamped executable bid.')
    if not -2<=now-received<=15 or not -2<=now-exchange<=15:raise ValueError('Trailing bid timestamp is stale or future.')
    if state.get('last_quote_received') is not None and received<=state['last_quote_received']:return state,False
    if state.get('last_quote_exchange') is not None and exchange<state['last_quote_exchange']:return state,False
    high=max(state['high_water'],bid)
    e,d,t=map(lambda x:Decimal(str(x)),(state['entry'],state['increment'],state['tick']))
    level=max(state['level'],int(((Decimal(str(high))-e)/d).to_integral_value(rounding=ROUND_FLOOR)))
    stop=None if level<1 else float(((e+(level-1)*d)/t).to_integral_value(rounding=ROUND_FLOOR)*t)
    if state.get('stop') is not None:stop=max(stop,state['stop'])
    result={**state,'high_water':high,'level':level,'armed':level>=1,'stop':stop,'next_trigger':float(e+(level+1)*d),'last_quote_received':received,'last_quote_exchange':exchange}
    return result,stop is not None and bid<=stop


def allocation(lots):
    if isinstance(lots,bool) or not isinstance(lots,int) or lots<1:raise ValueError('Verified whole filled lots required.')
    if lots==1:return [0,0,1]
    if lots==2:return [1,0,1]
    first=max(1,lots*30//100);second=max(1,lots*30//100)
    return [first,second,lots-first-second]


def target_quantity(state,remaining):
    if not state or not state.get('allocation'):return None
    for stage in (1,2):
        total=state['allocation'][stage-1]*state['lot_unit']
        filled=state.get('target_filled',{}).get(str(stage),0)
        qty=total-filled
        if state['level']>=stage and qty>0:
            if qty>remaining:raise ValueError('Partial target exceeds confirmed owned remainder.')
            if qty%state['lot_unit']:raise ValueError('Partial target remainder is not a verified whole lot; reconciliation required.')
            return stage,qty
    return None
