#!/usr/bin/env python3
"""Read-only FYERS NIFTY completed 30-minute candle snapshot."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sector_heatmap.config import load_config


def main() -> None:
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist)
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("A current FYERS token is required.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    response = client.history({"symbol": "NSE:NIFTY50-INDEX", "resolution": "30", "date_format": "1", "range_from": now.date().isoformat(), "range_to": now.date().isoformat(), "cont_flag": "1"})
    if response.get("s") != "ok":
        raise RuntimeError(response.get("message") or "FYERS history unavailable")
    # NSE 30-minute bars are anchored at the 09:15 session open, not at wall-clock
    # half-hour boundaries. A bar is complete only after its own 30-minute duration.
    completed = [row for row in response.get("candles") or [] if int(row[0]) + 1800 <= int(now.timestamp())]
    if not completed:
        raise RuntimeError("No completed 30-minute NIFTY candle available.")
    row = completed[-1]
    timestamp = datetime.fromtimestamp(int(row[0]), ist)
    print(f"{timestamp.isoformat()} close={float(row[4]):.2f}")


if __name__ == "__main__":
    main()
