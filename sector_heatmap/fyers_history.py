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
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        raise RuntimeError('FYERS quote fallback unavailable; automatic retry pending.') from error


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
