from datetime import datetime
import os
from pathlib import Path
import ssl
from threading import Lock, Thread
from fyers_apiv3.FyersWebsocket import data_ws
from .official_weights import OFFICIAL_WEIGHT_SET
from .sectors import SECTOR_DEFINITIONS, equity_symbol
from .market_calendar import market_session

TOKEN_ERROR_HINTS = ("token", "auth", "unauthor", "401", "expired", "invalid access")
TICK_TIMESTAMP_FIELDS = ("last_traded_time", "exch_feed_time", "timestamp")

def is_token_error(message):
    if isinstance(message, dict) and message.get("code") in {-8, -15, -16, -17, 401}:
        return True
    return any(hint in str(message).lower() for hint in TOKEN_ERROR_HINTS)


def provider_tick_timestamp(tick):
    """Return the provider value unchanged; do not replace it with snapshot time."""
    for field in TICK_TIMESTAMP_FIELDS:
        if isinstance(tick, dict) and tick.get(field) is not None:
            return tick[field]
    return None


def tick_timestamp_iso(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if abs(float(value)) >= 1_000_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds).astimezone().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().isoformat()
    except ValueError:
        return None


def _percentage_change(ltp, previous):
    if ltp is None or previous in (None, 0):
        return None
    return (float(ltp) - float(previous)) / float(previous) * 100

def configure_websocket_ca_bundle():
    """Select a trusted CA source without weakening TLS verification."""
    configured = os.getenv("WEBSOCKET_CLIENT_CA_BUNDLE")
    if configured:
        configured_path = Path(configured).expanduser()
        if not configured_path.exists():
            raise RuntimeError("WEBSOCKET_CLIENT_CA_BUNDLE does not exist")
        return str(configured_path)

    default_context = ssl.create_default_context()
    if default_context.cert_store_stats().get("x509_ca", 0) > 0:
        return "system"

    try:
        import certifi
    except ImportError as error:
        raise RuntimeError("Python has no trusted CA certificates; install certifi") from error
    certifi_path = Path(certifi.where())
    if not certifi_path.is_file():
        raise RuntimeError("The certifi CA bundle is unavailable")
    certifi_context = ssl.create_default_context(cafile=str(certifi_path))
    if certifi_context.cert_store_stats().get("x509_ca", 0) == 0:
        raise RuntimeError("The certifi CA bundle contains no trusted certificates")
    os.environ["WEBSOCKET_CLIENT_CA_BUNDLE"] = str(certifi_path)
    return str(certifi_path)

class FyersLiveFeed:
    def __init__(self, access_token):
        self.access_token, self.lock, self.ticks = access_token, Lock(), {}
        self.error, self.connected, self.token_expired = None, False, False
    def start(self):
        def on_message(message):
            symbol = message.get("symbol") if isinstance(message, dict) else None
            if symbol:
                with self.lock: self.ticks[symbol] = message
        def on_error(message):
            error = str(message)
            with self.lock:
                self.error, self.connected = error, False
                self.token_expired = is_token_error(message)
        def on_connect():
            with self.lock: self.connected, self.error = True, None
            index_symbols = [sector.symbol for sector in SECTOR_DEFINITIONS]
            stock_symbols = [equity_symbol(item.ticker) for sector in SECTOR_DEFINITIONS for item in sector.constituents]
            socket.subscribe(list(dict.fromkeys(index_symbols + stock_symbols)), data_type="SymbolUpdate")
        try:
            configure_websocket_ca_bundle()
        except RuntimeError as error:
            with self.lock:
                self.error, self.connected = str(error), False
            return
        socket = data_ws.FyersDataSocket(access_token=self.access_token, litemode=False, reconnect=True, on_message=on_message, on_error=on_error, on_connect=on_connect)
        Thread(target=socket.connect, daemon=True, name="fyers-market-data").start()
    def snapshot(self):
        with self.lock: ticks, error, connected = dict(self.ticks), self.error, self.connected
        rows = []
        provider_times = []
        for sector in SECTOR_DEFINITIONS:
            tick = ticks.get(sector.symbol, {})
            ltp, previous = tick.get("ltp"), tick.get("prev_close_price")
            change = _percentage_change(ltp, previous)
            index_tick_timestamp = provider_tick_timestamp(tick)
            index_tick_timestamp_iso = tick_timestamp_iso(index_tick_timestamp)
            if index_tick_timestamp_iso:
                provider_times.append(index_tick_timestamp_iso)
            drivers = []
            for constituent in sector.constituents:
                stock = ticks.get(equity_symbol(constituent.ticker), {})
                stock_ltp, stock_previous = stock.get("ltp"), stock.get("prev_close_price")
                stock_change = _percentage_change(stock_ltp, stock_previous)
                tick_timestamp = provider_tick_timestamp(stock)
                tick_iso = tick_timestamp_iso(tick_timestamp)
                if tick_iso:
                    provider_times.append(tick_iso)
                drivers.append({
                    "ticker": constituent.ticker,
                    "name": constituent.name,
                    "weight": constituent.weight,
                    "price": stock_ltp,
                    "change": stock_change,
                    "contribution": constituent.weight * stock_change / 100 if stock_change is not None else None,
                    "provider_tick_timestamp": tick_timestamp,
                    "provider_tick_timestamp_iso": tick_iso,
                })
            drivers.sort(key=lambda item: abs(item["contribution"]) if item["contribution"] is not None else -1, reverse=True)
            attribution = dict(sector.attribution)
            attribution["available_constituents"] = sum(item["change"] is not None for item in drivers)
            attribution["available_weight_pct"] = round(sum(item["weight"] for item in drivers if item["change"] is not None), 2)
            rows.append({
                "sector_id": sector.sector_id,
                "name": sector.name,
                "index": sector.symbol.split(":", 1)[1].removesuffix("-INDEX"),
                "change": change,
                "provider_tick_timestamp": index_tick_timestamp,
                "provider_tick_timestamp_iso": index_tick_timestamp_iso,
                "attribution": attribution,
                "top_contributors": [item for item in drivers if item["contribution"] is not None][:3],
                "drivers": drivers,
            })
        return {
            "mode": "live" if connected else "connecting",
            "connected": connected,
            "error": error,
            "updated_at": max(provider_times) if provider_times else None,
            "snapshot_at": datetime.now().astimezone().isoformat(),
            "provider": "FYERS",
            "weight_source": OFFICIAL_WEIGHT_SET.summary(),
            "market_session": market_session(),
            "sectors": rows,
        }
