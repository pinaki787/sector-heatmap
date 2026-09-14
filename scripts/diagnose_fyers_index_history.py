"""Read-only FYERS history diagnostic for sector-index symbols."""

from datetime import date, timedelta
from pathlib import Path
import sys

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sector_heatmap.config import load_config
from sector_heatmap.sector_service import CandleHistoryProvider


def client():
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise SystemExit("FYERS authentication is unavailable.")
    app_id, access_token = token.split(":", 1)
    return fyersModel.FyersModel(client_id=app_id, token=access_token)


def main():
    today = date.today()
    base = {
        "symbol": "NSE:NIFTYPHARMA-INDEX",
        "resolution": "D",
        "date_format": 1,
        "range_from": (today - timedelta(days=10)).isoformat(),
        "range_to": today.isoformat(),
    }
    api = client()
    for cont_flag in (0, 1):
        response = api.history({**base, "cont_flag": cont_flag})
        print({"cont_flag": cont_flag, "status": response.get("s"), "code": response.get("code"), "message": response.get("message"), "candles": len(response.get("candles") or [])})
    provider = CandleHistoryProvider(api)
    for timeframe in ("15m", "1h", "daily"):
        try:
            candles = provider.get("NSE:NIFTYPHARMA-INDEX", timeframe)
            print({"timeframe": timeframe, "result": "ok", "candles": len(candles)})
        except Exception as error:
            print({"timeframe": timeframe, "result": "error", "error": str(error)})


if __name__ == "__main__":
    main()
