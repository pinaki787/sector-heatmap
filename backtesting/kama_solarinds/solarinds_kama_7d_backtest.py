"""Read-only seven-day KAMA research backtest for SOLARINDS underlying.

This does not alter or invoke the live algorithm.  Signals use only completed
five-minute candles and execute at the following candle's open.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config


SYMBOL = "NSE:SOLARINDS-EQ"
RESOLUTION_SECONDS = 5 * 60
KAMA_ER_LENGTH, KAMA_FAST, KAMA_SLOW = 10, 2, 30
FEE_RATE, FIXED_FEE = 0.0003, 20.0  # conservative intraday estimate per order


def kama(values):
    result = [None] * len(values)
    if len(values) <= KAMA_ER_LENGTH:
        return result
    result[KAMA_ER_LENGTH] = values[KAMA_ER_LENGTH]
    fastest = 2 / (KAMA_FAST + 1)
    slowest = 2 / (KAMA_SLOW + 1)
    for index in range(KAMA_ER_LENGTH + 1, len(values)):
        change = abs(values[index] - values[index - KAMA_ER_LENGTH])
        volatility = sum(abs(values[item] - values[item - 1]) for item in range(index - KAMA_ER_LENGTH + 1, index + 1))
        efficiency = change / volatility if volatility else 0.0
        smoothing = (efficiency * (fastest - slowest) + slowest) ** 2
        result[index] = result[index - 1] + smoothing * (values[index] - result[index - 1])
    return result


def main():
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=token)
    now = datetime.now().astimezone()
    raw = client.history({"symbol": SYMBOL, "resolution": "5", "date_format": 1,
                          "range_from": (now - timedelta(days=7)).date().isoformat(),
                          "range_to": now.date().isoformat(), "cont_flag": 1})
    if raw.get("s") != "ok":
        raise RuntimeError(raw.get("message") or "FYERS history unavailable")
    rows = [row for row in raw["candles"] if row[0] + RESOLUTION_SECONDS <= now.timestamp()]
    closes, lines = [row[4] for row in rows], kama([row[4] for row in rows])
    position = None
    trades = []
    for index in range(KAMA_ER_LENGTH + 2, len(rows) - 1):
        current, prior = lines[index], lines[index - 1]
        if current is None or prior is None:
            continue
        signal_time = datetime.fromtimestamp(rows[index][0]).astimezone()
        next_open = rows[index + 1][1]
        is_last_session_bar = signal_time.hour == 15 and signal_time.minute >= 15
        long_signal = closes[index] > current and closes[index - 1] <= prior and current > prior
        exit_signal = closes[index] < current and closes[index - 1] >= prior
        if position is None and long_signal and not is_last_session_bar:
            position = {"entry": next_open, "at": rows[index + 1][0]}
        elif position and (exit_signal or is_last_session_bar):
            gross = (next_open / position["entry"] - 1)
            costs = 2 * FEE_RATE + 2 * FIXED_FEE / position["entry"]
            trades.append({"entry": position["entry"], "exit": next_open, "gross_return_pct": round(gross * 100, 3),
                           "net_return_pct": round((gross - costs) * 100, 3), "exit_reason": "session" if is_last_session_bar else "kama_cross"})
            position = None
    if position:
        trades.append({"entry": position["entry"], "exit": rows[-1][4], "gross_return_pct": round((rows[-1][4] / position["entry"] - 1) * 100, 3),
                       "net_return_pct": None, "exit_reason": "open_mark_to_market"})
    closed = [trade for trade in trades if trade["net_return_pct"] is not None]
    total_net = sum(trade["net_return_pct"] for trade in closed)
    print(json.dumps({"symbol": SYMBOL, "completed_bars": len(rows), "first_bar": rows[0][0], "last_bar": rows[-1][0],
                      "parameters": {"er_length": KAMA_ER_LENGTH, "fast": KAMA_FAST, "slow": KAMA_SLOW},
                      "closed_trades": len(closed), "wins": sum(trade["net_return_pct"] > 0 for trade in closed),
                      "net_return_pct": round(total_net, 3), "trades": trades}, indent=2))


if __name__ == "__main__":
    main()
