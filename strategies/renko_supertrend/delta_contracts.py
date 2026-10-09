"""Delta-native Renko boundary types. No network or execution side effects.

Never infer contract size, expiry, currency conversion, or a session from a
symbol. The strategy engine consumes host candles independently of this module.
"""
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import re

RESOLUTIONS = {'1 minute': '1m', '3 minutes': '3m', '5 minutes': '5m',
               '15 minutes': '15m', '30 minutes': '30m', '1 hour': '1h'}
PRODUCT = 'DELTA_LONG_OPTION'
FUTURES_PRODUCT = 'DELTA_PERPETUAL'
FUTURES_ROUTE = 'DELTA_PERPETUAL'
FUTURES_REVISION = 'delta-perpetual-v1'
TERMINAL = {'closed': 2, 'cancelled': 1, 'REJECTED': 5}


def decimal(value, name, positive=False):
    if isinstance(value, bool):
        raise ValueError(name + ' must be numeric.')
    try:
        number = Decimal(str(value))
    except Exception:
        raise ValueError(name + ' unavailable.') from None
    if not number.is_finite() or (positive and number <= 0):
        raise ValueError(name + ' invalid.')
    return number


def whole(value, name, positive=False):
    number = decimal(value, name, positive)
    if number != number.to_integral_value():
        raise ValueError(name + ' must be whole contracts.')
    return int(number)


