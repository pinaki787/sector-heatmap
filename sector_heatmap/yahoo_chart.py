"""Yahoo Finance historical OHLC for the analytical chart."""

from bisect import bisect_right
from datetime import datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
import time
from urllib.parse import quote

import requests

CUSTOM_HOURS = {"360", "840", "1320", "1380"}
AGGREGATED_INTRADAY = {"3": "1", "10": "5", "45": "15", "120": "60", "180": "60", "240": "60"}
REGULAR_SESSION_TYPES = {"EQUITY", "ETF", "INDEX"}
CUSTOM_MINUTES_MAX = 1440
CALENDAR_LIMITS = {"D": 365, "W": 52, "M": 12}

INTERVALS = {
    "1": ("1m", "5d", 60),
    "2": ("2m", "1mo", 120),
    "5": ("5m", "1mo", 300),
    "15": ("15m", "1mo", 900),
    "30": ("30m", "1mo", 1800),
    "60": ("60m", "1mo", 3600),
    "1D": ("1d", "5y", 86400),
    "1W": ("1wk", "5y", 604800),
    "1M": ("1mo", "5y", None),
}


def regular_sessions(periods):
    if isinstance(periods, dict):
        periods = periods.get("regular")
    return sorted({
        (entry["start"], entry["end"])
        for group in (periods or [])
        if isinstance(group, list)
        for entry in group
        if isinstance(entry, dict) and isinstance(entry.get("start"), int)
        and isinstance(entry.get("end"), int) and entry["end"] > entry["start"]
    })


def aggregate_regular_sessions(rows, periods, minutes, native_seconds, now):
    """Aggregate only complete regular-session Yahoo candles, including short closes."""
    sessions = regular_sessions(periods)
    if not sessions:
        raise ValueError("Yahoo Finance did not provide regular-session boundaries for this ticker.")
    opens = [start for start, _ in sessions]
    groups = {}
    seconds = minutes * 60
    for row in rows:
        stamp = row[0]
        index = bisect_right(opens, stamp) - 1
        if index < 0:
            continue
        start, close = sessions[index]
        if stamp >= close or (stamp - start) % native_seconds:
            continue
        opening = start + (stamp - start) // seconds * seconds
        end = min(opening + seconds, close)
        groups.setdefault((opening, end), []).append(row)
    result, close_times = [], {}
    for (opening, end), parts in sorted(groups.items()):
        if end > now or [row[0] for row in parts] != list(range(opening, end, native_seconds)):
            continue
        volumes = [row[5] for row in parts]
        result.append([opening, parts[0][1], max(row[2] for row in parts), min(row[3] for row in parts),
                       parts[-1][4], sum(volumes) if all(v is not None for v in volumes) else None])
        if end != opening + seconds:
            close_times[opening] = end
    return result, close_times


def aggregate_calendar(rows, interval, exchange_timezone, now, crypto, regular_close=None):
    from .chart_workspace import calendar_bounds

    try:
        zone = ZoneInfo(exchange_timezone)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        raise ValueError("Yahoo Finance did not provide an exchange time zone for this ticker.") from None
    unit = interval[-1]
    length = int(interval[:-1])
    last_friday = None
    if interval == "1W" and not crypto and isinstance(regular_close, int):
        end_local = datetime.fromtimestamp(regular_close, zone)
        if end_local.weekday() == 4:
            last_friday = int(datetime(end_local.year, end_local.month, end_local.day,
                                       tzinfo=timezone.utc).timestamp())
    groups = {}
    for row in rows:
        local = datetime.fromtimestamp(row[0], zone)
        # Weekly and monthly source bars open at local midnight. Yahoo may
        # append a separate quote snapshot which must never supply a period.
        if unit != "D" and (local.hour or local.minute or local.second
                            or (unit == "W" and local.weekday() != 0)
                            or (unit == "M" and local.day != 1)):
            continue
        day = int(datetime(local.year, local.month, local.day, tzinfo=timezone.utc).timestamp())
        start, end = calendar_bounds(day, interval, nse=False)
        groups.setdefault((start, end), {})[day] = row
    result, close_times = [], {}
    for index, ((start, end), grouped) in enumerate(sorted(groups.items())):
        stamps = sorted(grouped)
        if (unit != "D" or crypto) and len(stamps) != length:
            continue
        # The leading Yahoo date range may begin in the middle of a bucket.
        if unit == "D" and not crypto and index == 0 and stamps[0] != start:
            continue
        opening = int(datetime.fromtimestamp(start, timezone.utc).replace(tzinfo=zone).timestamp())
        boundary = int(datetime.fromtimestamp(end, timezone.utc).replace(tzinfo=zone).timestamp())
        if last_friday is not None and start <= last_friday < end:
            boundary = regular_close
        if boundary > now:
            continue
        parts = [grouped[stamp] for stamp in stamps]
        volumes = [row[5] for row in parts]
        result.append([opening, parts[0][1], max(row[2] for row in parts), min(row[3] for row in parts),
                       parts[-1][4], sum(volumes) if all(v is not None for v in volumes) else None])
        close_times[opening] = boundary
    return result, close_times


