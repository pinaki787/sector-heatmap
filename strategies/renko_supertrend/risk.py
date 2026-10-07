"""Underlying price hard boundaries, independent of completed entry candles."""
import math
from strategies.ema_crossover.runner import validate_spot_levels


def levels(payload):
    result={}
    for key in ('spot_target','spot_stop'):
        raw=payload.get(key)
        value=None if raw in (None,'') else float(raw)
        if value is not None and (isinstance(raw,bool) or not math.isfinite(value) or value<=0):
            raise ValueError('Underlying target and stop must be positive absolute prices or blank.')
        result[key]=value
    return result


def hard_exit(price,direction,config):
    bullish=direction=='BULLISH'
    stop,target=config.get('spot_stop'),config.get('spot_target')
    if stop is not None and (price<=stop if bullish else price>=stop):return 'SPOT_STOP_EXIT'
    if target is not None and (price>=target if bullish else price<=target):return 'SPOT_TARGET_EXIT'
    return None
