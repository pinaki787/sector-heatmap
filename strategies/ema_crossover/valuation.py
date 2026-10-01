"""Convert FYERS API quantities and quoted prices to rupees."""
import math


def multiplier(contract):
    raw = contract.get('quantity_multiplier')
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ValueError('Verified contract quantity multiplier required.') from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Invalid contract quantity multiplier.')
    return value


def amount(contract, quantity, price):
    return quantity * price * multiplier(contract)
