"""FYERS-backed candle caching and bounded sector rotation snapshot service."""
from copy import deepcopy
from datetime import datetime, time as clock_time, timedelta
import json
import logging
import os
from pathlib import Path
from threading import Lock, Thread
import time

from fyers_apiv3 import fyersModel

from .analysis import (
    calculate_sector, calculate_timeframe_state, classify_rotation, detect_events,
    market_overview, mtf_alignment, rank_sectors,
)
from .analysis_config import (
    MTF_MODES, REFRESH_INTERVAL_SECONDS, ROTATION, SNAPSHOT_INTERVAL_SECONDS,
    TIMEFRAMES,
)
from .config import _atomic_private_write
from .indicators import resample_weekly
from .market_calendar import IST, market_session
from .market_data import is_token_error
from .official_weights import OFFICIAL_WEIGHT_SET
from .sectors import BENCHMARK_SYMBOL, SECTOR_BY_ID, SECTOR_DEFINITIONS, equity_symbol

LOGGER = logging.getLogger(__name__)
DEFAULT_STATE_FILE = Path(os.getenv("SECTOR_ANALYSIS_STATE_FILE", Path.home() / ".fyers" / "sector-heatmap" / "analysis-history.json")).expanduser()
HISTORY_REQUEST_MIN_INTERVAL_SECONDS = 0.35
HISTORY_RATE_LIMIT_RETRIES = 3


class FyersAuthenticationError(RuntimeError):
    """Stop a refresh immediately when FYERS rejects the shared session."""


def rank_directional_drivers(drivers, direction):
    """Rank the bounded stock scan by directional move, not index weight.

    Official contribution remains attribution evidence, but multiplying a stock's
    move by its index weight suppresses lower-weight momentum leaders before their
    completed-candle alignment can be evaluated.
    """
    directional = [item for item in drivers if item.get("change") is not None]
    if direction == "BULLISH":
        directional = [item for item in directional if item["change"] > 0]
        return sorted(
            directional,
            key=lambda item: (item["change"], item.get("contribution") or -float("inf")),
            reverse=True,
        )
    directional = [item for item in directional if item["change"] < 0]
    return sorted(
        directional,
        key=lambda item: (item["change"], item.get("contribution") or float("inf")),
    )


