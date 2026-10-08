# Generated source and settings reference

Generated from source on 8 October 2026 without importing modules or reading credential/runtime files. This is a coverage map of all Python application, strategy, helper and research sources and root JavaScript. It complements the [technical guide](technical-guide.md), [user guide](user-functional-guide.md), and [deployment guide](deployment-guide.md). Function signatures list exact defaults; payload-setting entries list literal fallbacks. Defaults in wrappers can override helper defaults. Research modules remain research-only. Source links own full branches, formulas, validation and rounding; the catalog does not execute them.

## backtesting/coalindia_long_straddle/coalindia_long_straddle_check.py

[Owning source](../backtesting/coalindia_long_straddle/coalindia_long_straddle_check.py)

Read-only Dhan snapshot for a COALINDIA ATM long-straddle assessment.

### Callables and explicit defaults

- `credentials()`
- `main()`

## backtesting/coalindia_long_straddle/fyers_coalindia_snapshot.py

[Owning source](../backtesting/coalindia_long_straddle/fyers_coalindia_snapshot.py)

Read-only FYERS COALINDIA chart and ATM straddle evidence snapshot.

### Callables and explicit defaults

- `candle_summary(client, resolution: str, days: int)`
- `main()`

### Literal payload and lookup fallbacks

- `strike_price` → `-1`

## backtesting/delta_indicator_grid/render_report.py

[Owning source](../backtesting/delta_indicator_grid/render_report.py)

Render saved evidence, never rerank using final test results.

### Callables and explicit defaults

- `money(x)`
- `pct(x)`
- `config(c)`
- `chart(points)`
- `main()`

## backtesting/delta_indicator_grid/research.py

[Owning source](../backtesting/delta_indicator_grid/research.py)

Standalone public futures experiment. Never imports a broker/order client.

### Callables and explicit defaults

- `indicators(rows, period=14, multiplier=3, ema_length=50)`
- `run_sim(rows, signals, bb, ind, cfg, settings, units, tick, lo, hi, detail=False)`
- `main()`

## backtesting/ema_crossover_10_30/NIFTY_confluence_optimize.py

[Owning source](../backtesting/ema_crossover_10_30/NIFTY_confluence_optimize.py)

Predefined confluence comparison. Cached FYERS spot data; no order route.

### Callables and explicit defaults

- `run(name, period, cost=5)`

## backtesting/ema_crossover_10_30/NIFTY_ema_crossover_backtest.py

[Owning source](../backtesting/ema_crossover_10_30/NIFTY_ema_crossover_backtest.py)

EMA 10/30, Nifty spot proxy; read-only history, no broker order calls.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `message` → `'History unavailable'`

## backtesting/ema_daily_confluence/diagnostics.py

[Owning source](../backtesting/ema_daily_confluence/diagnostics.py)

Post-selection daily-cap and strict-confluence diagnostics; not fresh holdout.

## backtesting/ema_daily_confluence/fetch_volume.py

[Owning source](../backtesting/ema_daily_confluence/fetch_volume.py)

Read-only FYERS ETF volume history; never calls an order endpoint.

### Literal payload and lookup fallbacks

- `message` → `'History unavailable'`

## backtesting/ema_daily_confluence/render_report.py

[Owning source](../backtesting/ema_daily_confluence/render_report.py)

Render frequency and drawdown comparisons from saved research outputs.

## backtesting/ema_daily_confluence/research.py

[Owning source](../backtesting/ema_daily_confluence/research.py)

Daily-frequency confluence research. Immutable baseline; no live order path.

### Callables and explicit defaults

- `read(path)`
- `prepare()`
- `events(d, cfg)`
- `simulate(d, ev, cost=5)`
- `metrics(d, t, curve, days)`
- `main()`

### Literal payload and lookup fallbacks

- `daily_cap` → `3`

## backtesting/kama_solarinds/solarinds_kama_7d_backtest.py

[Owning source](../backtesting/kama_solarinds/solarinds_kama_7d_backtest.py)

Read-only seven-day KAMA research backtest for SOLARINDS underlying.

### Callables and explicit defaults

- `kama(values)`
- `main()`

## backtesting/kama_vwap_htf_solarinds/solarinds_kama_vwap_htf_7d_backtest.py

[Owning source](../backtesting/kama_vwap_htf_solarinds/solarinds_kama_vwap_htf_7d_backtest.py)

Read-only SOLARINDS KAMA, VWAP, and completed 15-minute trend-gate test.

### Callables and explicit defaults

- `kama(values)`
- `vwap(rows)`
- `main()`

## backtesting/kama_vwap_htf_solarinds/solarinds_kama_vwap_htf_confluence_optimize.py

[Owning source](../backtesting/kama_vwap_htf_solarinds/solarinds_kama_vwap_htf_confluence_optimize.py)

Read-only confluence sweep; it never calls an order endpoint.

### Callables and explicit defaults

- `kama(x)`
- `vwap(rows)`
- `main()`

## backtesting/kama_vwap_solarinds/solarinds_kama_vwap_7d_backtest.py

[Owning source](../backtesting/kama_vwap_solarinds/solarinds_kama_vwap_7d_backtest.py)

Read-only seven-day SOLARINDS KAMA plus session-VWAP research backtest.

### Callables and explicit defaults

- `kama(values)`
- `session_vwap(rows)`
- `main()`

## backtesting/nifty_30_point_feasibility/nifty_30_point_feasibility.py

[Owning source](../backtesting/nifty_30_point_feasibility/nifty_30_point_feasibility.py)

Read-only FYERS study of NIFTY's 30-point intraday opportunity frequency.

### Callables and explicit defaults

- `main()`

## backtesting/nifty_daily_pullback_proxy/nifty_daily_pullback_proxy.py

[Owning source](../backtesting/nifty_daily_pullback_proxy/nifty_daily_pullback_proxy.py)

Read-only NIFTY index proxy, daily multi-day trend-pullback continuation research.

### Callables and explicit defaults

- `fetch_daily(client: fyersModel.FyersModel, now: datetime)`
- `simulate(frame: pd.DataFrame)`
- `metrics(trades: list[dict])`
- `main()`

## backtesting/nifty_futures_feasibility/nifty_futures_feasibility.py

[Owning source](../backtesting/nifty_futures_feasibility/nifty_futures_feasibility.py)

Read-only feasibility gate for NIFTY futures history in FYERS.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## backtesting/nifty_price_action/nifty_opening_range_breakout_90d.py

[Owning source](../backtesting/nifty_price_action/nifty_opening_range_breakout_90d.py)

Read-only NIFTY 90-day price-action opening-range-breakout research.

### Callables and explicit defaults

- `main()`

## backtesting/nifty_price_action/nifty_orb_rsi_90d.py

[Owning source](../backtesting/nifty_price_action/nifty_orb_rsi_90d.py)

Read-only NIFTY ORB plus RSI(14) research using FYERS completed 5-minute candles.

### Callables and explicit defaults

- `rsi(close: pd.Series, period: int)`
- `main()`

## backtesting/nifty_prop_vwap_mean_reversion/nifty_vwap_mean_reversion.py

[Owning source](../backtesting/nifty_prop_vwap_mean_reversion/nifty_vwap_mean_reversion.py)

Read-only NIFTY prop-style VWAP mean-reversion research using FYERS 5-minute candles.

### Callables and explicit defaults

- `rsi(close: pd.Series, period: int)`
- `fetch_year(client: fyersModel.FyersModel, now: datetime)`
- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_regime_trend_continuation/nifty_regime_trend_continuation.py

[Owning source](../backtesting/nifty_regime_trend_continuation/nifty_regime_trend_continuation.py)

Read-only NIFTY regime-filtered trend-day continuation research using FYERS data.

### Callables and explicit defaults

- `fetch_history(client: fyersModel.FyersModel, now: datetime)`
- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_regime_trend_continuation_15m/nifty_regime_trend_continuation_15m.py

[Owning source](../backtesting/nifty_regime_trend_continuation_15m/nifty_regime_trend_continuation_15m.py)

Read-only NIFTY 15-minute regime-filtered trend-day continuation research.

### Callables and explicit defaults

- `fetch_history(client: fyersModel.FyersModel, now: datetime)`
- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_regime_trend_kama_15m/nifty_regime_trend_kama_15m.py

[Owning source](../backtesting/nifty_regime_trend_kama_15m/nifty_regime_trend_kama_15m.py)

Read-only 15-minute NIFTY continuation research with a KAMA trend filter.

### Callables and explicit defaults

- `kama(close: pd.Series)`
- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_renko_10pt_multitimeframe/nifty_renko_10pt_multitimeframe.py

[Owning source](../backtesting/nifty_renko_10pt_multitimeframe/nifty_renko_10pt_multitimeframe.py)

Read-only NIFTY 10-point fixed-brick Renko reversal research across timeframes.

### Callables and explicit defaults

- `main()`

## backtesting/nifty_renko_brick_diagnostic/nifty_renko_brick_diagnostic.py

[Owning source](../backtesting/nifty_renko_brick_diagnostic/nifty_renko_brick_diagnostic.py)

Read-only NIFTY fixed-Renko brick diagnostic from completed 15-minute candles.

### Callables and explicit defaults

- `main()`

## backtesting/nifty_renko_combo_comparison/nifty_renko_combo_comparison.py

[Owning source](../backtesting/nifty_renko_combo_comparison/nifty_renko_combo_comparison.py)

Read-only, bounded Renko combination comparison across three NIFTY timeframes.

### Callables and explicit defaults

- `kama(close)`
- `prepare(frame)`
- `run(frame, mode)`
- `metrics(records)`
- `main()`

## backtesting/nifty_renko_reversal_multitimeframe/nifty_renko_reversal_multitimeframe.py

[Owning source](../backtesting/nifty_renko_reversal_multitimeframe/nifty_renko_reversal_multitimeframe.py)

Read-only NIFTY intraday fixed-brick Renko reversal research across timeframes.

### Callables and explicit defaults

- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_smc_only_15m/nifty_smc_only_15m.py

[Owning source](../backtesting/nifty_smc_only_15m/nifty_smc_only_15m.py)

Read-only NIFTY 15-minute SMC-only market-structure-break research.

### Callables and explicit defaults

- `fetch_history(client: fyersModel.FyersModel, now: datetime)`
- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_smc_vwap_15m/nifty_smc_vwap_15m.py

[Owning source](../backtesting/nifty_smc_vwap_15m/nifty_smc_vwap_15m.py)

Read-only NIFTY 15-minute SMC plus session VWAP research.

### Callables and explicit defaults

- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_vwap_pullback_30pt_trail_multitimeframe/nifty_vwap_pullback_30pt_trail_multitimeframe.py

[Owning source](../backtesting/nifty_vwap_pullback_30pt_trail_multitimeframe/nifty_vwap_pullback_30pt_trail_multitimeframe.py)

Read-only NIFTY VWAP pullback research with a 30-point profit-trailing exit.

### Callables and explicit defaults

- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

## backtesting/nifty_vwap_pullback_8pt_trail_multitimeframe/nifty_vwap_pullback_8pt_trail_multitimeframe.py

[Owning source](../backtesting/nifty_vwap_pullback_8pt_trail_multitimeframe/nifty_vwap_pullback_8pt_trail_multitimeframe.py)

Read-only NIFTY VWAP pullback research with an 8-point profit trail.

### Callables and explicit defaults

- `main()`

## backtesting/nifty_vwap_pullback_multitimeframe/nifty_vwap_pullback_multitimeframe.py

[Owning source](../backtesting/nifty_vwap_pullback_multitimeframe/nifty_vwap_pullback_multitimeframe.py)

Read-only NIFTY pure VWAP pullback study across 3-, 5-, and 15-minute candles.

### Callables and explicit defaults

- `fetch_history(client: fyersModel.FyersModel, now: datetime, resolution: str)`
- `evaluate(frame: pd.DataFrame, days: int)`
- `main()`

### Configuration literals

- `TIMEFRAMES = ('3', '5', '15')`

## backtesting/pinaki_das_supertrend/nifty_pinaki_das_supertrend_research.py

[Owning source](../backtesting/pinaki_das_supertrend/nifty_pinaki_das_supertrend_research.py)

One-year, completed-candle research for the original Pinaki Das Supertrend.

### Callables and explicit defaults

- `fetch_history(client: fyersModel.FyersModel, now: datetime)`
- `wilder_atr(df: pd.DataFrame, length: int)`
- `add_indicator(df: pd.DataFrame)`
- `simulate(data: pd.DataFrame)`
- `main()`

### Literal payload and lookup fallbacks

- `message` → `'FYERS history unavailable'`

## backtesting/sensex_dhan_real_options/dhan_rolling_options_backtest.py

[Owning source](../backtesting/sensex_dhan_real_options/dhan_rolling_options_backtest.py)

Backtest the SENSEX long straddle on Dhan rolling expired-option candles.

### Callables and explicit defaults

- `load_credentials(path: Path)`
- `fetch_rolling_option(session: requests.Session, client_id: str, access_token: str, option_type: str, from_date: str, to_date: str, strike: str='ATM')`
- `strike_label(offset: int)`
- `date_chunks(start: pd.Timestamp, end: pd.Timestamp)`
- `fetch_surface(session: requests.Session, client_id: str, access_token: str, start: pd.Timestamp, end: pd.Timestamp, refresh: bool=False)`
- `option_lookup(surface: pd.DataFrame, option_type: str)`
- `compute_supertrend(frame: pd.DataFrame)`
- `compute_atr(frame: pd.DataFrame, period: int=ATR_STOP_PERIOD)`
- `spot_frame(surface: pd.DataFrame)`
- `low_vol_entries(spot: pd.DataFrame)`
- `combined_contract(ce: pd.DataFrame, pe: pd.DataFrame, strike: float)`
- `simulate(surface: pd.DataFrame, test_start: pd.Timestamp, cost_per_trade: float, slippage_points_per_leg: float, hard_stop_points: float | None=None, atr_stop_multiplier: float | None=None, cooldown_after_stop: bool=False, rv_rise_bars: int | None=None, iv_percentile: float | None=None, premium_breakout_bars: int | None=None, entry_start_time=None, entry_end_time=None, time_stop_minutes: int | None=None)`
- `longest_losing_streak(values: pd.Series)`
- `annualized_ratio(returns: pd.Series, downside_only: bool=False)`
- `report(trades: pd.DataFrame, diagnostics: dict, spot: pd.DataFrame, output: Path)`
- `main()`

## backtesting/sensex_dhan_real_options/optimize_atr_stop.py

[Owning source](../backtesting/sensex_dhan_real_options/optimize_atr_stop.py)

Optimize a combined-premium ATR stop for the SENSEX long straddle.

### Callables and explicit defaults

- `write_sensitivity_chart(frame: pd.DataFrame, output: Path)`
- `period_metrics(trades: pd.DataFrame)`
- `summarize(trades: pd.DataFrame, label: str, multiplier: float | None, cooldown: bool, split_date: pd.Timestamp)`
- `main()`

## backtesting/sensex_dhan_real_options/optimize_entry_filters.py

[Owning source](../backtesting/sensex_dhan_real_options/optimize_entry_filters.py)

Walk-forward search for volatility-expansion entries on SENSEX straddles.

### Callables and explicit defaults

- `metrics(trades: pd.DataFrame)`
- `main()`

## backtesting/sensex_dhan_real_options/optimize_hard_stop.py

[Owning source](../backtesting/sensex_dhan_real_options/optimize_hard_stop.py)

Compare hard-stop and post-stop cooldown variants on cached Dhan option data.

### Callables and explicit defaults

- `period_metrics(trades: pd.DataFrame)`
- `summarize(trades: pd.DataFrame, stop: float | None, cooldown: bool, split_date: pd.Timestamp)`
- `main()`

## backtesting/sensex_dhan_real_options/optimize_time_window.py

[Owning source](../backtesting/sensex_dhan_real_options/optimize_time_window.py)

Sensitivity test for entry cutoff and time stop on the selected entry structure.

### Callables and explicit defaults

- `write_chart(frame: pd.DataFrame, output: Path)`
- `metrics(trades: pd.DataFrame)`
- `main()`

## backtesting/swing_scan/fyers_stock_option_scan.py

[Owning source](../backtesting/swing_scan/fyers_stock_option_scan.py)

Read-only FYERS ATM option statistics for selected NSE stock-option underlyings.

### Callables and explicit defaults

- `number(value)`
- `main()`

## backtesting/swing_scan/fyers_swing_scan.py

[Owning source](../backtesting/swing_scan/fyers_swing_scan.py)

Read-only completed-candle swing scan for selected NSE equities using FYERS.

### Callables and explicit defaults

- `candles(client, symbol, resolution, days)`
- `metrics(frame)`
- `main()`

## backtesting/trailing_exit_research/audit.py

[Owning source](../backtesting/trailing_exit_research/audit.py)

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `config` → `{}`

## backtesting/trailing_exit_research/case_analysis.py

[Owning source](../backtesting/trailing_exit_research/case_analysis.py)

### Literal payload and lookup fallbacks

- `candles` → `[]`

## backtesting/trailing_exit_research/case_counterfactuals.py

[Owning source](../backtesting/trailing_exit_research/case_counterfactuals.py)

Recorded entries and baseline exits retained; close-only counterfactuals.

## backtesting/trailing_exit_research/cases.py

[Owning source](../backtesting/trailing_exit_research/cases.py)

## backtesting/trailing_exit_research/expired_catalog.py

[Owning source](../backtesting/trailing_exit_research/expired_catalog.py)

## backtesting/trailing_exit_research/fetch_cases.py

