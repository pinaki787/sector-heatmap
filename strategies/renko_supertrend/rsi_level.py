"""Optional strict RSI level entry gate; never changes exits."""
import math

def apply(entry,state,observation,direction,config):
    enabled=config.get('rsi_level_enabled',False)
    value=observation.get('rsi14')
    valid=isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    passed=valid and matches(value,direction,config)
    reason='WAITING_RSI_WARMUP' if not valid else 'WAITING_RSI_LEVEL'
    entry.update(rsi_level_mode=config.get('rsi_level_mode','THRESHOLD'),rsi_bullish_min=config.get('rsi_bullish_min',60),rsi_bullish_max=config.get('rsi_bullish_max',80),rsi_bearish_min=config.get('rsi_bearish_min',35),rsi_bearish_max=config.get('rsi_bearish_max',40),rsi_level_enabled=enabled,rsi_level_pass=passed if enabled else None,rsi_level_diagnostic=('PASS' if passed else reason) if enabled else 'OFF',rsi_bullish_above=config['rsi_bullish_above'],rsi_bearish_below=config['rsi_bearish_below'])
    if enabled and not passed:
        state['ema_qualified']=None
        if entry.get('entry_qualified') or entry.get('retest_signal'):
            entry.update(entry_direction=None,entry_qualified=False,entry_buy_signal=False,entry_sell_signal=False,entry_diagnostic=reason)
            if entry.get('retest_signal'):entry.update(retest_signal=False,retest_rsi_blocked=True)
    return entry


def matches(value,direction,config):
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):return False
    if config.get('rsi_level_mode','THRESHOLD')=='BETWEEN':
        prefix='rsi_bullish_' if direction=='BULLISH' else 'rsi_bearish_' if direction=='BEARISH' else None
        return prefix is not None and config[prefix+'min']<=value<=config[prefix+'max']
    return value>config['rsi_bullish_above'] if direction=='BULLISH' else value<config['rsi_bearish_below'] if direction=='BEARISH' else False
