"""Bound FYERS read-only candle requests; never retry a broker mutation."""
import requests
from fyers_apiv3 import fyersModel


def history(client, data):
    if not isinstance(client, fyersModel.FyersModel):
        return client.history(data)
    try:
        response = requests.get(
            fyersModel.Config.DATA_API + fyersModel.Config.history,
            params=data,
            headers={'Authorization': client.header, 'Content-Type': client.service.content, 'version': '3'},
            timeout=(3, 10),
        )
        response.raise_for_status()
        return response.json()
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
    if method not in ('positions', 'orderbook', 'funds', 'get_profile'):
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
