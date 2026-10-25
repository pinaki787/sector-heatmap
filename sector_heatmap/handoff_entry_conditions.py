"""Explicit recommendation entry semantics, never inferred from arbitrary prose."""
import math,time
def condition(symbol,direction,level):
    if direction not in ('BULLISH','BEARISH') or isinstance(level,bool) or not isinstance(level,(float,int)) or not math.isfinite(level) or level<=0:return None
    return dict(schema='handoff-entry-condition/v1',symbol=symbol,price_basis='UNDERLYING',operator='AT_OR_ABOVE' if direction=='BULLISH' else 'AT_OR_BELOW',level=level,max_chase_pct=.5,source='Completed 15-minute close from recommendation',order_type='LIMIT_AFTER_APPLICATION_TRIGGER')
def reached(c,q,now):
    if not isinstance(c,dict) or c.get('schema')!='handoff-entry-condition/v1' or c.get('price_basis')!='UNDERLYING' or c.get('operator') not in ('AT_OR_ABOVE','AT_OR_BELOW') or c.get('max_chase_pct')!=.5:return False,'Explicit supported recommendation entry condition is unavailable.'
    if not q or q.get('symbol')!=c.get('symbol') or not q.get('connected'):return False,'Exact underlying stream is disconnected/unavailable.'
    try:
        price=float(q['price']);age=now-float(q['provider_at']);received=now-float(q['received_at']);level=float(c['level'])
        if not all(math.isfinite(v) for v in (price,level,age,received)) or price<=0 or level<=0:raise ValueError()
    except (KeyError,TypeError,ValueError):return False,'Invalid streamed entry-price evidence.'
    if not 0<=age<=5 or not 0<=received<=5:return False,'Entry trigger price is stale.'
    if c['operator']=='AT_OR_ABOVE':met=level<=price<=level*1.005
    else:met=level*.995<=price<=level
    return met,'Recommended entry condition met within its 0.5% bound.' if met else 'Waiting for recommended entry; outside trigger or chase bound.'

def stop_limit_before_trigger(c,q,traded_symbol,action,tick,limit):
    if not c or c.get('schema')!='handoff-entry-condition/v1' or c.get('symbol')!=traded_symbol or c.get('price_basis')!='UNDERLYING':return False
    if action not in ('BUY','SELL') or c.get('operator')!=('AT_OR_ABOVE' if action=='BUY' else 'AT_OR_BELOW'):return False
    try:
        trigger=float(c['level']);tick=float(tick);limit=float(limit);price=float(q['price'])
        return all(math.isfinite(v) and v>0 for v in (trigger,tick,limit,price)) and abs(round(trigger/tick)*tick-trigger)<1e-8 and limit==trigger and (price<trigger if action=='BUY' else price>trigger)
    except (KeyError,ValueError,TypeError):return False
def order_fields(payload,leg):
    order=payload.get('execution_entry_order') or {'type':'LIMIT'}
    if order.get('type')=='LIMIT':return dict(type=1,stopPrice=0)
    c=payload.get('entry_condition') or {}
    if order.get('type')!='STOP_LIMIT' or c.get('symbol')!=leg.get('symbol') or c.get('price_basis')!='UNDERLYING' or payload.get('proposal',{}).get('kind')!='EQUITY':raise ValueError('Stop-limit requires an explicit trigger in the exact traded-instrument price basis; underlying option triggers must wait in the application.')
    trigger=float(c['level']);limit=float(leg['limit_price']);tick=float(leg['tick_size'])
    if not math.isfinite(trigger) or trigger<=0 or abs(round(trigger/tick)*tick-trigger)>1e-8 or (limit<trigger if leg['action']=='BUY' else limit>trigger):raise ValueError('Stop-limit trigger/limit/tick constraints are invalid.')
    return dict(type=4,stopPrice=trigger)
