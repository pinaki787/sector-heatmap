"""User-selected parent durations are strategy inputs, never exchange session hours."""
PARENT_HOURS={'NSE_BSE':6,'CRYPTO':23,'GOLD':22,'COMMODITY':14}
def parent_hours(market,asset=None,tokenized_gold=False,explicit_category=None):
    if explicit_category:
        if explicit_category not in PARENT_HOURS:raise ValueError('Unknown explicit sizing category')
        return PARENT_HOURS[explicit_category]
    if tokenized_gold:raise ValueError('Tokenized gold needs explicit GOLD or CRYPTO sizing category')
    if str(asset or '').upper()=='GOLD':return 22
    market=str(market).upper()
    if market in ('NSE','BSE'):return 6
    if market in ('CRYPTO','DELTA_INDIA'):return 23
    if market in ('MCX','COMMODITY','NCDEX'):return 14
    raise ValueError('Explicit market sizing category required')
def reference_window(market,completed_session=None,completed_parent_end=None):
    if str(market).upper() in ('CRYPTO','DELTA_INDIA'):
        if not completed_parent_end:raise ValueError('Continuous market requires explicit completed parent-window end and anchoring policy')
        return dict(kind='COMPLETED_PARENT_WINDOW',end=completed_parent_end)
    if not completed_session:raise ValueError('Previous completed trading session required')
    return dict(kind='PREVIOUS_COMPLETED_TRADING_SESSION',session=completed_session)