class CandleHistoryProvider:
    """Single shared memory cache over FYERS history calls."""

    def __init__(self, client, now=None):
        self.client = client
        self.now = now or (lambda: datetime.now(IST))
        self.cache = {}
        self.lock = Lock()
        self.request_lock = Lock()
        self.last_request = 0.0

    def get(self, symbol, timeframe):
        config = TIMEFRAMES[timeframe]
        cache_timeframe = "weekly" if timeframe == "weekly" else timeframe
        key = (symbol, cache_timeframe)
        current = time.monotonic()
        with self.lock:
            cached = self.cache.get(key)
            if cached and current - cached[0] < config["ttl_seconds"]:
                return deepcopy(cached[1])
        candles = self._download(symbol, config["resolution"], config["lookback_days"])
        if config.get("derive") == "weekly":
            candles = resample_weekly(candles)
        with self.lock:
            self.cache[key] = (current, deepcopy(candles))
        return candles

    def _download(self, symbol, resolution, lookback_days):
        end = self.now().date()
        start = end - timedelta(days=lookback_days)
        chunk_days = 30 if resolution in {"1", "2", "3", "5", "10", "15", "20", "30"} else 100 if resolution in {"60", "120", "240"} else 365
        candles_by_timestamp = {}
        cursor = start
        while cursor <= end:
            chunk_end = min(end, cursor + timedelta(days=chunk_days - 1))
            payload = {"symbol": symbol, "resolution": resolution, "date_format": 1, "range_from": cursor.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": 1}
            response = None
            for attempt in range(HISTORY_RATE_LIMIT_RETRIES + 1):
                with self.request_lock:
                    elapsed = time.monotonic() - self.last_request
                    if elapsed < HISTORY_REQUEST_MIN_INTERVAL_SECONDS:
                        time.sleep(HISTORY_REQUEST_MIN_INTERVAL_SECONDS - elapsed)
                    response = self.client.history(payload)
                    self.last_request = time.monotonic()
                message = response.get("message") if isinstance(response, dict) else "invalid response"
                rate_limited = "request limit" in str(message or "").lower()
                if not rate_limited or attempt == HISTORY_RATE_LIMIT_RETRIES:
                    break
                delay = 2 ** attempt
                LOGGER.warning(
                    "FYERS history rate limit for %s %s; retrying in %ss (%s/%s)",
                    symbol, resolution, delay, attempt + 1, HISTORY_RATE_LIMIT_RETRIES,
                )
                time.sleep(delay)
            if not isinstance(response, dict) or response.get("s") not in {"ok", None} or not isinstance(response.get("candles"), list):
                message = response.get("message") if isinstance(response, dict) else "invalid response"
                if is_token_error(response):
                    raise FyersAuthenticationError("FYERS authentication expired; use Refresh authentication and complete daily 2FA.")
                raise RuntimeError(f"FYERS history unavailable for {symbol} {resolution}: {message or 'no candles'}")
            for row in response["candles"]:
                if len(row) < 6:
                    continue
                timestamp, open_price, high, low, close, volume = row[:6]
                candles_by_timestamp[int(timestamp)] = {"timestamp": int(timestamp), "open": float(open_price), "high": float(high), "low": float(low), "close": float(close), "volume": float(volume or 0)}
            cursor = chunk_end + timedelta(days=1)
        return self._completed_only([candles_by_timestamp[key] for key in sorted(candles_by_timestamp)], resolution)

    def _completed_only(self, candles, resolution):
        current = self.now()
        if resolution == "D":
            market_closed = current.time() >= clock_time(15, 30)
            return [candle for candle in candles if datetime.fromtimestamp(candle["timestamp"], IST).date() < current.date() or market_closed]
        minutes = int(resolution)
        return [candle for candle in candles if datetime.fromtimestamp(candle["timestamp"], IST) + timedelta(minutes=minutes) <= current]


class AnalysisHistoryStore:
    def __init__(self, path=DEFAULT_STATE_FILE):
        self.path = Path(path)
        self.data = {"version": 1, "modes": {mode: {} for mode in MTF_MODES}}
        self._load()

    def _load(self):
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if loaded.get("version") == 1 and isinstance(loaded.get("modes"), dict):
                self.data = loaded
        except (OSError, ValueError, AttributeError):
            return

    def sector_history(self, mode, sector_id):
        return list(self.data.setdefault("modes", {}).setdefault(mode, {}).get(sector_id, []))

    def append(self, mode, sector):
        history = self.data.setdefault("modes", {}).setdefault(mode, {}).setdefault(sector["sector_id"], [])
        point = {key: sector.get(key) for key in ("last_updated", "overall_score", "trend_score", "relative_strength_score", "momentum_score", "breadth_score", "volume_score", "rank", "rotation_state", "acceleration_state", "rotation_readiness", "mtf_alignment")}
        point["timestamp"] = datetime.now(IST).isoformat()
        if history and history[-1].get("last_updated") == point.get("last_updated") and history[-1].get("overall_score") == point.get("overall_score"):
            history[-1] = point
        else:
            history.append(point)
        del history[:-ROTATION["history_limit"]]

    def save(self):
        _atomic_private_write(self.path, json.dumps(self.data, indent=2) + "\n")


class SectorAnalysisService:
    def __init__(self, access_token, state_file=DEFAULT_STATE_FILE, provider=None, now=None):
        self.lock = Lock()
        self.candidate_scan_lock = Lock()
        self.running = False
        self.snapshots = {mode: self._empty_snapshot(mode) for mode in MTF_MODES}
        self.store = AnalysisHistoryStore(state_file)
        self.last_saved = 0.0
        self.now = now or (lambda: datetime.now(IST))
        self.client = None
        if provider is not None:
            self.provider = provider
        elif access_token and ":" in access_token:
            app_id, token = access_token.split(":", 1)
            self.client = fyersModel.FyersModel(client_id=app_id, token=token)
            self.provider = CandleHistoryProvider(self.client)
        else:
            self.provider = None
        if self.provider is None:
            self.snapshots = {
                mode: self._empty_snapshot(
                    mode,
                    error="FYERS authentication is required for completed-candle sector analysis",
                    phase="FAILED",
                )
                for mode in MTF_MODES
            }

    @staticmethod
    def _empty_snapshot(mode, error=None, phase="CONNECTING"):
        loading = phase != "FAILED"
        return {
            "status": "LOADING" if loading else "UNAVAILABLE",
            "mode": mode,
            "benchmark": BENCHMARK_SYMBOL,
            "updated_at": None,
            "refreshing": loading,
            "refresh_error": None,
            "refresh_state": {
                "phase": phase,
                "completed": 0,
                "total": len(SECTOR_DEFINITIONS) + 1,
                "message": "Connecting to FYERS history" if loading else error,
            },
            "error": error,
            "market_session": market_session(),
            "market_overview": {},
            "weight_source": OFFICIAL_WEIGHT_SET.summary(),
            "sectors": [],
            "events": [],
        }

    def _set_refresh_state(self, phase, message, completed=0, total=None):
        progress = {
            "phase": phase,
            "completed": completed,
            "total": total if total is not None else len(SECTOR_DEFINITIONS) + 1,
            "message": message,
        }
        with self.lock:
            for snapshot in self.snapshots.values():
                snapshot["refreshing"] = True
                snapshot["refresh_error"] = None
                snapshot["refresh_state"] = progress.copy()

    def _record_refresh_failure(self, error):
        message = str(error)
        with self.lock:
            for snapshot in self.snapshots.values():
                has_valid_snapshot = bool(snapshot.get("sectors")) and snapshot.get("updated_at") is not None
                previous_phase = snapshot.get("refresh_state", {}).get("phase", "CONNECTING")
                snapshot["refreshing"] = False
                snapshot["refresh_state"] = {
                    "phase": "FAILED",
                    "last_phase": previous_phase,
                    "completed": snapshot.get("refresh_state", {}).get("completed", 0),
                    "total": snapshot.get("refresh_state", {}).get("total", len(SECTOR_DEFINITIONS) + 1),
                    "message": message,
                }
                if has_valid_snapshot:
                    snapshot["refresh_error"] = message
                else:
                    snapshot.update({"status": "UNAVAILABLE", "error": message, "refresh_error": None})

    def start(self):
        if self.running or not self.provider:
            return
        self.running = True
        Thread(target=self._loop, daemon=True, name="sector-analysis-refresh").start()

    def _loop(self):
        while self.running:
            try:
                self.refresh()
            except FyersAuthenticationError as error:
                LOGGER.warning("Sector analysis unavailable: %s", error)
                self._record_refresh_failure(error)
            except Exception as error:
                LOGGER.exception("Sector analysis refresh failed")
                self._record_refresh_failure(error)
            time.sleep(REFRESH_INTERVAL_SECONDS)

    def refresh(self):
        if not self.provider:
            return
        total_symbols = len(SECTOR_DEFINITIONS) + 1
        self._set_refresh_state("CONNECTING", "Connecting to FYERS history", total=total_symbols)
        benchmark_candles = self._timeframe_candles(BENCHMARK_SYMBOL)
        self._set_refresh_state("LOADING_BARS", "Loading completed bars", completed=1, total=total_symbols)
        benchmark_states = {timeframe: calculate_timeframe_state(timeframe, candles, candles, self._quality(timeframe, candles)) for timeframe, candles in benchmark_candles.items()}
        raw_sector_states = []
        for index, sector in enumerate(SECTOR_DEFINITIONS, start=2):
            timeframe_states = {}
            try:
                sector_candles = self._timeframe_candles(sector.symbol)
            except Exception as error:
                LOGGER.warning("Sector history failed for %s: %s", sector.symbol, error)
                sector_candles = {}
            for timeframe in TIMEFRAMES:
                candles = sector_candles.get(timeframe, [])
                timeframe_states[timeframe] = calculate_timeframe_state(timeframe, candles, benchmark_candles.get(timeframe, []), self._quality(timeframe, candles))
            raw_sector_states.append((sector, timeframe_states))
            self._set_refresh_state("LOADING_BARS", "Loading completed bars", completed=index, total=total_symbols)

        self._set_refresh_state("CALCULATING_INDICATORS", "Calculating indicators, ranks and rotation", completed=total_symbols, total=total_symbols)
        current = self.now()
        now = current.isoformat()
        session = market_session(current)
        new_snapshots = {}
        for mode in MTF_MODES:
            previous_ranks = {sector_id: history[-1].get("rank") for sector_id in SECTOR_BY_ID if (history := self.store.sector_history(mode, sector_id))}
            sectors = [calculate_sector(sector, states, mode) for sector, states in raw_sector_states]
            sectors = rank_sectors(sectors, previous_ranks)
            events = []
            for sector in sectors:
                history = self.store.sector_history(mode, sector["sector_id"])
                (
                    sector["rotation_state"],
                    sector["acceleration_state"],
                    sector["score_velocity"],
                    sector["rotation_readiness"],
                ) = classify_rotation(sector, history)
                sector["history"] = history
                definition = SECTOR_BY_ID[sector["sector_id"]]
                sector["constituents"] = [{"ticker": item.ticker, "name": item.name, "weight": item.weight} for item in definition.constituents]
                sector["attribution"] = definition.attribution
                previous = history[-1] if history else None
                events.extend(detect_events(previous, sector))
            overview = market_overview(sectors, benchmark_states)
            usable = any(sector.get("overall_score") is not None for sector in sectors)
            has_stale_data = any(sector.get("data_quality") == "STALE" for sector in sectors)
            status = "UNAVAILABLE" if not usable else "STALE" if has_stale_data else "MARKET_CLOSED" if session["status"] == "CLOSED" else "DELAYED"
            new_snapshots[mode] = {
                "status": status,
                "mode": mode,
                "benchmark": BENCHMARK_SYMBOL,
                "updated_at": now,
                "refreshing": False,
                "refresh_error": None,
                "refresh_state": {
                    "phase": "READY" if usable else "FAILED",
                    "completed": total_symbols,
                    "total": total_symbols,
                    "message": "Sector rotation is ready" if usable else "No sector has sufficient completed candle data",
                },
                "error": None if usable else "No sector has sufficient completed candle data",
                "market_session": session,
                "market_overview": overview,
                "benchmark_states": benchmark_states,
                "weight_source": OFFICIAL_WEIGHT_SET.summary(),
                "sectors": sectors,
                "events": events,
            }

        if time.monotonic() - self.last_saved >= SNAPSHOT_INTERVAL_SECONDS or not self.last_saved:
            for mode, snapshot in new_snapshots.items():
                for sector in snapshot["sectors"]:
                    self.store.append(mode, sector)
            try:
                self.store.save()
            except OSError as error:
                LOGGER.warning("Could not persist sector analysis history: %s", error)
            self.last_saved = time.monotonic()
        with self.lock:
            self.snapshots = new_snapshots

    def _timeframe_candles(self, symbol):
        result = {}
        for timeframe in ("15m", "1h"):
            try:
                result[timeframe] = self.provider.get(symbol, timeframe)
            except FyersAuthenticationError:
                raise
            except Exception as error:
                LOGGER.warning("%s history failed for %s: %s", timeframe, symbol, error)
        try:
            daily_source = self.provider.get(symbol, "daily")
            result["daily"] = daily_source
            result["weekly"] = resample_weekly(daily_source)
        except FyersAuthenticationError:
            raise
        except Exception as error:
            LOGGER.warning("Daily/Weekly history failed for %s: %s", symbol, error)
        return result

    def _quality(self, timeframe, candles):
        if not candles:
            return "UNAVAILABLE"
        last = datetime.fromtimestamp(int(candles[-1]["timestamp"]), IST)
        current = self.now()
        session = market_session(current)
        last_session = datetime.fromisoformat(session["last_completed_session"]).date()
        if session["status"] == "CLOSED" and last.date() >= last_session:
            return "MARKET CLOSED"
        age = (current - last).total_seconds()
        return "STALE" if age > TIMEFRAMES[timeframe]["stale_seconds"] else "DELAYED"

    def snapshot(self, mode="intraday", sector_id=None):
        mode = mode if mode in MTF_MODES else "intraday"
        with self.lock:
            snapshot = deepcopy(self.snapshots[mode])
        if sector_id:
            sector = next((item for item in snapshot["sectors"] if item["sector_id"] == sector_id), None)
            return {"status": snapshot["status"] if sector else "UNAVAILABLE", "mode": mode, "benchmark": snapshot["benchmark"], "updated_at": snapshot["updated_at"], "market_session": snapshot.get("market_session"), "weight_source": snapshot.get("weight_source"), "sector": sector, "error": snapshot.get("error") if sector else "Unknown or unavailable sector"}
        for sector in snapshot["sectors"]:
            for timeframe in sector.get("timeframe_states", {}).values():
                timeframe.pop("series", None)
        snapshot.pop("benchmark_states", None)
        return snapshot

    def alignment_candidates(self, live_sectors, mode="intraday", max_stocks_per_sector=3):
        """Scan directional live leaders inside fully aligned sectors on user request."""
        if not self.provider:
            raise RuntimeError("FYERS authentication is required to scan stock alignment.")
        mode = mode if mode in MTF_MODES else "intraday"
        snapshot = self.snapshot(mode)
        aligned_sectors = [
            sector for sector in snapshot.get("sectors", [])
            if sector.get("mtf_alignment") in {"FULL BULLISH ALIGNMENT", "FULL BEARISH ALIGNMENT"}
            and sector.get("data_quality") not in {"STALE", "UNAVAILABLE", "INSUFFICIENT DATA"}
        ]
        live_by_id = {item.get("sector_id"): item for item in live_sectors or []}
        sector_candidates = []
        stock_candidates = []
        scanned_stocks = 0
        with self.candidate_scan_lock:
            benchmark_candles = self._timeframe_candles(BENCHMARK_SYMBOL)
            for sector in aligned_sectors:
                direction = "BULLISH" if "BULLISH" in sector["mtf_alignment"] else "BEARISH"
                live = live_by_id.get(sector["sector_id"], {})
                sector_candidates.append({
                    "key": f"sector:{sector['sector_id']}",
                    "kind": "sector",
                    "sector_id": sector["sector_id"],
                    "name": sector["name"],
                    "symbol": sector["symbol"],
                    "direction": direction,
                    "mtf_alignment": sector["mtf_alignment"],
                    "rank": sector.get("rank"),
                    "overall_score": sector.get("overall_score"),
                    "relative_strength_state": sector.get("relative_strength_state"),
                    "data_quality": sector.get("data_quality"),
                    "last_updated": sector.get("last_updated"),
                    "price": None,
                    "market_change_pct": live.get("change"),
                    "provider_tick_timestamp_iso": live.get("provider_tick_timestamp_iso"),
                    "timeframe_states": {
                        timeframe: {key: value for key, value in state.items() if key != "series"}
                        for timeframe, state in sector.get("timeframe_states", {}).items()
                    },
                })
                drivers = rank_directional_drivers(live.get("drivers", []), direction)
                for driver in drivers[:max_stocks_per_sector]:
                    scanned_stocks += 1
                    symbol = equity_symbol(driver["ticker"])
                    stock_candles = self._timeframe_candles(symbol)
                    states = {
                        timeframe: calculate_timeframe_state(
                            timeframe,
                            stock_candles.get(timeframe, []),
                            benchmark_candles.get(timeframe, []),
                            self._quality(timeframe, stock_candles.get(timeframe, [])),
                        )
                        for timeframe in TIMEFRAMES
                    }
                    alignment = mtf_alignment(states)
                    if alignment != sector["mtf_alignment"]:
                        continue
                    qualities = [state.get("data_quality") for state in states.values()]
                    if any(quality in {"STALE", "UNAVAILABLE", "INSUFFICIENT DATA"} for quality in qualities):
                        continue
                    quality = "STALE" if "STALE" in qualities else "MARKET CLOSED" if "MARKET CLOSED" in qualities else "DELAYED"
                    stock_candidates.append({
                        "key": f"stock:{driver['ticker']}",
                        "kind": "stock",
                        "ticker": driver["ticker"],
                        "name": driver.get("name") or driver["ticker"],
                        "symbol": symbol,
                        "parent_sector_id": sector["sector_id"],
                        "parent_sector": sector["name"],
                        "direction": direction,
                        "mtf_alignment": alignment,
                        "data_quality": quality,
                        "last_updated": max((state.get("last_updated") for state in states.values() if state.get("last_updated")), default=None),
                        "price": driver.get("price"),
                        "market_change_pct": driver.get("change"),
                        "official_weight_pct": driver.get("weight"),
                        "official_contribution_pp": driver.get("contribution"),
                        "provider_tick_timestamp_iso": driver.get("provider_tick_timestamp_iso"),
                        "timeframe_states": {
                            timeframe: {key: value for key, value in state.items() if key != "series"}
                            for timeframe, state in states.items()
                        },
                    })
        # A constituent can occur in more than one official sector index. It is
        # still one underlying and must produce one handoff recommendation.
        unique_stocks = {}
        for candidate in stock_candidates:
            symbol = candidate["symbol"]
            current = unique_stocks.get(symbol)
            contribution = abs(float(candidate.get("official_contribution_pp") or 0))
            current_contribution = abs(float(current.get("official_contribution_pp") or 0)) if current else -1
            if current is None or contribution > current_contribution:
                unique_stocks[symbol] = candidate
        deduplicated_stocks = list(unique_stocks.values())
        return {
            "status": "READY",
            "mode": mode,
            "updated_at": snapshot.get("updated_at"),
            "market_session": snapshot.get("market_session"),
            "scope": {
                "sector_rule": "Exact FULL BULLISH ALIGNMENT or FULL BEARISH ALIGNMENT on completed 15m, 1h, Daily and Weekly states.",
                "stock_universe": f"Up to {max_stocks_per_sector} strongest direction-matching live moves from the official-weight constituents of each fully aligned sector.",
                "stock_selection_rule": "Directional percentage move ranks the bounded stock scan; official index weight and contribution are retained only as attribution evidence.",
                "scanned_stocks": scanned_stocks,
                "matched_stocks": len(deduplicated_stocks),
                "duplicate_recommendations_eliminated": len(stock_candidates) - len(deduplicated_stocks),
            },
            "candidates": sector_candidates + deduplicated_stocks,
        }
