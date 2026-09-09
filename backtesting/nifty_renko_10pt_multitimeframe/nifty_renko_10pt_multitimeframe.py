"""Read-only NIFTY 10-point fixed-brick Renko reversal research across timeframes."""
import importlib.util
import json
from datetime import datetime
from pathlib import Path

from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_renko_reversal_multitimeframe" / "nifty_renko_reversal_multitimeframe.py"
spec = importlib.util.spec_from_file_location("renko_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

base.BRICK_SIZE = 10.0
base.INITIAL_STOP_POINTS = 20.0
base.TRAIL_ACTIVATION_POINTS = 20.0
base.TRAIL_POINTS = 10.0


def main() -> None:
    app_id, token = base.base.load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client, now = fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(base.base.IST)
    results = {}
    for timeframe in base.base.TIMEFRAMES:
        frame = base.base.fetch_history(client, now, timeframe)
        results[f"{timeframe}m"] = {"completed_bars": len(frame), "windows": [base.evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps({"strategy": "Fixed 10-point Renko two-brick reversal with delayed one-brick trail", "rules": "build intraday fixed 10-point Renko bricks from completed raw-candle closes; enter after two same-direction bricks; use a 20-point two-brick initial stop; after a 20-point favorable move, trail by 10 points; exit on opposite two-brick reversal or 15:20 session exit; costs 0.06% plus Rs 40 per completed trade", "data_source": "FYERS completed NIFTY 50 index candles", "results": results}, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
