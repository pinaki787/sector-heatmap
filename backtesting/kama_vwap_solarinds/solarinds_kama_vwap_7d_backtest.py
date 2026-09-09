"""Read-only seven-day SOLARINDS KAMA plus session-VWAP research backtest."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

SYMBOL = "NSE:SOLARINDS-EQ"
SECONDS = 300
ER_LENGTH, FAST, SLOW = 10, 2, 30
FEE_RATE, FIXED_FEE = 0.0003, 20.0


def kama(values):
    output = [None] * len(values)
    if len(values) <= ER_LENGTH:
        return output
    output[ER_LENGTH] = values[ER_LENGTH]
    fast, slow = 2 / (FAST + 1), 2 / (SLOW + 1)
    for index in range(ER_LENGTH + 1, len(values)):
        change = abs(values[index] - values[index - ER_LENGTH])
        noise = sum(abs(values[item] - values[item - 1]) for item in range(index - ER_LENGTH + 1, index + 1))
        smoothing = ((change / noise if noise else 0) * (fast - slow) + slow) ** 2
        output[index] = output[index - 1] + smoothing * (values[index] - output[index - 1])
    return output


def session_vwap(rows):
    output, day, cumulative_pv, cumulative_volume = [], None, 0.0, 0.0
    for timestamp, _, high, low, close, volume in rows:
        candle_day = datetime.fromtimestamp(timestamp).astimezone().date()
        if candle_day != day:
            day, cumulative_pv, cumulative_volume = candle_day, 0.0, 0.0
        cumulative_pv += ((high + low + close) / 3) * volume
        cumulative_volume += volume
        output.append(cumulative_pv / cumulative_volume if cumulative_volume else close)
    return output


def main():
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    now = datetime.now().astimezone()
    client = fyersModel.FyersModel(client_id=app_id, token=token)
    response = client.history({"symbol": SYMBOL, "resolution": "5", "date_format": 1,
                               "range_from": (now - timedelta(days=7)).date().isoformat(),
                               "range_to": now.date().isoformat(), "cont_flag": 1})
    if response.get("s") != "ok":
        raise RuntimeError(response.get("message") or "FYERS history unavailable")
    rows = [row for row in response["candles"] if row[0] + SECONDS <= now.timestamp()]
    closes, kama_line, vwap = [row[4] for row in rows], kama([row[4] for row in rows]), session_vwap(rows)
    position, trades = None, []
    for index in range(ER_LENGTH + 2, len(rows) - 1):
        current, prior, price = kama_line[index], kama_line[index - 1], closes[index]
        if current is None or prior is None:
            continue
        moment = datetime.fromtimestamp(rows[index][0]).astimezone()
        next_open, last_bar = rows[index + 1][1], moment.hour == 15 and moment.minute >= 15
        entry = price > current and closes[index - 1] <= prior and current > prior and price > vwap[index]
        exit_now = price < current or price < vwap[index] or last_bar
        if position is None and entry and not last_bar:
            position = {"entry": next_open, "at": rows[index + 1][0]}
        elif position and exit_now:
            gross = next_open / position["entry"] - 1
            cost = 2 * FEE_RATE + 2 * FIXED_FEE / position["entry"]
            trades.append({"gross": gross, "net": gross - cost, "reason": "session" if last_bar else "kama_or_vwap"})
            position = None
    closed = trades
    print(json.dumps({"symbol": SYMBOL, "completed_bars": len(rows), "closed_trades": len(closed),
                      "wins": sum(item["net"] > 0 for item in closed), "net_return_pct": round(sum(item["net"] for item in closed) * 100, 3),
                      "parameters": {"kama": "ER 10, fast 2, slow 30", "vwap": "session anchored", "entry": "KAMA cross and close above VWAP", "exit": "close below KAMA or VWAP"}}, indent=2))


if __name__ == "__main__":
    main()
