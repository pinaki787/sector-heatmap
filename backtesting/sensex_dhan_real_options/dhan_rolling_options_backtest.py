#!/usr/bin/env python3
"""Backtest the SENSEX long straddle on Dhan rolling expired-option candles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import requests


DHAN_API_URL = "https://api.dhan.co/v2/charts/rollingoption"
DEFAULT_TOKEN_CACHE = Path("/Users/pinaki/.dhan/access_token.json")
SENSEX_SECURITY_ID = "51"
LOT_SIZE = 20
INITIAL_CAPITAL = 100_000.0
VOL_WINDOW = 78
VOL_LOOKBACK = 20 * 78
VOL_PERCENTILE = 50
SUPER_TREND_PERIOD = 7
SUPER_TREND_MULTIPLIER = 3.0
ACTIVATION_POINTS = 10.0
ATR_STOP_PERIOD = 14
EOD_TIME = pd.Timestamp("15:20").time()
STRIKE_OFFSETS = range(-10, 11)
SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / "cache"


def load_credentials(path: Path) -> tuple[str, str]:
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    client_id = str(data.get("dhanClientId") or data.get("client_id") or "")
    access_token = str(data.get("accessToken") or data.get("access_token") or "")
    if not client_id or not access_token:
        raise RuntimeError(f"Dhan credential cache is incomplete: {path}")
    return client_id, access_token


def fetch_rolling_option(
    session: requests.Session,
    client_id: str,
    access_token: str,
    option_type: str,
    from_date: str,
    to_date: str,
    strike: str = "ATM",
) -> pd.DataFrame:
    payload = {
        "exchangeSegment": "BSE_FNO",
        "interval": "5",
        "securityId": SENSEX_SECURITY_ID,
        "instrument": "OPTIDX",
        "expiryFlag": "WEEK",
        # Dhan's rolling-options endpoint numbers the nearest rolling expiry as 1.
        "expiryCode": 1,
        "strike": strike,
        "drvOptionType": option_type,
        "requiredData": ["open", "high", "low", "close", "iv", "volume", "strike", "oi", "spot"],
        "fromDate": from_date,
        "toDate": to_date,
    }
    response = session.post(
        DHAN_API_URL,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "client-id": client_id,
            "access-token": access_token,
        },
        json=payload,
        timeout=45,
    )
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:300]
        raise RuntimeError(f"Dhan HTTP {response.status_code}: {detail}")
    body = response.json()
    side = "ce" if option_type == "CALL" else "pe"
    values = (body.get("data") or {}).get(side)
    if not values:
        raise RuntimeError(f"Dhan returned no {side.upper()} data: {body}")
    frame = pd.DataFrame({key: values.get(key, []) for key in payload["requiredData"] + ["timestamp"]})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    return frame.set_index("timestamp").sort_index()


def strike_label(offset: int) -> str:
    if offset == 0:
        return "ATM"
    return f"ATM{offset:+d}"


def date_chunks(start: pd.Timestamp, end: pd.Timestamp):
    cursor = start.normalize()
    while cursor < end:
        chunk_end = min(cursor + pd.Timedelta(days=30), end)
        yield cursor, chunk_end
        cursor = chunk_end


def fetch_surface(
    session: requests.Session,
    client_id: str,
    access_token: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    refresh: bool = False,
) -> pd.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    requests_made = 0
    combinations = [(side, offset) for side in ("CALL", "PUT") for offset in STRIKE_OFFSETS]
    chunks = list(date_chunks(start, end))
    for chunk_number, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        for option_type, offset in combinations:
            cache_path = CACHE_DIR / (
                f"{chunk_start:%Y%m%d}_{chunk_end:%Y%m%d}_{option_type.lower()}_{offset:+d}.csv"
            )
            if cache_path.exists() and not refresh:
                frame = pd.read_csv(cache_path, index_col="timestamp", parse_dates=True)
            else:
                frame = fetch_rolling_option(
                    session, client_id, access_token, option_type,
                    chunk_start.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d"),
                    strike_label(offset),
                )
                frame.to_csv(cache_path)
                requests_made += 1
                time.sleep(0.22)
            frame["option_type"] = option_type
            frame["offset"] = offset
            frames.append(frame)
        print(f"Loaded option surface chunk {chunk_number}/{len(chunks)} through {chunk_end.date()}", flush=True)
    surface = pd.concat(frames).sort_index()
    surface = surface[~surface.reset_index().duplicated(
        subset=["timestamp", "option_type", "offset"], keep="last"
    ).to_numpy()]
    print(f"Dhan requests made: {requests_made}; cached files reused: {len(frames) - requests_made}")
    return surface


def option_lookup(surface: pd.DataFrame, option_type: str) -> pd.DataFrame:
    side = surface[surface["option_type"] == option_type].reset_index()
    side = side.dropna(subset=["strike"])
    side["strike"] = side["strike"].astype(float)
    side = side.sort_values(["timestamp", "strike", "offset"])
    side = side.drop_duplicates(["timestamp", "strike"], keep="first")
    return side.set_index(["timestamp", "strike"])[
        ["open", "high", "low", "close", "iv", "volume", "oi"]
    ]


def compute_supertrend(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    high, low, close = frame["high"], frame["low"], frame["close"]
    previous_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs(),
    ], axis=1).max(axis=1)
    atr = true_range.ewm(
        alpha=1 / SUPER_TREND_PERIOD,
        adjust=False,
        min_periods=SUPER_TREND_PERIOD,
    ).mean()
    midpoint = (high + low) / 2
    basic_upper = midpoint + SUPER_TREND_MULTIPLIER * atr
    basic_lower = midpoint - SUPER_TREND_MULTIPLIER * atr
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    trend_line = pd.Series(np.nan, index=frame.index, dtype=float)
    bullish = pd.Series(True, index=frame.index, dtype=bool)
    for i in range(1, len(frame)):
        if pd.isna(atr.iloc[i]):
            continue
        if pd.isna(final_upper.iloc[i - 1]):
            final_upper.iloc[i - 1] = basic_upper.iloc[i]
            final_lower.iloc[i - 1] = basic_lower.iloc[i]
        if basic_upper.iloc[i] >= final_upper.iloc[i - 1] and close.iloc[i - 1] <= final_upper.iloc[i - 1]:
            final_upper.iloc[i] = final_upper.iloc[i - 1]
        if basic_lower.iloc[i] <= final_lower.iloc[i - 1] and close.iloc[i - 1] >= final_lower.iloc[i - 1]:
            final_lower.iloc[i] = final_lower.iloc[i - 1]
        previous = bullish.iloc[i - 1]
        if previous and close.iloc[i] < final_lower.iloc[i]:
            bullish.iloc[i] = False
        elif not previous and close.iloc[i] > final_upper.iloc[i]:
            bullish.iloc[i] = True
        else:
            bullish.iloc[i] = previous
        trend_line.iloc[i] = final_lower.iloc[i] if bullish.iloc[i] else final_upper.iloc[i]
    return trend_line, bullish


def compute_atr(frame: pd.DataFrame, period: int = ATR_STOP_PERIOD) -> pd.Series:
    """Wilder ATR using only current and earlier combined-premium candles."""
    previous_close = frame["close"].shift(1)
    true_range = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - previous_close).abs(),
        (frame["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def spot_frame(surface: pd.DataFrame) -> pd.DataFrame:
    spot = surface[(surface["option_type"] == "CALL") & (surface["offset"] == 0)][["spot"]].copy()
    spot = spot[~spot.index.duplicated(keep="last")].dropna()
    spot = spot.between_time("09:15", "15:20")
    spot.columns = ["close"]
    return spot


def low_vol_entries(spot: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    log_return = np.log(spot["close"] / spot["close"].shift(1))
    rv = log_return.rolling(VOL_WINDOW).std() * np.sqrt(252 * 78)
    threshold = rv.rolling(VOL_LOOKBACK).apply(
        lambda values: np.percentile(values, VOL_PERCENTILE), raw=True
    )
    return (rv < threshold).fillna(False), rv


def combined_contract(ce: pd.DataFrame, pe: pd.DataFrame, strike: float) -> pd.DataFrame:
    try:
        call = ce.xs(strike, level="strike")
        put = pe.xs(strike, level="strike")
    except KeyError:
        return pd.DataFrame()
    joined = call.add_suffix("_ce").join(put.add_suffix("_pe"), how="inner")
    combined = pd.DataFrame(index=joined.index)
    for field in ("open", "high", "low", "close"):
        combined[field] = joined[f"{field}_ce"] + joined[f"{field}_pe"]
    combined["ce_close"] = joined["close_ce"]
    combined["pe_close"] = joined["close_pe"]
    combined["ce_iv"] = joined["iv_ce"]
    combined["pe_iv"] = joined["iv_pe"]
    combined["ce_oi"] = joined["oi_ce"]
    combined["pe_oi"] = joined["oi_pe"]
    return combined.sort_index()


def simulate(
    surface: pd.DataFrame,
    test_start: pd.Timestamp,
    cost_per_trade: float,
    slippage_points_per_leg: float,
    hard_stop_points: float | None = None,
    atr_stop_multiplier: float | None = None,
    cooldown_after_stop: bool = False,
    rv_rise_bars: int | None = None,
    iv_percentile: float | None = None,
    premium_breakout_bars: int | None = None,
    entry_start_time=None,
    entry_end_time=None,
    time_stop_minutes: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    if hard_stop_points is not None and atr_stop_multiplier is not None:
        raise ValueError("Use either a fixed hard stop or an ATR stop, not both")
    spot = spot_frame(surface)
    entry_signal, rv = low_vol_entries(spot)
    if rv_rise_bars is not None:
        entry_signal &= rv > rv.shift(rv_rise_bars)
    atm_iv = None
    if iv_percentile is not None:
        iv_rows = surface[surface["offset"] == 0].reset_index()
        iv_rows = iv_rows.drop_duplicates(["timestamp", "option_type"], keep="last")
        iv_sides = iv_rows.pivot(index="timestamp", columns="option_type", values="iv")
        atm_iv = iv_sides[["CALL", "PUT"]].replace(0, np.nan).mean(axis=1)
        iv_threshold = (
            atm_iv.dropna()
            .rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK)
            .quantile(iv_percentile / 100)
            .reindex(atm_iv.index)
            .ffill()
        )
        entry_signal &= atm_iv.reindex(spot.index) <= iv_threshold.reindex(spot.index)
    ce = option_lookup(surface, "CALL")
    pe = option_lookup(surface, "PUT")
    trades = []
    missing_entries = 0
    timestamp_index = spot.index[spot.index >= test_start]
    cursor = 0
    while cursor < len(timestamp_index):
        timestamp = timestamp_index[cursor]
        if (
            timestamp.time() >= EOD_TIME
            or (entry_start_time is not None and timestamp.time() < entry_start_time)
            or (entry_end_time is not None and timestamp.time() > entry_end_time)
            or not bool(entry_signal.get(timestamp, False))
        ):
            cursor += 1
            continue
        atm_rows = surface[
            (surface.index == timestamp)
            & (surface["option_type"] == "CALL")
            & (surface["offset"] == 0)
        ]
        if atm_rows.empty or pd.isna(atm_rows.iloc[0]["strike"]):
            missing_entries += 1
            cursor += 1
            continue
        strike = float(atm_rows.iloc[0]["strike"])
        contract = combined_contract(ce, pe, strike)
        # The live runner asks for recent history of the held weekly contract.
        # A nearest-weekly rolling series changes contract after Thursday expiry,
        # so Friday is the earliest valid warm-up boundary for the current cycle.
        days_since_friday = (timestamp.weekday() - 4) % 7
        cycle_start = (timestamp - pd.Timedelta(days=days_since_friday)).normalize()
        cycle_contract = contract[
            (contract.index >= cycle_start)
            & (contract.index <= timestamp.normalize() + pd.Timedelta(hours=15, minutes=20))
            & (contract.index.time >= pd.Timestamp("09:15").time())
            & (contract.index.time <= EOD_TIME)
        ]
        if timestamp not in cycle_contract.index:
            missing_entries += 1
            cursor += 1
            continue
        line, bullish = compute_supertrend(cycle_contract)
        entry_premium = float(cycle_contract.loc[timestamp, "close"])
        if premium_breakout_bars is not None:
            prior_high = cycle_contract["close"].shift(1).rolling(premium_breakout_bars).max().loc[timestamp]
            if pd.isna(prior_high) or entry_premium <= prior_high:
                cursor += 1
                continue
        entry_atr = float(compute_atr(cycle_contract).loc[timestamp])
        stop_distance = (
            entry_atr * atr_stop_multiplier
            if atr_stop_multiplier is not None and np.isfinite(entry_atr)
            else hard_stop_points
        )
        armed_at = None
        exit_time = None
        exit_reason = None
        candidates = cycle_contract.index[
            (cycle_contract.index > timestamp) & (cycle_contract.index.date == timestamp.date())
        ]
        for candidate in candidates:
            premium = float(cycle_contract.loc[candidate, "close"])
            pnl_points = premium - entry_premium
            if stop_distance is not None and pnl_points <= -stop_distance:
                exit_time, exit_reason = candidate, "stoploss"
                break
            if armed_at is None and pnl_points >= ACTIVATION_POINTS:
                armed_at = candidate
            if candidate.time() >= EOD_TIME:
                exit_time, exit_reason = candidate, "eod"
                break
            if (
                time_stop_minutes is not None
                and armed_at is None
                and candidate >= timestamp + pd.Timedelta(minutes=time_stop_minutes)
            ):
                exit_time, exit_reason = candidate, "time_stop"
                break
            if (
                armed_at is not None and candidate > armed_at
                and pd.notna(line.loc[candidate]) and not bool(bullish.loc[candidate])
            ):
                exit_time, exit_reason = candidate, "supertrend_trail"
                break
        if exit_time is None:
            missing_entries += 1
            cursor += 1
            continue
        exit_premium = float(cycle_contract.loc[exit_time, "close"])
        gross_points = exit_premium - entry_premium
        slippage_rupees = slippage_points_per_leg * 4 * LOT_SIZE
        gross_rupees = gross_points * LOT_SIZE
        net_rupees = gross_rupees - cost_per_trade - slippage_rupees
        trades.append({
            "entry_time": timestamp,
            "exit_time": exit_time,
            "strike": strike,
            "entry_spot": float(spot.loc[timestamp, "close"]),
            "entry_rv": float(rv.loc[timestamp]),
            "ce_entry": float(cycle_contract.loc[timestamp, "ce_close"]),
            "pe_entry": float(cycle_contract.loc[timestamp, "pe_close"]),
            "premium_entry": entry_premium,
            "premium_exit": exit_premium,
            "gross_pnl_points": gross_points,
            "gross_pnl_rupees": gross_rupees,
            "cost_rupees": cost_per_trade,
            "slippage_rupees": slippage_rupees,
            "net_pnl_rupees": net_rupees,
            "exit_reason": exit_reason,
            "supertrend_armed_time": armed_at,
            "entry_atr": entry_atr,
            "stop_distance_points": stop_distance,
            "entry_atm_iv": float(atm_iv.loc[timestamp]) if atm_iv is not None else np.nan,
        })
        if cooldown_after_stop and exit_reason == "stoploss":
            next_day = exit_time.normalize() + pd.Timedelta(days=1)
            cursor = int(timestamp_index.searchsorted(next_day, side="left"))
        else:
            cursor = int(timestamp_index.searchsorted(exit_time, side="right"))
    return pd.DataFrame(trades), {"missing_entry_bars": missing_entries, "spot_bars": len(timestamp_index)}


def longest_losing_streak(values: pd.Series) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value <= 0 else 0
        longest = max(longest, current)
    return longest


def annualized_ratio(returns: pd.Series, downside_only: bool = False) -> float:
    values = returns[returns < 0] if downside_only else returns
    deviation = values.std(ddof=1)
    if not np.isfinite(deviation) or deviation == 0:
        return np.nan
    return float(returns.mean() / deviation * np.sqrt(252))


def report(trades: pd.DataFrame, diagnostics: dict, spot: pd.DataFrame, output: Path) -> None:
    if trades.empty:
        raise RuntimeError("No complete trades were generated from Dhan option data")
    pnl = trades["net_pnl_rupees"]
    equity = INITIAL_CAPITAL + pnl.cumsum()
    drawdown = equity / equity.cummax() - 1
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    profit_factor = wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf
    trading_days = pd.Index(trades["entry_time"].dt.date).nunique()
    daily_pnl = trades.assign(date=trades["exit_time"].dt.date).groupby("date")["net_pnl_rupees"].sum()
    daily_index = pd.date_range(spot.index.min().normalize(), spot.index.max().normalize(), freq="B").date
    daily_pnl = daily_pnl.reindex(daily_index, fill_value=0.0)
    strategy_returns = daily_pnl / (INITIAL_CAPITAL + daily_pnl.cumsum().shift(1, fill_value=0.0))
    spot_daily = spot["close"].groupby(spot.index.date).last()
    benchmark_returns = spot_daily.pct_change().dropna()
    benchmark_equity = INITIAL_CAPITAL * (1 + benchmark_returns).cumprod()
    benchmark_drawdown = benchmark_equity / benchmark_equity.cummax() - 1
    benchmark_total_return = float(spot_daily.iloc[-1] / spot_daily.iloc[0] - 1)
    gross_pnl = trades["gross_pnl_rupees"]
    gross_losses = gross_pnl[gross_pnl <= 0]
    gross_pf = gross_pnl[gross_pnl > 0].sum() / -gross_losses.sum() if gross_losses.sum() < 0 else np.inf
    trades.to_csv(output, index=False)
    print("SENSEX LONG STRADDLE - DHAN REAL EXPIRED-OPTION BACKTEST")
    print(f"Coverage: {trades['entry_time'].min()} to {trades['exit_time'].max()}")
    print(f"Rules: low-vol P{VOL_PERCENTILE}; ST({SUPER_TREND_PERIOD},{SUPER_TREND_MULTIPLIER:g}) armed +{ACTIVATION_POINTS:g}; EOD {EOD_TIME}; no hard stop/target/cooldown")
    print("Prices: actual Dhan rolling weekly ATM+/- option 5-minute OHLC; held strike reconstructed")
    print(f"Trades: {len(trades)} across {trading_days} entry days")
    print(f"Gross win rate / profit factor: {(gross_pnl > 0).mean():.2%} / {gross_pf:.2f}")
    print(f"Win rate after modeled costs/slippage: {(pnl > 0).mean():.2%}")
    print(f"Profit factor: {profit_factor:.2f}")
    print(f"Gross P&L: Rs {trades['gross_pnl_rupees'].sum():+,.2f}")
    print(f"Net P&L: Rs {pnl.sum():+,.2f}")
    print(f"Return on Rs {INITIAL_CAPITAL:,.0f}: {pnl.sum() / INITIAL_CAPITAL:+.2%}")
    print(f"Max drawdown: {drawdown.min():.2%} (Rs {(equity.cummax() - equity).max():,.2f})")
    print(f"Longest losing streak: {longest_losing_streak(pnl)}")
    print(f"Best / worst trade: Rs {pnl.max():+,.2f} / Rs {pnl.min():+,.2f}")
    print(f"Exit reasons: {trades['exit_reason'].value_counts().to_dict()}")
    print(f"Incomplete/missing candidate entries skipped: {diagnostics['missing_entry_bars']}")
    print()
    print("STRATEGY VS SENSEX BENCHMARK")
    print(f"{'Metric':<20} {'Strategy':>14} {'SENSEX':>14}")
    print(f"{'Total return':<20} {pnl.sum() / INITIAL_CAPITAL:>13.2%} {benchmark_total_return:>13.2%}")
    print(f"{'Sharpe':<20} {annualized_ratio(strategy_returns):>14.2f} {annualized_ratio(benchmark_returns):>14.2f}")
    print(f"{'Sortino':<20} {annualized_ratio(strategy_returns, True):>14.2f} {annualized_ratio(benchmark_returns, True):>14.2f}")
    print(f"{'Max drawdown':<20} {drawdown.min():>13.2%} {benchmark_drawdown.min():>13.2%}")
    print(f"Trades CSV: {output}")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=equity, name="Strategy equity"), row=1, col=1)
        figure.add_trace(go.Scatter(x=spot_daily.index, y=benchmark_equity, name="SENSEX benchmark"), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=drawdown * 100, name="Strategy drawdown %", fill="tozeroy"), row=2, col=1)
        figure.update_layout(template="plotly_dark", title="SENSEX Dhan real-option backtest")
        chart_path = output.with_name("sensex_dhan_180d_equity.html")
        figure.write_html(chart_path, include_plotlyjs=True)
        print(f"Equity and drawdown chart: {chart_path}")
    except ImportError:
        print("Equity chart skipped: Plotly is unavailable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--token-cache", type=Path, default=DEFAULT_TOKEN_CACHE)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--cost-per-trade", type=float, default=100.0)
    parser.add_argument("--slippage-points-per-leg", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=SCRIPT_DIR / "sensex_dhan_180d_trades.csv")
    args = parser.parse_args()

    client_id, access_token = load_credentials(args.token_cache)
    with requests.Session() as session:
        if args.probe:
            call = fetch_rolling_option(session, client_id, access_token, "CALL", args.from_date, args.to_date)
            print(f"Dhan ATM weekly CALL bars: {len(call)}")
            if not call.empty:
                print(f"Range: {call.index.min()} to {call.index.max()}")
                print(call.tail(3).to_string())
            return
        test_start = pd.Timestamp(args.from_date, tz="Asia/Kolkata")
        test_end = pd.Timestamp(args.to_date, tz="Asia/Kolkata")
        warmup_start = test_start - pd.Timedelta(days=35)
        surface = fetch_surface(
            session, client_id, access_token, warmup_start, test_end,
            refresh=args.refresh,
        )
    trades, diagnostics = simulate(
        surface, test_start,
        cost_per_trade=args.cost_per_trade,
        slippage_points_per_leg=args.slippage_points_per_leg,
    )
    report(trades, diagnostics, spot_frame(surface).loc[test_start:test_end], args.output)


if __name__ == "__main__":
    main()
