"""Optional percentage spread gate; quote validity remains mandatory."""
def enabled(config):
    value=config.get('spread_filter_enabled',config.get('strategy')!='RENKO_SUPERTREND_V1')
    if not isinstance(value,bool):raise ValueError('Spread limit switch must be boolean.')
    return value
