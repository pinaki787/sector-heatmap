"""Read-only FYERS report evidence; historical rows never establish exit linkage.

Official schema: https://fyers.in/api-docs/v3/api/reports/{order,trade}-history/
Reports omit parentId and stopPrice. Do not synthesize native bracket children.
"""
from datetime import datetime
from decimal import Decimal
import hashlib
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def read_reports(reader, *, symbol, identity_hash, started_at, now, page_size=100, max_pages=20):
    if not 0 < started_at <= now or not identity_hash or not symbol:
        raise ValueError("The owned order's historical scope is unavailable.")
    scope = dict(symbol=symbol,
                 from_date=datetime.fromtimestamp(started_at, IST).date().isoformat(),
                 to_date=datetime.fromtimestamp(now, IST).date().isoformat(),
                 segment_type="0", exchange_type="0", page_size=str(page_size))
    reports = {}
    for name, key in (("order-history", "id_fyers"), ("trade-history", "tradeNumber")):
        found = {}
        previous_pages = set()
        for page in range(1, max_pages+1):
            reply = reader(name, dict(scope, page_no=str(page)))
            if not isinstance(reply, dict) or reply.get("s") != "ok" or not isinstance(reply.get("data"), list):
                raise ValueError("The FYERS historical report is unavailable.")
            rows = reply["data"]
            if len(rows) > page_size:
                raise ValueError("The FYERS historical page exceeds its requested size.")
            signature = []
            for row in rows:
                if (not isinstance(row, dict) or row.get("symbol") != symbol
                        or not row.get("clientId")
                        or hashlib.sha256(str(row["clientId"]).encode()).hexdigest() != identity_hash
                        or not row.get(key)):
                    raise ValueError("The FYERS historical report account or contract differs.")
                # Trade numbers are scoped to an exchange/segment/order, not globally unique.
                row_key = (str(row.get("exchange")), str(row.get("segment")),
                           str(row.get("orderNumber", "")), str(row[key]))
                signature.append(row_key)
                if row_key in found and found[row_key] != row:
                    raise ValueError("Conflicting historical records require broker review.")
                found[row_key] = dict(row)
            signature = tuple(signature)
            if rows and signature in previous_pages:
                raise ValueError("The FYERS historical report repeated a page.")
            previous_pages.add(signature)
            if len(rows) < page_size:
                reports[name] = list(found.values())
                break
        else:
            raise ValueError("The FYERS historical report exceeds the verified pagination limit.")
    return reports


def reconcile_archived_entry(plan, reports, entry_order_id):
    from .chart_trade_reconciliation import _number
    base = dict(account_id=plan.account_id, broker=plan.broker, symbol=plan.symbol,
                entry_order_id=str(entry_order_id), retry_allowed=False, protection_confirmed=False,
                open_quantity=None, exited_quantity=None)
    def state(status, message, **fields):
        return dict(base, status=status, message=message, **fields)
    parents = [r for r in reports["order-history"] if str(r.get("id_fyers")) == str(entry_order_id)]
    if len(parents) != 1:
        return state("BROKER_STATUS_UNAVAILABLE", "The owned entry is not uniquely present in broker history. Do not resubmit.")
    parent = parents[0]
    # Historical product labels differ from the current order book. Only documented mappings.
    products = {"INTRADAY": {"Intraday", "INTRADAY"}, "MARGIN": {"Overnight", "MARGIN"},
                "CNC": {"CNC", "Delivery"}, "MTF": {"MTF"}}
    if (parent.get("symbol") != plan.symbol or parent.get("transaction_type") != plan.side
            or parent.get("product_type") not in products.get(plan.product, set())
            or _number(parent.get("qty")) != plan.quantity
            or _number(parent.get("limit_price")) != _number(plan.limit_price)):
        raise ValueError("The historical entry differs from the reviewed native order.")
    # The public schema calls this tradedQty; its official example uses tradedqty.
    values = [parent[k] for k in ("tradedQty", "tradedqty") if k in parent]
    if not values or any(_number(v) != _number(values[0]) for v in values):
        raise ValueError("The historical entry filled quantity is ambiguous.")
    filled = _number(values[0])
    if filled != int(filled) or not 0 <= filled <= plan.quantity:
        raise ValueError("The historical entry filled quantity is invalid.")
    if filled and not parent.get("exchOrdId"):
        raise ValueError("The historical filled entry has no exchange order identity.")
    status = parent.get("status")
    if status not in {"Executed", "Cancelled", "Rejected"} or (status == "Executed" and filled != plan.quantity):
        raise ValueError("The historical entry status and quantities disagree.")
    trades = [r for r in reports["trade-history"] if str(r.get("orderNumber")) == str(entry_order_id)]
    total = Decimal(0)
    for trade in trades:
        qty = _number(trade.get("traded_qty"))
        if (trade.get("symbol") != plan.symbol or str(trade.get("side")) != ("1" if plan.side == "BUY" else "-1")
                or trade.get("product_type") not in products.get(plan.product, set())
                or str(trade.get("exchangeOrderNo")) != str(parent["exchOrdId"])
                or trade.get("exchange") != parent.get("exchange")
                or trade.get("segment") != parent.get("segment")
                or qty <= 0 or qty != int(qty) or _number(trade.get("trade_price")) <= 0):
            raise ValueError("The historical fill differs from the owned entry.")
        total += qty
    if total != filled:
        return state("BROKER_STATUS_UNAVAILABLE", "Historical order and exchange fills disagree. Do not resubmit.")
    if filled == 0:
        if status == "Executed":
            raise ValueError("An executed historical entry has no fills.")
        return state({"Cancelled": "CANCELLED", "Rejected": "REJECTED"}[status],
                     "Broker history confirms a terminal entry with no fills.", filled_quantity=0,
                     pending_quantity=0, unfilled_quantity=int(plan.quantity), evidence_source="BROKER_HISTORY")
    return state("ENTRY_FILLED_EXITS_UNVERIFIED",
                 "Historical exchange fills confirm the entry. Historical reports do not prove linked exit protection.",
                 filled_quantity=int(filled), pending_quantity=0,
                 unfilled_quantity=int(plan.quantity-filled), evidence_source="BROKER_HISTORY")