[Owning source](../backtesting/trailing_exit_research/fetch_cases.py)

### Literal payload and lookup fallbacks

- `candles` → `[]`

## backtesting/trailing_exit_research/fetch_crude_options.py

[Owning source](../backtesting/trailing_exit_research/fetch_crude_options.py)

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `order_history` → `[]`
- `symbol` → `''`

## backtesting/trailing_exit_research/fetch_history.py

[Owning source](../backtesting/trailing_exit_research/fetch_history.py)

Read-only FYERS history probes using existing application credentials. No login.

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `order_history` → `[]`

## backtesting/trailing_exit_research/fetch_selected.py

[Owning source](../backtesting/trailing_exit_research/fetch_selected.py)

Read-only exact listed-contract historical candles; no auth mutation/orders.

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `range_from` → `'9999'`
- `range_to` → `'0000'`

## backtesting/trailing_exit_research/open_case.py

[Owning source](../backtesting/trailing_exit_research/open_case.py)

Read-only open-position evidence; no runner or order mutations.

### Literal payload and lookup fallbacks

- `config` → `{}`

## backtesting/trailing_exit_research/prepare.py

[Owning source](../backtesting/trailing_exit_research/prepare.py)

Freeze baseline one-minute entry opportunities for paired exit research.

### Callables and explicit defaults

- `day(t)`
- `prepare()`

### Literal payload and lookup fallbacks

- `sideways_max_candles` → `3`

## backtesting/trailing_exit_research/probe_expired.py

[Owning source](../backtesting/trailing_exit_research/probe_expired.py)

## backtesting/trailing_exit_research/report.py

[Owning source](../backtesting/trailing_exit_research/report.py)

Render the saved research results as a self-contained readable HTML report.

### Callables and explicit defaults

- `read(name)`
- `table(rows, keys)`
- `main()`

### Literal payload and lookup fallbacks

- `MCX:CRUDEOIL26OCT8600PE` → `{}`
- `d` → `{}`

## backtesting/trailing_exit_research/research.py

[Owning source](../backtesting/trailing_exit_research/research.py)

Paired option-candle exit study. Research only; contains no broker/order code.

### Callables and explicit defaults

- `date(t)`
- `write_csv(name, rows)`
- `valid(c)`
- `features(rows, seconds)`
- `variants()`
- `replay(t, rows, f1, f5, quotes, v, slip=0.01, ema=True, path_model='close')`
- `metrics(trades)`
- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## backtesting/trailing_exit_research/source_snapshot/__init__.py

[Owning source](../backtesting/trailing_exit_research/source_snapshot/__init__.py)

## backtesting/trailing_exit_research/source_snapshot/candle_patterns.py

[Owning source](../backtesting/trailing_exit_research/source_snapshot/candle_patterns.py)

Explicit body-based patterns for completed host-candle retests.

### Callables and explicit defaults

- `matches(rows, bullish, config)`

### Literal payload and lookup fallbacks

- `retest_engulfing` → `True`
- `retest_harami` → `True`
- `retest_star` → `True`

## backtesting/trailing_exit_research/source_snapshot/retest.py

[Owning source](../backtesting/trailing_exit_research/source_snapshot/retest.py)

Optional completed-candle EMA10 retest with matching pattern confirmation.

### Callables and explicit defaults

- `evaluate(state, candle, previous, previous_emas, previous_direction, direction, entry, allowed, config=None)`

### Literal payload and lookup fallbacks

- `retest_bars` → `[]`
- `retest_ready` → `False`

## backtesting/trailing_exit_research/source_snapshot/rsi_slope.py

[Owning source](../backtesting/trailing_exit_research/source_snapshot/rsi_slope.py)

Wilder RSI14 of host closes, identical seeding/flat convention to chart display.

### Callables and explicit defaults

- `observe(state, close)`
- `apply(entry, state, observation, direction, enabled)`

### Literal payload and lookup fallbacks

- `count` → `0`
- `gain` → `0`
- `loss` → `0`
- `rsi_host` → `{}`

## backtesting/trailing_exit_research/source_snapshot/sideways.py

[Owning source](../backtesting/trailing_exit_research/source_snapshot/sideways.py)

Quick losing-position range lock; no swing history, entry signal or order route.

### Callables and explicit defaults

- `settings(payload)`
- `observe(exposure, entry_at, price, stamp, now, exit_at=None)`
- `candle_count(entry_at, exit_at, seconds)`
- `freeze(exposure, exit_at, realized, seconds, config, trade_id, underlying)`
- `breakout(lock, price, stamp, now)`

### Literal payload and lookup fallbacks

- `sideways_enabled` → `False`
- `sideways_max_candles` → `3`

## backtesting/trailing_exit_research/source_snapshot/signals.py

[Owning source](../backtesting/trailing_exit_research/source_snapshot/signals.py)

Sequential port of source.pine, including Pine-style missing-value warm-up.

### Callables and explicit defaults

- `settings(payload)`
- `completed(candles)`
- `rma(state, key, value, length)`
- `ema_setup(state, close, direction, allowed, window)`
- `project_lifecycle(state, timestamp, entry_direction, reversal_direction, seconds=300, close=None, ema10=None, deadline='15:15')`
- `Engine.__init__(self, config=None, tick_size=0.05, state=None)`
- `Engine.update(self, candle)`
- `series(candles, config=None, tick_size=0.05)`

### Literal payload and lookup fallbacks

- `ema_gaps` → `[]`
- `session_deadline` → `'15:15'`

### Configuration literals

- `DEFAULTS = dict(atr_length=5, factor=3.0, brick_mode='Auto', manual_brick=12.8, use_adx=False, adx_threshold=20.0, adx_length=14, adx_smoothing=14, widening_window=2, rsi_slope_enabled=True, retest_enabled=False, retest_engulfing=True, retest_harami=True, retest_star=True)`

## backtesting/trailing_exit_research/source_snapshot/trailing_stop.py

[Owning source](../backtesting/trailing_exit_research/source_snapshot/trailing_stop.py)

Optional monotonic full-position trailing exit; no partial profit targets.

### Callables and explicit defaults

- `settings(payload)`
- `advance(state, config, direction, price, exchange_at, received_at, now, opened_at)`

### Literal payload and lookup fallbacks

- `trailing_basis` → `'OPTION_PREMIUM_PERCENT'`
- `trailing_distance` → `10`
- `trailing_enabled` → `False`

## backtesting/trailing_exit_research/summarize.py

[Owning source](../backtesting/trailing_exit_research/summarize.py)

## backtesting/trailing_exit_research/uncertainty.py

[Owning source](../backtesting/trailing_exit_research/uncertainty.py)

Paired day-block bootstrap and observed entry-volatility slices.

## backtesting/trailing_exit_research/verify_outputs.py

[Owning source](../backtesting/trailing_exit_research/verify_outputs.py)

## get_fyers_token.py

[Owning source](../get_fyers_token.py)

Cross-platform entrypoint for interactive Fyers token renewal.

## heatmap_server.py

[Owning source](../heatmap_server.py)

Cross-platform entrypoint for the local sector heat-map server.

## nifty_ema_band_midpoint_live.py

[Owning source](../nifty_ema_band_midpoint_live.py)

NIFTY EMA-band midpoint signal runner.

### Callables and explicit defaults

- `parse_args()`
- `normalize_ohlcv(frame: pd.DataFrame)`
- `fetch_live_bars(interval: str)`
- `fyers_client()`
- `resolve_atm_option(signal: Signal, lots: int)`
- `submit_fyers_order(signal: Signal, trade_symbol: str, quantity: int, args: argparse.Namespace)`
- `validate_fyers_symbol(symbol: str, quantity: int)`
- `manage_signal(signal: Signal, state: dict, args: argparse.Namespace)`
- `session_pass(timestamp: pd.Timestamp, session: str)`
- `build_events(frame: pd.DataFrame, ema_length: int, session: str, cooldown: int, mode: str)`
- `print_candle_check(frame: pd.DataFrame, args: argparse.Namespace)`
- `load_state(path: Path)`
- `record(signals: list[Signal], journal: Path)`
- `main()`

### Literal payload and lookup fallbacks

- `FYERS_APP_ID` → `''`
- `data` → `{}`

## scripts/analyze_mahabank.py

[Owning source](../scripts/analyze_mahabank.py)

Read-only FYERS evidence snapshot for NSE:MAHABANK-EQ.

### Callables and explicit defaults

- `ema(values, period)`
- `rsi(values, period=14)`
- `adx(rows, period=14)`
- `completed(rows, resolution)`
- `history(client, resolution, days)`
- `summarize(rows)`
- `main()`

## scripts/audit_position_history_metadata.py

[Owning source](../scripts/audit_position_history_metadata.py)

Read-only exact-contract historical valuation evidence, no broker API calls.

### Literal payload and lookup fallbacks

- `order_history` → `[]`

## scripts/check_documentation.py

[Owning source](../scripts/check_documentation.py)

Check canonical guide local links, catalog coverage and credential-pattern exclusions.

## scripts/check_ema_cloud_stream.py

[Owning source](../scripts/check_ema_cloud_stream.py)

Bounded read-only stream probe. No runner, orders or settings changes.

## scripts/check_fyers_policy_readiness.py

[Owning source](../scripts/check_fyers_policy_readiness.py)

Read-only readiness check for the FYERS unattended policy.

### Callables and explicit defaults

- `readiness()`

## scripts/check_rsi_table.py

[Owning source](../scripts/check_rsi_table.py)

Read-only live endpoint check; no orders or runner mutation.

## scripts/check_setup.py

[Owning source](../scripts/check_setup.py)

Read-only module readiness. Never constructs runners or contacts a broker.

### Callables and explicit defaults

- `readiness()`

## scripts/check_trade_advisory.py

[Owning source](../scripts/check_trade_advisory.py)

Read-only smoke check: parses a sample plan, fetches market history, calls OpenAI.

## scripts/diagnose_fyers_index_history.py

[Owning source](../scripts/diagnose_fyers_index_history.py)

Read-only FYERS history diagnostic for sector-index symbols.

### Callables and explicit defaults

- `client()`
- `main()`

## scripts/ema_band_historical_check.py

[Owning source](../scripts/ema_band_historical_check.py)

Read-only reconstruction of an EMA-band decision at an IST timestamp.

### Callables and explicit defaults

- `main()`

## scripts/fyers_day_pnl_snapshot.py

[Owning source](../scripts/fyers_day_pnl_snapshot.py)

Read-only FYERS day P&L summary: realised report plus open mark-to-market.

### Callables and explicit defaults

- `number(value)`
- `main()`

## scripts/fyers_positions_snapshot.py

[Owning source](../scripts/fyers_positions_snapshot.py)

Read-only FYERS positions snapshot; never sends an order.

### Callables and explicit defaults

- `main()`

## scripts/generate_source_reference.py

[Owning source](../scripts/generate_source_reference.py)

Generate a secret-free module/settings map from source without imports or execution.

### Callables and explicit defaults

- `source_files()`
- `render()`

## scripts/nifty_completed_30m_snapshot.py

[Owning source](../scripts/nifty_completed_30m_snapshot.py)

Read-only FYERS NIFTY completed 30-minute candle snapshot.

### Callables and explicit defaults

- `main()`

## scripts/nifty_daily_swing_snapshot.py

[Owning source](../scripts/nifty_daily_swing_snapshot.py)

Read-only FYERS NIFTY daily swing snapshot; never sends an order.

### Callables and explicit defaults

- `ema(values: list[float], period: int)`
- `rsi(values: list[float], period: int=14)`
- `main()`

## scripts/nifty_expiry_snapshot.py

[Owning source](../scripts/nifty_expiry_snapshot.py)

Read-only FYERS NIFTY expiry snapshot. This module never places orders.

### Callables and explicit defaults

- `_client()`
- `_completed(candles, minutes, now)`
- `_ema(values, period)`
- `_spread(rows, spot, direction, lot_size)`
- `main()`

### Literal payload and lookup fallbacks

- `data` → `{}`

## scripts/nifty_iron_condor_snapshot.py

[Owning source](../scripts/nifty_iron_condor_snapshot.py)

Read-only live FYERS NIFTY iron-condor quote and payoff snapshot.

### Callables and explicit defaults

- `quote(row: dict, side: int)`
- `main()`

### Literal payload and lookup fallbacks

- `data` → `{}`

## scripts/package_release.py

[Owning source](../scripts/package_release.py)

Build and validate a source-only deployable from an exact Git commit.

### Callables and explicit defaults

- `build(ref='HEAD', output=None)`

## scripts/preview_trade_advisory.py

[Owning source](../scripts/preview_trade_advisory.py)

Isolated UI fixture preview. GET-only server; no broker or OpenAI calls.

### Callables and explicit defaults

- `Handler.do_GET(self)`
- `Handler.log_message(self, *args)`

## scripts/probe_rsi_table_history.py

[Owning source](../scripts/probe_rsi_table_history.py)

Read-only provider resolution diagnosis; sanitized metadata only.

### Literal payload and lookup fallbacks

- `candles` → `[]`

## scripts/rank_chartink_candidates.py

[Owning source](../scripts/rank_chartink_candidates.py)

Read-only FYERS ranking for a supplied Chartink cash-equity shortlist.

### Callables and explicit defaults

- `summary(rows)`
- `score(daily, hourly, quote)`
- `main()`

### Literal payload and lookup fallbacks

- `d` → `[]`
- `v` → `{}`

## scripts/refresh_official_weights.py

[Owning source](../scripts/refresh_official_weights.py)

Validate and atomically install a reviewed monthly NSE weight dataset.

### Callables and explicit defaults

- `install_candidate(candidate_path, destination=DATA_DIRECTORY, check_only=False)`
- `main()`

## scripts/render_user_functional_guide.py

[Owning source](../scripts/render_user_functional_guide.py)

Render the repository's small Markdown functional guide without dependencies.

### Callables and explicit defaults

- `inline(text)`
- `render()`

## scripts/save_default_fyers_paper_policy.py

[Owning source](../scripts/save_default_fyers_paper_policy.py)

Save the requested disabled FYERS PAPER policy draft.

### Callables and explicit defaults

- `exact_equity_universe()`
- `validate_index_option_support(client)`
- `main()`

### Literal payload and lookup fallbacks

- `data` → `{}`
- `message` → `'FYERS profile validation failed.'`
- `optionsChain` → `[]`

## scripts/suggest_high_conviction_spreads.py

[Owning source](../scripts/suggest_high_conviction_spreads.py)

Read-only FYERS defined-risk spread proposals for current bullish candidates.

### Callables and explicit defaults

- `requested_candidates(argv)`
- `main()`

### Literal payload and lookup fallbacks

- `data` → `{}`
- `optionsChain` → `[]`

## scripts/verify_redbar_zones.py

[Owning source](../scripts/verify_redbar_zones.py)

Independent Python reference for the checked-in Red Bar Pine zone algorithm.

### Callables and explicit defaults

- `reference(candles, symbol, tick)`

## sector_heatmap/__init__.py

[Owning source](../sector_heatmap/__init__.py)

Local Fyers-powered NSE sector heat-map application.

## sector_heatmap/analysis.py

[Owning source](../sector_heatmap/analysis.py)

Explainable multi-timeframe sector scoring, ranking, and rotation logic.

### Callables and explicit defaults

- `_round(value, digits=2)`
- `state_from_score(score)`
- `rsi_state(value)`
- `_structure_score(close, ema20, ema50, ema200)`
- `_relative_strength(pairs)`
- `calculate_timeframe_state(timeframe, candles, benchmark_candles, data_quality='DELAYED')`
- `weighted_available(values, weights)`
- `mtf_alignment(timeframe_states)`
- `calculate_sector(sector, timeframe_states, mode='intraday', constituent_metrics=None)`
- `rank_sectors(sectors, previous_ranks=None)`
- `_distinct_prior_rotation_history(current, history)`
- `classify_rotation(current, history)`
- `detect_events(previous, current)`
- `market_overview(sectors, benchmark_states)`

### Literal payload and lookup fallbacks

- `breadth` → `[]`
- `daily` → `{}`
- `timeframe_states` → `{}`
- `volume` → `[]`
- `weekly` → `{}`

## sector_heatmap/analysis_config.py

[Owning source](../sector_heatmap/analysis_config.py)

Central configuration for deterministic multi-timeframe sector analysis.

### Configuration literals

- `TIMEFRAMES = {'15m': {'resolution': '15', 'lookback_days': 45, 'ttl_seconds': 15 * 60, 'stale_seconds': 2 * 60 * 60}, '1h': {'resolution': '60', 'lookback_days': 180, 'ttl_seconds': 60 * 60, 'stale_seconds': 4 * 60 * 60}, 'daily': {'resolution': 'D', 'lookback_days': 1700, 'ttl_seconds': 60 * 60, 'stale_seconds': 4 * 24 * 60 * 60}, 'weekly': {'resolution': 'D', 'lookback_days': 1700, 'ttl_seconds': 6 * 60 * 60, 'stale_seconds': 11 * 24 * 60 * 60, 'derive': 'weekly'}}`
- `TREND_WEIGHTS = {'structure': 0.4, 'slope': 0.2, 'rsi': 0.2, 'dmi': 0.2}`
- `MOMENTUM_WEIGHTS = {'rsi': 0.45, 'roc': 0.3, 'ema_slope': 0.25}`
- `SECTOR_SCORE_WEIGHTS = {'trend': 0.25, 'relative_strength': 0.25, 'breadth': 0.2, 'volume': 0.15, 'momentum': 0.15}`
- `MTF_MODES = {'intraday': {'15m': 0.3, '1h': 0.4, 'daily': 0.25, 'weekly': 0.05}, 'swing': {'15m': 0.0, '1h': 0.1, 'daily': 0.5, 'weekly': 0.4}}`
- `ROTATION = {'minimum_snapshots': 2, 'leading_score': 70, 'improving_score': 55, 'lagging_score': 35, 'velocity_threshold': 1.0, 'acceleration_threshold': 0.75, 'history_limit': 120}`

