"""Read-only NIFTY VWAP pullback research with an 8-point profit trail."""
import importlib.util
import json
from datetime import datetime
from pathlib import Path

from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_vwap_pullback_30pt_trail_multitimeframe" / "nifty_vwap_pullback_30pt_trail_multitimeframe.py"
spec = importlib.util.spec_from_file_location("trail_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

# Activation and trailing distance are both 8 points, locking break-even before costs.
base.ACTIVATION_POINTS = 8.0
base.TRAIL_POINTS = 8.0


def main() -> None:
    app_id, token = base.base.load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client, now = fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(base.base.IST)
    results = {}
    for timeframe in base.base.TIMEFRAMES:
        frame = base.base.fetch_history(client, now, timeframe)
        results[f"{timeframe}m"] = {"completed_bars": len(frame), "windows": [base.evaluate(frame, days) for days in (7, 30, 90, 365)]}
    print(json.dumps({"strategy": "Pure VWAP pullback with 8-point profit-trailing exit", "rules": "same pure VWAP pullback entry; initial stop at pullback extreme; after an 8-point favorable move, activate an 8-point trailing stop; 15:20 session exit; one trade per session; costs 0.06% plus Rs 40 per completed trade", "data_source": "FYERS completed NIFTY 50 index candles", "results": results}, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
