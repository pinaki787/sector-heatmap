"""NCDEX trading sessions in minutes from midnight Asia/Kolkata."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# NCDEX 2026 master trading circular, including the January election holiday.
CLOSED_2026 = frozenset(date(2026, month, day) for month, day in (
    (1, 15), (1, 26), (3, 3), (3, 26), (3, 31), (4, 3), (4, 14), (5, 1),
    (5, 28), (6, 26), (9, 14), (10, 2), (10, 20), (11, 10), (11, 24), (12, 25),
))
MUHURAT = date(2026, 11, 8)
MUMBAI_LAUNCH = date(2026, 5, 29)
CHENNAI_LAUNCH = date(2026, 8, 31)
WINTER_HOURS = date(2026, 11, 2)


def trading_bounds(timestamp, underlying):
    """Return the 2026 session applicable to a native contract."""
    day = datetime.fromtimestamp(timestamp, IST).date()
    if day.year != 2026:
        raise ValueError(f"NCDEX holiday calendar requires an update for {day.year}.")

    product = str(underlying).strip().upper()
    if (product == "RAINMUMBAI" and day < MUMBAI_LAUNCH
            or product == "RAINCHNNAI" and day < CHENNAI_LAUNCH):
        return 0, 0
    if day == MUHURAT:
        return 14 * 60 + 20, 15 * 60 + 30
    if day.weekday() >= 5 or day in CLOSED_2026:
        return 0, 0

    # NCDEX/TRADING-021, -038 and -044/2026 govern weather contracts.
    if product == "RAINCHNNAI":
        return 600, 1435 if day >= WINTER_HOURS else 1410
    if product == "RAINMUMBAI" and day < WINTER_HOURS:
        return 600, 1410
    return 600, 1020