## sector_heatmap/auth_refresh.py

[Owning source](../sector_heatmap/auth_refresh.py)

Refresh FYERS resources without restarting the shared process or other brokers.

### Callables and explicit defaults

- `refresh_fyers_session(code, exchange, load, replace, state)`

## sector_heatmap/authentication.py

[Owning source](../sector_heatmap/authentication.py)

Fyers OAuth browser flow and local callback capture.

### Callables and explicit defaults

- `create_session(cfg, state=None)`
- `validated_config(expected_port=None)`
- `authorization_url(expected_port=None, state=None)`
- `exchange_auth_code(auth_code)`
- `refresh_access_token()`

## sector_heatmap/automation.py

[Owning source](../sector_heatmap/automation.py)

Disabled-by-default FYERS unattended-policy authoring and audit support.

### Callables and explicit defaults

- `_policy_digest(policy)`
- `_finite(value, label, minimum=None, maximum=None, integer=False)`
- `_clock(value, label)`
- `validate_automation_policy(raw)`
- `policy_summary(policy)`
- `HashChainAuditLog.__init__(self, path=AUDIT_PATH, now=None)`
- `HashChainAuditLog._rows(self)`
- `HashChainAuditLog.append(self, event, detail)`
- `HashChainAuditLog.verify(self)`
- `AutomationPolicyService.__init__(self, profile_path=PROFILE_PATH, audit=None, now=None)`
- `AutomationPolicyService.current(self)`
- `AutomationPolicyService.preview(self, raw)`
- `AutomationPolicyService.save(self, preview_id, acknowledgement)`
- `AutomationPolicyService.save_draft(self, raw)`
- `AutomationPolicyService.evaluate_order(self, context)`
- `AutomationPolicyService.halt(self, reference, reason)`
- `AutomationPolicyService.halt_uncertain(self, reference)`

### Literal payload and lookup fallbacks

- `allowed_segments` → `[]`
- `allowed_strategies` → `[]`
- `allowed_symbols` → `[]`
- `completed_candle_conditions` → `[]`
- `dte` → `-1`
- `full_alignment` → `''`
- `kill_switch_engaged` → `True`
- `max_bid_ask_spread_pct` → `0`
- `max_concurrent_orders` → `0`
- `max_concurrent_positions` → `0`
- `max_daily_loss` → `0`
- `max_dte` → `-1`
- `max_limit_buffer_pct` → `0`
- `min_dte` → `0`
- `minutes_since_last_order` → `0`
- `order_type` → `''`
- `per_idea_risk` → `0`
- `reference` → `''`
- `reference` → `'unknown'`
- `required_alignment_values` → `[]`
- `reward_to_risk` → `0`
- `segment` → `''`
- `stale_data_seconds` → `0`
- `strategy` → `''`
- `supported_index_underlyings` → `[]`
- `symbol` → `''`
- `trading_end` → `'00:00'`
- `trading_start` → `'99:99'`

## sector_heatmap/config.py

[Owning source](../sector_heatmap/config.py)

### Callables and explicit defaults

- `_read_env_file(path)`
- `_normalize_aliases(values)`
- `_user_config_files()`
- `_read_token_cache()`
- `load_config()`
- `_atomic_private_write(path, content)`
- `save_access_token(token)`

### Literal payload and lookup fallbacks

- `FYERS_APP_ID` → `''`
- `HEATMAP_PORT` → `'8080'`

## sector_heatmap/delta_adaptive.py

[Owning source](../sector_heatmap/delta_adaptive.py)

Causal rolling research and guarded candidate selection; no trading mutations.

### Callables and explicit defaults

- `digest(value)`
- `regimes(rows)`
- `score(metrics)`
- `evidence(records, at, regime, min_trades)`
- `select_candidate(ranking, incumbent, state, at, regime, library, cfg)`
- `walk_forward(raw, combinations, settings, units, tick, config, prior_library=None, cancel=None, progress=None)`
- `AdaptiveResearch.__init__(self, root, read, metadata, workspace, clock=time.time, ai=None, can_run=None)`
- `AdaptiveResearch.save(self)`
- `AdaptiveResearch.limits(self)`
- `AdaptiveResearch.status(self)`
- `AdaptiveResearch.configure(self, payload)`
- `AdaptiveResearch._plan(self, c)`
- `AdaptiveResearch.run(self, _=None)`
- `AdaptiveResearch.start_loop(self, _=None)`
- `AdaptiveResearch.stop_loop(self, _=None)`
- `AdaptiveResearch.cancel(self, _=None)`
- `AdaptiveResearch._schedule(self)`
- `AdaptiveResearch.update(self, **values)`
- `AdaptiveResearch._data(self, c, cancel)`
- `AdaptiveResearch._cycle(self, c, cancel)`
- `AdaptiveResearch._forward(self, rows, product, c, settings, sealed, result, units, tick)`
- `AdaptiveResearch.proposal(self, ident)`
- `AdaptiveResearch.add_proposals(self, _=None)`
- `AdaptiveResearch.holdout_once(self, payload)`
- `AdaptiveResearch._score_holdout(self, sealed, ident, entry)`

### Literal payload and lookup fallbacks

- `asof` → `0`
- `experiments` → `[]`
- `interval` → `0`
- `last_switch` → `-1e+30`
- `latest` → `{}`
- `records` → `[]`
- `streak` → `0`

### Configuration literals

- `DEFAULTS = dict(symbol='BTCUSD', resolution='5m', rsi_lengths=[10, 14, 21], ma_lengths=[14], ma_types=['EMA'], filters=['BASELINE', 'EXPANDING', 'SQUEEZE_RELEASE'], history_bars=3600, train_bars=600, validation_bars=200, holdout_bars=300, min_train_trades=15, min_validation_trades=20, improvement_margin=0.05, persistence=2, cooldown_bars=400, cadence_minutes=60, capital=10000, contracts=10, fee_bps=6, slippage_bps=2, half_spread_bps=1, funding_bps_day=0, adx_enabled=True, adx_thresholds=[25], momentum_enabled=True, bb_lengths=[20], bb_deviation=2, squeeze_lookback=100, squeeze_percentile=20, release_bars=3, entry_rule='CURRENT', direction='BOTH', ai_enabled=False, ai_calls_per_day=2, ai_tokens_per_day=12000, ai_max_output_tokens=400, ai_model='gpt-4.1-mini')`

## sector_heatmap/delta_adx.py

[Owning source](../sector_heatmap/delta_adx.py)

Wilder ADX(14) on completed candles only; optional runner entry gate.

### Callables and explicit defaults

- `series(candles, period=14)`
- `settings(payload)`
- `allows(cfg, value)`

### Literal payload and lookup fallbacks

- `adx_enabled` → `False`
- `adx_threshold` → `25`

## sector_heatmap/delta_backtest.py

[Owning source](../sector_heatmap/delta_backtest.py)

Bounded, public-data-only Delta futures research. No execution dependencies.

### Callables and explicit defaults

- `number(value, name, low, high, integer=False)`
- `choices(payload, name, default, allowed=None, numeric=None)`
- `numeric_choices(payload, name, legacy, default, low, high, integer=False)`
- `boolean_choices(payload, name, legacy)`
- `plan(payload, now=None)`
- `audit(raw, interval, start, end, now)`
- `coverage(rows, bounds)`
- `bollinger_features(rows, cfg)`
- `adverse_fill(price, side, settings, tick)`
- `simulate(rows, features, adx, cfg, settings, units, tick, start, end)`
- `DeltaBacktest.__init__(self, root, read, metadata, clock=time.time)`
- `DeltaBacktest.inspect(self, payload)`
- `DeltaBacktest.status(self)`
- `DeltaBacktest.detail(self, ident)`
- `DeltaBacktest.start(self, payload)`
- `DeltaBacktest.cancel(self, _=None)`
- `DeltaBacktest._update(self, **values)`
- `DeltaBacktest._fetch(self, symbol, resolution, bounds, cancel)`
- `DeltaBacktest._run(self, config, cancel)`

### Literal payload and lookup fallbacks

- `capital` → `10000`
- `contracts` → `10`
- `direction` → `'BOTH'`
- `entry_rule` → `'CURRENT'`
- `fee_bps` → `6`
- `funding_bps_day` → `0`
- `half_spread_bps` → `1`
- `holdout_percent` → `30`
- `slippage_bps` → `2`
- `symbol` → `'BTCUSD'`

### Configuration literals

- `INTERVALS = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '6h': 21600, '1d': 86400}`

## sector_heatmap/delta_backtest_server.py

[Owning source](../sector_heatmap/delta_backtest_server.py)

Loopback-only public-data research worker, independent of broker runners.

### Callables and explicit defaults

- `public_read(path, params=None)`
- `public_metadata(symbol)`
- `handler(service, agent=None)`
- `main()`
- `ensure_research_worker()`

### Literal payload and lookup fallbacks

- `Content-Length` → `'0'`
- `Origin` → `'http://127.0.0.1:8080'`

## sector_heatmap/delta_currency.py

[Owning source](../sector_heatmap/delta_currency.py)

Read-only verification of Delta India's fixed settlement conversion policy.

### Callables and explicit defaults

- `policy(path, now=None, fetch=None)`

## sector_heatmap/delta_history.py

[Owning source](../sector_heatmap/delta_history.py)

Public completed-candle archive, independent of execution ledgers.

### Callables and explicit defaults

- `CandleArchive.__init__(self, path, mirror=None)`
- `CandleArchive.watch(self, product, resolution)`
- `CandleArchive.ingest(self, product, resolution, rows, interval, now)`
- `CandleArchive.fail(self, symbol, resolution, error)`
- `CandleArchive.read(self, symbol, resolution, limit=10000)`
- `CandleArchive.watches(self)`
- `CandleArchive.export(self, symbol, resolution)`
- `CandleArchive._export(self, symbol, resolution)`

## sector_heatmap/delta_india.py

[Owning source](../sector_heatmap/delta_india.py)

### Callables and explicit defaults

- `DeltaIndia.__init__(self, state_path, credentials=lambda: {}, requester=None, clock=time.time)`
- `DeltaIndia._remember_monitor(self, position, cfg)`
- `DeltaIndia._monitor_checkpoint(self)`
- `DeltaIndia._exit_only_finished(self)`
- `DeltaIndia.restore_exit_monitor(self, payload=None)`
- `DeltaIndia.start_monitoring_supervisor(self)`
- `DeltaIndia._get(self, path, params=None, private=False)`
- `DeltaIndia._credentials(self)`
- `DeltaIndia._identity(self)`
- `DeltaIndia._gate(self)`
- `DeltaIndia.status(self)`
- `DeltaIndia.configure(self, payload)`
- `DeltaIndia._private(self, method, path, params=None, body=None, credentials=None)`
- `DeltaIndia.verify_auth(self)`
- `DeltaIndia._number(value)`
- `DeltaIndia.account(self, payload=None)`
- `DeltaIndia._write(self, path, data)`
- `DeltaIndia._save_live(self)`
- `DeltaIndia.catalog(self)`
- `DeltaIndia._metadata(self, r)`
- `DeltaIndia.product(self, symbol)`
- `DeltaIndia.ticker(self, symbol)`
- `DeltaIndia.chart_option(self, symbol, direction)`
- `DeltaIndia._chart_intent(self, payload, paper=False)`
- `DeltaIndia._rsi_intent(self, payload, symbol, wanted, prefix='')`
- `DeltaIndia._manual_intent(self, payload, symbol, wanted, prefix='')`
- `DeltaIndia._execution_intent(self, payload, paper=False, runner=False)`
- `DeltaIndia._inr_conversion(self)`
- `DeltaIndia._journal_context(self, payload, reason, signal_close=None)`
- `DeltaIndia._paper_reduction(self, payload)`
- `DeltaIndia.chart(self, symbol, resolution='5m', rsi_length=14, ma_length=14, ma_type='SMA')`
- `DeltaIndia.saved_history(self, symbol, resolution='5m')`
- `DeltaIndia.start_history(self)`
- `DeltaIndia._history_loop(self)`
- `DeltaIndia._paper_contract(self, symbol)`
- `DeltaIndia._paper_funds_status(self)`
- `DeltaIndia.paper_funds(self, initial=None)`
- `DeltaIndia.paper_commitment(self, initial, notional, product)`
- `DeltaIndia.preview(self, payload, runner=False)`
- `DeltaIndia._save(self)`
- `DeltaIndia.record_paper(self, payload)`
- `DeltaIndia.close_paper(self, payload)`
- `DeltaIndia._position(self, product_id)`
- `DeltaIndia._live_ready(self)`
- `DeltaIndia._validate_order(self, payload, runner=False)`
- `DeltaIndia._apply_order(self, owned, r)`
- `DeltaIndia.submit(self, payload, runner=False)`
- `DeltaIndia.submit_discretionary(self, payload)`
- `DeltaIndia._owned(self, payload)`
- `DeltaIndia.reconcile(self, payload)`
- `DeltaIndia.cancel(self, payload)`
- `DeltaIndia.fills(self, payload)`
- `DeltaIndia._submit_config(self, payload)`
- `DeltaIndia._stage_submit(self, owned)`
- `DeltaIndia._launch_monitor(self)`
- `DeltaIndia._activate_submit(self, owned)`
- `DeltaIndia._begin_submit(self, payload, position)`
- `DeltaIndia._submit_complete(self)`
- `DeltaIndia._missed_exit(self, snapshot, position, cfg)`
- `DeltaIndia._latch_exit(self, position, signal, mode)`
- `DeltaIndia._finish_latched_exit(self, position, cfg)`
- `DeltaIndia._submit_tick(self)`
- `DeltaIndia.start_runner(self, payload)`
- `DeltaIndia.resume_paper_runner(self, payload=None)`
- `DeltaIndia.stop_runner(self, payload=None)`
- `DeltaIndia._settle_runner(self)`
- `DeltaIndia._prepare_atr(self, symbol, cfg)`
- `DeltaIndia._runner_order(self, side, size, reduce, action, signal_close=None, symbol=None, signal_direction=None, entry_reason=None)`
- `DeltaIndia.runner_tick(self)`
- `DeltaIndia._signal_side(self, position, cfg)`
- `DeltaIndia._enter_atm_option(self, cfg, last, direction, close)`
- `DeltaIndia.close_runner(self, payload)`
- `DeltaIndia._paper_reduce(self, size, reason, stage=None, signal_close=None, signal_direction=None)`
- `DeltaIndia._manage_trailing(self)`
- `DeltaIndia._run(self, event)`

### Literal payload and lookup fallbacks

- `DELTA_INDIA_ENABLE_LIVE_ORDERS` → `'1'`
- `DELTA_MCP_ENV` → `'india_prod'`
- `_runner_origin` → `False`
- `adx_threshold` → `25`
- `available_balance` → `'0'`
- `candle` → `{}`
- `candles` → `[]`
- `config` → `{}`
- `direction` → `'BOTH'`
- `error` → `'Delta runner order rejected; runner stopped.'`
- `execution_reason` → `'MANUAL'`
- `exit_reason` → `'TRAILING_STOP'`
- `filled_contracts` → `0`
- `journal_fills` → `[]`
- `mode` → `'PAPER'`
- `order_type` → `'limit_order'`
- `orders` → `{}`
- `owned_reduction_applied` → `0`
- `paper_capital_inr` → `100000`
- `realized_pnl` → `0`
- `reason` → `'EXPLICIT_CLOSE'`
- `reduce_only` → `False`
- `resolution` → `'5m'`
- `side` → `'LONG'`
- `strategy_mode` → `'CONTRACT'`
- `time_in_force` → `'ioc'`
- `trades` → `[]`

### Configuration literals

- `RESOLUTIONS = {'1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '2h': 7200, '4h': 14400, '6h': 21600, '1d': 86400, '1w': 604800}`

## sector_heatmap/delta_journal.py

[Owning source](../sector_heatmap/delta_journal.py)

Event-time public indicator evidence; never a trading decision or backfill.

### Callables and explicit defaults

- `snapshot(analysis, settings, observed_at, reason, signal_close=None)`

### Literal payload and lookup fallbacks

- `adx_enabled` → `False`
- `adx_threshold` → `25`
- `candles` → `[]`
- `momentum_enabled` → `False`

## sector_heatmap/delta_journal_export.py

[Owning source](../sector_heatmap/delta_journal_export.py)

Local XLSX export using the installed Codex spreadsheet runtime.

### Callables and explicit defaults

- `export_xlsx(data, root)`

## sector_heatmap/delta_lifecycle.py

[Owning source](../sector_heatmap/delta_lifecycle.py)

Read-only weighted-average position accounting from broker fill snapshots.

### Callables and explicit defaults

- `number(value)`
- `lifecycles(fills, positions, history_complete)`

## sector_heatmap/delta_monitoring.py

[Owning source](../sector_heatmap/delta_monitoring.py)

Position-specific exit monitoring evidence and health; chart preferences are irrelevant.

### Callables and explicit defaults

- `saved_paper_config(position)`
- `health(position, runner, now)`

### Literal payload and lookup fallbacks

- `error` → `''`

## sector_heatmap/delta_research_ai.py

[Owning source](../sector_heatmap/delta_research_ai.py)

Bounded, cached OpenAI experiment reviews. Never price/decision/order calls.

