from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import csv
import io
import json
import os
from pathlib import Path
import requests
import secrets
import re
import threading
import html as html_lib
from urllib.parse import parse_qs, urlparse
from .config import ROOT, load_config
from .authentication import authorization_url, exchange_auth_code
from .market_data import FyersLiveFeed, is_token_error, tick_timestamp_iso
from .market_calendar import market_session
from .official_weights import OFFICIAL_WEIGHT_SET
from .sectors import SECTOR_DEFINITIONS
from .sector_service import SectorAnalysisService
from .sensex_straddle import SensexStraddleService
from .nifty_straddle import NiftyStraddleService
from .straddle_squareoff import StraddleSquareOffService
from .fyers_execution import FyersExecutionService, FyersExecutionUnavailable, PreviewChanged, available_funds
from .automation import AutomationPolicyService
from .analysis import calculate_timeframe_state, mtf_alignment
from .analysis_config import TIMEFRAMES
from .handoff import (
    FyersCmMaster, FyersFoMaster, apply_invalidation_choice, build_defined_risk_spreads, build_equity_opportunity, evidence_conviction, fetch_fyers_chain, packet_prompt,
    size_equity_candidate, validate_handoff_request, validate_risk_policy,
)
from fyers_apiv3 import fyersModel

FYERS_REALISED_PNL_URL = "https://api-t1.fyers.in/api/v3/realised-pnl-history"
FYERS_MASTER_SOURCES = {
    "NSE_CM": "https://public.fyers.in/sym_details/NSE_CM.csv",
    "BSE_CM": "https://public.fyers.in/sym_details/BSE_CM.csv",
    "NSE_FO": "https://public.fyers.in/sym_details/NSE_FO.csv",
    "BSE_FO": "https://public.fyers.in/sym_details/BSE_FO.csv",
    "MCX_COM": "https://public.fyers.in/sym_details/MCX_COM.csv",
}
EMA_DIRECTION_TO_OPTION_TYPE = {"BULLISH": "CE", "BEARISH": "PE"}
EMA_MAX_TRADE_LOSS = 3000.0
EMA_IST = ZoneInfo("Asia/Kolkata")


def ema_entry_session_for_symbol(symbol):
    """Use the authorised MCX window; equity and index entries stop at 15:15 IST."""
    return "0915-2330" if str(symbol or "").upper().startswith("MCX:") else "0915-1515"


def ema_candle_in_entry_session(timestamp, entry_session):
    """Return whether a completed candle belongs to the configured IST entry window."""
    match = re.fullmatch(r"(\d{2})(\d{2})-(\d{2})(\d{2})", str(entry_session or ""))
    if not match:
        raise ValueError("Entry session must use HHMM-HHMM format in IST.")
    start_hour, start_minute, end_hour, end_minute = (int(part) for part in match.groups())
    moment = datetime.fromtimestamp(float(timestamp), tz=EMA_IST)
    value = moment.hour * 60 + moment.minute
    return start_hour * 60 + start_minute <= value <= end_hour * 60 + end_minute


def ema_profit_protection(entry_price, ltp, risk_unit_pct, peak_price=None, prior_stop=None):
    """Calculate a premium-based protection stop without submitting an order.

    One R is the configured percentage of the paid option premium. The policy
    starts with a 1R loss cap, moves to breakeven at +1R, locks +0.5R at +1.5R,
    then keeps 60% of the maximum open profit (a 40% giveback trail).
    """
    entry, current, risk = float(entry_price), float(ltp), float(risk_unit_pct) / 100
    if entry <= 0 or current <= 0 or not 0 < risk < 1:
        raise ValueError("Profit protection needs positive prices and a risk unit between 0 and 100 percent.")
    peak = max(float(peak_price or entry), current)
    profit = peak - entry
    r_value = entry * risk
    stop = entry - r_value
    stage = "INITIAL_RISK"
    if profit >= r_value:
        stop, stage = entry, "BREAKEVEN"
    if profit >= 1.5 * r_value:
        stop, stage = entry + 0.5 * r_value, "LOCK_HALF_R"
        stop = max(stop, entry + .60 * profit)
        stage = "TRAIL_40_PERCENT_GIVEBACK"
    if prior_stop is not None:
        stop = max(float(prior_stop), stop)
    return {"peak_price": round(peak, 4), "stop_price": round(stop, 4), "stage": stage,
            "risk_unit_points": round(r_value, 4), "exit": current <= stop}


def estimate_fyers_trade_charges(trades):
    """Estimate FYERS charges from today's executed option fills.

    This is deliberately marked as an estimate: the official contract note is
    authoritative for exchange rounding, state stamp duty, broker credits and
    any special levies.  It is nevertheless useful intraday because it uses
    actual executed turnover and order identifiers, not an assumed lot size.
    """
    totals = {"brokerage": 0.0, "stt_ctt": 0.0, "transaction": 0.0,
              "ipft": 0.0, "sebi": 0.0, "stamp_duty": 0.0, "gst": 0.0}
    seen_orders = set()
    for trade in trades or []:
        symbol = str(trade.get("symbol") or "").upper()
        try:
            turnover = abs(float(trade.get("tradeValue") or 0))
            side = int(trade.get("side") or 0)
        except (TypeError, ValueError):
            continue
        if turnover <= 0 or not (symbol.startswith("NSE:") or symbol.startswith("MCX:")):
            continue
        mcx = symbol.startswith("MCX:")
        # The dashboard only estimates the F&O / commodity-option fills it can
        # classify confidently.  Unknown cash/futures symbols are excluded.
        option = symbol.endswith("CE") or symbol.endswith("PE")
        if not option:
            continue
        order_id = str(trade.get("orderNumber") or trade.get("exchangeOrderNo") or "")
        unique_order = ("MCX" if mcx else "NSE", order_id or f"row:{trade.get('row')}")
        if unique_order not in seen_orders:
            totals["brokerage"] += 20.0
            seen_orders.add(unique_order)
        if side < 0:
            totals["stt_ctt"] += turnover * (0.0005 if mcx else 0.0015)
        totals["transaction"] += turnover * (0.000918 if mcx else 0.0004403)
        totals["sebi"] += turnover * 0.0000001
        if not mcx:
            totals["ipft"] += turnover * 0.000005
        # Indicative option stamp duty is charged on purchases.  The official
        # contract note remains the source of truth because it is state-specific.
        if side > 0:
            totals["stamp_duty"] += turnover * 0.00003
    totals["gst"] = 0.18 * (totals["brokerage"] + totals["transaction"] + totals["ipft"])
    total = sum(totals.values())
    return {"available": bool(trades), "estimated": True,
            "orders": len(seen_orders), "breakdown": {key: round(value, 2) for key, value in totals.items()},
            "total": round(total, 2),
            "disclaimer": "Estimated from executed FYERS option fills and the published charges schedule; final contract-note charges can differ because of exchange rounding, state stamp duty, or broker credits."}


def ema_live_ticket_preview(contract, quote, lots, stop_loss_pct=None, target_profit_pct=None, profit_protection_pct=None, now=None):
    """Build the exact LIVE entry order parameters from a fresh option quote.

    stop_loss_pct/target_profit_pct are optional safety nets. When omitted the
    position instead exits on the indicator-defined signal (see
    ema_band_exit_signal): a completed candle closing back inside the EMA
    High/Low band, the same rule the Pine strategy uses.
    """
    try:
        lot_size = int(contract["lot_size"])
        tick_size = float(contract["tick_size"])
        lots = int(lots)
        stop_loss_pct = None if stop_loss_pct is None else float(stop_loss_pct)
        target_profit_pct = None if target_profit_pct is None else float(target_profit_pct)
        profit_protection_pct = None if profit_protection_pct is None else float(profit_protection_pct)
        bid = float(quote["bid"])
        ask = float(quote["ask"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("A fresh two-sided option quote and valid FYERS lot/tick data and lots are required for a live order ticket.") from error
    if lot_size < 1 or tick_size <= 0 or lots < 1:
        raise ValueError("Live order tickets require valid FYERS lot/tick metadata and at least one lot.")
    if stop_loss_pct is not None and not 0 < stop_loss_pct < 100:
        raise ValueError("Live order tickets require a stop-loss below 100% when one is set.")
    if target_profit_pct is not None and target_profit_pct <= 0:
        raise ValueError("Live order tickets require a positive target percentage when one is set.")
    if profit_protection_pct is not None and not 0 < profit_protection_pct < 100:
        raise ValueError("Profit protection needs a risk unit below 100% when enabled.")
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ValueError("FYERS did not return a valid fresh two-sided option quote for the selected contract.")
    entry = round(ask / tick_size) * tick_size
    quantity = lots * lot_size
    stop_price = max(tick_size, round((entry * (1 - stop_loss_pct / 100)) / tick_size) * tick_size) if stop_loss_pct is not None else None
    target_price = round((entry * (1 + target_profit_pct / 100)) / tick_size) * tick_size if target_profit_pct is not None else None
    created = (now or datetime.now().astimezone())
    return {
        "ticket_id": f"EMA-{secrets.token_hex(5).upper()}", "status": "LIVE_ORDER_READY", "action": "BUY",
        "symbol": contract["symbol"], "description": contract["description"], "option_type": contract["option_type"],
        "strike": contract["strike"], "expiry_epoch": contract["expiry_epoch"], "lots": lots, "quantity": quantity,
        "lot_size": lot_size, "tick_size": tick_size,
        "limit_price": round(entry, 4), "quote": {"bid": bid, "ask": ask},
        "stop_price": round(stop_price, 4) if stop_price is not None else None,
        "target_price": round(target_price, 4) if target_price is not None else None,
        "stop_loss_pct": stop_loss_pct, "target_profit_pct": target_profit_pct,
        "profit_protection_pct": profit_protection_pct,
        "exit_mode": "PERCENT_AND_INDICATOR" if (stop_loss_pct is not None or target_profit_pct is not None) else "INDICATOR_ONLY",
        "maximum_premium_at_risk": round(entry * quantity, 2),
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(seconds=120)).isoformat(),
        "message": "Live EMA entry order ticket built from a fresh FYERS quote.",
    }


def _ema_order_ids(response):
    """Pull FYERS order id(s) out of a place_order/orderbook-shaped response."""
    ids = []
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"id", "orderId", "order_id"} and child:
                    ids.append(str(child))
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(response)
    return list(dict.fromkeys(ids))


def ema_master_row_matches_segment(row, selected_segment):
    """Keep an EMA Band search inside the instrument class selected in the UI."""
    if len(row) < 17:
        return False
    if selected_segment == "stock-option":
        # NSE_FO/BSE_FO masters list futures and options together.  A segment
        # match alone must not let a future appear in the stock-options picker.
        return str(row[16]).upper() in {"CE", "PE"}
    return True


def ema_cash_or_index_row_matches_exchange(row, exchange):
    """Accept cash equities and index underlyings supported by each FYERS cash master."""
    if len(row) < 10:
        return False
    symbol = str(row[9]).upper()
    if not symbol.startswith(f"{exchange}:"):
        return False
    if exchange == "NSE":
        return symbol.endswith(("-EQ", "-INDEX"))
    if exchange == "BSE":
        # BSE records indices (including SENSEX) with type 10 rather than the
        # type 0 used for cash equities.
        return str(row[2]) == "0" or symbol.endswith("-INDEX")
    return False


def ema_master_search_rank(item, needle):
    """Prefer an exact FYERS symbol or underlying over a substring match."""
    symbol = str(item.get("symbol") or "").upper()
    underlying = str(item.get("underlying") or "").upper().replace(" ", "")
    normalized = str(needle or "").upper().split(":", 1)[-1].replace("-INDEX", "").replace(" ", "")
    root = symbol.split(":", 1)[-1].removesuffix("-INDEX").replace(" ", "")
    if symbol == str(needle or "").upper():
        return (0, symbol)
    if underlying == normalized:
        return (1, symbol)
    if symbol.endswith(str(needle or "").upper()):
        return (2, symbol)
    if "-INDEX" in symbol and normalized in root:
        return (3, len(root), symbol)
    if root.startswith(normalized):
        return (4, symbol)
    if normalized in root:
        return (5, symbol)
    return (6, symbol)


def select_ema_atm_option(rows, underlying, direction, spot, now_epoch):
    """Select one current-master directional ATM option; never constructs a symbol."""
    option_type = EMA_DIRECTION_TO_OPTION_TYPE.get(str(direction or "").upper())
    try:
        reference_price = float(spot)
    except (TypeError, ValueError) as error:
        raise ValueError("FYERS did not return a valid underlying price for ATM selection.") from error
    if option_type is None:
        raise ValueError("Choose a bullish Call (CE) or bearish Put (PE) direction.")
    if reference_price <= 0:
        raise ValueError("FYERS did not return a positive underlying price for ATM selection.")
    contracts = []
    normalized_underlying = str(underlying or "").strip().upper()
    for row in rows:
        if len(row) < 17 or str(row[13]).strip().upper() != normalized_underlying or str(row[16]).upper() != option_type:
            continue
        try:
            expiry = float(row[8])
            strike = float(row[15])
            lot_size = int(float(row[3]))
            tick_size = float(row[4])
        except (TypeError, ValueError):
            continue
        if expiry <= float(now_epoch) or strike <= 0 or lot_size <= 0 or tick_size <= 0 or not str(row[9]).strip():
            continue
        contracts.append({
            "symbol": row[9], "description": row[1], "underlying": row[13], "expiry_epoch": int(expiry),
            "strike": strike, "option_type": option_type, "lot_size": lot_size, "tick_size": tick_size,
        })
    if not contracts:
        raise ValueError(f"No unexpired {option_type} contract is available in the current FYERS master for {normalized_underlying}.")
    # ATM is the nearest strike in the nearest listed expiry, with a stable
    # lower-strike/symbol tie-breaker.  The master, not a constructed string,
    # remains the source of the executable contract identity.
    nearest_expiry = min(contract["expiry_epoch"] for contract in contracts)
    candidates = [contract for contract in contracts if contract["expiry_epoch"] == nearest_expiry]
    return min(candidates, key=lambda contract: (abs(contract["strike"] - reference_price), contract["strike"], contract["symbol"]))


def ema_band_strategy_signal(candles, ema_length=21, entry_session=None):
    """Derive a CE/PE direction only from the completed EMA Band entry signal."""
    try:
        length = int(ema_length)
    except (TypeError, ValueError) as error:
        raise ValueError("EMA Band length must be a positive whole number.") from error
    if length < 1:
        raise ValueError("EMA Band length must be a positive whole number.")
    if len(candles) < max(length + 1, 3):
        return {"status": "INSUFFICIENT_HISTORY", "direction": None, "message": "EMA Band needs more completed candles before it can derive direction."}
    def series(field):
        values, previous = [], None
        alpha = 2 / (length + 1)
        for candle in candles:
            value = float(candle[field])
            previous = value if previous is None else alpha * value + (1 - alpha) * previous
            values.append(previous)
        return values
    high_band, low_band = series("high"), series("low")
    setup, completed = candles[-2], candles[-1]
    setup_index, completed_index = len(candles) - 2, len(candles) - 1
    midpoint = (float(setup["high"]) + float(setup["low"])) / 2
    bullish = float(setup["open"]) <= high_band[setup_index] and float(setup["close"]) > high_band[setup_index] and float(completed["close"]) > float(completed["open"]) and float(completed["open"]) > midpoint
    bearish = float(setup["open"]) >= low_band[setup_index] and float(setup["close"]) < low_band[setup_index] and float(completed["close"]) < float(completed["open"]) and float(completed["open"]) < midpoint
    direction = "BULLISH" if bullish else "BEARISH" if bearish else None
    if direction and entry_session and not ema_candle_in_entry_session(completed.get("timestamp"), entry_session):
        return {
            "status": "NO_SIGNAL", "direction": None, "completed_candle": completed.get("timestamp"),
            "setup_candle": setup.get("timestamp"), "ema_high": round(high_band[completed_index], 4),
            "ema_low": round(low_band[completed_index], 4),
            "message": f"Completed EMA Band entry signal is outside the {entry_session} IST entry window; ATM contract selection is blocked.",
        }
    return {
        "status": "SIGNAL" if direction else "NO_SIGNAL", "direction": direction,
        "completed_candle": completed.get("timestamp"), "setup_candle": setup.get("timestamp"),
        "ema_high": round(high_band[completed_index], 4), "ema_low": round(low_band[completed_index], 4),
        "message": f"Completed EMA Band {direction.lower()} entry signal." if direction else "No completed EMA Band entry signal; ATM contract selection is blocked.",
    }


