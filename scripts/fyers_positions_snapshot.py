#!/usr/bin/env python3
"""Read-only FYERS positions snapshot; never sends an order."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sector_heatmap.config import load_config


def main() -> None:
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("A current FYERS token is required.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    result = client.positions()
    if result.get("s") != "ok":
        raise RuntimeError(result.get("message") or "FYERS positions unavailable")
    positions = []
    for item in result.get("netPositions") or []:
        symbol = str(item.get("symbol") or "")
        if "NIFTY" in symbol and int(item.get("netQty") or 0):
            positions.append({key: item.get(key) for key in ("symbol", "netQty", "buyAvg", "sellAvg", "ltp", "pl", "productType")})
    print(json.dumps({"nifty_open_positions": positions}, indent=2))


if __name__ == "__main__":
    main()