def history(symbol, interval, now=None, *, before=None):

    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=\-]{0,29}", symbol):
        raise ValueError("Enter a valid Yahoo Finance ticker.")
    metadata_only = interval == "capabilities"
    calendar = re.fullmatch(r"([1-9][0-9]{0,2})([DWM])", interval)
    custom_calendar = bool(calendar and 1 < int(calendar[1]) <= CALENDAR_LIMITS[calendar[2]])
    aggregate = interval in CUSTOM_HOURS
    aggregate_native = AGGREGATED_INTRADAY.get(interval)
    arbitrary = not aggregate and not aggregate_native and interval not in INTERVALS and bool(
        re.fullmatch(r"[1-9][0-9]{0,3}", interval) and int(interval) <= CUSTOM_MINUTES_MAX
    )
    if arbitrary:
        minutes = int(interval)
        aggregate_native = next(str(size) for size in (60, 30, 15, 5, 2, 1) if minutes % size == 0)
    if interval not in INTERVALS and not aggregate and not aggregate_native and not custom_calendar and not metadata_only:
        raise ValueError("This interval is unavailable from Yahoo Finance.")
    source_interval = "1" + calendar[2] if custom_calendar else "60" if aggregate else "1D" if metadata_only else aggregate_native or interval
    native, span, seconds = INTERVALS[source_interval]
    if metadata_only:
        span = "5d"
    elif aggregate:
        span = "1y"
    now = time.time() if now is None else now
    params = {"interval": native, "range": span, "includePrePost": "false"}
    calendar_history = bool(calendar and (interval in INTERVALS or custom_calendar))
    if before is not None:
        from .chart_workspace import validate_chart_cursor

        before = validate_chart_cursor(before, now, max_age_days=None)
        if not calendar_history or before <= 0:
            raise ValueError("Older Yahoo Finance history requires a calendar interval and a positive cursor.")
        params.pop("range")
        params.update(period1=max(0, before - 5 * 366 * 86400), period2=before)
        now = before
    response = requests.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol, safe=""),
        params=params,
        headers={"User-Agent": "Mozilla/5.0"}, timeout=(4, 12),
    )
    if before is not None and response.status_code == 400:
        error = (response.json().get("chart") or {}).get("error") or {}
        if str(error.get("description", "")).startswith("Data doesn't exist for startDate"):
            return {"provider": "Yahoo Finance", "symbol": symbol, "rows": [],
                    "close_times": {}, "older_history": False}
    if response.status_code == 404:
        raise ValueError("Yahoo Finance did not find this ticker.")
    response.raise_for_status()
    data = response.json()["chart"]["result"][0]
    metadata = data.get("meta", {})
    instrument_type = metadata.get("instrumentType")
    crypto = instrument_type == "CRYPTOCURRENCY"
    custom_supported = crypto or instrument_type in REGULAR_SESSION_TYPES
    exchange_timezone = metadata.get("exchangeTimezoneName")
    try:
        ZoneInfo(exchange_timezone)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        exchange_timezone = None
    if metadata_only:
        return {"provider": "Yahoo Finance", "symbol": symbol,
                "custom_hours": sorted(CUSTOM_HOURS, key=int) if custom_supported else [],
                "custom_minutes_max": CUSTOM_MINUTES_MAX if custom_supported else 0,
                "custom_calendar": bool(exchange_timezone),
                "aggregated_intraday": sorted(AGGREGATED_INTRADAY, key=int),
                "exchange_timezone": exchange_timezone,
                "instrument_type": instrument_type}
    if (aggregate or arbitrary) and not custom_supported:
        raise ValueError("These Yahoo Finance intervals require equity, ETF, index, or cryptocurrency history.")
    native_calendar = interval in ("1W", "1M") and exchange_timezone is not None
    timestamps = data["timestamp"]
    values = data["indicators"]["quote"][0]
    rows = []
    close_times = {}
    native_sessions = regular_sessions(metadata.get("tradingPeriods")) if (
        interval.isdecimal() and interval in INTERVALS and instrument_type in REGULAR_SESSION_TYPES
    ) else []
    native_opens = [opening for opening, _ in native_sessions]
    for index, stamp in enumerate(timestamps):
        if before is not None and stamp >= before:
            continue
        closing_time = stamp + seconds if seconds else None
        if native_sessions:
            session_index = bisect_right(native_opens, stamp) - 1
            if session_index >= 0 and stamp < native_sessions[session_index][1]:
                closing_time = min(closing_time, native_sessions[session_index][1])
        if index + 1 == len(timestamps) and not (
            aggregate_native or custom_calendar or native_calendar or (aggregate and not crypto)
        ):
            if closing_time is not None:
                boundary = closing_time
            else:
                date = datetime.fromtimestamp(stamp, timezone.utc)
                boundary = datetime(date.year + (date.month == 12), date.month % 12 + 1, 1,
                                    tzinfo=timezone.utc).timestamp() + 86400
            if now < boundary:
                continue
        prices = [values[key][index] for key in ("open", "high", "low", "close")]
        if any(value is None or not isfinite(value) for value in prices):
            continue
        opening, high, low, close = prices
        if not low <= min(opening, close) <= max(opening, close) <= high:
            continue
        volume = (values.get("volume") or [None] * len(timestamps))[index]
        rows.append([stamp, opening, high, low, close, volume])
        if native_sessions and closing_time < stamp + seconds:
            close_times[stamp] = closing_time
    if custom_calendar or native_calendar:
        regular = (metadata.get("currentTradingPeriod") or {}).get("regular") or {}
        session_close = regular.get("end") if instrument_type in REGULAR_SESSION_TYPES else None
        rows, close_times = aggregate_calendar(rows, interval, exchange_timezone, now, crypto, session_close)
    elif crypto and (aggregate or aggregate_native):
        from .chart_workspace import combine_bars

        width = int(interval) * 60
        rows = combine_bars(rows, int(interval), seconds // 60, now=now, nse=False, utc_daily=True)
        for opening, *_ in rows:
            midnight = opening - opening % 86400 + 86400
            if midnight < opening + width:
                close_times[opening] = midnight
    elif aggregate or aggregate_native:
        rows, close_times = aggregate_regular_sessions(rows, metadata.get("tradingPeriods"), int(interval), seconds, now)
    result = {"provider": "Yahoo Finance", "symbol": symbol, "rows": rows, "close_times": close_times}
    if calendar_history and before is None and interval.endswith(('W', 'M')):
        from .yahoo_snapshot import calendar_snapshot
        snapshot = calendar_snapshot(timestamps, values, interval, source_interval, metadata, now)
        if snapshot and snapshot['bar'][0] not in {row[0] for row in rows}:
            result['forming_snapshot'] = snapshot
            close_times[snapshot['bar'][0]] = snapshot['close_time']
    if calendar_history:
        result["older_history"] = bool(rows) and rows[0][0] > 0
    return result


def search_symbols(query):
    query = query.strip()
    if not 2 <= len(query) <= 60:
        return []
    response = requests.get(
        "https://query1.finance.yahoo.com/v1/finance/search",
        params={"q": query, "quotesCount": 12, "newsCount": 0},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=(4, 8),
    )
    response.raise_for_status()
    symbols = {}
    for row in response.json().get("quotes", []):
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=\-]{0,29}", symbol):
            continue
        label = row.get("shortname") or row.get("longname") or symbol
        exchange = row.get("exchDisp")
        symbols.setdefault(symbol, {"symbol": symbol, "name": str(label)[:100],
                                    "exchange": str(exchange or "")[:40]})
    return list(symbols.values())[:12]


def serve(handler, auth):
    from urllib.parse import parse_qs, urlsplit
    from .chart_workspace import require_chart

    try:
        user = auth.authorize(handler.headers)
        require_chart(user, auth.store, "/api/chart-workspace/yahoo-history")
        query = parse_qs(urlsplit(handler.path).query)
        if query.get("interval") == ["availability"]:
            handler.send_json(200, {"provider": "Yahoo Finance"})
            return
        if query.get("interval") == ["search"]:
            result = {"symbols": search_symbols((query.get("q") or [""])[0])}
        else:
            before_values = query.get("before", [])
            if len(before_values) > 1 or (before_values and query.get("after")):
                raise ValueError("Use one Yahoo Finance history cursor.")
            result = history((query.get("symbol") or ["^NSEI"])[0],
                             (query.get("interval") or ["1D"])[0],
                             before=before_values[0] if before_values else None)
    except PermissionError as error:
        handler.send_json(403, {"error": str(error)})
    except ValueError as error:
        handler.send_json(400, {"error": str(error)})
    except (requests.RequestException, KeyError, IndexError, TypeError):
        handler.send_json(503, {"error": "Yahoo Finance history is temporarily unavailable."})
    else:
        handler.send_json(200, result)
