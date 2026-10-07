"""Optional host-close EMA exit calculations; no order route or strategy mutation."""
import math


def settings(payload):
    enabled=payload.get('ema_exit_enabled',False)
    if not isinstance(enabled,bool):raise ValueError('EMA exit enable must be a boolean.')
    raw=payload.get('ema_exit_length',10)
    try:length=float(raw)
    except (ValueError,TypeError):raise ValueError('EMA exit length must be a whole number from 1 to 1000.')
    if isinstance(raw,bool) or not math.isfinite(length) or not length.is_integer() or not 1<=length<=1000:
        raise ValueError('EMA exit length must be a whole number from 1 to 1000.')
    return dict(ema_exit_enabled=enabled,ema_exit_length=int(length))


def confirmed_values(rows,length):
    """Seed from the original host history anchor, using completed close prices only."""
    alpha=2/(length+1);value=None;result=[]
    for row in rows:
        if row.get('is_forming'):continue
        close=row['close']
        if not isinstance(close,(int,float)) or not math.isfinite(close) or close<=0:
            raise ValueError('Valid completed host closes required for EMA exit.')
        value=close if value is None else alpha*close+(1-alpha)*value
        result.append(dict(timestamp=row['timestamp'],close=close,ema_exit=value))
    return result


def confirmed_cross(previous,current,direction,enabled=True):
    if not enabled or previous is None or current.get('is_forming'):return False
    if current['timestamp']<=previous['timestamp']:return False
    if direction=='BULLISH':return previous['close']>=previous['ema_exit'] and current['close']<current['ema_exit']
    if direction=='BEARISH':return previous['close']<=previous['ema_exit'] and current['close']>current['ema_exit']
    raise ValueError('Unknown option direction.')


def live_breach(previous_ema,price,stamp,now,length,direction,enabled=True):
    if not enabled:return False,None
    if not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0 or not 0<=now-stamp<=15:
        raise ValueError('Fresh underlying tick required for EMA exit.')
    alpha=2/(length+1);ema=alpha*price+(1-alpha)*previous_ema
    return (price<ema if direction=='BULLISH' else price>ema),ema
