"""Compare candle or ordered Renko OHLC exports from Sector Pulse and TradingView."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from zoneinfo import ZoneInfo

FIELDS = ("open", "high", "low", "close")


def timestamp(value, zone, fractional=False):
    if fractional:
        try:
            numeric = Decimal(value)
        except InvalidOperation:
            pass
        else:
            if not numeric.is_finite():
                raise ValueError("Timestamp must be finite.")
            return numeric
    try:
        return int(value)
    except ValueError:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        if parsed.microsecond:
            if fractional:
                return Decimal(str(parsed.timestamp()))
            raise ValueError("Expected a whole-second candle timestamp.")
        return int(parsed.timestamp())


def read_bars(path, zone, date, studies=(), renko=False):
    rows = {}
    previous_time = previous_brick = None
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        headers = {name.strip().lower(): name for name in reader.fieldnames or []}
        clock = headers.get("source_time_utc") or headers.get("time")
        if not clock or any(field not in headers for field in FIELDS):
            raise ValueError(f"{path.name} needs a time column and OHLC columns.")
        for study in studies:
            if (reader.fieldnames or []).count(study) != 1:
                raise ValueError(f"{path.name} needs exactly one column named {study!r}.")
        for row in reader:
            brick = (row.get(headers.get("brick_index")) or "").strip()
            if brick and not renko:
                raise ValueError("This comparison requires regular candles. Renko needs ordered brick comparison.")
            try:
                key = timestamp((row.get(clock) or "").strip(), zone, fractional=renko)
                if date and datetime.fromtimestamp(float(key), zone).date().isoformat() != date:
                    continue
                if (row.get(headers.get("provisional")) or "").strip() == "1":
                    continue
                values = tuple(Decimal(row[headers[field]]) for field in FIELDS)
                if not all(value.is_finite() for value in values):
                    raise ValueError("Prices must be finite.")
                if renko:
                    if previous_time is not None and key < previous_time:
                        raise ValueError("Renko export must be in chronological order.")
                    previous_time = key
                    if brick:
                        brick_number = int(brick)
                        if brick_number < 1 or (previous_brick is not None and brick_number != previous_brick + 1):
                            raise ValueError("Sector Pulse brick indexes must be consecutive and increasing.")
                        previous_brick = brick_number
                elif key in rows:
                    raise ValueError("Duplicate candle timestamp.")
                readings = []
                for study in studies:
                    raw = (row.get(study) or "").strip()
                    value = Decimal(raw) if raw else None
                    if value is not None and not value.is_finite():
                        raise ValueError(f"Study {study!r} must be finite or blank.")
                    readings.append(value)
                rows[len(rows) if renko else key] = values + tuple(readings)
            except (ValueError, TypeError, InvalidOperation, OverflowError, OSError) as error:
                raise ValueError(f"{path.name}:{reader.line_num}: {error}") from error
    return rows


def utc(time):
    return datetime.fromtimestamp(time, timezone.utc).isoformat()


def compare(sector, tradingview, tolerance):
    overlap = sorted(sector.keys() & tradingview.keys())
    sector_only = sorted(sector.keys() - tradingview.keys())
    tradingview_only = sorted(tradingview.keys() - sector.keys())
    counts = dict.fromkeys(FIELDS, 0)
    maxima = dict.fromkeys(FIELDS, Decimal(0))
    mismatches = []
    mismatch_count = 0
    for time in overlap:
        differences = {}
        for field, actual, reference in zip(FIELDS, sector[time], tradingview[time]):
            delta = abs(actual - reference)
            maxima[field] = max(maxima[field], delta)
            if delta > tolerance:
                counts[field] += 1
                differences[field] = {"sector_pulse": str(actual), "tradingview": str(reference)}
        if differences:
            mismatch_count += 1
            if len(mismatches) < 10:
                mismatches.append({"time_utc": utc(time), "fields": differences})
    return {
        "matched_timestamps": len(overlap),
        "matching_bars": len(overlap) - mismatch_count,
        "sector_pulse_only": len(sector_only),
        "tradingview_only": len(tradingview_only),
        "sector_pulse_only_examples": [utc(time) for time in sector_only[:10]],
        "tradingview_only_examples": [utc(time) for time in tradingview_only[:10]],
        "mismatched_bars": mismatch_count,
        "field_mismatches": counts,
        "max_abs_difference": {field: str(value) if overlap else None for field, value in maxima.items()},
        "mismatch_examples": mismatches,
        "pass": bool(overlap) and not (sector_only or tradingview_only or mismatch_count),
    }


def compare_renko(sector, tradingview, tolerance):
    shared = min(len(sector), len(tradingview))
    first = None
    matching_prefix = 0
    positional_matches = 0
    for index in range(shared):
        left, right = sector[index], tradingview[index]
        if all(abs(actual - reference) <= tolerance for actual, reference in zip(left, right)):
            positional_matches += 1
            if first is None:
                matching_prefix += 1
        elif first is None:
            first = {"position": index + 1,
                     "sector_pulse": dict(zip(FIELDS, map(str, left))),
                     "tradingview": dict(zip(FIELDS, map(str, right)))}
    if first is None and len(sector) != len(tradingview):
        first = {"position": shared + 1,
                 "sector_pulse": dict(zip(FIELDS, map(str, sector[shared]))) if shared in sector else None,
                 "tradingview": dict(zip(FIELDS, map(str, tradingview[shared]))) if shared in tradingview else None}
    return {"mode": "ordered_renko", "sector_pulse_bricks": len(sector), "tradingview_bricks": len(tradingview),
            "matching_prefix": matching_prefix, "positional_matches": positional_matches,
            "first_divergence": first, "pass": bool(shared) and first is None}


def compare_studies(sector, tradingview, mappings, tolerance):
    common = sorted(sector.keys() & tradingview.keys())
    reports = []
    for index, (sector_column, tradingview_column) in enumerate(mappings, start=len(FIELDS)):
        compared = missing = mismatched = shared_blanks = 0
        maximum = None
        examples = []
        for time in common:
            actual, reference = sector[time][index], tradingview[time][index]
            if actual is None and reference is None:
                shared_blanks += 1
                continue
            if actual is None or reference is None:
                missing += 1
            else:
                compared += 1
                difference = abs(actual - reference)
                maximum = difference if maximum is None else max(maximum, difference)
                if difference <= tolerance:
                    continue
                mismatched += 1
            if len(examples) < 10:
                examples.append({"time_utc": utc(time), "sector_pulse": str(actual) if actual is not None else None,
                                 "tradingview": str(reference) if reference is not None else None})
        reports.append({"sector_pulse_column": sector_column, "tradingview_column": tradingview_column,
                        "compared_values": compared, "shared_blanks": shared_blanks,
                        "one_sided_blanks": missing, "mismatched_values": mismatched,
                        "max_abs_difference": None if maximum is None else str(maximum),
                        "examples": examples, "pass": bool(compared) and not (missing or mismatched)})
    return reports


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("sector_pulse", type=Path)
    cli.add_argument("tradingview", type=Path)
    cli.add_argument("--date", help="Compare only this local session date (YYYY-MM-DD).")
    cli.add_argument("--timezone", default="Asia/Kolkata", help="Timezone for session dates and timestamps without offsets.")
    cli.add_argument("--tolerance", type=Decimal, default=Decimal("0.01"))
    cli.add_argument("--study", nargs=2, action="append", default=[], metavar=("SECTOR_COLUMN", "TV_COLUMN"),
                     help="Compare these exact indicator column names. Repeat for multiple plots.")
    cli.add_argument("--renko", action="store_true", help="Compare OHLC by brick position. Match starting brick and settings before exporting.")
    cli.add_argument("--renko-start", nargs=2, type=int, metavar=("SECTOR_ROW", "TV_ROW"),
                     help="Start at these 1-based brick positions after date and provisional filtering.")
    args = cli.parse_args()
    if args.renko_start and (not args.renko or min(args.renko_start) < 1):
        cli.error("--renko-start requires --renko and two positive brick positions.")
    if args.renko and args.study:
        cli.error("Study comparison is available for regular candles.")
    if not args.tolerance.is_finite() or args.tolerance < 0:
        cli.error("Tolerance must be finite and non-negative.")
    try:
        if args.date and datetime.strptime(args.date, "%Y-%m-%d").date().isoformat() != args.date:
            raise ValueError("Use YYYY-MM-DD for the comparison date.")
        zone = ZoneInfo(args.timezone)
        sector = read_bars(args.sector_pulse, zone, args.date, [left for left, _ in args.study], args.renko)
        tradingview = read_bars(args.tradingview, zone, args.date, [right for _, right in args.study], args.renko)
        if args.renko_start:
            left, right = args.renko_start
            if left > len(sector) or right > len(tradingview):
                raise ValueError("A Renko start position exceeds the number of retained bricks.")
            sector = dict(enumerate(list(sector.values())[left - 1:]))
            tradingview = dict(enumerate(list(tradingview.values())[right - 1:]))
        comparator = compare_renko if args.renko else compare
        result = comparator(sector, tradingview, args.tolerance)
        if args.renko_start:
            result["start_positions"] = {"sector_pulse": left, "tradingview": right}
        if args.study:
            result["ohlc_pass"] = result["pass"]
            result["studies"] = compare_studies(sector, tradingview, args.study, args.tolerance)
            result["pass"] = result["ohlc_pass"] and all(study["pass"] for study in result["studies"])
    except (OSError, ValueError, KeyError) as error:
        cli.error(str(error))
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