### Callables and explicit defaults

- `existing_key(workspace)`
- `ResearchAI.__init__(self, path, workspace, clock=time.time, sender=None, key_reader=None)`
- `ResearchAI.save(self)`
- `ResearchAI.day(self)`
- `ResearchAI.status(self, limits)`
- `ResearchAI._send(self, key, model, input_text, max_output)`
- `ResearchAI.review(self, evidence, limits)`

### Literal payload and lookup fallbacks

- `content` → `[]`
- `error` → `{}`
- `experiments` → `[]`
- `output` → `[]`
- `reason` → `''`
- `text` → `''`
- `usage` → `{}`

## sector_heatmap/delta_signals.py

[Owning source](../sector_heatmap/delta_signals.py)

Delta completed-bar entries; exits continue to use cross_direction only.

### Callables and explicit defaults

- `momentum_settings(payload)`
- `momentum_evidence(row, prior)`
- `momentum_allows(cfg, row, direction)`
- `delta_rsi_series(candles, rsi_length=14, ma_length=14, ma_type='SMA')`

### Literal payload and lookup fallbacks

- `momentum_enabled` → `False`

## sector_heatmap/delta_trailing.py

[Owning source](../sector_heatmap/delta_trailing.py)

Fixed entry-based steps on executable Delta bids (long) or asks (short).

### Callables and explicit defaults

- `settings(payload)`
- `initial(entry, tick, quantity, side, config)`
- `advance(state, quote, now, atr=None, atr_candle=None)`
- `target(state, remaining)`
- `atr_value(candles, period=14)`

### Literal payload and lookup fallbacks

- `trailing_enabled` → `False`
- `trailing_mode` → `'PERCENTAGE'`

## sector_heatmap/equity_exit_plan.py

[Owning source](../sector_heatmap/equity_exit_plan.py)

Planning-only cash-equity exit plans; contains no broker mutations.

### Callables and explicit defaults

- `build_equity_exit_plan(direction, quantity, entry, target, mode='FIXED_TARGET')`
- `advance_exit_plan(plan, event, candle=None)`

## sector_heatmap/file_lock.py

[Owning source](../sector_heatmap/file_lock.py)

OS-backed cross-process locks; never silently fall back to thread-only locks.

### Callables and explicit defaults

- `lock_file(fd, blocking=True)`
- `unlock_file(fd)`

## sector_heatmap/fyers_execution.py

[Owning source](../sector_heatmap/fyers_execution.py)

FYERS-only, confirmation-gated ticket preparation and reconciliation.

### Callables and explicit defaults

- `PreviewChanged.__init__(self, preview)`
- `_require_cash_session(now)`
- `_fresh_market_state(now, instrument)`
- `_number(value, default=None)`
- `_ok(response)`
- `_message(response, fallback)`
- `_current_client(client_factory=None)`
- `_fresh_depth_quote(client, symbol, now)`
- `DailyRiskLedger.__init__(self, path=RISK_LEDGER_PATH)`
- `DailyRiskLedger._load(self)`
- `DailyRiskLedger.entries(self, day=None)`
- `DailyRiskLedger.append(self, entry, day=None)`
- `DailyRiskLedger.open_risk(self, day=None)`
- `available_funds(response)`
- `_positions(response)`
- `_orders(response)`
- `_quotes(response)`
- `_round_tick(price, tick)`
- `_realized_loss(positions)`
- `option_order_policy(expiry_iso, trading_day)`
- `_order_ids(response)`
- `FyersExecutionService.__init__(self, client_factory=None, master=None, cm_master=None, ledger=None, now=None, execution_halt=None, live_gate_name='SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS', live_gate=None, equity_margin_provider=None)`
- `FyersExecutionService.capabilities(self)`
- `FyersExecutionService._live_submission_enabled(self)`
- `FyersExecutionService._risk_settings(payload)`
- `FyersExecutionService._preflight_option_spread(self, client, payload, proposal, minimum_rr)`
- `FyersExecutionService._preflight_long_option(self, client, payload, proposal, minimum_rr)`
- `FyersExecutionService._equity_leverage(self, symbol)`
- `FyersExecutionService._preflight_equity(self, client, payload, proposal, invalidation, minimum_rr)`
- `FyersExecutionService._preflight(self, payload)`
- `FyersExecutionService.prepare(self, payload)`
- `FyersExecutionService._budget_equity_batch(self, payload, items)`
- `FyersExecutionService._batch_preflight(self, payload)`
- `FyersExecutionService.prepare_batch(self, payload)`
- `FyersExecutionService.submit_batch(self, preview_id, confirmation)`
- `FyersExecutionService._submit_option_batch(self, preview_id, refreshed)`
- `FyersExecutionService.submit(self, preview_id, confirmation)`

### Literal payload and lookup fallbacks

- `broker` → `''`
- `contracts` → `[{}]`
- `data` → `[]`
- `data` → `{}`
- `net_qty` → `0`
- `optionsChain` → `[]`
- `quote` → `{}`
- `realizedProfit` → `0`
- `warnings` → `[]`

## sector_heatmap/handoff.py

[Owning source](../sector_heatmap/handoff.py)

Local analysis handoff and read-only FYERS option-spread construction.

### Callables and explicit defaults

- `_positive_number(value: Any)`
- `risk_budget(planning_capital, max_loss_value, max_loss_unit)`
- `validate_risk_policy(policy)`
- `_invalidation_price(entry, direction, risk)`
- `size_equity_candidate(candidate, risk, available_funds=None)`
- `build_equity_opportunity(candidate, policy)`
- `apply_invalidation_choice(candidate, opportunity, policy, selection, tick_size=0.05, option_proposal=None)`
- `evidence_conviction(candidate, opportunity, option_proposal=None)`
- `FyersFoMaster.__init__(self, cache_path=FYERS_FO_MASTER_CACHE, requester=None, now=None, master_url=FYERS_FO_MASTER_URL)`
- `FyersFoMaster._content(self)`
- `FyersFoMaster.lookup(self, symbols)`
- `FyersCmMaster.__init__(self, cache_path=FYERS_CM_MASTER_CACHE, requester=None, now=None)`
- `fetch_fyers_chain(client, underlying_symbol, strike_count=8)`
- `_leg(chain_item, master)`
- `_spread(identifier, label, direction, strategy, long_leg, short_leg, width, scenario)`
- `_nearest_pair(legs, spot, long_higher=False)`
- `build_defined_risk_spreads(chain_payload, expiry, master_records, direction, risk=None)`
- `build_long_option_proposals(chain_payload, expiry, master_records, direction, risk=None)`
- `validate_handoff_request(payload)`
- `packet_prompt(recipient)`

### Literal payload and lookup fallbacks

- `action` → `''`
- `data` → `{}`
- `expiry` → `''`
- `recipient` → `''`
- `relative_strength_state` → `'available relative-strength'`
- `risk_reserve` → `''`
- `risk_reserve` → `-1`
- `sizing` → `{}`

## sector_heatmap/indicators.py

[Owning source](../sector_heatmap/indicators.py)

Dependency-free technical indicators used by the sector domain engine.

### Callables and explicit defaults

- `clamp(value, low=0.0, high=100.0)`
- `ema(values, length)`
- `true_ranges(candles)`
- `wilder_series(values, length)`
- `atr(candles, length=14)`
- `rsi(values, length=14)`
- `roc(values, length=10)`
- `normalized_slope(series, atr_value, lookback=5)`
- `adx_dmi(candles, length=14)`
- `resample_weekly(candles)`
- `align_closes(sector_candles, benchmark_candles)`
- `breadth_score(constituents)`
- `volume_participation_score(constituents)`
- `finite_or_none(value)`

### Literal payload and lookup fallbacks

- `change` → `0`
- `relative_strength_score` → `50`
- `volume` → `0`

## sector_heatmap/kama_strategy.py

[Owning source](../sector_heatmap/kama_strategy.py)

Independent completed-candle KAMA V6 signal engine.

### Callables and explicit defaults

- `kama_exit_state_machine(signal, completed_candle, broker_state='UNKNOWN')`
- `kama_entry_policy_decision(signal, policy, account_position_exists=False)`
- `_in_session(timestamp, session)`
- `kama_series(candles, kama_length=10, fast_length=2, slow_length=30)`
- `kama_v6_signal(candles, position=0, last_long_exit_bar=None, last_short_exit_bar=None, kama_length=10, fast_length=2, slow_length=30, minimum_efficiency=0.35, breakout_bars=5, cooldown_bars=2, allow_reclaims=True, slope_lookback=8, minimum_slope_atr=0.1, entry_session='0915-1510', squareoff_session='1515-1530')`

## sector_heatmap/market_calendar.py

[Owning source](../sector_heatmap/market_calendar.py)

NSE capital-market trading sessions used to interpret data freshness.

### Callables and explicit defaults

- `_as_ist(moment)`
- `is_trading_day(day)`
- `previous_trading_day(day)`
- `next_trading_day(day)`
- `market_session(moment=None)`

## sector_heatmap/market_data.py

[Owning source](../sector_heatmap/market_data.py)

### Callables and explicit defaults

- `is_token_error(message)`
- `provider_tick_timestamp(tick)`
- `tick_timestamp_iso(value)`
- `_percentage_change(ltp, previous)`
- `configure_websocket_ca_bundle()`
- `FyersLiveFeed.__init__(self, access_token)`
- `FyersLiveFeed.start(self)`
- `FyersLiveFeed.stop(self)`
- `FyersLiveFeed.snapshot(self)`

### Literal payload and lookup fallbacks

- `x509_ca` → `0`

## sector_heatmap/nifty_straddle.py

[Owning source](../sector_heatmap/nifty_straddle.py)

Guarded process bridge for the external NIFTY long-straddle runner.

### Callables and explicit defaults

- `NiftyStraddleService.__init__(self, script_path=None, credential_provider=None, process_factory=None, runtime_dir=None)`
- `NiftyStraddleService.state_path(self)`
- `NiftyStraddleService.trades_path(self)`
- `NiftyStraddleService.chart_path(self)`
- `NiftyStraddleService.snapshot(self)`
- `NiftyStraddleService.start(self, mode='live', lots=1, stoploss=15, target=30, exit_mode='supertrend', entry_start='09:15', entry_end='11:30', confirmation='', paper_capital_inr=100000)`
- `NiftyStraddleService.stop(self)`

### Literal payload and lookup fallbacks

- `ENTRY_WINDOW_END_TIME` → `'11:30'`
- `ENTRY_WINDOW_START_TIME` → `'09:15'`
- `EOD_SQUARE_OFF_TIME` → `'—'`
- `MAX_REENTRIES_PER_DAY` → `1`
- `STOPLOSS_POINTS` → `15`
- `SUPER_TREND_ACTIVATION_POINTS` → `10`
- `SUPER_TREND_MULTIPLIER` → `3`
- `SUPER_TREND_PERIOD` → `7`
- `TARGET_POINTS` → `30`
- `VOL_LOOKBACK_DAYS` → `'—'`
- `VOL_PERCENTILE` → `'—'`

## sector_heatmap/official_weights.py

[Owning source](../sector_heatmap/official_weights.py)

Validated, versioned official NSE Indices factsheet weights.

### Callables and explicit defaults

- `OfficialIndexWeights.weight_coverage_pct(self)`
- `OfficialIndexWeights.is_complete(self)`
- `OfficialIndexWeights.provenance(self)`
- `OfficialWeightSet.summary(self)`
- `validate_weight_document(document)`
- `load_weight_document(path)`
- `latest_weight_file(data_directory=DATA_DIRECTORY)`
- `load_latest_weight_set(data_directory=DATA_DIRECTORY)`

## sector_heatmap/paper_wallet.py

[Owning source](../sector_heatmap/paper_wallet.py)

Finite INR wallet for legacy simulation lifecycles; no broker API access.

### Callables and explicit defaults

- `capital(value=100000)`
- `wallet(initial=100000, realized=0, fees=0, reserved=0)`
- `reserve(current, notional, fee_rate=0.005)`
- `release(current, notional, realized, fee_rate=0.005)`

## sector_heatmap/parser_lifecycle.py

[Owning source](../sector_heatmap/parser_lifecycle.py)

Durable parser attribution and broker OCO protection; mutation is opt-in.

### Callables and explicit defaults

- `protection_plan(parsed, contract, order, selected_target=None)`
- `ParserLifecycle.__init__(self, path, broker, enabled=lambda: False)`
- `ParserLifecycle.mutation_lock(self)`
- `ParserLifecycle._save(self, key, data)`
- `ParserLifecycle.rows(self)`
- `ParserLifecycle.submit_entry(self, ticket)`
- `ParserLifecycle.reconcile(self, key)`
- `ParserLifecycle._reconcile(self, row)`

### Literal payload and lookup fallbacks

- `netQty` → `0`
- `orderTag` → `''`

## sector_heatmap/parser_protection_broker.py

[Owning source](../sector_heatmap/parser_protection_broker.py)

FYERS adapter used only by explicitly enabled future parser protection.

### Callables and explicit defaults

- `ParserProtectionBroker.snapshot(self)`
- `ParserProtectionBroker.fresh_price(self, symbol)`
- `ParserProtectionBroker.place_entry(self, order)`
- `ParserProtectionBroker.place_oco(self, order)`

## sector_heatmap/parser_quote.py

[Owning source](../sector_heatmap/parser_quote.py)

Read-only last-traded-price display for an already resolved parser contract.

### Callables and explicit defaults

- `fetch_parser_quote(symbol, token, get=requests.get, now=None)`

### Literal payload and lookup fallbacks

- `Retry-After` → `60`
- `d` → `[]`

## sector_heatmap/parser_submission.py

[Owning source](../sector_heatmap/parser_submission.py)

Durable at-most-once guard for a deliberate parser Submit action.

### Callables and explicit defaults

- `ParserSubmissionGuard.__init__(self, path)`
- `ParserSubmissionGuard.submit(self, key, payload, callback)`

## sector_heatmap/portable_journal.py

[Owning source](../sector_heatmap/portable_journal.py)

Portable static evidence exports. Recorded values are never recomputed as fills.

### Callables and explicit defaults

- `_text(value)`
- `_rows(sheet, records)`
- `export_journal(data, kind)`

### Literal payload and lookup fallbacks

- `orders` → `[]`
- `paper` → `{}`
- `state` → `{}`
- `trades` → `[]`

## sector_heatmap/rsi_table.py

[Owning source](../sector_heatmap/rsi_table.py)

Read-only multi-timeframe RSI. Does not import any order/runner service.

### Callables and explicit defaults

