"""Fresh, confirmation-gated FYERS square-off for managed straddle runners."""

from datetime import datetime, timedelta
import os
import secrets
from threading import Lock

from fyers_apiv3 import fyersModel


PREVIEW_TTL_SECONDS = 30


def _ok(response):
    return isinstance(response, dict) and response.get("s") == "ok"


def _rows(response, key):
    value = response.get(key, []) if isinstance(response, dict) else []
    return value if isinstance(value, list) else []


class StraddleSquareOffService:
    def __init__(self, credential_provider, runners, client_factory=None, now=None):
        self.credential_provider = credential_provider
        self.runners = runners
        self.client_factory = client_factory or self._client
        self.now = now or (lambda: datetime.now().astimezone())
        self.previews = {}
        self.lock = Lock()

    def _client(self):
        token = str(self.credential_provider() or "")
        if ":" not in token:
            raise RuntimeError("Fresh FYERS credentials are unavailable; no position was changed.")
        app_id, access_token = token.split(":", 1)
        return fyersModel.FyersModel(client_id=app_id, token=access_token, is_async=False, log_path="")

    def _runner(self, name):
        runner = self.runners.get(str(name or "").strip().lower())
        if runner is None:
            raise ValueError("Choose the Sensex or NIFTY managed straddle runner.")
        return runner

    def _preflight(self, name):
        runner = self._runner(name)
        snapshot = runner.snapshot()
        if snapshot.get("mode") != "LIVE":
            raise PermissionError("Square-off is available only for a managed LIVE runner; paper state never reaches FYERS.")
        state = snapshot.get("position") or {}
        symbols = [state.get("ce_symbol"), state.get("pe_symbol")]
        if not all(isinstance(symbol, str) and symbol for symbol in symbols):
            raise RuntimeError("The runner has no persisted CE and PE symbols; no FYERS order was prepared.")
        client = self.client_factory()
        positions_response, orders_response = client.positions(), client.orderbook()
        if not _ok(positions_response) or not _ok(orders_response):
            raise RuntimeError("Fresh FYERS positions and orders could not both be verified; no square-off was prepared.")
        positions = _rows(positions_response, "netPositions") or _rows(positions_response, "positions")
        orders = _rows(orders_response, "orderBook") or _rows(orders_response, "orders")
        legs = []
        for symbol in symbols:
            matches = [item for item in positions if item.get("symbol") == symbol and int(float(item.get("netQty", 0) or 0)) != 0]
            if not matches:
                continue
            if len(matches) != 1:
                raise RuntimeError(f"FYERS shows more than one open position for {symbol}; no square-off was prepared.")
            net_qty = int(float(matches[0].get("netQty", 0) or 0))
            product = str(matches[0].get("productType") or matches[0].get("product_type") or "INTRADAY")
            exit_side = -1 if net_qty > 0 else 1
            pending_exits = [
                item for item in orders
                if item.get("symbol") == symbol
                and int(item.get("side", 0) or 0) == exit_side
                and int(item.get("status", 0) or 0) not in {1, 2, 5, 7}
            ]
            if pending_exits:
                raise RuntimeError(f"FYERS already has a pending exit order for {symbol}; no duplicate exit was prepared.")
            legs.append({
                "symbol": symbol,
                "quantity": abs(net_qty),
                "action": "SELL" if net_qty > 0 else "BUY_TO_COVER",
                "order_type": "MARKET",
                "product_type": product,
            })
        if not legs:
            raise RuntimeError("FYERS shows no open position for either runner-owned leg; no square-off was prepared.")
        return {"runner": name, "runner_name": snapshot.get("name"), "legs": legs, "position_entry_time": state.get("entry_time")}

    def prepare(self, name):
        preview = self._preflight(name)
        preview_id = f"EXIT-{secrets.token_hex(4).upper()}"
        now = self.now()
        preview.update({
            "preview_id": preview_id,
            "status": "PREVIEW_ONLY",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=PREVIEW_TTL_SECONDS)).isoformat(),
            "confirmation_phrase": f"CONFIRM EXIT {preview_id}",
            "warning": "Only open positions in the exact runner-owned CE and PE symbols are included. Other positions and orders are untouched.",
            "submission_eligible": os.getenv("SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS") == "1",
        })
        with self.lock:
            self.previews[preview_id] = preview
        return preview

    def submit(self, preview_id, confirmation):
        if os.getenv("SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS") != "1":
            raise PermissionError("Live FYERS submission is disabled; no position was changed.")
        with self.lock:
            preview = self.previews.get(preview_id)
        if not preview:
            raise ValueError("Unknown or expired square-off preview.")
        if confirmation != preview["confirmation_phrase"]:
            raise ValueError("Type the exact confirmation phrase from the fresh square-off preview.")
        if self.now() >= datetime.fromisoformat(preview["expires_at"]):
            raise ValueError("The square-off preview expired; refresh it before exiting.")
        refreshed = self._preflight(preview["runner"])
        if refreshed["legs"] != preview["legs"] or refreshed.get("position_entry_time") != preview.get("position_entry_time"):
            replacement = self.prepare(preview["runner"])
            error = RuntimeError("FYERS position state changed; review the replacement square-off preview.")
            error.replacement_preview = replacement
            raise error
        runner = self._runner(preview["runner"])
        runner.stop()
        orders = [{
            "symbol": leg["symbol"], "qty": leg["quantity"], "type": 2,
            "side": -1 if leg["action"] == "SELL" else 1,
            "productType": leg["product_type"], "limitPrice": 0, "stopPrice": 0,
            "validity": "DAY", "disclosedQty": 0, "offlineOrder": False,
        } for leg in refreshed["legs"]]
        response = self.client_factory().place_basket_orders(orders)
        data = response.get("data", []) if isinstance(response, dict) else []
        order_ids = [str(item.get("id")) for item in data if isinstance(item, dict) and item.get("id")]
        with self.lock:
            self.previews.pop(preview_id, None)
        if not _ok(response) or len(order_ids) != len(refreshed["legs"]):
            return {"status": "EXECUTION_STATUS_UNCERTAIN", "order_ids": order_ids, "message": "Runner stopped, but the FYERS exit was not fully acknowledged. Reconcile the listed legs in FYERS immediately; do not retry automatically."}
        return {"status": "PENDING", "order_ids": order_ids, "message": "Runner stopped and FYERS accepted every previewed exit order. Verify that each listed leg fills; unrelated positions were untouched."}
