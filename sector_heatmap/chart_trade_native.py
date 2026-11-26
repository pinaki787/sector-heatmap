"""Broker-native payloads for reviewed chart levels; no network requests.

References checked 18 November 2026:
FYERS sync/single-order (absolute stopLoss/takeProfit, no legType);
Dhan v2 super-order; Delta v2 CreateOrderRequest bracket fields.
"""
from decimal import Decimal
import hashlib
import math
from .chart_trade_plan import ChartTradePlan


def _number(value):
    exact=Decimal(value)
    result=float(exact)
    if not math.isfinite(result) or Decimal(str(result))!=exact:
        raise ValueError("The broker numeric transport cannot preserve this exact executable price.")
    return result


def native_bracket_order(plan, contract, *, client_order_id, broker_client_id=None):
    if not isinstance(plan, ChartTradePlan) or contract.get("symbol") != plan.symbol:
        raise ValueError("An exact reviewed native chart plan is required.")
    if not client_order_id:
        raise ValueError("A durable chart submission identifier is required.")
    token = "CH" + hashlib.sha256(str(client_order_id).encode()).hexdigest()[:24]
    if plan.broker == "FYERS":
        if plan.product not in {"INTRADAY", "CNC", "MARGIN", "MTF"}:
            raise ValueError("Unsupported FYERS chart product.")
        return {"method": "POST", "path": "/api/v3/orders/sync",
                "sdk_method": "place_order",
                "body": {"symbol": plan.symbol, "qty": plan.quantity,
                         "type": 4 if plan.entry_type == "STOP_LIMIT" else 1,
                         "side": 1 if plan.side == "BUY" else -1, "productType": plan.product,
                         "limitPrice": _number(plan.limit_price),
                         "stopPrice": _number(plan.entry) if plan.entry_type == "STOP_LIMIT" else 0,
                         "stopLoss": _number(plan.stop_loss), "takeProfit": _number(plan.target),
                         "validity": "DAY", "offlineOrder": False, "disclosedQty": 0, "isSliceOrder": False,
                         "orderTag": token},
                "entry_trigger": plan.price_trigger,
                "exit_price_basis": "ABSOLUTE_PRICE", "linked_exit_host": "BROKER"}
    if plan.broker == "DHAN":
        # Published v2 Super Order API currently documents LIMIT/MARKET only.
        # Never turn a reviewed breakout into an immediately marketable LIMIT.
        if plan.entry_type != "LIMIT":
            raise ValueError("Dhan stop-limit chart entry requires a verified conditional-entry adapter; no limit or market substitution.")
        if not broker_client_id or not contract.get("security_id") or not contract.get("exchange_segment"):
            raise ValueError("Selected-account Dhan client and exact security/segment are required.")
        return {"method": "POST", "path": "/super/orders",
                "body": {"dhanClientId": str(broker_client_id), "correlationId": token,
                         "transactionType": plan.side, "exchangeSegment": contract["exchange_segment"],
                         "securityId": str(contract["security_id"]), "productType": plan.product,
                         "orderType": "LIMIT", "quantity": plan.quantity, "price": _number(plan.limit_price),
                         "stopLossPrice": _number(plan.stop_loss), "targetPrice": _number(plan.target),
                         "trailingJump": 0},
                "entry_trigger": plan.price_trigger,
                "exit_price_basis": "ABSOLUTE_PRICE", "linked_exit_host": "BROKER"}
    if plan.broker == "DELTA_INDIA":
        product_id = contract.get("product_id")
        if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
            raise ValueError("The exact Delta product ID is required.")
        body = {"product_id": product_id, "size": plan.quantity, "side": plan.side.lower(),
                "order_type": "limit_order", "limit_price": plan.limit_price,
                "time_in_force": "gtc", "client_order_id": token,
                "reduce_only": False, "post_only": False, "cancel_orders_accepted": False,
                "bracket_stop_trigger_method": plan.exit_trigger_method,
                "bracket_stop_loss_price": plan.stop_loss, "bracket_take_profit_price": plan.target}
        if plan.entry_type == "STOP_LIMIT":
            body.update(stop_order_type="stop_loss_order", stop_price=plan.entry,
                        stop_trigger_method="last_traded_price")
        return {"method": "POST", "path": "/v2/orders", "body": body,
                "entry_trigger": plan.price_trigger,
                "exit_price_basis": "ABSOLUTE_PRICE", "linked_exit_host": "BROKER"}
    raise ValueError("The selected broker needs a verified linked-exit execution adapter before this chart order can be armed.")



def dhan_super_margin_payload(plan,contract,*,broker_client_id):
    """Read-only calculator terms; never permission to place a conditional entry."""
    from dataclasses import replace
    if plan.broker!="DHAN":
        raise ValueError("Dhan margin terms require a Dhan chart plan.")
    native=replace(plan,entry_type="LIMIT",entry=plan.limit_price)
    body=native_bracket_order(native,contract,client_order_id="MARGIN-PREVIEW",
                              broker_client_id=broker_client_id)["body"]
    return {key:value for key,value in body.items() if key in {
        "dhanClientId","exchangeSegment","transactionType","quantity",
        "productType","securityId","price"}} | {"triggerPrice":0}


def dhan_triggered_bracket_order(plan,contract,*,client_order_id,broker_client_id,claim,tick,now):
    """Explicit claimed STOP_LIMIT transition; no untriggered LIMIT fallback."""
    from dataclasses import replace
    from .chart_trade_dhan_trigger import _tick
    if plan.broker!="DHAN" or plan.entry_type!="STOP_LIMIT" or not isinstance(claim,dict):
        raise ValueError("A durably claimed Dhan stop-limit trigger is required.")
    if claim.get("fingerprint")!=plan.fingerprint():
        raise ValueError("The claimed Dhan trigger differs from this reviewed order.")
    token=claim.get("claim_token")
    if not isinstance(token,str) or len(token)!=32 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("A verified durable conditional-entry claim token is required.")
    try:age=float(now)-float(claim["claimed_at"])
    except (KeyError,TypeError,ValueError):
        raise ValueError("The Dhan trigger claim time is unavailable.") from None
    if not math.isfinite(age) or not 0<=age<=30:
        raise ValueError("The Dhan trigger claim aged before native placement.")
    price,provider,received=_tick(plan,tick,float(now))
    if (tick["stream_id"]!=claim.get("stream_id") or tick["connection_revision"]!=claim.get("connection_revision")
            or tick["sequence"]<claim.get("sequence",0) or provider<claim.get("provider_at",float("inf"))
            or received<claim.get("received_at",float("inf"))):
        raise ValueError("The Dhan trigger stream changed after its durable claim.")
    if not (price>=Decimal(plan.entry) if plan.side=="BUY" else price<=Decimal(plan.entry)):
        raise ValueError("Fresh native price no longer satisfies the claimed Dhan entry trigger.")
    # The trigger was managed and claimed above. The separately reviewed cap
    # is the actual broker limit; persisted plan/fingerprint remains STOP_LIMIT.
    native=replace(plan,entry_type="LIMIT",entry=plan.limit_price)
    result=native_bracket_order(native,contract,client_order_id=client_order_id,
                               broker_client_id=broker_client_id)
    return dict(result,entry_trigger=plan.price_trigger,managed_trigger=plan.entry,
                reviewed_fingerprint=plan.fingerprint())
