#!/usr/bin/env python3
"""Compare hard-stop and post-stop cooldown variants on cached Dhan option data."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import dhan_rolling_options_backtest as engine


STOP_VALUES = (15.0, 20.0, 30.0, 40.0, 50.0)


def period_metrics(trades: pd.DataFrame) -> tuple[float, float]:
    if trades.empty:
        return 0.0, np.nan
    pnl = trades["net_pnl_rupees"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    profit_factor = wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf
    return float(pnl.sum()), float(profit_factor)


def summarize(
    trades: pd.DataFrame,
    stop: float | None,
    cooldown: bool,
    split_date: pd.Timestamp,
) -> dict:
    pnl = trades["net_pnl_rupees"]
    equity = engine.INITIAL_CAPITAL + pnl.cumsum()
    drawdown = equity / equity.cummax() - 1
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    profit_factor = wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf
    in_sample = trades[trades["entry_time"] < split_date]
    out_of_sample = trades[trades["entry_time"] >= split_date]
    in_sample_pnl, in_sample_pf = period_metrics(in_sample)
    out_of_sample_pnl, out_of_sample_pf = period_metrics(out_of_sample)
    return {
        "hard_stop_points": "none" if stop is None else stop,
        "cooldown_after_stop": cooldown,
        "trades": len(trades),
        "net_pnl_rupees": pnl.sum(),
        "profit_factor": profit_factor,
        "max_drawdown_pct": drawdown.min() * 100,
        "win_rate_pct": (pnl > 0).mean() * 100,
        "total_costs_rupees": (trades["cost_rupees"] + trades["slippage_rupees"]).sum(),
        "worst_trade_rupees": pnl.min(),
        "stop_exits": int(trades["exit_reason"].eq("stoploss").sum()),
        "in_sample_net_pnl": in_sample_pnl,
        "in_sample_profit_factor": in_sample_pf,
        "out_of_sample_net_pnl": out_of_sample_pnl,
        "out_of_sample_profit_factor": out_of_sample_pf,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--token-cache", type=Path, default=engine.DEFAULT_TOKEN_CACHE)
    parser.add_argument("--cost-per-trade", type=float, default=100.0)
    parser.add_argument("--slippage-points-per-leg", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=engine.SCRIPT_DIR / "hard_stop_optimization.csv")
    args = parser.parse_args()

    client_id, access_token = engine.load_credentials(args.token_cache)
    test_start = pd.Timestamp(args.from_date, tz="Asia/Kolkata")
    test_end = pd.Timestamp(args.to_date, tz="Asia/Kolkata")
    split_date = test_start + (test_end - test_start) * (2 / 3)
    with requests.Session() as session:
        surface = engine.fetch_surface(
            session,
            client_id,
            access_token,
            test_start - pd.Timedelta(days=35),
            test_end,
        )

    configurations = [(None, False)]
    configurations.extend((stop, cooldown) for stop in STOP_VALUES for cooldown in (False, True))
    results = []
    journal_dir = engine.SCRIPT_DIR / "optimization_trades"
    journal_dir.mkdir(exist_ok=True)
    for stop, cooldown in configurations:
        trades, _ = engine.simulate(
            surface,
            test_start,
            cost_per_trade=args.cost_per_trade,
            slippage_points_per_leg=args.slippage_points_per_leg,
            hard_stop_points=stop,
            cooldown_after_stop=cooldown,
        )
        label = "none" if stop is None else f"{stop:g}pt_{'cooldown' if cooldown else 'reentry'}"
        trades.to_csv(journal_dir / f"trades_{label}.csv", index=False)
        results.append(summarize(trades, stop, cooldown, split_date))

    frame = pd.DataFrame(results)
    frame["composite_rank"] = (
        frame["net_pnl_rupees"].rank(ascending=False, method="min")
        + frame["profit_factor"].rank(ascending=False, method="min")
        + frame["max_drawdown_pct"].rank(ascending=False, method="min")
    )
    frame = frame.sort_values(
        ["composite_rank", "net_pnl_rupees", "max_drawdown_pct"],
        ascending=[True, False, False],
    )
    frame.to_csv(args.output, index=False)
    print(frame.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
    print(f"Chronological split: in-sample before {split_date.date()}, out-of-sample from {split_date.date()}")
    print(f"Results CSV: {args.output}")
    print(f"Trade journals: {journal_dir}")


if __name__ == "__main__":
    main()
