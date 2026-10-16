"""Read-only evidence check for a broker-flat, externally closed FYERS position."""
from datetime import datetime
import math
from zoneinfo import ZoneInfo


def confirmed_close(position, positions, orders):
    """Return one unambiguous existing full exit; never construct a broker order.

    Partial exits, intervening same-product trades, absent evidence and outstanding
    orders fail closed. Other products cannot supply closure evidence.
    """
    symbol = position['symbol']
    quantity = int(position['quantity'])
    side = int(position.get('entry_side', 1))
    rows = [r for r in orders if r.get('symbol') == symbol]
    if any(int(r.get('status', 0)) not in {1, 2, 5, 7} for r in rows):
        raise ValueError('Outstanding order prevents external-close reconciliation.')
    if any(float(r.get('netQty', 0)) != 0 for r in positions if r.get('symbol') == symbol):
        raise ValueError('Broker contract is not flat; external close cannot be reconciled.')
    entries = [r for r in rows if str(r.get('id')) == str(position.get('entry_order_id'))]
    if len(entries) != 1:
        raise ValueError('Unique original entry order is required.')
    entry = entries[0]
    if int(entry.get('status', 0)) != 2 or int(entry.get('side', 0)) != side or int(entry.get('filledQty', 0)) != quantity or int(entry.get('qty', 0)) != quantity:
        raise ValueError('Original entry fill differs from owned quantity.')
    product = entry.get('productType')
    if product not in {'MARGIN', 'INTRADAY'}:
        raise ValueError('Verified FYERS product is required.')
    def stamp(row):
        return datetime.strptime(row['orderDateTime'], '%d-%b-%Y %H:%M:%S').replace(tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
    opening = stamp(entry)
    after = sorted((r for r in rows if r.get('productType') == product and int(r.get('filledQty', 0)) > 0 and str(r.get('id')) != str(entry['id']) and stamp(r) >= opening), key=stamp)
    if not after:
        raise ValueError('No confirmed external exit fill was found.')
    exit_row = after[0]
    price = float(exit_row.get('tradedPrice', 0))
    if stamp(exit_row) <= opening or int(exit_row.get('status', 0)) != 2 or int(exit_row.get('side', 0)) != -side or int(exit_row.get('qty', 0)) != quantity or int(exit_row.get('filledQty', 0)) != quantity or not math.isfinite(price) or price <= 0:
        raise ValueError('External exit is partial, ambiguous or unconfirmed.')
    return dict(order_id=str(exit_row['id']), symbol=symbol, quantity=quantity,
                side=-side, product=product, price=price, filled_at=stamp(exit_row),
                entry_order_id=str(entry['id']))
