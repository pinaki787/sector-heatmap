"""NSE capital-market trading sessions used to interpret data freshness."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")
REGULAR_OPEN = time(9, 15)
REGULAR_CLOSE = time(15, 30)

# NSE Capital Market holidays published for calendar year 2026. Weekend entries
# are intentionally omitted because they are handled by ``weekday`` below.
NSE_CM_HOLIDAYS = {
    date(2026, 1, 15): "Municipal Corporation Election - Maharashtra",
    date(2026, 1, 26): "Republic Day",
    date(2026, 3, 3): "Holi",
    date(2026, 3, 26): "Shri Ram Navami",
    date(2026, 3, 31): "Shri Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday",
    date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2026, 5, 1): "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id",
    date(2026, 6, 26): "Muharram",
    date(2026, 9, 14): "Ganesh Chaturthi",
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra",
    date(2026, 11, 10): "Diwali-Balipratipada",
    date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2026, 12, 25): "Christmas",
}

# NSE declared a full normal Capital Market session for the Union Budget.
NSE_SPECIAL_SESSIONS = {
    date(2026, 2, 1): (REGULAR_OPEN, REGULAR_CLOSE, "Union Budget live trading session"),
}


def _as_ist(moment):
    if moment is None:
        return datetime.now(IST)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=IST)
    return moment.astimezone(IST)


def is_trading_day(day):
    return day in NSE_SPECIAL_SESSIONS or (day.weekday() < 5 and day not in NSE_CM_HOLIDAYS)


def previous_trading_day(day):
    candidate = day
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_trading_day(day):
    candidate = day
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def market_session(moment=None):
    """Return the regular NSE equity-session state for a point in time."""
    current = _as_ist(moment)
    day = current.date()
    special = NSE_SPECIAL_SESSIONS.get(day)
    open_at, close_at = special[:2] if special else (REGULAR_OPEN, REGULAR_CLOSE)
    opens = datetime.combine(day, open_at, IST)
    closes = datetime.combine(day, close_at, IST)
    trading_day = is_trading_day(day)
    is_open = trading_day and opens <= current < closes

    if is_open:
        reason = special[2] if special else "Regular trading session"
        last_session = previous_trading_day(day - timedelta(days=1))
        next_open = opens
    elif trading_day and current < opens:
        reason = "Pre-open / before regular session"
        last_session = previous_trading_day(day - timedelta(days=1))
        next_open = opens
    elif trading_day:
        reason = "Regular session completed"
        last_session = day
        next_day = next_trading_day(day + timedelta(days=1))
        next_open = datetime.combine(next_day, NSE_SPECIAL_SESSIONS.get(next_day, (REGULAR_OPEN,))[0], IST)
    else:
        reason = NSE_CM_HOLIDAYS.get(day, "Weekend")
        last_session = previous_trading_day(day - timedelta(days=1))
        next_day = next_trading_day(day + timedelta(days=1))
        next_open = datetime.combine(next_day, NSE_SPECIAL_SESSIONS.get(next_day, (REGULAR_OPEN,))[0], IST)

    last_close_at = NSE_SPECIAL_SESSIONS.get(last_session, (REGULAR_OPEN, REGULAR_CLOSE))[1]
    last_close = datetime.combine(last_session, last_close_at, IST)
    return {
        "status": "OPEN" if is_open else "CLOSED",
        "label": "MARKET OPEN" if is_open else "MARKET CLOSED — last completed session",
        "reason": reason,
        "timezone": "Asia/Kolkata",
        "regular_session": "09:15–15:30 IST",
        "last_completed_session": last_session.isoformat(),
        "last_completed_session_close": last_close.isoformat(),
        "next_open": next_open.isoformat(),
    }
