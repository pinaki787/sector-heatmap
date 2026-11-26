"""Latest selected-market conversion; native reference acquisition is separate."""
try:from .updated_sizing_policy import convert,SETTINGS,parent_contract,option_factor
except ImportError:from updated_sizing_policy import convert,SETTINGS,parent_contract,option_factor

def segment(market,asset=None,tokenized_gold=False,explicit_category=None):
    market=str(market).upper();asset=str(asset or '').upper()
    # Exchange classification wins over asset names and legacy category drafts.
    if market=='MCX':return 'MCX_COMMODITY'
    if market in ('NSE','BSE'):return 'INDEX'
    if tokenized_gold and not explicit_category:raise ValueError('Tokenized gold needs explicit GOLD or CRYPTO sizing category')
    if explicit_category=='FOREX':return 'FOREX'
    if explicit_category in ('GOLD','GLOBAL_COMMODITY'):return 'GLOBAL_COMMODITY'
    if explicit_category=='CRYPTO':return 'CRYPTO'
    if explicit_category=='NSE_BSE':return 'INDEX'
    if explicit_category=='COMMODITY':return 'MCX_COMMODITY'
    if explicit_category:raise ValueError('Unknown explicit sizing category')
    if market=='FOREX':return 'FOREX'
    if asset in ('GOLD','SILVER'):return 'GLOBAL_COMMODITY'
    if market in ('CRYPTO','DELTA_INDIA'):return 'CRYPTO'
    if market in ('GLOBAL_COMMODITY','GOLD'):return 'GLOBAL_COMMODITY'
    if market in ('COMMODITY','NCDEX'):return 'MCX_COMMODITY'
    raise ValueError('Explicit market sizing category required')

def parent_hours(market,asset=None,tokenized_gold=False,explicit_category=None):
    return SETTINGS[segment(market,asset,tokenized_gold,explicit_category)][0]

def atr_length(market,asset=None,explicit_category=None):
    return SETTINGS[segment(market,asset,explicit_category=explicit_category)][1]

def reference_window(market,completed_session=None,completed_parent_end=None):
    if str(market).upper() in ('CRYPTO','DELTA_INDIA'):
        if not completed_parent_end:raise ValueError('Continuous market requires explicit completed parent-window end and anchoring policy')
        return dict(kind='COMPLETED_PARENT_WINDOW',end=completed_parent_end)
    if not completed_session:raise ValueError('Previous completed trading session required')
    return dict(kind='PREVIOUS_COMPLETED_TRADING_SESSION',session=completed_session)

def scale_reference(reference,market,asset=None,*,delta=None,is_option=False,tokenized_gold=False,explicit_category=None,option_moneyness='OTM'):
    # delta remains accepted as selection metadata for older call sites. Its
    # magnitude NEVER participates in conversion under the 22-Nov contract.
    category=segment(market,asset,tokenized_gold,explicit_category)
    option=is_option or delta is not None
    base=convert(reference,segment=category)
    factor=option_factor(option_moneyness) if option else 1
    premium=convert(reference,segment=category,is_option=True,option_moneyness=option_moneyness)['brick'] if option else None
    return dict(parent_hours=base['parent_hours'],atr_length=base['atr_length'],baseline_minutes=30,divisor=base['divisor'],base_brick=base['brick'],premium_brick=premium,option_divisor=int(1/factor),option_multiplier=factor,option_moneyness=option_moneyness if option else None,policy_revision='selected-native-20261122')

def size_instrument(instrument,reference,*,delta=None):
    market=instrument.get('market');asset=instrument.get('asset');category=instrument.get('sizing_category')
    hours=parent_hours(market,asset,instrument.get('tokenized_gold',False),category)
    length=atr_length(market,asset,category)
    if not instrument.get('underlying') or reference.get('symbol')!=instrument['underlying']:raise ValueError('Reference belongs to another underlying')
    if reference.get('parent_hours')!=hours or reference.get('atr_length')!=length:raise ValueError('Native reference parent/ATR length mismatch')
    if reference.get('chart_session')!='Regular trading hours':raise ValueError('Regular-session native reference required')
    product=instrument.get('product_type')
    if product not in ('OPTION','FUTURE','PERPETUAL','STOCK','FOREX'):raise ValueError('Explicit supported product type required')
    if product!='OPTION' and delta is not None:raise ValueError('Direct instruments do not use option delta')
    result=scale_reference(reference.get('native_box'),market,asset,is_option=product=='OPTION',tokenized_gold=instrument.get('tokenized_gold',False),explicit_category=category,option_moneyness=instrument.get('option_moneyness','OTM'))
    return dict(result,symbol=instrument['underlying'],product_type=product,brick=result['premium_brick'] if product=='OPTION' else result['base_brick'],reference_session=reference.get('reference_session'))

def instrument_contract(market,asset=None,*,is_option=False,explicit_category=None,option_moneyness='OTM'):
    return parent_contract(segment=segment(market,asset,explicit_category=explicit_category),is_option=is_option,option_moneyness=option_moneyness)
