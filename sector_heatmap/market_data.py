from datetime import datetime
from threading import Lock, Thread
from fyers_apiv3.FyersWebsocket import data_ws
from .sectors import SECTORS, SECTOR_STOCKS, equity_symbol

TOKEN_ERROR_HINTS = ("token", "auth", "unauthor", "401", "expired", "invalid access")

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
                self.token_expired = any(hint in error.lower() for hint in TOKEN_ERROR_HINTS)
        def on_connect():
            with self.lock: self.connected, self.error = True, None
            index_symbols = [symbol for _, symbol, _ in SECTORS]
            stock_symbols = [equity_symbol(ticker) for stocks in SECTOR_STOCKS.values() for ticker, _ in stocks]
            socket.subscribe(list(dict.fromkeys(index_symbols + stock_symbols)), data_type="SymbolUpdate")
        socket = data_ws.FyersDataSocket(access_token=self.access_token, litemode=False, reconnect=True, on_message=on_message, on_error=on_error, on_connect=on_connect)
        Thread(target=socket.connect, daemon=True, name="fyers-market-data").start()
    def snapshot(self):
        with self.lock: ticks, error, connected = dict(self.ticks), self.error, self.connected
        rows = []
        for name, symbol, weight in SECTORS:
            tick = ticks.get(symbol, {}); ltp, previous = tick.get("ltp"), tick.get("prev_close_price")
            change = round((ltp - previous) / previous * 100, 2) if ltp and previous else None
            drivers = []
            for ticker, driver_weight in SECTOR_STOCKS[name]:
                stock = ticks.get(equity_symbol(ticker), {})
                stock_ltp, stock_previous = stock.get("ltp"), stock.get("prev_close_price")
                stock_change = round((stock_ltp - stock_previous) / stock_previous * 100, 2) if stock_ltp and stock_previous else None
                drivers.append({"ticker": ticker, "weight": driver_weight, "price": stock_ltp, "change": stock_change,
                                "contribution": round(driver_weight * stock_change / 100, 3) if stock_change is not None else None})
            drivers.sort(key=lambda item: item["contribution"] if item["contribution"] is not None else float("-inf"), reverse=True)
            rows.append({"name": name, "index": symbol.split(":", 1)[1].removesuffix("-INDEX"), "weight": weight, "change": change, "drivers": drivers})
        return {"mode": "live" if connected else "connecting", "connected": connected, "error": error, "updated_at": datetime.now().astimezone().isoformat(), "sectors": rows}
