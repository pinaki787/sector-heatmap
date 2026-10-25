"""Read-only dated realised reports. No execution or runner dependencies."""
from datetime import date
from pathlib import Path
import csv
import hashlib
import threading
import time

_CACHE = {}
_LOCK = threading.Lock()
_TYPES = {11: "Index futures", 12: "Volatility futures", 13: "Stock futures", 14: "Index options", 15: "Stock options"}

def report_range(period, today, start=None, end=None):
    floor = today.replace(month=4, day=1) if today.month >= 4 else today.replace(year=today.year-1, month=4, day=1)
    if bool(start) != bool(end):
        raise ValueError("Both from_date and to_date are required.")
    if start:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if not floor <= first <= last <= today:
            raise ValueError("Report dates must be ordered and within the current financial year through today.")
        return first, last
    from datetime import timedelta
    return ({"daily": today, "weekly": max(floor, today-timedelta(days=today.weekday())), "monthly": today.replace(day=1)}.get(period, floor), today)

def master_types(master_dir):
    result = {}
    if not master_dir:
        return result
    for name in ("NSE_FO.csv", "BSE_FO.csv", "NSE_CM.csv", "BSE_CM.csv", "MCX_COM.csv"):
        path = Path(master_dir) / name
        if not path.exists():
            continue
        with path.open(newline="") as handle:
            for row in csv.reader(handle):
                if len(row) > 9:
                    try: result[row[9]] = int(row[2])
                    except ValueError: pass
    return result

def category(row, types):
    segment = str(row.get("segment_name") or "Unclassified")
    exchange = str(row.get("exchange_name") or segment.split("_")[0])
    kind = types.get(row.get("symbol_name"))
    if segment in {"NSE_CASH", "BSE_CASH"}:
        return exchange + (" equity" if kind in (None, 0) else " cash · other instruments")
    if segment in {"NSE_FNO", "BSE_FNO"}:
        return exchange + " · " + _TYPES.get(kind, "Derivatives · type unavailable")
    if exchange == "MCX" or "COM" in segment:
        return exchange + " commodities"
    if "CD" in segment or "CURRENCY" in segment:
        return exchange + " currency derivatives"
    return segment

def range_report(app_id, token, period, today, fetcher, master_dir=None, start=None, end=None):
    first, last = report_range(period, today, start, end)
    key = (hashlib.sha256((app_id+":"+token).encode()).hexdigest(), first, last)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and time.monotonic()-cached[0] < 300:
            return dict(cached[1], period=period)
    raw = fetcher(app_id, token, first, last)
    types = master_types(master_dir)
    records = [{"symbol": r.get("symbol_name", "—"), "segment": r.get("segment_name", "Unclassified"), "exchange": r.get("exchange_name"), "category": category(r, types), "buy_qty": r.get("buy_qty", 0), "buy_rate": r.get("buy_rate", 0), "sell_qty": r.get("sell_qty", 0), "sell_rate": r.get("sell_rate", 0), "pnl": r.get("realized_pnl", 0), "from_date": first.isoformat(), "to_date": last.isoformat()} for r in raw.get("data", [])]
    result = dict(period=period, from_date=first.isoformat(), to_date=last.isoformat(), records=records, summary=raw.get("summary_data", {}), connected=True, supported=raw.get("supported", False), hierarchy_supported=True, broker="FYERS", currency="INR", execution_mode="LIVE", source="realised_pnl_history", message=raw.get("message"))
    with _LOCK:
        if len(_CACHE) > 512: _CACHE.clear()
        _CACHE[key] = (time.monotonic(), result)
    return result
