"""Bound FYERS read-only candle requests; never retry a broker mutation."""
import requests
import hashlib, math, threading, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from fyers_apiv3 import fyersModel


class FyersHistoryAuthenticationRequired(RuntimeError):
    pass


class FyersHistoryRateLimited(RuntimeError):
    def __init__(self, retry_after):
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__(f"FYERS historical data is rate-limited or restricted by the account plan. Wait at least {self.retry_after} seconds before retrying; the broker session was not renewed.")


_HISTORY_COOLDOWNS = {}
_HISTORY_COOLDOWN_LOCK = threading.Lock()


def _retry_seconds(response):
    headers = getattr(response, "headers", {}) or {}
    candidates = []
    for key, factor in (("Retry-After", 1), ("X-Retry-After-Ms", .001)):
        raw = headers.get(key)
        try:
            value = float(raw) * factor
            if math.isfinite(value) and value >= 0:
                candidates.append(value)
        except (TypeError, ValueError):
            if key == "Retry-After" and isinstance(raw, str):
                try:
                    stamp = parsedate_to_datetime(raw)
                    if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone.utc)
                    candidates.append(max(0, stamp.timestamp()-time.time()))
                except (TypeError, ValueError, OverflowError): pass
    return min(86400, max(1, math.ceil(max(candidates, default=60))))


def _history_budget_key(client):
    # A token refresh has a distinct scope; no credential text is stored or logged.
    return hashlib.sha256(str(client.header).encode()).digest()


def _check_history_cooldown(key):
    now = time.monotonic()
    with _HISTORY_COOLDOWN_LOCK:
        for old, until in list(_HISTORY_COOLDOWNS.items()):
            if until <= now: _HISTORY_COOLDOWNS.pop(old, None)
        until = _HISTORY_COOLDOWNS.get(key, 0)
    if until > now: raise FyersHistoryRateLimited(until-now)


def _limit_history(key, response):
    seconds = _retry_seconds(response)
    with _HISTORY_COOLDOWN_LOCK:
        if len(_HISTORY_COOLDOWNS) >= 256 and key not in _HISTORY_COOLDOWNS:
            _HISTORY_COOLDOWNS.pop(min(_HISTORY_COOLDOWNS, key=_HISTORY_COOLDOWNS.get), None)
        _HISTORY_COOLDOWNS[key] = max(_HISTORY_COOLDOWNS.get(key, 0), time.monotonic()+seconds)
    raise FyersHistoryRateLimited(seconds)


def history(client, data):
    if not isinstance(client, fyersModel.FyersModel):
        return client.history(data)
    key = _history_budget_key(client)
    _check_history_cooldown(key)
    transport = getattr(client, '_sector_pulse_ipv4_session', requests)
    try:
        response = transport.get(
            fyersModel.Config.DATA_API + fyersModel.Config.history,
            params=data,
            headers={'Authorization': client.header, 'Content-Type': client.service.content, 'version': '3'},
            timeout=(3, 10),
        )
        if response.status_code == 429:
            _limit_history(key, response)
        if response.status_code == 401:
            raise FyersHistoryAuthenticationRequired("FYERS history requires authentication.")
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and result.get('code') in {429, -429, -360}:
            _limit_history(key, response)
        return result
    except requests.Timeout as error:
        raise RuntimeError('FYERS candle history timed out; automatic retry will use fresh candles.') from error
    except requests.RequestException as error:
        raise RuntimeError('FYERS candle history connection failed; automatic retry pending.') from error


def quotes(client, data):
    if not isinstance(client, fyersModel.FyersModel):
        return client.quotes(data)
    try:
        response = requests.get(
            fyersModel.Config.DATA_API + fyersModel.Config.quotes,
            params=data,
            headers={'Authorization': client.header, 'Content-Type': client.service.content, 'version': '3'},
            timeout=(3, 10),
        )
        if response.status_code == 429:
            raise RuntimeError('FYERS quote requests are rate-limited. Wait a few minutes before preparing a fresh preview.')
        if response.status_code in (401, 403):
            raise RuntimeError('FYERS quote authentication or access was rejected. Check this account connection before preparing a preview.')
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError as error:
            raise RuntimeError('FYERS returned an unreadable quote response. A fresh preview is required; no order was submitted.') from error
        if isinstance(result, dict) and result.get('code') in (-429, 429):
            raise RuntimeError('FYERS quote requests are rate-limited. Wait a few minutes before preparing a fresh preview.')
        return result
    except requests.Timeout as error:
        raise RuntimeError('FYERS quote request timed out. Prepare a fresh preview when connectivity recovers.') from error
    except requests.RequestException as error:
        raise RuntimeError('FYERS quote request failed. A fresh successful quote is required before order review.') from error


def account_read(client, method):
    """Only bounded, read-only account endpoints; mutations cannot use this path."""
    if method not in ('positions', 'holdings', 'orderbook', 'funds', 'get_profile'):
        raise ValueError('Unsupported read-only FYERS endpoint.')
    if not isinstance(client, fyersModel.FyersModel):
        return getattr(client, method)()
    try:
        response = requests.get(
            fyersModel.Config.API + getattr(fyersModel.Config, method),
            headers={'Authorization': client.header, 'Content-Type': client.service.content, 'version': '3'},
            timeout=(3, 10),
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        raise ValueError('FYERS account read unavailable; execution blocked pending a fresh successful check.') from error
