"""Chart destinations are stored separately; existing switches own execution.

Missing chart destinations are legacy configurations. Do not add fields to saved
runner identities merely by loading them; the UI migrates drafts explicitly.
"""
RULES = ('supertrend_enabled','ema_fast_enabled','ema_slow_enabled','ema_widening_enabled',
         'rsi_slope_enabled','use_adx','supertrend_exit_enabled','ema_exit_enabled',
         'ema_slow_exit_enabled','rsi_exit_enabled','ema_widening_exit_enabled',
         'adx_exit_enabled','market_structure_exit_enabled','zone_target_enabled','market_structure_enabled','higher_timeframe_enabled','ema_proximity_enabled','retest_enabled')
REVISION = 'strategy-indicator-destinations-v2'

def settings(payload):
    result = {key+'_indicator':payload[key+'_indicator'] for key in RULES if key+'_indicator' in payload}
    if any(not isinstance(value,bool) for value in result.values()):
        raise ValueError('Indicator destination switches must be booleans.')
    return result

def chart(payload):
    """Project visual selections into an isolated engine config, never mutate execution."""
    settings(payload)
    return {**{k:v for k,v in payload.items() if not k.endswith('_indicator')},
            **{key:payload.get(key+'_indicator',payload.get(key)) for key in RULES
               if key+'_indicator' in payload or key in payload}}