- `session_bounds(symbol, day)`
- `period_end(symbol, stamp, resolution)`
- `normalize(raw)`
- `aggregate_6h(raw, symbol, now)`
- `RsiTable.__init__(self)`
- `RsiTable.history(self, client, symbol, resolution, target, now)`
- `RsiTable.snapshot(self, client, symbol, rsi_length, ma_length, ma_type, now=None)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `retry_at` → `0`

### Configuration literals

- `TIMEFRAMES = [('5 minutes', '5'), ('15 minutes', '15'), ('30 minutes', '30'), ('6 hours', '6H'), ('1 day', 'D'), ('1 week', '1W'), ('1 month', '1M')]`

## sector_heatmap/sector_service.py

[Owning source](../sector_heatmap/sector_service.py)

FYERS-backed candle caching and bounded sector rotation snapshot service.

### Callables and explicit defaults

- `rank_directional_drivers(drivers, direction)`
- `CandleHistoryProvider.__init__(self, client, now=None)`
- `CandleHistoryProvider.get(self, symbol, timeframe)`
- `CandleHistoryProvider._download(self, symbol, resolution, lookback_days)`
- `CandleHistoryProvider._completed_only(self, candles, resolution)`
- `AnalysisHistoryStore.__init__(self, path=DEFAULT_STATE_FILE)`
- `AnalysisHistoryStore._load(self)`
- `AnalysisHistoryStore.sector_history(self, mode, sector_id)`
- `AnalysisHistoryStore.append(self, mode, sector)`
- `AnalysisHistoryStore.save(self)`
- `SectorAnalysisService.__init__(self, access_token, state_file=DEFAULT_STATE_FILE, provider=None, now=None)`
- `SectorAnalysisService._empty_snapshot(mode, error=None, phase='CONNECTING')`
- `SectorAnalysisService._set_refresh_state(self, phase, message, completed=0, total=None)`
- `SectorAnalysisService._record_refresh_failure(self, error)`
- `SectorAnalysisService.start(self)`
- `SectorAnalysisService._loop(self)`
- `SectorAnalysisService.refresh(self)`
- `SectorAnalysisService._timeframe_candles(self, symbol)`
- `SectorAnalysisService._quality(self, timeframe, candles)`
- `SectorAnalysisService.snapshot(self, mode='intraday', sector_id=None)`
- `SectorAnalysisService.alignment_candidates(self, live_sectors, mode='intraday', max_stocks_per_sector=3)`

### Literal payload and lookup fallbacks

- `completed` → `0`
- `drivers` → `[]`
- `phase` → `'CONNECTING'`
- `refresh_state` → `{}`
- `sectors` → `[]`
- `timeframe_states` → `{}`

## sector_heatmap/sectors.py

[Owning source](../sector_heatmap/sectors.py)

FYERS symbols joined to versioned official NSE Indices constituent weights.

### Callables and explicit defaults

- `SectorDefinition.constituents(self)`
- `SectorDefinition.attribution(self)`
- `_sector(sector_id, name, symbol)`
- `equity_symbol(ticker)`

## sector_heatmap/sensex_straddle.py

[Owning source](../sector_heatmap/sensex_straddle.py)

Guarded process bridge for the external SENSEX long-straddle runner.

### Callables and explicit defaults

- `SensexStraddleService.__init__(self, script_path=None, credential_provider=None, process_factory=None, runtime_dir=None)`
- `SensexStraddleService.state_path(self)`
- `SensexStraddleService.trades_path(self)`
- `SensexStraddleService.chart_path(self)`
- `SensexStraddleService._read_json(self, path)`
- `SensexStraddleService._read_config(self)`
- `SensexStraddleService._interpreter(self)`
- `SensexStraddleService._recent_trades(self)`
- `SensexStraddleService._refresh_process(self)`
- `SensexStraddleService.snapshot(self)`
- `SensexStraddleService._capture_output(self, process)`
- `SensexStraddleService.start(self, mode='live', exit_mode='supertrend', lots=1, entry_start='09:15', entry_end='11:30', confirmation='', paper_capital_inr=100000)`
- `SensexStraddleService.start_paper(self)`
- `SensexStraddleService.snapshot_unlocked(self, message=None)`
- `SensexStraddleService.stop(self)`

### Literal payload and lookup fallbacks

- `ENTRY_WINDOW_END_TIME` → `'11:30'`
- `ENTRY_WINDOW_START_TIME` → `'09:15'`
- `EOD_SQUARE_OFF_TIME` → `'—'`
- `MAX_REENTRIES_PER_DAY` → `1`
- `STOPLOSS_POINTS` → `15`
- `SUPER_TREND_ACTIVATION_POINTS` → `'—'`
- `SUPER_TREND_MULTIPLIER` → `'—'`
- `SUPER_TREND_PERIOD` → `'—'`
- `VOL_PERCENTILE` → `'—'`

## sector_heatmap/straddle_paper.py

[Owning source](../sector_heatmap/straddle_paper.py)

Prepare an isolated Paper copy of the external straddle source.

### Callables and explicit defaults

- `prepare(source, runtime, initial, lots=1)`

## sector_heatmap/straddle_squareoff.py

[Owning source](../sector_heatmap/straddle_squareoff.py)

Fresh, confirmation-gated FYERS square-off for managed straddle runners.

### Callables and explicit defaults

- `_ok(response)`
- `_rows(response, key)`
- `StraddleSquareOffService.__init__(self, credential_provider, runners, client_factory=None, now=None)`
- `StraddleSquareOffService._client(self)`
- `StraddleSquareOffService._runner(self, name)`
- `StraddleSquareOffService._preflight(self, name)`
- `StraddleSquareOffService.prepare(self, name)`
- `StraddleSquareOffService.submit(self, preview_id, confirmation)`

### Literal payload and lookup fallbacks

- `data` → `[]`
- `netQty` → `0`
- `side` → `0`
- `status` → `0`

## sector_heatmap/telegram_parser.py

[Owning source](../sector_heatmap/telegram_parser.py)

Separate broker-selected recommendation tickets; execution only on explicit submit.

### Callables and explicit defaults

- `TelegramParser.__init__(self, parse, fyers_preview, fyers_submit, delta, guard, polling, clock=time.time)`
- `TelegramParser.parse(self, p)`
- `TelegramParser.submit(self, p, automatic=False)`
- `TelegramParser.auto(self, row, execution)`
- `TelegramParser.reconcile(self, p)`

### Literal payload and lookup fallbacks

- `message` → `'Exact contract required.'`

## sector_heatmap/telegram_polling.py

[Owning source](../sector_heatmap/telegram_polling.py)

Telegram Bot API channel updates, durable review queue, explicit stopped startup.

### Callables and explicit defaults

- `TelegramPolling.__init__(self, path, requester=requests, clock=time.time)`
- `TelegramPolling.save(self)`
- `TelegramPolling.running(self)`
- `TelegramPolling.status(self)`
- `TelegramPolling.configure(self, p)`
- `TelegramPolling.api(self, method, body=None)`
- `TelegramPolling.verify(self)`
- `TelegramPolling.ingest(self, updates, baseline=False)`
- `TelegramPolling.snapshot(self, ident, revision)`
- `TelegramPolling.reserve(self, ident, revision, submission_id)`
- `TelegramPolling.poll(self)`
- `TelegramPolling.start(self, p=None)`
- `TelegramPolling.loop(self)`
- `TelegramPolling.stop(self)`

### Literal payload and lookup fallbacks

- `auto` → `False`
- `broker` → `'DELTA_INDIA'`
- `channel` → `''`
- `interval` → `30`
- `quantity` → `1`

## sector_heatmap/trade_advisory.py

[Owning source](../sector_heatmap/trade_advisory.py)

Read-only, bounded OpenAI feedback. No order client or submission dependency.

### Callables and explicit defaults

- `settings()`
- `unavailable(reason, status='UNAVAILABLE')`
- `schema()`
- `completed_bars(rows, resolution, now)`
- `summarize(bars, resolution, now, symbol)`
- `resolve_context(contract, master_dir)`
- `collect_evidence(parsed, contract, token, master_dir, deadline, get=requests.get, now=None)`
- `validate_reports(data, evidence)`
- `analyze(preview_provider, payload, token_provider, master_dir, post=requests.post, get=requests.get)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `content` → `[]`
- `entry_instruction` → `'LIMIT'`
- `error` → `{}`
- `output` → `[]`
- `targets` → `[]`
- `text` → `''`
- `underlying` → `''`

## sector_heatmap/web.py

[Owning source](../sector_heatmap/web.py)

### Callables and explicit defaults

- `ema_entry_session_for_symbol(symbol)`
- `ema_candle_in_entry_session(timestamp, entry_session)`
- `ema_rsi_series(values, length=14)`
- `ema_profit_protection(entry_price, ltp, risk_unit_pct, peak_price=None, prior_stop=None)`
- `estimate_fyers_trade_charges(trades)`
- `ema_live_ticket_preview(contract, quote, lots, stop_loss_pct=None, target_profit_pct=None, profit_protection_pct=None, now=None)`
- `_ema_order_ids(response)`
- `ema_master_row_matches_segment(row, selected_segment)`
- `ema_cash_or_index_row_matches_exchange(row, exchange)`
- `ema_master_search_rank(item, needle)`
- `select_ema_atm_option(rows, underlying, direction, spot, now_epoch)`
- `ema_band_slope_regime(candles, ema_length=21, lookback=8, minimum_atr_per_bar=0.1)`
- `ema_band_resistance_volume_exit(candles, volume_lookback=20, volume_multiple=1.5, proximity_atr=0.25)`
- `ema_band_strategy_signal(candles, ema_length=21, entry_session=None, slope_lookback=8, minimum_slope_atr=0.0)`
- `ema_band_entry_checklist(candles, ema_length=21, has_active_position=False, slope_lookback=8, minimum_slope_atr=0.0)`
- `ema_band_exit_signal(candles, ema_length=21)`
- `fetch_chartink_source(url, requester=None)`
- `enrich_chartink_candidates(candidates, quote_fetcher)`
- `chartink_candidate_sectors(candidates, source_sectors=None)`
- `join_unique_reasons(items)`
- `instrument_route(payload)`
- `closed_position_records(positions)`
- `open_position_underlyings(positions)`
- `ema_open_buy_reconciliation(response, symbol, minimum_quantity)`
- `candidate_has_open_position(candidate, position_exposures)`
- `fetch_realized_pnl_report(app_id, access_token, start, end, requester=None)`
- `kama_trade_report(records)`
- `kama_scheduled_squareoff_due(position, now=None)`
- `run_server()`

### Literal payload and lookup fallbacks

- `Content-Length` → `'0'`
- `HEATMAP_PORT` → `'8080'`
- `acknowledgement` → `''`
- `allow_reclaims` → `True`
- `buy_qty` → `0`
- `buy_rate` → `0`
- `candidates` → `[]`
- `candles` → `[]`
- `config` → `{}`
- `confirmation` → `''`
- `data` → `[]`
- `data` → `{}`
- `drivers` → `[]`
- `entry_end` → `'11:30'`
- `entry_start` → `'09:15'`
- `exit_mode` → `'supertrend'`
- `filledQty` → `0`
- `id` → `''`
- `idea_risk_limit` → `2000`
- `legs` → `[]`
- `lots` → `1`
- `method` → `'structure'`
- `mode` → `'PAPER'`
- `mode` → `'live'`
- `netPositions` → `[]`
- `netQty` → `0`
- `net_qty` → `0`
- `optionsChain` → `[]`
- `ord_status` → `0`
- `orderBook` → `[]`
- `paper_capital_inr` → `100000`
- `pl` → `0`
- `positions` → `[]`
- `preview_id` → `''`
- `qty` → `0`
- `realized_pnl` → `0`
- `reconciliation` → `'NOT_APPLICABLE'`
- `resistance_volume_exit` → `False`
- `retry_at` → `0`
- `rows` → `[]`
- `score` → `0`
- `sectors` → `[]`
- `segment_name` → `'—'`
- `sell_qty` → `0`
- `sell_rate` → `0`
- `side` → `0`
- `stoploss` → `15`
- `summary_data` → `{}`
- `symbol_name` → `'—'`
- `target` → `30`
- `top_contributors` → `[]`
- `tradeBook` → `[]`
- `trade_history` → `[]`
- `underlying` → `''`
- `volume` → `0`

## sector_heatmap/whatsapp_polling.py

[Owning source](../sector_heatmap/whatsapp_polling.py)

Read-only polling and durable review queue. No broker execution capability.

### Callables and explicit defaults

- `WhatsAppPolling.__init__(self, path, preview, reconcile, source=None, clock=None)`
- `WhatsAppPolling.status(self)`
- `WhatsAppPolling.configure(self, payload)`
- `WhatsAppPolling.start(self)`
- `WhatsAppPolling.stop(self)`
- `WhatsAppPolling._run(self)`
- `WhatsAppPolling._fresh(self, stamp)`
- `WhatsAppPolling._verify(self, text)`
- `WhatsAppPolling.ingest(self, message)`
- `WhatsAppPolling.review(self, key)`
- `WhatsAppPolling.dismiss(self, key)`

### Literal payload and lookup fallbacks

- `group` → `''`
- `interval` → `60`

## sector_heatmap/whatsapp_source.py

[Owning source](../sector_heatmap/whatsapp_source.py)

Local native adapter; invoked only by explicit Start, never at startup.

### Callables and explicit defaults

- `NativeWhatsAppSource.__init__(self, executable)`
- `NativeWhatsAppSource.readiness(self)`
- `NativeWhatsAppSource.read_latest(self, group)`

## sensex_ema_band_midpoint_live.py

[Owning source](../sensex_ema_band_midpoint_live.py)

SENSEX EMA-band midpoint signal runner.

### Callables and explicit defaults

- `parse_args()`
- `normalize_ohlcv(frame: pd.DataFrame)`
- `fetch_live_bars(interval: str)`
- `fyers_client()`
- `resolve_atm_option(signal: Signal, lots: int)`
- `submit_fyers_order(signal: Signal, trade_symbol: str, quantity: int, args: argparse.Namespace)`
- `validate_fyers_symbol(symbol: str, quantity: int)`
- `manage_signal(signal: Signal, state: dict, args: argparse.Namespace)`
- `report_live_pnl(state: dict)`
- `session_pass(timestamp: pd.Timestamp, session: str)`
- `build_events(frame: pd.DataFrame, ema_length: int, session: str, cooldown: int, mode: str)`
- `load_state(path: Path)`
- `record(signals: list[Signal], journal: Path)`
- `main()`

### Literal payload and lookup fallbacks

- `FYERS_APP_ID` → `''`
- `data` → `{}`
- `netPositions` → `[]`

## strategies/ema_band/backtest.py

[Owning source](../strategies/ema_band/backtest.py)

Read-only 5-minute EMA Band backtest; expects FYERS-format OHLC candles.

### Callables and explicit defaults

- `run(bars)`

## strategies/ema_band/signals.py

[Owning source](../strategies/ema_band/signals.py)

Paper-first translation of the uploaded EMA High/Low Band Pine rules.

### Callables and explicit defaults

- `ema(values, length)`
- `evaluate(bars, position=0)`

## strategies/ema_band/slope_filter_backtest.py

[Owning source](../strategies/ema_band/slope_filter_backtest.py)

Read-only FYERS comparison: baseline EMA Band versus its slope-filtered variant.

### Callables and explicit defaults

- `completed_candles()`
- `ema(values, length)`
- `run(candles, slope_filter, resistance_volume_exit=False)`
- `metrics(trades)`
- `print_comparison(candles, days)`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## strategies/ema_crossover/__init__.py

[Owning source](../strategies/ema_crossover/__init__.py)

## strategies/ema_crossover/audit_contract.py

[Owning source](../strategies/ema_crossover/audit_contract.py)

Read-only master, funds and margin-calculator evidence; never submits orders.

### Callables and explicit defaults

- `main()`

## strategies/ema_crossover/backtest.py

[Owning source](../strategies/ema_crossover/backtest.py)

Diagnostic underlying-point backtest, not an option-price profitability study.

### Callables and explicit defaults

- `run(path, friction=5)`

## strategies/ema_crossover/broker.py

[Owning source](../strategies/ema_crossover/broker.py)

FYERS adapter: current masters, streaming prices and fresh order preflight.

### Callables and explicit defaults

- `IndependentDataSocket.__new__(cls, *args, **kwargs)`
- `IndependentDataSocket.reset_feed_state(self)`
- `FyersBroker.__init__(self, master_dir, fetch_candles, select_atm, on_tick=None)`
- `FyersBroker.live_enabled(self)`
- `FyersBroker.rows(self, segment)`
- `FyersBroker.underlying(self, symbol)`
- `FyersBroker.contract(self, symbol)`
- `FyersBroker.validate_config(self, c)`
- `FyersBroker.stream_status(self)`
- `FyersBroker.subscribe_all(self)`
- `FyersBroker.start(self)`
- `FyersBroker.stop(self)`
- `FyersBroker.tick(self, symbol)`
- `FyersBroker.quote(self, symbol)`
- `FyersBroker.candles(self, c)`
- `FyersBroker.resolve(self, c, direction)`
- `FyersBroker.order(self, symbol, qty, side, quote)`
- `FyersBroker.validate_order(self, order)`
- `FyersBroker.positions(self)`
- `FyersBroker.orders(self)`
- `FyersBroker.reconcile_position(self, symbol, qty)`
- `FyersBroker.preflight(self, order, c)`
- `FyersBroker.authenticated_client(self)`
- `FyersBroker.place(self, order)`
- `FyersBroker.cancel(self, order_id)`

### Literal payload and lookup fallbacks

- `ask_price` → `0`
- `bid_price` → `0`
- `expiryDate` → `0`
- `ltp` → `0`
- `minLotSize` → `0`
- `netQty` → `0`
- `status` → `0`
- `strikePrice` → `-1`
- `tickSize` → `0`

## strategies/ema_crossover/check_master_valuation.py

[Owning source](../strategies/ema_crossover/check_master_valuation.py)

Read-only validation of all current option valuation metadata and examples.

### Callables and explicit defaults

- `main()`

## strategies/ema_crossover/cloud_backtest.py

[Owning source](../strategies/ema_crossover/cloud_backtest.py)

EMA Cloud diagnostic on underlying prices, not an option execution backtest.

### Callables and explicit defaults

- `run(path)`

## strategies/ema_crossover/history.py

[Owning source](../strategies/ema_crossover/history.py)

Position history from explicit ownership links; never pair by contract adjacency.

### Callables and explicit defaults

- `position_history(orders)`
- `verified_legacy_rows(orders, events, position, config, metadata=None, links=None)`

### Literal payload and lookup fallbacks

- `entry_side` → `1`
- `filled` → `0`
- `message` → `''`
- `requested` → `0`

## strategies/ema_crossover/paper_capital.py

[Owning source](../strategies/ema_crossover/paper_capital.py)

Finite virtual Paper capital. Never reads live funds or submits orders.

### Callables and explicit defaults

- `balance(state, rate=1)`
- `preflight(state, order, contract, quote, rate=1)`

### Literal payload and lookup fallbacks

- `config` → `{}`
- `entry_side` → `1`
- `order` → `{}`
- `order_history` → `[]`
- `paper_capital_inr` → `100000`
- `position` → `{}`
- `quantity` → `0`
- `realized_pnl` → `0`
- `started_at` → `0`
- `submitted_at` → `0`

## strategies/ema_crossover/runner.py

[Owning source](../strategies/ema_crossover/runner.py)

Independent opt-in runner. Durable intent precedes every broker mutation.

### Callables and explicit defaults

- `configuration(payload)`
- `validate_spot_levels(spot, direction, config)`
- `spot_exit(candle, direction, config)`
- `Runner.signal_key(self, sig)`
- `Runner.session_bounds(self, c)`
- `Runner.exit_reason_for(self, sig, position)`
- `Runner.exit_is_later(self, sig, position)`
- `Runner.exit_signal(self, sig, direction)`
- `Runner.__init__(self, adapter, state_path, clock=time.time)`
- `Runner.save(self)`
- `Runner.event(self, status, message)`
- `Runner.snapshot(self)`
- `Runner.preview(self, payload)`
- `Runner.start(self, payload, background=True)`
- `Runner.release(self)`
- `Runner.stop(self)`
- `Runner.loop(self)`
- `Runner.signal(self)`
- `Runner.fresh_cross(self, sig)`
- `Runner.record_order(self, pending, status, filled=0, price=None)`
- `Runner.is_entry_order(order, position)`
- `Runner.paper_rate(self)`
- `Runner.paper_funds(self)`
- `Runner.entry_preflight(self, order, contract, quote)`
- `Runner.validate_entry_authorization(self, position)`
- `Runner.submit(self, order, position, reason)`
- `Runner.complete_pending(self, filled, price)`
- `Runner.reconcile(self)`
- `Runner.step(self)`

