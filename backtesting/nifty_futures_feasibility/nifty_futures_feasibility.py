"""Read-only feasibility gate for NIFTY futures history in FYERS."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

IST = ZoneInfo("Asia/Kolkata")
SYMBOL = "NSE:NIFTY26SEPFUT"
PAST_SYMBOL = "NSE:NIFTY25SEPFUT"


def main() -> None:
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=token)
    now = datetime.now(IST)
    quote = client.quotes({"symbols": SYMBOL})
    history = client.history({
        "symbol": SYMBOL, "resolution": "D", "date_format": 1,
        "range_from": (now.date() - timedelta(days=730)).isoformat(),
        "range_to": now.date().isoformat(), "cont_flag": 1,
    })
    recent_history = client.history({
        "symbol": SYMBOL, "resolution": "D", "date_format": 1,
        "range_from": (now.date() - timedelta(days=30)).isoformat(),
        "range_to": now.date().isoformat(), "cont_flag": 1,
    })
    past_history = client.history({
        "symbol": PAST_SYMBOL, "resolution": "D", "date_format": 1,
        "range_from": "2025-08-01", "range_to": "2025-09-30", "cont_flag": 1,
    })
    candles = history.get("candles", []) if history.get("s") == "ok" else []
    first = datetime.fromtimestamp(candles[0][0], IST).date().isoformat() if candles else None
    last = datetime.fromtimestamp(candles[-1][0], IST).date().isoformat() if candles else None
    print(json.dumps({"symbol": SYMBOL, "quote_status": quote.get("s"), "history_status": history.get("s"),
                      "daily_candles": len(candles), "first_candle": first, "last_candle": last,
                      "history_message": history.get("message"), "recent_history_status": recent_history.get("s"),
                      "recent_daily_candles": len(recent_history.get("candles", [])),
                      "recent_history_message": recent_history.get("message"), "past_symbol": PAST_SYMBOL,
                      "past_history_status": past_history.get("s"), "past_daily_candles": len(past_history.get("candles", [])),
                      "past_history_message": past_history.get("message")}, indent=2))


if __name__ == "__main__":
    main()
