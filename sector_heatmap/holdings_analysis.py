"""Read-only portfolio review. Deterministic hypotheses, never an order interface."""
from .persistent_jobs import checkpoint
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import math
import threading
import time
import uuid
from zoneinfo import ZoneInfo

from .broker_diagnostics import diagnostics
from .market_calendar import market_session
from .fyers_history import account_read, history, quotes

IST = ZoneInfo('Asia/Kolkata')
ACTIONS = ('HOLD', 'TRAIL', 'EXIT', 'BOOK_PROFIT', 'REVIEW_NEEDED')


def number(value):
    if isinstance(value, bool): return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError, OverflowError):
        return None


def ema(values, period):
    if len(values) < period:
        raise ValueError('Insufficient completed candles.')
    result = sum(values[:period]) / period
    for value in values[period:]:
        result += (value - result) * 2 / (period + 1)
    return result


def indicators(rows):
    if len(rows) < 110:
        raise ValueError('At least 110 completed daily candles are required for daily and weekly context.')
    closes = [r['close'] for r in rows]
    tr = [max(b['high'] - b['low'], abs(b['high'] - a['close']), abs(b['low'] - a['close'])) for a, b in zip(rows, rows[1:])]
    gains = [max(b - a, 0) for a, b in zip(closes, closes[1:])]
    losses = [max(a - b, 0) for a, b in zip(closes, closes[1:])]
    def wilder(values):
        result = sum(values[:14]) / 14
        for value in values[14:]: result = (13 * result + value) / 14
        return result
    gain, loss = wilder(gains), wilder(losses)
    rsi = 50 if gain == loss == 0 else 100 if loss == 0 else 100 - 100 / (1 + gain / loss)
    weeks = {}
    # The week containing the latest session can still form; exclude it conservatively.
    latest_week = datetime.fromtimestamp(rows[-1]['timestamp'], IST).date().isocalendar()[:2]
    for row in rows:
        key = datetime.fromtimestamp(row['timestamp'], IST).date().isocalendar()[:2]
        if key != latest_week: weeks[key] = row['close']
    weekly = list(weeks.values())
    if len(weekly) < 20: raise ValueError('Fewer than 20 completed prior weeks are available.')
    return {'close': closes[-1], 'ema20': ema(closes, 20), 'ema50': ema(closes, 50),
            'atr14': wilder(tr), 'rsi14': rsi, 'weekly_close': weekly[-1], 'weekly_ema20': ema(weekly, 20),
            'support20': min(r['low'] for r in rows[-21:-1]), 'resistance20': max(r['high'] for r in rows[-21:-1]),
            'low5': min(r['low'] for r in rows[-5:]), 'high5': max(r['high'] for r in rows[-5:])}


