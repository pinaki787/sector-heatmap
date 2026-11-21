"""Causal Renko close swings, confirmed by two completed closes on each side.

Only completed brick input advances recurrence. A pending count freezes its
reference; equality or a close back inside resets it. New confirmed pivots apply
on the next attempt. Full precision is retained.
"""
from copy import deepcopy
REVISION='renko-swing-breakout-v1'
DEFAULTS={'swing_breakout_bricks':2}

def enabled(config):
    return config.get('swing_breakout_enabled', 'swing_breakout_bricks' in config) is True

def settings(payload):
    raw=payload.get('swing_breakout_bricks',2)
    try:
        n=int(raw)
        if isinstance(raw,bool) or float(raw)!=n or not 1<=n<=100:raise ValueError()
    except (TypeError,ValueError,OverflowError):
        raise ValueError('Swing breakout confirmation must be 1 to 100 completed bricks.') from None
    result={'swing_breakout_bricks':n}
    if 'swing_breakout_enabled' in payload:
        if not isinstance(payload['swing_breakout_enabled'],bool):raise ValueError('Swing breakout switch must be boolean.')
        result['swing_breakout_enabled']=payload['swing_breakout_enabled']
    return result

def observe(state,brick,config):
    n=settings(config)['swing_breakout_bricks']
    s=state.setdefault('swing_breakout',{'rows':[],'high':None,'low':None,'attempts':{}})
    if brick.get('provisional') or brick.get('is_forming'):return deepcopy(s.get('last',{}))
    rows=s['rows'];rows.append({'close':brick['close'],'timestamp':brick['timestamp']})
    if len(rows)>=5:
        window=rows[-5:];center=window[2];others=window[:2]+window[3:]
        for key,compare in (('high',lambda a,b:a>b),('low',lambda a,b:a<b)):
            if all(compare(center['close'],r['close']) for r in others):
                s[key]={'price':center['close'],'origin_at':center['timestamp'],'confirmed_at':brick['timestamp']}
    s['rows']=rows[-5:]
    sides={}
    for side,key in (('BULLISH','high'),('BEARISH','low')):
        attempt=s['attempts'].get(side) or {'reference':deepcopy(s[key]),'count':0}
        if attempt['count']>=n and attempt['reference']!=s[key]:attempt={'reference':deepcopy(s[key]),'count':0}
        ref=attempt['reference'];beyond=ref is not None and (brick['close']>ref['price'] if side=='BULLISH' else brick['close']<ref['price'])
        if beyond:attempt['count']+=1
        else:attempt={'reference':deepcopy(s[key]),'count':0}
        s['attempts'][side]=attempt
        allowed=attempt['count']>=n
        reason='PASS' if allowed else 'WAITING_CONFIRMED_RENKO_SWING' if attempt['reference'] is None else 'WAITING_SWING_BREAKOUT_CLOSES'
        sides[side]={**deepcopy(attempt),'required':n,'allowed':allowed,'reason':reason}
    result={'revision':REVISION,'high':deepcopy(s['high']),'low':deepcopy(s['low']),'sides':sides,'required':n,'pivot_left':2,'pivot_right':2}
    s['last']=deepcopy(result)
    return result

def check(config,signal,direction):
    if not enabled(config):return {'allowed':True,'reason':'CAPTURED_PRE_SWING_RULES'}
    if config.get('strategy_basis')!='RENKO':return {'allowed':True,'reason':'NOT_RENKO'}
    gate=(signal.get('swing_breakout') or {}).get('sides',{}).get(direction) or {}
    allowed=bool(not signal.get('provisional') and signal.get('has_completed_brick') and gate.get('allowed') and gate.get('required')==config.get('swing_breakout_bricks',2))
    return {**gate,'allowed':allowed,'reason':gate.get('reason','WAITING_CONFIRMED_RENKO_SWING') if not allowed else 'PASS'}
