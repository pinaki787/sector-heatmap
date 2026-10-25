"""Master strategy gates; stored subordinate choices and chart destinations stay independent."""
FAMILIES={
 'supertrend':('supertrend_enabled','supertrend_exit_enabled','higher_timeframe_enabled'),
 'ema':('ema_fast_enabled','ema_slow_enabled','ema_third_enabled','ema_widening_enabled','ema_proximity_enabled','ema_momentum_enabled','retest_enabled','ema_exit_enabled','ema_slow_exit_enabled','ema_widening_exit_enabled'),
 'rsi':('rsi_level_enabled','rsi_slope_enabled','rsi_exit_enabled','rsi_htf_1_enabled','rsi_htf_2_enabled','rsi_htf_3_enabled'),
 'adx':('use_adx','adx_exit_enabled'),
 'structure':('market_structure_enabled','market_structure_exit_enabled'),
 'zones':('zone_target_enabled',),
}
DEFAULTS={name+'_family_enabled':True for name in FAMILIES}
REVISION='indicator-family-masters-v1'
def restore(payload):
    result=dict(payload)
    choices=payload.get('indicator_family_choices') or {}
    if not isinstance(choices,dict):raise ValueError('Indicator family choices must be an object.')
    known={key for keys in FAMILIES.values() for key in keys}
    for key,value in choices.items():
        if key not in known or not isinstance(value,bool):raise ValueError('Invalid saved indicator choice.')
        family=next(name for name,keys in FAMILIES.items() if key in keys)
        previous=payload.get('indicator_family_applied') or {}
        masked=payload.get(family+'_family_enabled',True) is False or previous.get(family,True) is False
        if key=='retest_enabled':masked=masked or payload.get('supertrend_family_enabled',True) is False or previous.get('supertrend',True) is False
        if masked or key not in result:result[key]=value
    return result
def apply(payload):
    result=restore(payload)
    for key,default in DEFAULTS.items():
        value=result.get(key,default)
        if not isinstance(value,bool):raise ValueError('Indicator family switches must be booleans.')
        result[key]=value
    legacy_on={'supertrend_enabled','ema_fast_enabled','ema_slow_enabled','ema_third_enabled','ema_widening_enabled','rsi_slope_enabled','supertrend_exit_enabled'}
    for family,keys in FAMILIES.items():
        if not result[family+'_family_enabled']:
            for key in keys:result.setdefault(key,key in legacy_on)
    choices={key:result[key] for keys in FAMILIES.values() for key in keys if key in result}
    for family,keys in FAMILIES.items():
        if not result[family+'_family_enabled']:
            for key in keys:result[key]=False
    # Retest requires BOTH EMA and Supertrend; no forced enable of either family.
    if not result['supertrend_family_enabled'] or not result['ema_family_enabled']:result['retest_enabled']=False
    result['indicator_family_applied']={name:result[name+'_family_enabled'] for name in FAMILIES}
    result['indicator_family_choices']=choices
    return result
