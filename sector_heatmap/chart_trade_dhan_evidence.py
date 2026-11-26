"""Strict read-only account evidence for the staged Dhan chart adapter.

These checks do not resolve a security, authorize trading, or submit an order.
"""
from hashlib import sha256
from ipaddress import ip_address
from .dhan_protection import number

SEGMENTS = {"NSE_EQ": "Equity", "BSE_EQ": "Equity",
            "NSE_FNO": "Derivative", "BSE_FNO": "Derivative",
            "NSE_CURRENCY": "Currency", "BSE_CURRENCY": "Currency",
            "MCX_COMM": "Commodity"}


def account_identity(account, client_id, profile, ips, egress, *, segment, product):
    if account.get("broker") != "DHAN" or not account.get("id"):
        raise PermissionError("Select a registered Dhan account.")
    client_id = str(client_id or "")
    if not client_id or str(account.get("account_ref") or "") != client_id:
        raise PermissionError("The selected Dhan account and credential client differ.")
    if not isinstance(profile, dict) or str(profile.get("dhanClientId") or "") != client_id:
        raise PermissionError("The native Dhan session belongs to a different account.")
    if str(profile.get("dataPlan") or "").strip().lower() != "active":
        raise ValueError("Dhan Data API subscription must be active for fresh chart execution quotes.")
    expected = SEGMENTS.get(segment)
    if expected is None:
        raise ValueError("This chart symbol has no verified tradable Dhan exchange segment.")
    active = {part.strip().casefold() for part in str(profile.get("activeSegment") or "").split(",")}
    if expected.casefold() not in active:
        raise ValueError("The selected Dhan account has not activated this exchange segment.")
    if product == "MTF" and str(profile.get("mtf") or "").strip().lower() != "active":
        raise ValueError("MTF is not active for the selected Dhan account.")
    if product not in {"CNC", "INTRADAY", "MARGIN", "MTF"}:
        raise ValueError("Choose a supported Dhan chart product.")
    if product in {"CNC", "MTF"} and not segment.endswith("_EQ"):
        raise ValueError("Delivery and MTF products cannot be used for a derivative contract.")
    if product == "MARGIN" and segment.endswith("_EQ"):
        raise ValueError("Choose a verified equity product for this Dhan contract.")
    if not isinstance(ips, dict):
        raise ValueError("Dhan static IP evidence is unavailable.")
    try:
        outgoing = ip_address(egress)
        allowed = {ip_address(value) for value in (ips.get("primaryIP"), ips.get("secondaryIP")) if value}
    except ValueError:
        raise ValueError("Dhan static IP evidence is invalid.") from None
    if outgoing not in allowed:
        raise ValueError("This server is not whitelisted for the selected Dhan account.")
    return sha256(client_id.encode()).hexdigest()


def no_contract_exposure(client_id, segment, security_id, positions, orders):
    if not isinstance(positions, list) or not isinstance(orders, list):
        raise ValueError("Fresh native Dhan positions and orders are required.")
    terminal = {"TRADED", "CANCELLED", "REJECTED", "EXPIRED"}
    known = terminal | {"TRANSIT", "PENDING", "PART_TRADED"}
    def selected(row):
        if not isinstance(row, dict) or str(row.get("dhanClientId") or "") != str(client_id):
            raise PermissionError("Dhan account evidence is missing or belongs to a different account.")
        if not row.get("exchangeSegment") or not row.get("securityId"):
            raise ValueError("Native Dhan instrument ownership is incomplete.")
        return row["exchangeSegment"] == segment and str(row["securityId"]) == str(security_id)
    for row in positions:
        match = selected(row)
        net = number(row.get("netQty"))
        if net != int(net):
            raise ValueError("Native Dhan position quantity is invalid.")
        if match and net:
            raise ValueError("The selected contract already has a Dhan position; use its existing exit workflow.")
    for row in orders:
        match = selected(row)
        if row.get("orderStatus") not in known:
            raise ValueError("An unknown Dhan order status requires broker reconciliation.")
        if match and row["orderStatus"] not in terminal:
            raise ValueError("A pending Dhan order already exists for this contract.")


def margin_coverage(client_id, funds, margin, *, minimum_required=0):
    if not isinstance(funds, dict) or str(funds.get("dhanClientId") or "") != str(client_id):
        raise PermissionError("Dhan funds belong to a different account.")
    if not isinstance(margin, dict):
        raise ValueError("A native Dhan margin preview is required.")
    if margin.get("dhanClientId") is not None and str(margin["dhanClientId"]) != str(client_id):
        raise PermissionError("Dhan margin belongs to a different account.")
    cash = number(funds.get("availabelBalance", funds.get("availableBalance")))
    available = number(margin.get("availableBalance"))
    required = number(margin.get("totalMargin"))
    minimum = number(minimum_required)
    if min(cash, available, required, minimum) < 0 or required == 0:
        raise ValueError("Dhan funds or required margin evidence is invalid.")
    # The native insufficientBalance field can contain surplus. Never use its
    # sign as the funding decision, and never invent an absent margin balance.
    required = max(required, minimum)
    available = min(cash, available)
    if required > available:
        raise ValueError("The selected Dhan account cannot fund this chart order.")
    return dict(available_funds=str(available), required_margin=str(required),
                settlement_currency="INR", margin_status="NATIVE_PREVIEW")