def review(row, candles, expected_session, now=None):
    """Review long delivery shares only. Derivatives are deliberately not reduced to spot rules."""
    result = {**row, 'action': 'REVIEW_NEEDED', 'reasons': [], 'candidate_stop': None,
              'gross_pnl': None, 'gross_return_pct': None, 'evidence': {}, 'timeframe': 'Daily + prior completed weeks', 'analysed_at': datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc).isoformat(),
              'limitations': ['Technical swing hypothesis; not backtested or calibrated.',
                              'P&L excludes taxes, fees, dividends and corporate-action adjustments.',
                              'No existing stop, target, strategy ownership or personal risk budget is assumed.']}
    qty, cost, price = (number(row.get(k)) for k in ('quantity', 'average_price', 'price'))
    if qty and cost and price and qty > 0 and cost > 0 and price > 0:
        result.update(gross_pnl=round(qty * (price - cost), 2), gross_return_pct=round((price / cost - 1) * 100, 2))
    if row.get('kind') != 'DELIVERY_EQUITY':
        result['reasons'] = [row.get('review_reason') or 'Contract-specific underlying, expiry, liquidity and position-risk review required.']
        return result
    if qty is None or qty <= 0 or cost is None or cost <= 0 or price is None or price <= 0:
        result['reasons'] = ['Current quantity, positive acquisition cost or price is unavailable.']
        return result
    stamp = number(row.get('quote_timestamp'))
    current = now if now is not None else time.time()
    session = market_session(datetime.fromtimestamp(current, IST))
    quote_day = datetime.fromtimestamp(stamp, IST).date().isoformat() if stamp and 0 < stamp <= current + 5 else None
    if (session['status'] == 'OPEN' and (not stamp or not -5 <= current - stamp <= 120)) or (session['status'] != 'OPEN' and quote_day != expected_session):
        result['reasons'] = ['Quote timestamp is missing or stale for this market session.']
        return result
    try:
        rows = []
        previous = None
        for raw in candles:
            if not isinstance(raw, dict): raise ValueError('Candle schema is invalid.')
            values = {k: number(raw.get(k)) for k in ('timestamp', 'open', 'high', 'low', 'close')}
            if any(v is None for v in values.values()): raise ValueError('Candle values are missing or non-finite.')
            if not 0 < values['timestamp'] <= current + 5: raise ValueError('Candle timestamp is invalid.')
            if previous is not None and values['timestamp'] <= previous: raise ValueError('Candle times are duplicated or unordered.')
            previous = values['timestamp']
            if min(values[k] for k in ('open', 'high', 'low', 'close')) <= 0 or values['high'] < max(values['open'], values['close'], values['low']) or values['low'] > min(values['open'], values['close']):
                raise ValueError('Candle OHLC values are inconsistent.')
            day = datetime.fromtimestamp(values['timestamp'], IST).date().isoformat()
            if day <= expected_session and not raw.get('is_forming'): rows.append(values)
        if not rows or datetime.fromtimestamp(rows[-1]['timestamp'], IST).date().isoformat() != expected_session:
            raise ValueError('Latest completed daily candle is stale or unavailable.')
        info = indicators(rows)
        if info['atr14'] <= 0: raise ValueError('A positive ATR is unavailable.')
    except (ValueError, TypeError, OverflowError, OSError) as error:
        result['reasons'] = [str(error)]
        return result
    result['evidence'] = {**{k: round(v, 4) for k, v in info.items()}, 'completed_session': expected_session,
                          'quote_timestamp': datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                          'price_basis': 'Recent quote' if session['status'] == 'OPEN' else 'Last completed session quote'}
    close, e20, e50, atr, rsi = (info[k] for k in ('close', 'ema20', 'ema50', 'atr14', 'rsi14'))
    if abs(price - close) > 3 * atr:
        result['reasons'] = ['Current price differs from the completed daily close by more than 3 ATR; review the gap and intraday risk before relying on swing rules.']
        return result
    weekly_up = info['weekly_close'] > info['weekly_ema20']
    pnl = result['gross_pnl']
    if close < e50 and e20 < e50 and not weekly_up:
        result.update(action='EXIT', reasons=['Daily close and EMA20 are below EMA50, with a weak prior completed weekly trend.',
                                               'Consider exiting after checking current liquidity and any strategy-managed exits.'])
    elif pnl > 0 and rsi >= 70 and close - e20 >= 2 * atr and close >= info['resistance20'] - .5 * atr:
        result.update(action='BOOK_PROFIT', reasons=['Profitable holding is extended at least 2 ATR above EMA20, RSI ≥ 70 and near the prior 20-session high.',
                                                      'Consider a partial profit booking; the quantity depends on your risk and tax plan.'])
    elif close > e20 > e50 and weekly_up:
        stop = max(e20, close - 2 * atr, info['low5'])
        if pnl > 0 and close - cost >= atr and cost < stop < min(price, close):
            result.update(action='TRAIL', candidate_stop=round(stop, 4),
                          reasons=['Daily and prior weekly trends are positive; the candidate protective level is above acquisition cost.',
                                   'Candidate = max(EMA20, completed close − 2 ATR, five-session low). Raise an existing long stop only; never loosen it.'])
        else:
            result.update(action='HOLD', reasons=['Daily close > EMA20 > EMA50 and the prior completed weekly close is above its EMA20.',
                                                 'Trend remains constructive; reassess on a completed daily close below EMA20.'])
    else:
        result['reasons'] = ['Daily and weekly evidence is mixed; no supported Hold, Trail, Exit or Book Profit rule matched.']
    return result