def ema_band_entry_checklist(candles, ema_length=21, has_active_position=False):
    """Explain the completed-candle EMA entry gate without changing its signal."""
    length = int(ema_length)
    required = max(length + 1, 3)
    count = len(candles)
    checks = {"sufficient_completed_history": {"pass": count >= required, "value": f"{count}/{required} completed candles"},
              "current_candle_completed": {"pass": True, "value": "FYERS in-progress candle excluded"},
              "flat_no_runner_position": {"pass": not has_active_position, "value": "flat" if not has_active_position else "runner position active"},
              "session_gate": {"pass": True, "value": "disabled"},
              "same_direction_cooldown": {"pass": True, "value": "disabled"}}
    if count < required:
        return {"ready": False, "completed_candle": candles[-1].get("timestamp") if candles else None, "checks": checks}
    def series(field):
        values, previous = [], None
        alpha = 2 / (length + 1)
        for candle in candles:
            value = float(candle[field])
            previous = value if previous is None else alpha * value + (1 - alpha) * previous
            values.append(previous)
        return values
    high_band, low_band = series("high"), series("low")
    setup, current = candles[-2], candles[-1]
    midpoint = (float(setup["high"]) + float(setup["low"])) / 2
    long_cross = float(setup["open"]) <= high_band[-2] and float(setup["close"]) > high_band[-2]
    short_cross = float(setup["open"]) >= low_band[-2] and float(setup["close"]) < low_band[-2]
    bullish, bearish = float(current["close"]) > float(current["open"]), float(current["close"]) < float(current["open"])
    long_mid, short_mid = float(current["open"]) > midpoint, float(current["open"]) < midpoint
    checks.update({
        "prior_body_crosses_ema_high_long": {"pass": long_cross, "value": f"open {setup['open']}, close {setup['close']}, EMA high {round(high_band[-2], 4)}"},
        "prior_body_crosses_ema_low_short": {"pass": short_cross, "value": f"open {setup['open']}, close {setup['close']}, EMA low {round(low_band[-2], 4)}"},
        "current_candle_direction_long": {"pass": bullish, "value": f"open {current['open']}, close {current['close']}"},
        "current_candle_direction_short": {"pass": bearish, "value": f"open {current['open']}, close {current['close']}"},
        "current_open_beyond_midpoint_long": {"pass": long_mid, "value": f"open {current['open']}, midpoint {round(midpoint, 4)}"},
        "current_open_beyond_midpoint_short": {"pass": short_mid, "value": f"open {current['open']}, midpoint {round(midpoint, 4)}"},
    })
    long_ready = all(checks[key]["pass"] for key in ("sufficient_completed_history", "current_candle_completed", "flat_no_runner_position", "session_gate", "same_direction_cooldown", "prior_body_crosses_ema_high_long", "current_candle_direction_long", "current_open_beyond_midpoint_long"))
    short_ready = all(checks[key]["pass"] for key in ("sufficient_completed_history", "current_candle_completed", "flat_no_runner_position", "session_gate", "same_direction_cooldown", "prior_body_crosses_ema_low_short", "current_candle_direction_short", "current_open_beyond_midpoint_short"))
    return {"ready": long_ready or short_ready, "long_ready": long_ready, "short_ready": short_ready,
            "completed_candle": current.get("timestamp"), "checks": checks}


def ema_band_exit_signal(candles, ema_length=21):
    """Indicator-defined exit: a completed candle closes back inside the EMA High/Low band (matches the Pine strategy's longExit/shortExit)."""
    try:
        length = int(ema_length)
    except (TypeError, ValueError) as error:
        raise ValueError("EMA Band length must be a positive whole number.") from error
    if length < 1:
        raise ValueError("EMA Band length must be a positive whole number.")
    if len(candles) < length + 1:
        return {"status": "INSUFFICIENT_HISTORY", "exit": False, "message": "EMA Band needs more completed candles before it can evaluate an exit."}
    def series(field):
        values, previous = [], None
        alpha = 2 / (length + 1)
        for candle in candles:
            value = float(candle[field])
            previous = value if previous is None else alpha * value + (1 - alpha) * previous
            values.append(previous)
        return values
    high_band, low_band = series("high"), series("low")
    completed = candles[-1]
    index = len(candles) - 1
    inside_band = low_band[index] <= float(completed["close"]) <= high_band[index]
    return {
        "status": "EXIT" if inside_band else "NO_EXIT", "exit": inside_band,
        "completed_candle": completed.get("timestamp"), "ema_high": round(high_band[index], 4), "ema_low": round(low_band[index], 4),
        "message": "Completed candle closed back inside the EMA High/Low band." if inside_band else "Completed candle remains outside the EMA High/Low band.",
    }


def fetch_chartink_source(url, requester=None):
    """Manually fetch one explicitly supplied Chartink screener; never trades."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"chartink.com", "www.chartink.com"} or not parsed.path.startswith("/screener/"):
        raise ValueError("Use a valid http(s) Chartink screener URL.")
    session = None if requester else requests.Session()
    response = (requester or session.get)(url, timeout=20, headers={"User-Agent": "SectorPulse/1.0 read-only manual screener fetch"})
    response.raise_for_status()
    html = response.text
    lowered = html.casefold()
    now = datetime.now().astimezone().isoformat()
    if "captcha" in lowered or "cloudflare" in lowered:
        return {"fetch_schema": 2, "status": "CAPTCHA", "count": None, "fetched_at": now, "error": "Chartink requires an interactive captcha."}
    if "login" in lowered and "password" in lowered:
        return {"fetch_schema": 2, "status": "LOGIN_REQUIRED", "count": None, "fetched_at": now, "error": "Chartink login is required."}
    symbols = list(dict.fromkeys(re.findall(r'(?:NSE:|/stocks/)([A-Z][A-Z0-9&.-]{1,24})', html)))
    if symbols:
        return {"fetch_schema": 2, "status": "READY", "count": len(symbols), "fetched_at": now, "candidates": symbols,
                "validation": "SOURCE_ONLY_REQUIRES_COMPLETED_CANDLE_AND_FRESH_MARKET_DATA"}
    if requester:
        return {"fetch_schema": 2, "status": "ACCESS_REQUIRED", "count": None, "fetched_at": now,
                "error": "Chartink returned the screener page definition, not executed scan rows. Open the source in signed-in Chartink or use manual Refresh with scan access."}
    csrf = re.search(r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)', html, re.I)
    query = re.search(r'&quot;atlas_query&quot;:&quot;(.*?)&quot;', html, re.I | re.S)
    if not csrf or not query:
        return {"fetch_schema": 2, "status": "ACCESS_REQUIRED", "count": None, "fetched_at": now,
                "error": "Chartink did not expose an executable scan definition; signed-in browser access may be required."}
    scan_clause = html_lib.unescape(query.group(1)).replace(r"\/", "/")
    configured_columns = re.search(r'&quot;column_clause&quot;:&quot;(.*?)&quot;', html, re.I | re.S)
    requested_columns = ["close", "per_chg", "volume", "sector", "market cap"]
    if configured_columns:
        requested_columns.extend(part.strip() for part in html_lib.unescape(configured_columns.group(1)).split(",") if part.strip())
    column_clause = ",".join(dict.fromkeys(requested_columns))
    scan = session.post(
        "https://chartink.com/screener/process", data={"scan_clause": scan_clause, "column_clause": column_clause}, timeout=30,
        headers={"X-CSRF-TOKEN": csrf.group(1), "X-Requested-With": "XMLHttpRequest", "Referer": url},
    )
    scan.raise_for_status()
    try:
        payload = scan.json()
    except ValueError:
        return {"fetch_schema": 2, "status": "ACCESS_REQUIRED", "count": None, "fetched_at": now,
                "error": "Chartink scan processing returned no readable result payload; signed-in browser access may be required."}
    rows = payload.get("data") if isinstance(payload, dict) else None
    total = payload.get("recordsTotal") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not isinstance(total, int):
        return {"fetch_schema": 2, "status": "UNSUPPORTED", "count": None, "fetched_at": now, "error": "Chartink returned an unsupported scan result shape."}
    candidates = list(dict.fromkeys(str(row.get("nsecode") or "").strip().upper() for row in rows if row.get("nsecode")))
    source_sectors = {}
    source_volumes = {}
    source_market_caps = {}
    source_fields = {}
    reserved_fields = {"sr", "nsecode", "bsecode", "name", "close", "per_chg", "volume", ",volume", "sector", "sector_name", "market cap", ",market cap", "market_cap", "marketcap"}
    for row in rows:
        symbol = str(row.get("nsecode") or "").strip().upper()
        sector = str(row.get("sector") or row.get("sector_name") or "").strip()
        if symbol and sector:
            source_sectors[symbol] = sector
        raw_volume = row.get("volume", row.get(",volume"))
        try:
            volume = int(float(raw_volume))
        except (TypeError, ValueError):
            volume = None
        if symbol and volume is not None and volume >= 0:
            source_volumes[symbol] = volume
        raw_market_cap = next((row.get(key) for key in ("market cap", ",market cap", "market_cap", "marketcap") if row.get(key) is not None), None)
        try:
            market_cap = float(str(raw_market_cap).replace(",", ""))
        except (TypeError, ValueError):
            market_cap = None
        if symbol and market_cap is not None and market_cap >= 0:
            source_market_caps[symbol] = market_cap
        if symbol:
            source_fields[symbol] = {str(key).lstrip(","): value for key, value in row.items() if key not in reserved_fields and value is not None}
    field_names = list(dict.fromkeys(key for values in source_fields.values() for key in values))
    source_field_schema = []
    for field in field_names:
        values = [values[field] for values in source_fields.values() if field in values]
        lowered_field = field.casefold()
        if values and all(isinstance(value, bool) for value in values):
            kind = "boolean"
        else:
            numeric = 0
            for value in values:
                try:
                    float(str(value).replace(",", "").replace("%", "")); numeric += 1
                except (TypeError, ValueError):
                    pass
            kind = "number" if values and numeric == len(values) else "datetime" if any(token in lowered_field for token in ("date", "time", "timestamp", " as of")) else "category" if len(set(map(str, values))) <= 20 else "text"
        source_field_schema.append({"key": field, "label": field.replace("_", " ").strip().title(), "type": kind})
    return {"fetch_schema": 2, "status": "READY" if total else "EMPTY", "count": total, "fetched_at": now, "candidates": candidates,
            "source_sectors": source_sectors, "source_volumes": source_volumes, "source_market_caps": source_market_caps,
            "source_fields": source_fields, "source_field_schema": source_field_schema,
            "validation": "SOURCE_ONLY_REQUIRES_COMPLETED_CANDLE_AND_FRESH_MARKET_DATA"}


def enrich_chartink_candidates(candidates, quote_fetcher):
    """Attach provider-stamped FYERS prices without changing Chartink membership."""
    symbols = list(dict.fromkeys(str(value or "").strip().upper() for value in candidates if value))
    market_data = {}
    timestamps = []
    errors = []
    for offset in range(0, len(symbols), 40):
        batch = symbols[offset:offset + 40]
        response = quote_fetcher({"symbols": ",".join(f"NSE:{symbol}-EQ" for symbol in batch)})
        if not isinstance(response, dict) or response.get("s") != "ok":
            errors.append(str(response.get("message") if isinstance(response, dict) else "Invalid FYERS response") or "FYERS quote batch unavailable")
            continue
        for row in response.get("d") or []:
            values = row.get("v") or {}
            provider_symbol = str(row.get("n") or values.get("symbol") or "")
            symbol = provider_symbol.removeprefix("NSE:").removesuffix("-EQ")
            if symbol not in symbols:
                continue
            raw_timestamp = values.get("tt")
            if isinstance(raw_timestamp, str) and raw_timestamp.strip().lstrip("-").isdigit():
                raw_timestamp = float(raw_timestamp)
            timestamp = tick_timestamp_iso(raw_timestamp)
            try:
                price = float(values["lp"])
                change = float(values["ch"])
                change_pct = float(values["chp"])
            except (KeyError, TypeError, ValueError):
                continue
            if price <= 0 or not timestamp:
                continue
            volume = values.get("volume")
            try:
                volume = int(float(volume))
            except (TypeError, ValueError):
                volume = None
            market_data[symbol] = {"last_price": price, "day_change": change, "day_change_pct": change_pct, "provider_timestamp": timestamp,
                                   "volume": volume if volume is not None and volume >= 0 else None}
            timestamps.append(timestamp)
    result = {"market_data_schema": 1, "market_data": market_data, "market_data_as_of": max(timestamps) if timestamps else None,
              "market_data_provider": "FYERS_READ_ONLY", "market_data_available": len(market_data)}
    if errors or len(market_data) < len(symbols):
        missing = len(symbols) - len(market_data)
        result["market_data_error"] = f"FYERS price data unavailable for {missing} of {len(symbols)} candidates."
        if errors:
            result["market_data_error"] += f" {errors[0]}"
    return result


def chartink_candidate_sectors(candidates, source_sectors=None):
    """Prefer source-returned sectors, then use versioned official NSE membership."""
    requested = set(str(value or "").strip().upper() for value in candidates if value)
    memberships = {symbol: [] for symbol in requested}
    for sector in SECTOR_DEFINITIONS:
        for constituent in sector.constituents:
            if constituent.ticker in memberships:
                memberships[constituent.ticker].append(sector.name)
    source_sectors = {str(symbol).strip().upper(): str(value).strip() for symbol, value in (source_sectors or {}).items() if str(value).strip()}
    sectors = {}
    origins = {}
    for symbol in requested:
        if source_sectors.get(symbol):
            sectors[symbol] = source_sectors[symbol]
            origins[symbol] = "CHARTINK_SOURCE"
        elif memberships[symbol]:
            sectors[symbol] = " / ".join(memberships[symbol])
            origins[symbol] = "NSE_INDEX_FALLBACK"
    return {
        "sectors": sectors, "sector_origins": origins,
        "sector_source": "CHARTINK_WITH_NSE_INDICES_FALLBACK",
        "sector_source_as_of": OFFICIAL_WEIGHT_SET.source_as_of,
    }


def join_unique_reasons(items):
    reasons = [str(item.get("reason") or "").strip() for item in items]
    return "; ".join(dict.fromkeys(reason for reason in reasons if reason))


def instrument_route(payload):
    """Return the one explicitly selected, non-mixed handoff instrument route."""
    route = str((payload or {}).get("instrument_route") or "").strip().lower()
    if route not in {"cash_equity", "stock_options"}:
        raise ValueError("Choose Cash equity or Stock options before collecting matches.")
    return route


def closed_position_records(positions):
    """Normalize today's fully squared-off position rows from FYERS positions."""
    records = []
    for row in positions or []:
        net_qty = float(row.get("netQty", row.get("net_qty", 0)) or 0)
        buy_qty = float(row.get("buyQty", row.get("buy_qty", 0)) or 0)
        sell_qty = float(row.get("sellQty", row.get("sell_qty", 0)) or 0)
        if net_qty != 0 or buy_qty <= 0 or sell_qty <= 0:
            continue
        records.append({
            "symbol": row.get("symbol", row.get("symbol_name", "—")),
            "segment": row.get("segment", row.get("segment_name", "—")),
            "buy_qty": buy_qty,
            "buy_rate": row.get("buyAvg", row.get("buy_rate", 0)),
            "sell_qty": sell_qty,
            "sell_rate": row.get("sellAvg", row.get("sell_rate", 0)),
            "pnl": row.get("realized_profit", row.get("realizedProfit", row.get("pl", 0))),
        })
    return records


