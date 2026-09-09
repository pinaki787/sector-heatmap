"""Read-only NIFTY fixed-Renko brick diagnostic from completed 15-minute candles."""
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_vwap_pullback_multitimeframe" / "nifty_vwap_pullback_multitimeframe.py"
spec = importlib.util.spec_from_file_location("data_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def main() -> None:
    app_id, token = base.load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    frame = base.fetch_history(fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(base.IST), "15")
    previous = frame.groupby("session")["close"].shift(1)
    true_range = pd.concat([frame["high"] - frame["low"], (frame["high"] - previous).abs(), (frame["low"] - previous).abs()], axis=1).max(axis=1)
    atr = true_range.groupby(frame["session"]).transform(lambda values: values.rolling(14, min_periods=14).mean()).dropna()
    median = float(atr.median())
    brick = round(median / 10) * 10
    print(json.dumps({"completed_15m_bars": len(frame), "median_15m_atr_points": round(median, 2), "recommended_fixed_brick_points": brick, "selection_rule": "one median completed 15-minute ATR rounded to the nearest 10 points"}, indent=2))


if __name__ == "__main__":
    main()
