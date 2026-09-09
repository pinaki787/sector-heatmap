#!/usr/bin/env python3
"""Optimize a combined-premium ATR stop for the SENSEX long straddle."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import dhan_rolling_options_backtest as engine


ATR_MULTIPLIERS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)


def write_sensitivity_chart(frame: pd.DataFrame, output: Path) -> Path | None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return None
    atr = frame[frame["atr_multiplier"].notna()].copy()
    atr["reentry_policy"] = np.where(
        atr["cooldown_after_stop"], "Daily cooldown", "Immediate re-entry"
    )
    metrics = (
        ("net_pnl_rupees", "Net P&L (Rs)"),
        ("profit_factor", "Profit factor"),
        ("max_drawdown_pct", "Max drawdown (%)"),
    )
    figure = make_subplots(rows=1, cols=3, subplot_titles=[title for _, title in metrics])
    policies = ["Daily cooldown", "Immediate re-entry"]
    for column, (metric, _) in enumerate(metrics, start=1):
        pivot = atr.pivot(index="reentry_policy", columns="atr_multiplier", values=metric).reindex(policies)
        figure.add_trace(
            go.Heatmap(
                z=pivot.to_numpy(), x=pivot.columns, y=pivot.index,
                colorscale="RdYlGn", showscale=column == 3,
                text=np.round(pivot.to_numpy(), 2), texttemplate="%{text}",
            ),
            row=1, col=column,
        )
    figure.update_layout(template="plotly_dark", title="SENSEX ATR stop sensitivity")
    chart_path = output.with_name("atr_stop_sensitivity.html")
    figure.write_html(chart_path, include_plotlyjs=True)
    return chart_path


def period_metrics(trades: pd.DataFrame) -> tuple[float, float]:
    if trades.empty:
        return 0.0, np.nan
    pnl = trades["net_pnl_rupees"]
    losses = pnl[pnl <= 0]
    profit_factor = pnl[pnl > 0].sum() / -losses.sum() if losses.sum() < 0 else np.inf
    return float(pnl.sum()), float(profit_factor)


def summarize(
    trades: pd.DataFrame,
    label: str,
    multiplier: float | None,
    cooldown: bool,
    split_date: pd.Timestamp,
) -> dict:
    pnl = trades["net_pnl_rupees"]
    equity = engine.INITIAL_CAPITAL + pnl.cumsum()
    drawdown = equity / equity.cummax() - 1
    _, profit_factor = period_metrics(trades)
    in_sample_pnl, in_sample_pf = period_metrics(trades[trades["entry_time"] < split_date])
    out_sample_pnl, out_sample_pf = period_metrics(trades[trades["entry_time"] >= split_date])
    return {
        "configuration": label,
        "atr_multiplier": multiplier,
        "cooldown_after_stop": cooldown,
        "trades": len(trades),
        "net_pnl_rupees": pnl.sum(),
        "profit_factor": profit_factor,
        "max_drawdown_pct": drawdown.min() * 100,
        "win_rate_pct": (pnl > 0).mean() * 100,
        "total_costs_rupees": (trades["cost_rupees"] + trades["slippage_rupees"]).sum(),
        "worst_trade_rupees": pnl.min(),
        "median_stop_points": trades["stop_distance_points"].median(),
        "stop_exits": int(trades["exit_reason"].eq("stoploss").sum()),
        "in_sample_net_pnl": in_sample_pnl,
        "in_sample_profit_factor": in_sample_pf,
        "out_of_sample_net_pnl": out_sample_pnl,
        "out_of_sample_profit_factor": out_sample_pf,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--token-cache", type=Path, default=engine.DEFAULT_TOKEN_CACHE)
    parser.add_argument("--cost-per-trade", type=float, default=100.0)
    parser.add_argument("--slippage-points-per-leg", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=engine.SCRIPT_DIR / "atr_stop_optimization.csv")
    args = parser.parse_args()

    test_start = pd.Timestamp(args.from_date, tz="Asia/Kolkata")
    test_end = pd.Timestamp(args.to_date, tz="Asia/Kolkata")
    split_date = test_start + (test_end - test_start) * (2 / 3)
    client_id, access_token = engine.load_credentials(args.token_cache)
    with requests.Session() as session:
        surface = engine.fetch_surface(
            session, client_id, access_token,
            test_start - pd.Timedelta(days=35), test_end,
        )

    configurations = [("no_stop", None, False), ("fixed_15_cooldown", None, True)]
    configurations.extend(
        (f"atr_{multiplier:g}_{'cooldown' if cooldown else 'reentry'}", multiplier, cooldown)
        for multiplier in ATR_MULTIPLIERS
        for cooldown in (False, True)
    )
    results = []
    journal_dir = engine.SCRIPT_DIR / "atr_optimization_trades"
    journal_dir.mkdir(exist_ok=True)
    for label, multiplier, cooldown in configurations:
        fixed_stop = 15.0 if label == "fixed_15_cooldown" else None
        trades, _ = engine.simulate(
            surface,
            test_start,
            cost_per_trade=args.cost_per_trade,
            slippage_points_per_leg=args.slippage_points_per_leg,
            hard_stop_points=fixed_stop,
            atr_stop_multiplier=multiplier,
            cooldown_after_stop=cooldown,
        )
        trades.to_csv(journal_dir / f"trades_{label}.csv", index=False)
        results.append(summarize(trades, label, multiplier, cooldown, split_date))

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
    chart_path = write_sensitivity_chart(frame, args.output)
    print(frame.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
    print(f"Chronological split: in-sample before {split_date.date()}, out-of-sample from {split_date.date()}")
    print(f"Results CSV: {args.output}")
    print(f"Trade journals: {journal_dir}")
    if chart_path is not None:
        print(f"Sensitivity chart: {chart_path}")


if __name__ == "__main__":
    main()
