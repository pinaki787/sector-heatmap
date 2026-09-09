"""Read-only FYERS study of NIFTY's 30-point intraday opportunity frequency."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

IST = ZoneInfo("Asia/Kolkata")
SYMBOL, TARGET_POINTS = "NSE:NIFTY50-INDEX", 30.0


def main() -> None:
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client, now = fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(IST)
    rows, cursor, end = [], now.date() - timedelta(days=365), now.date()
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=99), end)
        response = client.history({"symbol": SYMBOL, "resolution": "5", "date_format": 1,
                                   "range_from": cursor.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": 1})
        if response.get("s") != "ok":
            raise RuntimeError(response.get("message") or "history unavailable")
        rows.extend(response["candles"])
        cursor = chunk_end + timedelta(days=1)
    frame = pd.DataFrame(rows, columns=["epoch", "open", "high", "low", "close", "volume"]).drop_duplicates("epoch").sort_values("epoch")
    frame["timestamp"] = pd.to_datetime(frame["epoch"], unit="s", utc=True).dt.tz_convert(IST)
    frame = frame[frame["epoch"] + 300 <= now.timestamp()].copy()
    sessions = []
    for session, bars in frame.groupby(frame["timestamp"].dt.date, sort=True):
        opening = bars.iloc[0]["open"]
        high, low = bars["high"].max(), bars["low"].min()
        sessions.append({"date": session, "range": high - low, "up": high - opening, "down": opening - low})
    summary = pd.DataFrame(sessions)
    print(json.dumps({"target_points": TARGET_POINTS, "sessions": len(summary),
                      "range_at_least_target_pct": round(100 * (summary["range"] >= TARGET_POINTS).mean(), 2),
                      "up_from_open_at_least_target_pct": round(100 * (summary["up"] >= TARGET_POINTS).mean(), 2),
                      "down_from_open_at_least_target_pct": round(100 * (summary["down"] >= TARGET_POINTS).mean(), 2),
                      "either_direction_from_open_at_least_target_pct": round(100 * ((summary["up"] >= TARGET_POINTS) | (summary["down"] >= TARGET_POINTS)).mean(), 2),
                      "median_daily_range_points": round(summary["range"].median(), 2), "average_daily_range_points": round(summary["range"].mean(), 2)}, indent=2))


if __name__ == "__main__":
    main()
