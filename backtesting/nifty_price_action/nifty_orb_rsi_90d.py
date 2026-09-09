"""Read-only NIFTY ORB plus RSI(14) research using FYERS completed 5-minute candles."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

SYMBOL = "NSE:NIFTY50-INDEX"
STOP = 0.005
TARGET = 0.01
RSI_PERIOD = 14
LONG_RSI_MIN = 55
SHORT_RSI_MAX = 45
COST_RATE = 0.0006
FIXED_COST = 40


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def main() -> None:
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=token)
    now = datetime.now().astimezone()
    response = client.history({
        "symbol": SYMBOL, "resolution": "5", "date_format": 1,
        "range_from": (now - timedelta(days=90)).date().isoformat(),
        "range_to": now.date().isoformat(), "cont_flag": 1,
    })
    if response.get("s") != "ok":
        raise RuntimeError(response.get("message") or "history unavailable")
    rows = [row for row in response["candles"] if row[0] + 300 <= now.timestamp()]
    frame = pd.DataFrame(rows, columns=["epoch", "open", "high", "low", "close", "volume"])
    frame["rsi"] = rsi(frame["close"], RSI_PERIOD)
    rows = frame.to_dict("records")
    days = {}
    for row in rows:
        days.setdefault(datetime.fromtimestamp(row["epoch"]).astimezone().date(), []).append(row)

    returns, reasons = [], []
    for bars in days.values():
        if len(bars) < 6:
            continue
        opening = bars[:3]
        orb_high = max(bar["high"] for bar in opening)
        orb_low = min(bar["low"] for bar in opening)
        side = entry = None
        for index in range(3, len(bars) - 1):
            bar, next_open = bars[index], bars[index + 1]["open"]
            timestamp = datetime.fromtimestamp(bar["epoch"]).astimezone()
            if side is None:
                if bar["close"] > orb_high and bar["rsi"] > LONG_RSI_MIN:
                    side, entry = "long", next_open
                elif bar["close"] < orb_low and bar["rsi"] < SHORT_RSI_MAX:
                    side, entry = "short", next_open
                continue
            stop = entry * (1 - STOP) if side == "long" else entry * (1 + STOP)
            target = entry * (1 + TARGET) if side == "long" else entry * (1 - TARGET)
            hit_stop = bar["low"] <= stop if side == "long" else bar["high"] >= stop
            hit_target = bar["high"] >= target if side == "long" else bar["low"] <= target
            session_end = timestamp.hour == 15 and timestamp.minute >= 15
            if hit_stop or hit_target or session_end:
                exit_price = stop if hit_stop else target if hit_target else next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - COST_RATE - FIXED_COST / entry)
                reasons.append("stop" if hit_stop else "target" if hit_target else "session")
                side = entry = None
                break

    equity = peak = 1.0
    drawdown = 0.0
    for trade_return in returns:
        equity *= 1 + trade_return
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    print(json.dumps({
        "lookback_days": 90, "completed_5m_bars": len(rows), "closed_trades": len(returns),
        "wins": sum(value > 0 for value in returns),
        "win_rate_pct": round(sum(value > 0 for value in returns) / len(returns) * 100, 2) if returns else None,
        "net_return_pct": round((equity - 1) * 100, 3), "max_drawdown_pct": round(drawdown * 100, 3),
        "exits": {reason: reasons.count(reason) for reason in set(reasons)},
        "definition": "first 15-minute range; long close break only if RSI(14)>55, short close break only if RSI(14)<45; next-open fill; 0.5% stop, 1% target, 15:20 exit",
    }, indent=2))


if __name__ == "__main__":
    main()
