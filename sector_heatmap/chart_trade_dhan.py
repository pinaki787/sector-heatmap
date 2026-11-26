"""Staged Dhan chart adapter. Not registered for hosted live submission.

Execution remains disabled until shared admission, conditional entries and
complete exchange-fill reconciliation are implemented.
"""
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import json
import hashlib
import sqlite3
from contextlib import closing
import re
import time
from .chart_trade_plan import build_plan, positive, ChartTradePlan
from .chart_trade_native import native_bracket_order, dhan_super_margin_payload, dhan_triggered_bracket_order
from .chart_trade_dhan_evidence import account_identity, no_contract_exposure, margin_coverage
from .chart_trade_admission import entry_revision, entry_lock, mark_dhan_entry_attempt, ChartOrderNotSent
from .dhan_execution import fresh_quote_snapshot, IST, DhanAPIError


class DhanChartAdapter:
    broker = "DHAN"

    def __init__(self, account, execution, *, clock=time.time, session_validator=None, submission_enabled=False, tick_reader=None, activation_check=None):
        if account.get("broker") != self.broker or account.get("id") != execution.account.get("id"):
            raise PermissionError("An exact selected Dhan execution account is required.")
        self.account = dict(account)
        self.account_id = account["id"]
        self.execution = execution
        self.clock = clock
        self.tick_reader = tick_reader
        from .chart_trade_dhan_sessions import validate_session
        self.session_validator = session_validator or validate_session
        self.last_preflight = None
        self._submission_enabled = submission_enabled is True
        self.activation_check=activation_check if activation_check is not None else lambda:True

    def live_enabled(self):
        return bool(self._submission_enabled and self.activation_check() is True and self.account.get("live_enabled")
                    and self.execution.execution_allowed())

    def _journals(self):
        for directory in ("dhan-orders", "dhan-strategy-intents"):
            for path in (Path(self.execution.folder)/directory).glob("*.json"):
                record = json.loads(path.read_text())
                if not isinstance(record, dict) or not record.get("status"):
                    raise ValueError("A Dhan submission journal needs reconciliation.")
                if record["status"] in {"UNKNOWN", "SUBMITTING"}:
                    raise ValueError("An uncertain Dhan submission must be reconciled before another entry.")

    def _contract(self, symbol):
        match = re.fullmatch(r"(NSE_EQ|BSE_EQ|NSE_FNO|BSE_FNO|NSE_CURRENCY|BSE_CURRENCY|MCX_COMM):([1-9][0-9]*)", symbol)
        if not match:
            raise ValueError("Choose an exact tradable Dhan segment and security ID; indices remain analysis-only.")
        segment, security = match.groups()
        now = datetime.fromtimestamp(self.clock(), IST)
        native = self.execution.master.resolve(dict(security_id=security, exchange_segment=segment,
                                                   proposal={"kind":"NATIVE"}), now)
        if str(native.get("security_id")) != security or native.get("exchange_segment") != segment:
            raise ValueError("The current Dhan master resolved a different contract.")
        if native.get("instrument_name") == "OPTSTK":
            from .dhan_execution import contract_underlying
            rows = self.execution.master.load(now)
            selected = [row for row in rows if row.get("SEM_EXM_EXCH_ID") == segment.split("_",1)[0]
                        and row.get("SEM_SEGMENT") == "D" and str(row.get("SEM_SMST_SECURITY_ID")) == security]
            if len(selected) != 1:
                raise ValueError("The selected stock option is not uniquely present in the Dhan master.")
            underlying = contract_underlying(selected[0])
            native["stock_option_expiries"] = [row.get("SEM_EXPIRY_DATE","")[:10] for row in rows
                if row.get("SEM_EXM_EXCH_ID") == segment.split("_",1)[0]
                and row.get("SEM_SEGMENT") == "D" and row.get("SEM_INSTRUMENT_NAME") == "OPTSTK"
                and contract_underlying(row) == underlying and row.get("SEM_OPTION_TYPE") in {"CE","PE"}]
        tick = positive(native.get("tick_size"), "Dhan master tick")
        lot = positive(native.get("lot_size"), "Dhan master lot")
        if lot != int(lot):
            raise ValueError("The Dhan master lot size must be whole.")
        expiry = native.get("expiry")
        if not segment.endswith("_EQ") and not expiry:
            raise ValueError("Native Dhan derivative expiry is required.")
        if expiry and str(expiry)[:10] < now.date().isoformat():
            raise ValueError("The selected Dhan contract has expired.")
        # Session/expiry cutoffs require the exact exchange calendar and contract.
        # The staging adapter has no guessed fallback for these execution gates.
        if self.session_validator is None:
            raise ValueError("A verified Dhan contract session and expiry validator is required.")
        self.session_validator(dict(native,native_symbol=native.get('symbol')), now)
        return dict(native, native_symbol=native.get('symbol'), symbol=symbol, tick_size=str(tick), lot_size=int(lot),
                    tradable=True, linked_exit_capability="NATIVE_OCO",
                    products=["INTRADAY", "CNC", "MTF"] if segment.endswith("_EQ") else ["INTRADAY", "MARGIN"])

    def _exposure(self, client, contract):
        positions = client.request("GET", "/positions")
        orders = client.request("GET", "/orders")
        no_contract_exposure(client.client_id, contract["exchange_segment"],
                             contract["security_id"], positions, orders)

    def _plan(self, client, payload, account, contract, *, triggered=False):
        quote, received = fresh_quote_snapshot(client, contract["exchange_segment"],
                                              contract["security_id"], self.clock, max_age=5)
        try:
            bid = positive(quote["depth"]["buy"][0]["price"], "Dhan bid")
            ask = positive(quote["depth"]["sell"][0]["price"], "Dhan ask")
        except (KeyError, IndexError, TypeError):
            raise ValueError("Fresh two-sided Dhan market depth is required.") from None
        if bid > ask:
            raise ValueError("The Dhan market depth is crossed.")
        plan = build_plan(payload, account=account, contract=contract, quote=dict(
            account_id=self.account_id, symbol=contract["symbol"], last_price=quote.get("last_price"),
            received_at=received, provider_at=received), now=self.clock(), triggered_dhan_entry=triggered)
        return plan, dict(ltp=quote.get("last_price"), bid=str(bid), ask=str(ask),
                          provider_timestamp=received, timestamp_basis="DHAN_REST_SNAPSHOT")

    def prepare(self, payload):
        return self._prepare(payload)

    def _prepare(self, payload, *, triggered=False, own_token=None):
        self.last_preflight = None
        if payload.get("account_id") != self.account_id or payload.get("broker") != self.broker:
            raise PermissionError("The chart and Dhan execution account must match.")
        from .chart_trade_admission import assert_dhan_chart_entry_allowed
        assert_dhan_chart_entry_allowed(self.execution,client_order_id=own_token)
        self._journals()
        client = self.execution._client()
        contract = self._contract(str(payload.get("symbol") or ""))
        profile = client.request("GET", "/profile")
        ips = client.request("GET", "/ip/getIP")
        identity = account_identity(self.account, client.client_id, profile, ips,
                                    self.execution.egress(), segment=contract["exchange_segment"],
                                    product=payload.get("product"))
        account = dict(self.account, native_identity=identity,
                       native_entry_revision=entry_revision(self.broker,folder=self.execution.folder))
        self._exposure(client, contract)
        plan, quote = self._plan(client, payload, account, contract,triggered=triggered)
        margin_terms=dhan_super_margin_payload(plan,contract,broker_client_id=client.client_id)
        funds = client.request("GET", "/fundlimit")
        margin = client.request("POST", "/margincalculator", margin_terms)
        multiplier = positive(contract.get("quantity_multiplier", 1), "Dhan value multiplier")
        notional = Decimal(plan.limit_price)*plan.quantity*multiplier
        minimum = notional if plan.side == "BUY" and contract.get("option_type") in {"CE","PE"} else 0
        coverage = margin_coverage(client.client_id, funds, margin, minimum_required=minimum)
        # Native margin reads may take time. Refresh exposure and quote, never
        # place from the earlier snapshot or substitute a different entry type.
        self._journals()
        self._exposure(client, contract)
        self.session_validator(contract, datetime.fromtimestamp(self.clock(), IST))
        refreshed, quote = self._plan(client, payload, account, contract,triggered=triggered)
        if refreshed.fingerprint() != plan.fingerprint():
            raise ValueError("The Dhan chart plan changed during preview.")
        self.last_preflight = dict(coverage, fingerprint=plan.fingerprint(),
            checked_at=self.clock(), contract=contract, quote=quote,
            order_notional=str(notional),
            notice="Order value exceeds ₹50,000. Review the quantity and account carefully." if notional > 50000 else "",
            submission_available=self.live_enabled())
        return refreshed

    def warm_live_feed(self,plan):
        if self.tick_reader:self.tick_reader(plan.symbol)

    def refresh(self, plan):
        return self.prepare(plan.terms())

    def _durable_intent(self, plan, preview_id):
        path=Path(self.execution.folder)/"chart-trading.sqlite3"
        if not path.exists():raise ValueError("A durable reviewed Dhan chart intent is required.")
        with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=5)) as db:
            row=db.execute("SELECT plan,state,result FROM previews WHERE id=?",(preview_id,)).fetchone()
        if not row or row[1]!="SUBMISSION_UNCERTAIN" or ChartTradePlan(**json.loads(row[0])).fingerprint()!=plan.fingerprint():
            raise ValueError("The durable Dhan chart intent differs from this order.")
        intent=json.loads(row[2] or "{}")
        if intent.get("entry_order_id") or intent.get("filled_quantity") or intent.get("status")!="SUBMISSION_UNCERTAIN":
            raise ValueError("This Dhan intent already has native evidence; reconcile without retry.")
        return intent

    def _trigger_context(self,plan,preview_id,intent):
        proof=intent.get("conditional_trigger")
        if not isinstance(proof,dict) or not self.tick_reader:
            raise ValueError("A durable conditional claim and fresh Dhan WebSocket reader are required.")
        with closing(sqlite3.connect(Path(self.execution.folder)/"chart-trading.sqlite3",timeout=5)) as db:
            row=db.execute("SELECT plan,snapshot,claim_token FROM dhan_chart_conditions WHERE preview_id=?",(preview_id,)).fetchone()
        if not row or ChartTradePlan(**json.loads(row[0])).fingerprint()!=plan.fingerprint() or row[2]!=proof.get("claim_token"):
            raise ValueError("The Dhan conditional claim is not durably owned by this plan.")
        snapshot=json.loads(row[1])
        if snapshot.get("status")!="TRIGGERED" or self.clock()>=snapshot.get("expires_at",0):
            raise ValueError("The Dhan conditional claim expired or changed.")
        tick=self.tick_reader(plan.symbol)
        # Validate raw source and current trigger/stream before expensive reads.
        dhan_triggered_bracket_order(plan,dict(symbol=plan.symbol,exchange_segment=plan.symbol.split(":",1)[0],
            security_id=plan.symbol.split(":",1)[1]),client_order_id=preview_id,
            broker_client_id=self.account["account_ref"],claim=proof,tick=tick,now=self.clock())
        return proof,tick

    def refresh_triggered(self,plan,*,preview_id):
        intent=self._durable_intent(plan,preview_id)
        self._trigger_context(plan,preview_id,intent)
        token="CH"+hashlib.sha256(str(preview_id).encode()).hexdigest()[:24]
        refreshed=self._prepare(plan.terms(),triggered=True,own_token=token)
        if refreshed.fingerprint()!=plan.fingerprint():
            raise ValueError("Dhan contract, account or admission changed after the conditional entry review.")
        self.last_preflight["conditional_preview_id"]=preview_id
        return refreshed

    def submit_bracket(self, plan, *, idempotency_key):
        invoked=False
        try:
            if not self.live_enabled():
                raise PermissionError("Dhan chart submission is not activated for this account.")
            with self.execution.lock:
                with entry_lock(self.broker,folder=self.execution.folder):
                    with self.execution._submission_lock():
                        if not self.live_enabled():raise PermissionError("Dhan execution was disabled.")
                        state=self.last_preflight
                        if not state or state.get("fingerprint")!=plan.fingerprint():
                            raise ValueError("Refresh the exact Dhan chart order before submission.")
                        if plan.account_id!=self.account_id or plan.broker!=self.broker:
                            raise PermissionError("The selected Dhan execution account changed.")
                        if plan.native_entry_revision!=entry_revision(self.broker,folder=self.execution.folder):
                            raise ValueError("Another entry attempt changed the Dhan account; review again.")
                        intent=self._durable_intent(plan,idempotency_key)
                        self._journals()
                        client=self.execution._client()
                        identity=str(client.client_id)
                        if identity!=str(self.account.get("account_ref")) or hashlib.sha256(identity.encode()).hexdigest()!=plan.native_account_hash:
                            raise PermissionError("The Dhan native account differs from this reviewed order.")
                        contract=state["contract"]
                        self._exposure(client,contract)
                        self.session_validator(contract,datetime.fromtimestamp(self.clock(),IST))
                        refreshed,_=self._plan(client,plan.terms(),dict(self.account,
                            native_identity=plan.native_account_hash,native_entry_revision=plan.native_entry_revision),contract,
                            triggered=plan.entry_type=="STOP_LIMIT")
                        if refreshed.fingerprint()!=plan.fingerprint() or not 0<=self.clock()-state["checked_at"]<=5:
                            raise ValueError("The Dhan preflight aged or changed; prepare another review.")
                        if plan.entry_type=="STOP_LIMIT":
                            if state.get("conditional_preview_id")!=idempotency_key:
                                raise ValueError("Refresh the durably claimed Dhan trigger before placement.")
                            proof,tick=self._trigger_context(plan,idempotency_key,intent)
                            request=dhan_triggered_bracket_order(plan,contract,client_order_id=idempotency_key,
                                broker_client_id=identity,claim=proof,tick=tick,now=self.clock())
                        else:
                            request=native_bracket_order(plan,contract,client_order_id=idempotency_key,broker_client_id=identity)
                        sender=client.request
                        if not self.live_enabled():raise PermissionError("Dhan execution was disabled during final checks.")
                        mark_dhan_entry_attempt(self.execution,client_order_id=request["body"]["correlationId"])
                        invoked=True
                        try:
                            reply=sender(request["method"],request["path"],request["body"])
                        except DhanAPIError as error:
                            if error.definitive_rejection:return {"status":"REJECTED"}
                            raise
                        if isinstance(reply,dict) and reply.get("orderStatus")=="REJECTED":
                            return {"status":"REJECTED"}
                        if isinstance(reply,dict) and reply.get("orderId"):
                            return dict(entry_order_id=str(reply["orderId"]),account_id=self.account_id,
                                        broker=self.broker,symbol=plan.symbol)
                        return {"status":"SUBMISSION_UNCERTAIN"}
        except Exception as error:
            if invoked:raise
            raise ChartOrderNotSent("A final Dhan chart pre-submission check failed; no placement was invoked.") from error

    def reconcile(self, plan, *, preview_id, entry_order_id=None):
        from .chart_trade_dhan_reconciliation import reconcile_dhan_super
        from .chart_trade_dhan_exits import reconcile_dhan_exits
        if plan.account_id != self.account_id or plan.broker != self.broker:
            raise PermissionError("The chart order belongs to a different Dhan account.")
        started=self.clock()
        client=self.execution._client()
        profile=client.request("GET","/profile")
        identity=str(profile.get("dhanClientId") or "") if isinstance(profile,dict) else ""
        if (not identity or identity!=str(client.client_id) or identity!=str(self.account.get("account_ref"))
                or not plan.native_account_hash or hashlib.sha256(identity.encode()).hexdigest()!=plan.native_account_hash):
            raise PermissionError("The native Dhan login differs from the chart order owner.")
        segment,security=plan.symbol.split(":",1)
        contract=dict(symbol=plan.symbol,exchange_segment=segment,security_id=security)
        rows=client.request("GET","/super/orders")
        proof=reconcile_dhan_super(plan,contract,preview_id=preview_id,broker_client_id=client.client_id,
                                   rows=rows,entry_order_id=entry_order_id)
        if proof.get("filled_quantity",0)>0:
            owned=[row for row in rows if str(row.get("orderId"))==proof.get("entry_order_id")]
            if len(owned)!=1:raise ValueError("The owned Dhan parent is ambiguous.")
            parent=owned[0]
            orders=client.request("GET","/orders")
            trades=client.request("GET","/trades")
            positions=client.request("GET","/positions")
            refreshed=client.request("GET","/super/orders")
            current=[row for row in refreshed if isinstance(row,dict) and str(row.get("orderId"))==str(parent["orderId"])] if isinstance(refreshed,list) else []
            if len(current)!=1 or current[0]!=parent:
                raise ValueError("The Dhan Super parent changed while its exchange fills were read.")
            exits=reconcile_dhan_exits(plan,contract,parent,client_id=client.client_id,preview_id=preview_id,
                                      orders=orders,trades=trades,positions=positions)
            if (proof.get("protection_confirmed") is True and exits.get("status")=="ENTRY_FILLED_EXITS_UNVERIFIED"
                    and exits.get("open_quantity")==plan.quantity and exits.get("exited_quantity")==0):
                proof=dict(proof,open_quantity=exits["open_quantity"],exited_quantity=0)
            else:
                proof=exits
        checked=self.clock()
        if not 0<=checked-started<=5:
            raise ValueError("The native Dhan status snapshot aged during reconciliation; refresh it.")
        return dict(proof,checked_at=checked)
