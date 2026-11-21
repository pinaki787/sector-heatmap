"""Calendar-year price returns from completed public daily bars."""
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from functools import partial
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import requests

from .persistent_jobs import checkpoint
from .seasonality import symbol_options

INDIA = ZoneInfo('Asia/Kolkata')
YEARS = range(1, 11)
SESSION_GAP = timedelta(days=7)


def anniversary(day, years):
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # February 29 in a non-leap year.
        return day.replace(year=day.year - years, day=28)


def daily_quotes(data, provider_symbol):
    results = (data.get('chart') or {}).get('result') or []
    if len(results) != 1:
        return {}
    series = results[0]
    meta = series.get('meta', {})
    if (meta.get('symbol', '').upper() != provider_symbol
            or meta.get('instrumentType') != 'EQUITY'
            or meta.get('exchangeTimezoneName') != 'Asia/Kolkata'):
        return {}
    quotes = (series.get('indicators', {}).get('quote') or [{}])[0]
    return dict(quotes, timestamp=series.get('timestamp', []))


def valid_price(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def calculate(data, provider_symbol, cutoff):
    quotes = daily_quotes(data, provider_symbol)
    prices = {}
    for stamp, close in zip(quotes.get('timestamp', []), quotes.get('close', [])):
        if not valid_price(close):
            continue
        day = datetime.fromtimestamp(stamp, INDIA).date()
        if day <= cutoff:
            prices[day] = close
    dates = sorted(prices)
    if not dates or cutoff - dates[-1] > SESSION_GAP:
        return {}
    end = dates[-1]
    results = {}
    for years in YEARS:
        target = anniversary(end, years)
        index = bisect_right(dates, target) - 1
        if index < 0 or target - dates[index] > SESSION_GAP:
            continue
        start = dates[index]
        results[str(years)] = {
            'return_pct': (prices[end] / prices[start] - 1) * 100,
            'from_date': start.isoformat(),
            'to_date': end.isoformat(),
        }
    return results


def daily_pullback(data, provider_symbol, cutoff):
    unavailable = {'reason': 'Recent completed daily highs, lows and closes are unavailable.'}
    quotes = daily_quotes(data, provider_symbol)
    columns = (quotes.get(key, []) for key in ('timestamp', 'high', 'low', 'close'))
    recent = {}
    for stamp, high, low, close in zip(*columns):
        day = datetime.fromtimestamp(stamp, INDIA).date()
        if cutoff - timedelta(days=183) <= day <= cutoff:
            recent[day] = (high, low, close)
    days = sorted(recent)
    width = 5
    if (len(days) < 2 * width + 6 or cutoff - days[-1] > SESSION_GAP
            or any(not all(map(valid_price, bar)) or not bar[1] <= bar[2] <= bar[0]
                   for bar in recent.values())):
        return unavailable
    highs, lows, closes = zip(*(recent[day] for day in days))
    low_index = None
    swing = None
    for i in range(width, len(days) - width):
        neighbors = range(i - width, i + width + 1)
        pivot_low = all(lows[i] < lows[j] for j in neighbors if j != i)
        pivot_high = all(highs[i] > highs[j] for j in neighbors if j != i)
        if pivot_high and low_index is not None:
            swing = (low_index, i)
        if pivot_low:
            low_index = i
    confirmed = False
    if swing is not None:
        start, end = swing
        low, high = lows[start], highs[end]
        confirmed = (high > low and min(lows[start + 1:]) > low
                     and max(highs[start:end + 1]) <= high
                     and max(highs[end + 1:]) <= high)
    if not confirmed:
        if low_index is None:
            return {'reason': 'No confirmed daily swing low in the last six months.'}
        start = low_index
        low = lows[start]
        if min(lows[start + 1:]) <= low:
            return {'reason': 'Price reached the swing low. Waiting for a new confirmed daily low.'}
        end = max(range(start + 1, len(days)), key=lambda i: (highs[i], i))
        high = highs[end]
        if high <= low:
            return {'reason': 'No daily advance above the confirmed swing low.'}
    return {
        'price_50': high - 0.50 * (high - low),
        'price_56': high - 0.56 * (high - low),
        'swing_high_status': 'CONFIRMED' if confirmed else 'DEVELOPING',
        'swing_low': low,
        'swing_high': high,
        'swing_low_date': days[start].isoformat(),
        'swing_high_date': days[end].isoformat(),
        'as_of': days[-1].isoformat(),
    }


def load(row, cache, now):
    symbol = row['symbol']
    try:
        if not row.get('market_bar_at'):
            return {}
        _, provider_symbol = symbol_options({'symbol': symbol})
        captured = datetime.fromtimestamp(now, INDIA)
        cutoff = datetime.fromisoformat(row['market_bar_at']).astimezone(INDIA).date()
        # Exclude the current session until the normal NSE session is closed.
        if captured.time() < time(15, 30):
            cutoff = min(cutoff, captured.date() - timedelta(days=1))
        else:
            cutoff = min(cutoff, captured.date())
        key = hashlib.sha256(f'daily-pullback-v3:{provider_symbol}:{cutoff}'.encode()).hexdigest()
        path = cache / (key + '.json')
        if path.is_file() and 0 <= now - path.stat().st_mtime < 6 * 3600:
            return json.loads(path.read_text())
        begin = anniversary(cutoff, 10) - timedelta(days=21)
        period1 = int(datetime.combine(begin, time.min, INDIA).timestamp())
        period2 = int(datetime.combine(cutoff + timedelta(days=1), time.min, INDIA).timestamp())
        response = requests.get(
            'https://query1.finance.yahoo.com/v8/finance/chart/' + requests.utils.quote(provider_symbol, safe=''),
            params={'period1': period1, 'period2': period2, 'interval': '1d'},
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=(4, 12),
        )
        response.raise_for_status()
        data = response.json()
        annual_returns = calculate(data, provider_symbol, cutoff)
        values = {
            'annual_returns': annual_returns,
            'daily_pullback': daily_pullback(data, provider_symbol, cutoff),
        }
        if annual_returns or 'price_50' in values['daily_pullback']:
            temporary = path.with_suffix('.' + uuid4().hex + '.tmp')
            try:
                temporary.write_text(json.dumps(values))
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        return values
    except (requests.RequestException, OSError, ValueError, TypeError, KeyError, OverflowError):
        return {}


def enrich(workspace, result, now):
    cache = Path(workspace) / 'data' / 'investment-returns'
    cache.mkdir(parents=True, exist_ok=True)
    unique = {row['symbol']: row for row in result['rows'] + result['audit'] if row.get('market_bar_at')}
    rows = iter(unique.values())
    total = len(unique)
    done = 0
    # Submit one batch at a time so cancellation does not leave an entire
    # shortlist of requests queued.
    with ThreadPoolExecutor(max_workers=4) as pool:
        while batch := [row for _, row in zip(range(4), rows)]:
            checkpoint(f'Checking daily swings and annual returns for {done} of {total} symbols.')
            for row, values in zip(batch, pool.map(partial(load, cache=cache, now=now), batch)):
                row['annual_returns'] = values.get('annual_returns', {})
                row['daily_pullback'] = values.get('daily_pullback', {
                    'reason': 'Completed daily market history could not be loaded.',
                })
                done += 1
            checkpoint(f'Checked daily swings and annual returns for {done} of {total} symbols.', result)
