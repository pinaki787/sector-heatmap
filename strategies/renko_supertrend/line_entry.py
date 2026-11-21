"""Optional Bull/Bear line entry filter on actual completed Renko bricks."""
import math
import json
REVISION='drawn-renko-bull-bear-v2'
DEFAULTS=dict(line_entry_enabled=False,line_entry_definition='')

def valid_line(line):
    if line.get('kind')=='horizontal':numbers=[line['price']]
    elif line.get('kind')=='trend':
        points=line['points']
        if len(points)!=2 or points[0]['time']>=points[1]['time']:raise ValueError()
        numbers=[n for point in points for n in (point['time'],point['value'])]
    else:raise ValueError()
    if any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n<=0 for n in numbers):raise ValueError()

def settings(payload):
    enabled=payload.get('line_entry_enabled',False)
    if not isinstance(enabled,bool):raise ValueError('Line entry switch must be boolean.')
    raw=payload.get('line_entry_definition','')
    if not raw and not enabled:return dict(line_entry_enabled=False,line_entry_definition='')
    try:
        definition=json.loads(raw) if isinstance(raw,str) else raw
        if not isinstance(definition,dict):raise ValueError()
        if not isinstance(definition.get('symbol'),str) or not definition['symbol']:raise ValueError()
        if not isinstance(definition.get('timeframe'),str) or not definition['timeframe']:raise ValueError()
        for side in ('bullish','bearish'):
            line=definition.get(side)
            if line is None:
                if enabled:raise ValueError()
                continue
            valid_line(line)
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):raise ValueError('Select valid Bull and Bear entry lines for this instrument and timeframe.') from None
    return dict(line_entry_enabled=enabled,line_entry_definition=json.dumps(definition,separators=(',',':'),allow_nan=False))

def level(line,at):
    if line['kind']=='horizontal':return line['price']
    a,b=line['points']
    return a['value']+(b['value']-a['value'])*(at-a['time'])/(b['time']-a['time'])

def observe(state,config,signal,run_id):
    if not config.get('line_entry_enabled'):return dict(enabled=False,allowed=True,reason='OFF')
    definition=json.loads(settings(config)['line_entry_definition'])
    if definition['symbol']!=config['underlying'] or definition['timeframe']!=config['timeframe']:
        return dict(enabled=True,allowed=False,reason='LINE_SCOPE_MISMATCH')
    if config.get('strategy_basis')!='RENKO' or signal.get('provisional') or signal.get('has_completed_brick') is not True:
        return dict(enabled=True,allowed=False,reason='WAITING_COMPLETED_RENKO_BRICK')
    direction=signal.get('cross_direction') or signal.get('direction')
    at=signal.get('market_event_at',signal['timestamp'])
    close=signal.get('close')
    bull=level(definition['bullish'],at);bear=level(definition['bearish'],at)
    valid=isinstance(close,(int,float)) and not isinstance(close,bool) and math.isfinite(close)
    beyond=bool(valid and bull>0 and bear>0 and ((direction=='BULLISH' and close>bull) or (direction=='BEARISH' and close<bear)))
    allowed=bool(beyond and signal.get('entry_qualified') and direction==signal.get('cross_direction') and direction==signal.get('direction'))
    return dict(enabled=True,allowed=allowed,reason='PASS' if allowed else 'WAITING_RENKO_CLOSE_AND_STRATEGY',direction=direction,brick_close=close,bull_line=bull,bear_line=bear,event_at=at)
