"""Selected-broker candle history and WebSocket aggregation for chart analysis."""

import csv
from functools import lru_cache
from pathlib import Path
import io
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


def calendar_history(daily, interval, now, after, nse=True, *, daily_close=55800, first_trading_day=None,
                     session_day=None, period_closed=None):
    """Build calendar candles from selected-broker daily OHLC."""
    groups = {}
    cursor = int(after) if after is not None else None
    for row in daily:
        start, end = calendar_bounds(row[0], interval, nse)
        if interval == "1D" and nse:
            end = start + (daily_close(start) if callable(daily_close) else daily_close)
        if cursor is None or start > cursor:
            groups.setdefault((start, end), []).append(row)
    rows, prefix = [], None
    oldest_start = calendar_bounds(daily[0][0], interval, nse)[0] if daily else None
    for (start, end), parts in sorted(groups.items()):
        if nse and cursor is None and start == oldest_start:
            first_day = parts[0][0]
            if start != first_day and (session_day is None or any(
                session_day(datetime.fromtimestamp(stamp + 19800, timezone.utc).date())
                for stamp in range(start, first_day, 86400)
            )):
                continue
        expected = range(max(start, first_trading_day or start), min(end, int(now // 86400) * 86400), 86400)
        if not nse and [row[0] for row in parts] != list(expected):
            continue
        if session_day is not None and interval != "1D":
            observed = {row[0] for row in parts}
            # For a forming period, verify the history through the last
            # completed source session before combining it with live OHLC.
            coverage_end = end if end <= now else parts[-1][0] + 86400
            if any(stamp not in observed and session_day(
                datetime.fromtimestamp(stamp + 19800, timezone.utc).date()
            ) for stamp in range(start, coverage_end, 86400)):
                continue
        volumes = [row[5] for row in parts]
        candle = [start, parts[0][1], max(row[2] for row in parts), min(row[3] for row in parts),
                  parts[-1][4], sum(volumes) if all(v is not None for v in volumes) else None]
        if end <= now or (period_closed and period_closed(start, end, parts, now)):
            rows.append(candle)
        else:
            through = parts[-1][0]
            prefix = {"bar": candle, "through": through}
            if session_day is not None:
                prefix["next_session"] = next((
                    stamp for stamp in range(through + 86400, end, 86400)
                    if session_day(datetime.fromtimestamp(stamp + 19800, timezone.utc).date())
                ), None)
    return {"rows": rows, "prefix": prefix}


def fyers_nse_period_closed(start, end, parts, now):
    """Confirm a period early only with complete NSE cash-session history."""
    from .market_calendar import IST, NSE_SPECIAL_SESSIONS, is_trading_day

    days = [(stamp, datetime.fromtimestamp(stamp, IST).date())
            for stamp in range(start, end, 86400)]
    # The bundled NSE cash holiday schedule covers 2026.
    if not days or any(day.year != 2026 for _, day in days):
        return False
    muhurat = date(2026, 11, 8)
    sessions = [(stamp, day) for stamp, day in days if is_trading_day(day) or day == muhurat]
    if not sessions or [row[0] for row in parts] != [stamp for stamp, _ in sessions]:
        return False
    last_stamp, last_day = sessions[-1]
    # Preserve the calendar boundary for a special closing session.
    if last_day in NSE_SPECIAL_SESSIONS or last_day == muhurat:
        return False
    return now >= last_stamp + 55800


def calendar_live(daily, interval, nse=True):
    return [[calendar_bounds(row[0], interval, nse)[0], *row[1:], row[0]] for row in daily]


def history_payload(result):
    return result if isinstance(result, dict) else {"rows": result}


def nse_daily(rows, now, session_end=55800):
    normalized = {}
    for row in rows:
        if len(row) < 5 or not all(isinstance(v, (int, float)) and isfinite(v) for v in row[:5]):
            continue
        stamp, opening, high, low, close = row[:5]
        session, _ = calendar_bounds(stamp, "1D", True)
        if session + session_end <= now and 0 < low <= min(opening, close) <= max(opening, close) <= high:
            volume = row[5] if len(row) > 5 else None
            if not isinstance(volume, (int, float)) or not isfinite(volume) or volume < 0:
                volume = None
            normalized[session] = [session, opening, high, low, close, volume]
    return [normalized[key] for key in sorted(normalized)]


def combine_bars(rows, minutes, native, now=None, cursor=None, nse=True, *, session_open=33300, session_seconds=22500, utc_daily=False):
    """Combine broker bars, requiring all constituent candles for completed history."""
    seconds = minutes * 60
    groups = {}
    for row in rows:
        stamp = int(row[0])
        elapsed = (stamp + 19800) % 86400 - session_open if nse else stamp
        if utc_daily:
            elapsed = stamp % 86400
        opening = stamp - elapsed % seconds
        end = min(opening + seconds, stamp - elapsed + session_seconds) if nse else opening + seconds
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


def serve_pine_worker(handler, local_auth, worker_path):
    try:
        user = local_auth.authorize(handler.headers)
        require_chart(user, local_auth.store, "/api/chart-workspace/pine-worker.js")
    except PermissionError as error:
        handler.send_json(403, {"error": str(error)})
        return
    try:
        body = worker_path.read_bytes()
    except OSError:
        handler.send_json(503, {"error": "Pine worker unavailable."})
        return
    handler.send_response(200)
    handler.send_header("Content-Type", "text/javascript; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-eval'; connect-src 'none'")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass


CHART_CALENDAR_LOOKBACK_DAYS = 1700


def validate_chart_cursor(value, now=None, *, max_age_days=CHART_CALENDAR_LOOKBACK_DAYS + 366):
    if value is None:
        return None
    now = time.time() if now is None else now
    if not re.fullmatch(r"[0-9]{1,12}", str(value)) or int(value) > now:
        raise ValueError("History cursor must be a non-negative Unix timestamp at or before the current time.")
    stamp = int(value)
    if max_age_days is not None and stamp < now - max_age_days * 86400:
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


FYERS_CHART_SYMBOL = re.compile(r"(?:NSE|BSE|MCX):[A-Z0-9][A-Z0-9&_.`-]{0,79}")


def _fyers_master_rows(lines):
    return tuple((row[9], row[1], f"{row[9]} {row[1]}".upper()) for row in csv.reader(lines)
                 if len(row) > 9 and FYERS_CHART_SYMBOL.fullmatch(row[9]))


@lru_cache(maxsize=10)
def _cached_fyers_master(path, version):
    with path.open(encoding="utf-8", newline="") as stream:
        return _fyers_master_rows(stream)


@lru_cache(maxsize=4)
def _fyers_master_tickers(path, version):
    return frozenset(symbol for symbol, _, _ in _cached_fyers_master(path, version))


def fyers_extra_session(symbol):
    if not symbol.startswith("NSE:"):
        return None
    directory = Path(__file__).resolve().parent.parent / ".private" / "ema-band-masters"
    for segment, close in (("NSE_CD", 61200), ("NSE_COM", 86100)):
        path = directory / f"{segment}.csv"
        try:
            if symbol in _fyers_master_tickers(path, path.stat().st_mtime_ns):
                return 32400, close
        except (OSError, UnicodeError, csv.Error):
            continue
    return None


def search_cached_fyers_chart_symbols(paths, query="", offset=0, limit=100, *, instrument_kind=""):
    catalogs = []
    unavailable = []
    for path in paths:
        try:
            catalog = _cached_fyers_master(path, path.stat().st_mtime_ns)
        except (OSError, UnicodeError, csv.Error):
            catalog = ()
        if catalog:
            catalogs.append(catalog)
        else:
            unavailable.append(path.stem)
    if not catalogs:
        raise RuntimeError("FYERS instrument catalog is unavailable.")
    result = _search_fyers_catalogs(catalogs, query, offset, limit, instrument_kind=instrument_kind)
    if unavailable:
        result["unavailable_segments"] = unavailable
    return result


def search_fyers_chart_symbols(master_contents, query="", offset=0, limit=100):
    """Search the provider's instrument masters using native chart symbols."""
    catalogs = (_fyers_master_rows(io.StringIO(content)) for content in master_contents)
    return _search_fyers_catalogs(catalogs, query, offset, limit)


def _search_fyers_catalogs(catalogs, query, offset, limit, *, instrument_kind=""):
    if instrument_kind not in ("", "FUT", "OPT"):raise ValueError("Invalid derivative type")
    needle = query.strip().upper()
    exchange, separator, native_query = needle.partition(":")
    exchange_prefix = exchange + separator if exchange in {"NSE", "BSE", "MCX"} else ""
    ticker_query = native_query.strip() if exchange_prefix else needle
    terms = ticker_query.split()
    matches = {symbol: description for catalog in catalogs for symbol, description, search_text in catalog
               if symbol.startswith(exchange_prefix) and (not instrument_kind or (symbol.endswith("FUT") if instrument_kind=="FUT" else symbol.endswith(("CE","PE")))) and all(term in search_text for term in terms)}
    def rank(symbol):
        native = symbol.split(":", 1)[1]
        cash_ticker, separator, series = native.rpartition("-")
        exact_ticker = native == ticker_query or bool(separator and series.isalpha() and cash_ticker == ticker_query)
        return (symbol != exchange_prefix + ticker_query, not exact_ticker, not native.startswith(ticker_query),
                symbol != FyersChartBars.SYMBOL, symbol)

    ordered = sorted(matches, key=rank)
    return {"symbols": [{"id": symbol, "symbol": symbol, "description": matches[symbol]}
                        for symbol in ordered[offset:offset + limit]], "total": len(ordered)}


def requested_chart_symbol(query, broker):
    values = query.get("symbol")
    if values is None:
        return None
    if broker == "FYERS" and len(values) == 1 and FYERS_CHART_SYMBOL.fullmatch(values[0]):
        return values[0]
    if broker == "DHAN" and len(values) == 1 and re.fullmatch(r"(?:IDX_I|MCX_COMM|(?:NSE|BSE)_(?:EQ|FNO|CURRENCY)):[0-9]{1,12}", values[0]):
        return values[0]
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
        dhan_history = broker == "DHAN" and load_dhan is not None and not trade_interval(interval)
        fyers_history = broker == "FYERS" and not trade_interval(interval)
        if fyers_history or dhan_history:
            validate_chart_cursor(before, max_age_days=None)
        else:
            validate_chart_cursor(before)
        if before is not None and (after is not None or trade_interval(interval)
                                   or (broker != "DELTA_INDIA" and not fyers_history and not dhan_history)):
            raise ValueError("Older pages require Delta, FYERS, or Dhan candle history and a single cursor.")
        if trade_interval(interval):
            if broker != "DELTA_INDIA":
                raise ValueError("Seconds and trade-count candles are unavailable for this broker and symbol.")
            handler.send_json(200, {"provider": "Delta India", "symbol": symbol or DELTA_SYMBOL, "rows": []})
            return
        if broker == "FYERS":
            options = {"symbol": symbol} if symbol else {}
            if before is not None:
                options["before"] = before
            payload = history_payload(load_fyers(interval, after, **options))
            result = {"provider": "FYERS", "symbol": symbol or FyersChartBars.SYMBOL, **payload}
            if fyers_history and after is None:
                result["older_history"] = bool(payload["rows"])
            if symbol and (session := fyers_extra_session(symbol)):
                result["regular_session"] = session
        elif broker == "DELTA_INDIA":
            options = {"symbol": symbol} if symbol else {}
            if before is not None:
                options["before"] = before
            rows = load_delta(interval, after, **options)
            payload = history_payload(rows)
            result = {"provider": "Delta India", "symbol": symbol or DELTA_SYMBOL, **payload,
                      "older_history": bool(payload["rows"])}
        elif broker == "DHAN" and load_dhan:
            options = {"symbol": symbol} if symbol else {}
            if before is not None:
                options["before"] = before
            payload = history_payload(load_dhan(interval, after, **options))
            result = {"provider": "Dhan", "symbol": symbol or "NIFTY", **payload}
            if dhan_history and after is None:
                result["older_history"] = bool(payload["rows"])
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

    def __init__(self, symbol=SYMBOL, *, currency=False, mcx_bounds=None):
        self.symbol = symbol
        self.mcx = symbol.startswith("MCX:") or mcx_bounds is not None
        self.mcx_bounds = mcx_bounds or (lambda stamp: fyers_mcx_session_bounds(symbol, stamp))
        regular_open = 32400 if self.mcx or currency else 33300
        regular_close = 86400 if self.mcx else 61200 if currency else 55800
        self.session_open, session_close = fyers_extra_session(symbol) or (regular_open, regular_close)
        self.session_seconds = session_close - self.session_open
        self.lock = Lock()
        self.session_minutes = self.session_seconds // 60
        self.series = {minutes: {} for minutes in (1, self.session_minutes)}
        self.latest = None
        self.latest_price = None
        self.revision = 0
        self.session_covered = False
        self.coverage_since = None
        self.session_quote = None

    def ingest(self, tick, now=None):
        if tick.get("symbol") != self.symbol:
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
        bounds = self.mcx_bounds(stamp) if self.mcx else None
        session_open = bounds[0] * 60 if bounds else self.session_open
        session_end = bounds[1] * 60 if bounds else self.session_open + self.session_seconds
        elapsed = local_second - session_open
        if not 0 <= elapsed < session_end - session_open:
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
            opening, high, low = (tick.get(key) for key in ("open_price", "high_price", "low_price"))
            traded = tick.get("last_traded_time")
            if isinstance(traded, (int, float)) and traded >= 10**12:
                traded /= 1000
            day = int(stamp + 19800) // 86400
            current_trade = traded is None or (
                isinstance(traded, (int, float)) and isfinite(traded)
                and 0 < traded <= stamp + 2 and int(traded + 19800) // 86400 == day
            )
            self.session_quote = None
            if (current_trade and all(isinstance(value, (int, float)) and isfinite(value)
                                      for value in (opening, high, low))
                    and 0 < low <= min(opening, price) <= max(opening, price) <= high):
                volume = tick.get("vol_traded_today")
                if not isinstance(volume, (int, float)) or not isfinite(volume) or volume < 0:
                    volume = None
                self.session_quote = [day * 86400 - 19800, opening, high, low, price, volume]
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
            self.session_quote = None
            self.session_covered = False
            for bars in self.series.values():
                bars.clear()
            self.revision += 1

    def quote_snapshot(self, connected):
        """Constant-size read of this exact instrument's cached broker tick."""
        with self.lock:
            packet=dict(symbol=getattr(self,'symbol',self.SYMBOL),connected=connected,
                latest_tick=self.latest if connected else None,
                latest_price=self.latest_price if connected else None,
                session_bounds=self.mcx_bounds(self.latest) if getattr(self,'mcx',False) and connected and self.latest is not None else None)
            # Read one cached minute, not a history snapshot or a quote-created candle.
            if connected and self.latest is not None:
                opening=int(self.latest)//60*60
                row=self.series.get(1,{}).get(opening)
                if row is not None and self.coverage_since is not None and self.coverage_since<=opening:
                    packet.update(forming_row=row.copy(),forming_frame=1,forming_at=self.latest)
            return quote_only_frame(packet)

    def snapshot(self, interval, connected):
        with self.lock:
            if not connected:
                rows = []
            elif isinstance(interval, str):
                if self.session_quote is not None:
                    daily = [self.session_quote]
                else:
                    observed = list(self.series[self.session_minutes].values())[-1:] if self.session_covered else []
                    daily = [[row[0] - (row[0] + 19800) % 86400, *row[1:]] for row in observed]
                rows = calendar_live(daily, interval)
            elif self.coverage_since is None:
                rows = []
            else:
                covered = [row for row in self.series[1].values() if row[0] >= self.coverage_since]
                if self.mcx:
                    rows = mcx_history_bars(covered, interval, 1, self.latest, None,
                                            include_current=True, coverage_since=self.coverage_since, session_bounds=self.mcx_bounds)
                else:
                    rows = combine_bars(covered, interval, 1, session_open=self.session_open, session_seconds=self.session_seconds)
            minute_frame = None
            if connected and not self.mcx and isinstance(interval, int) and self.coverage_since is not None:
                first = (self.coverage_since // 60) * 60
                # Only send the tail that can overlap the currently forming candle.
                first = max(first, int(self.latest) - interval * 60)
                minute_frame = {"coverage_since": self.coverage_since,
                                "minutes": [row.copy() for stamp, row in self.series[1].items() if stamp >= first]}
            return {
                "fyers_intraday": minute_frame,
                "provider": "FYERS", "symbol": self.symbol, "connected": connected,
                "latest_tick": self.latest if connected else None,
                "latest_price": self.latest_price if connected else None, "revision": [self.revision, connected],
                "rows": rows, "replace_provisional": True,
                "session_bounds": self.mcx_bounds(self.latest)
                if self.mcx and connected and self.latest is not None else None,
            }


def chart_session_exception(broker, symbol, moment=None):
    """NSE capital-market calendar exceptions for the chart badge."""
    from .market_calendar import IST, NSE_CM_HOLIDAYS, NSE_SPECIAL_SESSIONS

    if broker == "FYERS":
        eligible = (symbol or FyersChartBars.SYMBOL).startswith("NSE:") and (
            symbol or FyersChartBars.SYMBOL).endswith(("-EQ", "-INDEX"))
    elif broker == "DHAN":
        eligible = symbol is None or symbol.startswith("NSE_EQ:")
    else:
        eligible = False
    if not eligible:
        return {}
    current = datetime.now(IST) if moment is None else moment.astimezone(IST)
    day = current.date()
    holiday = NSE_CM_HOLIDAYS.get(day)
    special = NSE_SPECIAL_SESSIONS.get(day)
    midnight = int(current.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    if special:
        opening, closing, name = special
        return {"session_exception": {
            "midnight": midnight, "reason": name,
            "opens": int(datetime.combine(day, opening, IST).timestamp()),
            "closes": int(datetime.combine(day, closing, IST).timestamp()),
        }}
    if holiday:
        return {"session_exception": {"midnight": midnight, "reason": holiday}}
    return {}


def quote_only_frame(frame):
    """Small immutable LTP packet; never retransmit candle history for a quote."""
    price=frame.get('latest_price')
    if not isinstance(price,(int,float)) or isinstance(price,bool) or not isfinite(price) or price<=0:
        row=frame.get('native_row') or (frame.get('rows') or [None])[-1]
        price=row[4] if isinstance(row,(list,tuple)) and len(row)>4 else None
    if not isinstance(price,(int,float)) or isinstance(price,bool) or not isfinite(price) or price<=0:price=None
    return dict(symbol=frame.get('symbol'),connected=frame.get('connected') is True,
                latest_tick=frame.get('latest_tick'),latest_price=price,rows=[],revision='quote-only',
                **{k:frame[k] for k in ('session_bounds','session_exception','forming_row','forming_frame','forming_at') if k in frame})

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
        price_only=query.get("price_only")==["1"]
        send=lambda frame:handler.send_json(200,quote_only_frame(frame) if price_only else frame)
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
            if price_only:options['price_only']=True
            if signed:
                options["trade_delta"] = True
            send(delta_snapshot(minutes, **options))
        elif broker == "DHAN" and dhan_snapshot:
            options={'symbol':symbol} if symbol else {}
            if price_only:options['price_only']=True
            frame=dhan_snapshot(minutes, **options)
            frame={**frame, **chart_session_exception(broker,symbol)}
            handler.send_json(200,quote_only_frame(frame) if price_only else frame)
        elif broker == "FYERS":
            if feed and feed.token_expired:
                raise ChartAuthenticationRequired()
            connected = bool(feed and feed.connected)
            if symbol and symbol != FyersChartBars.SYMBOL:
                bars = feed.chart_bars_for(symbol) if feed else FyersChartBars(symbol)
            frame = bars.quote_snapshot(connected) if price_only else bars.snapshot(minutes, connected)
            send({**frame, **chart_session_exception(broker, symbol)})
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

def fyers_mcx_session_bounds(symbol, stamp):
    """Resolve known non-agricultural contracts against the exchange calendar."""
    if not re.match(r"MCX:(?:CRUDEOILM?|NATURALGASM?|GOLD(?:M|GUINEA|PETAL)?|SILVER(?:M|MIC)?|COPPER|ZINC(?:MINI)?|ALUMINIUM(?:MINI)?|LEAD(?:MINI)?|NICKEL)[0-9]", symbol):
        return None
    from .motilal_calendar import trading_bounds
    try:
        return trading_bounds(stamp)
    except ValueError:
        return None


def mcx_history_bars(rows, minutes, native, now, cursor, *, include_current=False, coverage_since=None, symbol="", session_bounds=None):
    """Aggregate native MCX bars from 09:00 IST without crossing local dates."""
    groups = {}
    period = minutes * 60
    for row in rows:
        stamp = row[0]
        local_midnight = stamp - (stamp + 19800) % 86400
        bounds = session_bounds(stamp) if session_bounds else fyers_mcx_session_bounds(symbol, stamp)
        if bounds and bounds[0] == bounds[1]:
            continue
        session_start = local_midnight + (bounds[0] * 60 if bounds else 9 * 3600)
        session_end = local_midnight + (bounds[1] * 60 if bounds else 86400)
        if not session_start <= stamp < session_end or (not include_current and min(stamp + native * 60, session_end) > now):
            continue
        opening = session_start + (stamp - session_start) // period * period
        end = min(opening + period, session_end)
        if (include_current or end <= now) and (cursor is None or opening > cursor) and (coverage_since is None or opening >= coverage_since):
            groups.setdefault((opening, end, bounds is not None), []).append(row)
    result = []
    for (opening, end, known_session), parts in sorted(groups.items()):
        # A bucket needs a verified opening and continuous native coverage.
        # The final observed candle may precede midnight when the market closes.
        stamps = [row[0] for row in parts]
        expected_end = end if known_session and not include_current else stamps[-1] + 1
        if stamps != list(range(int(opening), int(expected_end), native * 60)):
            continue
        volumes = [row[5] for row in parts]
        result.append([opening, parts[0][1], max(row[2] for row in parts), min(row[3] for row in parts),
                       parts[-1][4], sum(volumes) if all(isinstance(v, (int, float)) and isfinite(v) and v >= 0
                                                         for v in volumes) else None])
    return result


def fetch_fyers_history(client, interval, now=None, after=None, *, symbol=FyersChartBars.SYMBOL, include_forming=False, before=None):
    """Read completed regular-session history from the selected FYERS account."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from .fyers_history import history
    from .market_data import is_token_error

    zone = ZoneInfo("Asia/Kolkata")
    now = datetime.now(zone) if now is None else now.astimezone(zone)
    mcx = symbol.startswith("MCX:")
    session_open, session_close = fyers_extra_session(symbol) or (33300, 86400 if mcx else 55800)
    minutes = chart_interval(interval)
    cursor = validate_chart_cursor(after, now.timestamp())
    older = validate_chart_cursor(before, now.timestamp(), max_age_days=None)
    if older is not None and (cursor is not None or trade_interval(interval)):
        raise ValueError("Older FYERS history requires a time interval and a single cursor.")
    if isinstance(minutes, str):
        # The 5Y range uses weekly candles. Allow for leap days and a complete opening week.
        lookback = 5 * 366 + 7 if interval == "1W" else CHART_CALENDAR_LOOKBACK_DAYS
        last_day = now.date()
        if older is not None:
            boundary, _ = calendar_bounds(older, interval, True)
            last_day = datetime.fromtimestamp(boundary, zone).date() - timedelta(days=1)
        start = (last_day - timedelta(days=lookback) if cursor is None
                 else datetime.fromtimestamp(cursor, zone).date())
        candles = []
        while start <= last_day:
            end = min(last_day, start + timedelta(days=364))
            reply = history(client, {
                "symbol": symbol, "resolution": "D", "date_format": 1,
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
        # MCX daily bars become historical after the exchange-local date rolls over.
        early_close = (fyers_nse_period_closed
                       if minutes != "1D" and symbol.startswith("NSE:") and symbol.endswith(("-EQ", "-INDEX"))
                       else None)
        payload = calendar_history(nse_daily(candles, now.timestamp(), session_close),
                                   interval, now.timestamp(), cursor, daily_close=session_close,
                                   period_closed=early_close)
        if older is not None:
            payload["rows"] = [row for row in payload["rows"] if row[0] < older]
            payload["prefix"] = None
        return payload
    native = next(value for value in (30, 15, 5, 1) if minutes % value == 0)
    lookback = timedelta(days=10 if native == 1 else 45)
    last_day = now.date()
    start = (now - lookback).date()
    if older is not None:
        boundary = datetime.fromtimestamp(older, zone)
        last_day = boundary.date()
        if (boundary.hour * 3600 + boundary.minute * 60 + boundary.second) <= session_open and not mcx:
            last_day -= timedelta(days=1)
        start = last_day - lookback
    after_stamp = cursor
    if after_stamp is not None:
        latest = int(now.timestamp())
        if not latest - 46 * 86400 <= after_stamp <= latest:
            raise ValueError("History cursor is outside the supported range.")
        start = datetime.fromtimestamp(after_stamp, zone).date()
    candles = []
    day = start
    while day <= last_day:
        end = min(last_day, day + timedelta(days=29))
        reply = history(client, {
            "symbol": symbol, "resolution": str(native), "date_format": 1,
            "range_from": day.isoformat(), "range_to": end.isoformat(), "cont_flag": 0,
        })
        if not isinstance(reply, dict) or reply.get("s") != "ok" or not isinstance(reply.get("candles"), list):
            if is_token_error(reply):
                raise ChartAuthenticationRequired()
            if isinstance(reply, dict) and reply.get("s") == "no_data" and reply.get("candles") in (None, []):
                day = end + timedelta(days=1)
                continue
            raise RuntimeError("FYERS history unavailable.")
        candles.extend(reply["candles"])
        day = end + timedelta(days=1)
    rows = {}
    current_parts = {}
    for row in candles:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        if not all(isinstance(value, (int, float)) and isfinite(value) for value in row[:5]):
            continue
        stamp = row[0]
        local_second = int(stamp + 19800) % 86400
        if mcx:
            rows[stamp] = [*row[:5], row[5] if len(row) > 5 else None]
            continue
        if session_open <= local_second < session_close:
            volume = row[5] if len(row) > 5 else None
            bar = [*row[:5], volume]
            if stamp + min(native * 60, session_close - local_second) <= now.timestamp():
                rows[stamp] = bar
            if include_forming and stamp <= now.timestamp() and 0 < row[3] <= min(row[1], row[4]) <= max(row[1], row[4]) <= row[2]:
                if not isinstance(volume, (int, float)) or not isfinite(volume) or volume < 0:
                    bar = [*row[:5], None]
                current_parts[stamp] = bar
    ordered = [rows[stamp] for stamp in sorted(rows)]
    if mcx:
        result = mcx_history_bars(ordered, minutes, native, now.timestamp(), cursor, symbol=symbol)
        return result if older is None else [row for row in result if row[0] < older]
    result = combine_bars(ordered, minutes, native, now.timestamp(), after_stamp,
                          session_open=session_open, session_seconds=session_close - session_open)
    if older is not None:
        return [row for row in result if row[0] < older]
    if not result and after_stamp is None:
        raise RuntimeError("FYERS returned no completed regular candles.")
    if not include_forming:
        return result
    payload = {"rows": result}
    stamp = int(now.timestamp())
    elapsed = (stamp + 19800) % 86400 - session_open
    if 0 <= elapsed < session_close - session_open:
        opening = stamp - elapsed % (minutes * 60)
        current_native = stamp - elapsed % (native * 60)
        parts = [current_parts.get(t) for t in range(opening, current_native + 1, native * 60)]
        if all(part is not None for part in parts):
            forming = combine_bars(parts, minutes, native, session_open=session_open,
                                   session_seconds=session_close - session_open)
            if forming:
                payload["fyers_forming_seed"] = {"bar": forming[0], "sampled_at": stamp}
    return payload

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


def delta_live_snapshot(stream, minutes, *, symbol=DELTA_SYMBOL, price_only=False):
    if price_only:
        with stream.lock:
            tick = stream.ticks.get(symbol) or {}
            valid = stream.connected and tick.get('symbol') == symbol
            packet=dict(symbol=symbol,connected=stream.connected,
                latest_tick=tick.get('exch_feed_time') if valid else None,
                latest_price=tick.get('ltp') if valid else None)
            # Read one exact native bucket, never traverse/retransmit history.
            if valid and isinstance(minutes,int) and minutes>0 and isinstance(packet['latest_tick'],(int,float)):
                seconds=minutes*60;stamp=int(packet['latest_tick'])//seconds*seconds
                candle=stream.forming_bars.get((symbol,seconds,stamp))
                if candle:
                    packet.update(forming_row=[candle.get(k) for k in ('timestamp','open','high','low','close','volume')],
                                  forming_frame=minutes,forming_at=candle.get('stream_exchange_at'))
            return quote_only_frame(packet)

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


def motilal_eod_candle(service, exchange, token, now, close_offset):
    """Read the published daily snapshot for the exact broker instrument."""
    from .motilal_api import MotilalError

    try:
        reply = service.eod_snapshot(exchange)
    except MotilalError as error:
        if error.auth_required:
            raise
        return []
    rows = reply.get("data")
    if not isinstance(rows, list):
        return []
    matches = []
    for row in rows:
        if not isinstance(row, dict) or row.get("exchange") != exchange or str(row.get("scripcode")) != str(token):
            continue
        try:
            day = datetime.strptime(row["date"], "%d-%m-%Y").replace(tzinfo=timezone.utc)
            prices = [float(row[field]) for field in ("open", "high", "low", "close")]
            volume = float(row["volume"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        matches.append([int(day.timestamp()) - 19800, *prices, volume])
    if len(matches) != 1:
        return []
    if callable(close_offset):
        try:
            close_offset = close_offset(matches[0][0])
        except ValueError:
            return []
        if not close_offset:
            return []
    return nse_daily(matches, now, close_offset)


def motilal_chart(service, interval, after=None, live=False, *, symbol=None, before=None):
    """Use the selected account’s native stream and captured history."""
    if trade_interval(interval):
        raise ValueError("Seconds and trade-count candles are unavailable for this broker and symbol.")
    minutes = chart_interval(interval)
    cursor = validate_chart_cursor(after, service.clock() if after is not None else None)
    if before is not None:
        if live or after is not None or not isinstance(minutes, int):
            raise ValueError("Older Motilal history requires a minute or hour interval and one cursor.")
        before = validate_chart_cursor(before, service.clock())
    service.ready()
    index = symbol is None or symbol.startswith("MO:INDEX:")
    if index:
        match = re.fullmatch(r"MO:INDEX:(NSE|BSE):([0-9]{1,10})", symbol) if symbol else None
        if symbol and not match:
            raise ValueError("Invalid Motilal chart index.")
        exchange = match[1] if match else "NSE"
        candidates = service.master.indices(exchange)
        matches = [row for row in candidates if row["token"] == int(match[2])] if match else [
            row for row in candidates if "".join(c for c in row["name"].upper() if c.isalnum()) == "NIFTY50"]
        if len(matches) != 1:
            raise ValueError("Cannot resolve the selected native Motilal index.")
        token = matches[0]["token"]
        symbol = f"MO:INDEX:{exchange}:{token}"
        service.feed.subscribe_index(exchange, token)
    else:
        if not re.fullmatch(r"MO:(NSE|BSE|NSEFO|BSEFO|NSECD|MCX|NCDEX):[0-9]{1,10}", symbol):
            raise ValueError("Invalid Motilal chart instrument.")
        instrument = service.master.exact(symbol, market_data=True)
        exchange, token = instrument["exchange"], instrument["token"]
        service.feed.subscribe(exchange, token)
    service.feed.start()
    now = int(service.clock())
    ncdex = exchange == "NCDEX"
    currency = exchange == "NSECD"
    bounds = None
    if exchange == "MCX":
        from .motilal_calendar import trading_bounds
        bounds = trading_bounds
    elif ncdex:
        from .ncdex_calendar import trading_bounds
        underlying = instrument["underlying"]

        def bounds(stamp):
            return trading_bounds(stamp, underlying)

    def session_closes(timestamps):
        if not ncdex:
            return {}
        days = {int(stamp) - int(stamp + 19800) % 86400 for stamp in timestamps}
        return {"session_closes": {day: bounds(day)[1] * 60 for day in days}}
    session_open = "09:00" if currency else "09:15"
    session_start = 32400 if currency else 33300
    session_minutes = 480 if currency else 375
    session_end = session_start + session_minutes * 60
    calendar = minutes if isinstance(minutes, str) else None
    session_day = None
    if calendar and bounds:
        def session_day(day):
            stamp = int(datetime.combine(day, datetime.min.time(), timezone.utc).timestamp()) - 19800
            try:
                opening, closing = bounds(stamp)
            except ValueError:
                return True  # An unknown calendar cannot establish a closure.
            return closing > opening
    elif calendar and exchange == "NSE":
        from .market_calendar import is_trading_day
        session_day = is_trading_day
    if calendar and not live:
        fields = ("timestamp", "open", "high", "low", "close", "volume")
        if bounds:
            sessions = service.history.candles(symbol, 1440, limit=750, session_bounds=bounds)
            normalization_close = 0

            def close_offset(stamp):
                return bounds(stamp)[1] * 60
        else:
            options = {"session_open": session_open, "minutes": session_minutes} if currency else {}
            sessions = service.history.session_candles(symbol, **options)
            close_offset = normalization_close = session_end
        daily = nse_daily([[row.get(key) for key in fields] for row in sessions], now, normalization_close)
        # Any calendar view collects the daily snapshot. Longer periods
        # still require every scheduled trading day.
        if ncdex:
            for row in motilal_eod_candle(service, exchange, token, now, close_offset):
                service.history.save_daily_snapshot(symbol, row)
            snapshots = [row for row in service.history.daily_snapshots(symbol)
                         if (close := close_offset(row[0])) and row[0] + close <= now]
        elif exchange in {"NSE", "BSE"}:
            for row in motilal_eod_candle(service, exchange, token, now, close_offset):
                service.history.save_daily_snapshot(symbol, row)
            snapshots = [row for row in service.history.daily_snapshots(symbol)
                         if row[0] + close_offset <= now]
        else:
            snapshots = []
        if snapshots:
            merged = {row[0]: row for row in daily}
            merged.update((row[0], row) for row in snapshots)
            daily = [merged[stamp] for stamp in sorted(merged)]
        def ncdex_period_closed(start, end, parts, timestamp):
            try:
                sessions = [(day, close) for day in range(start, end, 86400)
                            if (close := close_offset(day))]
            except ValueError:
                return False  # The exchange calendar does not cover the whole period.
            if not sessions or [row[0] for row in parts] != [day for day, _ in sessions]:
                return False
            last_day, last_close = sessions[-1]
            return timestamp >= last_day + last_close

        return {"provider": "Motilal Oswal", "symbol": symbol,
                **calendar_history(daily, calendar, now, cursor, daily_close=close_offset,
                                   session_day=session_day,
                                   period_closed=ncdex_period_closed if ncdex and calendar != "1D" else None),
                **session_closes(row[0] for row in daily)}
    if calendar:
        minutes = session_minutes
    options = {"session_bounds": bounds} if bounds else {"session_open": session_open, "session_minutes": session_minutes}
    if before is not None:
        options["before"] = before
    rows = [] if live else service.history.candles(symbol, minutes, limit=751, **options)
    rows = [row for row in rows if (cursor is None or row["timestamp"] > cursor)
            and (bounds or session_start <= (row["timestamp"] + 19800) % 86400 < session_end)]
    fields = ("timestamp", "open", "high", "low", "close", "volume")
    result = {"provider": "Motilal Oswal", "symbol": symbol,
              "rows": [[row.get(k) for k in fields] for row in rows[-750:]],
              **session_closes(row["timestamp"] for row in rows[-750:])}
    if not live and cursor is None:
        result["older_history"] = len(rows) > 750
    if not live:
        return result
    result["replace_provisional"] = True
    if bounds:
        midnight = now - (now + 19800) % 86400
        try:
            opening_minute, closing_minute = bounds(now)
        except ValueError:
            pass  # A calendar outside its coverage cannot establish market status.
        else:
            session = {"midnight": midnight}
            if closing_minute > opening_minute:
                session.update(opens=midnight + opening_minute * 60,
                               closes=midnight + closing_minute * 60)
            else:
                session["reason"] = f"{exchange} has no scheduled trading session today"
                session["closed_label"] = "Market closed"
            result["session_exception"] = session
    if ncdex and calendar:
        start, end = calendar_bounds(now, calendar, True)
        try:
            for day in range(end - 86400, start - 1, -86400):
                _, close = bounds(day)
                if close:
                    result["period_closes_at"] = day + close * 60
                    break
        except ValueError:
            pass  # No period deadline without a verified final session.
    try:
        price, stamp = service.feed.price(exchange, token, index=index)
    except ValueError:
        return {**result, "rows": [], "connected": service.feed.connected,
                "latest_tick": None, "revision": None}
    if bounds:
        start, end = bounds(stamp)
        session_start, session_minutes = start * 60, end - start
        if calendar:
            minutes = session_minutes
    elapsed = int(stamp + 19800) % 86400 - session_start
    if not 0 <= elapsed < session_minutes * 60:
        return {**result, "rows": [], "connected": service.feed.connected,
                "latest_tick": None, "revision": None}
    opening = int(stamp) - elapsed % (minutes * 60)
    minute = int(stamp) // 60 * 60
    parts = service.history.candles(symbol, 1, limit=min(minutes, session_minutes), **({"session_bounds": bounds} if bounds else {"session_open": session_open}))
    parts = [row for row in parts if opening <= row["timestamp"] < minute]
    with service.history.lock:
        forming = dict(service.history.forming.get(symbol) or {})
    if forming.get("timestamp") == minute and forming.get("open_verified"):
        parts.append(forming)
    if [part["timestamp"] for part in parts] != list(range(opening, minute + 60, 60)):
        return {**result, "connected": now - stamp <= 15, "latest_tick": stamp, "revision": stamp}
    row = [opening, parts[0]["open"], max(p["high"] for p in parts),
           min(p["low"] for p in parts), price, None]
    values = calendar_live([[row[0] - session_start, *row[1:]]], calendar) if calendar else [row]
    if calendar and session_day is not None:
        period, *_, session = values[0]

        if period != session and not any(
            session_day(datetime.fromtimestamp(day + 19800, timezone.utc).date())
            for day in range(period, session, 86400)
        ):
            values[0].append(True)  # First scheduled trading session of the period.
    return {**result, "rows": values, "connected": now - stamp <= 15,
            "latest_tick": stamp, "revision": [stamp, *row[1:5]],
            "session_bounds": [start, end] if bounds else None}

def require_dhan_data(client):
    profile = client.request("GET", "/profile")
    if not isinstance(profile, dict) or str(profile.get("dhanClientId")) != client.client_id:
        raise PermissionError("Dhan session does not belong to the selected account.")
    if str(profile.get("dataPlan", "")).strip().lower() != "active":
        raise PermissionError("The selected Dhan account requires an active market data plan.")


def dhan_mcx_chart_bounds(stamp):
    from .dhan_mcx import trading_bounds
    try:
        return trading_bounds(stamp)
    except ValueError:
        return None


def search_dhan_chart_symbols(master, query, now, limit=100, *, offset=0, segment_filter=""):
    """Search current Dhan instruments supported by the chart adapter."""
    instrument_kind=""
    if segment_filter in ("MCX_COMM_FUT","MCX_COMM_OPT"):
        segment_filter,instrument_kind=segment_filter.rsplit("_",1)
    exact = query.strip().upper()
    exact_id = re.fullmatch(r"(?:IDX_I|MCX_COMM|(?:NSE|BSE)_(?:EQ|FNO|CURRENCY)):[0-9]{1,12}", exact)
    venue, separator, native = exact.partition(":")
    exchange_filter = venue if separator and venue in ("NSE", "BSE", "MCX") else ""
    ticker_query = native.strip() if exchange_filter else exact
    board = ""
    if exchange_filter in ("NSE", "BSE"):
        ticker, dash, suffix = ticker_query.rpartition("-")
        if dash and suffix in ("EQ", "INDEX"):
            ticker_query, board = ticker, ("E" if suffix == "EQ" else "I")
    terms = ticker_query.split()
    compact_query = re.sub(r"[^A-Z0-9]", "", ticker_query)
    exact_indexes = set()
    today = now.date().isoformat()
    results = {}
    for row in master.load(now):
        exchange = row.get("SEM_EXM_EXCH_ID")
        segment = {"I": "IDX_I", "E": f"{exchange}_EQ", "D": f"{exchange}_FNO", "C": f"{exchange}_CURRENCY", "M": "MCX_COMM"}.get(row.get("SEM_SEGMENT"))
        security_id = row.get("SEM_SMST_SECURITY_ID", "")
        symbol = row.get("SEM_TRADING_SYMBOL", "")
        description = row.get("SEM_CUSTOM_SYMBOL", "")
        instrument = row.get("SEM_INSTRUMENT_NAME", "")
        expiry = row.get("SEM_EXPIRY_DATE", "")[:10]
        supported_exchange = exchange == "MCX" if segment == "MCX_COMM" else exchange in ("NSE", "BSE")
        if not supported_exchange or not segment or not security_id.isdecimal() or not symbol:
            continue
        if segment_filter and segment != segment_filter:
            continue
        if instrument_kind and not instrument.startswith(instrument_kind):
            continue
        if (exchange_filter and exchange != exchange_filter) or (board and row.get("SEM_SEGMENT") != board):
            continue
        if row.get("SEM_SEGMENT") in ("D", "C", "M") and expiry < today:
            continue
        key = f"{segment}:{security_id}"
        if exact_id and key != exact:
            continue
        index_alias = segment == "IDX_I" and compact_query and compact_query in (
            re.sub(r"[^A-Z0-9]", "", symbol.upper()),
            re.sub(r"[^A-Z0-9]", "", (description or "").upper()),
        )
        if not index_alias and not all(term in f"{symbol} {description} {exchange} {instrument} {key}".upper() for term in terms):
            continue
        if index_alias:
            exact_indexes.add(key)
        try:
            tick = float(row.get("SEM_TICK_SIZE") or "") / 100
        except (TypeError, ValueError):
            tick = None
        metadata = {"tick_size": tick} if tick is not None and isfinite(tick) and tick > 0 else {}
        results.setdefault(key, {"id": key, "symbol": symbol, "description": description,
                                 "exchange": exchange, "segment": segment, "instrument": instrument, **metadata})
    ordered = sorted(results.values(), key=lambda row: (
        row["id"] not in exact_indexes and row["symbol"].upper() != ticker_query,
        not row["symbol"].upper().startswith(ticker_query),
        row["segment"] != "IDX_I", row["symbol"], row["id"]))
    return {"symbols": ordered[offset:offset + limit], "total": len(ordered), "offset": offset}


def resolve_dhan_chart_symbol(master, symbol, now):
    segment, security_id = symbol.split(":", 1)
    exchange, _, suffix = segment.partition("_")
    master_segment = {"I": "I", "EQ": "E", "FNO": "D", "CURRENCY": "C", "COMM": "M"}[suffix]
    instruments = {
        row["SEM_INSTRUMENT_NAME"] for row in master.load(now)
        if row.get("SEM_SEGMENT") == master_segment
        and row.get("SEM_SMST_SECURITY_ID") == security_id
        and (row.get("SEM_EXM_EXCH_ID") in ("NSE", "BSE") if segment == "IDX_I"
             else row.get("SEM_EXM_EXCH_ID") == exchange)
        and (suffix not in ("FNO", "CURRENCY", "COMM") or row.get("SEM_EXPIRY_DATE", "")[:10] >= now.date().isoformat())
        and row.get("SEM_INSTRUMENT_NAME")
    }
    if len(instruments) != 1:
        raise ValueError("Instrument is unavailable in the current Dhan master.")
    return {"security_id": security_id, "exchange_segment": segment, "instrument": instruments.pop()}


def fetch_dhan_history(client, interval, after=None, now=None, *, before=None, security_id="13",
                       exchange_segment="IDX_I", instrument="INDEX"):
    """Fetch and aggregate candles for a Dhan instrument with a regular Indian equity session."""
    instrument_fields = {
        "securityId": str(security_id), "exchangeSegment": exchange_segment, "instrument": instrument,
    }
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Kolkata")
    now = datetime.now(zone) if now is None else now.astimezone(zone)
    cursor = int(after) if after is not None else 0
    mcx = exchange_segment == "MCX_COMM"
    currency = exchange_segment.endswith("_CURRENCY")
    session_open, session_end = (32400, 61200) if currency else (33300, 55800)
    session_seconds = session_end - session_open
    minutes = chart_interval(interval)
    if before is not None and (after is not None or trade_interval(interval)):
        raise ValueError("Older Dhan history requires a time interval and a single cursor.")
    older = validate_chart_cursor(before, now.timestamp(), max_age_days=None)
    if isinstance(minutes, str):
        if older is not None and calendar_bounds(older, interval, True)[0] != older:
            raise ValueError("Older history cursor must be a calendar candle boundary.")
        stop = datetime.fromtimestamp(older, zone) if older is not None else now
        first_day = ((stop - timedelta(days=CHART_CALENDAR_LOOKBACK_DAYS)).date() if after is None
                     else datetime.fromtimestamp(int(after), zone).date())
        raw = client.request("POST", "/charts/historical", {
            **instrument_fields,
            "expiryCode": 0, "oi": False, "fromDate": first_day.isoformat(),
            "toDate": (stop.date() + timedelta(days=older is None)).isoformat(),
        })
        daily = nse_daily(dhan_rows(raw), stop.timestamp(), 86400 if mcx else session_end)
        return calendar_history(daily, interval, stop.timestamp(), after)
    native = next(value for value in (25, 15, 5, 1) if minutes % value == 0)
    oldest_date = now.date().replace(day=28) if now.month == 2 and now.day == 29 else now.date()
    oldest = datetime.combine(oldest_date.replace(year=oldest_date.year - 5), datetime.min.time(), tzinfo=zone)
    if older is not None:
        now = datetime.fromtimestamp(older, zone)
        if now <= oldest:
            return []
    start = max(oldest, now - timedelta(days=10 if native == 1 else 45))
    if cursor:
        if not int(start.timestamp()) <= cursor <= now.timestamp():
            raise ValueError("History cursor is outside the supported range.")
        start = datetime.fromtimestamp(cursor, zone)
    raw = client.request("POST", "/charts/intraday", {
        **instrument_fields,
        "interval": str(native), "oi": False,
        "fromDate": start.strftime("%Y-%m-%d %H:%M:%S"),
        "toDate": now.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if mcx:
        rows = mcx_history_bars(sorted(dhan_rows(raw)), minutes, native, now.timestamp(),
                                cursor, session_bounds=dhan_mcx_chart_bounds)
        if not rows and after is None and before is None:
            raise RuntimeError("Dhan returned no completed candles for this instrument.")
        return rows
    groups = {}
    seen = set()
    for stamp, opening, high, low, close, volume in dhan_rows(raw):
        if not all(isinstance(value, (int, float)) and isfinite(value)
                   for value in (stamp, opening, high, low, close)):
            raise RuntimeError("Dhan returned invalid candle fields.")
        local = int(stamp + 19800) % 86400 - session_open
        if not 0 <= local < session_seconds or local % (native * 60):
            continue
        if stamp in seen or not 0 < low <= min(opening, close) <= max(opening, close) <= high:
            raise RuntimeError("Dhan returned invalid or duplicate OHLC.")
        seen.add(stamp)
        bar_start = int(stamp) - local % (minutes * 60)
        end = min(bar_start + minutes * 60, int(stamp) - local + session_seconds)
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
    if not rows and after is None and before is None:
        raise RuntimeError("Dhan returned no completed candles for this instrument.")
    return rows


def dhan_rows(raw):
    fields = ("timestamp", "open", "high", "low", "close", "volume")
    if not isinstance(raw, dict) or any(not isinstance(raw.get(key), list) for key in fields) or len({len(raw[key]) for key in fields}) != 1:
        raise RuntimeError("Dhan returned incomplete candle arrays.")
    return sorted(zip(*(raw[key] for key in fields)))



class DhanChartStream:
    """A read-only, multi-instrument ticker socket for one Dhan session."""

    SEGMENTS = {"IDX_I": 0, "NSE_EQ": 1, "NSE_FNO": 2, "NSE_CURRENCY": 3, "BSE_EQ": 4, "MCX_COMM": 5, "BSE_CURRENCY": 7, "BSE_FNO": 8}

    def __init__(self, client, *, symbol=None, account_id=None, clock=time.time):
        from threading import Lock, Thread
        from urllib.parse import urlencode
        import websocket

        self.lock = Lock()
        self.instruments = {}
        self.connected = False
        self.started = time.monotonic()
        self.account_id = account_id
        import hashlib, secrets
        self.stream_id = secrets.token_hex(16)
        self.native_identity = hashlib.sha256(str(client.client_id).encode()).hexdigest()
        self.clock = clock
        self.tick_sequence = 0
        self.connection_revision = 0
        self.latest_ticks = {}
        self.subscribe(symbol)
        url = "wss://api-feed.dhan.co?" + urlencode({
            "version": 2, "token": client.headers["access-token"],
            "clientId": client.client_id, "authType": 2,
        })

        def opened(socket):
            with self.lock:
                self.connection_revision += 1
                self.latest_ticks.clear()
                for segment, security_id, bars in self.instruments.values():
                    bars.reset_coverage()
                    self.send_subscription(socket, segment, security_id)
                self.connected = True

        def closed(*args):
            with self.lock:
                self.connected = False
                self.latest_ticks.clear()

        self.socket = websocket.WebSocketApp(url, on_open=opened, on_message=self.ingest,
                                             on_error=closed, on_close=closed)
        self.thread = Thread(target=self.socket.run_forever, kwargs={"ping_interval": 20, "ping_timeout": 10},
                             daemon=True, name="dhan-chart-market-data")
        self.thread.start()

    @staticmethod
    def send_subscription(socket, segment, security_id):
        import json

        socket.send(json.dumps({"RequestCode": 15, "InstrumentCount": 1,
                                "InstrumentList": [{"ExchangeSegment": segment, "SecurityId": security_id}]}))

    def subscribe(self, symbol):
        segment, security_id = (symbol or "IDX_I:13").split(":", 1)
        key = (self.SEGMENTS[segment], int(security_id))
        with self.lock:
            if key not in self.instruments:
                if len(self.instruments) >= 100:
                    raise RuntimeError("Dhan chart subscription capacity reached.")
                if self.connected:
                    self.send_subscription(self.socket, segment, security_id)
                self.instruments[key] = (segment, security_id, FyersChartBars(currency=segment.endswith("_CURRENCY"),
                        mcx_bounds=dhan_mcx_chart_bounds if segment == "MCX_COMM" else None))
            return self.instruments[key][2]

    def ingest(self, socket, packet):
        import struct

        if not isinstance(packet, bytes) or len(packet) != 16:
            return
        code, length, segment, security, price, stamp = struct.unpack("<BHbIfI", packet)
        if code != 2 or length != len(packet):
            return
        with self.lock:
            instrument = self.instruments.get((segment, security))
            received = self.clock()
            prior=self.latest_ticks.get((segment,security))
            if (instrument and self.connected and isfinite(price) and price>0 and stamp>0 and stamp<=received+1
                    and (not prior or stamp>=prior["provider_at"])):
                self.tick_sequence += 1
                self.latest_ticks[(segment,security)] = dict(
                    account_id=self.account_id,broker="DHAN",symbol=instrument[0]+":"+instrument[1],
                    native_account_hash=self.native_identity,stream_id=self.stream_id,connection_revision=self.connection_revision,
                    sequence=self.tick_sequence,price=str(price),provider_at=stamp,received_at=received,
                    source="BROKER_WEBSOCKET")
        if instrument:
            bars = instrument[2]
            bars.ingest({"symbol": bars.SYMBOL, "ltp": price, "exch_feed_time": stamp})

    def execution_tick(self, symbol):
        segment,security=symbol.split(":",1)
        key=(self.SEGMENTS[segment],int(security))
        with self.lock:
            tick=self.latest_ticks.get(key)
            now=self.clock()
            if (not self.connected or not tick or not self.account_id
                    or not 0<=now-tick["received_at"]<=2 or not -1<=now-tick["provider_at"]<=2):
                return None
            return dict(tick)

    def quote_snapshot(self, *, symbol=None):
        bars=self.subscribe(symbol)
        return {**bars.quote_snapshot(self.connected), 'provider':'Dhan', 'symbol':symbol or 'IDX_I:13'}

    def snapshot(self, minutes, *, symbol=None):
        bars = self.subscribe(symbol)
        return {**bars.snapshot(minutes, self.connected), "provider": "Dhan", "symbol": symbol or "NIFTY"}

    def stop(self):
        with self.lock:
            self.connected=False
            self.latest_ticks.clear()
        self.socket.close()
