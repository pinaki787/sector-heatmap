"""Read-only NIFTY index proxy, daily multi-day trend-pullback continuation research."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

IST = ZoneInfo("Asia/Kolkata")
SYMBOL = "NSE:NIFTY50-INDEX"
FAST_EMA, SLOW_EMA, ATR_PERIOD = 20, 50, 14
STOP_ATR_MULTIPLE, REWARD_RISK, MAX_HOLD_DAYS = 1.5, 2.0, 10
COST_RATE, FIXED_COST = 0.0006, 40


def fetch_daily(client: fyersModel.FyersModel, now: datetime) -> pd.DataFrame:
    rows, cursor, end = [], now.date() - timedelta(days=730), now.date()
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=365), end)
        response = client.history({"symbol": SYMBOL, "resolution": "D", "date_format": 1,
                                   "range_from": cursor.isoformat(), "range_to": chunk_end.isoformat(), "cont_flag": 1})
        if response.get("s") != "ok":
            raise RuntimeError(response.get("message") or "daily history unavailable")
        rows.extend(response["candles"])
        cursor = chunk_end + timedelta(days=1)
    frame = pd.DataFrame(rows, columns=["epoch", "open", "high", "low", "close", "volume"]).drop_duplicates("epoch").sort_values("epoch").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["epoch"], unit="s", utc=True).dt.tz_convert(IST).dt.date
    frame["ema20"] = frame["close"].ewm(span=FAST_EMA, adjust=False, min_periods=FAST_EMA).mean()
    frame["ema50"] = frame["close"].ewm(span=SLOW_EMA, adjust=False, min_periods=SLOW_EMA).mean()
    previous_close = frame["close"].shift(1)
    frame["atr"] = pd.concat([frame["high"] - frame["low"], (frame["high"] - previous_close).abs(), (frame["low"] - previous_close).abs()], axis=1).max(axis=1).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean()
    return frame


def simulate(frame: pd.DataFrame) -> list[dict]:
    trades, position = [], None
    for index in range(1, len(frame) - 1):
        bar, next_bar = frame.iloc[index], frame.iloc[index + 1]
        if position is None:
            bullish = bar["ema20"] > bar["ema50"] and bar["close"] > bar["ema50"]
            bearish = bar["ema20"] < bar["ema50"] and bar["close"] < bar["ema50"]
            long_signal = bullish and bar["low"] <= bar["ema20"] and bar["close"] > bar["ema20"]
            short_signal = bearish and bar["high"] >= bar["ema20"] and bar["close"] < bar["ema20"]
            if (long_signal or short_signal) and pd.notna(bar["atr"]):
                side, entry = ("long" if long_signal else "short"), next_bar["open"]
                risk = STOP_ATR_MULTIPLE * bar["atr"]
                position = {"side": side, "entry": entry, "entry_date": next_bar["date"], "stop": entry - risk if side == "long" else entry + risk,
                            "target": entry + REWARD_RISK * risk if side == "long" else entry - REWARD_RISK * risk, "bars": 0}
            continue
        position["bars"] += 1
        hit_stop = bar["low"] <= position["stop"] if position["side"] == "long" else bar["high"] >= position["stop"]
        hit_target = bar["high"] >= position["target"] if position["side"] == "long" else bar["low"] <= position["target"]
        final_bar = index == len(frame) - 2
        if hit_stop or hit_target or position["bars"] >= MAX_HOLD_DAYS or final_bar:
            exit_price = position["stop"] if hit_stop else position["target"] if hit_target else bar["close"]
            gross = exit_price / position["entry"] - 1 if position["side"] == "long" else position["entry"] / exit_price - 1
            trades.append({"entry_date": position["entry_date"], "exit_date": bar["date"], "side": position["side"], "return": gross - COST_RATE - FIXED_COST / position["entry"],
                           "exit": "stop" if hit_stop else "target" if hit_target else "time"})
            position = None
    return trades


def metrics(trades: list[dict]) -> dict:
    equity = peak = 1.0
    max_drawdown = 0.0
    for trade in trades:
        equity *= 1 + trade["return"]
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
    return {"closed_trades": len(trades), "wins": sum(trade["return"] > 0 for trade in trades),
            "win_rate_pct": round(100 * sum(trade["return"] > 0 for trade in trades) / len(trades), 2) if trades else None,
            "net_return_pct": round(100 * (equity - 1), 3), "max_drawdown_pct": round(100 * max_drawdown, 3),
            "long_trades": sum(trade["side"] == "long" for trade in trades), "short_trades": sum(trade["side"] == "short" for trade in trades),
            "exits": {kind: sum(trade["exit"] == kind for trade in trades) for kind in ("stop", "target", "time")}}


def main() -> None:
    app_id, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    frame = fetch_daily(fyersModel.FyersModel(client_id=app_id, token=token), datetime.now(IST))
    trades = simulate(frame)
    out_sample_start = frame["date"].max() - timedelta(days=183)
    result = {"strategy": "Daily trend-pullback continuation on the NIFTY index proxy", "proxy_notice": "NIFTY index price is used because FYERS did not provide a valid two-year continuous NIFTY futures series.",
              "rules": "EMA20 above/below EMA50 and close on the same side of EMA50 define trend; pullback touches EMA20 and closes back through it; enter following daily open; 1.5 ATR stop, 2R target, maximum 10 sessions; costs 0.06% plus Rs 40 per completed trade.",
              "data_coverage": {"first_date": str(frame["date"].min()), "last_date": str(frame["date"].max()), "daily_bars": len(frame)},
              "two_year": metrics(trades), "out_of_sample_final_six_months": metrics([trade for trade in trades if trade["entry_date"] >= out_sample_start])}
    print(json.dumps(result, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value)))


if __name__ == "__main__":
    main()
