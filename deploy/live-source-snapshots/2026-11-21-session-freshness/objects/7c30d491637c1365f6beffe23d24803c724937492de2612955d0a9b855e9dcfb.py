"""Selected-broker candle history and WebSocket aggregation for chart analysis."""

from datetime import date, datetime, timedelta, timezone
from math import isfinite
import re
from threading import Lock
import time
from urllib.parse import parse_qs, urlsplit

from .section_permissions import allowed
from .dhan_execution import DhanAPIError
from .fyers_history import FyersHistoryAuthenticationRequired


def chart_minutes(interval):
    if not interval.isascii() or not interval.isdigit() or len(interval) > 4:
        raise ValueError("The selected broker chart requires a minute or hour interval.")
    minutes = int(interval)
    if not 1 <= minutes <= 1440 or str(minutes) != interval:
        raise ValueError("Choose an interval from 1 to 1,440 minutes.")
    return minutes


CALENDAR_LIMITS = {"D": 365, "W": 52, "M": 12}


def trade_interval(interval):
    return bool(re.fullmatch(r"(?:[1-9][0-9]{0,2}S|(?:1|10|100|1000)T)", interval)
                and (interval.endswith("T") or int(interval[:-1]) <= 299))


def chart_interval(interval):
    if trade_interval(interval):
        return interval
    match = re.fullmatch(r"([1-9][0-9]{0,2})([DWM])", interval)
    if match:
        length, unit = match.groups()
        if int(length) <= CALENDAR_LIMITS[unit]:
            return interval
        raise ValueError(f"Choose a calendar interval from 1 to {CALENDAR_LIMITS[unit]} {unit}.")
    return chart_minutes(interval)


def calendar_bounds(stamp, interval, nse):
    shift = 19800 if nse else 0
    day = datetime.fromtimestamp(stamp + shift, timezone.utc).date()
    length, unit = int(interval[:-1]), interval[-1]
    if unit == "M":
        month_index = day.year * 12 + day.month - 1
        first = month_index - month_index % length
        start_year, start_month = divmod(first, 12)
        end_year, end_month = divmod(first + length, 12)
        start = date(start_year, start_month + 1, 1)
        end = date(end_year, end_month + 1, 1)
    else:
        anchor = date(1970, 1, 5) if unit == "W" else date(1970, 1, 1)
        days = length * (7 if unit == "W" else 1)
        start = day - timedelta(days=(day - anchor).days % days)
        end = start + timedelta(days=days)
    return tuple(int(datetime.combine(value, datetime.min.time(), timezone.utc).timestamp()) - shift
                 for value in (start, end))