def review_linear(row, candles, now):
    """Verified vanilla futures only; symmetric contract-trend review for long/short."""
    base = review(row, [], '', now)
    base.update(gross_pnl=None, gross_return_pct=None)
    base['timeframe'] = 'Completed UTC daily contract candles + prior completed weeks'
    if row.get('kind') != 'LINEAR_FUTURE': return base
    qty, cost, price, units, stamp = (number(row.get(k)) for k in ('quantity', 'average_price', 'price', 'contract_value', 'quote_timestamp'))
    if qty in (None, 0) or any(v is None or v <= 0 for v in (cost, price, units, stamp)) or not -2 <= now - stamp <= 15:
        base['reasons'] = ['Verified contract units, acquisition price or fresh executable quote is unavailable.']
        return base
    expiry = number(row.get('expiry_timestamp'))
    if expiry is not None and expiry - now <= 86400:
        base['reasons'] = ['Contract expires within 24 hours or has expired; review settlement and liquidity manually.']
        return base
    try:
        rows = []
        last = None
        for raw in candles:
            values = {k: number(raw.get(k)) for k in ('timestamp', 'open', 'high', 'low', 'close')}
            if any(v is None for v in values.values()) or any(values[k] <= 0 for k in values): raise ValueError('Invalid contract OHLC evidence.')
            if last is not None and values['timestamp'] <= last: raise ValueError('Contract candle times must be ordered and unique.')
            last = values['timestamp']
            if values['high'] < max(values['open'], values['close'], values['low']) or values['low'] > min(values['open'], values['close']):
                raise ValueError('Contract candle prices are inconsistent.')
            if values['timestamp'] + 86400 <= now and not raw.get('is_forming'): rows.append(values)
        expected = int(now // 86400) * 86400 - 86400
        if not rows or rows[-1]['timestamp'] != expected: raise ValueError('Latest completed UTC daily contract candle is missing.')
        info = indicators(rows)
        if info['atr14'] <= 0: raise ValueError('Positive contract ATR is unavailable.')
    except (ValueError, TypeError, OSError, OverflowError) as error:
        base['reasons'] = [str(error)]; return base
    pnl = qty * units * (price - cost)
    side = 1 if qty > 0 else -1
    close, e20, e50, atr, rsi = (info[k] for k in ('close', 'ema20', 'ema50', 'atr14', 'rsi14'))
    if abs(price - close) > 3 * atr:
        base['reasons'] = ['Executable contract price has moved more than 3 ATR from the completed daily close; review current risk manually.']
        return base
    weekly = side * (info['weekly_close'] - info['weekly_ema20']) > 0
    base.update(gross_pnl=round(pnl, 6), gross_return_pct=round(side * (price / cost - 1) * 100, 2),
                evidence={**{k: round(v, 4) for k, v in info.items()}, 'quote_timestamp': datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                          'completed_session': datetime.fromtimestamp(expected, timezone.utc).date().isoformat(),
                          'price_basis': 'Executable bid for long exit / ask for short exit', 'contract_value': units},
                limitations=['Contract-price trend hypothesis; not backtested or calibrated.',
                             'Gross P&L = signed contracts × verified contract units × (executable exit price − entry); excludes fees and funding.',
                             'Return is unlevered price movement, not return on margin.',
                             'Hedges and strategy ownership must be checked before acting.'])
    if side * (close - e50) < 0 and side * (e20 - e50) < 0 and not weekly:
        base.update(action='EXIT', reasons=['Completed daily and prior weekly trends oppose the position direction.', 'Consider closing only after checking hedges and the owning strategy.'])
    elif pnl > 0 and (rsi >= 70 if side > 0 else rsi <= 30) and side * (close - e20) >= 2 * atr and (close >= info['resistance20'] - .5 * atr if side > 0 else close <= info['support20'] + .5 * atr):
        base.update(action='BOOK_PROFIT', reasons=['Profitable contract is extended at least 2 ATR in the position direction, with extreme RSI near the prior range boundary.', 'Consider partial profit taking after checking spread, fees and funding.'])
    elif side * (close - e20) > 0 and side * (e20 - e50) > 0 and weekly:
        stop = max(e20, close - 2 * atr, info['low5']) if side > 0 else min(e20, close + 2 * atr, info['high5'])
        protected = cost < stop < min(price, close) if side > 0 else max(price, close) < stop < cost
        if pnl > 0 and side * (close - cost) >= atr and protected:
            base.update(action='TRAIL', candidate_stop=round(stop, 6), reasons=['Daily and prior weekly contract trends support the position; candidate level protects a gross price profit.', 'Tighten only: raise a long stop or lower a short stop. Never replace a strategy-owned stop automatically.'])
        else:
            base.update(action='HOLD', reasons=['Completed daily and prior weekly contract trends support the current position direction.', 'Reassess if a completed daily close crosses EMA20 against the position.'])
    else: base['reasons'] = ['Daily and weekly contract evidence is mixed; review the existing trade thesis.']
    return base


class FyersHoldings:
    broker = 'FYERS'
    def __init__(self, client):
        self.client = client
        self.identity = sha256(str(getattr(client, 'header', id(client))).encode()).hexdigest()

    def inventory(self):
        response = account_read(self.client, 'holdings')
        if not isinstance(response, dict) or response.get('s') != 'ok' or not isinstance(response.get('holdings'), list):
            raise ValueError('FYERS holdings could not be read. Refresh broker authentication and retry.')
        result = []
        for index, raw in enumerate(response['holdings']):
            qty = number(raw.get('remainingQuantity', raw.get('quantity')))
            if qty == 0: continue
            symbol = str(raw.get('symbol') or '')
            result.append({'id': str(index), 'symbol': symbol or 'Unresolved holding', 'quantity': qty,
                           'average_price': number(raw.get('costPrice')), 'price': None, 'quote_timestamp': None,
                           'kind': 'DELIVERY_EQUITY' if symbol.startswith(('NSE:', 'BSE:')) and symbol.endswith('-EQ') else 'OTHER_HOLDING',
                           'holding_type': raw.get('holdingType'), 'currency': 'INR',
                           'review_reason': 'This holding does not have a supported exchange equity series; manual product-specific review is required.'})
        return result

    def enrich(self, rows):
        symbols = list(dict.fromkeys(r['symbol'] for r in rows if r['kind'] == 'DELIVERY_EQUITY'))
        if not symbols: return rows
        response = quotes(self.client, {'symbols': ','.join(symbols)})
        if not isinstance(response, dict) or response.get('s') != 'ok': raise ValueError('FYERS current quotes unavailable.')
        values = {item.get('n'): item.get('v', {}) for item in response.get('d', []) if item.get('s') == 'ok'}
        for row in rows:
            quote = values.get(row['symbol'], {})
            row.update(price=number(quote.get('lp')), quote_timestamp=number(quote.get('tt')))
        return rows

    def candles(self, row, now):
        response = history(self.client, {'symbol': row['symbol'], 'resolution': 'D', 'date_format': '1',
                                        'range_from': datetime.fromtimestamp(now - 365 * 86400, IST).date().isoformat(),
                                        'range_to': datetime.fromtimestamp(now, IST).date().isoformat(), 'cont_flag': '0'})
        if not isinstance(response, dict) or response.get('s') != 'ok': raise ValueError('FYERS daily history unavailable.')
        raw = response.get('candles')
        if not isinstance(raw, list): raise ValueError('FYERS daily history schema unavailable.')
        result = []
        for candle in raw:
            if not isinstance(candle, (list, tuple)) or len(candle) < 5: raise ValueError('FYERS daily candle schema unavailable.')
            result.append(dict(zip(('timestamp', 'open', 'high', 'low', 'close'), candle[:5])))
        return result


class DeltaHoldings:
    broker = 'DELTA_INDIA'
    def __init__(self, delta):
        self.delta = delta
        self.identity = sha256(str(delta._identity()).encode()).hexdigest()

    def inventory(self):
        # Read the position endpoint directly: account() also reconciles local lifecycle journals.
        raw = self.delta._private('GET', '/v2/positions/margined').get('result')
        if not isinstance(raw, list): raise ValueError('Delta open-position snapshot unavailable.')
        result = []
        for index, position in enumerate(raw):
            size = number(position.get('size'))
            if size == 0: continue
            product = position.get('product') or {}
            result.append({'id': str(index), 'symbol': position.get('product_symbol') or product.get('symbol') or str(position.get('product_id') or 'Unresolved contract'),
                           'quantity': size, 'average_price': number(position.get('entry_price')), 'price': number(position.get('mark_price')),
                           'kind': 'DERIVATIVE_POSITION', 'currency': position.get('settling_asset_symbol') or 'Unverified settlement currency',
                           'broker_unrealized_pnl': number(position.get('unrealized_pnl')), 'quote_timestamp': None,
                           'review_reason': 'Delta position requires underlying, contract-unit, expiry, spread and strategy-ownership evidence. Cash-equity rules cannot safely classify it.'})
        return result

    def enrich(self, rows):
        for row in rows:
            try:
                product = self.delta.product(row['symbol'])
                if product.get('contract_type') not in ('perpetual_futures', 'futures') or product.get('notional_type') != 'vanilla' or product.get('is_quanto') is not False or product.get('contract_unit_currency') != product.get('underlying') or product.get('quoting_currency') != product.get('settlement_currency'):
                    continue
                quote = self.delta.ticker(row['symbol'])
                row.update(kind='LINEAR_FUTURE', contract_value=number(product.get('contract_value')),
                           price=number(quote.get('bid' if (row['quantity'] or 0) > 0 else 'ask')),
                           quote_timestamp=number(quote.get('exchange_at')), currency=product.get('settlement_currency'))
                expiry = product.get('settlement_time')
                if expiry:
                    row['expiry_timestamp'] = datetime.fromisoformat(str(expiry).replace('Z', '+00:00')).timestamp()
            except Exception:
                row['review_reason'] = 'Fresh verified linear-contract metadata or executable quote unavailable.'
                row['kind'] = 'DERIVATIVE_POSITION'
        return rows

    def candles(self, row, now):
        raw = self.delta._get('/v2/history/candles', {'symbol': row['symbol'], 'resolution': '1d', 'start': int(now - 365 * 86400), 'end': int(now)}).get('result')
        if not isinstance(raw, list): raise ValueError('Delta daily history unavailable.')
        return sorted([{'timestamp': number(r.get('time')), **{k: number(r.get(k)) for k in ('open', 'high', 'low', 'close')}} for r in raw], key=lambda r: r['timestamp'])


class HoldingsAnalysis:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.captures = {}
        self.history_cache = {}
        self.last_read = 0.0

    def pace(self):
        # Limit additional analysis reads; existing strategy traffic remains independent.
        with self.lock:
            delay = max(0, self.last_read + .4 - time.monotonic())
            if delay: time.sleep(delay)
            self.last_read = time.monotonic()

    def batch(self, adapter, capture_id=None, offset=0, limit=5, inventory_only=False):
        if type(inventory_only) is not bool or (inventory_only and offset != 0):
            raise ValueError('Inventory-only reads must start at offset zero.')
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 5:
            raise ValueError('Use a non-negative offset and a batch size of 1–5.')
        now = self.clock()
        key = (adapter.broker, adapter.identity)
        with self.lock:
            self.captures = {k: v for k, v in self.captures.items() if now - v['at'] <= 600}
            if capture_id:
                capture = self.captures.get(capture_id)
                if not capture or capture['key'] != key: raise ValueError('Holdings snapshot expired or account changed. Start a fresh analysis.')
            else:
                if offset != 0: raise ValueError('Start with the first holdings batch.')
                if any(v['key'] == key and now - v['at'] < 60 for v in self.captures.values()):
                    raise ValueError('A holdings snapshot was requested recently. Wait 60 seconds before starting again.')
                self.pace()
                rows = diagnostics.call(adapter.broker, "holdings.inventory", adapter.inventory)
                capture_id = uuid.uuid4().hex
                capture = {'key': key, 'at': self.clock(), 'rows': rows, 'results': {}, 'lock': threading.Lock(),
                           'session': market_session(datetime.fromtimestamp(now, IST))['last_completed_session']}
                if len(self.captures) >= 8: self.captures.pop(next(iter(self.captures)))
                self.captures[capture_id] = capture
        with capture['lock']:
            if offset > len(capture['rows']): raise ValueError('Batch offset exceeds this portfolio snapshot.')
            end = offset if inventory_only else min(offset + limit, len(capture['rows']))
            pending = [dict(capture['rows'][i]) for i in range(offset, end) if i not in capture['results']]
            enrichment_error = None
            try:
                if pending:
                    self.pace()
                    diagnostics.call(adapter.broker, "holdings.current_quotes", adapter.enrich, pending)
            except Exception: enrichment_error = 'Current broker quote snapshot unavailable. Retry with a new analysis after checking authentication.'
            for row in pending:
                checkpoint("Reviewing holding "+row["symbol"]+".")
                candles, failure = [], enrichment_error
                if row['kind'] in ('DELIVERY_EQUITY', 'LINEAR_FUTURE') and not failure:
                    cache_key = (key, row['symbol'], capture['session'])
                    try:
                        with self.lock: cached = self.history_cache.get(cache_key)
                        if cached and now - cached[0] < 900: candles = cached[1]
                        else:
                            self.pace()
                            candles = diagnostics.call(adapter.broker, "holdings.daily_history", adapter.candles, row, now)
                            with self.lock:
                                if len(self.history_cache) >= 500: self.history_cache.pop(next(iter(self.history_cache)))
                                self.history_cache[cache_key] = (now, candles)
                    except Exception: failure = 'Broker daily history unavailable; no recommendation produced.'
                item = diagnostics.call(adapter.broker, 'holdings.rule_analysis', review_linear, row, candles, self.clock()) if adapter.broker == 'DELTA_INDIA' else diagnostics.call(adapter.broker, 'holdings.rule_analysis', review, row, candles, capture['session'], self.clock())
                if failure:
                    item.update(action='REVIEW_NEEDED', reasons=[failure], candidate_stop=None)
                # Index IDs preserve split T1/demat rows rather than hiding holdings by symbol.
                index = next(i for i in range(offset, end) if capture['rows'][i]['id'] == row['id'])
                capture['results'][index] = item
            all_results = [capture['results'][i] for i in sorted(capture['results'])]
            priced = [r for r in all_results if r.get('kind') == 'DELIVERY_EQUITY' and number(r.get('price')) and number(r.get('quantity')) and r['quantity'] > 0]
            value = sum(r['quantity'] * r['price'] for r in priced)
            for item in all_results:
                item['priced_holdings_weight_pct'] = round(item['quantity'] * item['price'] / value * 100, 2) if value > 0 and item in priced else None
            return {'schema_version': 1, 'capture_id': capture_id, 'broker': adapter.broker,
                    'as_of': datetime.fromtimestamp(capture['at'], timezone.utc).isoformat(),
                    'generated_at': datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                    'completed_session': capture['session'], 'total': len(capture['rows']), 'analysed': len(all_results),
                    'next_offset': end if end < len(capture['rows']) else None,
                    'rows': [capture['results'][i] for i in range(offset, end)],
                    'summary': dict(Counter(r['action'] for r in all_results)),
                    'portfolio': {'priced_holdings_value': round(value, 2) if priced else None, 'currency': 'INR' if adapter.broker != 'DELTA_INDIA' else None,
                                  'priced_rows': len(priced), 'reviewed_rows': len(all_results), 'complete': len(all_results) == len(capture['rows']),
                                  'weight_basis': 'Priced delivery holdings only; provisional until every row is analysed. Derivatives excluded.'},
                    'scope': getattr(adapter,'scope',None) or ('Delivery holdings, including separate T1/demat records' if adapter.broker == 'FYERS' else 'Open derivative positions; wallet cash is not an equity holding'),
                    'policy': 'Advisory only · swing horizon assumed · completed daily/prior-week evidence · no orders or stop modifications',
                    'limitations': ['No fundamental, news, tax or portfolio suitability model.', 'Quotes and holdings are broker snapshots; quantities must be rechecked before any trade.']}