def open_position_underlyings(positions):
    """Return normalized FYERS exposure identifiers for duplicate-entry checks."""
    exposures = []
    for row in positions or []:
        try:
            net_qty = float(row.get("netQty", row.get("net_qty", row.get("qty", 0))) or 0)
        except (TypeError, ValueError):
            continue
        if net_qty == 0:
            continue
        symbols = [row.get("symbol"), row.get("underlying"), row.get("underlyingSymbol"), row.get("underlying_symbol")]
        exposures.extend(str(symbol).strip().upper() for symbol in symbols if str(symbol or "").strip())
    return set(exposures)


def ema_open_buy_reconciliation(response, symbol, minimum_quantity):
    """Classify whether FYERS freshly confirms the runner-owned long position."""
    if not isinstance(response, dict) or response.get("s") != "ok":
        return "UNAVAILABLE", "FYERS positions are unavailable; cannot confirm an open EMA Band buy position."
    rows = response.get("netPositions") or (response.get("data") or {}).get("netPositions") or []
    for row in rows:
        if str(row.get("symbol")) != str(symbol):
            continue
        try:
            net_qty = float(row.get("netQty", row.get("qty", 0)) or 0)
            buy_qty = float(row.get("buyQty", row.get("boughtQty", net_qty)) or 0)
        except (TypeError, ValueError):
            net_qty = buy_qty = 0
        if net_qty >= float(minimum_quantity) and buy_qty >= float(minimum_quantity):
            return "CONFIRMED", None
        return "ABSENT_OR_PARTIAL", f"FYERS does not show the required open buy quantity of {minimum_quantity} for {symbol}."
    return "ABSENT_OR_PARTIAL", f"No confirmed, filled FYERS buy position of at least {minimum_quantity} found for {symbol}."


def candidate_has_open_position(candidate, position_exposures):
    """Match a cash candidate to the same FYERS cash, future, or option underlying."""
    symbol = str((candidate or {}).get("symbol") or "").strip().upper()
    ticker = str((candidate or {}).get("ticker") or "").strip().upper()
    if not ticker and symbol.startswith("NSE:"):
        ticker = symbol[4:].split("-", 1)[0]
    if not symbol or not ticker:
        return False
    prefix = f"NSE:{ticker}"
    for exposure in position_exposures or set():
        if exposure == symbol or exposure in {ticker, f"NSE:{ticker}"}:
            return True
        if exposure.startswith(prefix) and (len(exposure) == len(prefix) or exposure[len(prefix)] in "-0123456789"):
            return True
    return False


def fetch_realized_pnl_report(app_id, access_token, start, end, requester=None):
    """Fetch the read-only Reports API that fyers-apiv3 3.1.7 does not wrap."""
    requester = requester or requests.get
    records = []
    summary = {}
    page_size = 100
    for page in range(1, 101):
        response = requester(
            FYERS_REALISED_PNL_URL,
            headers={"Authorization": f"{app_id}:{access_token}"},
            params={
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "page_size": page_size,
                "page_no": page,
            },
            timeout=20,
        )
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(f"FYERS realised P&L returned a non-JSON response (HTTP {response.status_code})") from error
        if response.status_code in {404, 405}:
            return {"supported": False, "message": "FYERS realised P&L history is not available for this account.", "data": [], "summary_data": {}}
        if response.status_code != 200 or payload.get("s") != "ok":
            message = payload.get("message") or f"HTTP {response.status_code}"
            raise RuntimeError(f"FYERS realised P&L is unavailable: {message}")
        page_records = payload.get("data") or []
        if not isinstance(page_records, list):
            raise RuntimeError("FYERS realised P&L returned an invalid data payload")
        records.extend(page_records)
        summary = payload.get("summary_data") or summary
        if len(page_records) < page_size:
            break
    return {"supported": True, "message": payload.get("message"), "data": records, "summary_data": summary}

