#!/usr/bin/env python3
"""Read-only FYERS day P&L summary: realised report plus open mark-to-market."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sector_heatmap.config import load_config
from sector_heatmap.web import fetch_realized_pnl_report


def number(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("A current FYERS token is required.")
    app_id, access_token = token.split(":", 1)
    today = datetime.now().date()
    report = fetch_realized_pnl_report(app_id, access_token, today, today)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    positions = client.positions()
    if positions.get("s") != "ok":
        raise RuntimeError(positions.get("message") or "FYERS positions unavailable")
    open_mtm = round(sum(number(row.get("pl")) for row in positions.get("netPositions") or [] if number(row.get("netQty"))), 2)
    records = report.get("data") or []
    realized = round(sum(number(row.get("realized_pnl")) for row in records), 2)
    print(json.dumps({
        "date": today.isoformat(), "realized_pnl": realized, "open_mtm": open_mtm,
        "gross_day_pnl": round(realized + open_mtm, 2),
        "realized_records": len(records),
        "broker_summary": report.get("summary_data") or {},
        "charges_included": False,
    }, indent=2))


if __name__ == "__main__":
    main()
