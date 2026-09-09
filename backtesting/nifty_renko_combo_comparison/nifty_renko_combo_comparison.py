"""Read-only, bounded Renko combination comparison across three NIFTY timeframes."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fyers_apiv3 import fyersModel

BASE_PATH = Path(__file__).resolve().parents[1] / "nifty_vwap_pullback_multitimeframe" / "nifty_vwap_pullback_multitimeframe.py"
spec = importlib.util.spec_from_file_location("data_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

BRICK, HARD_STOP, TRAIL_START, TRAIL = 30.0, 60.0, 60.0, 30.0


def kama(close):
    change = (close - close.shift(10)).abs()
    efficiency = (change / close.diff().abs().rolling(10).sum().replace(0, float("nan"))).fillna(0)
    smooth = (efficiency * (2 / 3 - 2 / 31) + 2 / 31) ** 2
    result = pd.Series(index=close.index, dtype=float)
    result.iloc[10] = close.iloc[10]
    for index in range(11, len(close)):
        result.iloc[index] = result.iloc[index - 1] + smooth.iloc[index] * (close.iloc[index] - result.iloc[index - 1])
    return result


def prepare(frame):
    frame = frame.copy()
    typical = (frame.high + frame.low + frame.close) / 3
    frame["vwap"] = (typical * frame.volume).groupby(frame.session).cumsum() / frame.volume.groupby(frame.session).cumsum()
    frame["kama"] = kama(frame.close)
    return frame


def run(frame, mode):
    records = []
    for session, bars in frame.groupby("session", sort=True):
        bars = bars.reset_index(drop=True); anchor = bars.iloc[0].open; directions = []
        side = entry = None; highwater = lowwater = None; trail_active = False
        for i in range(1, len(bars) - 1):
            bar, nxt = bars.iloc[i], bars.iloc[i + 1].open; move = bar.close - anchor; fresh = []
            while move >= BRICK: anchor += BRICK; move -= BRICK; fresh.append(1)
            while move <= -BRICK: anchor -= BRICK; move += BRICK; fresh.append(-1)
            directions = (directions + fresh)[-2:]
            signal = directions[0] if len(directions) == 2 and directions[0] == directions[1] else 0
            h, m = bar.timestamp.hour, bar.timestamp.minute
            vwap_ok = (signal == 1 and bar.close > bar.vwap) or (signal == -1 and bar.close < bar.vwap)
            prior_kama = bars.iloc[i - 1].kama
            kama_ok = pd.notna(bar.kama) and ((signal == 1 and bar.close > bar.kama and bar.kama > prior_kama) or (signal == -1 and bar.close < bar.kama and bar.kama < prior_kama))
            allowed = mode == "Renko" or (mode == "Renko+VWAP" and vwap_ok) or (mode == "Renko+KAMA" and kama_ok) or (mode == "Renko+VWAP+KAMA" and vwap_ok and kama_ok)
            end = (h, m) >= (15, 15)
            if side is None:
                if fresh and signal and allowed and (h, m) >= (9, 30) and (h, m) < (14, 45):
                    side, entry, highwater, lowwater = ("long" if signal == 1 else "short"), nxt, nxt, nxt
                continue
            hard = entry - HARD_STOP if side == "long" else entry + HARD_STOP
            trail = highwater - TRAIL if side == "long" else lowwater + TRAIL
            hit_hard = bar.low <= hard if side == "long" else bar.high >= hard
            hit_trail = trail_active and (bar.low <= trail if side == "long" else bar.high >= trail)
            opposite = (side == "long" and signal == -1) or (side == "short" and signal == 1)
            if hit_hard or hit_trail or opposite or end:
                exit_price = hard if hit_hard else trail if hit_trail else nxt
                gross = exit_price / entry - 1 if side == "long" else entry / exit_price - 1
                records.append({"date": session, "return": gross - base.COST_RATE - base.FIXED_COST / entry})
                side = entry = None; trail_active = False
            else:
                highwater, lowwater = max(highwater, bar.high), min(lowwater, bar.low)
                trail_active = trail_active or (highwater - entry >= TRAIL_START if side == "long" else entry - lowwater >= TRAIL_START)
        if side is not None:
            last = bars.iloc[-1]; gross = last.close / entry - 1 if side == "long" else entry / last.close - 1
            records.append({"date": session, "return": gross - base.COST_RATE - base.FIXED_COST / entry})
    return records


def metrics(records):
    equity = peak = 1.0; drawdown = 0.0
    for row in records:
        equity *= 1 + row["return"]; peak = max(peak, equity); drawdown = min(drawdown, equity / peak - 1)
    return {"trades": len(records), "win_rate_pct": round(100 * sum(row["return"] > 0 for row in records) / len(records), 2) if records else None, "net_return_pct": round(100 * (equity - 1), 3), "max_drawdown_pct": round(100 * drawdown, 3)}


def main():
    app, token = base.load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client, now = fyersModel.FyersModel(client_id=app, token=token), datetime.now(base.IST)
    modes = ("Renko", "Renko+VWAP", "Renko+KAMA", "Renko+VWAP+KAMA")
    output = []
    for tf in base.TIMEFRAMES:
        frame = prepare(base.fetch_history(client, now, tf))
        oos_start = frame.timestamp.max().date() - timedelta(days=183)
        for mode in modes:
            trades = run(frame, mode)
            output.append({"timeframe": f"{tf}m", "combination": mode, "one_year": metrics(trades), "final_six_months_oos": metrics([row for row in trades if row["date"] >= oos_start])})
    print(json.dumps({"base": "fixed 30-point Renko two-brick reversal", "controls": "same 60-point hard stop, delayed 30-point trail, next-bar fills, session exit and costs for every combination", "results": output}, indent=2))


if __name__ == "__main__": main()