### Literal payload and lookup fallbacks

- `entry_side` → `1`
- `events` → `[]`
- `execution_route` → `'OPTIONS'`
- `filledQty` → `0`
- `last_exit_bar` → `0`
- `ma_type` → `'SMA'`
- `message` → `'FYERS rejected order'`
- `mode` → `'PAPER'`
- `orderTag` → `''`
- `order_history` → `[]`
- `paper_capital_inr` → `100000`
- `qty` → `-1`
- `realized_pnl` → `0`
- `seven_day_session` → `False`
- `side` → `0`
- `sma_length` → `14`
- `timeframe` → `'5 minutes'`
- `trades_used` → `0`
- `trailing_config` → `{}`
- `underlying` → `''`

### Configuration literals

- `TIMEFRAMES = {'1 minute': 60, '2 minutes': 120, '3 minutes': 180, '5 minutes': 300, '10 minutes': 600, '15 minutes': 900, '30 minutes': 1800, '1 hour': 3600}`

## strategies/ema_crossover/signals.py

[Owning source](../strategies/ema_crossover/signals.py)

EMA Cloud completed-close conditions; identical warm-up and deduplication to the dashboard.

### Callables and explicit defaults

- `series(candles, fast=10, slow=30, exit_period=None)`
- `exit_on_close(candle, direction)`
- `rsi_sma_series(candles, rsi_length=14, sma_length=14, ma_type='SMA')`
- `rsi_cross(previous_rsi, previous_ma, rsi, ma)`
- `rsi_exit_on_close(candle, direction)`

## strategies/ema_crossover/trailing.py

[Owning source](../strategies/ema_crossover/trailing.py)

Optional fixed-distance steps on fresh executable long-option bids.

### Callables and explicit defaults

- `settings(payload)`
- `initial(entry, tick, config, quantity=None, lot_unit=None)`
- `advance(state, quote, now)`
- `allocation(lots)`
- `target_quantity(state, remaining)`

### Literal payload and lookup fallbacks

- `target_filled` → `{}`
- `trailing_enabled` → `False`
- `trailing_mode` → `'PERCENTAGE'`

## strategies/ema_crossover/valuation.py

[Owning source](../strategies/ema_crossover/valuation.py)

Convert FYERS API quantities and quoted prices to rupees.

### Callables and explicit defaults

- `multiplier(contract)`
- `amount(contract, quantity, price)`

## strategies/long_straddle/nifty_straddle.py

[Owning source](../strategies/long_straddle/nifty_straddle.py)

LIVE NIFTY straddle trader on Fyers — implements the final validated config

### Callables and explicit defaults

- `log(msg)`
- `is_market_open(now=None)`
- `_entry_count_today()`
- `_record_entry()`
- `_next_five_minute_close(after)`
- `record_reentry_wait(exited_at)`
- `reentry_allowed(now)`
- `entry_allowed(now)`
- `_load_fyers_credentials()`
- `get_spot_ltp()`
- `get_nearest_weekly_expiry_and_atm_symbols(spot)`
- `resolve_fyers_lot_size(symbol)`
- `resolve_pair_quantity(ce_symbol, pe_symbol)`
- `get_ltp(symbol)`
- `get_recent_5min_candles(lookback_days)`
- `get_symbol_5min_candles(symbol, lookback_days=10)`
- `compute_supertrend(df, period, multiplier)`
- `get_combined_premium_chart(ce_symbol, pe_symbol, now=None)`
- `get_combined_premium_supertrend(ce_symbol, pe_symbol, now=None, candles=None)`
- `compute_current_vol_signal(now=None)`
- `place_order(symbol, qty, side)`
- `log_trade(row)`
- `save_state(state)`
- `load_state()`
- `clear_state()`
- `save_premium_chart(state, now, ce_ltp, pe_ltp, candles, supertrend_armed, error=None)`
- `clear_premium_chart()`
- `enter_position()`
- `exit_position(state, reason)`
- `main_loop()`
- `validate_current_contracts()`

### Literal payload and lookup fallbacks

- `FYERS_APP_ID` → `''`
- `entries` → `0`
- `expiry` → `'unknown'`
- `expiryData` → `[]`

## strategies/long_straddle/sensex_straddle.py

[Owning source](../strategies/long_straddle/sensex_straddle.py)

LIVE SENSEX straddle trader on Fyers. The default exit mode matches the

### Callables and explicit defaults

- `log(msg)`
- `is_market_open(now=None)`
- `_entry_count_today()`
- `_record_entry()`
- `_next_five_minute_close(after)`
- `record_reentry_wait(exited_at)`
- `reentry_allowed(now)`
- `entry_allowed(now)`
- `_load_fyers_credentials()`
- `get_spot_ltp()`
- `get_nearest_weekly_expiry_and_atm_symbols(spot)`
- `get_ltp(symbol)`
- `get_recent_5min_candles(lookback_days)`
- `get_symbol_5min_candles(symbol, lookback_days=10)`
- `compute_supertrend(df, period, multiplier)`
- `get_combined_premium_chart(ce_symbol, pe_symbol, now=None)`
- `get_combined_premium_supertrend(ce_symbol, pe_symbol, now=None, candles=None)`
- `compute_current_vol_signal(now=None)`
- `place_order(symbol, qty, side)`
- `log_trade(row)`
- `save_state(state)`
- `load_state()`
- `clear_state()`
- `save_premium_chart(state, now, ce_ltp, pe_ltp, candles, supertrend_armed, error=None)`
- `clear_premium_chart()`
- `record_exit_date()`
- `in_daily_cooldown()`
- `enter_position()`
- `exit_position(state, reason)`
- `main_loop()`

### Literal payload and lookup fallbacks

- `FYERS_APP_ID` → `''`
- `entries` → `0`
- `expiry` → `'unknown'`
- `expiryData` → `[]`

## strategies/nifty_call_credit_monitor/run.py

[Owning source](../strategies/nifty_call_credit_monitor/run.py)

NIFTY conditional bear-call-spread runner.

### Callables and explicit defaults

- `completed_candle(client)`
- `require_market_open()`
- `exact_call(rows, strike)`
- `build_preview(client, lots, short_strike, long_strike)`
- `reject_duplicate_exposure(client, preview)`
- `basket_payload(preview)`
- `basket_margin(client, orders)`
- `main()`

### Literal payload and lookup fallbacks

- `message` → `'unknown error'`
- `net_qty` → `0`
- `strike_price` → `-1`

## strategies/renko_supertrend/__init__.py

[Owning source](../strategies/renko_supertrend/__init__.py)

Pinaki Renko ST Auto Research port; no protected-original parity claim.

## strategies/renko_supertrend/adoption.py

[Owning source](../strategies/renko_supertrend/adoption.py)

Explicit adoption of broker-confirmed long MARGIN options; never an entry fill.

### Callables and explicit defaults

- `identity(row)`
- `fingerprint(account, position)`
- `AdoptedRunner.step(self)`
- `Manager.__init__(self, path, broker_factory, read_broker, account_reader, owners=lambda: [], runner_type=AdoptedRunner)`
- `Manager.guard(self, runner)`
- `Manager.owned_symbols(self)`
- `Manager.inventory(self)`
- `Manager.exclusive(self)`
- `Manager.control(self, payload, background=True)`
- `Manager.apply(self, payload, background=True)`

### Literal payload and lookup fallbacks

- `adoption_reentry` → `False`
- `buyAvg` → `0`
- `id` → `''`
- `netQty` → `0`
- `orderTag` → `''`
- `status` → `0`

## strategies/renko_supertrend/batch.py

[Owning source](../strategies/renko_supertrend/batch.py)

Explicit multi-instrument activation with durable, non-replaying batch IDs.

### Callables and explicit defaults

- `Batch.__init__(self, path, create, lookup)`
- `Batch.save(self, file, data)`
- `Batch.start(self, payload, background=True)`

## strategies/renko_supertrend/candle_patterns.py

[Owning source](../strategies/renko_supertrend/candle_patterns.py)

Explicit body-based patterns for completed host-candle retests.

### Callables and explicit defaults

- `matches(rows, bullish, config)`

### Literal payload and lookup fallbacks

- `retest_engulfing` → `True`
- `retest_harami` → `True`
- `retest_star` → `True`

## strategies/renko_supertrend/chart_history.py

[Owning source](../strategies/renko_supertrend/chart_history.py)

Bounded, durable fixed-contract OHLC history for read-only chart research.

### Callables and explicit defaults

