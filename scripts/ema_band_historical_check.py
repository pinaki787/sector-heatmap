#!/usr/bin/env python3
"""Read-only reconstruction of an EMA-band decision at an IST timestamp."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sector_heatmap.config import load_config
from sector_heatmap.web import ema_band_entry_checklist, ema_band_strategy_signal

IST = ZoneInfo("Asia/Kolkata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--at", required=True, help="IST timestamp, e.g. 2026-09-09T14:05")
    parser.add_argument("--continuous", action="store_true", help="Use FYERS continuous-futures history for comparison only.")
    args = parser.parse_args()
    target = datetime.fromisoformat(args.at).replace(tzinfo=IST)
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("A current FYERS token is required.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    response = client.history({"symbol": args.symbol, "resolution": "5", "date_format": "1", "range_from": (target - timedelta(days=10)).date().isoformat(), "range_to": target.date().isoformat(), "cont_flag": "1" if args.continuous else "0"})
    if response.get("s") != "ok":
        raise RuntimeError(response.get("message") or "FYERS history unavailable")
    candles = []
    for row in response.get("candles") or []:
        start = datetime.fromtimestamp(int(row[0]), IST)
        if start + timedelta(minutes=5) <= target:
            candles.append({"timestamp": int(row[0]), "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4]), "volume": float(row[5])})
    if len(candles) < 22:
        raise RuntimeError("Insufficient completed candles for EMA 21.")
    signal = ema_band_strategy_signal(candles, 21)
    checklist = ema_band_entry_checklist(candles, 21)
    output = {"symbol": args.symbol, "continuous_history": args.continuous, "at": target.isoformat(), "evaluated_bars": len(candles), "signal": signal, "checklist": checklist, "setup_bar": candles[-2], "confirmation_bar": candles[-1]}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
