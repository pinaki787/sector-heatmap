"""Authoritative broker/instrument scope for settings and runner actions."""
BROKERS={'FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'}

def normalize_settings(values,broker=None,instrument=None):
    result=dict(values)
    symbol=result.get('symbol') or instrument or ''
    if instrument and result.get('symbol') not in (None,'',instrument):
        raise ValueError('Settings instrument differs from selected runner.')
    if instrument:result['symbol']=instrument
    if broker=='DELTA_INDIA' and symbol and ':' in symbol:
        raise ValueError('Delta runner cannot use an Indian exchange instrument.')
    if broker in {'FYERS','DHAN','MOTILAL_OSWAL'} and symbol and not symbol.startswith(('NSE:','BSE:','MCX:')):
        raise ValueError('Indian broker runner cannot use a Delta instrument.')
    if symbol and not symbol.startswith('MCX:'):result.pop('commodity-holding',None)
    elif result.get('commodity-holding') in (None,''):result.pop('commodity-holding',None)
    equity=result.get('market') in ('NSE_EQUITY','BSE_EQUITY') or str(symbol).endswith('-EQ')
    if symbol and not equity:result.pop('cash-product',None)
    elif result.get('cash-product') in (None,''):result.pop('cash-product',None)
    if broker and broker!='DELTA_INDIA':
        for key in ('delta-execution-route','price-source','order-terms','carry-policy'):result.pop(key,None)
    return result

def validate_request(payload,broker,instrument=None,account_id=None):
    if payload.get('broker') not in (None,broker):raise ValueError('Action broker differs from selected runner.')
    if account_id and payload.get('account_id') not in (None,account_id):raise ValueError('Action account differs from selected runner.')
    if instrument:
        for key in ('underlying','symbol','instrument'):
            if payload.get(key) not in (None,'',instrument):raise ValueError('Action instrument differs from selected runner.')
        if isinstance(payload.get('settings'),dict):
            normalize_settings(payload['settings'],broker,instrument)
    return payload
