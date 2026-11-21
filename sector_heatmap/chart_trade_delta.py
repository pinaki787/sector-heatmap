"""Delta chart entries with broker-attached exits; staged, not HTTP-activated."""
from datetime import datetime
from decimal import Decimal
import time
from .chart_trade_native import native_bracket_order
from .chart_trade_plan import build_plan
from .chart_trade_admission import entry_revision,ChartOrderNotSent


class DeltaChartAdapter:
    broker = "DELTA_INDIA"

    def __init__(self, account, execution, *, clock=time.time):
        if account.get("broker") != self.broker:
            raise PermissionError("A Delta India account is required.")
        self.account = dict(account)
        self.account_id = account["id"]
        self.execution = execution
        self.clock = clock
        self.last_preflight = None

    def live_enabled(self):
        return bool(self.account.get("live_enabled") and self.execution._gate() and not self.execution.corrupt)

    def _flat_lifecycle(self, product_id):
        execution = self.execution
        if execution.corrupt:
            raise ValueError("Reconcile the Delta execution ledger before preparing chart orders.")
        if (execution.runner.get("running") or execution.runner.get("pending")
                or execution.live.get("runner_position") or execution.paper.get("position")):
            raise ValueError("An existing Delta lifecycle must be resolved before a chart entry.")
        if any(row.get("status") in {"SUBMITTING","UNKNOWN","open","pending","CANCEL_UNKNOWN"}
               for row in (execution.live.get("orders") or {}).values()):
            raise ValueError("An outstanding owned Delta order must be reconciled before a chart entry.")
        if execution._position(product_id) != 0:
            raise ValueError("An existing position in this Delta product requires its own exit workflow.")
        reply = execution._private("GET","/v2/orders",params={"product_ids":product_id,"states":"open,pending"})
        rows = reply.get("result")
        if not isinstance(rows,list) or (reply.get("meta") or {}).get("after"):
            raise ValueError("The Delta pending-order snapshot is incomplete.")
        if any(str(row.get("product_id")) == str(product_id) and row.get("state") in {"open","pending"} for row in rows):
            raise ValueError("An existing pending Delta product order must be reconciled first.")

    def _contract(self,symbol):
        self.execution.cache.pop(("product",symbol),None)
        self.execution.cache.pop(("product",symbol,"chart"),None)
        product = self.execution.product(symbol,chart=True)
        if product.get("contract_type") not in {"perpetual_futures","futures","call_options","put_options"}:
            raise ValueError("Native chart entry/exit verification is not yet implemented for this Delta contract type.")
        if (product.get("trading_status") != "operational"
                or (product.get("product_specs") or {}).get("only_reduce_only_orders_allowed")):
            raise ValueError("The Delta product currently does not permit new entries.")
        expiry = product.get("settlement_time")
        expiry = datetime.fromisoformat(expiry.replace("Z","+00:00")).timestamp() if expiry else None
        contract = dict(symbol=product["symbol"],product_id=product["id"],tick_size=product["tick_size"],
                        lot_size=1,expires_at=expiry,tradable=True,products=["MARGIN"],
                        linked_exit_capability="NATIVE_OCO")
        return contract,product

    def _quote(self,symbol):
        reply=self.execution._get("/v2/tickers/"+symbol)
        row=reply.get("result") or {}
        quotes=row.get("quotes") or {}
        last=Decimal(str(row.get("close")))
        bid,ask=(Decimal(str(quotes.get(name))) for name in ("best_bid","best_ask"))
        if row.get("symbol")!=symbol or not all(value.is_finite() and value>0 for value in (last,bid,ask)) or bid>ask:
            raise ValueError("Fresh Delta last-trade and executable bid/ask evidence is required.")
        return dict(account_id=self.account_id,symbol=symbol,last_price=str(last),
                    received_at=self.clock(),provider_at=float(row.get("timestamp",0))/1e6,
                    bid=str(bid),ask=str(ask),mark_price=row.get("mark_price"))

    def _wallet(self,product):
        currency=product.get("settlement_currency")
        rows=self.execution._private("GET","/v2/wallet/balances").get("result")
        if not currency or not isinstance(rows,list):
            raise ValueError("Verified native Delta settlement wallet evidence is required.")
        matches=[row for row in rows if row.get("asset_symbol")==currency]
        if len(matches)!=1:
            raise ValueError("The exact Delta settlement wallet could not be resolved.")
        available=Decimal(str(matches[0].get("available_balance")))
        if not available.is_finite() or available<=0:
            raise ValueError("No positive available balance in this contract's settlement wallet.")
        return currency,available

    def prepare(self,payload):
        with self.execution.lock:
            from .chart_trade_ownership import assert_workspace_chart_entry_allowed
            assert_workspace_chart_entry_allowed(self.broker)
            self.execution.verify_auth()  # Authenticated read, no live gate changes.
            identity=self.execution._identity()
            contract,product=self._contract(str(payload.get("symbol") or ""))
            self._flat_lifecycle(contract["product_id"])
            currency,available=self._wallet(product)
            quote=self._quote(contract["symbol"])
            plan=build_plan(payload,account=dict(self.account,native_identity=identity,native_entry_revision=entry_revision(self.broker)),
                            contract=contract,quote=quote,now=self.clock())
            if plan.quantity > 100000:
                raise ValueError("Delta chart orders retain the existing 100,000-contract execution limit.")
            self._flat_lifecycle(contract["product_id"])
            self.last_preflight=dict(fingerprint=plan.fingerprint(),checked_at=self.clock(),contract=contract,
                                     available_funds=str(available),settlement_currency=currency,
                                     margin_status="BROKER_ENFORCED_ON_SUBMISSION",quote=quote)
            return plan

    def refresh(self,plan):
        return self.prepare(plan.terms())

    def submit_bracket(self,plan,*,idempotency_key):
        with self.execution.lock:
            try:
                if not self.live_enabled():
                    raise PermissionError("The selected Delta account live gate is disabled.")
                state=self.last_preflight
                if (not state or state["fingerprint"]!=plan.fingerprint()
                        or not 0<=self.clock()-state["checked_at"]<=5
                        or plan.native_account_hash!=self.execution._identity()):
                    raise ValueError("Refresh this exact Delta chart order before submitting.")
                self.execution._live_ready()
                self._flat_lifecycle(state["contract"]["product_id"])
                # Re-read wallet and quote after the auth/exposure checks.
                contract,product=self._contract(plan.symbol)
                self._wallet(product)
                refreshed=build_plan(plan.terms(),account=dict(self.account,native_identity=self.execution._identity(),native_entry_revision=entry_revision(self.broker)),
                                     contract=contract,quote=self._quote(plan.symbol),now=self.clock())
                if refreshed.fingerprint()!=plan.fingerprint():
                    raise ValueError("The Delta contract or account changed; review a new chart order.")
                request=native_bracket_order(plan,contract,client_order_id=idempotency_key)
            except Exception as error:
                raise ChartOrderNotSent("A final Delta chart pre-submission check failed.") from error
            reply=self.execution._private("POST",request["path"],body=request["body"])
            order=reply.get("result") or {}
            # An uncertain response is never retried; durable intent is owned by the preview store.
            if (order.get("id") and str(order.get("product_id"))==str(contract["product_id"])
                    and order.get("side")==plan.side.lower()
                    and Decimal(str(order.get("size")))==plan.quantity
                    and order.get("client_order_id")==request["body"]["client_order_id"]
                    and Decimal(str(order.get("limit_price")))==Decimal(plan.limit_price)
                    and (plan.entry_type!="STOP_LIMIT" or Decimal(str(order.get("stop_price")))==Decimal(plan.entry))):
                return dict(entry_order_id=str(order["id"]),account_id=self.account_id,symbol=plan.symbol)
            return dict(status="SUBMISSION_UNCERTAIN")

    def reconcile(self,plan,*,preview_id,entry_order_id=None):
        import hashlib
        if plan.account_id!=self.account_id or plan.broker!=self.broker or plan.native_account_hash!=self.execution._identity():
            raise PermissionError("The Delta credentials or chart account changed.")
        token="CH"+hashlib.sha256(str(preview_id).encode()).hexdigest()[:24]
        row=self.execution._private("GET","/v2/orders/client_order_id/"+token).get("result")
        if not isinstance(row,dict):
            raise ValueError("The owned Delta order could not be read.")
        if (row.get("client_order_id")!=token or row.get("product_symbol")!=plan.symbol
                or row.get("side")!=plan.side.lower() or (entry_order_id and str(row.get("id"))!=str(entry_order_id))):
            raise ValueError("The native Delta order differs from this chart entry.")
        size,unfilled=(Decimal(str(row.get(key))) for key in ("size","unfilled_size"))
        if (not all(value.is_finite() and value==int(value) for value in (size,unfilled))
                or size!=plan.quantity or not 0<=unfilled<=size):
            raise ValueError("The Delta entry quantities cannot be reconciled.")
        filled=size-unfilled
        state=row.get("state")
        result=dict(account_id=self.account_id,broker=self.broker,symbol=plan.symbol,
                    entry_order_id=str(row["id"]),filled_quantity=int(filled),pending_quantity=int(unfilled),
                    protection_confirmed=False,retry_allowed=False,checked_at=self.clock(),
                    unfilled_quantity=int(unfilled))
        if state in {"closed","cancelled"}:
            result["pending_quantity"]=0
        if state not in {"open","pending","closed","cancelled"} or (state=="closed" and unfilled!=0):
            return dict(result,status="BROKER_STATUS_UNAVAILABLE",message="The Delta order status and quantities disagree.")
        if filled>0:
            average=Decimal(str(row.get("average_fill_price")))
            if not average.is_finite() or average<=0:
                raise ValueError("Delta entry fill-price evidence is unavailable.")
            result.update(average_fill_price=str(average))
            try:
                proof=self._exit_snapshot(plan,row)
            except (ValueError,KeyError,TypeError,ArithmeticError):
                return dict(result,status="ENTRY_FILLED_EXITS_UNVERIFIED" if unfilled==0 else "ENTRY_PARTIALLY_FILLED_EXITS_UNVERIFIED",
                            message="Native Delta entry fills are confirmed, but complete position-bracket evidence is unavailable.")
            return dict(result,**proof)
        if state=="cancelled":
            return dict(result,status="CANCELLED",message="Delta reports the entry cancelled with no confirmed fills.")
        return dict(result,status="ENTRY_PENDING",message="Delta entry is pending; no entry fill is confirmed.")

    @staticmethod
    def _timestamp(value):
        text=str(value or "")
        if text.isdigit():
            stamp=int(text)
            return stamp if stamp>10**12 else stamp*1000000
        parsed=datetime.fromisoformat(text.replace("Z","+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("A timezone-qualified Delta order timestamp is required.")
        return int(parsed.timestamp()*1000000)

    def _pages(self,path,params):
        rows=[];cursor=None;seen=set()
        for _ in range(20):
            query=dict(params,page_size=100)
            if cursor:query["after"]=cursor
            reply=self.execution._private("GET",path,params=query)
            batch=reply.get("result")
            if not isinstance(batch,list):
                raise ValueError("Complete Delta order/fill evidence is unavailable.")
            rows.extend(batch)
            cursor=(reply.get("meta") or {}).get("after")
            if not cursor:return rows
            if cursor in seen:raise ValueError("Delta broker pagination repeated.")
            seen.add(cursor)
        raise ValueError("Delta broker history is incomplete; exit protection cannot be verified.")

    def _exit_snapshot(self,plan,parent):
        from .chart_trade_delta_exits import verify_delta_exits
        product_id=parent["product_id"]
        start=self._timestamp(parent["created_at"])
        end=int(self.clock()*1000000)
        if not 0<start<=end:
            raise ValueError("The Delta parent creation timestamp is unavailable.")
        params=dict(product_ids=product_id,start_time=start,end_time=end)
        active=self._pages("/v2/orders",dict(product_ids=product_id,states="open,pending"))
        history=self._pages("/v2/orders/history",params)
        # Retain only the current entry's time window, regardless of server filtering.
        history=[row for row in history if self._timestamp(row.get("created_at"))>=start]
        fills=self._pages("/v2/fills",params)
        fills=[row for row in fills if self._timestamp(row.get("created_at"))>=start]
        position=self.execution._position(product_id)
        latest=self.execution._private("GET","/v2/orders/client_order_id/"+parent["client_order_id"]).get("result") or {}
        if any(latest.get(key)!=parent.get(key) for key in ("id","size","unfilled_size","state")):
            raise ValueError("The Delta parent changed while exits were read.")
        return verify_delta_exits(plan,parent,active+history,fills,position)
