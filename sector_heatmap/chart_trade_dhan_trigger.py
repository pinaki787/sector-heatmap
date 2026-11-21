"""Pure, serializable Dhan stop-limit trigger state; never submits an order.

Only selected-account raw WebSocket ticker evidence is accepted. A durable
worker must atomically claim TRIGGERED before any future native placement.
"""
from dataclasses import dataclass, asdict, replace
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
import struct
from .chart_trade_plan import ChartTradePlan, positive


@dataclass(frozen=True)
class DhanTriggerState:
    fingerprint: str
    account_id: str
    symbol: str
    native_account_hash: str
    armed_at: float
    expires_at: float
    stream_id: str
    connection_revision: int
    sequence: int
    provider_at: float
    received_at: float
    status: str = "WAITING_FOR_TRIGGER"
    reason: str = ""
    trigger_price: str = ""
    triggered_at: float | None = None

    def terms(self):
        return asdict(self)


def wire_tick_price(value, tick):
    """Resolve float32 ticker quantization only when one exact broker tick fits."""
    price=positive(value,"Native Dhan ticker price")
    step=positive(tick,"Native Dhan tick")
    try:
        numeric=float(price)
        wire=struct.unpack("<f",struct.pack("<f",numeric))[0]
    except (ValueError,OverflowError,struct.error):
        raise ValueError("The Dhan ticker price cannot be verified.") from None
    if not math.isfinite(wire) or wire!=numeric:
        raise ValueError("The price is not an unmodified Dhan float32 ticker value.")
    spacing=Decimal(2)**max(-149,math.frexp(wire)[1]-24)
    if step<=spacing:
        raise ValueError("Dhan ticker precision cannot uniquely resolve this contract tick.")
    with localcontext() as context:
        context.prec=60
        exact=(price/step).to_integral_value(rounding=ROUND_HALF_UP)*step
        # Decimal(str(float32)) incurs only decimal representation noise.
        tolerance=spacing/2+abs(price)*Decimal("1e-15")
        if exact<=0 or abs(exact-price)>tolerance:
            raise ValueError("The Dhan ticker price does not match a unique native contract tick.")
        return exact


def _tick(plan,tick,now):
    if not isinstance(tick,dict) or tick.get("source")!="BROKER_WEBSOCKET":
        raise ValueError("A raw Dhan WebSocket tick is required.")
    if (tick.get("broker")!="DHAN" or tick.get("account_id")!=plan.account_id
            or tick.get("symbol")!=plan.symbol or not plan.native_account_hash
            or tick.get("native_account_hash")!=plan.native_account_hash):
        raise ValueError("The Dhan ticker belongs to a different account or instrument.")
    for field in ("sequence","connection_revision"):
        if type(tick.get(field)) is not int or tick[field]<=0:
            raise ValueError("A verified native ticker sequence and connection are required.")
    stream=tick.get("stream_id")
    if not isinstance(stream,str) or len(stream)!=32 or any(c not in "0123456789abcdef" for c in stream):
        raise ValueError("A verified ticker stream instance is required.")
    try:
        provider=float(tick["provider_at"]);received=float(tick["received_at"])
    except (KeyError,TypeError,ValueError):
        raise ValueError("Native ticker timing is unavailable.") from None
    if not all(math.isfinite(v) for v in (now,provider,received)) or not 0<=now-received<=2 or not -1<=now-provider<=2:
        raise ValueError("The native Dhan tick is stale or its clock is invalid.")
    return wire_tick_price(tick.get("price"),plan.tick_size),provider,received


def arm_trigger(plan,tick,*,now,expires_at):
    if not isinstance(plan,ChartTradePlan) or plan.broker!="DHAN" or plan.entry_type!="STOP_LIMIT":
        raise ValueError("An exact reviewed Dhan stop-limit chart plan is required.")
    now=float(now);expires=float(expires_at)
    if not math.isfinite(expires) or expires<=now:
        raise ValueError("A future conditional-entry expiry is required.")
    price,provider,received=_tick(plan,tick,now)
    entry=positive(plan.entry,"Entry")
    limit=positive(plan.limit_price,"Entry cap")
    target=positive(plan.target,"Target")
    stop=positive(plan.stop_loss,"Stop")
    if not (stop<entry<limit<target and price<entry if plan.side=="BUY" else target<limit<entry<stop and price>entry if plan.side=="SELL" else False):
        raise ValueError("Review a new conditional order; the fresh broker price or marked geometry changed.")
    return DhanTriggerState(plan.fingerprint(),plan.account_id,plan.symbol,plan.native_account_hash,
        now,expires,tick["stream_id"],tick["connection_revision"],tick["sequence"],provider,received)


def evaluate_trigger(state,plan,tick,*,now):
    if state.status!="WAITING_FOR_TRIGGER":
        return state
    now=float(now)
    def review(reason):
        return replace(state,status="REVIEW_REQUIRED",reason=reason)
    if not math.isfinite(now) or now<state.armed_at or now<state.received_at:
        return review("The conditional-entry clock changed.")
    if state.fingerprint!=plan.fingerprint():
        return review("The reviewed chart order changed.")
    if now>=state.expires_at:
        return replace(state,status="EXPIRED",reason="The conditional entry expired without a native placement.")
    if now-state.received_at>2:
        return review("The Dhan ticker had a freshness gap; review this entry again.")
    if tick is None:
        return state
    try:price,provider,received=_tick(plan,tick,now)
    except (ValueError,TypeError) as error:return review(str(error))
    if tick["stream_id"]!=state.stream_id or tick["connection_revision"]!=state.connection_revision:
        return review("The Dhan stream reconnected or restarted; review this entry again.")
    if tick["sequence"]<state.sequence or provider<state.provider_at or received<state.received_at:
        return review("Dhan ticker ordering changed; review this entry again.")
    if tick["sequence"]==state.sequence:
        return state
    updated=replace(state,sequence=tick["sequence"],provider_at=provider,received_at=received)
    # Dhan LTT has whole-second precision. A packet stamped before the arm
    # instant cannot establish that the marked level was reached after arming.
    if provider<state.armed_at:
        return updated
    reached=price>=Decimal(plan.entry) if plan.side=="BUY" else price<=Decimal(plan.entry)
    if not reached:return updated
    return replace(updated,status="TRIGGERED",trigger_price=str(price),triggered_at=now,
                   reason="A fresh owned Dhan tick reached the marked trigger; the reviewed entry cap remains unchanged.")
