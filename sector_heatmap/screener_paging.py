"""Validated paging for advisory scans; never silently drops requested symbols."""
import json

MAX_SYMBOLS = 1000
BATCH_SIZE = 12

def page_request(payload):
    raw = payload.get("symbols")
    symbols = list(dict.fromkeys(str(value).strip().upper() for value in raw if str(value).strip())) if isinstance(raw, list) else []
    if len(symbols) > MAX_SYMBOLS:
        raise ValueError(f"Select at most {MAX_SYMBOLS} symbols per scan.")
    offset = max(0, int(payload.get("offset") or 0))
    limit = min(BATCH_SIZE, max(1, int(payload.get("limit") or BATCH_SIZE)))
    page = symbols[offset:offset + limit]
    prices = payload.get("prices") if isinstance(payload.get("prices"), dict) else {}
    cache_key = (tuple(symbols), offset, limit, json.dumps({s:prices.get(s) for s in page}, sort_keys=True))
    return symbols, offset, limit, page, prices, cache_key
