#!/usr/bin/env python3
"""Walk-forward search for volatility-expansion entries on SENSEX straddles."""

from __future__ import annotations

import argparse
import datetime as dt
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import dhan_rolling_options_backtest as engine


RV_RISE_BARS = (1, 3, 6)
BREAKOUT_BARS = (1, 3, 6)
IV_PERCENTILES = (50.0, 70.0, None)
TIME_STOP_MINUTES = 45


def metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "net": 0.0, "pf": np.nan, "dd": 0.0, "win_rate": np.nan}
    pnl = trades["net_pnl_rupees"]
    losses = pnl[pnl <= 0]
    pf = pnl[pnl > 0].sum() / -losses.sum() if losses.sum() < 0 else np.inf
    equity = engine.INITIAL_CAPITAL + pnl.cumsum()
    dd = (equity / equity.cummax() - 1).min() * 100
    return {
        "trades": len(trades), "net": pnl.sum(), "pf": pf, "dd": dd,
        "win_rate": (pnl > 0).mean() * 100,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--token-cache", type=Path, default=engine.DEFAULT_TOKEN_CACHE)
    parser.add_argument("--output", type=Path, default=engine.SCRIPT_DIR / "entry_filter_optimization.csv")
    args = parser.parse_args()

    start = pd.Timestamp(args.from_date, tz="Asia/Kolkata")
    end = pd.Timestamp(args.to_date, tz="Asia/Kolkata")
    split = start + (end - start) * (2 / 3)
    client_id, access_token = engine.load_credentials(args.token_cache)
    with requests.Session() as session:
        surface = engine.fetch_surface(
            session, client_id, access_token, start - pd.Timedelta(days=35), end
        )

    rows = []
    journal_dir = engine.SCRIPT_DIR / "entry_filter_trades"
    journal_dir.mkdir(exist_ok=True)
    for rv_bars, breakout, iv_pct in product(
        RV_RISE_BARS, BREAKOUT_BARS, IV_PERCENTILES
    ):
        trades, _ = engine.simulate(
            surface, start, cost_per_trade=100.0, slippage_points_per_leg=0.5,
            atr_stop_multiplier=1.25, cooldown_after_stop=True,
            rv_rise_bars=rv_bars, iv_percentile=iv_pct,
            premium_breakout_bars=breakout,
            entry_start_time=dt.time(9, 25), entry_end_time=dt.time(13, 30),
            time_stop_minutes=TIME_STOP_MINUTES,
        )
        iv_label = "none" if iv_pct is None else f"{iv_pct:g}"
        label = f"rv{rv_bars}_bo{breakout}_iv{iv_label}_ts{TIME_STOP_MINUTES}"
        trades.to_csv(journal_dir / f"{label}.csv", index=False)
        overall = metrics(trades)
        if trades.empty:
            ins = metrics(trades)
            oos = metrics(trades)
        else:
            ins = metrics(trades[trades["entry_time"] < split])
            oos = metrics(trades[trades["entry_time"] >= split])
        rows.append({
            "configuration": label, "rv_rise_bars": rv_bars,
            "breakout_bars": breakout, "iv_percentile": iv_pct,
            "time_stop_minutes": TIME_STOP_MINUTES,
            "trades": overall["trades"], "net_pnl_rupees": overall["net"],
            "profit_factor": overall["pf"], "max_drawdown_pct": overall["dd"],
            "win_rate_pct": overall["win_rate"],
            "in_sample_trades": ins["trades"], "in_sample_net_pnl": ins["net"],
            "in_sample_profit_factor": ins["pf"],
            "out_sample_trades": oos["trades"], "out_sample_net_pnl": oos["net"],
            "out_sample_profit_factor": oos["pf"], "out_sample_max_drawdown_pct": oos["dd"],
        })

    frame = pd.DataFrame(rows)
    eligible = frame["in_sample_trades"] >= 20
    frame["selection_rank"] = np.nan
    frame.loc[eligible, "selection_rank"] = (
        frame.loc[eligible, "in_sample_net_pnl"].rank(ascending=False, method="min")
        + frame.loc[eligible, "in_sample_profit_factor"].rank(ascending=False, method="min")
        + frame.loc[eligible, "max_drawdown_pct"].rank(ascending=False, method="min")
    )
    frame = frame.sort_values(
        ["selection_rank", "in_sample_net_pnl", "net_pnl_rupees"],
        ascending=[True, False, False], na_position="last",
    )
    frame.to_csv(args.output, index=False)
    print(frame.head(15).to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
    print(f"Chronological split: in-sample before {split.date()}, out-of-sample from {split.date()}")
    print(f"Results CSV: {args.output}")
    print(f"Trade journals: {journal_dir}")


if __name__ == "__main__":
    main()