def configuration(payload):
    """Validate Delta policy explicitly, then use unchanged Renko rule validation."""
    from .runner import configuration as renko_configuration
    symbol = str(payload.get('underlying', '')).strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,79}', symbol):
        raise ValueError('Select a listed Delta perpetual signal instrument.')
    if payload.get('broker') != 'DELTA_INDIA':
        raise ValueError('Select Delta India explicitly.')
    if payload.get('price_source') != 'PERPETUAL_LAST_TRADE':
        raise ValueError('Delta Renko supports perpetual last-trade candles only.')
    if payload.get('order_terms') != 'MARKETABLE_LIMIT_IOC':
        raise ValueError('Select Delta marketable IOC limit orders explicitly.')
    if payload.get('timeframe', '5 minutes') not in RESOLUTIONS:
        raise ValueError('Unsupported Delta host timeframe; no implicit resampling.')
    carry = payload.get('carry_policy', 'CONTINUOUS')
    if carry not in ('CONTINUOUS', 'DAILY_SQUARE_OFF'):
        raise ValueError('Choose continuous crypto trading or an optional daily strategy cutoff.')
    deadline = payload.get('session_deadline') if carry == 'DAILY_SQUARE_OFF' else None
    if carry == 'DAILY_SQUARE_OFF' and (not isinstance(deadline, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', deadline) or deadline == '00:00'):
        raise ValueError('Choose an optional daily strategy cutoff in IST after 00:00.')
    # Shared capital/timeframe validation currently requires an Indian exchange
    # prefix. It validates no contract there; Delta metadata is validated below.
    route = payload.get('execution_route', 'OPTIONS')
    if route not in ('OPTIONS', FUTURES_ROUTE):
        raise ValueError('Choose Delta options or perpetual futures explicitly.')
    if route == FUTURES_ROUTE and payload.get('sideways_enabled', False):
        raise ValueError('Perpetual after-cost sideways filtering requires funding evidence; clear that optional filter.')
    contracts=whole(payload.get('lots'), 'Delta contracts', True)
    if contracts>100000:raise ValueError('Delta quantity exceeds 100000 whole contracts.')
    config = renko_configuration({**payload, 'lots':min(contracts,100), 'execution_route': 'OPTIONS', 'underlying': 'NSE:DELTA-VALIDATION'})
    config['lots']=contracts
    config.update(execution_route=route)
    if route == FUTURES_ROUTE:config['collateral_policy']='FULL_NOTIONAL'
    config.update(underlying=symbol, broker='DELTA_INDIA',
                  price_source='PERPETUAL_LAST_TRADE', order_terms='MARKETABLE_LIMIT_IOC',
                  session_open='00:00', session_deadline=deadline,
                  session_segment='DELTA_INDIA', session_source='EXPLICIT_USER_POLICY',
                  carry_policy=carry, seven_day_session=True)
    return config


def option_contract(product, now):
    if product.get('contract_type') not in ('call_options', 'put_options'):
        raise ValueError('Renko execution/adoption requires a listed long Call or Put.')
    if product.get('state') != 'live' or product.get('trading_status') != 'operational':
        raise ValueError('Delta option is not operational.')
    product_id = whole(product.get('id'), 'Product ID', True)
    value = decimal(product.get('contract_value'), 'Contract value', True)
    tick = decimal(product.get('tick_size'), 'Tick size', True)
    currency = product.get('quoting_currency')
    if (product.get('notional_type') != 'vanilla' or product.get('is_quanto') is not False
            or not product.get('underlying')
            or product.get('contract_unit_currency') != product['underlying']
            or not currency or currency != product.get('settlement_currency')):
        raise ValueError('Verified linear contract units and identical quote/settlement currencies required.')
    try:
        expiry = datetime.fromisoformat(str(product['settlement_time']).replace('Z', '+00:00'))
        if expiry.tzinfo is None:
            raise ValueError()
        expiry = expiry.timestamp()
    except Exception:
        raise ValueError('Timezone-qualified broker expiry required.') from None
    if expiry <= now:
        raise ValueError('Delta option has expired; no entry or adoption permitted.')
    return dict(symbol=product['symbol'], product_id=product_id, lot_size=1,
                quantity_multiplier=float(value), contract_value=str(value),
                tick_size=float(tick), quote_currency=currency,
                settlement_currency=currency, expiry_epoch=expiry,
                strike=float(decimal(product.get('strike_price'), 'Strike', True)),
                underlying_asset=product['underlying'],
                option_type='CE' if product['contract_type'] == 'call_options' else 'PE',
                broker='DELTA_INDIA', product=PRODUCT)


def perpetual_contract(product, require_entry=True):
    """Linear native perpetual only; reserve full notional, never set leverage."""
    if product.get('contract_type') != 'perpetual_futures':
        raise ValueError('Perpetual execution requires the exact listed perpetual.')
    if product.get('state') != 'live' or product.get('trading_status') != 'operational':
        raise ValueError('Delta perpetual is not operational.')
    currency = product.get('quoting_currency')
    if (product.get('notional_type') != 'vanilla' or product.get('is_quanto') is not False
            or not product.get('underlying') or product.get('contract_unit_currency') != product['underlying']
            or not currency or currency != product.get('settlement_currency')):
        raise ValueError('Verified linear native perpetual units and currencies required.')
    initial = decimal(product.get('initial_margin'), 'Initial margin percent', True)
    maintenance = decimal(product.get('maintenance_margin'), 'Maintenance margin percent', True)
    rate = decimal(product.get('taker_commission_rate'), 'Taker commission rate', True)
    if not maintenance <= initial <= 100 or rate >= 1:
        raise ValueError('Invalid perpetual margin or fee metadata.')
    if require_entry and (product.get('product_specs') or {}).get('only_reduce_only_orders_allowed') is not False:
        raise ValueError('Perpetual entry permissions unavailable or reduce-only.')
    value = decimal(product.get('contract_value'), 'Contract value', True)
    return dict(symbol=product['symbol'], product_id=whole(product.get('id'), 'Product ID', True),
                lot_size=1, quantity_multiplier=float(value), contract_value=str(value),
                tick_size=float(decimal(product.get('tick_size'), 'Tick size', True)),
                quote_currency=currency, settlement_currency=currency, underlying_asset=product['underlying'],
                broker='DELTA_INDIA', product=FUTURES_PRODUCT, execution_route=FUTURES_ROUTE,
                initial_margin_percent=float(initial), maintenance_margin_percent=float(maintenance),
                taker_commission_rate=float(rate), collateral_policy='FULL_NOTIONAL')


def contract_metadata(product, now):
    return perpetual_contract(product, require_entry=False) if product.get('contract_type') == 'perpetual_futures' else option_contract(product, now)


def position(row, product, now):
    meta = contract_metadata(product, now)
    if whole(row.get('product_id'), 'Position product ID', True) != meta['product_id']:
        raise ValueError('Position/product identity differs.')
    if row.get('product_symbol') != meta['symbol']:
        raise ValueError('Position symbol differs from listed product.')
    size = whole(row.get('size'), 'Position size')
    if not size or (meta['product'] == PRODUCT and size < 0):
        raise ValueError('Nonzero signed perpetual or positive long-option quantity required.')
    price = decimal(row.get('entry_price'), 'Broker entry average', True)
    return {**meta, 'netQty': size, 'netAvg': float(price), 'side': 1 if size > 0 else -1,
            'productType': meta['product']}


def order_intent(symbol, size, side, quote, product, now, reduce_only=None):
    meta = contract_metadata(product, now)
    futures = meta['product'] == FUTURES_PRODUCT
    if futures and reduce_only is False:perpetual_contract(product)
    if futures and not isinstance(reduce_only, bool):
        raise ValueError('Perpetual entry/exit intent must be explicit.')
    if not futures and reduce_only is not None and reduce_only is not (side == -1):
        raise ValueError('Long option entries BUY; exits SELL reduce-only.')
    if symbol != meta['symbol'] or side not in (1, -1) or isinstance(side, bool):
        raise ValueError('Exact contract and explicit BUY/SELL required.')
    size = whole(size, 'Order size', True)
    if size > 100000:
        raise ValueError('Order exceeds the supported contract count.')
    for field in ('exchange_at', 'received_at'):
        age = now - float(decimal(quote.get(field), 'Quote ' + field))
        if not 0 <= age <= 15:
            raise ValueError('Fresh executable quote required.')
    bid = decimal(quote.get('bid'), 'Bid', True)
    ask = decimal(quote.get('ask'), 'Ask', True)
    if bid > ask:
        raise ValueError('Crossed executable quote.')
    tick = decimal(product['tick_size'], 'Tick size', True)
    reference = ask if side == 1 else bid
    rounding = ROUND_CEILING if side == 1 else ROUND_FLOOR
    # Existing Delta runner terms: at most one tick beyond the executable quote.
    limit = (reference / tick).to_integral_value(rounding=rounding) * tick + (tick if side == 1 else -tick)
    if limit <= 0:
        raise ValueError('No positive marketable IOC exit price available.')
    return dict(mode='LIVE', symbol=symbol, contracts=size,
                side='buy' if side == 1 else 'sell', order_type='limit_order',
                time_in_force='ioc', limit_price=str(limit), reduce_only=reduce_only if futures else side == -1,
                product_id=meta['product_id'], strategy='RENKO_SUPERTREND_V1')


def owned_order(owned, expected_account):
    """Normalize verified Delta cumulative evidence, retaining native order terms."""
    if not expected_account or owned.get('account_identity') != expected_account:
        raise ValueError('Delta order belongs to a different account.')
    request = owned['request']
    size = whole(request.get('size'), 'Requested size', True)
    filled = whole(owned.get('filled_contracts'), 'Cumulative filled size')
    if not 0 <= filled <= size:
        raise ValueError('Cumulative fill exceeds requested size.')
    state = owned.get('status')
    if state not in {*TERMINAL, 'open', 'pending', 'SUBMITTING', 'UNKNOWN', 'CANCEL_UNKNOWN'}:
        raise ValueError('Unknown broker order state.')
    if state == 'closed' and filled != size:
        raise ValueError('Closed order has inconsistent fills.')
    side = request.get('side')
    futures = (owned.get('product') or {}).get('contract_type') == 'perpetual_futures'
    if side not in ('buy', 'sell') or not isinstance(request.get('reduce_only'), bool) or (not futures and request['reduce_only'] is not (side == 'sell')):
        raise ValueError('Renko exits must be reduce-only; entries must BUY.')
    if request.get('order_type') != 'limit_order' or request.get('time_in_force') != 'ioc':
        raise ValueError('Delta Renko order terms differ from IOC-limit policy.')
    price = float(decimal(owned.get('average_fill_price'), 'Fill average', True)) if filled else None
    status = TERMINAL.get(state, 6)
    return dict(id=str(owned.get('order_id') or owned['client_order_id']),
                symbol=owned['symbol'], side=1 if side == 'buy' else -1,
                qty=size, filledQty=filled, remainingQuantity=size-filled,
                tradedPrice=price, productType=FUTURES_PRODUCT if futures else PRODUCT, status=status,
                orderTag=owned['request_id'], native_status=state,
                product_id=whole(request.get('product_id'), 'Order product ID', True),
                reduce_only=request['reduce_only'], limit_price=request['limit_price'],
                commission=owned.get('commission'), broker='DELTA_INDIA')
