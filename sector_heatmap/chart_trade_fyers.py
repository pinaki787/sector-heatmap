"""FYERS chart-order adapter using fresh native reads and sync TPSL submission.

The adapter is not activated merely by importing it. Submission requires both
the existing FYERS live gate and a consumed account-bound chart preview.
"""
from datetime import datetime
from decimal import Decimal
import math
import hashlib
import time
from .chart_trade_plan import build_plan
from .chart_trade_native import native_bracket_order
from .chart_trade_admission import entry_revision,mark_entry_attempt,ChartOrderNotSent


class FyersChartAdapter:
    broker = "FYERS"

    def __init__(self, account, execution, *, client_factory=None, quote_reader=None,
                 margin_reader=None, history_reader=None, clock=time.time):
        if account.get("broker") != self.broker:
            raise PermissionError("A FYERS account is required.")
        self.account = dict(account)
        self.account_id = account["id"]
        self.execution = execution
        self.client_factory = client_factory
        self.quote_reader = quote_reader
        self.margin_reader = margin_reader
        self.history_reader = history_reader
        self.clock = clock
        self.last_preflight = None
        self._reconciliation_snapshot = None

    def live_enabled(self):
        return bool(self.account.get("live_enabled") and self.execution._live_submission_enabled())

    def _client(self):
        if self.client_factory:
            return self.client_factory()
        from .fyers_execution import _current_client
        return _current_client(self.execution.client_factory)

    @staticmethod
    def _rows(response, key):
        if not isinstance(response, dict) or response.get("s") != "ok" or not isinstance(response.get(key), list):
            raise ValueError("Fresh FYERS account evidence is unavailable.")
        return response[key]

    def _contract(self, symbol):
        metadata = self.execution.master.lookup([symbol]).get(symbol)
        derivative = metadata is not None
        if metadata is None:
            metadata = self.execution.cm_master.lookup([symbol]).get(symbol)
        if not metadata or metadata.get("symbol", symbol) != symbol:
            raise ValueError("The exact symbol is absent from the current FYERS master.")
        if metadata.get("suspended") or metadata.get("banned"):
            raise ValueError("The selected FYERS contract is not tradable.")
        expiry = metadata.get("expiry_epoch") if derivative else None
        if derivative and not expiry:
            raise ValueError("Native derivative expiry evidence is required.")
        return {"symbol": symbol, "tick_size": metadata.get("tick_size"),
                "lot_size": metadata.get("lot_size", 1) if derivative else 1,
                "expires_at": float(expiry) if expiry else None, "tradable": True,
                "linked_exit_capability": "NATIVE_OCO",
                "products": ["INTRADAY", "MARGIN"] if derivative else ["INTRADAY", "CNC", "MTF"]}

    def _margin(self, client, body):
        if self.margin_reader:
            return self.margin_reader(client, body)
        # This is the read-only margin calculator, never the placement endpoint.
        response = client._sector_pulse_ipv4_session.post(
            "https://api-t1.fyers.in/api/v3/multiorder/margin",
            headers={"Authorization": client.header, "Content-Type": "application/json"},
            json={"data": [body]}, timeout=15)
        response.raise_for_status()
        return response.json()

    def prepare(self, payload):
        from .chart_trade_ownership import assert_workspace_chart_entry_allowed
        assert_workspace_chart_entry_allowed(self.broker)
        client = self._client()
        profile = client.get_profile()
        if not isinstance(profile, dict) or profile.get("s") != "ok":
            raise ValueError("The selected FYERS account session could not be verified.")
        identity = (profile.get("data") or {}).get("fy_id")
        if not identity:
            raise ValueError("The native FYERS account identity is unavailable.")
        account = dict(self.account, native_identity=hashlib.sha256(str(identity).encode()).hexdigest(),
                       native_entry_revision=entry_revision(self.broker))
        contract = self._contract(str(payload.get("symbol") or ""))
        positions = self._rows(client.positions(), "netPositions")
        orders = self._rows(client.orderbook(), "orderBook")
        for row in positions:
            if row.get("symbol") == contract["symbol"] and float(row.get("netQty") or 0) != 0:
                raise ValueError("An existing position in this contract must be handled through its own exit workflow.")
        for row in orders:
            if row.get("symbol") == contract["symbol"] and row.get("status") not in {1,2,5,7}:
                raise ValueError("An existing pending order in this contract must be reconciled first.")
        from .fyers_execution import _fresh_depth_quote, available_funds
        available = Decimal(str(available_funds(client.funds())))
        quote = self.quote_reader(client, contract["symbol"], self.clock()) if self.quote_reader else (
            _fresh_depth_quote(client, contract["symbol"], datetime.fromtimestamp(self.clock()).astimezone()))
        stamp = float(quote.get("provider_timestamp") or 0)
        if stamp > 1e10:
            stamp /= 1000
        plan = build_plan(payload, account=account, contract=contract,
                          quote={"account_id": self.account_id, "symbol": contract["symbol"],
                                 "last_price": quote.get("ltp"), "received_at": self.clock(),
                                 "provider_at": stamp}, now=self.clock())
        body = native_bracket_order(plan, contract, client_order_id="MARGIN-PREVIEW")["body"]
        result = self._margin(client, body)
        if not isinstance(result, dict) or result.get("s") != "ok" or not isinstance(result.get("data"), dict):
            raise ValueError("The native FYERS margin preview is unavailable.")
        margin = result["data"]
        try:
            required = Decimal(str(margin["margin_total"]))
            margin_available = Decimal(str(margin["margin_avail"]))
        except (KeyError, ValueError, TypeError):
            raise ValueError("The FYERS margin response is incomplete.") from None
        if not all(value.is_finite() and value >= 0 for value in [required, margin_available, available]):
            raise ValueError("The FYERS margin response is invalid.")
        if required > min(available, margin_available):
            raise ValueError("The selected account cannot fund this chart order's broker margin.")
        # Margin calls can take time. Recheck price timing and contract exposure
        # after that call before issuing a usable preview or refreshed intent.
        positions = self._rows(client.positions(), "netPositions")
        orders = self._rows(client.orderbook(), "orderBook")
        if any(row.get("symbol") == plan.symbol and float(row.get("netQty") or 0) != 0 for row in positions):
            raise ValueError("The selected contract acquired a position while the preview was prepared.")
        if any(row.get("symbol") == plan.symbol and row.get("status") not in {1,2,5,7} for row in orders):
            raise ValueError("The selected contract acquired a pending order while the preview was prepared.")
        quote = self.quote_reader(client, contract["symbol"], self.clock()) if self.quote_reader else (
            _fresh_depth_quote(client, contract["symbol"], datetime.fromtimestamp(self.clock()).astimezone()))
        stamp = float(quote.get("provider_timestamp") or 0)
        if stamp > 1e10:
            stamp /= 1000
        plan = build_plan(payload, account=account, contract=contract,
                          quote={"account_id": self.account_id, "symbol": contract["symbol"],
                                 "last_price": quote.get("ltp"), "received_at": self.clock(),
                                 "provider_at": stamp}, now=self.clock())
        self.last_preflight = {"fingerprint": plan.fingerprint(),
                               "available_funds": float(available), "required_margin": float(required),
                               "settlement_currency": "INR", "margin_status": "NATIVE_PREVIEW",
                               "quote": {key: quote.get(key) for key in ("ltp", "bid", "ask", "provider_timestamp")},
                               "checked_at": self.clock(), "contract": contract}
        return plan

    def refresh(self, plan):
        return self.prepare(plan.terms())

    def submit_bracket(self, plan, *, idempotency_key):
        try:
            if not self.account.get("live_enabled") or not self.execution._live_submission_enabled():
                raise PermissionError("The selected FYERS account's live gate is disabled.")
            state = self.last_preflight
            if not state or state.get("fingerprint") != plan.fingerprint() or not 0 <= self.clock()-state["checked_at"] <= 5:
                raise ValueError("Refresh the FYERS chart order before submission.")
            if plan.native_entry_revision!=entry_revision(self.broker):
                raise ValueError("Another entry attempt changed this account; review a fresh chart order.")
            request = native_bracket_order(plan, state["contract"], client_order_id=idempotency_key)
            from .chart_trade_ownership import assert_workspace_chart_entry_allowed
            assert_workspace_chart_entry_allowed(self.broker,client_order_id=request["body"]["orderTag"])
            sender=self._client().place_order
            mark_entry_attempt(self.broker)
        except Exception as error:
            raise ChartOrderNotSent("A final FYERS chart pre-submission check failed.") from error
        reply = sender(request["body"])
        if isinstance(reply, dict) and reply.get("s") == "error":
            return {"status": "REJECTED"}
        if isinstance(reply, dict) and reply.get("s") == "ok" and reply.get("id"):
            return {"entry_order_id": str(reply["id"]), "account_id": self.account_id, "symbol": plan.symbol}
        return {"status": "SUBMISSION_UNCERTAIN"}


    def reconcile(self, plan, *, preview_id, entry_order_id=None):
        snapshot=self._reconciliation_snapshot or self._read_reconciliation_snapshot()
        if not 0<=self.clock()-snapshot["checked_at"]<=5:
            raise ValueError("The FYERS account reconciliation snapshot aged; refresh it.")
        if not plan.native_account_hash or snapshot["identity"] != plan.native_account_hash:
            raise PermissionError("The native FYERS login differs from the account that owns this chart order.")
        from .chart_trade_reconciliation import reconcile_fyers
        return dict(reconcile_fyers(plan,snapshot["orders"],preview_id,entry_order_id),checked_at=snapshot["checked_at"])

    def _history(self, name, params):
        if name not in {"order-history", "trade-history"}:
            raise ValueError("Unsupported FYERS read-only report.")
        if self.history_reader:
            return self.history_reader(name, params)
        client=self._client()
        response=client._sector_pulse_ipv4_session.get(
            "https://api-t1.fyers.in/api/v3/"+name,
            headers={"Authorization":client.header}, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def reconcile_record(self, plan, *, record):
        original=record.get("result") or {}
        entry_id=original.get("entry_order_id")
        result=self.reconcile(plan,preview_id=record["preview_id"],entry_order_id=entry_id)
        snapshot=self._reconciliation_snapshot
        if snapshot is None:
            # Retake and retain a fresh account snapshot for the fallback decision.
            snapshot=self._read_reconciliation_snapshot()
        if (result["status"] != "BROKER_STATUS_UNAVAILABLE" or not entry_id
                or any(str(r.get("id") or "")==str(entry_id) for r in snapshot["orders"])):
            return result
        from .chart_trade_fyers_history import read_reports, reconcile_archived_entry
        reports=read_reports(self._history,symbol=plan.symbol,identity_hash=plan.native_account_hash,
                             started_at=float(record["expires_at"])-120,now=self.clock())
        # Reports can be slow; revalidate the selected login and current book afterwards.
        fresh=self._read_reconciliation_snapshot()
        if fresh["identity"] != plan.native_account_hash:
            raise PermissionError("The native FYERS login changed while reading historical evidence.")
        if any(str(r.get("id") or "")==str(entry_id) for r in fresh["orders"]):
            from .chart_trade_reconciliation import reconcile_fyers
            return dict(reconcile_fyers(plan,fresh["orders"],record["preview_id"],entry_id),
                        checked_at=fresh["checked_at"])
        return dict(reconcile_archived_entry(plan,reports,entry_id),checked_at=fresh["checked_at"])

    def _read_reconciliation_snapshot(self):
        client=self._client()
        profile=client.get_profile()
        identity=(profile.get("data") or {}).get("fy_id") if isinstance(profile,dict) and profile.get("s")=="ok" else None
        if not identity:raise PermissionError("The native FYERS account identity is unavailable.")
        return dict(identity=hashlib.sha256(str(identity).encode()).hexdigest(),
                    orders=self._rows(client.orderbook(),"orderBook"),checked_at=self.clock())

    def begin_reconciliation_batch(self):
        self._reconciliation_snapshot=self._read_reconciliation_snapshot()
