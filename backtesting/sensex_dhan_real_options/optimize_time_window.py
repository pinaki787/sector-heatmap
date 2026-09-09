#!/usr/bin/env python3
"""Sensitivity test for entry cutoff and time stop on the selected entry structure."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import dhan_rolling_options_backtest as engine


ENTRY_ENDS = (dt.time(11, 30), dt.time(13, 30), dt.time(15, 0))
TIME_STOPS = (30, 45, 60, 90, None)


def write_chart(frame: pd.DataFrame, output: Path) -> Path | None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return None
    plot = frame.copy()
    plot["time_stop_label"] = plot["time_stop_minutes"].fillna("none").astype(str)
    figure = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Net P&L (Rs)", "Profit factor", "Max drawdown (%)"),
    )
    for column, metric in enumerate(
        ("net_pnl_rupees", "profit_factor", "max_drawdown_pct"), start=1
    ):
        pivot = plot.pivot(index="entry_end", columns="time_stop_label", values=metric)
        figure.add_trace(
            go.Heatmap(
                z=pivot.to_numpy(), x=pivot.columns, y=pivot.index,
                coloraxis=f"coloraxis{column}", hoverongaps=False,
            ),
            row=1, col=column,
        )
    figure.update_layout(
        template="plotly_dark", title="SENSEX entry-window and time-stop sensitivity",
        coloraxis={"colorscale": "RdYlGn"},
        coloraxis2={"colorscale": "RdYlGn"},
        coloraxis3={"colorscale": "RdYlGn"},
    )
    chart_path = output.with_name("time_window_sensitivity.html")
    figure.write_html(chart_path, include_plotlyjs=True)
    return chart_path


def metrics(trades: pd.DataFrame) -> tuple[int, float, float, float]:
    if trades.empty:
        return 0, 0.0, np.nan, 0.0
    pnl = trades["net_pnl_rupees"]
    losses = pnl[pnl <= 0]
    pf = pnl[pnl > 0].sum() / -losses.sum() if losses.sum() < 0 else np.inf
    equity = engine.INITIAL_CAPITAL + pnl.cumsum()
    drawdown = (equity / equity.cummax() - 1).min() * 100
    return len(trades), float(pnl.sum()), float(pf), float(drawdown)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--token-cache", type=Path, default=engine.DEFAULT_TOKEN_CACHE)
    parser.add_argument("--output", type=Path, default=engine.SCRIPT_DIR / "time_window_optimization.csv")
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
    journal_dir = engine.SCRIPT_DIR / "time_window_trades"
    journal_dir.mkdir(exist_ok=True)
    for entry_end in ENTRY_ENDS:
        for time_stop in TIME_STOPS:
            trades, _ = engine.simulate(
                surface, start, cost_per_trade=100.0, slippage_points_per_leg=0.5,
                atr_stop_multiplier=1.25, cooldown_after_stop=True,
                rv_rise_bars=6, premium_breakout_bars=6,
                entry_start_time=dt.time(9, 25), entry_end_time=entry_end,
                time_stop_minutes=time_stop,
            )
            label = f"end{entry_end:%H%M}_ts{'none' if time_stop is None else time_stop}"
            trades.to_csv(journal_dir / f"{label}.csv", index=False)
            ins = trades[trades["entry_time"] < split] if not trades.empty else trades
            oos = trades[trades["entry_time"] >= split] if not trades.empty else trades
            count, net, pf, dd = metrics(trades)
            in_count, in_net, in_pf, _ = metrics(ins)
            out_count, out_net, out_pf, out_dd = metrics(oos)
            rows.append({
                "configuration": label, "entry_end": f"{entry_end:%H:%M}",
                "time_stop_minutes": time_stop, "trades": count,
                "net_pnl_rupees": net, "profit_factor": pf, "max_drawdown_pct": dd,
                "in_sample_trades": in_count, "in_sample_net_pnl": in_net,
                "in_sample_profit_factor": in_pf, "out_sample_trades": out_count,
                "out_sample_net_pnl": out_net, "out_sample_profit_factor": out_pf,
                "out_sample_max_drawdown_pct": out_dd,
            })
    frame = pd.DataFrame(rows).sort_values(
        ["out_sample_net_pnl", "net_pnl_rupees"], ascending=False
    )
    frame.to_csv(args.output, index=False)
    chart_path = write_chart(frame, args.output)
    print(frame.to_string(index=False, float_format=lambda value: f"{value:,.2f}"))
    print(f"Results CSV: {args.output}")
    if chart_path is not None:
        print(f"Sensitivity chart: {chart_path}")
    print(f"Trade journals: {journal_dir}")


if __name__ == "__main__":
    main()