- `selected_range(preset='45', start='', end='', now=None)`
- `candle_issue(row)`
- `ChartHistory.__init__(self, path, min_interval=0.35)`
- `ChartHistory.load(self, client, symbol, timeframe, preset='45', start='', end='', config=None, tick=0.05, now=None)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `forming_retry_count` → `0`
- `message` → `'invalid response'`
- `next_retry` → `0`
- `refreshed_at` → `0`
- `repair_after` → `0`
- `rows` → `[]`

## strategies/renko_supertrend/costs.py

[Owning source](../strategies/renko_supertrend/costs.py)

Explicit Sensex-options cost estimates from owned cumulative fills, never broker bills.

### Callables and explicit defaults

- `rounded(x, unit='0.01')`
- `valid(x)`
- `settings(payload)`
- `applicable(row)`
- `fee(turnover, side, brokerage=15, stt=None, stamp=None)`
- `ledger_costs(orders)`
- `trade_costs(trade, ledger)`

### Literal payload and lookup fallbacks

- `additional_slippage_points` → `0`
- `submitted_at` → `0`
- `symbol` → `''`

### Configuration literals

- `RATES = dict(exchange=0.000325, sebi=1e-06, stt_sell=0.0015, stamp_buy=3e-05, gst=0.18)`

## strategies/renko_supertrend/delta_broker.py

[Owning source](../strategies/renko_supertrend/delta_broker.py)

Independent Delta market stream and native broker adapter for shared Renko.

### Callables and explicit defaults

- `Broker.__init__(self, delta, history_path, on_tick=None)`
- `Broker.live_enabled(self)`
- `Broker.session_policy(self, config)`
- `Broker._master_row(self, product)`
- `Broker.rows(self, segment)`
- `Broker.underlying(self, symbol)`
- `Broker.host_tick_size(self, symbol)`
- `Broker.contract(self, symbol)`
- `Broker.route_availability(self, config)`
- `Broker.validate_config(self, config)`
- `Broker.authenticated_client(self)`
- `Broker.subscribe(self, symbol, seconds=None)`
- `Broker.subscribe_all(self)`
- `Broker.ingest(self, message, received=None)`
- `Broker.start(self)`
- `Broker.stop(self)`
- `Broker.stream_status(self)`
- `Broker.tick(self, symbol)`
- `Broker.quote(self, symbol)`
- `Broker.candles(self, config)`
- `Broker.resolve(self, config, direction)`
- `Broker.warm_options(self, config)`
- `Broker.positions(self)`
- `Broker.orders(self)`
- `Broker.reconcile_position(self, symbol, size)`
- `Broker.order(self, symbol, qty, side, quote)`
- `Broker.validate_order(self, order)`
- `Broker.preflight(self, order, config)`
- `Broker.place(self, order)`
- `Broker.cancel(self, order_id)`

### Literal payload and lookup fallbacks

- `exchange_at` → `0`

## strategies/renko_supertrend/delta_contracts.py

[Owning source](../strategies/renko_supertrend/delta_contracts.py)

Delta-native Renko boundary types. No network or execution side effects.

### Callables and explicit defaults

- `decimal(value, name, positive=False)`
- `whole(value, name, positive=False)`
- `configuration(payload)`
- `option_contract(product, now)`
- `position(row, product, now)`
- `order_intent(symbol, size, side, quote, product, now)`
- `owned_order(owned, expected_account)`

### Literal payload and lookup fallbacks

- `carry_policy` → `'CONTINUOUS'`
- `timeframe` → `'5 minutes'`
- `underlying` → `''`

### Configuration literals

- `RESOLUTIONS = {'1 minute': '1m', '3 minutes': '3m', '5 minutes': '5m', '15 minutes': '15m', '30 minutes': '30m', '1 hour': '1h'}`

## strategies/renko_supertrend/delta_costs.py

[Owning source](../strategies/renko_supertrend/delta_costs.py)

Delta native-currency regular option fee estimates; never broker invoices.

### Callables and explicit defaults

- `number(value)`
- `order_cost(row)`
- `trade_costs(trade, ledger)`

## strategies/renko_supertrend/delta_execution.py

[Owning source](../strategies/renko_supertrend/delta_execution.py)

Internal Delta execution boundary; deliberately not registered as an HTTP action.

### Callables and explicit defaults

- `Execution.__init__(self, delta)`
- `Execution.authenticate(self)`
- `Execution.active_orders(self)`
- `Execution.positions(self)`
- `Execution.reconcile(self, request_id)`
- `Execution.submit(self, symbol, size, side, quote, token, signal_symbol, reason)`
- `Execution.cancel(self, request_id)`

## strategies/renko_supertrend/delta_runner.py

[Owning source](../strategies/renko_supertrend/delta_runner.py)

Shared Renko rules with explicit Delta policy and native accounting labels.

### Callables and explicit defaults

- `DeltaRunner.read_preferences(self)`
- `DeltaRunner.save_preferences(self, payload)`
- `DeltaRunner.deadline(self)`
- `DeltaRunner.submit(self, order, position, reason)`
- `DeltaRunner.record_order(self, pending, status, filled=0, price=None)`
- `DeltaRunner.snapshot(self)`

### Literal payload and lookup fallbacks

- `trade_history` → `[]`

## strategies/renko_supertrend/delta_service.py

[Owning source](../strategies/renko_supertrend/delta_service.py)

Delta Renko HTTP component: shared chart math, isolated execution ownership.

### Callables and explicit defaults

- `Service.__init__(self, delta, root, instance_key='default', instrument=None)`
- `Service.chart_config(self, query)`
- `Service.chart(self, query)`
- `Service.get(self, handler, path)`
- `Service.post(self, handler, path, payload)`
- `Service.stream(self, handler, query)`

### Literal payload and lookup fallbacks

- `trade_history` → `[]`

## strategies/renko_supertrend/directional_research.py

[Owning source](../strategies/renko_supertrend/directional_research.py)

Isolated completed-OHLC recovery-lock experiment. Never imported by runner.

### Callables and explicit defaults

- `RecoveryLocks.__init__(self, policy)`
- `RecoveryLocks.loss(self, direction, high, low, at)`
- `RecoveryLocks.observe(self, close, at)`
- `RecoveryLocks.allows(self, direction)`
- `simulate(rows, policy, bps, seconds=60, max_candles=3)`
- `summarize(result, days)`
- `main()`

## strategies/renko_supertrend/ema_exit.py

[Owning source](../strategies/renko_supertrend/ema_exit.py)

Optional host-close EMA exit calculations; no order route or strategy mutation.

### Callables and explicit defaults

- `settings(payload)`
- `confirmed_values(rows, length)`
- `confirmed_cross(previous, current, direction, enabled=True)`
- `live_breach(previous_ema, price, stamp, now, length, direction, enabled=True)`

### Literal payload and lookup fallbacks

- `ema_exit_enabled` → `False`
- `ema_exit_length` → `10`

## strategies/renko_supertrend/ema_proximity.py

[Owning source](../strategies/renko_supertrend/ema_proximity.py)

New entries only: absolute underlying distance from EMA10, scaled by completed ATR.

### Callables and explicit defaults

- `settings(payload)`
- `check(config, price, ema10, confirmed_atr)`

### Literal payload and lookup fallbacks

- `ema_proximity_distance` → `0.5`
- `ema_proximity_enabled` → `False`
- `ema_proximity_mode` → `'ATR'`

## strategies/renko_supertrend/execution_audit.py

[Owning source](../strategies/renko_supertrend/execution_audit.py)

Display owned fills against a candidate's candle, retaining the first assessment.

### Callables and explicit defaults

- `entry_orders(event, orders, seconds)`

## strategies/renko_supertrend/history.py

[Owning source](../strategies/renko_supertrend/history.py)

Actual owned option-trade reporting; never turn signal rows into fills.

### Callables and explicit defaults

- `trade_history(orders, position=None, unrealized=None, valuation=None)`

### Literal payload and lookup fallbacks

- `ema_exit_enabled` → `True`
- `ema_exit_length` → `10`
- `execution_route` → `'OPTIONS'`
- `filled` → `0`
- `reconciliation_events` → `[]`
- `spot_fill_observations` → `[]`

## strategies/renko_supertrend/journal_export.py

[Owning source](../strategies/renko_supertrend/journal_export.py)

Presentable, immutable journal export; spreadsheet generation has no order route.

### Callables and explicit defaults

- `export_xlsx(data, root)`

## strategies/renko_supertrend/market_structure.py

[Owning source](../strategies/renko_supertrend/market_structure.py)

Optional directional structure gate from confirmed actual host pivots.

### Callables and explicit defaults

- `settings(payload)`
- `check(rows, direction, seconds, event_at)`

### Literal payload and lookup fallbacks

- `market_structure_enabled` → `False`

## strategies/renko_supertrend/mtf_supertrend.py

[Owning source](../strategies/renko_supertrend/mtf_supertrend.py)

Completed one/five-minute Supertrend agreement; no order routing.

### Callables and explicit defaults

- `latest(candles, config, tick_size, seconds, at)`
- `agreement(one, five, direction)`
- `check(one_rows, five_rows, config, tick_size, direction, at)`

## strategies/renko_supertrend/preferences.py

[Owning source](../strategies/renko_supertrend/preferences.py)

Versioned UI preferences, kept separate from armed runner configuration.

### Callables and explicit defaults

- `read(path)`
- `write(path, payload, now)`

### Literal payload and lookup fallbacks

- `cash-product` → `'INTRADAY'`
- `chart-view` → `'host'`
- `commodity-holding` → `'INTRADAY'`
- `history-preset` → `'45'`
- `market` → `'ALL'`
- `mode` → `'PAPER'`

## strategies/renko_supertrend/research_replay.py

[Owning source](../strategies/renko_supertrend/research_replay.py)

Read-only underlying proxy replay, not a historical ATM-option backtest.

### Callables and explicit defaults

- `replay(rows, cost_bps)`
- `main()`

## strategies/renko_supertrend/retest.py

[Owning source](../strategies/renko_supertrend/retest.py)

Optional completed-candle EMA10 retest with matching pattern confirmation.

### Callables and explicit defaults

- `evaluate(state, candle, previous, previous_emas, previous_direction, direction, entry, allowed, config=None)`

### Literal payload and lookup fallbacks

- `retest_bars` → `[]`
- `retest_ready` → `False`

## strategies/renko_supertrend/risk.py

[Owning source](../strategies/renko_supertrend/risk.py)

Underlying price hard boundaries, independent of completed entry candles.

### Callables and explicit defaults

- `levels(payload)`
- `hard_exit(price, direction, config)`

## strategies/renko_supertrend/rsi_slope.py

[Owning source](../strategies/renko_supertrend/rsi_slope.py)

Wilder RSI14 of host closes, identical seeding/flat convention to chart display.

### Callables and explicit defaults

- `observe(state, close)`
- `apply(entry, state, observation, direction, enabled)`

### Literal payload and lookup fallbacks

- `count` → `0`
- `gain` → `0`
- `loss` → `0`
- `rsi_host` → `{}`

## strategies/renko_supertrend/runner.py

[Owning source](../strategies/renko_supertrend/runner.py)

Independent Renko state using the existing durable FYERS lifecycle.

### Callables and explicit defaults

- `price_fingerprint(row)`
- `price_state(state)`
- `analysis(candles, config, tick_size, saved=None, retain=500)`
- `ema_adverse(sig, direction)`
- `overnight(config)`
- `commodity_expiry_exit_at(expiry, session)`
- `after_cutoff(now, config=None)`
- `master_session_policy(row)`
- `ema_exit_observation(confirmed, price, stamp, config, now)`
- `provisional(confirmed, forming, config, tick_size, now)`
- `configuration(payload)`
- `Broker.cash_contract(self, symbol)`
- `Broker.contract(self, symbol)`
- `Broker.order(self, symbol, qty, side, quote)`
- `Broker.validate_order(self, order)`
- `Broker.reconcile_position(self, symbol, qty)`
- `Broker.holdings(self)`
- `Broker.preflight(self, order, c)`
- `Broker.stop(self)`
- `Broker.__init__(self, *args, on_tick=None, **kwargs)`
- `Broker.observe(self, c, rows)`
- `Broker.candles(self, c)`
- `Broker.live_price(self, c, now)`
- `Broker.quote(self, symbol)`
- `Broker.forming(self, c, rows, now)`
- `Broker.route_availability(self, c)`
- `Broker.session_policy(self, c)`
- `Broker.resolve(self, c, direction)`
- `Broker.warm_options(self, c)`
- `Broker.host_tick_size(self, symbol)`
- `Broker.validate_config(self, c)`
- `Runner.__init__(self, *args, **kwargs)`
- `Runner.read_preferences(self)`
- `Runner.drain_position_ticks(self)`
- `Runner.observe_position_tick(self, tick, received_at=None, persist=True)`
- `Runner.sideways_entry_gate(self)`
- `Runner.indicator_snapshot(self, sig=None, reason=None)`
- `Runner.save_preferences(self, payload)`
- `Runner.preview(self, payload)`
- `Runner.activate(self, payload, background=True)`
- `Runner.stop(self)`
- `Runner._chart_identity(self, payload)`
- `Runner.chart_stop(self, payload)`
- `Runner.chart_mode(self, payload)`
- `Runner.prepare_zone_target(self, position, config)`
- `Runner.session_bounds(self, c)`
- `Runner.snapshot(self)`
- `Runner.signal_key(self, sig)`
- `Runner.deadline(self)`
- `Runner.step(self)`
- `Runner.record_order(self, pending, status, filled=0, price=None)`
- `Runner.complete_pending(self, filled, price)`
- `Runner.override_entry(self, payload)`
- `Runner.validate_entry_authorization(self, position)`
- `Runner.submit(self, order, position, reason)`
- `Runner.record_entry_assessment(self, sig, eligible, code, reason)`
- `Runner.fresh_cross(self, sig)`
- `Runner.remember_execution_signal(self, sig, eligible, reason=None)`
- `Runner.exit_reason_for(self, sig, position)`
- `Runner.exit_is_later(self, sig, position)`
- `Runner.exit_signal(self, sig, direction)`
- `Runner.exit_ema(self, rows, c)`
- `Runner.current_analysis(self, rows, c, tick)`
- `Runner.supertrend_agreement(self, direction, at, host_rows=None)`
- `Runner.signal(self)`

### Literal payload and lookup fallbacks

- `accepting_entries` → `False`
- `additional_slippage_points` → `0`
- `broker` → `'FYERS'`
- `cash_product` → `'INTRADAY'`
- `ema_exit_enabled` → `True`
- `ema_exit_length` → `10`
- `ema_gaps` → `[]`
- `entry_side` → `1`
- `event_at` → `0`
- `execution_route` → `'OPTIONS'`
- `execution_signals` → `[]`
- `filled` → `0`
- `fingerprints` → `{}`
- `history_recoveries` → `[]`
- `intrabar_entries` → `False`
- `last_exit_bar` → `0`
- `last_traded_time` → `0`
- `ltp` → `0`
- `market_event_at` → `0`
- `master_regular_session` → `''`
- `master_regular_session` → `'0915-1530'`
- `message` → `'No confirmed order intent or fill.'`
- `mode` → `'PAPER'`
- `netQty` → `0`
- `order_history` → `[]`
- `price_fingerprints` → `{}`
- `quantity` → `0`
- `quantity_multiplier` → `1`
- `reason` → `'Confirmed market structure unavailable; entry blocked.'`
- `reason` → `'One-minute/five-minute Supertrend agreement unavailable; entry blocked.'`
- `reconciliation_events` → `[]`
- `rows` → `[]`
- `seen` → `[]`
- `session_deadline` → `'15:10'`
- `session_open` → `'09:15'`
- `settings` → `{}`
- `seven_day_session` → `False`
- `sideways_archived` → `[]`
- `sideways_enabled` → `False`
- `sideways_events` → `[]`
- `sideways_max_candles` → `3`
- `spot_fill_observations` → `[]`
- `status` → `'PENDING'`
- `timestamp` → `0`
- `trades_used` → `0`
- `trailing_basis` → `'OPTION_PREMIUM_PERCENT'`
- `underlying` → `''`

## strategies/renko_supertrend/sideways.py

[Owning source](../strategies/renko_supertrend/sideways.py)

Quick losing-position range lock; no swing history, entry signal or order route.

### Callables and explicit defaults

- `settings(payload)`
- `observe(exposure, entry_at, price, stamp, now, exit_at=None)`
- `candle_count(entry_at, exit_at, seconds)`
- `freeze(exposure, exit_at, realized, seconds, config, trade_id, underlying)`
- `breakout(lock, price, stamp, now)`

### Literal payload and lookup fallbacks

- `sideways_enabled` → `False`
- `sideways_max_candles` → `3`

## strategies/renko_supertrend/signals.py

[Owning source](../strategies/renko_supertrend/signals.py)

Sequential port of source.pine, including Pine-style missing-value warm-up.

### Callables and explicit defaults

- `settings(payload)`
- `completed(candles)`
- `rma(state, key, value, length)`
- `ema_setup(state, close, direction, allowed, window)`
- `project_lifecycle(state, timestamp, entry_direction, reversal_direction, seconds=300, close=None, ema10=None, deadline='15:15')`
- `Engine.__init__(self, config=None, tick_size=0.05, state=None)`
- `Engine.update(self, candle)`
- `series(candles, config=None, tick_size=0.05)`

### Literal payload and lookup fallbacks

- `ema_gaps` → `[]`
- `session_deadline` → `'15:15'`

### Configuration literals

- `DEFAULTS = dict(atr_length=5, factor=3.0, brick_mode='Auto', manual_brick=12.8, use_adx=False, adx_threshold=20.0, adx_length=14, adx_smoothing=14, widening_window=2, rsi_slope_enabled=True, retest_enabled=False, retest_engulfing=True, retest_harami=True, retest_star=True)`

## strategies/renko_supertrend/source_reference.py

[Owning source](../strategies/renko_supertrend/source_reference.py)

Test-only evaluator of the arithmetic statements in the supplied Pine source.

### Callables and explicit defaults

- `ternary(expression)`
- `rma(values, length)`
- `reference(candles, config, tick=0.05)`

### Literal payload and lookup fallbacks

- `direction` → `1`

## strategies/renko_supertrend/stream.py

[Owning source](../strategies/renko_supertrend/stream.py)

Read-only browser stream and isolated FYERS order notifications.

### Callables and explicit defaults

- `IndependentOrderSocket.__new__(cls, *args, **kwargs)`
- `QuietLogger.__getattr__(self, name)`
- `OrderNotifications.__init__(self, runner, wake, log_path)`
- `OrderNotifications.start(self)`
- `OrderNotifications.snapshot(self)`
- `BrowserSnapshotCache.__init__(self, snapshot, clock=time.time)`
- `BrowserSnapshotCache.refresh(self)`
- `BrowserSnapshotCache.read(self, now)`
- `browser_snapshot(runner, now)`
- `browser_managers(runners, now)`
- `browser_frame(runner, broker, config, order_stream, now=None)`

## strategies/renko_supertrend/trailing_stop.py

[Owning source](../strategies/renko_supertrend/trailing_stop.py)

Optional monotonic full-position trailing exit; no partial profit targets.

### Callables and explicit defaults

- `settings(payload)`
- `advance(state, config, direction, price, exchange_at, received_at, now, opened_at)`

### Literal payload and lookup fallbacks

- `trailing_basis` → `'OPTION_PREMIUM_PERCENT'`
- `trailing_distance` → `10`
- `trailing_enabled` → `False`

## strategies/renko_supertrend/zone_target.py

[Owning source](../strategies/renko_supertrend/zone_target.py)

Optional completed-5m opposing-zone exit. Pure OHLC evidence; no execution.

### Callables and explicit defaults

- `settings(payload)`
- `validate(rows)`
- `zones(rows, timeline=None)`
- `assess(rows, position, now)`

### Literal payload and lookup fallbacks

- `zone_target_enabled` → `False`

## dashboard-enhancements.js

[Owning source](../dashboard-enhancements.js)

### Named functions

`renderPaperFunds`

### UI field and toggle identifiers

`account-state`, `add-screener`, `ai-review-state`, `analysis-board`, `analysis-exclusions`, `analysis-panel`, `analysis-refresh-interval`, `analysis-status`, `analyze-screener-options`, `analyze-screeners`, `auto-ack`, `auto-completed`, `auto-cooldown`, `auto-daily-loss`, `auto-enabled`, `auto-end`, `auto-idea-risk`, `auto-index-underlyings`, `auto-kill`, `auto-limit-buffer`, `auto-max-dte`, `auto-max-orders`, `auto-max-positions`, `auto-max-spread`, `auto-min-dte`, `auto-min-rr`, `auto-mode`, `auto-option-evidence`, `auto-order-type`, `auto-planning-capital`, `auto-preview`, `auto-review`, `auto-risk-defined`, `auto-risk-reserve`, `auto-segments`, `auto-signals`, `auto-stale`, `auto-start`, `auto-status`, `auto-strategies`, `auto-symbols`, `auto-target`, `auto-uncertain`, `auto-universe`, `broker`, `broker-dot`, `broker-state`, `candidate-batch-actions`, `candidate-list`, `candidate-status`, `cash-product-choice`, `clear-candidate-selection`, `closed-pnl`, `closed-pnl-label`, `closed-positions`, `closed-summary`, `collect-candidates`, `confirm-funds`, `confirm-nifty-straddle-squareoff`, `confirm-straddle-squareoff`, `constituent-workflow`, `copy-packet`, `daily-loss-limit`, `download-packet`, `ema-band`, `ema-band-broker-chart`, `ema-band-chart-bars`, `ema-band-chart-timeframe`, `ema-band-confirmation`, `ema-band-contract`, `ema-band-cooldown`, `ema-band-direction`, `ema-band-execution-log`, `ema-band-length`, `ema-band-lots`, `ema-band-master-refresh`, `ema-band-master-status`, `ema-band-minimum-slope-atr`, `ema-band-mode`, `ema-band-mode-status`, `ema-band-paper-capital`, `ema-band-pnl-chart`, `ema-band-position-cards`, `ema-band-profit-protection-pct`, `ema-band-resistance-volume-exit`, `ema-band-resistance-volume-lookback`, `ema-band-resistance-volume-multiple`, `ema-band-runner-status`, `ema-band-runner-toggle`, `ema-band-search`, `ema-band-segment`, `ema-band-session`, `ema-band-slope-lookback`, `ema-band-status`, `ema-band-stop-pct`, `ema-band-strategy-direction`, `ema-band-target-pct`, `ema-band-ticket-preview`, `ema-band-timeframe`, `ema-band-tracked-positions`, `ema-band-underlying`, `ema-band-underlying-picker`, `ema-band-underlying-search`, `enforce-risk-controls`, `estimated-charges`, `estimated-charges-note`, `estimated-net-pnl`, `external-open-risk`, `funds`, `handoff`, `handoff-allocation-budget`, `handoff-batch-confirmation`, `handoff-batch-external-risk`, `handoff-batch-panel`, `handoff-batch-preview`, `handoff-batch-review`, `handoff-batch-status`, `handoff-budget-label`, `handoff-option-lots`, `handoff-option-lots-field`, `idea-risk-limit`, `include-funds`, `kama`, `kama-breakout`, `kama-capability`, `kama-chart`, `kama-chart-type`, `kama-cooldown`, `kama-efficiency`, `kama-events`, `kama-execution-mode`, `kama-exit-session`, `kama-fast`, `kama-idea-risk`, `kama-invalidation`, `kama-invalidation-help`, `kama-length`, `kama-minimum-slope-atr`, `kama-mode`, `kama-paper-capital`, `kama-policy`, `kama-quantity`, `kama-reclaims`, `kama-refresh-interval`, `kama-runner-status`, `kama-runner-toggle`, `kama-size-help`, `kama-slope-lookback`, `kama-slow`, `kama-state`, `kama-timeframe`, `kama-trade-rows`, `kama-trade-summary`, `kama-underlying`, `kama-underlying-search`, `kama-underlying-status`, `live-pnl`, `market-overview`, `max-positions`, `minimum-rr`, `nifty-premium-chart`, `nifty-straddle`, `nifty-straddle-action-status`, `nifty-straddle-contract`, `nifty-straddle-entry-end`, `nifty-straddle-entry-start`, `nifty-straddle-lots`, `nifty-straddle-options`, `nifty-straddle-output`, `nifty-straddle-position`, `nifty-straddle-runner-state`, `nifty-straddle-squareoff-confirmation`, `nifty-straddle-squareoff-preview`, `nifty-straddle-squareoff-review`, `nifty-straddle-stoploss`, `nifty-straddle-tab`, `nifty-straddle-target`, `nifty-straddle-trades`, `nifty-straddle-updated`, `open-count`, `open-positions`, `order-type`, `packet-panel`, `packet-preview`, `packet-status`, `parser-lifecycle-refresh`, `parser-lifecycle-status`, `parser-protect`, `parser-protection-target`, `pipeline-kicker`, `pipeline-message`, `pipeline-track`, `planning-capital`, `policy-impact`, `policy-validation`, `premium-chart`, `premium-chart-updated`, `prepare-handoff-batch`, `prepare-packet`, `prepare-screener-order`, `prepare-ticket`, `preview-auto-policy`, `reauth`, `reauth-help`, `refresh-pipeline`, `refresh-screeners`, `risk-reserve`, `risk-strip`, `save-auto-draft`, `save-auto-policy`, `screener`, `screener-analysis`, `screener-analysis-next`, `screener-analysis-results`, `screener-analysis-status`, `screener-batch-selection`, `screener-bulk-selection`, `screener-clear-selection`, `screener-label`, `screener-options`, `screener-options-results`, `screener-options-status`, `screener-order`, `screener-order-confirmation`, `screener-order-external-risk`, `screener-order-preview`, `screener-order-product`, `screener-order-review`, `screener-order-status`, `screener-select-all`, `screener-selected-count`, `screener-sources`, `screener-status`, `screener-url`, `screener-watchlist`, `screener-watchlist-results`, `sector-body`, `sector-detail`, `sector-filter`, `sector-sort`, `sectors`, `select-all-candidates`, `sensex-straddle`, `sensex-straddle-tab`, `settings`, `settings-content`, `squareoff-nifty-straddle`, `squareoff-straddle`, `start-nifty-straddle`, `start-straddle`, `stop-basis`, `stop-nifty-straddle`, `stop-straddle`, `straddle-action-status`, `straddle-contract`, `straddle-entry-end`, `straddle-entry-start`, `straddle-lots`, `straddle-options`, `straddle-output`, `straddle-position`, `straddle-runner-state`, `straddle-squareoff-confirmation`, `straddle-squareoff-preview`, `straddle-squareoff-review`, `straddle-trades`, `straddle-updated`, `straddles`, `strongest-stocks`, `submit-handoff-batch`, `submit-screener-order`, `submit-ticket`, `ticket-broker`, `ticket-capability`, `ticket-confirmation`, `ticket-lots`, `ticket-panel`, `ticket-preview`, `ticket-proposal`, `ticket-review`, `ticket-status`, `trade-parser`, `trade-parser-ai-result`, `trade-parser-clear`, `trade-parser-entry-help`, `trade-parser-entry-mode`, `trade-parser-input`, `trade-parser-limit-price`, `trade-parser-lots`, `trade-parser-ltp`, `trade-parser-order`, `trade-parser-order-status`, `trade-parser-refresh-ltp`, `trade-parser-result`, `trade-parser-run`, `trade-parser-status`, `trade-parser-submit-order`, `trade-parser-trigger-price`, `weight-source`

## delta-adaptive.js

[Owning source](../delta-adaptive.js)

### Named functions

`button`, `mount`, `paint`, `payload`, `perform`, `plot`, `poll`, `request`, `table`

### UI field and toggle identifiers

`dar-add`, `dar-ai`, `dar-asof`, `dar-cancel`, `dar-comparison`, `dar-curve`, `dar-error`, `dar-experiments`, `dar-fields`, `dar-folds`, `dar-form`, `dar-history`, `dar-input-`, `dar-library`, `dar-panel`, `dar-progress`, `dar-proposal`, `dar-proposal-box`, `dar-review`, `dar-run`, `dar-seal`, `dar-selection`, `dar-settings`, `dar-start`, `dar-state`, `dar-stop`

## delta-backtest.js

[Owning source](../delta-backtest.js)

### Named functions

`count`, `coverageReport`, `mount`, `paintDetail`, `payload`, `plot`, `poll`, `ranking`, `render`, `request`, `save`, `selectResult`, `sync`, `table`

### UI field and toggle identifiers

`dbt-adx`, `dbt-adx-compare`, `dbt-adx-values`, `dbt-bb-dev`, `dbt-bb-lengths`, `dbt-cancel`, `dbt-capital`, `dbt-contracts`, `dbt-copy`, `dbt-count`, `dbt-coverage`, `dbt-direction`, `dbt-download`, `dbt-drawdown`, `dbt-end`, `dbt-entry`, `dbt-equity`, `dbt-equity-label`, `dbt-fee`, `dbt-filters`, `dbt-form`, `dbt-form-error`, `dbt-funding`, `dbt-holdout`, `dbt-job`, `dbt-job-state`, `dbt-lookback`, `dbt-ma`, `dbt-ma-types`, `dbt-metrics`, `dbt-model`, `dbt-momentum`, `dbt-momentum-compare`, `dbt-percentile`, `dbt-progress`, `dbt-progress-text`, `dbt-ranking`, `dbt-release`, `dbt-results`, `dbt-rsi`, `dbt-run`, `dbt-segment`, `dbt-selected`, `dbt-slip`, `dbt-spread`, `dbt-start`, `dbt-symbol`, `dbt-test-band`, `dbt-timeframes`, `dbt-trade-next`, `dbt-trade-page`, `dbt-trade-prev`, `dbt-trades`, `dbt-train-band`, `delta-backtest-panel`, `delta-market-panel`

## delta-india.js

[Owning source](../delta-india.js)

### Named functions

`accountTable`, `act`, `chartSubmit`, `check`, `connect`, `create`, `executionCandidate`, `flush`, `invalidate`, `loadCatalog`, `mount`, `orderControls`, `pnlLine`, `populate`, `refresh`, `refreshAccount`, `refreshExecutionChart`, `refreshMarkers`, `refreshPaperHistoryColors`, `refreshRoutes`, `renderChartPositions`, `renderJournal`, `renderMonitoring`, `renderPnl`, `renderStatus`, `renderSubmitCondition`, `renderWorkflowPositions`, `repair`, `request`, `restorePreferences`, `routeSummary`, `savePreferences`, `schedule`, `strategyControls`, `submitStrategySettings`, `submitTicket`, `ticket`, `trailingPreview`

### UI field and toggle identifiers

`delta-account`, `delta-account-basis`, `delta-account-disclosure`, `delta-account-panel`, `delta-account-status`, `delta-account-summary`, `delta-account-text`, `delta-adx-enabled`, `delta-adx-note`, `delta-adx-threshold`, `delta-ask`, `delta-auth`, `delta-bid`, `delta-broker`, `delta-catalog`, `delta-chart`, `delta-chart-buy`, `delta-chart-route`, `delta-chart-sell`, `delta-close`, `delta-close-runner`, `delta-connect`, `delta-connection-panel`, `delta-contracts`, `delta-control-state`, `delta-current-position-panel`, `delta-direction`, `delta-events`, `delta-execution-chart`, `delta-execution-disclosure`, `delta-execution-summary`, `delta-history`, `delta-history-source`, `delta-india`, `delta-indicator-panel`, `delta-inr-policy-note`, `delta-journal`, `delta-journal-download`, `delta-journal-note`, `delta-key`, `delta-lifecycle-disclosure`, `delta-lifecycle-summary`, `delta-live-fills`, `delta-live-positions`, `delta-ma`, `delta-ma-length`, `delta-message`, `delta-mode`, `delta-momentum-enabled`, `delta-momentum-note`, `delta-monitoring-health`, `delta-note`, `delta-order-note`, `delta-order-type`, `delta-orders`, `delta-paper-capital`, `delta-paper-disclosure`, `delta-paper-funds`, `delta-paper-history-panel`, `delta-paper-summary`, `delta-positions-disclosure`, `delta-positions-summary`, `delta-price`, `delta-price-field`, `delta-price-inr`, `delta-price-label`, `delta-product`, `delta-reduce`, `delta-refresh`, `delta-restore-exit`, `delta-rsi`, `delta-runner`, `delta-runner-note`, `delta-saved-credentials`, `delta-saved-history`, `delta-saved-symbol`, `delta-search`, `delta-secret`, `delta-side`, `delta-signal`, `delta-start`, `delta-stop`, `delta-strategy-help`, `delta-strategy-mode`, `delta-strategy-route-state`, `delta-stream-health`, `delta-submit`, `delta-submit-condition`, `delta-symbol`, `delta-ticket-auth`, `delta-ticket-mode`, `delta-ticket-panel`, `delta-ticket-route`, `delta-tif`, `delta-timeframe`, `delta-trailing-enabled`, `delta-trailing-mode`, `delta-trailing-preview`, `delta-trailing-state`, `delta-trailing-step`, `delta-trailing-step-label`, `delta-type`, `delta-workflow`, `delta-workflow-disclosure`, `delta-workflow-pnl`, `delta-workflow-positions`, `delta-workflow-summary`

## delta-inr.js

[Owning source](../delta-inr.js)

### Named functions

`format`, `load`, `note`, `set`, `valid`, `value`

## delta-journal.js

[Owning source](../delta-journal.js)

## ema-cloud-chart.js

[Owning source](../ema-cloud-chart.js)

### Named functions

`activePrice`, `adxRows`, `bollingerRows`, `chart`, `clock`, `closeMenu`, `displayRows`, `drawCloud`, `drawRsiZones`, `drawingList`, `entrySignals`, `fibCaption`, `legend`, `mount`, `mtfRows`, `paint`, `paintCaptions`, `preserveRange`, `refreshMtf`, `renkoRows`, `saveDrawings`, `sessionBands`, `setLevels`, `setPositionOverlay`, `showOverlayCaptions`, `sizePanes`, `updateBollinger`, `updatePriceStyle`

### UI field and toggle identifiers

`bollinger`, `cloud`, `cpr`, `ema`, `fixed-fib`, `floating-fib`, `levels`, `mtf`, `periods`, `rsi`, `sessions`, `tentative`, `volume`, `zones`

## ema-crossover-live.js

[Owning source](../ema-crossover-live.js)

### Named functions

`applyLabel`, `config`, `groupBefore`, `invalidate`, `mount`, `refresh`, `render`, `request`, `restoreSettings`, `saveSettings`

### UI field and toggle identifiers

`cross-budget`, `cross-journal`, `cross-label`, `cross-live-message`, `cross-live-state`, `cross-lots`, `cross-max-trades`, `cross-mode`, `cross-order-action`, `cross-order-contract`, `cross-order-history`, `cross-order-phase`, `cross-order-price`, `cross-order-quantity`, `cross-order-reference`, `cross-order-time`, `cross-owned`, `cross-paper-capital`, `cross-paper-funds`, `cross-pending`, `cross-premium`, `cross-runner-start`, `cross-runtime`, `cross-spot-stop`, `cross-spot-target`, `cross-trailing-allocation`, `cross-trailing-choice`, `cross-trailing-enabled`, `cross-trailing-mode`, `cross-trailing-state`, `cross-trailing-step`

## ema-crossover.js

[Owning source](../ema-crossover.js)

### Named functions

`clear`, `get`, `load`, `mount`, `rsiSignals`, `sectionVisible`, `signals`

### UI field and toggle identifiers

`cross-chart`, `cross-event`, `cross-history`, `cross-ma-type`, `cross-pnl`, `cross-rsi-length`, `cross-search`, `cross-sma-length`, `cross-status`, `cross-symbol`, `cross-timeframe`, `cross-trend`, `cross-values`, `ema-cross`

## paper-capital.js

[Owning source](../paper-capital.js)

### Named functions

`ensure`

## position-history-links.js

[Owning source](../position-history-links.js)

## position-history-metadata.js

[Owning source](../position-history-metadata.js)

## position-history.js

[Owning source](../position-history.js)

### Named functions

`project`

## redbar-overlays.js

[Owning source](../redbar-overlays.js)

### Named functions

`dailyReferences`, `fibonacciReferences`, `parts`, `referencesForView`, `sessionMarkers`, `supplyDemand`, `zonedTimestamp`

## renko-assessment.js

[Owning source](../renko-assessment.js)

### Named functions

`assessment`

## renko-supertrend.js

[Owning source](../renko-supertrend.js)

### Named functions

`applyNamedFields`, `applyStatus`, `cashEquity`, `chartAnalysisAvailable`, `chartCandles`, `chartControlState`, `chartStreamHealth`, `chartStreamStatus`, `chooseConfiguration`, `clearAnalysis`, `closeConfigOptions`, `configurationLibrary`, `configurationState`, `configurationText`, `connectStream`, `controls`, `costPnlValues`, `deleteConfiguration`, `disclosure`, `eventTable`, `executionMarkers`, `fiveMinuteSupertrendPoints`, `fiveMinuteZoneRows`, `hostZones`, `inrPolicy`, `instanceList`, `invalidate`, `load`, `loadNamedConfiguration`, `managerTable`, `matchInstrumentConfiguration`, `mount`, `overrideState`, `paintAssessment`, `paintChartControls`, `paintConfigOptions`, `paintMarkers`, `paintPnl`, `paintRsi`, `paintSideways`, `paintStreamHealth`, `paintSupertrendPointers`, `paintZones`, `persistDraft`, `pnlValues`, `positionAssessment`, `preservePreviousDraft`, `readCandle`, `rebuildSma`, `refreshBroker`, `renderTradeTable`, `renderTrades`, `request`, `restore`, `restoredConfigurationFields`, `rsiHistory`, `rsiSma`, `rsiStep`, `rsiZone`, `saveBatchSelection`, `searchInstruments`, `signalNavigation`, `signalSettings`, `smaPeriod`, `status`, `storeConfiguration`, `syncChartControl`, `syncRsiHover`, `table`, `toggleRunner`, `toggleState`, `volumePoints`, `writeLibrary`, `zoneBandPrimitive`, `zoneBandRect`

### UI field and toggle identifiers

`renko-`, `renko-action-error`, `renko-add-batch`, `renko-additional-slippage-points`, `renko-adopt`, `renko-adopted-managers`, `renko-adoption-reentry`, `renko-adoption-status`, `renko-adx-length`, `renko-adx-smoothing`, `renko-adx-threshold`, `renko-anchor`, `renko-assessment`, `renko-assessment-wire`, `renko-atr-length`, `renko-batch-help`, `renko-batch-result`, `renko-batch-summary`, `renko-batch-symbols`, `renko-box`, `renko-brick-mode`, `renko-broker`, `renko-broker-note`, `renko-broker-orders`, `renko-broker-positions`, `renko-broker-refresh`, `renko-candle-readout`, `renko-carry-policy`, `renko-cash-note`, `renko-cash-product`, `renko-cash-product-field`, `renko-chart`, `renko-chart-action-error`, `renko-chart-control-note`, `renko-chart-controls`, `renko-chart-description`, `renko-chart-mode`, `renko-chart-mode-state`, `renko-chart-stack`, `renko-chart-stop`, `renko-chart-toggle`, `renko-chart-toolbar`, `renko-chart-view`, `renko-commodity-holding`, `renko-commodity-holding-field`, `renko-config-dropdown`, `renko-config-name`, `renko-config-option-`, `renko-config-options`, `renko-config-state`, `renko-daily-budget`, `renko-delete-configuration`, `renko-direction`, `renko-ema-exit-enabled`, `renko-ema-exit-length`, `renko-ema-proximity-distance`, `renko-ema-proximity-enabled`, `renko-ema-proximity-mode`, `renko-entry-audit`, `renko-event`, `renko-events`, `renko-events-page`, `renko-exit-fullscreen`, `renko-export-settings`, `renko-factor`, `renko-fit-chart`, `renko-full-chart`, `renko-history-from`, `renko-history-preset`, `renko-history-range`, `renko-history-to`, `renko-inr-policy-note`, `renko-instance-count`, `renko-instances`, `renko-intrabar-entries`, `renko-journal-mode`, `renko-latest-signal`, `renko-live-pnl`, `renko-lots`, `renko-manual-brick`, `renko-market`, `renko-market-policy-note`, `renko-market-structure-enabled`, `renko-market-structure-state`, `renko-max-premium`, `renko-max-trades`, `renko-mode`, `renko-mode-note`, `renko-named-config-note`, `renko-new-instance`, `renko-newer-events`, `renko-older-events`, `renko-order-terms`, `renko-orders`, `renko-override-direction`, `renko-override-entry`, `renko-override-note`, `renko-paper-capital`, `renko-paper-funds`, `renko-pnl`, `renko-policy`, `renko-price-source`, `renko-provisional-status`, `renko-readable-chart`, `renko-reset-chart`, `renko-retest-enabled`, `renko-retest-engulfing`, `renko-retest-harami`, `renko-retest-star`, `renko-retest-status`, `renko-rsi-chart`, `renko-rsi-hover`, `renko-rsi-readout`, `renko-rsi-slope-enabled`, `renko-rsi-slope-status`, `renko-rsi-sma-period`, `renko-rsi-sma-readout`, `renko-runner-message`, `renko-runner-panel`, `renko-save-settings`, `renko-search`, `renko-session-deadline`, `renko-show-five-minute-label`, `renko-show-one-minute-label`, `renko-sideways-enabled`, `renko-sideways-max-candles`, `renko-sideways-status`, `renko-signal-range`, `renko-spot-stop`, `renko-spot-target`, `renko-st`, `renko-start-selected`, `renko-state`, `renko-status`, `renko-stream-status`, `renko-supertrend`, `renko-supertrend-pointers`, `renko-supertrend-visuals`, `renko-symbol`, `renko-timeframe`, `renko-toggle`, `renko-trades`, `renko-trailing-basis`, `renko-trailing-distance`, `renko-trailing-enabled`, `renko-trailing-status`, `renko-use-adx`, `renko-widening-window`, `renko-workspace`, `renko-zone-status`, `renko-zone-target-enabled`, `renko-zone-target-state`

## sector-dashboard-model.js

[Owning source](../sector-dashboard-model.js)

### Named functions

`analysisStatusText`, `exposeSectorDashboardModel`, `filterAndSortSectors`, `latestDataTimestamp`, `qualityText`, `refreshPhaseState`, `riskPolicyPreview`, `rotationDisplay`, `rotationOverviewValue`

## telegram-parser.js

[Owning source](../telegram-parser.js)

### Named functions

`action`, `api`, `invalidate`, `render`

### UI field and toggle identifiers

`telegram-parser`, `tg-auto`, `tg-broker`, `tg-channel`, `tg-channel-label`, `tg-connection`, `tg-entry-mode`, `tg-interval`, `tg-limit`, `tg-message`, `tg-parse`, `tg-quantity`, `tg-quantity-label`, `tg-queue`, `tg-refresh`, `tg-save`, `tg-start`, `tg-stop`, `tg-submit`, `tg-text`, `tg-ticket`, `tg-token`, `tg-trigger`, `tg-verify`

## trade-parser-advisory.js

[Owning source](../trade-parser-advisory.js)

### Named functions

`create`, `render`

## trade-parser-quote.js

[Owning source](../trade-parser-quote.js)

### Named functions

`clear`, `create`, `refresh`, `render`, `select`

## whatsapp-polling.js

[Owning source](../whatsapp-polling.js)

### Named functions

`act`, `api`, `refreshStatus`, `render`

### UI field and toggle identifiers

`wa-group`, `wa-interval`, `wa-queue`, `wa-refresh`, `wa-save`, `wa-source`, `wa-start`, `wa-status`, `wa-stop`
