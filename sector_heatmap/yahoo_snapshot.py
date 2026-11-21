"""Provider-stamped, provisional calendar snapshots; never completed history."""
from datetime import datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re


def calendar_snapshot(timestamps, values, interval, source_interval, metadata, now, *, before=None):
    if before is not None or not re.fullmatch(r'[1-9][0-9]{0,2}[WM]', interval):
        return None
    if source_interval not in ('1W', '1M') or source_interval[-1] != interval[-1]:
        return None
    try:
        zone = ZoneInfo(metadata.get('exchangeTimezoneName'))
        as_of = float(metadata.get('regularMarketTime'))
        if not isfinite(as_of) or as_of <= 0 or as_of > now:
            return None
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return None
    from .chart_workspace import calendar_bounds
    def utc_day(local):
        return int(datetime(local.year, local.month, local.day, tzinfo=timezone.utc).timestamp())
    def exchange_time(day):
        return int(datetime.fromtimestamp(day, timezone.utc).replace(tzinfo=zone).timestamp())
    start, end = calendar_bounds(utc_day(datetime.fromtimestamp(now, zone)), interval, nse=False)
    parts = {}
    for index, stamp in enumerate(timestamps):
        try:
            if not isinstance(stamp, (int, float)) or not isfinite(stamp) or stamp > as_of:
                continue
            local = datetime.fromtimestamp(stamp, zone)
            if local.hour or local.minute or local.second:
                continue  # Yahoo's appended quote is not another source period.
            if (source_interval == '1W' and local.weekday() != 0) or (source_interval == '1M' and local.day != 1):
                continue
            day = utc_day(local)
            if not start <= day < end:
                continue
            o, h, l, c = [float(values[key][index]) for key in ('open', 'high', 'low', 'close')]
            if not all(isfinite(x) for x in (o, h, l, c)) or not 0 < l <= min(o,c) <= max(o,c) <= h:
                return None
            volume = (values.get('volume') or [None] * len(timestamps))[index]
            volume = float(volume) if volume is not None else None
            if volume is not None and (not isfinite(volume) or volume < 0):
                volume = None
            row = [o,h,l,c,volume]
            if day in parts and parts[day] != row:
                return None
            parts[day] = row
        except (ValueError, TypeError, IndexError, KeyError, OverflowError, OSError):
            return None
    days = sorted(parts)
    if not days or days[0] != start:
        return None
    expected=[];day=start
    while day <= days[-1]:
        expected.append(day)
        day=calendar_bounds(day, source_interval, nse=False)[1]
    if days != expected:
        return None
    source_end = exchange_time(day)
    observed = int(min(as_of, source_end))
    opening, closing = exchange_time(start), exchange_time(end)
    if observed < exchange_time(days[-1]) or closing <= now:
        return None
    rows=[parts[day] for day in days]
    volumes=[row[4] for row in rows]
    return {'bar':[opening,rows[0][0],max(r[1] for r in rows),min(r[2] for r in rows),rows[-1][3],
                   sum(volumes) if all(v is not None for v in volumes) else None],
            'as_of':observed,'close_time':closing,'source_interval':source_interval,
            'provider':'Yahoo Finance','provisional':True,'history_only':True}
