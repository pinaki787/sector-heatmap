"""Read-only last-traded-price display for an already resolved parser contract."""
from datetime import datetime
import math
import time
import threading

_rate_lock = threading.Lock()
_retry_after = 0.0
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo('Asia/Kolkata')


def fetch_parser_quote(symbol, token, get=requests.get, now=None):
    global _retry_after
    fetched = now or datetime.now(IST)
    unavailable = {'status': 'UNAVAILABLE', 'symbol': symbol, 'ltp': None,
                   'fetched_at': fetched.isoformat(), 'provider_timestamp': None,
                   'freshness': 'UNKNOWN', 'message': 'FYERS LTP unavailable.'}
    if not token or ':' not in token:
        return {**unavailable, 'message': 'FYERS LTP unavailable: broker connection is missing.'}
    with _rate_lock:
        wait = math.ceil(_retry_after - time.monotonic())
    if wait > 0:
        return {**unavailable, 'reason': 'RATE_LIMITED', 'retry_after_seconds': wait,
                'message': f'FYERS LTP rate-limited (HTTP 429). Retry after {wait} seconds.'}
    try:
        response = get('https://api-t1.fyers.in/data/quotes', headers={'Authorization': token},
                       params={'symbols': symbol}, timeout=8)
        if response.status_code == 429:
            try:
                delay = max(60, min(3600, int(response.headers.get('Retry-After', 60))))
            except (TypeError, ValueError):
                delay = 60
            with _rate_lock:
                _retry_after = time.monotonic() + delay
            return {**unavailable, 'reason': 'RATE_LIMITED', 'retry_after_seconds': delay,
                    'message': f'FYERS LTP rate-limited (HTTP 429). Retry after {delay} seconds.'}
        if response.status_code in (401, 403):
            return {**unavailable, 'reason': 'AUTHORIZATION', 'message': 'FYERS LTP request denied. Check broker authentication/access.'}
        response.raise_for_status()
        data = response.json()
        if data.get('s') != 'ok':
            return unavailable
        item = next((item for item in data.get('d', []) if item.get('n') == symbol and item.get('s') == 'ok'), None)
        values = item.get('v') or {} if item else {}
        ltp = float(values.get('lp'))
        if not math.isfinite(ltp) or ltp <= 0:
            return unavailable
        fetched = now or datetime.now(IST)
        stamp = None
        try:
            raw = float(values.get('tt'))
            if math.isfinite(raw) and raw > 0:
                stamp = datetime.fromtimestamp(raw / 1000 if raw > 1e12 else raw, IST)
        except (ValueError, TypeError, OverflowError, OSError):
            pass
        age = (fetched - stamp).total_seconds() if stamp else None
        freshness = 'FRESH' if age is not None and -5 <= age <= 30 else 'UNCONFIRMED'
        return {'status': 'READY', 'symbol': symbol, 'ltp': ltp,
                'fetched_at': fetched.isoformat(), 'provider_timestamp': stamp.isoformat() if stamp else None,
                'provider_age_seconds': max(0, round(age)) if age is not None else None,
                'freshness': freshness,
                'message': 'FYERS timestamp is within 30 seconds.' if freshness == 'FRESH' else 'Freshness unconfirmed: FYERS timestamp is old, missing or in the future.'}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return unavailable
