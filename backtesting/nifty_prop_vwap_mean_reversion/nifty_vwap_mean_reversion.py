"""Read-only NIFTY prop-style VWAP mean-reversion research using FYERS 5-minute candles."""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

IST = ZoneInfo("Asia/Kolkata")
SYMBOL = "NSE:NIFTY50-INDEX"
RSI_PERIOD = 14
DEVIATION_BARS = 20
ENTRY_Z = 1.5
LONG_RSI_MAX = 35
SHORT_RSI_MIN = 65
STOP_PCT = 0.006
COST_RATE = 0.0006
FIXED_COST = 40


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    ratio = gains / losses.replace(0, float("nan"))
    return 100 - 100 / (1 + ratio)


def fetch_year(client: fyersModel.FyersModel, now: datetime) -> pd.DataFrame:
    start = now.date() - timedelta(days=365)
    end = now.date()
    collected = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=99), end)
        response = client.history({
            "symbol": SYMBOL, "resolution": "5", "date_format": 1,
            "range_from": cursor.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": 1,
        })
        if response.get("s") != "ok":
            raise RuntimeError(response.get("message") or f"history unavailable for {cursor} to {chunk_end}")
        collected.extend(response["candles"])
        cursor = chunk_end + timedelta(days=1)
    frame = pd.DataFrame(collected, columns=["epoch", "open", "high", "low", "close", "volume"])
    frame = frame.drop_duplicates("epoch").sort_values("epoch")
    frame["timestamp"] = pd.to_datetime(frame["epoch"], unit="s", utc=True).dt.tz_convert(IST)
    frame = frame[frame["epoch"] + 300 <= now.timestamp()].copy()
    frame["session"] = frame["timestamp"].dt.date
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    frame["vwap"] = (typical * frame["volume"]).groupby(frame["session"]).cumsum() / frame["volume"].groupby(frame["session"]).cumsum()
    frame["deviation"] = frame["close"] - frame["vwap"]
    frame["deviation_std"] = frame.groupby("session")["deviation"].transform(lambda values: values.rolling(DEVIATION_BARS, min_periods=DEVIATION_BARS).std())
    frame["rsi"] = rsi(frame["close"], RSI_PERIOD)
    return frame


def evaluate(frame: pd.DataFrame, days: int) -> dict:
    cutoff = frame["timestamp"].max().date() - timedelta(days=days)
    data = frame[frame["session"] >= cutoff]
    returns, exits, sides = [], [], []
    for _, bars in data.groupby("session", sort=True):
        bars = bars.reset_index(drop=True)
        side = entry = None
        for index in range(len(bars) - 1):
            bar, next_open = bars.iloc[index], bars.iloc[index + 1]["open"]
            hour, minute = bar["timestamp"].hour, bar["timestamp"].minute
            if side is None:
                after_opening = (hour, minute) >= (10, 30)
                lower = bar["vwap"] - ENTRY_Z * bar["deviation_std"]
                upper = bar["vwap"] + ENTRY_Z * bar["deviation_std"]
                if after_opening and pd.notna(lower) and bar["close"] < lower and bar["rsi"] < LONG_RSI_MAX:
                    side, entry = "long", next_open
                elif after_opening and pd.notna(upper) and bar["close"] > upper and bar["rsi"] > SHORT_RSI_MIN:
                    side, entry = "short", next_open
                continue
            stop = entry * (1 - STOP_PCT) if side == "long" else entry * (1 + STOP_PCT)
            hit_stop = bar["low"] <= stop if side == "long" else bar["high"] >= stop
            hit_vwap = bar["high"] >= bar["vwap"] if side == "long" else bar["low"] <= bar["vwap"]
            session_end = (hour, minute) >= (15, 15)
            if hit_stop or hit_vwap or session_end:
                exit_price = stop if hit_stop else bar["vwap"] if hit_vwap else next_open
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                returns.append(gross - COST_RATE - FIXED_COST / entry)
                exits.append("stop" if hit_stop else "vwap" if hit_vwap else "session")
                sides.append(side)
                break
    equity = peak = 1.0
    drawdown = 0.0
    for trade_return in returns:
        equity *= 1 + trade_return
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    return {
        "calendar_lookback_days": days, "completed_5m_bars": len(data), "closed_trades": len(returns),
        "wins": sum(value > 0 for value in returns),
        "win_rate_pct": round(sum(value > 0 for value in returns) / len(returns) * 100, 2) if returns else None,
        "net_return_pct": round((equity - 1) * 100, 3), "max_drawdown_pct": round(drawdown * 100, 3),
        "long_trades": sides.count("long"), "short_trades": sides.count("short"),
        "exits": {kind: exits.count(kind) for kind in sorted(set(exits))},
    }


def main() -> None:
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=token)
    frame = fetch_year(client, datetime.now(IST))
    result = {
        "strategy": "VWAP mean reversion after a 1.5-standard-deviation intraday move, with RSI(14) extreme confirmation",
        "rules": "after 10:30 IST, long below session VWAP by 1.5 rolling deviation standard deviations with RSI<35; short above by 1.5 deviations with RSI>65; next-bar-open entry; exit at VWAP, 0.6% stop, or 15:20 IST; one trade per session; costs 0.06% plus Rs 40 per completed trade",
        "data_source": "FYERS completed NIFTY 50 index 5-minute candles",
        "results": [evaluate(frame, days) for days in (7, 30, 90, 365)],
    }
    print(json.dumps(result, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
