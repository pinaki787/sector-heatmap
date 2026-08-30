"""FYERS-backed candle caching and bounded sector rotation snapshot service."""
from copy import deepcopy
from datetime import datetime, time as clock_time, timedelta
import json
import logging
import os
from pathlib import Path
from threading import Lock, Thread
import time
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel

from .analysis import (
    calculate_sector, calculate_timeframe_state, classify_rotation, detect_events,
    market_overview, rank_sectors,
)
from .analysis_config import (
    MTF_MODES, REFRESH_INTERVAL_SECONDS, ROTATION, SNAPSHOT_INTERVAL_SECONDS,
    TIMEFRAMES,
)
from .config import _atomic_private_write
from .indicators import resample_weekly
from .sectors import BENCHMARK_SYMBOL, SECTOR_BY_ID, SECTOR_DEFINITIONS

LOGGER = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
DEFAULT_STATE_FILE = Path(os.getenv("SECTOR_ANALYSIS_STATE_FILE", Path.home() / ".fyers" / "sector-heatmap" / "analysis-history.json")).expanduser()


class CandleHistoryProvider:
    """Single shared memory cache over FYERS history calls."""

    def __init__(self, client, now=None):
        self.client = client
        self.now = now or (lambda: datetime.now(IST))
        self.cache = {}
        self.lock = Lock()
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
            elapsed = time.monotonic() - self.last_request
            if elapsed < 0.12:
                time.sleep(0.12 - elapsed)
            response = self.client.history(payload)
            self.last_request = time.monotonic()
            if not isinstance(response, dict) or response.get("s") not in {"ok", None} or not isinstance(response.get("candles"), list):
                message = response.get("message") if isinstance(response, dict) else "invalid response"
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
        point = {key: sector.get(key) for key in ("last_updated", "overall_score", "trend_score", "relative_strength_score", "momentum_score", "breadth_score", "volume_score", "rank", "rotation_state", "acceleration_state", "mtf_alignment")}
        point["timestamp"] = datetime.now(IST).isoformat()
        if history and history[-1].get("last_updated") == point.get("last_updated") and history[-1].get("overall_score") == point.get("overall_score"):
            history[-1] = point
        else:
            history.append(point)
        del history[:-ROTATION["history_limit"]]

    def save(self):
        _atomic_private_write(self.path, json.dumps(self.data, indent=2) + "\n")


class SectorAnalysisService:
    def __init__(self, access_token, state_file=DEFAULT_STATE_FILE, provider=None):
        self.lock = Lock()
        self.running = False
        self.snapshots = {mode: self._empty_snapshot(mode, "Analysis is loading") for mode in MTF_MODES}
        self.store = AnalysisHistoryStore(state_file)
        self.last_saved = 0.0
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
            self.snapshots = {mode: self._empty_snapshot(mode, "FYERS authentication is required for completed-candle sector analysis") for mode in MTF_MODES}

    @staticmethod
    def _empty_snapshot(mode, error):
        return {"status": "UNAVAILABLE", "mode": mode, "benchmark": BENCHMARK_SYMBOL, "updated_at": None, "refreshing": False, "error": error, "market_overview": {}, "sectors": [], "events": []}

    def start(self):
        if self.running or not self.provider:
            return
        self.running = True
        Thread(target=self._loop, daemon=True, name="sector-analysis-refresh").start()

    def _loop(self):
        while self.running:
            try:
                self.refresh()
            except Exception as error:
                LOGGER.exception("Sector analysis refresh failed")
                with self.lock:
                    for snapshot in self.snapshots.values():
                        snapshot.update({"status": "UNAVAILABLE", "refreshing": False, "error": str(error)})
            time.sleep(REFRESH_INTERVAL_SECONDS)

    def refresh(self):
        if not self.provider:
            return
        with self.lock:
            for snapshot in self.snapshots.values():
                snapshot["refreshing"] = True
        benchmark_candles = self._timeframe_candles(BENCHMARK_SYMBOL)
        benchmark_states = {timeframe: calculate_timeframe_state(timeframe, candles, candles, self._quality(timeframe, candles)) for timeframe, candles in benchmark_candles.items()}
        raw_sector_states = []
        for sector in SECTOR_DEFINITIONS:
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

        now = datetime.now(IST).isoformat()
        new_snapshots = {}
        for mode in MTF_MODES:
            previous_ranks = {sector_id: history[-1].get("rank") for sector_id in SECTOR_BY_ID if (history := self.store.sector_history(mode, sector_id))}
            sectors = [calculate_sector(sector, states, mode) for sector, states in raw_sector_states]
            sectors = rank_sectors(sectors, previous_ranks)
            events = []
            for sector in sectors:
                history = self.store.sector_history(mode, sector["sector_id"])
                sector["rotation_state"], sector["acceleration_state"], sector["score_velocity"] = classify_rotation(sector, history)
                sector["history"] = history
                sector["constituents"] = [{"ticker": ticker, "weight": weight} for ticker, weight in SECTOR_BY_ID[sector["sector_id"]].constituents]
                previous = history[-1] if history else None
                events.extend(detect_events(previous, sector))
            overview = market_overview(sectors, benchmark_states)
            usable = any(sector.get("overall_score") is not None for sector in sectors)
            new_snapshots[mode] = {"status": "DELAYED" if usable else "UNAVAILABLE", "mode": mode, "benchmark": BENCHMARK_SYMBOL, "updated_at": now, "refreshing": False, "error": None if usable else "No sector has sufficient completed candle data", "market_overview": overview, "benchmark_states": benchmark_states, "sectors": sectors, "events": events}

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
            except Exception as error:
                LOGGER.warning("%s history failed for %s: %s", timeframe, symbol, error)
        try:
            daily_source = self.provider.get(symbol, "daily")
            result["daily"] = daily_source
            result["weekly"] = resample_weekly(daily_source)
        except Exception as error:
            LOGGER.warning("Daily/Weekly history failed for %s: %s", symbol, error)
        return result

    @staticmethod
    def _quality(timeframe, candles):
        if not candles:
            return "UNAVAILABLE"
        last = datetime.fromtimestamp(int(candles[-1]["timestamp"]), IST)
        age = (datetime.now(IST) - last).total_seconds()
        return "STALE" if age > TIMEFRAMES[timeframe]["stale_seconds"] else "DELAYED"

    def snapshot(self, mode="intraday", sector_id=None):
        mode = mode if mode in MTF_MODES else "intraday"
        with self.lock:
            snapshot = deepcopy(self.snapshots[mode])
        if sector_id:
            sector = next((item for item in snapshot["sectors"] if item["sector_id"] == sector_id), None)
            return {"status": snapshot["status"] if sector else "UNAVAILABLE", "mode": mode, "benchmark": snapshot["benchmark"], "updated_at": snapshot["updated_at"], "sector": sector, "error": snapshot.get("error") if sector else "Unknown or unavailable sector"}
        for sector in snapshot["sectors"]:
            for timeframe in sector.get("timeframe_states", {}).values():
                timeframe.pop("series", None)
        snapshot.pop("benchmark_states", None)
        return snapshot