def calendar_history(daily, interval, now, after, nse=True, *, first_trading_day=None):
    """Build calendar candles from selected-broker daily OHLC."""
    groups = {}
    cursor = int(after) if after is not None else None
    for row in daily:
        start, end = calendar_bounds(row[0], interval, nse)
        if interval == "1D" and nse:
            end = start + 55800
        if cursor is None or start > cursor:
            groups.setdefault((start, end), []).append(row)
    rows, prefix = [], None
    oldest_start = calendar_bounds(daily[0][0], interval, nse)[0] if daily else None
    for (start, end), parts in sorted(groups.items()):
        if nse and cursor is None and start == oldest_start and start != parts[0][0]:
            continue
        expected = range(max(start, first_trading_day or start), min(end, int(now // 86400) * 86400), 86400)
        if not nse and [row[0] for row in parts] != list(expected):
            continue
        volumes = [row[5] for row in parts]
        candle = [start, parts[0][1], max(row[2] for row in parts), min(row[3] for row in parts),
                  parts[-1][4], sum(volumes) if all(v is not None for v in volumes) else None]
        if end <= now:
            rows.append(candle)
        else:
            prefix = {"bar": candle, "through": parts[-1][0]}
    return {"rows": rows, "prefix": prefix}


def calendar_live(daily, interval, nse=True):
    return [[calendar_bounds(row[0], interval, nse)[0], *row[1:], row[0]] for row in daily]


def history_payload(result):
    return result if isinstance(result, dict) else {"rows": result}


def nse_daily(rows, now):
    normalized = {}
    for row in rows:
        if len(row) < 5 or not all(isinstance(v, (int, float)) and isfinite(v) for v in row[:5]):
            continue
        stamp, opening, high, low, close = row[:5]
        session, _ = calendar_bounds(stamp, "1D", True)
        if session + 55800 <= now and 0 < low <= min(opening, close) <= max(opening, close) <= high:
            volume = row[5] if len(row) > 5 else None
            if not isinstance(volume, (int, float)) or not isfinite(volume) or volume < 0:
                volume = None
            normalized[session] = [session, opening, high, low, close, volume]
    return [normalized[key] for key in sorted(normalized)]


def combine_bars(rows, minutes, native, now=None, cursor=None, nse=True, *, utc_daily=False):
    """Combine broker bars, requiring all constituent candles for completed history."""
    seconds = minutes * 60
    groups = {}
    for row in rows:
        stamp = int(row[0])
        elapsed = (stamp + 19800) % 86400 - 33300 if nse else stamp
        if utc_daily:
            elapsed = stamp % 86400
        opening = stamp - elapsed % seconds
        end = min(opening + seconds, stamp - elapsed + 22500) if nse else opening + seconds
        if utc_daily:
            end = min(end, stamp - elapsed + 86400)
        if cursor is None or opening > cursor:
            groups.setdefault((opening, end), []).append(row)
    result = []
    for (opening, end), parts in sorted(groups.items()):
        expected_end = end if now is not None else int(parts[-1][0]) + native * 60
        if (now is not None and end > now) or [row[0] for row in parts] != list(range(opening, expected_end, native * 60)):
            continue
        volumes = [row[5] for row in parts]
        result.append([opening, parts[0][1], max(row[2] for row in parts), min(row[3] for row in parts),
                       parts[-1][4], sum(volumes) if all(v is not None for v in volumes) else None])
    return result


def require_chart(user, store, path):
    if not user or not store or not allowed(user, path):
        raise PermissionError("Chart workspace permission required.")
    if not store.sidebar_visibility().get("chart-workspace", False):
        raise PermissionError("Chart workspace is hidden.")


CHART_CALENDAR_LOOKBACK_DAYS = 1700


def validate_chart_cursor(value, now=None):
    if value is None:
        return None
    now = time.time() if now is None else now
    if not re.fullmatch(r"[0-9]{1,12}", str(value)) or int(value) > now:
        raise ValueError("History cursor must be a non-negative Unix timestamp at or before the current time.")
    stamp = int(value)
    if stamp < now - (CHART_CALENDAR_LOOKBACK_DAYS + 366) * 86400:
        raise ValueError("History cursor predates the supported chart lookback.")
    return stamp


class ChartAuthenticationRequired(RuntimeError):
    pass


def chart_auth_failure(handler, error, broker):
    auth_required = not isinstance(error, DhanAPIError) or error.reauthentication_required
    if auth_required:
        handler.send_json(401, {"error": f"Reconnect {broker} in Accounts to resume chart data.",
                                "auth_required": True})
    else:
        handler.send_json(503, {"error": "Selected broker market data is unavailable."})


def requested_chart_symbol(query, broker):
    values = query.get("symbol")
    if values is None:
        return None
    if broker != "DELTA_INDIA" or len(values) != 1 or not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,79}", values[0]):
        raise ValueError("Unsupported chart instrument for the selected broker.")
    return values[0]


def serve_history(handler, local_auth, workspace_guard, load_fyers, load_delta, load_dhan=None):
    """Serve the chart endpoint after the dashboard's normal session checks."""
    try:
        if workspace_guard:
            user = handler.workspace_identity[0]
            store = workspace_guard.store
        elif local_auth:
            user = local_auth.authorize(handler.headers)
            store = local_auth.store
        else:
            user = store = None
        query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
        require_chart(user, store, "/api/chart-workspace/history")
        interval = (query.get("interval") or ["5"])[0]
        chart_interval(interval)
        broker = handler.workspace_identity[1]["broker"] if workspace_guard else None
        symbol = requested_chart_symbol(query, broker)
        after = (query.get("after") or [None])[0]
        validate_chart_cursor(after)
        before_values = query.get("before", [])
        if len(before_values) > 1:
            raise ValueError("Use a single older history cursor.")
        before = before_values[0] if before_values else None
        validate_chart_cursor(before)
        if before is not None and (
            after is not None or broker != "DELTA_INDIA" or trade_interval(interval)
        ):
            raise ValueError("Older pages require Delta candle history and a single cursor.")
        if trade_interval(interval):
            if broker != "DELTA_INDIA":
                raise ValueError("Seconds and trade-count candles are unavailable for this broker and symbol.")
            handler.send_json(200, {"provider": "Delta India", "symbol": symbol or DELTA_SYMBOL, "rows": []})
            return
        if broker == "FYERS":
            result = {"provider": "FYERS", "symbol": FyersChartBars.SYMBOL, **history_payload(load_fyers(interval, after))}
        elif broker == "DELTA_INDIA":
            options = {"symbol": symbol} if symbol else {}
            if before is not None:
                options["before"] = before
            rows = load_delta(interval, after, **options)
            payload = history_payload(rows)
            result = {"provider": "Delta India", "symbol": symbol or DELTA_SYMBOL, **payload,
                      "older_history": bool(payload["rows"])}
        elif broker == "DHAN" and load_dhan:
            result = {"provider": "Dhan", "symbol": "NIFTY", **history_payload(load_dhan(interval, after))}
        else:
            raise ValueError("The selected broker does not have a chart data adapter.")
    except PermissionError as error:
        handler.send_json(403, {"error": str(error)})
    except ValueError as error:
        handler.send_json(400, {"error": str(error)})
    except (ChartAuthenticationRequired, FyersHistoryAuthenticationRequired, DhanAPIError) as error:
        chart_auth_failure(handler, error, "Dhan" if isinstance(error, DhanAPIError) else "FYERS")
    except (OSError, RuntimeError):
        handler.send_json(503, {"error": "Selected broker history is unavailable."})
    else:
        handler.send_json(200, result)


class FyersChartBars:
    """Aggregate observed broker socket prices independently of strategy state."""

    SYMBOL = "NSE:NIFTY50-INDEX"

    def __init__(self):
        self.lock = Lock()
        self.series = {minutes: {} for minutes in (1, 375)}
        self.latest = None
        self.latest_price = None
        self.revision = 0
        self.session_covered = False
        self.coverage_since = None

    def ingest(self, tick, now=None):
        if tick.get("symbol") != self.SYMBOL:
            return
        now = time.time() if now is None else now
        stamp = tick.get("exch_feed_time", tick.get("last_traded_time"))
        price = tick.get("ltp")
        if not all(isinstance(value, (int, float)) and isfinite(value) for value in (stamp, price)):
            return
        if stamp >= 10**12:
            stamp /= 1000
        if abs(now - stamp) > 60 or price <= 0:
            return
        local_second = int(stamp + 19800) % 86400
        elapsed = local_second - 33300
        if not 0 <= elapsed < 22500:
            return
        with self.lock:
            if self.latest is not None and stamp < self.latest:
                return
            new_session = self.latest is None or (int(self.latest) + 19800) // 86400 != (int(stamp) + 19800) // 86400
            if new_session or stamp - self.latest > 60:
                self.coverage_since = int(stamp)
                self.session_covered = new_session and elapsed == 0
            self.latest = stamp
            self.latest_price = price
            for minutes, bars in self.series.items():
                opening = int(stamp) - elapsed % (minutes * 60)
                if opening in bars:
                    row = bars[opening]
                    row[2] = max(row[2], price)
                    row[3] = min(row[3], price)
                    row[4] = price
                else:
                    bars[opening] = [opening, price, price, price, price, None]
                    if len(bars) > 750:
                        del bars[next(iter(bars))]
            self.revision += 1

    def reset_coverage(self):
        with self.lock:
            self.latest = self.latest_price = self.coverage_since = None
            self.session_covered = False
            for bars in self.series.values():
                bars.clear()
            self.revision += 1

    def snapshot(self, interval, connected):
        with self.lock:
            if not connected:
                rows = []
            elif isinstance(interval, str):
                daily = list(self.series[375].values())[-1:] if self.session_covered else []
                rows = calendar_live([[row[0] - 33300, *row[1:]] for row in daily], interval)
            elif self.coverage_since is None:
                rows = []
            else:
                covered = [row for row in self.series[1].values() if row[0] >= self.coverage_since]
                rows = combine_bars(covered, interval, 1)
            return {
                "provider": "FYERS", "symbol": self.SYMBOL, "connected": connected,
                "latest_tick": self.latest if connected else None,
                "latest_price": self.latest_price if connected else None, "revision": [self.revision, connected],
                "rows": rows, "replace_provisional": True,
            }


def serve_live(handler, local_auth, workspace_guard, bars, feed, delta_snapshot, dhan_snapshot=None):
    try:
        if workspace_guard:
            user, store = handler.workspace_identity[0], workspace_guard.store
        elif local_auth:
            user, store = local_auth.authorize(handler.headers), local_auth.store
        else:
            user = store = None
        require_chart(user, store, "/api/chart-workspace/live")
        query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
        raw = (query.get("interval") or ["5"])[0]
        minutes = chart_interval(raw)
        broker = handler.workspace_identity[1]["broker"] if workspace_guard else None
        symbol = requested_chart_symbol(query, broker)
        if trade_interval(raw) and broker != "DELTA_INDIA":
            raise ValueError("Seconds and trade-count candles are unavailable for this broker and symbol.")
        signed = query.get("trade_delta") == ["1"]
        if signed and (broker != "DELTA_INDIA" or not (isinstance(minutes, int) or minutes == "1D"
                or (isinstance(minutes, str) and minutes.endswith("S")))):
            raise ValueError("Tick-based volume delta requires a Delta India time interval up to one day.")
        if broker == "DELTA_INDIA":
            options = {"symbol": symbol} if symbol else {}
            if signed:
                options["trade_delta"] = True
            handler.send_json(200, delta_snapshot(minutes, **options))
        elif broker == "DHAN" and dhan_snapshot:
            handler.send_json(200, dhan_snapshot(minutes))
        elif broker == "FYERS":
            if feed and feed.token_expired:
                raise ChartAuthenticationRequired()
            connected = bool(feed and feed.connected)
            handler.send_json(200, bars.snapshot(minutes, connected))
        else:
            raise ValueError("The selected broker does not have a live chart adapter.")
    except PermissionError as error:
        handler.send_json(403, {"error": str(error)})
    except ValueError as error:
        handler.send_json(400, {"error": str(error)})
    except (ChartAuthenticationRequired, FyersHistoryAuthenticationRequired, DhanAPIError) as error:
        chart_auth_failure(handler, error, "Dhan" if isinstance(error, DhanAPIError) else "FYERS")
    except (OSError, RuntimeError):
        handler.send_json(503, {"error": "Selected broker live data is unavailable."})

def fetch_fyers_history(client, interval, now=None, after=None):
    """Read completed regular-session history from the selected FYERS account."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from .fyers_history import history
    from .market_data import is_token_error

    zone = ZoneInfo("Asia/Kolkata")
    now = datetime.now(zone) if now is None else now.astimezone(zone)
    minutes = chart_interval(interval)
    cursor = validate_chart_cursor(after, now.timestamp())
    if isinstance(minutes, str):
        # The 5Y range uses weekly candles. Allow for leap days and a complete opening week.
        lookback = 5 * 366 + 7 if interval == "1W" else CHART_CALENDAR_LOOKBACK_DAYS
        start = (now.date() - timedelta(days=lookback) if cursor is None
                 else datetime.fromtimestamp(cursor, zone).date())
        candles = []
        while start <= now.date():
            end = min(now.date(), start + timedelta(days=364))
            reply = history(client, {
                "symbol": FyersChartBars.SYMBOL, "resolution": "D", "date_format": 1,
                "range_from": start.isoformat(), "range_to": end.isoformat(), "cont_flag": 0,
            })
            start = end + timedelta(days=1)
            # A valid empty window can precede listing or follow contract expiry.
            if isinstance(reply, dict) and reply.get("s") == "no_data" and reply.get("candles") in (None, []):
                continue
            if not isinstance(reply, dict) or reply.get("s") != "ok" or not isinstance(reply.get("candles"), list):
                if is_token_error(reply):
                    raise ChartAuthenticationRequired()
                raise RuntimeError("FYERS daily history unavailable.")
            candles.extend(reply["candles"])
        return calendar_history(nse_daily(candles, now.timestamp()), interval, now.timestamp(), after)
    native = next(value for value in (30, 15, 5, 1) if minutes % value == 0)
    start = now - timedelta(days=10 if native == 1 else 45)
    after_stamp = cursor
    if after_stamp is not None:
        latest = int(now.timestamp())
        if not latest - 46 * 86400 <= after_stamp <= latest:
            raise ValueError("History cursor is outside the supported range.")
        start = datetime.fromtimestamp(after_stamp, zone)
    candles = []
    day = start.date()
    while day <= now.date():
        end = min(now.date(), day + timedelta(days=29))
        reply = history(client, {
            "symbol": FyersChartBars.SYMBOL, "resolution": str(native), "date_format": 1,
            "range_from": day.isoformat(), "range_to": end.isoformat(), "cont_flag": 0,
        })
        if not isinstance(reply, dict) or reply.get("s") != "ok" or not isinstance(reply.get("candles"), list):
            if is_token_error(reply):
                raise ChartAuthenticationRequired()
            raise RuntimeError("FYERS history unavailable.")
        candles.extend(reply["candles"])
        day = end + timedelta(days=1)
    rows = {}
    for row in candles:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        if not all(isinstance(value, (int, float)) and isfinite(value) for value in row[:5]):
            continue
        stamp = row[0]
        local_second = int(stamp + 19800) % 86400
        if 33300 <= local_second < 55800 and stamp + min(native * 60, 55800 - local_second) <= now.timestamp():
            rows[stamp] = [*row[:5], row[5] if len(row) > 5 else None]
    result = combine_bars([rows[stamp] for stamp in sorted(rows)], minutes, native, now.timestamp(), after_stamp)
    if not result and after_stamp is None:
        raise RuntimeError("FYERS returned no completed regular candles.")
    return result

DELTA_SYMBOL = "BTCUSD"
DELTA_CHART_SYMBOLS = frozenset({DELTA_SYMBOL, "ETHUSD"})
DELTA_INTERVALS = {1440: "1d", 360: "6h", 240: "4h", 120: "2h", 60: "1h", 30: "30m", 15: "15m", 5: "5m", 3: "3m", 1: "1m"}


DELTA_HISTORY_LIMIT = 999


def fetch_delta_history(delta, interval, after=None, *, symbol=DELTA_SYMBOL, before=None):
    product = delta.product(symbol, chart=True) if symbol not in DELTA_CHART_SYMBOLS else {}
    now = int(delta.clock())
    minutes = chart_interval(interval)
    if before is not None and after is not None:
        raise ValueError("Older pages require a single cursor.")
    if isinstance(minutes, str):
        if before is not None:
            boundary = int(before)
            if boundary <= 0 or boundary > now or calendar_bounds(boundary, interval, nse=False)[0] != boundary:
                raise ValueError("Older history cursor must be a completed calendar candle boundary.")
            now = boundary
        daily = fetch_delta_history(delta, "1440", after=after, symbol=symbol, before=before)
        # The built-in symbols also have a listing boundary. Fetch metadata only
        # when the daily window is missing the start of a calendar period.
        if symbol in DELTA_CHART_SYMBOLS and daily:
            first = daily[0][0]
            period_start = calendar_bounds(first, interval, nse=False)[0]
            if first != period_start and first - 86400 >= now - DELTA_HISTORY_LIMIT * 86400:
                lookup = getattr(delta, "product", None)
                if lookup is not None:
                    try:
                        product = lookup(symbol, chart=True)
                    except (OSError, RuntimeError, ValueError, KeyError):
                        pass
        launch = product.get("launch_time")
        launch_timestamp = None
        if launch:
            try:
                launched_at = datetime.fromisoformat(launch)
                if launched_at.tzinfo is not None:
                    launch_timestamp = int(launched_at.timestamp())
            except (TypeError, ValueError):
                pass

        def aggregate(daily, boundary, after):
            first_trading_day = None
            if launch_timestamp is not None:
                first_trading_day = launch_timestamp // 86400 * 86400
                # Some contracts publish their first daily candle after the intraday launch date.
                if launch_timestamp > first_trading_day and daily and daily[0][0] == first_trading_day + 86400:
                    first_trading_day += 86400
            return calendar_history(daily, interval, boundary, after, nse=False, first_trading_day=first_trading_day)

        result = aggregate(daily, now, after)
        if before is None or result["rows"]:
            return result
        # An empty window can contain an incomplete period or a broker data gap.
        # Include the period straddling the previous window's oldest daily bar.
        for _ in range(2):
            oldest = now - DELTA_HISTORY_LIMIT * 86400
            if oldest <= (launch_timestamp or 0):
                break
            start, end = calendar_bounds(oldest, interval, nse=False)
            cursor = start if oldest == start else end
            if cursor >= now:
                break
            now = cursor
            daily = fetch_delta_history(delta, "1440", symbol=symbol, before=cursor)
            result = aggregate(daily, now, None)
            if result["rows"]:
                break
        return result
    native, resolution = next((value, name) for value, name in DELTA_INTERVALS.items() if minutes % value == 0)
    seconds = native * 60
    cursor = int(after) if after is not None else None
    if cursor is not None and cursor > now:
        raise ValueError("History cursor is in the future.")
    if before is not None:
        boundary = int(before)
        if boundary <= 0 or boundary > now or boundary % 86400 % (minutes * 60):
            raise ValueError("Older history cursor must be a completed candle boundary.")
        now = boundary
    start = max(0, now - seconds * DELTA_HISTORY_LIMIT, min(cursor + minutes * 60, cursor - cursor % 86400 + 86400) if cursor is not None else 0)
    if start >= now:
        return []
    response = delta._get("/v2/history/candles", {
        "symbol": symbol, "resolution": resolution, "start": start, "end": now,
    })
    raw = response.get("result")
    if not isinstance(raw, list):
        raise RuntimeError("Delta candle history unavailable.")
    rows = {}
    for bar in raw:
        try:
            stamp, opening, high, low, close = (float(bar[field]) for field in ("time", "open", "high", "low", "close"))
            volume = float(bar["volume"]) if bar.get("volume") is not None else None
        except (KeyError, TypeError, ValueError):
            continue
        if not all(isfinite(value) for value in (stamp, opening, high, low, close)):
            continue
        if stamp % seconds or not start <= stamp <= now - seconds or not 0 < low <= min(opening, close) <= max(opening, close) <= high:
            continue
        row = [int(stamp), opening, high, low, close, volume if volume is not None and isfinite(volume) and volume >= 0 else None]
        if stamp in rows and rows[stamp] != row:
            raise RuntimeError("Delta published conflicting completed candles.")
        rows[stamp] = row
    result = combine_bars([rows[stamp] for stamp in sorted(rows)], minutes, native, now, cursor, nse=False, utc_daily=True)
    if before is not None:
        return result
    if native != minutes:
        current = now - now % 86400 % (minutes * 60)
        prefix = [row for stamp, row in sorted(rows.items()) if stamp >= current]
        return {"rows": result, "intraday_prefix": prefix, "native_seconds": seconds, "utc_daily": True}
    return result


def subscribe_delta_chart(stream, activity, symbol, now):
    """Reuse idle subscriptions while preserving symbols polled by open charts."""
    import json

    with stream.lock:
        if symbol not in stream.symbols:
            if len(stream.symbols) >= 24:
                idle = [name for name in activity if now - activity[name] >= 90]
                if not idle:
                    raise RuntimeError("All Delta chart stream subscriptions are currently in use.")
                oldest = min(idle, key=activity.__getitem__)
                channels = [
                    {"name": "candlestick_" + resolution, "symbols": [oldest]}
                    for seconds, resolution in stream.candle_resolutions.items()
                    if (oldest, seconds) in stream.frame_seconds
                ]
                if stream.connected and stream.socket and channels:
                    stream.socket.send(json.dumps({"type": "unsubscribe", "payload": {"channels": channels}}))
                stream.symbols.remove(oldest)
                del activity[oldest]
                for key in list(stream.frame_seconds):
                    if key[0] == oldest:
                        del stream.frame_seconds[key]
                for key in list(stream.forming_bars):
                    if key[0] == oldest:
                        del stream.forming_bars[key]
                stream.ticks.pop(oldest, None)
            stream.symbols.add(symbol)
            for seconds in stream.candle_resolutions:
                stream.frame_seconds[(symbol, seconds)] = True
            stream.subscribe_all()
        activity[symbol] = now


def delta_live_snapshot(stream, minutes, *, symbol=DELTA_SYMBOL):

    calendar = minutes if isinstance(minutes, str) else None
    native = 1440 if calendar else next(value for value in DELTA_INTERVALS if minutes % value == 0)
    with stream.lock:
        if not stream.connected:
            return {"provider": "Delta India", "symbol": symbol, "connected": False,
                    "latest_tick": None, "revision": [stream.generation, False, None, None],
                    "rows": [], "replace_provisional": True}
        rows = sorted((row for (instrument, seconds, _), row in stream.forming_bars.items()
                       if instrument == symbol and seconds == native * 60), key=lambda row: row["timestamp"])
        latest = rows[-1]["stream_exchange_at"] if rows else None
        values = [[row[key] for key in ("timestamp", "open", "high", "low", "close", "volume")] for row in rows]
        combined = calendar_live(values[-1:], calendar, nse=False) if calendar else combine_bars(values, minutes, native, nse=False, utc_daily=True)
        extra = {"native_row": values[-1]} if values and not calendar and native != minutes else {}
        return {"provider": "Delta India", "symbol": symbol, "connected": stream.connected,
                "latest_tick": latest, "revision": [stream.generation, True, latest, combined[-1] if combined else extra.get("native_row")],
                "rows": combined, "replace_provisional": True, **extra}


def motilal_chart(service, interval, after=None, live=False):
    """Use only the selected account's native index stream and captured history."""
    if trade_interval(interval):
        raise ValueError("Seconds and trade-count candles are unavailable for this broker and symbol.")
    minutes = chart_interval(interval)
    cursor = validate_chart_cursor(after, service.clock() if after is not None else None)
    service.ready()
    matches = [row for row in service.master.indices("NSE")
               if "".join(c for c in row["name"].upper() if c.isalnum()) == "NIFTY50"]
    if len(matches) != 1:
        raise ValueError("Cannot resolve the native Motilal NIFTY 50 index.")
    token = matches[0]["token"]
    symbol = f"MO:INDEX:NSE:{token}"
    service.feed.subscribe_index("NSE", token)
    service.feed.start()
    now = int(service.clock())
    calendar = minutes if isinstance(minutes, str) else None
    if calendar and not live:
        fields = ("timestamp", "open", "high", "low", "close", "volume")
        daily = nse_daily([[row.get(key) for key in fields] for row in service.history.session_candles(symbol)], now)
        return {"provider": "Motilal Oswal", "symbol": symbol, **calendar_history(daily, calendar, now, cursor)}
    if calendar:
        minutes = 375
    rows = [] if live else service.history.candles(symbol, minutes, limit=750, session_open="09:15", session_minutes=375)
    rows = [row for row in rows if (cursor is None or row["timestamp"] > cursor)
            and 33300 <= (row["timestamp"] + 19800) % 86400 < 55800]
    fields = ("timestamp", "open", "high", "low", "close", "volume")
    result = {"provider": "Motilal Oswal", "symbol": symbol, "rows": [[row.get(k) for k in fields] for row in rows]}
    if live:
        result["replace_provisional"] = True
    if not live:
        return result
    try:
        price, stamp = service.feed.price("NSE", token, index=True)
    except ValueError:
        return {**result, "rows": [], "connected": False, "latest_tick": None, "revision": None}
    elapsed = int(stamp + 19800) % 86400 - 33300
    if not 0 <= elapsed < 22500:
        return {**result, "rows": [], "connected": False, "latest_tick": None, "revision": None}
    opening = int(stamp) - elapsed % (minutes * 60)
    minute = int(stamp) // 60 * 60
    parts = service.history.candles(symbol, 1, limit=min(minutes, 375), session_open="09:15")
    parts = [row for row in parts if opening <= row["timestamp"] < minute]
    with service.history.lock:
        forming = dict(service.history.forming.get(symbol) or {})
    if forming.get("timestamp") == minute and forming.get("open_verified"):
        parts.append(forming)
    if [part["timestamp"] for part in parts] != list(range(opening, minute + 60, 60)):
        return {**result, "connected": now - stamp <= 15, "latest_tick": stamp, "revision": stamp}
    row = [opening, parts[0]["open"], max(p["high"] for p in parts),
           min(p["low"] for p in parts), price, None]
    values = calendar_live([[row[0] - 33300, *row[1:]]], calendar) if calendar else [row]
    return {**result, "rows": values, "connected": now - stamp <= 15,
            "latest_tick": stamp, "revision": [stamp, *row[1:5]]}

def require_dhan_data(client):
    profile = client.request("GET", "/profile")
    if not isinstance(profile, dict) or str(profile.get("dhanClientId")) != client.client_id:
        raise PermissionError("Dhan session does not belong to the selected account.")
    if str(profile.get("dataPlan", "")).strip().lower() != "active":
        raise PermissionError("The selected Dhan account requires an active market data plan.")


def fetch_dhan_history(client, interval, after=None, now=None):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Kolkata")
    now = datetime.now(zone) if now is None else now.astimezone(zone)
    cursor = int(after) if after is not None else 0
    minutes = chart_interval(interval)
    if isinstance(minutes, str):
        raw = client.request("POST", "/charts/historical", {
            "securityId": "13", "exchangeSegment": "IDX_I", "instrument": "INDEX",
            "expiryCode": 0, "oi": False, "fromDate": (
                (now - timedelta(days=CHART_CALENDAR_LOOKBACK_DAYS)).date() if after is None else datetime.fromtimestamp(int(after), zone).date()
            ).isoformat(),
            "toDate": (now.date() + timedelta(days=1)).isoformat(),
        })
        return calendar_history(nse_daily(dhan_rows(raw), now.timestamp()), interval, now.timestamp(), after)
    native = next(value for value in (25, 15, 5, 1) if minutes % value == 0)
    start = now - timedelta(days=10 if native == 1 else 45)
    if cursor:
        if not int(start.timestamp()) <= cursor <= now.timestamp():
            raise ValueError("History cursor is outside the supported range.")
        start = datetime.fromtimestamp(cursor, zone)
    raw = client.request("POST", "/charts/intraday", {
        "securityId": "13", "exchangeSegment": "IDX_I", "instrument": "INDEX",
        "interval": str(native), "oi": False,
        "fromDate": start.strftime("%Y-%m-%d %H:%M:%S"),
        "toDate": now.strftime("%Y-%m-%d %H:%M:%S"),
    })
    groups = {}
    seen = set()
    for stamp, opening, high, low, close, volume in dhan_rows(raw):
        if not all(isinstance(value, (int, float)) and isfinite(value)
                   for value in (stamp, opening, high, low, close)):
            raise RuntimeError("Dhan returned invalid candle fields.")
        local = int(stamp + 19800) % 86400 - 33300
        if not 0 <= local < 22500 or local % (native * 60):
            continue
        if stamp in seen or not 0 < low <= min(opening, close) <= max(opening, close) <= high:
            raise RuntimeError("Dhan returned invalid or duplicate OHLC.")
        seen.add(stamp)
        bar_start = int(stamp) - local % (minutes * 60)
        end = min(bar_start + minutes * 60, int(stamp) - local + 22500)
        if bar_start <= cursor or end > now.timestamp():
            continue
        usable_volume = volume if isinstance(volume, (int, float)) and isfinite(volume) and volume >= 0 else None
        groups.setdefault((bar_start, end), []).append([stamp, opening, high, low, close, usable_volume])
    rows = []
    for (opening, end), bars in groups.items():
        if [bar[0] for bar in bars] != list(range(opening, end, native * 60)):
            continue
        rows.append([opening, bars[0][1], max(bar[2] for bar in bars), min(bar[3] for bar in bars),
                     bars[-1][4], sum(bar[5] for bar in bars) if all(bar[5] is not None for bar in bars) else None])
    if not rows and after is None:
        raise RuntimeError("Dhan returned no completed NIFTY candles.")
    return rows


def dhan_rows(raw):
    fields = ("timestamp", "open", "high", "low", "close", "volume")
    if not isinstance(raw, dict) or any(not isinstance(raw.get(key), list) for key in fields) or len({len(raw[key]) for key in fields}) != 1:
        raise RuntimeError("Dhan returned incomplete candle arrays.")
    return sorted(zip(*(raw[key] for key in fields)))



class DhanChartStream:
    """A read-only ticker socket scoped to the selected Dhan session."""

    def __init__(self, client):
        from threading import Thread
        from urllib.parse import urlencode
        import json
        import websocket

        self.bars = FyersChartBars()
        self.connected = False
        self.started = time.monotonic()
        url = "wss://api-feed.dhan.co?" + urlencode({
            "version": 2, "token": client.headers["access-token"],
            "clientId": client.client_id, "authType": 2,
        })

        def opened(socket):
            socket.send(json.dumps({"RequestCode": 15, "InstrumentCount": 1,
                                    "InstrumentList": [{"ExchangeSegment": "IDX_I", "SecurityId": "13"}]}))
            self.connected = True

        def closed(*args):
            self.connected = False

        self.socket = websocket.WebSocketApp(url, on_open=opened, on_message=self.ingest,
                                             on_error=closed, on_close=closed)
        self.thread = Thread(target=self.socket.run_forever, kwargs={"ping_interval": 20, "ping_timeout": 10},
                             daemon=True, name="dhan-chart-market-data")
        self.thread.start()

    def ingest(self, socket, packet):
        import struct

        if not isinstance(packet, bytes) or len(packet) != 16:
            return
        code, length, segment, security, price, stamp = struct.unpack("<BHbIfI", packet)
        if (code, segment, security) == (2, 0, 13):
            self.bars.ingest({"symbol": self.bars.SYMBOL, "ltp": price, "exch_feed_time": stamp})

    def snapshot(self, minutes):
        return {**self.bars.snapshot(minutes, self.connected), "provider": "Dhan", "symbol": "NIFTY"}

    def stop(self):
        self.socket.close()