def run_server():
    port = int(os.getenv("HEATMAP_PORT", "8080"))
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    feed = FyersLiveFeed(token) if token else None
    if feed: feed.start()
    sector_analysis = SectorAnalysisService(token)
    sector_analysis.start()
    state = {"feed": feed, "sector_analysis": sector_analysis, "renewing": False, "auth_error": None, "next_auth_attempt": 0.0}
    fyers_fo_master = FyersFoMaster()
    fyers_cm_master = FyersCmMaster()
    ema_master_dir = ROOT / ".private" / "ema-band-masters"
    live_pnl_snapshot_path = ROOT / ".private" / "live-pnl.json"
    ema_chart_cache = {"key": None, "snapshot": None, "refreshed_at": None}

    def publish_live_pnl_snapshot(account):
        """Publish the small shared P&L feed atomically for all dashboard views."""
        snapshot = {
            "schema_version": 1,
            "source": "FYERS executed fills and live positions",
            "updated_at": datetime.now().astimezone().isoformat(),
            "gross_live_pnl": account.get("pnl"),
            "estimated_charges": account.get("estimated_charges"),
            "estimated_net_pnl": account.get("estimated_net_pnl"),
            "open_position_count": sum(1 for item in account.get("positions", []) if float(item.get("netQty", item.get("net_qty", 0)) or 0) != 0),
        }
        live_pnl_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = live_pnl_snapshot_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
        temporary.replace(live_pnl_snapshot_path)
        return snapshot

    def read_live_pnl_snapshot():
        if not live_pnl_snapshot_path.exists():
            return {"available": False, "message": "Live P&L has not been refreshed yet."}
        try:
            return {"available": True, **json.loads(live_pnl_snapshot_path.read_text(encoding="utf-8"))}
        except (OSError, ValueError, json.JSONDecodeError):
            return {"available": False, "message": "Live P&L snapshot is temporarily unavailable."}

    def ema_master_status():
        now = datetime.now().astimezone()
        segments = []
        for segment, source in FYERS_MASTER_SOURCES.items():
            path = ema_master_dir / f"{segment}.csv"
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=now.tzinfo) if path.exists() else None
            age_hours = (now - modified).total_seconds() / 3600 if modified else None
            segments.append({"segment": segment, "source": source, "cached_at": modified.isoformat() if modified else None, "fresh": bool(age_hours is not None and age_hours <= 24), "usable": bool(age_hours is not None and age_hours <= 72), "age_hours": round(age_hours, 1) if age_hours is not None else None})
        return {"segments": segments, "fresh": bool(segments) and all(item["fresh"] for item in segments), "usable": bool(segments) and all(item["usable"] for item in segments), "schedule": "automatic daily refresh; stale cache remains usable for up to 72 hours"}

    def refresh_ema_masters():
        ema_master_dir.mkdir(parents=True, exist_ok=True)
        for segment, source in FYERS_MASTER_SOURCES.items():
            response = requests.get(source, timeout=90)
            response.raise_for_status()
            temporary = ema_master_dir / f".{segment}.tmp"
            temporary.write_text(response.text, encoding="utf-8")
            temporary.replace(ema_master_dir / f"{segment}.csv")
        return ema_master_status()

    def search_ema_master(query, segment=""):
        state = ema_master_status()
        if not state["usable"]:
            raise RuntimeError("FYERS master cache is missing or older than 72 hours. Contract selection is fail-closed until a refresh succeeds.")
        needle = str(query or "").strip().upper()
        if len(needle) < 2:
            return {"matches": [], "status": state}
        matches = []
        for item in state["segments"]:
            allowed = {"cash": {"NSE_CM", "BSE_CM"}, "index": {"NSE_CM", "BSE_CM"}, "fno": {"NSE_FO", "BSE_FO"}, "commodity": {"MCX_COM"}, "stock-option": {"NSE_FO", "BSE_FO"}}
            if segment and item["segment"] not in allowed.get(segment, {segment}):
                continue
            for row in csv.reader(io.StringIO((ema_master_dir / f"{item['segment']}.csv").read_text(encoding="utf-8"))):
                if not ema_master_row_matches_segment(row, segment) or needle not in " ".join(row).upper():
                    continue
                matches.append({"segment": item["segment"], "symbol": row[9], "description": row[1], "underlying": row[13], "lot_size": row[3], "tick_size": row[4], "expiry": row[8], "strike": row[15], "option_type": row[16]})
        matches.sort(key=lambda item: ema_master_search_rank(item, needle))
        return {"matches": matches[:20], "status": state}

    def search_ema_option_underlyings(query):
        """Offer only master-backed NSE/BSE cash/index underlyings with listed options."""
        state = ema_master_status()
        if not state["usable"]:
            raise RuntimeError("FYERS master cache is missing or older than 72 hours. Underlying selection is fail-closed until a refresh succeeds.")
        needle = str(query or "").strip().upper()
        if len(needle) < 2:
            return {"matches": [], "status": state}
        cash_underlyings = {}
        for cash_segment in ("NSE_CM", "BSE_CM"):
            exchange = cash_segment.split("_", 1)[0]
            for row in csv.reader(io.StringIO((ema_master_dir / f"{cash_segment}.csv").read_text(encoding="utf-8"))):
                if len(row) < 14:
                    continue
                if not ema_cash_or_index_row_matches_exchange(row, exchange):
                    continue
                cash_underlyings[(exchange, str(row[13]).strip().upper())] = {"symbol": row[9], "description": row[1]}
        matches = {}
        for option_segment in ("NSE_FO", "BSE_FO"):
            exchange = option_segment.split("_", 1)[0]
            for row in csv.reader(io.StringIO((ema_master_dir / f"{option_segment}.csv").read_text(encoding="utf-8"))):
                if len(row) < 17 or str(row[16]).upper() not in {"CE", "PE"}:
                    continue
                underlying = str(row[13]).strip().upper()
                cash = cash_underlyings.get((exchange, underlying))
                if not cash or needle not in f"{underlying} {cash['symbol']} {cash['description']}".upper():
                    continue
                matches[(option_segment, cash["symbol"])] = {
                    "underlying": underlying, "symbol": cash["symbol"], "description": cash["description"], "option_segment": option_segment, "market_kind": "CASH_OR_INDEX",
                }
        now_epoch = datetime.now().timestamp()
        mcx_rows = list(csv.reader(io.StringIO((ema_master_dir / "MCX_COM.csv").read_text(encoding="utf-8"))))
        option_underlyings = {str(row[13]).strip().upper() for row in mcx_rows if len(row) >= 17 and str(row[16]).upper() in {"CE", "PE"}}
        active_futures = {}
        for row in mcx_rows:
            if len(row) < 17 or str(row[16]).upper() != "XX" or str(row[13]).strip().upper() not in option_underlyings:
                continue
            try:
                expiry = float(row[8])
            except (TypeError, ValueError):
                continue
            if expiry <= now_epoch:
                continue
            underlying = str(row[13]).strip().upper()
            current = active_futures.get(underlying)
            if current is None or expiry < current[0]:
                active_futures[underlying] = (expiry, row)
        for underlying, (_, row) in active_futures.items():
            if needle not in f"{underlying} {row[9]} {row[1]}".upper():
                continue
            matches[("MCX_COM", row[9])] = {
                "underlying": underlying, "symbol": row[9], "description": row[1], "option_segment": "MCX_COM", "market_kind": "COMMODITY_FUTURE",
            }
        def rank(item):
            symbol = item["symbol"].upper()
            if item["underlying"] == needle or symbol == needle:
                return (0, item["underlying"], symbol)
            if item["underlying"].startswith(needle) or symbol.endswith(needle):
                return (1, item["underlying"], symbol)
            return (2, item["underlying"], symbol)
        return {"matches": sorted(matches.values(), key=rank)[:20], "status": state}

    def ema_band_candles(client, symbol, timeframe, include_forming=False):
        resolution = {"5 minutes": "5", "15 minutes": "15", "1 hour": "60"}.get(str(timeframe))
        if not resolution:
            raise ValueError("Choose the EMA Band 5-minute, 15-minute, or 1-hour timeframe.")
        now = datetime.now().astimezone()
        lookback_days = 45 if resolution in {"5", "15"} else 180
        # The picker resolves a specific, nearest-unexpired futures contract.
        # Keep history on that exact contract as well: cont_flag=1 would splice
        # a continuous series into the calculation and can disagree with the
        # selected expiry around a roll.
        response = client.history({"symbol": symbol, "resolution": resolution, "date_format": 1, "range_from": (now - timedelta(days=lookback_days)).date().isoformat(), "range_to": now.date().isoformat(), "cont_flag": 0})
        if not isinstance(response, dict) or response.get("s") != "ok" or not isinstance(response.get("candles"), list):
            message = response.get("message") if isinstance(response, dict) else "invalid response"
            raise RuntimeError(f"FYERS EMA Band history is unavailable: {message or 'no candles'}")
        interval_seconds = int(resolution) * 60
        return [{"timestamp": int(row[0]), "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]) if len(row) > 5 and row[5] is not None else 0.0, "is_forming": int(row[0]) + interval_seconds > now.timestamp()} for row in response["candles"] if len(row) >= 5 and (include_forming or int(row[0]) + interval_seconds <= now.timestamp())]

    def ema_band_completed_candles(client, symbol, timeframe):
        return ema_band_candles(client, symbol, timeframe, include_forming=False)

    def ema_band_current_signal(client, symbol, timeframe, ema_length, entry_session=None):
        completed = ema_band_completed_candles(client, symbol, timeframe)
        return {**ema_band_strategy_signal(completed, ema_length, entry_session), "timeframe": timeframe, "completed_candles": len(completed)}

    def ema_band_current_exit(client, symbol, timeframe, ema_length):
        completed = ema_band_completed_candles(client, symbol, timeframe)
        return {**ema_band_exit_signal(completed, ema_length), "timeframe": timeframe, "completed_candles": len(completed)}

    def ema_band_chart_snapshot(client, symbol, timeframe, ema_length, bars=80):
        """Return fixed-contract FYERS candles, including a display-only forming bar."""
        cache_key = (symbol, timeframe, int(ema_length), int(bars))
        now = datetime.now().astimezone()
        cached_at = ema_chart_cache.get("refreshed_at")
        cached = ema_chart_cache.get("snapshot")
        if ema_chart_cache.get("key") == cache_key and cached and cached_at and (now - cached_at).total_seconds() < 15:
            snapshot = json.loads(json.dumps(cached))
        else:
            candles = ema_band_candles(client, symbol, timeframe, include_forming=True)
            length = int(ema_length)
            if len(candles) < max(length + 1, 3):
                raise RuntimeError("EMA Band chart needs more completed FYERS candles.")
            alpha = 2 / (length + 1)
            high_values, low_values, high_ema, low_ema = [], [], None, None
            for candle in candles:
                high = float(candle["high"]); low = float(candle["low"])
                high_ema = high if high_ema is None else alpha * high + (1 - alpha) * high_ema
                low_ema = low if low_ema is None else alpha * low + (1 - alpha) * low_ema
                high_values.append(high_ema); low_values.append(low_ema)
            state, markers = 0, {}
            for index in range(1, len(candles)):
                prior, current = candles[index - 1], candles[index]
                inside_band = low_values[index] <= float(current["close"]) <= high_values[index]
                if state and inside_band:
                    markers[index] = "EXIT BUY" if state > 0 else "EXIT SELL"; state = 0; continue
                midpoint = (float(prior["high"]) + float(prior["low"])) / 2
                long_ready = state == 0 and float(prior["open"]) <= high_values[index - 1] and float(prior["close"]) > high_values[index - 1] and float(current["close"]) > float(current["open"]) and float(current["open"]) > midpoint
                short_ready = state == 0 and float(prior["open"]) >= low_values[index - 1] and float(prior["close"]) < low_values[index - 1] and float(current["close"]) < float(current["open"]) and float(current["open"]) < midpoint
                if long_ready:
                    markers[index] = "BUY"; state = 1
                elif short_ready:
                    markers[index] = "SELL"; state = -1
            start = max(0, len(candles) - max(20, min(int(bars), 200)))
            completed = [candle for candle in candles if not candle.get("is_forming")]
            pivots = []
            for index in range(2, len(completed) - 2):
                high = float(completed[index]["high"])
                low = float(completed[index]["low"])
                if high > max(float(completed[i]["high"]) for i in (index - 2, index - 1, index + 1, index + 2)):
                    pivots.append(("RESISTANCE", high, completed[index]["timestamp"]))
                if low < min(float(completed[i]["low"]) for i in (index - 2, index - 1, index + 1, index + 2)):
                    pivots.append(("SUPPORT", low, completed[index]["timestamp"]))
            reference = float(completed[-1]["close"])
            supports = [item for item in pivots if item[0] == "SUPPORT" and item[1] <= reference]
            resistances = [item for item in pivots if item[0] == "RESISTANCE" and item[1] >= reference]
            levels = []
            if supports:
                label, price, timestamp = max(supports, key=lambda item: item[1])
                levels.append({"label": label, "price": round(price, 4), "timestamp": timestamp})
            if resistances:
                label, price, timestamp = min(resistances, key=lambda item: item[1])
                levels.append({"label": label, "price": round(price, 4), "timestamp": timestamp})
            snapshot = {"symbol": symbol, "timeframe": timeframe, "ema_length": length, "source": "FYERS fixed-contract candles", "levels": levels, "candles": [{**candle, "ema_high": round(high_values[index], 4), "ema_low": round(low_values[index], 4), "marker": None if candle.get("is_forming") else markers.get(index)} for index, candle in enumerate(candles[start:], start)]}
            ema_chart_cache.update({"key": cache_key, "snapshot": snapshot, "refreshed_at": now})
        quote = client.quotes({"symbols": symbol})
        values = ((quote.get("d") or [{}])[0].get("v") or {}) if isinstance(quote, dict) and quote.get("s") == "ok" else {}
        ltp = values.get("lp")
        if ltp is not None:
            live_price = float(ltp)
            snapshot["live_price"] = live_price
            snapshot["live_price_at"] = now.isoformat()
            if snapshot["candles"] and snapshot["candles"][-1].get("is_forming"):
                candle = snapshot["candles"][-1]
                candle["close"] = live_price
                candle["high"] = max(float(candle["high"]), live_price)
                candle["low"] = min(float(candle["low"]), live_price)
        return snapshot

    def ema_band_mode_capability(mode):
        requested_mode = str(mode or "PAPER").upper()
        if requested_mode not in {"PAPER", "LIVE"}:
            raise ValueError("EMA Band mode must be PAPER or LIVE.")
        if requested_mode == "PAPER":
            return {"mode": "PAPER", "submission_available": False, "message": "Paper/forward testing is active. No broker order route exists in this mode."}
        broker = fyers_execution.capabilities()
        submission_available = bool(broker["fyers_configured"] and broker["live_submission_enabled"])
        return {
            "mode": "LIVE", "submission_available": submission_available, "broker_configured": broker["fyers_configured"],
            "runtime_gate_enabled": broker["live_submission_enabled"],
            "required_gates": ["current FYERS master contract", "fresh underlying and option quotes", "exact order parameters from a fresh quote", "SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=1 runtime gate"],
            "message": ("Live EMA Band automatically submits a BUY order on a fresh completed-candle signal and auto-exits on the configured stop-loss/target percentage. No per-order manual confirmation step exists."
                        if submission_available else
                        "Live EMA Band order submission is configured but the runtime gate is off. Set SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=1 and connect a FYERS token to enable it."),
        }

    def resolve_ema_atm_option(underlying_symbol, timeframe, ema_length, mode="PAPER", entry_session=None):
        """Resolve a directional ATM option from a fresh quote and the cached master."""
        mode_status = ema_band_mode_capability(mode)
        state = ema_master_status()
        if not state["usable"]:
            raise RuntimeError("FYERS master cache is missing or older than 72 hours. ATM resolution is fail-closed until a refresh succeeds.")
        symbol = str(underlying_symbol or "").strip().upper()
        exchange = symbol.split(":", 1)[0] if ":" in symbol else ""
        cash_segment, option_segment = ("MCX_COM", "MCX_COM") if exchange == "MCX" else (f"{exchange}_CM", f"{exchange}_FO")
        if cash_segment not in FYERS_MASTER_SOURCES or option_segment not in FYERS_MASTER_SOURCES:
            raise ValueError("Choose a broker-master NSE/BSE cash/index or MCX commodity-future underlying.")
        def eligible_underlying(row):
            if len(row) < 17 or row[9] != symbol:
                return False
            if exchange == "MCX":
                return str(row[16]).upper() == "XX" and bool(str(row[13]).strip())
            return ema_cash_or_index_row_matches_exchange(row, exchange)
        cash_row = next((row for row in csv.reader(io.StringIO((ema_master_dir / f"{cash_segment}.csv").read_text(encoding="utf-8"))) if eligible_underlying(row)), None)
        if not cash_row:
            raise ValueError("The selected underlying is absent from the current FYERS supported cash/index or commodity-future master.")
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            raise RuntimeError("FYERS authentication is required to obtain a fresh underlying quote for ATM selection.")
        app_id, access_token = token.split(":", 1)
        client = fyersModel.FyersModel(client_id=app_id, token=access_token)
        signal = ema_band_current_signal(client, symbol, timeframe, ema_length, entry_session)
        if not signal.get("direction"):
            raise RuntimeError(signal["message"])
        quote = client.quotes({"symbols": symbol})
        quote_values = ((quote.get("d") or [{}])[0].get("v") or {}) if isinstance(quote, dict) and quote.get("s") == "ok" else {}
        spot = quote_values.get("lp")
        rows = csv.reader(io.StringIO((ema_master_dir / f"{option_segment}.csv").read_text(encoding="utf-8")))
        contract = select_ema_atm_option(rows, cash_row[13], signal["direction"], spot, datetime.now().timestamp())
        response = client.quotes({"symbols": contract["symbol"]})
        option_values = ((response.get("d") or [{}])[0].get("v") or {}) if isinstance(response, dict) and response.get("s") == "ok" else {}
        option_quote = {"bid": option_values.get("bid"), "ask": option_values.get("ask")}
        return {
            "underlying_symbol": symbol, "underlying": cash_row[13], "direction": signal["direction"], "signal": signal,
            "spot": float(spot), "segment": option_segment, "contract": contract,
            "master_validation": "current FYERS master; nearest unexpired expiry and nearest strike to fresh FYERS underlying quote",
            "requested_mode": mode_status["mode"], "mode_status": mode_status,
            "option_quote": option_quote,
            "execution": "PAPER_ONLY_NO_ORDER_ROUTE" if mode_status["mode"] == "PAPER" else "LIVE_PREVIEW_ONLY_NO_ORDER_ROUTE",
        }

    ema_runner = {"running": False, "status": "STOPPED", "config": None, "last_event": None, "last_signal_key": None, "last_watch_key": None, "run_started_at": None, "thread": None, "position": None, "chart": None}
    ema_runner_lock = threading.Lock()
    ema_runner_paper_log = ROOT / ".private" / "ema-band-runner-paper.jsonl"
    ema_runner_live_log = ROOT / ".private" / "ema-band-runner-live.jsonl"

    def ema_execution_log(limit=200):
        """Merge the paper and live EMA Band journals into one newest-first execution log."""
        entries = []
        for path, source in ((ema_runner_paper_log, "PAPER"), (ema_runner_live_log, "LIVE")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (FileNotFoundError, OSError):
                continue
            for line in lines[-limit:]:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict):
                    record.setdefault("source", source)
                    entries.append(record)
        entries.sort(key=lambda item: item.get("at") or "", reverse=True)
        return entries[:limit]

    def ema_runner_snapshot():
        with ema_runner_lock:
            snapshot = {key: value for key, value in ema_runner.items() if key != "thread"}
            # A stopping monitor can be unwinding an API call. Never expose any
            # context it may race to write after stop was requested.
            if not snapshot["running"]:
                snapshot.update({"status": "STOPPED", "config": None, "last_event": None,
                                 "last_signal_key": None, "last_watch_key": None, "run_started_at": None, "position": None, "chart": None})
            return snapshot

    def start_ema_runner(payload):
        mode = str(payload.get("mode") or "PAPER").upper()
        config = {
            "underlying": str(payload.get("underlying") or "").upper(), "timeframe": str(payload.get("timeframe") or "5 minutes"),
            "ema_length": int(payload.get("ema_length") or 21), "mode": mode,
        }
        if not config["underlying"]:
            raise ValueError("Choose an option-eligible broker-master underlying before starting the EMA Band runner.")
        requested_session = str(payload.get("entry_session") or ema_entry_session_for_symbol(config["underlying"])).strip()
        if requested_session != ema_entry_session_for_symbol(config["underlying"]):
            raise ValueError(f"The EMA Band entry session for {config['underlying'].split(':', 1)[0]} must be {ema_entry_session_for_symbol(config['underlying'])} IST.")
        # Validate formatting before the live thread starts. This only gates new
        # entries; exits remain available after the entry window closes.
        ema_candle_in_entry_session(datetime.now(tz=EMA_IST).timestamp(), requested_session)
        config["entry_session"] = requested_session
        ema_band_mode_capability(mode)
        if mode == "LIVE":
            def optional_pct(key):
                raw = payload.get(key)
                if raw is None or str(raw).strip() == "":
                    return None
                try:
                    return float(raw)
                except (TypeError, ValueError) as error:
                    raise ValueError(f"{key.replace('_', ' ')} must be a number when provided.") from error
            try:
                config["lots"] = int(payload.get("lots"))
            except (TypeError, ValueError) as error:
                raise ValueError("Live order submission requires whole-number lots.") from error
            if config["lots"] < 1:
                raise ValueError("Live order submission requires at least one lot.")
            config["stop_loss_pct"] = optional_pct("stop_loss_pct")
            config["target_profit_pct"] = optional_pct("target_profit_pct")
            config["profit_protection_pct"] = optional_pct("profit_protection_pct")
            if config["stop_loss_pct"] is not None and not 0 < config["stop_loss_pct"] < 100:
                raise ValueError("The stop-loss percentage, when set, must be below 100%.")
            if config["target_profit_pct"] is not None and config["target_profit_pct"] <= 0:
                raise ValueError("The target percentage, when set, must be positive.")
            if config["profit_protection_pct"] is not None and not 0 < config["profit_protection_pct"] < 100:
                raise ValueError("The profit-protection risk unit, when set, must be below 100%.")
            if config["stop_loss_pct"] is not None and config["target_profit_pct"] is not None and config["target_profit_pct"] < config["stop_loss_pct"]:
                raise ValueError("The target percentage must be at least the stop-loss percentage.")
            # Stop-loss/target are optional safety nets. The indicator-based exit
            # (a completed candle closing back inside the EMA High/Low band, the
            # same rule the Pine strategy uses) is always active for live positions.
        else:
            # Paper mode mirrors the price and protection lifecycle but never
            # reaches a broker-order function.
            config.update({"lots": int(payload.get("lots") or 1), "stop_loss_pct": None,
                           "target_profit_pct": None, "profit_protection_pct": float(payload.get("profit_protection_pct") or 20)})
        with ema_runner_lock:
            if ema_runner["running"]:
                raise RuntimeError("The EMA Band runner is already monitoring a selected underlying.")
            ema_runner.update({"running": True, "status": "MONITORING", "config": config, "last_event": None, "last_signal_key": None, "last_watch_key": None, "run_started_at": datetime.now().astimezone().isoformat(), "position": None, "chart": None})

        def live_client():
            token = load_config().get("FYERS_ACCESS_TOKEN", "")
            if not token or ":" not in token:
                raise RuntimeError("FYERS authentication is required for live EMA Band order submission.")
            app_id, access_token = token.split(":", 1)
            return fyersModel.FyersModel(client_id=app_id, token=access_token)

        def broker_has_open_position():
            response = live_client().positions()
            if not isinstance(response, dict) or response.get("s") != "ok":
                raise RuntimeError("FYERS positions are unavailable; fresh EMA entry is blocked.")
            for row in response.get("netPositions") or (response.get("data") or {}).get("netPositions") or []:
                try:
                    if float(row.get("netQty", row.get("qty", 0)) or 0) != 0:
                        return True
                except (TypeError, ValueError):
                    continue
            return False

        def adopt_matching_manual_position():
            """Adopt exactly one broker-confirmed long option on this underlying.

            Ambiguous, short, or unmapped positions fail closed: an automated exit
            must never be pointed at a guessed manual trade.
            """
            client = live_client()
            response = client.positions()
            if not isinstance(response, dict) or response.get("s") != "ok":
                raise RuntimeError("FYERS positions are unavailable; manual-position adoption is blocked.")
            exchange = config["underlying"].split(":", 1)[0]
            segment = "MCX_COM" if exchange == "MCX" else f"{exchange}_FO"
            selected_master = "MCX_COM" if exchange == "MCX" else f"{exchange}_CM"
            source_rows = list(csv.reader(io.StringIO((ema_master_dir / f"{selected_master}.csv").read_text(encoding="utf-8"))))
            selected = next((row for row in source_rows if len(row) > 13 and row[9] == config["underlying"]), None)
            if not selected:
                raise RuntimeError("The selected EMA underlying is absent from the current FYERS master.")
            option_rows = {row[9]: row for row in csv.reader(io.StringIO((ema_master_dir / f"{segment}.csv").read_text(encoding="utf-8"))) if len(row) > 16 and row[13] == selected[13] and str(row[16]).upper() in {"CE", "PE"}}
            candidates = []
            for row in response.get("netPositions") or (response.get("data") or {}).get("netPositions") or []:
                symbol = str(row.get("symbol") or "")
                try:
                    quantity = int(float(row.get("netQty", row.get("qty", 0)) or 0))
                    entry = float(row.get("netAvg", row.get("buyAvg", row.get("buy_rate", 0))) or 0)
                except (TypeError, ValueError):
                    continue
                if symbol in option_rows and quantity > 0 and entry > 0:
                    candidates.append((row, option_rows[symbol], quantity, entry))
            if len(candidates) > 1:
                raise RuntimeError("More than one matching manual long option is open; choose one position before starting automated EMA management.")
            if not candidates:
                return None
            row, contract_row, quantity, entry = candidates[0]
            lot_size, tick_size = int(float(contract_row[3])), float(contract_row[4])
            return {"symbol": str(row["symbol"]), "description": str(contract_row[1]), "quantity": quantity, "lots": max(1, quantity // lot_size), "entry_price": entry, "stop_price": None, "target_price": None, "profit_protection_pct": config["profit_protection_pct"], "profit_peak_price": entry, "profit_protection_stop": None, "adopted_manual_position": True, "opened_at": datetime.now().astimezone().isoformat(), "lot_size": lot_size, "tick_size": tick_size}

        def submit_live_entry(ticket):
            if os.getenv("SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS") != "1":
                raise RuntimeError("Live FYERS submission is disabled. Set SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=1 to allow the EMA Band runner to place real orders.")
            client = live_client()
            order = {"symbol": ticket["symbol"], "qty": ticket["quantity"], "type": 1, "side": 1,
                     "productType": "MARGIN", "limitPrice": ticket["limit_price"], "stopPrice": 0,
                     "validity": "DAY", "disclosedQty": 0, "offlineOrder": False}
            response = client.place_order(order)
            order_ids = _ema_order_ids(response)
            if not order_ids:
                raise RuntimeError(f"FYERS did not accept the EMA Band entry order: {response}")
            return order_ids[0]

        def confirm_open_buy_position(client, symbol, minimum_quantity):
            """Verify FYERS itself shows a filled, still-open BUY of at least this quantity
            for this exact symbol before any SELL exit order is ever submitted."""
            result, message = ema_open_buy_reconciliation(client.positions(), symbol, minimum_quantity)
            return result == "CONFIRMED", message

        def submit_live_exit(position, reason, ltp):
            client = live_client()
            confirmed, block_reason = confirm_open_buy_position(client, position["symbol"], position["quantity"])
            if not confirmed:
                raise PermissionError(block_reason)
            with ema_runner_lock:
                if not ema_runner["running"] or ema_runner.get("position") != position:
                    raise PermissionError("EMA Band runner stopped or its position context was reset; no exit order will be submitted.")
            order = {"symbol": position["symbol"], "qty": position["quantity"], "type": 2, "side": -1,
                     "productType": "MARGIN", "limitPrice": 0, "stopPrice": 0,
                     "validity": "DAY", "disclosedQty": 0, "offlineOrder": False}
            response = client.place_order(order)
            order_ids = _ema_order_ids(response)
            if not order_ids:
                raise RuntimeError(f"FYERS did not accept the EMA Band exit order: {response}")
            return {"exit_order_id": order_ids[0], "exit_reason": reason, "exit_ltp": ltp}

        def append_live_log(event):
            ema_runner_live_log.parent.mkdir(parents=True, exist_ok=True)
            with ema_runner_live_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, separators=(",", ":")) + "\n")

        def record_ema_tick(ltp, max_points=200):
            """Append one live price point to the open position's chart and refresh its live P&L."""
            with ema_runner_lock:
                chart = ema_runner.get("chart")
                if not chart or chart.get("closed"):
                    return
                entry_price = chart.get("entry_price")
                quantity = chart.get("quantity") or 0
                chart["ticks"].append({"at": datetime.now().astimezone().isoformat(), "ltp": ltp})
                if len(chart["ticks"]) > max_points:
                    chart["ticks"] = chart["ticks"][-max_points:]
                chart["ltp"] = ltp
                if entry_price:
                    chart["unrealized_pnl_rupees"] = round((ltp - entry_price) * quantity, 2)
                    chart["unrealized_pnl_pct"] = round((ltp / entry_price - 1) * 100, 2)

        def monitor():
            while True:
                with ema_runner_lock:
                    if not ema_runner["running"]:
                        return
                try:
                    with ema_runner_lock:
                        position = ema_runner.get("position")
                    if config["mode"] == "LIVE" and position:
                        client = live_client()
                        reconciliation, reconciliation_message = ema_open_buy_reconciliation(
                            client.positions(), position["symbol"], position["quantity"]
                        )
                        if reconciliation != "CONFIRMED":
                            # A manual square-off, partial fill, or unavailable broker state
                            # invalidates local context. Never chart or submit an exit for it.
                            event = {"at": datetime.now().astimezone().isoformat(), "mode": "LIVE",
                                     "status": "LIVE_POSITION_RECONCILIATION_FAILED",
                                     "reconciliation": reconciliation, "message": reconciliation_message}
                            with ema_runner_lock:
                                ema_runner["status"] = event["status"]
                                ema_runner["last_event"] = event
                                ema_runner["position"] = None
                                ema_runner["chart"] = None
                            append_live_log(event)
                            threading.Event().wait(15)
                            continue
                        quote = client.quotes({"symbols": position["symbol"]})
                        values = ((quote.get("d") or [{}])[0].get("v") or {}) if isinstance(quote, dict) and quote.get("s") == "ok" else {}
                        ltp = values.get("lp")
                        if ltp is None:
                            raise RuntimeError("FYERS did not return a live price for the open EMA Band position.")
                        ltp = float(ltp)
                        protection = None
                        if position.get("profit_protection_pct") is not None:
                            protection = ema_profit_protection(position["entry_price"], ltp, position["profit_protection_pct"], position.get("profit_peak_price"), position.get("profit_protection_stop"))
                            position["profit_peak_price"] = protection["peak_price"]
                            position["profit_protection_stop"] = protection["stop_price"]
                            position["profit_protection_stage"] = protection["stage"]
                        hit_stop = (position.get("stop_price") is not None and ltp <= position["stop_price"]) or bool(protection and protection["exit"])
                        hit_target = position.get("target_price") is not None and ltp >= position["target_price"]
                        record_ema_tick(ltp)
                        indicator_exit = ema_band_current_exit(client, config["underlying"], config["timeframe"], config["ema_length"])
                        hit_indicator = bool(indicator_exit.get("exit"))
                        if hit_stop or hit_target or hit_indicator:
                            reason = "PROFIT_PROTECTION" if protection and protection["exit"] else "STOP_LOSS" if hit_stop else "TARGET" if hit_target else "INDICATOR_EXIT"
                            try:
                                exit_result = submit_live_exit(position, reason, ltp)
                            except PermissionError as blocked:
                                # Submit-time reconciliation failed: never place a SELL and
                                # discard the stale local position/chart context.
                                event = {"at": datetime.now().astimezone().isoformat(), "mode": "LIVE", "status": "LIVE_POSITION_RECONCILIATION_FAILED",
                                          "reconciliation": "ABSENT_OR_PARTIAL", "message": str(blocked)}
                                with ema_runner_lock:
                                    ema_runner["status"] = event["status"]
                                    ema_runner["last_event"] = event
                                    ema_runner["position"] = None
                                    ema_runner["chart"] = None
                                append_live_log(event)
                            else:
                                realized_pnl = round((ltp - position["entry_price"]) * position["quantity"], 2) if ltp is not None else None
                                event = {"at": datetime.now().astimezone().isoformat(), "mode": "LIVE", "status": "LIVE_EXIT_SUBMITTED",
                                          "position": position, "indicator_exit": indicator_exit, "realized_pnl_rupees": realized_pnl, **exit_result}
                                with ema_runner_lock:
                                    ema_runner["status"] = event["status"]
                                    ema_runner["last_event"] = event
                                    ema_runner["position"] = None
                                    if ema_runner.get("chart"):
                                        ema_runner["chart"].update({"closed": True, "exit_price": ltp, "exit_reason": reason,
                                                                     "exit_order_id": exit_result.get("exit_order_id"), "realized_pnl_rupees": realized_pnl,
                                                                     "closed_at": event["at"]})
                                append_live_log(event)
                        else:
                            with ema_runner_lock:
                                ema_runner["status"] = "LIVE_POSITION_OPEN"
                                ema_runner["last_event"] = {"at": datetime.now().astimezone().isoformat(), "mode": "LIVE", "status": "LIVE_POSITION_OPEN", "position": position, "ltp": ltp, "indicator_exit": indicator_exit, "profit_protection": protection}
                    elif config["mode"] == "PAPER" and position:
                        client = live_client()
                        quote = client.quotes({"symbols": position["symbol"]})
                        values = ((quote.get("d") or [{}])[0].get("v") or {}) if isinstance(quote, dict) and quote.get("s") == "ok" else {}
                        ltp = values.get("lp")
                        if ltp is None:
                            raise RuntimeError("FYERS did not return a live price for the paper EMA option position.")
                        ltp = float(ltp)
                        protection = ema_profit_protection(position["entry_price"], ltp, position["profit_protection_pct"], position.get("profit_peak_price"), position.get("profit_protection_stop"))
                        position.update({"profit_peak_price": protection["peak_price"], "profit_protection_stop": protection["stop_price"], "profit_protection_stage": protection["stage"]})
                        record_ema_tick(ltp)
                        indicator_exit = ema_band_current_exit(client, config["underlying"], config["timeframe"], config["ema_length"])
                        if protection["exit"] or indicator_exit.get("exit"):
                            reason = "PROFIT_PROTECTION" if protection["exit"] else "INDICATOR_EXIT"
                            realized_pnl = round((ltp - position["entry_price"]) * position["quantity"], 2)
                            event = {"at": datetime.now().astimezone().isoformat(), "mode": "PAPER", "status": "PAPER_EXIT_RECORDED", "position": position, "exit_ltp": ltp, "exit_reason": reason, "realized_pnl_rupees": realized_pnl, "indicator_exit": indicator_exit}
                            with ema_runner_lock:
                                ema_runner.update({"status": event["status"], "last_event": event, "position": None})
                                if ema_runner.get("chart"):
                                    ema_runner["chart"].update({"closed": True, "exit_price": ltp, "exit_reason": reason, "realized_pnl_rupees": realized_pnl, "closed_at": event["at"]})
                            append_live_log(event)
                        else:
                            with ema_runner_lock:
                                ema_runner["status"] = "PAPER_POSITION_OPEN"
                                ema_runner["last_event"] = {"at": datetime.now().astimezone().isoformat(), "mode": "PAPER", "status": "PAPER_POSITION_OPEN", "position": position, "ltp": ltp, "indicator_exit": indicator_exit, "profit_protection": protection}
                    else:
                        if config["mode"] == "LIVE" and broker_has_open_position():
                            event = {"at": datetime.now().astimezone().isoformat(), "mode": "LIVE", "status": "BLOCKED_BROKER_POSITION_OPEN", "message": "FYERS reports an open broker position. No fresh EMA entry will be submitted until the broker position is closed."}
                            with ema_runner_lock:
                                ema_runner["status"] = event["status"]
                                ema_runner["last_event"] = event
                            threading.Event().wait(15)
                            continue
                        resolved = resolve_ema_atm_option(config["underlying"], config["timeframe"], config["ema_length"], config["mode"], config["entry_session"])
                        signal_key = f"{resolved['signal']['completed_candle']}:{resolved['contract']['symbol']}"
                        event = {"at": datetime.now().astimezone().isoformat(), "signal": resolved["signal"], "contract": resolved["contract"], "underlying": resolved["underlying_symbol"], "mode": config["mode"]}
                        with ema_runner_lock:
                            duplicate = ema_runner["last_signal_key"] == signal_key
                            ema_runner["last_signal_key"] = signal_key
                        if config["mode"] == "PAPER":
                            ticket = ema_live_ticket_preview(resolved["contract"], resolved.get("option_quote") or {}, config["lots"], config["stop_loss_pct"], config["target_profit_pct"], config["profit_protection_pct"])
                            event["ticket"] = ticket
                            event["status"] = "PAPER_ENTRY_RECORDED" if not duplicate else "PAPER_ENTRY_ALREADY_RECORDED"
                            with ema_runner_lock:
                                ema_runner["status"] = event["status"]
                                ema_runner["last_event"] = event
                                if not duplicate:
                                    position = {"symbol": ticket["symbol"], "description": ticket["description"], "quantity": ticket["quantity"], "lots": ticket["lots"], "entry_price": ticket["limit_price"], "stop_price": ticket["stop_price"], "target_price": ticket["target_price"], "profit_protection_pct": ticket["profit_protection_pct"], "profit_peak_price": ticket["limit_price"], "profit_protection_stop": None, "opened_at": event["at"]}
                                    ema_runner["position"] = position
                                    ema_runner["chart"] = {"symbol": ticket["symbol"], "description": ticket["description"], "quantity": ticket["quantity"], "entry_price": ticket["limit_price"], "stop_price": ticket["stop_price"], "target_price": ticket["target_price"], "opened_at": event["at"], "closed": False, "exit_price": None, "exit_reason": None, "realized_pnl_rupees": None, "ticks": []}
                            if not duplicate:
                                ema_runner_paper_log.parent.mkdir(parents=True, exist_ok=True)
                                with ema_runner_paper_log.open("a", encoding="utf-8") as handle:
                                    handle.write(json.dumps(event, separators=(",", ":")) + "\n")
                        elif not duplicate:
                            ticket = ema_live_ticket_preview(resolved["contract"], resolved.get("option_quote") or {}, config["lots"], config["stop_loss_pct"], config["target_profit_pct"], config["profit_protection_pct"])
                            order_id = submit_live_entry(ticket)
                            position = {"symbol": ticket["symbol"], "description": ticket["description"], "quantity": ticket["quantity"],
                                        "lots": ticket["lots"], "entry_price": ticket["limit_price"], "stop_price": ticket["stop_price"],
                                        "target_price": ticket["target_price"], "profit_protection_pct": ticket["profit_protection_pct"], "profit_peak_price": ticket["limit_price"], "profit_protection_stop": None, "entry_order_id": order_id, "opened_at": event["at"]}
                            event["ticket"] = ticket
                            event["order_id"] = order_id
                            event["status"] = "LIVE_ENTRY_SUBMITTED"
                            with ema_runner_lock:
                                ema_runner["status"] = event["status"]
                                ema_runner["last_event"] = event
                                ema_runner["position"] = position
                                ema_runner["chart"] = {
                                    "symbol": ticket["symbol"], "description": ticket["description"], "quantity": ticket["quantity"],
                                    "entry_price": ticket["limit_price"], "stop_price": ticket["stop_price"], "target_price": ticket["target_price"],
                                    "opened_at": event["at"], "closed": False, "exit_price": None, "exit_reason": None, "realized_pnl_rupees": None,
                                    "ticks": [],
                                }
                            append_live_log(event)
                        else:
                            event["status"] = "LIVE_ENTRY_ALREADY_SUBMITTED"
                            with ema_runner_lock:
                                ema_runner["status"] = event["status"]
                                ema_runner["last_event"] = event
                except Exception as error:
                    message = str(error)
                    checklist = None
                    watch_key = None
                    if "No completed EMA Band entry signal" in message:
                        try:
                            candles = ema_band_completed_candles(live_client(), config["underlying"], config["timeframe"])
                            checklist = ema_band_entry_checklist(candles, config["ema_length"], has_active_position=False)
                            watch_key = json.dumps({"candle": checklist.get("completed_candle"), "checks": checklist.get("checks")}, sort_keys=True)
                        except Exception as checklist_error:
                            message = f"{message}; checklist unavailable: {checklist_error}"
                    with ema_runner_lock:
                        ema_runner["status"] = "WATCHING_NO_ENTRY" if "No completed EMA Band entry signal" in message else "BLOCKED"
                        event = {"at": datetime.now().astimezone().isoformat(), "status": ema_runner["status"], "message": message, "mode": config["mode"], "checklist": checklist}
                        changed_watch = checklist is not None and ema_runner.get("last_watch_key") != watch_key
                        if changed_watch:
                            ema_runner["last_watch_key"] = watch_key
                        ema_runner["last_event"] = event
                    if changed_watch:
                        journal = ema_runner_paper_log if config["mode"] == "PAPER" else ema_runner_live_log
                        journal.parent.mkdir(parents=True, exist_ok=True)
                        with journal.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(event, separators=(",", ":")) + "\n")
                # LIVE mode places real FYERS orders: a BUY entry on a fresh completed-candle
                # signal, then an automatic SELL exit once the indicator-defined exit fires
                # (or, if configured, once the optional stop-loss/target price is hit).
                threading.Event().wait(15)

        if config["mode"] == "LIVE":
            adopted = adopt_matching_manual_position()
            if adopted:
                event = {"at": datetime.now().astimezone().isoformat(), "mode": "LIVE", "status": "LIVE_MANUAL_POSITION_ADOPTED", "position": adopted, "message": "Broker-confirmed manual option position adopted for EMA exits and premium protection."}
                with ema_runner_lock:
                    ema_runner.update({"status": event["status"], "last_event": event, "position": adopted, "chart": {"symbol": adopted["symbol"], "description": adopted["description"], "quantity": adopted["quantity"], "entry_price": adopted["entry_price"], "stop_price": None, "target_price": None, "opened_at": event["at"], "closed": False, "exit_price": None, "exit_reason": None, "realized_pnl_rupees": None, "ticks": []}})
                append_live_log(event)
        thread = threading.Thread(target=monitor, daemon=True, name="ema-band-runner")
        with ema_runner_lock:
            ema_runner["thread"] = thread
        thread.start()
        return ema_runner_snapshot()

    def stop_ema_runner():
        with ema_runner_lock:
            # The execution journals are durable history.  The runner snapshot is
            # only current monitoring context, so never expose an old ticket,
            # closed chart, or prior entry/exit as though it belongs to a stopped
            # runner.
            ema_runner.update({
                "running": False, "status": "STOPPED", "config": None,
                "last_event": None, "last_signal_key": None, "last_watch_key": None, "run_started_at": None, "thread": None,
                "position": None, "chart": None,
            })
        return ema_runner_snapshot()

    def ema_master_refresh_loop():
        while True:
            try:
                if not ema_master_status()["fresh"]:
                    refresh_ema_masters()
            except Exception:
                # Preserve the last successful cache; status exposes freshness.
                pass
            threading.Event().wait(3600)

    threading.Thread(target=ema_master_refresh_loop, daemon=True, name="ema-band-master-refresh").start()
    automation_policy = AutomationPolicyService()
    sensex_straddle = SensexStraddleService(
        credential_provider=lambda: load_config().get("FYERS_ACCESS_TOKEN", ""),
        runtime_dir=ROOT / ".private" / "sensex-straddle",
    )
    nifty_straddle = NiftyStraddleService(
        credential_provider=lambda: load_config().get("FYERS_ACCESS_TOKEN", ""),
        runtime_dir=ROOT / ".private" / "nifty-straddle",
    )
    straddle_squareoff = StraddleSquareOffService(
        credential_provider=lambda: load_config().get("FYERS_ACCESS_TOKEN", ""),
        runners={"sensex": sensex_straddle, "nifty": nifty_straddle},
    )
    fyers_execution = FyersExecutionService(execution_halt=automation_policy.halt)
    analysis_runs = {}
    screener_analysis_cache = {}

    def replace_feed(token):
        previous_feed = state.get("feed")
        if previous_feed:
            previous_feed.stop()
        previous_analysis = state.get("sector_analysis")
        if previous_analysis:
            previous_analysis.running = False
        replacement = FyersLiveFeed(token)
        replacement.start()
        state["feed"] = replacement
        replacement_analysis = SectorAnalysisService(token)
        replacement_analysis.start()
        state["sector_analysis"] = replacement_analysis
        state["auth_error"] = None

    def mark_auth_failure(*responses):
        if not any(is_token_error(response) for response in responses):
            return
        state["auth_error"] = "Fyers authentication expired; browser reauthentication is required."
        active_feed = state["feed"]
        if active_feed:
            with active_feed.lock:
                active_feed.token_expired = True
                active_feed.connected = False
                active_feed.error = state["auth_error"]

    def renew_when_needed():
        """Reuse a newly cached token first, then start supported browser OAuth."""
        import time
        while True:
            time.sleep(1)
            active_feed = state["feed"]
            needs_auth = active_feed is None or active_feed.token_expired
            if not needs_auth or state["renewing"] or time.monotonic() < state["next_auth_attempt"]:
                continue
            latest_token = load_config().get("FYERS_ACCESS_TOKEN", "")
            if latest_token and (active_feed is None or latest_token != active_feed.access_token):
                print("New Fyers token found in the private cache; reconnecting the feed.")
                replace_feed(latest_token)
                continue
            state["auth_error"] = "Fyers authentication expired; use Refresh authentication and complete daily 2FA."
            state["next_auth_attempt"] = time.monotonic() + 60
    from threading import Thread
    Thread(target=renew_when_needed, daemon=True, name="fyers-token-supervisor").start()
    def snapshot():
        if state["feed"]:
            result = state["feed"].snapshot()
            if state["auth_error"] and not result.get("connected"):
                result["error"] = state["auth_error"]
            return result
        return {"mode":"needs_token", "connected":False, "error":state["auth_error"] or "No reusable Fyers token was found. Reauthentication will start automatically.", "updated_at":None, "snapshot_at":datetime.now().astimezone().isoformat(), "provider":"FYERS", "weight_source":OFFICIAL_WEIGHT_SET.summary(), "market_session":market_session(), "sectors":[]}

    def attach_live_attribution(result):
        live_by_id = {item.get("sector_id"): item for item in snapshot().get("sectors", [])}
        for sector in result.get("sectors", []):
            live_sector = live_by_id.get(sector.get("sector_id"))
            if not live_sector:
                continue
            sector["constituent_movers"] = live_sector.get("drivers", [])
            sector["top_contributors"] = live_sector.get("top_contributors", [])
            sector["attribution"] = live_sector.get("attribution", sector.get("attribution"))
            sector["provider_tick_timestamp"] = live_sector.get("provider_tick_timestamp")
            sector["provider_tick_timestamp_iso"] = live_sector.get("provider_tick_timestamp_iso")
        return result
    def account_summary():
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            return {"pnl": 0, "positions": [], "available_funds": None, "week_realized_pnl": None, "month_realized_pnl": None, "connected": False, "error": state["auth_error"] or "No reusable Fyers token was found."}
        app_id, access_token = token.split(":", 1)
        client = fyersModel.FyersModel(client_id=app_id, token=access_token)
        response = client.positions()
        positions = response.get("netPositions", [])
        funds = client.funds()
        mark_auth_failure(response, funds)
        connected = response.get("s") == "ok" and funds.get("s") == "ok"
        if not connected:
            return {"pnl": None, "positions": [], "available_funds": None, "week_realized_pnl": None, "month_realized_pnl": None, "connected": False, "error": state["auth_error"] or "FYERS account data is unavailable."}
        try:
            balance = available_funds(funds)
        except FyersExecutionUnavailable as error:
            return {"pnl": None, "positions": [], "available_funds": None, "week_realized_pnl": None, "month_realized_pnl": None, "connected": False, "error": str(error)}
        state["auth_error"] = None
        gross_pnl = round(sum(float(item.get("pl", 0) or 0) for item in positions), 2)
        try:
            tradebook = client.tradebook()
            mark_auth_failure(tradebook)
            trades = tradebook.get("tradeBook") or tradebook.get("tradebook") or tradebook.get("data") or []
            charges = estimate_fyers_trade_charges(trades) if tradebook.get("s") == "ok" else {"available": False, "estimated": True, "total": None, "breakdown": {}, "disclaimer": "FYERS tradebook was unavailable, so intraday charges cannot be estimated."}
        except Exception:
            charges = {"available": False, "estimated": True, "total": None, "breakdown": {}, "disclaimer": "FYERS tradebook was unavailable, so intraday charges cannot be estimated."}
        estimated_net = round(gross_pnl - charges["total"], 2) if charges.get("total") is not None else None
        account = {"pnl": gross_pnl, "estimated_charges": charges, "estimated_net_pnl": estimated_net,
                   "positions": positions, "available_funds": balance, "week_realized_pnl": None, "month_realized_pnl": None, "connected": True, "error": None}
        account["live_pnl_snapshot"] = publish_live_pnl_snapshot(account)
        return account
    def realized_pnl(period):
        today = datetime.now().date()
        if period == "daily": start = today
        elif period == "weekly": start = today - timedelta(days=today.weekday())
        elif period == "monthly": start = today.replace(day=1)
        else: start = today.replace(month=4, day=1) if today.month >= 4 else today.replace(year=today.year - 1, month=4, day=1)
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            return {"period": period, "from_date": start.isoformat(), "to_date": today.isoformat(), "records": [], "summary": {}, "connected": False, "supported": False, "message": "Connect FYERS to load realised P&L history."}
        app_id, access_token = token.split(":", 1)
        report = fetch_realized_pnl_report(app_id, access_token, start, today)
        if not report["supported"]:
            return {"period": period, "from_date": start.isoformat(), "to_date": today.isoformat(), "records": [], "summary": {}, "connected": True, "supported": False, "message": report["message"]}
        mark_auth_failure(report)
        records = [{"symbol": row.get("symbol_name", "—"), "segment": row.get("segment_name", "—"), "buy_qty": row.get("buy_qty", 0), "buy_rate": row.get("buy_rate", 0), "sell_qty": row.get("sell_qty", 0), "sell_rate": row.get("sell_rate", 0), "pnl": row.get("realized_pnl", 0)} for row in report.get("data", [])]
        if records:
            return {"period": period, "from_date": start.isoformat(), "to_date": today.isoformat(), "records": records, "summary": report.get("summary_data", {}), "connected": True, "supported": True, "source": "realised_pnl_history", "message": report.get("message")}

        # FYERS can publish the reports feed after intraday positions have already
        # been squared off. Surface those broker rows now instead of showing empty.
        positions_response = fyersModel.FyersModel(client_id=app_id, token=access_token).positions()
        mark_auth_failure(positions_response)
        fallback_records = closed_position_records(positions_response.get("netPositions", [])) if positions_response.get("s") == "ok" else []
        fallback_summary = {"net_pnl": round(sum(float(row["pnl"] or 0) for row in fallback_records), 2)} if fallback_records else {}
        return {"period": period, "from_date": start.isoformat(), "to_date": today.isoformat(), "records": fallback_records, "summary": fallback_summary, "connected": True, "supported": True, "source": "positions_same_day_fallback" if fallback_records else "realised_pnl_history", "message": "Showing today’s squared-off FYERS positions while the realised-P&L report is pending." if fallback_records else report.get("message")}

    def alignment_candidates(mode):
        return state["sector_analysis"].alignment_candidates(snapshot().get("sectors", []), mode=mode)

    def analyze_screener_candidates(payload):
        """Bounded advisory analysis of explicit Chartink members; never creates order authority."""
        raw_symbols = payload.get("symbols") if isinstance(payload.get("symbols"), list) else []
        symbols = list(dict.fromkeys(str(value or "").strip().upper() for value in raw_symbols if value))[:61]
        offset = max(0, int(payload.get("offset") or 0))
        limit = min(12, max(1, int(payload.get("limit") or 12)))
        page = symbols[offset:offset + limit]
        prices = payload.get("prices") if isinstance(payload.get("prices"), dict) else {}
        service = state["sector_analysis"]
        if not service.provider:
            raise RuntimeError("FYERS authentication is required for completed-candle screener analysis.")
        cache_key = tuple(page)
        cached = screener_analysis_cache.get(cache_key)
        import time as time_module
        if cached and time_module.monotonic() - cached[0] < 300:
            result = dict(cached[1]); result["cached"] = True; return result
        benchmark = service._timeframe_candles("NSE:NIFTY50-INDEX")
        rows = []
        with service.candidate_scan_lock:
            for ticker in page:
                symbol = f"NSE:{ticker}-EQ"
                try:
                    candles = service._timeframe_candles(symbol)
                    states = {timeframe: calculate_timeframe_state(timeframe, candles.get(timeframe, []), benchmark.get(timeframe, []), service._quality(timeframe, candles.get(timeframe, []))) for timeframe in TIMEFRAMES}
                    alignment = mtf_alignment(states)
                    qualities = [str(item.get("data_quality") or "UNAVAILABLE").upper() for item in states.values()]
                    stripped = {name: {key: value for key, value in item.items() if key != "series"} for name, item in states.items()}
                    if any(value in {"STALE", "UNAVAILABLE", "INSUFFICIENT DATA"} for value in qualities):
                        rows.append({"symbol": ticker, "decision": "REJECT", "reason": "Completed-candle evidence is stale, unavailable, or insufficient.", "alignment": alignment, "timeframe_states": stripped}); continue
                    if alignment not in {"FULL BULLISH ALIGNMENT", "FULL BEARISH ALIGNMENT"}:
                        rows.append({"symbol": ticker, "decision": "WATCHLIST", "reason": f"Requires full 15m, 1h, Daily and Weekly agreement; current state is {alignment}.", "alignment": alignment, "timeframe_states": stripped}); continue
                    direction = "BULLISH" if "BULLISH" in alignment else "BEARISH"
                    candidate = {"key": f"screener:{ticker}", "kind": "stock", "ticker": ticker, "name": ticker, "symbol": symbol, "direction": direction, "mtf_alignment": alignment,
                                 "data_quality": "READY", "price": prices.get(ticker), "timeframe_states": stripped}
                    opportunity = build_equity_opportunity(candidate, {"minimum_reward_to_risk": 2.0})
                    if opportunity.get("status") == "EXCLUDED":
                        rows.append({"symbol": ticker, "decision": "REJECT", "reason": opportunity.get("reason"), "alignment": alignment, "timeframe_states": stripped}); continue
                    stop = (opportunity.get("recommended_invalidation") or {}).get("price")
                    entry = opportunity.get("entry")
                    target = entry + 2 * (entry - stop) if direction == "BULLISH" and entry and stop else entry - 2 * (stop - entry) if entry and stop else None
                    opportunity["target"] = round(target, 2) if target else None
                    conviction = evidence_conviction(candidate, opportunity)
                    rows.append({"symbol": ticker, "decision": "PASS", "reason": opportunity.get("thesis"), "alignment": alignment, "direction": direction,
                                 "entry": entry, "stop": stop, "target": opportunity.get("target"), "reward_to_risk": 2.0, "conviction": conviction, "timeframe_states": stripped})
                except Exception as error:
                    rows.append({"symbol": ticker, "decision": "REJECT", "reason": str(error), "alignment": "UNAVAILABLE", "timeframe_states": {}})
        rank = {"PASS": 0, "WATCHLIST": 1, "REJECT": 2}
        rows.sort(key=lambda row: (rank[row["decision"]], -(row.get("conviction") or {}).get("score", 0), row["symbol"]))
        result = {"status": "READY", "offset": offset, "limit": limit, "total": len(symbols), "analyzed": len(page), "has_more": offset + len(page) < len(symbols), "results": rows,
                  "operational_limits": {"maximum_symbols": 61, "batch_size": 12, "cache_seconds": 300, "background_polling": False},
                  "safeguards": "Decision support only. No candidate selection, packet, ticket, order, or broker mutation is created."}
        screener_analysis_cache[cache_key] = (time_module.monotonic(), result)
        return result

    def analyze_screener_options(payload):
        """Build bounded, defined-risk option spreads for prequalified screener equities."""
        candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
        candidates = candidates[:12]
        if not candidates:
            raise ValueError("Complete the equity analysis before requesting stock-option spreads.")
        session = market_session()
        if session.get("status") != "OPEN":
            return {"status": "MARKET_CLOSED", "plans": [], "excluded": [],
                    "message": "Fresh stock-option screening is available only during the live NSE session."}
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            raise RuntimeError("FYERS authentication is required for fresh stock-option screening.")
        app_id, access_token = token.split(":", 1)
        client = fyersModel.FyersModel(client_id=app_id, token=access_token)
        plans, excluded = [], []
        for item in candidates:
            ticker = str(item.get("symbol") or "").strip().upper()
            direction = str(item.get("direction") or "").upper()
            stop = item.get("stop")
            if not ticker or direction not in {"BULLISH", "BEARISH"} or not isinstance(stop, (int, float)):
                excluded.append({"symbol": ticker or "Unknown", "reason": "The equity signal lacks a valid direction or structural stop."})
                continue
            underlying = f"NSE:{ticker}-EQ"
            risk = {"planning_capital": 100000, "max_loss_value": 2000, "max_loss_unit": "rupees",
                    "invalidation": stop, "stop_basis": "price", "max_simultaneous_positions": 3,
                    "minimum_reward_to_risk": 2.0}
            try:
                chain, expiry = fetch_fyers_chain(client, underlying)
                symbols = [row.get("symbol") for row in chain.get("data", {}).get("optionsChain", []) if row.get("symbol")]
                options = build_defined_risk_spreads(chain, expiry, fyers_fo_master.lookup(symbols), direction, risk)
                ready = []
                candidate = {"direction": direction, "data_quality": "READY", "timeframe_states": item.get("timeframe_states") or {}}
                for proposal in options.get("proposals") or []:
                    sizing = proposal.get("sizing") or {}
                    grade = evidence_conviction(candidate, item, proposal)
                    if sizing.get("status") == "SIZED" and sizing.get("lots") and grade.get("rating") == "High":
                        ready.append((proposal, grade))
                if not ready:
                    excluded.append({"symbol": ticker, "reason": join_unique_reasons(options.get("rejected_proposals") or []) or "No defined-risk spread passed sizing, liquidity and evidence gates."})
                    continue
                proposal, grade = max(ready, key=lambda pair: (pair[0].get("reward_to_risk") or 0, -(pair[0].get("max_loss_per_lot") or float("inf"))))
                plans.append({"symbol": ticker, "underlying": underlying, "direction": direction,
                              "alignment": item.get("alignment"), "timeframe_states": item.get("timeframe_states") or {},
                              "expiry": options.get("expiry"), "spot": options.get("spot"),
                              "proposal": proposal, "conviction": grade, "decision_support_only": True})
            except Exception as error:
                excluded.append({"symbol": ticker, "reason": str(error)})
        return {"status": "READY", "plans": plans, "excluded": excluded,
                "message": f"{len(plans)} defined-risk stock-option spread(s) passed fresh FYERS validation."}

    def analysis_packet(payload):
        recipient, action, selected_keys, include_funds = validate_handoff_request(payload)
        route = instrument_route(payload)
        policy = validate_risk_policy(payload.get("risk_policy"))
        mode = payload.get("mode") if payload.get("mode") in {"intraday", "swing"} else "intraday"
        collection = alignment_candidates(mode)
        by_key = {candidate["key"]: candidate for candidate in collection["candidates"]}
        missing = [key for key in selected_keys if key not in by_key]
        if missing:
            raise ValueError("One or more selected candidates no longer has full alignment. Collect candidates again.")
        wrong_route = [key for key in selected_keys if by_key[key].get("kind") != "stock"]
        if wrong_route:
            raise ValueError("The selected instrument route supports fully aligned cash stocks only; collect matches again.")
        account = {"included": False, "reason": "Current funds were not requested and confirmed for this local packet."}
        current_funds = None
        if include_funds:
            refreshed_account = account_summary()
            if not refreshed_account.get("connected") or refreshed_account.get("available_funds") is None:
                raise RuntimeError(refreshed_account.get("error") or "Fresh FYERS funds are unavailable.")
            current_funds = refreshed_account["available_funds"]
            account = {
                "included": True,
                "broker": "FYERS (read-only account snapshot)",
                "available_funds": current_funds,
                "refreshed_at": datetime.now().astimezone().isoformat(),
                "confirmation": "User explicitly confirmed inclusion for this local packet.",
            }
        risks = payload.get("risk_inputs") if isinstance(payload.get("risk_inputs"), dict) else {}
        candidates = []
        for key in selected_keys:
            candidate = by_key[key]
            submitted_risk = risks.get(key) if isinstance(risks.get(key), dict) else {}
            submitted_invalidation = submitted_risk.get("invalidation")
            if candidate.get("kind") == "stock" and not isinstance(submitted_invalidation, (int, float)):
                derived_plan = build_equity_opportunity(candidate, policy)
                derived = (derived_plan.get("recommended_invalidation") or {}).get("price")
                if not isinstance(derived, (int, float)) or derived <= 0:
                    raise ValueError(
                        f"{candidate.get('name') or key}: completed-candle structure did not produce a valid stop/invalidation; collect fresh evidence."
                    )
                submitted_risk = {
                    **submitted_risk,
                    "invalidation": derived,
                    "stop_basis": "price",
                    "invalidation_source": "AUTO_COMPLETED_CANDLE_STRUCTURE",
                    "invalidation_rationale": (derived_plan.get("recommended_invalidation") or {}).get("rationale"),
                }
            risk = {
                **submitted_risk,
                "planning_capital": policy["planning_capital"],
                "max_loss_value": policy["idea_risk_limit"],
                "max_loss_unit": "rupees",
                "daily_loss_limit": policy["daily_loss_limit"],
                "protected_daily_buffer": policy["risk_reserve"],
                "max_simultaneous_positions": policy["max_simultaneous_positions"],
                "minimum_reward_to_risk": policy["minimum_reward_to_risk"],
                "stop_basis": submitted_risk.get("stop_basis", policy["stop_basis"]),
                "order_type": policy["order_type"],
            }
            item = {**candidate, "risk_input": risk}
            item["instrument_route"] = route
            if route == "cash_equity":
                item["equity_sizing"] = size_equity_candidate(candidate, risk, current_funds)
            else:
                item["options"] = {"status": "REQUESTED", "proposals": []}
            if route == "stock_options":
                try:
                    token = load_config().get("FYERS_ACCESS_TOKEN", "")
                    if not token or ":" not in token:
                        raise RuntimeError("FYERS authentication is required for current option-chain analysis.")
                    app_id, access_token = token.split(":", 1)
                    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
                    chain, expiry = fetch_fyers_chain(client, candidate["symbol"])
                    symbols = [row.get("symbol") for row in chain.get("data", {}).get("optionsChain", []) if row.get("symbol")]
                    master_records = fyers_fo_master.lookup(symbols)
                    item["options"] = build_defined_risk_spreads(chain, expiry, master_records, candidate["direction"], risk)
                except Exception as error:
                    item["options"] = {"status": "UNAVAILABLE", "reason": str(error), "proposals": []}
            candidates.append(item)
        return {
            "schema": "sector-pulse-analysis-handoff/v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "recipient": recipient,
            "instrument_route": route,
            "requested_action": action,
            "delivery": {
                "transmitted": False,
                "channel": "LOCAL_PREVIEW" if action == "preview" else "LOCAL_EXPORT",
                "statement": "Sector Pulse does not send this packet to ChatGPT, Codex, a broker, or any external recipient.",
            },
            "prompt": packet_prompt(recipient),
            "source": {
                "market_data_broker": "FYERS_READ_ONLY",
                "analysis_mode": mode,
                "instrument_route": route,
                "analysis_updated_at": collection.get("updated_at"),
                "market_session": collection.get("market_session"),
                "candidate_scope": collection.get("scope"),
            },
            "risk_policy": {
                **policy,
                "hard_max_daily_loss": 5000,
                "sizing_rule": "No quantity without explicit max loss and stop/invalidation; trade preview also applies the daily realized-plus-open-risk ledger and fresh broker capital/margin.",
            },
            "account": account,
            "candidates": candidates,
            "order_authority": "NONE — this packet cannot authorize or trigger an order.",
        }

    def analysis_opportunities(payload):
        """Analyze fresh full-alignment candidates without creating order authority."""
        recipient = str(payload.get("recipient") or "").lower()
        if recipient not in {"chatgpt", "codex"}:
            raise ValueError("Choose ChatGPT or Codex before collecting AI analysis.")
        policy = validate_risk_policy(payload.get("risk_policy"))
        route = instrument_route(payload)
        mode = payload.get("mode") if payload.get("mode") in {"intraday", "swing"} else "intraday"
        collection = alignment_candidates(mode)
        candidates = [candidate for candidate in collection.get("candidates", []) if candidate.get("kind") == "stock"]
        cards, exclusions = [], []
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            raise RuntimeError("FYERS authentication is required to exclude already-open positions from Analysis Handoff.")
        app_id, access_token = token.split(":", 1)
        client = fyersModel.FyersModel(client_id=app_id, token=access_token)
        positions_response = client.positions()
        if not isinstance(positions_response, dict) or positions_response.get("s") != "ok":
            raise RuntimeError("FYERS positions are unavailable; Analysis Handoff will not show possible duplicate exposure.")
        position_exposures = open_position_underlyings(
            positions_response.get("netPositions") or (positions_response.get("data") or {}).get("netPositions") or []
        )
        duplicate_candidates = [candidate for candidate in candidates if candidate_has_open_position(candidate, position_exposures)]
        candidates = [candidate for candidate in candidates if not candidate_has_open_position(candidate, position_exposures)]
        exclusions.extend({
            "candidate_key": candidate["key"], "name": candidate.get("name"), "kind": "OPEN_POSITION",
            "reason": "An open FYERS position already exists for this underlying; duplicate exposure is excluded.",
        } for candidate in duplicate_candidates)
        level_plans = {}
        for candidate in candidates:
            plan = build_equity_opportunity(candidate, policy)
            level_plans[candidate["key"]] = plan
            recommended = plan.get("recommended_invalidation") or {}
            if isinstance(recommended.get("price"), (int, float)) and recommended["price"] > 0:
                candidate["derived_invalidation"] = {
                    "status": "READY", "method": recommended.get("method", "structure"),
                    "price": recommended["price"], "basis": "Exact price from completed-candle structure",
                    "rationale": recommended.get("rationale"),
                }
            else:
                candidate["derived_invalidation"] = {
                    "status": "UNAVAILABLE",
                    "reason": plan.get("reason") or "Completed-candle structure did not produce a valid directional invalidation.",
                }
            if route == "cash_equity":
                if plan.get("status") == "REQUIRES_INVALIDATION":
                    try:
                        proposed = apply_invalidation_choice(candidate, plan, policy, {"method": "structure"})
                        plan["proposed_sizing"] = proposed
                        plan["target"] = proposed["target"]
                        plan["quantity"] = proposed["quantity"]
                        plan["estimated_max_loss"] = proposed["estimated_max_loss"]
                        plan["estimated_notional"] = proposed["estimated_notional"]
                    except ValueError as error:
                        plan["proposal_warning"] = str(error)
                    plan["conviction"] = evidence_conviction(candidate, plan)
                    cards.append({"candidate_key": candidate["key"], "candidate": candidate, "analysis": plan})
                else:
                    exclusions.append({"candidate_key": candidate["key"], "name": candidate.get("name"), "kind": "EQUITY", "reason": plan.get("reason")})

        if route == "stock_options":
            if not token or ":" not in token:
                exclusions.append({"kind": "OPTIONS", "reason": "FYERS authentication is required for fresh option analysis."})
            else:
                option_candidates = list(candidates)
                option_candidates.sort(key=lambda item: (item.get("kind") != "sector", -abs(float(item.get("official_contribution_pp") or 0))))
                option_scan_limit = 12
                for omitted in option_candidates[option_scan_limit:]:
                    exclusions.append({"candidate_key": omitted["key"], "name": omitted.get("name"), "kind": "OPTIONS", "reason": "Option refresh deferred by the bounded FYERS request budget; no contract was inferred."})
                for candidate in option_candidates[:option_scan_limit]:
                    plan = level_plans.get(candidate["key"], {})
                    invalidation = (plan.get("recommended_invalidation") or {}).get("price")
                    if not isinstance(invalidation, (int, float)) or invalidation <= 0:
                        exclusions.append({
                            "candidate_key": candidate["key"], "name": candidate.get("name"), "kind": "OPTIONS",
                            "reason": "Completed-candle structure did not produce a valid underlying invalidation; option construction was blocked.",
                        })
                        continue
                    risk = {
                        "planning_capital": policy["planning_capital"], "max_loss_value": policy["idea_risk_limit"],
                        "max_loss_unit": "rupees", "invalidation": invalidation, "stop_basis": "price",
                        "max_simultaneous_positions": policy["max_simultaneous_positions"],
                        "minimum_reward_to_risk": policy["minimum_reward_to_risk"],
                    }
                    try:
                        chain, expiry = fetch_fyers_chain(client, candidate["symbol"])
                        symbols = [row.get("symbol") for row in chain.get("data", {}).get("optionsChain", []) if row.get("symbol")]
                        options = build_defined_risk_spreads(chain, expiry, fyers_fo_master.lookup(symbols), candidate["direction"], risk)
                        ready = []
                        for proposal in options.get("proposals") or []:
                            sizing = proposal.get("sizing") or {}
                            if sizing.get("status") != "SIZED" or not sizing.get("lots"):
                                exclusions.append({"candidate_key": candidate["key"], "name": candidate.get("name"), "kind": "OPTIONS", "reason": "A validated spread exists but the configured risk/capital does not support one lot."})
                                continue
                            target_profit_per_lot = min(proposal["max_profit_per_lot"], proposal["max_loss_per_lot"] * policy["minimum_reward_to_risk"])
                            target_points = proposal["entry_points"] + target_profit_per_lot / proposal["lot_size"] if proposal["structure"] == "DEBIT" else max(0, proposal["entry_points"] - target_profit_per_lot / proposal["lot_size"])
                            ready.append({
                                **proposal,
                                "underlying": candidate["symbol"], "expiry": options.get("expiry"), "expiry_iso": options.get("expiry_iso"),
                                "spot": options.get("spot"), "target_exit_points": round(target_points, 2),
                                "underlying_invalidation": invalidation,
                                "exit_conditions": [
                                    f"Exit if the underlying reaches invalidation ₹{invalidation:.2f}." if invalidation else "No valid underlying invalidation; do not trade.",
                                    f"Target spread value {target_points:.2f} points while preserving at least 1:{policy['minimum_reward_to_risk']} planned reward:risk.",
                                    "Exit/stand aside if any leg quote, liquidity, Greeks/OI/volume, expiry, or completed-candle alignment becomes stale or invalid.",
                                ],
                                "liquidity_evidence": {"rules": options.get("liquidity_rules"), "legs": [{"symbol": leg.get("symbol"), "bid": leg.get("bid"), "ask": leg.get("ask"), "spread_pct": leg.get("spread_pct"), "open_interest": leg.get("open_interest"), "volume": leg.get("volume"), "greeks": leg.get("greeks"), "lot_size": leg.get("lot_size"), "tick_size": leg.get("tick_size")} for leg in proposal.get("legs", [])]},
                                "decision_support_only": True,
                            })
                        if ready:
                            proposal = max(ready, key=lambda item: (item.get("reward_to_risk") or 0, -(item.get("max_loss_per_lot") or float("inf"))))
                            option_analysis = {
                                "status": "REQUIRES_INVALIDATION_ACCEPTANCE", "kind": "OPTION_SPREAD", "direction": candidate["direction"],
                                "entry": options.get("spot"), "invalidation_choices": plan.get("invalidation_choices"),
                                "recommended_invalidation": plan.get("recommended_invalidation"), "active_invalidation": None,
                                "thesis": plan.get("thesis"), "entry_trigger": plan.get("entry_trigger"), "proposal": proposal,
                            }
                            option_analysis["conviction"] = evidence_conviction(candidate, option_analysis, proposal)
                            cards.append({"candidate_key": candidate["key"], "candidate": candidate, "analysis": option_analysis})
                        if not ready:
                            reason = join_unique_reasons(options.get("rejected_proposals") or [])
                            exclusions.append({"candidate_key": candidate["key"], "name": candidate.get("name"), "kind": "OPTIONS", "reason": reason or options.get("reason") or "No exact defined-risk spread passed the configured gates."})
                    except Exception as error:
                        exclusions.append({"candidate_key": candidate["key"], "name": candidate.get("name"), "kind": "OPTIONS", "reason": str(error)})
        analysis_id = secrets.token_urlsafe(12)
        for index, card in enumerate(cards):
            card["card_id"] = f"card-{index + 1}"
        result = {
            "schema": "sector-pulse-auto-analysis/v1", "generated_at": datetime.now().astimezone().isoformat(),
            "analysis_id": analysis_id, "status": "READY", "decision_support_only": True, "order_authority": "NONE",
            "analysis_recipient": recipient,
            "instrument_route": route,
            "ai_review": {
                "status": "UNAVAILABLE", "recipient": recipient, "transmitted": False,
                "message": f"{recipient.title()} is not connected to this local dashboard. The cards below are transparent rule-engine proposals, not {recipient.title()} output.",
                "recommendation_source": "LOCAL_EVIDENCE_RULE_ENGINE",
            },
            "risk_policy": policy, "source": {"broker": "FYERS", "mode": mode, "analysis_updated_at": collection.get("updated_at"), "market_session": collection.get("market_session")},
            "scope": {**(collection.get("scope") or {}), "option_scan_limit": 12},
            "candidates": candidates, "cards": cards, "exclusions": exclusions,
        }
        analysis_runs[analysis_id] = {"created_at": datetime.now().timestamp(), "cards": {card["card_id"]: card for card in cards}, "policy": policy}
        for old_id, run in list(analysis_runs.items()):
            if datetime.now().timestamp() - run["created_at"] > 900:
                analysis_runs.pop(old_id, None)
        return result

    def size_analysis_opportunity(payload):
        """Accept/edit one proposed stop and recompute dependent values from a fresh FYERS quote."""
        run = analysis_runs.get(str(payload.get("analysis_id") or ""))
        if not run:
            raise ValueError("This analysis expired. Collect fresh matches again.")
        card = run["cards"].get(str(payload.get("card_id") or ""))
        if not card:
            raise ValueError("The selected analysis card is no longer available.")
        candidate, opportunity = card["candidate"], card["analysis"]
        policy = validate_risk_policy(payload.get("risk_policy"))
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            raise RuntimeError("FYERS authentication is required to accept a proposal and size it from a fresh quote.")
        app_id, access_token = token.split(":", 1)
        client = fyersModel.FyersModel(client_id=app_id, token=access_token)
        quote_response = client.quotes({"symbols": candidate["symbol"]})
        if not isinstance(quote_response, dict) or quote_response.get("s") != "ok" or not quote_response.get("d"):
            raise RuntimeError("FYERS did not return a fresh quote for the selected underlying.")
        quote_values = (quote_response["d"][0].get("v") or {})
        fresh_price = quote_values.get("lp")
        if not isinstance(fresh_price, (int, float)) or fresh_price <= 0:
            raise RuntimeError("FYERS returned an invalid current price for the selected underlying.")
        refreshed = {**opportunity, "entry": float(fresh_price), "current_price": float(fresh_price)}
        if opportunity.get("kind") == "OPTION_SPREAD":
            option_proposal = opportunity.get("proposal")
            tick_size = 0.05
        else:
            master = fyers_cm_master.lookup([candidate["symbol"]]).get(candidate["symbol"])
            if not master:
                raise RuntimeError("The exact equity contract is absent from today's FYERS cash-market master.")
            tick_size = master["tick_size"]
            option_proposal = None
        sizing = apply_invalidation_choice(candidate, refreshed, policy, payload.get("selection"), tick_size=tick_size, option_proposal=option_proposal)
        return {
            "analysis_id": payload.get("analysis_id"), "card_id": payload.get("card_id"), "status": "ACCEPTED_AND_SIZED",
            "fresh_quote": {"symbol": candidate["symbol"], "price": fresh_price, "provider_timestamp": quote_values.get("tt")},
            "active_invalidation": sizing, "ticket_confirmation_invalidated": True,
            "message": "Stop selection accepted and recomputed from fresh FYERS evidence. Any earlier ticket preview or confirmation is invalid.",
        }

    class Handler(SimpleHTTPRequestHandler):
        def end_headers(self):
            if not self.path.split("?", 1)[0].startswith("/api/"):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_json(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/ema-band/master-status":
                self.send_json(200, ema_master_status()); return
            if path == "/api/ema-band/master-search":
                try:
                    query = (parse_qs(urlparse(self.path).query).get("q") or [""])[0]
                    segment = (parse_qs(urlparse(self.path).query).get("segment") or [""])[0]
                    self.send_json(200, search_ema_master(query, segment))
                except Exception as error:
                    self.send_json(409, {"error": str(error), "status": ema_master_status()})
                return
            if path == "/api/ema-band/underlying-search":
                try:
                    query = (parse_qs(urlparse(self.path).query).get("q") or [""])[0]
                    self.send_json(200, search_ema_option_underlyings(query))
                except Exception as error:
                    self.send_json(409, {"error": str(error), "status": ema_master_status()})
                return
            if path == "/api/ema-band/atm-option":
                try:
                    query = parse_qs(urlparse(self.path).query)
                    self.send_json(200, resolve_ema_atm_option((query.get("underlying") or [""])[0], (query.get("timeframe") or ["5 minutes"])[0], (query.get("ema_length") or ["21"])[0], (query.get("mode") or ["PAPER"])[0]))
                except Exception as error:
                    self.send_json(409, {"error": str(error), "status": ema_master_status()})
                return
            if path == "/api/ema-band/mode-capability":
                try:
                    mode = (parse_qs(urlparse(self.path).query).get("mode") or ["PAPER"])[0]
                    self.send_json(200, ema_band_mode_capability(mode))
                except Exception as error:
                    self.send_json(409, {"error": str(error)})
                return
            if path == "/api/ema-band/runner":
                self.send_json(200, ema_runner_snapshot())
                return
            if path == "/api/ema-band/chart":
                try:
                    runner = ema_runner_snapshot()
                    config = runner.get("config") or {}
                    query = parse_qs(urlparse(self.path).query)
                    symbol = str((query.get("symbol") or [config.get("underlying") or ""])[0]).upper()
                    if not symbol:
                        # Keep the broker chart reviewable after the runner is
                        # stopped; execution logs retain the last validated
                        # underlying but do not imply that a runner is active.
                        for entry in ema_execution_log(100):
                            candidate = str(entry.get("underlying") or "").upper()
                            if candidate:
                                symbol = candidate
                                break
                    timeframe = str((query.get("timeframe") or [config.get("timeframe") or "5 minutes"])[0])
                    ema_length = int((query.get("ema_length") or [config.get("ema_length") or 21])[0])
                    token = load_config().get("FYERS_ACCESS_TOKEN", "")
                    if not symbol or ":" not in token:
                        raise RuntimeError("Start the EMA runner or select a FYERS instrument before loading its broker chart.")
                    app_id, access_token = token.split(":", 1)
                    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
                    self.send_json(200, ema_band_chart_snapshot(client, symbol, timeframe, ema_length))
                except Exception as error:
                    self.send_json(409, {"error": str(error)})
                return
            if path == "/api/ema-band/execution-log":
                try:
                    limit = int((parse_qs(urlparse(self.path).query).get("limit") or ["200"])[0])
                except ValueError:
                    limit = 200
                self.send_json(200, {"entries": ema_execution_log(max(1, min(limit, 1000)))})
                return
            if path == "/api/auth/start":
                try:
                    oauth_state = secrets.token_urlsafe(24)
                    url = authorization_url(expected_port=port, state=oauth_state)
                    state["oauth_state"] = oauth_state
                    state["renewing"] = True
                    state["auth_error"] = "Complete Fyers login and 2FA in the browser. If FYERS shows 'We couldn't connect', click Try Now once."
                    self.send_json(200, {"url": url})
                except Exception as error:
                    state["renewing"] = False
                    state["auth_error"] = str(error)
                    self.send_json(500, {"error": str(error)})
                return
            if path == "/callback":
                callback_query = parse_qs(urlparse(self.path).query)
                code = (callback_query.get("auth_code") or [None])[0]
                returned_state = (callback_query.get("state") or [None])[0]
                if not code:
                    self.send_error(400, "Fyers did not return an authorization code"); return
                if not state.get("oauth_state") or not secrets.compare_digest(str(returned_state or ""), state["oauth_state"]):
                    state["renewing"] = False
                    self.send_error(400, "Fyers returned an invalid OAuth state"); return
                try:
                    exchange_auth_code(code)
                except Exception as error:
                    state["renewing"] = False
                    self.send_error(502, str(error)); return
                state.pop("oauth_state", None)
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(b'<meta http-equiv="refresh" content="2;url=/"><h2>Fyers authorization received.</h2><p>The dashboard is reconnecting.</p>')
                def restart_server():
                    import sys, time
                    time.sleep(0.25)
                    print("Token renewed; restarting the live heat-map feed.")
                    os.execv(sys.executable, [sys.executable, str(ROOT / "heatmap_server.py")])
                from threading import Thread
                Thread(target=restart_server, daemon=True, name="fyers-server-restart").start()
                return
            if path == "/api/realized-pnl":
                try:
                    period = (parse_qs(urlparse(self.path).query).get("period") or ["annual"])[0]
                    if period not in {"annual", "monthly", "weekly", "daily"}: period = "annual"
                    self.send_json(200, realized_pnl(period))
                except Exception as error:
                    self.send_json(502, {"error": str(error), "supported": False})
                return
            if path == "/api/account":
                try:
                    body = json.dumps(account_summary()).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception as error:
                    self.send_json(502, {"error": str(error)})
                return
            if path == "/api/live-pnl":
                self.send_json(200, read_live_pnl_snapshot())
                return
            if path == "/api/sensex-straddle":
                self.send_json(200, sensex_straddle.snapshot())
                return
            if path == "/api/nifty-straddle":
                self.send_json(200, nifty_straddle.snapshot())
                return
            if path == "/api/analysis-handoff/candidates":
                try:
                    mode = (parse_qs(urlparse(self.path).query).get("mode") or ["intraday"])[0]
                    self.send_json(200, alignment_candidates(mode))
                except Exception as error:
                    self.send_json(502, {"error": str(error)})
                return
            if path == "/api/trade-ticket/capabilities":
                self.send_json(200, fyers_execution.capabilities())
                return
            if path == "/api/automation/profile":
                self.send_json(200, automation_policy.current())
                return
            if path == "/api/sector-analysis":
                mode = (parse_qs(urlparse(self.path).query).get("mode") or ["intraday"])[0]
                self.send_json(200, attach_live_attribution(state["sector_analysis"].snapshot(mode=mode)))
                return
            if path == "/api/sector-analysis/detail":
                query = parse_qs(urlparse(self.path).query)
                mode = (query.get("mode") or ["intraday"])[0]
                sector_id = (query.get("sector") or [""])[0]
                result = state["sector_analysis"].snapshot(mode=mode, sector_id=sector_id)
                if result.get("sector"):
                    live_sector = next((item for item in snapshot().get("sectors", []) if item.get("sector_id") == result["sector"]["sector_id"]), None)
                    if live_sector:
                        result["sector"]["constituent_movers"] = live_sector.get("drivers", [])
                        result["sector"]["top_contributors"] = live_sector.get("top_contributors", [])
                        result["sector"]["attribution"] = live_sector.get("attribution", result["sector"].get("attribution"))
                self.send_json(200 if result.get("sector") else 404, result)
                return
            if path == "/api/heatmap":
                body = json.dumps(snapshot()).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            super().do_GET()

        def read_json(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ValueError("Invalid request length.") from error
            if length <= 0 or length > 1_000_000:
                raise ValueError("A non-empty JSON body under 1 MB is required.")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("Request body must be valid JSON.") from error
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            try:
                payload = self.read_json()
                if path == "/api/ema-band/master-refresh":
                    self.send_json(200, refresh_ema_masters())
                    return
                if path == "/api/ema-band/runner/start":
                    self.send_json(200, start_ema_runner(payload))
                    return
                if path == "/api/ema-band/runner/stop":
                    self.send_json(200, stop_ema_runner())
                    return
                if path == "/api/analysis-handoff/preview":
                    self.send_json(200, analysis_packet(payload))
                    return
                if path == "/api/chartink/refresh":
                    result = fetch_chartink_source(payload.get("url"))
                    if result.get("status") == "READY":
                        result.update(chartink_candidate_sectors(result.get("candidates", []), result.get("source_sectors")))
                        token = load_config().get("FYERS_ACCESS_TOKEN", "")
                        if token and ":" in token:
                            app_id, access_token = token.split(":", 1)
                            client = fyersModel.FyersModel(client_id=app_id, token=access_token)
                            result.update(enrich_chartink_candidates(result.get("candidates", []), client.quotes))
                        else:
                            result.update({"market_data_schema": 1, "market_data": {}, "market_data_as_of": None, "market_data_provider": "FYERS_READ_ONLY", "market_data_available": 0,
                                           "market_data_error": "FYERS is not connected; price enrichment is unavailable."})
                    self.send_json(200, result)
                    return
                if path == "/api/chartink/analyze":
                    self.send_json(200, analyze_screener_candidates(payload))
                    return
                if path == "/api/chartink/analyze-options":
                    self.send_json(200, analyze_screener_options(payload))
                    return
                if path == "/api/analysis-handoff/analyze":
                    self.send_json(200, analysis_opportunities(payload))
                    return
                if path == "/api/analysis-handoff/size":
                    self.send_json(200, size_analysis_opportunity(payload))
                    return
                if path == "/api/trade-ticket/prepare":
                    self.send_json(200, fyers_execution.prepare(payload))
                    return
                if path == "/api/trade-ticket/prepare-batch":
                    self.send_json(200, fyers_execution.prepare_batch(payload))
                    return
                if path == "/api/trade-ticket/submit":
                    try:
                        result = fyers_execution.submit(str(payload.get("preview_id", "")), str(payload.get("confirmation", "")))
                    except PreviewChanged as error:
                        self.send_json(409, {"error": str(error), "replacement_preview": error.preview})
                        return
                    self.send_json(200, result)
                    return
                if path == "/api/trade-ticket/submit-batch":
                    try:
                        result = fyers_execution.submit_batch(str(payload.get("preview_id", "")), str(payload.get("confirmation", "")))
                    except PreviewChanged as error:
                        self.send_json(409, {"error": str(error), "replacement_preview": error.preview})
                        return
                    self.send_json(200, result)
                    return
                if path == "/api/automation/profile/preview":
                    self.send_json(200, automation_policy.preview(payload))
                    return
                if path == "/api/automation/profile/draft":
                    self.send_json(200, automation_policy.save_draft(payload))
                    return
                if path == "/api/automation/profile/save":
                    self.send_json(200, automation_policy.save(str(payload.get("preview_id", "")), str(payload.get("acknowledgement", ""))))
                    return
                if path in {"/api/sensex-straddle/start", "/api/sensex-straddle/start-paper"}:
                    if path.endswith("start-paper"):
                        payload = {"mode": "paper", "exit_mode": "supertrend"}
                    self.send_json(200, sensex_straddle.start(
                        mode=payload.get("mode", "live"),
                        exit_mode=payload.get("exit_mode", "supertrend"),
                        lots=payload.get("lots", 1),
                        entry_start=payload.get("entry_start", "09:15"),
                        entry_end=payload.get("entry_end", "11:30"),
                        confirmation=payload.get("confirmation", ""),
                    ))
                    return
                if path == "/api/sensex-straddle/stop":
                    self.send_json(200, sensex_straddle.stop())
                    return
                if path == "/api/nifty-straddle/start":
                    self.send_json(200, nifty_straddle.start(
                        mode=payload.get("mode", "live"),
                        lots=payload.get("lots", 1),
                        stoploss=payload.get("stoploss", 15),
                        target=payload.get("target", 30),
                        exit_mode=payload.get("exit_mode", "supertrend"),
                        entry_start=payload.get("entry_start", "09:15"),
                        entry_end=payload.get("entry_end", "11:30"),
                        confirmation=payload.get("confirmation", ""),
                    ))
                    return
                if path == "/api/nifty-straddle/stop":
                    self.send_json(200, nifty_straddle.stop())
                    return
                if path == "/api/straddle-squareoff/prepare":
                    self.send_json(200, straddle_squareoff.prepare(payload.get("runner")))
                    return
                if path == "/api/straddle-squareoff/submit":
                    self.send_json(200, straddle_squareoff.submit(
                        str(payload.get("preview_id", "")),
                        str(payload.get("confirmation", "")),
                    ))
                    return
                self.send_json(404, {"error": "Unknown API endpoint."})
            except PermissionError as error:
                self.send_json(403, {"error": str(error)})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            except Exception as error:
                self.send_json(502, {"error": str(error)})
        def log_message(self, *args): pass
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Sector heat map: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSector heat map stopped cleanly. Restart with ./setup_and_run.sh when ready.")
    finally:
        active_analysis = state.get("sector_analysis")
        if active_analysis:
            active_analysis.running = False
        active_feed = state.get("feed")
        if active_feed:
            active_feed.stop()
        sensex_straddle.stop()
        nifty_straddle.stop()
        server.server_close()
