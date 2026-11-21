# Generated source and settings reference

Generated from source on 21 November 2026 without importing modules or reading credential/runtime files. This is a coverage map of all Python application, strategy, helper and research sources and root JavaScript. It complements the [technical guide](technical-guide.md), [user guide](user-functional-guide.md), and [deployment guide](deployment-guide.md). Function signatures list exact defaults; payload-setting entries list literal fallbacks. Defaults in wrappers can override helper defaults. Research modules remain research-only. Source links own full branches, formulas, validation and rounding; the catalog does not execute them.

## backtesting/btc_antichop_permissive_20261028/anti_chop_snapshot.py

[Owning source](../backtesting/btc_antichop_permissive_20261028/anti_chop_snapshot.py)

Optional, completed-host-candle, entry-only anti-chop checklist.

### Callables and explicit defaults

- `settings(payload)`
- `standalone_rules(payload)`
- `compatible(payload)`
- `observe(state, candle, config, direction, seconds=300)`
- `apply(entry, gate)`
- `generate_entry(entry, gate, state)`

### Literal payload and lookup fallbacks

- `count` → `0`
- `timeframe` → `'5 minutes'`

### Configuration literals

- `DEFAULTS = dict(anti_chop_enabled=False, anti_chop_role='Filter', anti_chop_mode='Adaptive', anti_chop_atr_length=14, anti_chop_atr_average_length=20, anti_chop_ema_fast_length=20, anti_chop_ema_slow_length=50, anti_chop_adaptive_window=200, anti_chop_slope_percentile=60.0, anti_chop_gap_percentile=60.0, anti_chop_overlap_percentile=40.0, anti_chop_slope_bars=3, anti_chop_slope_atr=0.15, anti_chop_gap_atr=0.2, anti_chop_cross_bars=6, anti_chop_structure_bars=3, anti_chop_overlap_percent=50.0)`

## backtesting/btc_antichop_permissive_20261028/btc_antichop_compare.py

[Owning source](../backtesting/btc_antichop_permissive_20261028/btc_antichop_compare.py)

Read-only BTCUSD adaptive anti-chop research; never accesses order APIs.

### Callables and explicit defaults

- `simulate(name, qualified, directions, begin, end, cost)`

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

## backtesting/ema_gap_contraction_review/review.py

[Owning source](../backtesting/ema_gap_contraction_review/review.py)

### Callables and explicit defaults

- `stats(data)`

## backtesting/goldm_reentry/research_20261029.py

[Owning source](../backtesting/goldm_reentry/research_20261029.py)

Frozen GOLDM underlying proxy experiment. Never imports runner or broker.

### Callables and explicit defaults

- `day(t)`
- `generate(mult)`
- `simulate(obs, policy, delay=0)`
- `stats(ts, selected)`

### Literal payload and lookup fallbacks

- `entry_qualified` → `False`

## backtesting/goldm_reentry/validate_20261029.py

[Owning source](../backtesting/goldm_reentry/validate_20261029.py)

### Callables and explicit defaults

- `e(st, brick, cross=None)`

## backtesting/handoff_structure_20261101/research.py

[Owning source](../backtesting/handoff_structure_20261101/research.py)

Fixed-design causal swing test; research only.

### Callables and explicit defaults

- `load(s)`
- `candles(d)`
- `structures(d)`

## backtesting/handoff_structure_20261101/robustness.py

[Owning source](../backtesting/handoff_structure_20261101/robustness.py)

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

## backtesting/nifty_antichop_20261028/build_report.py

[Owning source](../backtesting/nifty_antichop_20261028/build_report.py)

### Callables and explicit defaults

- `table(df)`

## backtesting/nifty_antichop_20261028/extra_evidence.py

[Owning source](../backtesting/nifty_antichop_20261028/extra_evidence.py)

## backtesting/nifty_antichop_20261028/nifty_antichop_backtest.py

[Owning source](../backtesting/nifty_antichop_20261028/nifty_antichop_backtest.py)

Read-only NIFTY spot-index filter study and explicitly hypothetical strategy.

### Callables and explicit defaults

- `read_frame(name)`
- `regular(d)`

## backtesting/nifty_antichop_20261028/verify_antichop.py

[Owning source](../backtesting/nifty_antichop_20261028/verify_antichop.py)

## backtesting/nifty_atm_options/analyse_results.py

[Owning source](../backtesting/nifty_atm_options/analyse_results.py)

Summarise the frozen development-selected grid; never tune on validation.

### Callables and explicit defaults

- `analyse(folder)`

### Literal payload and lookup fallbacks

- `trades` → `{}`

## backtesting/nifty_atm_options/archive_data.py

[Owning source](../backtesting/nifty_atm_options/archive_data.py)

Create a credential-free, version-preserving market-data archive.

### Callables and explicit defaults

- `archive(folder, destination)`

### Literal payload and lookup fallbacks

- `option_files` → `[]`
- `responses` → `[]`
- `rows` → `[]`
- `timestamp` → `[]`
- `underlying_files` → `[]`

## backtesting/nifty_atm_options/audit_results.py

[Owning source](../backtesting/nifty_atm_options/audit_results.py)

Offline consistency audit of prices, contract continuity and selection.

## backtesting/nifty_atm_options/build_report.py

[Owning source](../backtesting/nifty_atm_options/build_report.py)

Render the audited grid summary as a reviewable Markdown artifact.

### Callables and explicit defaults

- `describe(r, grid)`
- `render(folder)`

## backtesting/nifty_atm_options/expiry_calendar.py

[Owning source](../backtesting/nifty_atm_options/expiry_calendar.py)

Calendar-derived expected expiry; not broker-certified historical contract metadata.

### Callables and explicit defaults

- `expected_weekly_expiry(day)`

## backtesting/nifty_atm_options/fetch_history.py

[Owning source](../backtesting/nifty_atm_options/fetch_history.py)

Resumable read-only option history. Never imports trading/order clients.

### Callables and explicit defaults

- `fetch_history(credentials_path, underlying_path, destination, workers=3, offsets=range(-3, 4))`

### Literal payload and lookup fallbacks

- `cached` → `False`

## backtesting/nifty_atm_options/journal_candidates.py

[Owning source](../backtesting/nifty_atm_options/journal_candidates.py)

Append explicitly exploratory journals without changing frozen selection.

## backtesting/nifty_atm_options/prepare_signals.py

[Owning source](../backtesting/nifty_atm_options/prepare_signals.py)

Freeze a bounded grid using production indicator components, research only.

## backtesting/nifty_atm_options/repair_history.py

[Owning source](../backtesting/nifty_atm_options/repair_history.py)

Fetch only missing fixed-strike history using the documented ATM-relative band.

### Callables and explicit defaults

- `repair(folder, results_path, credentials_path, workers=6)`

### Literal payload and lookup fallbacks

- `strike` → `[]`
- `timestamp` → `[]`

## backtesting/nifty_atm_options/replay.py

[Owning source](../backtesting/nifty_atm_options/replay.py)

Offline option-candle replay. No broker, service, order or runner objects.

### Callables and explicit defaults

- `aggregate(rows, minutes)`
- `atm_strike(price)`
- `fixed_quote(quotes, timestamp, side, strike, expected_expiry=None)`
- `load_quotes(directories)`
- `metrics(trades, curve)`
- `simulate(rows, signals, quotes, entry_config, risk, zone_timeline, rsi_context, period_days, keep_trades=False)`

### Literal payload and lookup fallbacks

- `timestamp` → `[]`

## backtesting/nifty_atm_options/run_grid.py

[Owning source](../backtesting/nifty_atm_options/run_grid.py)

Checkpointed read-only parameter replay. Two research CPU workers at most.

### Callables and explicit defaults

- `batch(n)`
- `main()`

## backtesting/nifty_atm_options/seal_study.py

[Owning source](../backtesting/nifty_atm_options/seal_study.py)

Hash the credential-free replay inputs, source, caches and final artifacts.

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

## backtesting/nifty_renko12_one_brick_20261110/backtest.py

[Owning source](../backtesting/nifty_renko12_one_brick_20261110/backtest.py)

Research-only one-brick-reversal Renko12; minute-close path approximation.

### Callables and explicit defaults

- `frame(rows)`
- `cents(value)`
- `step(level, price)`
- `provider(path, params, name)`
- `master(day, part)`
- `load(sym)`
- `cost(p, qty, buy)`
- `exit_time(sym, wanted)`
- `eligible_breakout(batch, lock, at)`
- `close(ts, reason)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_renko12_one_brick_20261110/job_runtime.py

[Owning source](../backtesting/nifty_renko12_one_brick_20261110/job_runtime.py)

### Callables and explicit defaults

- `write()`
- `progress(stage=None, **items)`
- `heartbeats()`

## backtesting/nifty_renko12_one_brick_20261110/run_job.py

[Owning source](../backtesting/nifty_renko12_one_brick_20261110/run_job.py)

## backtesting/nifty_renko12_one_brick_20261110/verify.py

[Owning source](../backtesting/nifty_renko12_one_brick_20261110/verify.py)

Independent audit of the minute-close Renko approximation, not tick-fidelity certification.

### Callables and explicit defaults

- `metrics(d)`
- `fee(p, q, buy)`
- `scenario(delta)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_renko_10pt_multitimeframe/nifty_renko_10pt_multitimeframe.py

[Owning source](../backtesting/nifty_renko_10pt_multitimeframe/nifty_renko_10pt_multitimeframe.py)

Read-only NIFTY 10-point fixed-brick Renko reversal research across timeframes.

### Callables and explicit defaults

- `main()`

## backtesting/nifty_renko_30sessions_20261019/fetch.py

[Owning source](../backtesting/nifty_renko_30sessions_20261019/fetch.py)

Research-only historical downloads. No order or runner mutations.

### Literal payload and lookup fallbacks

- `bars` → `0`
- `candles` → `[]`

## backtesting/nifty_renko_30sessions_20261019/fetch_options.py

[Owning source](../backtesting/nifty_renko_30sessions_20261019/fetch_options.py)

Resumable historical download only; no execution clients.

### Callables and explicit defaults

- `work(t)`

## backtesting/nifty_renko_30sessions_20261019/finalize.py

[Owning source](../backtesting/nifty_renko_30sessions_20261019/finalize.py)

## backtesting/nifty_renko_30sessions_20261019/report.py

[Owning source](../backtesting/nifty_renko_30sessions_20261019/report.py)

Produce retained research report and trade journals, never deploy settings.

### Callables and explicit defaults

- `metric(r, scenario, period)`
- `valid(r)`
- `score(r)`
- `eligible(r)`

## backtesting/nifty_renko_30sessions_20261019/research.py

[Owning source](../backtesting/nifty_renko_30sessions_20261019/research.py)

Offline research of current production Renko formulas. Never instantiates a runner.

### Callables and explicit defaults

- `clock(ts)`
- `aggregate(rows, n)`
- `configs(base)`
- `load_spot()`
- `prepare()`
- `load_quotes()`
- `measure(trades, curve)`
- `simulate(minute, host, signals, c, quotes, days, slip)`
- `run()`

### Literal payload and lookup fallbacks

- `ema_exit_length` → `30`

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

## backtesting/nifty_sma30_five_minute_20261110/backtest.py

[Owning source](../backtesting/nifty_sma30_five_minute_20261110/backtest.py)

Five-minute signal and midpoint timeframe; minute-level option execution, read-only.

### Callables and explicit defaults

- `frame(rows)`
- `costs(p, qty, buy)`
- `bar_rule(direction, stop, first_target, activated, lo, hi, opposite_flip, priority='target')`
- `next_exit(symbol, ts)`
- `sell(a, ts, qty, reason)`
- `metrics(d)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_sma30_five_minute_20261110/verify.py

[Owning source](../backtesting/nifty_sma30_five_minute_20261110/verify.py)

Independent five-minute causality/equity audit and saved-result attribution.

## backtesting/nifty_sma30_options_20261110/nifty_sma30_backtest.py

[Owning source](../backtesting/nifty_sma30_options_20261110/nifty_sma30_backtest.py)

Read-only FYERS baseline. Run from project root; no runner or order APIs.

### Callables and explicit defaults

- `get(name, path, params)`
- `frame(rows)`
- `symbol(day, strike, side)`
- `costs(p, buy)`
- `serial(x)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_sma30_six_month_20261110/backtest.py

[Owning source](../backtesting/nifty_sma30_six_month_20261110/backtest.py)

Five-minute signal and midpoint timeframe; minute-level option execution, read-only.

### Callables and explicit defaults

- `frame(rows)`
- `provider(path, params, name)`
- `load_option(sym)`
- `costs(p, qty, buy)`
- `bar_rule(direction, stop, first_target, activated, lo, hi, opposite_flip, priority='target')`
- `next_exit(symbol, ts)`
- `sell(a, ts, qty, reason)`
- `metrics(d)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_sma30_six_month_20261110/job_runtime.py

[Owning source](../backtesting/nifty_sma30_six_month_20261110/job_runtime.py)

### Callables and explicit defaults

- `write()`
- `progress(stage=None, **items)`
- `heartbeats()`

## backtesting/nifty_sma30_six_month_20261110/run_job.py

[Owning source](../backtesting/nifty_sma30_six_month_20261110/run_job.py)

## backtesting/nifty_sma30_six_month_20261110/verify.py

[Owning source](../backtesting/nifty_sma30_six_month_20261110/verify.py)

Read-only validation, coverage audit, monthly attribution and fixed-path execution sensitivity.

### Callables and explicit defaults

- `metric(d)`
- `cost(p, qty, buy)`
- `slipcase(delta)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_sma30_two_lot_midpoint_20261110/analyze_exits.py

[Owning source](../backtesting/nifty_sma30_two_lot_midpoint_20261110/analyze_exits.py)

Read-only exit attribution of saved ledgers; does not rerun strategy.

### Callables and explicit defaults

- `group(d, key)`

## backtesting/nifty_sma30_two_lot_midpoint_20261110/backtest.py

[Owning source](../backtesting/nifty_sma30_two_lot_midpoint_20261110/backtest.py)

Two-lot first-target partial plus causal candle-midpoint trail; read-only.

### Callables and explicit defaults

- `frame(rows)`
- `costs(p, qty, buy)`
- `bar_rule(direction, stop, first_target, activated, lo, hi)`
- `next_exit(symbol, ts)`
- `sell(a, ts, qty, reason)`
- `metrics(d)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_sma30_two_lot_midpoint_20261110/verify.py

[Owning source](../backtesting/nifty_sma30_two_lot_midpoint_20261110/verify.py)

## backtesting/nifty_sma30_two_lot_sma_exit_20261110/analyze_losses.py

[Owning source](../backtesting/nifty_sma30_two_lot_sma_exit_20261110/analyze_losses.py)

Read-only attribution of saved corrected two-lot SMA-exit ledgers.

### Callables and explicit defaults

- `agg(d, key)`

## backtesting/nifty_sma30_two_lot_sma_exit_20261110/backtest.py

[Owning source](../backtesting/nifty_sma30_two_lot_sma_exit_20261110/backtest.py)

Corrected two-lot pre-target SMA flip, then partial and midpoint trail; read-only.

### Callables and explicit defaults

- `frame(rows)`
- `costs(p, qty, buy)`
- `bar_rule(direction, stop, first_target, activated, lo, hi, opposite_flip, priority='target')`
- `next_exit(symbol, ts)`
- `sell(a, ts, qty, reason)`
- `metrics(d)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`

## backtesting/nifty_sma30_two_lot_sma_exit_20261110/verify.py

[Owning source](../backtesting/nifty_sma30_two_lot_sma_exit_20261110/verify.py)

Independent read-only checks of corrected study and collision sensitivity.

## backtesting/nifty_sma30_v1_grid_20261110/audit_grid.py

[Owning source](../backtesting/nifty_sma30_v1_grid_20261110/audit_grid.py)

Audit causal V1 grid availability; no invented target/stop trading results.

## backtesting/nifty_sma30_v1_grid_20261110/grid_backtest.py

[Owning source](../backtesting/nifty_sma30_v1_grid_20261110/grid_backtest.py)

Read-only October V1 grid trailing study; run from project root.

### Callables and explicit defaults

- `frame(rows)`
- `costs(p, buy)`
- `step(direction, stop, targets, reached, entry, lo, hi)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`
- `same_bar_target_touch` → `False`

## backtesting/nifty_sma30_v1_grid_20261110/verify_comparison.py

[Owning source](../backtesting/nifty_sma30_v1_grid_20261110/verify_comparison.py)

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

## backtesting/renko_regime_calibration/adx_candidate.py

[Owning source](../backtesting/renko_regime_calibration/adx_candidate.py)

Frozen primary paper-research gate. Does not authorize or submit trades.

### Callables and explicit defaults

- `assess(rows, direction, now)`

## backtesting/renko_regime_calibration/audit.py

[Owning source](../backtesting/renko_regime_calibration/audit.py)

## backtesting/renko_regime_calibration/candidate.py

[Owning source](../backtesting/renko_regime_calibration/candidate.py)

Frozen paper-research assessment only. Never imports or calls an order adapter.

### Callables and explicit defaults

- `assess(rows, direction, now)`

## backtesting/renko_regime_calibration/grid.py

[Owning source](../backtesting/renko_regime_calibration/grid.py)

Bounded, declared sideways-regime calibration; completed information only.

### Callables and explicit defaults

- `add(family, **params)`
- `gate(history, name, direction)`

### Literal payload and lookup fallbacks

- `floor` → `0`
- `n` → `1`

## backtesting/renko_regime_calibration/price_action.py

[Owning source](../backtesting/renko_regime_calibration/price_action.py)

Causal confirmed price-structure checks; no new indicator entry gates.

### Callables and explicit defaults

- `gate(history, name, direction)`
- `initialize()`
- `main()`

## backtesting/renko_regime_calibration/report.py

[Owning source](../backtesting/renko_regime_calibration/report.py)

## backtesting/renko_regime_calibration/robustness.py

[Owning source](../backtesting/renko_regime_calibration/robustness.py)

Audit first-year shortlist without adjusting filter thresholds.

### Callables and explicit defaults

- `main()`

## backtesting/renko_regime_calibration/run.py

[Owning source](../backtesting/renko_regime_calibration/run.py)

Persistent two-process calibration. No credentials, live settings or order calls.

### Callables and explicit defaults

- `initialize()`
- `block(d)`
- `run_trial(name, brick=27.71, cap=2, recovery=False)`
- `checkpoint(status, **fields)`
- `main()`

## backtesting/renko_regime_calibration/select.py

[Owning source](../backtesting/renko_regime_calibration/select.py)

Explicit historical stability ranking, not selection on highest full-sample PF.

### Callables and explicit defaults

- `main()`

## backtesting/renko_regime_calibration/uncertainty.py

[Owning source](../backtesting/renko_regime_calibration/uncertainty.py)

Paired five-observed-session block resampling; descriptive uncertainty only.

### Callables and explicit defaults

- `run(name)`

## backtesting/renko_regime_lifecycle/report.py

[Owning source](../backtesting/renko_regime_lifecycle/report.py)

## backtesting/renko_regime_lifecycle/review.py

[Owning source](../backtesting/renko_regime_lifecycle/review.py)

Isolated two-year completed-candle underlying lifecycle research, never a live runner.

### Callables and explicit defaults

- `day(r)`
- `stats(trades, drag=2)`
- `filter_entry(history, name, direction)`
- `simulate(raw, config, rule, cap=2, drag=2, recovery=False)`
- `main()`

### Literal payload and lookup fallbacks

- `ema_exit_length` → `30`

## backtesting/renko_regime_lifecycle/robustness.py

[Owning source](../backtesting/renko_regime_lifecycle/robustness.py)

Frozen candidate checks: daily trade-limit and completed-OHLC recovery-lock sensitivity.

## backtesting/renko_regime_risk/high_win.py

[Owning source](../backtesting/renko_regime_risk/high_win.py)

High-hit-rate target/stop calibration with strict joint acceptance thresholds.

### Callables and explicit defaults

- `trial(entry, exit_name)`
- `main()`

## backtesting/renko_regime_risk/high_win_report.py

[Owning source](../backtesting/renko_regime_risk/high_win_report.py)

## backtesting/renko_regime_risk/model.py

[Owning source](../backtesting/renko_regime_risk/model.py)

One-minute underlying-price stop replay. No broker/order APIs.

### Callables and explicit defaults

- `day(stamp)`
- `stop_level(value, direction)`
- `stop_fill(position, bar)`
- `target_fill(position, bar)`
- `update_stop(position, bar, rule, drag)`
- `stats(trades, drag=2)`
- `simulate(hosts, minutes, config, entry_rule, exit_name, score_start, drag=2)`

## backtesting/renko_regime_risk/report.py

[Owning source](../backtesting/renko_regime_risk/report.py)

## backtesting/renko_regime_risk/robustness.py

[Owning source](../backtesting/renko_regime_risk/robustness.py)

Neighboring entry thresholds, stop distances and brick sizes; fixed existing exits.

### Callables and explicit defaults

- `trial(entry, exit_name, brick)`
- `main()`

## backtesting/renko_regime_risk/run.py

[Owning source](../backtesting/renko_regime_risk/run.py)

### Callables and explicit defaults

- `initialize()`
- `trial(entry, exit_name)`
- `checkpoint(status, **fields)`
- `main()`

## backtesting/renko_regime_risk/select.py

[Owning source](../backtesting/renko_regime_risk/select.py)

Risk-first shortlist: no rewarding zero-trade or breakeven streak tricks.

### Callables and explicit defaults

- `main()`

## backtesting/renko_sideways_entry/fetch_six_months.py

[Owning source](../backtesting/renko_sideways_entry/fetch_six_months.py)

Read-only FYERS history retrieval; never submits or changes orders.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## backtesting/renko_sideways_entry/research.py

[Owning source](../backtesting/renko_sideways_entry/research.py)

Research only. Never imported by runtime; no broker or order clients.

### Callables and explicit defaults

- `features(rows, cfg)`
- `allowed(s, policy)`
- `simulate(rows, signals, cfg, days, policy, bps, quota_mode='UNLIMITED')`
- `main()`

### Literal payload and lookup fallbacks

- `ema_exit_enabled` → `True`
- `ema_exit_length` → `30`

## backtesting/renko_sideways_entry/six_month_research.py

[Owning source](../backtesting/renko_sideways_entry/six_month_research.py)

Six-month extension: research only; no runtime imports or broker mutations.

### Callables and explicit defaults

- `main()`

## backtesting/renko_smc_review/audit.py

[Owning source](../backtesting/renko_smc_review/audit.py)

### Callables and explicit defaults

- `main()`

## backtesting/renko_smc_review/engine_audit.py

[Owning source](../backtesting/renko_smc_review/engine_audit.py)

Use the currently installed Engine calibrated gate, including its rearming.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `k` → `2`

## backtesting/renko_smc_review/parity.py

[Owning source](../backtesting/renko_smc_review/parity.py)

## backtesting/renko_smc_review/replay.py

[Owning source](../backtesting/renko_smc_review/replay.py)

One-minute underlying-price stop replay. No broker/order APIs.

### Callables and explicit defaults

- `day(stamp)`
- `stop_level(value, direction)`
- `stop_fill(position, bar)`
- `target_fill(position, bar)`
- `update_stop(position, bar, rule, drag)`
- `stats(trades, drag=2)`
- `simulate(hosts, minutes, config, entry_rule, exit_name, score_start, drag=2, entry_filter=None)`

## backtesting/renko_smc_review/report.py

[Owning source](../backtesting/renko_smc_review/report.py)

### Callables and explicit defaults

- `read(n)`
- `main()`

## backtesting/renko_smc_review/sensitivity_replay.py

[Owning source](../backtesting/renko_smc_review/sensitivity_replay.py)

One-minute underlying-price stop replay. No broker/order APIs.

### Callables and explicit defaults

- `day(stamp)`
- `stop_level(value, direction)`
- `stop_fill(position, bar)`
- `target_fill(position, bar)`
- `update_stop(position, bar, rule, drag)`
- `stats(trades, drag=2)`
- `simulate(hosts, minutes, config, entry_rule, exit_name, score_start, drag=2, entry_filter=None, recovery=False, rearm=False)`

## backtesting/renko_smc_review/smc.py

[Owning source](../backtesting/renko_smc_review/smc.py)

Deterministic completed-candle structure, no orders and no future pivots.

### Callables and explicit defaults

- `build_facts(rows, k=2)`
- `allows(fact, direction, price, atr, rule)`

## backtesting/renko_smc_review/study.py

[Owning source](../backtesting/renko_smc_review/study.py)

Offline SMC comparison. Cancel with a CANCEL file in this folder.

### Callables and explicit defaults

- `checkpoint(status, **kw)`
- `main()`

### Literal payload and lookup fallbacks

- `k` → `2`

## backtesting/renko_supertrend_regime/ema_slope_review.py

[Owning source](../backtesting/renko_supertrend_regime/ema_slope_review.py)

Frozen exploratory EMA slope / volatility comparisons; no execution imports.

### Callables and explicit defaults

- `assess(rows, rule)`
- `run(prior=False)`

## backtesting/renko_supertrend_regime/flatness_review.py

[Owning source](../backtesting/renko_supertrend_regime/flatness_review.py)

Exploratory prolonged-flatness entry filter, with optional completed-price breakout.

### Callables and explicit defaults

- `assess(rows, rule)`
- `main()`

## backtesting/renko_supertrend_regime/followup.py

[Owning source](../backtesting/renko_supertrend_regime/followup.py)

Exploratory follow-up; prior quarter results have already been inspected.

### Callables and explicit defaults

- `assess(rows, rule)`
- `main()`

## backtesting/renko_supertrend_regime/prior_year.py

[Owning source](../backtesting/renko_supertrend_regime/prior_year.py)

Freeze the follow-up specification and assess the earlier archive year.

## backtesting/renko_supertrend_regime/report.py

[Owning source](../backtesting/renko_supertrend_regime/report.py)

## backtesting/renko_supertrend_regime/review.py

[Owning source](../backtesting/renko_supertrend_regime/review.py)

Read-only index signal study. No broker execution or runner modifications.

### Callables and explicit defaults

- `day(r)`
- `assess(rows, rule)`
- `summary(rows)`
- `main()`

## backtesting/renko_supertrend_regime/slope_review.py

[Owning source](../backtesting/renko_supertrend_regime/slope_review.py)

Supertrend line slope only; other indicators are not added as regime gates.

### Callables and explicit defaults

- `assess(rows, rule)`
- `main()`

## backtesting/renko_supply_demand_review/audit.py

[Owning source](../backtesting/renko_supply_demand_review/audit.py)

### Callables and explicit defaults

- `main()`

## backtesting/renko_supply_demand_review/replay.py

[Owning source](../backtesting/renko_supply_demand_review/replay.py)

One-minute underlying-price stop replay. No broker/order APIs.

### Callables and explicit defaults

- `day(stamp)`
- `stop_level(value, direction)`
- `stop_fill(position, bar)`
- `target_fill(position, bar)`
- `update_stop(position, bar, rule, drag)`
- `stats(trades, drag=2)`
- `simulate(hosts, minutes, config, entry_rule, exit_name, score_start, drag=2, entry_filter=None, recovery=False, rearm=False, zone_context=None, zone_exits=False, remove_atr_target=False)`

## backtesting/renko_supply_demand_review/report.py

[Owning source](../backtesting/renko_supply_demand_review/report.py)

### Callables and explicit defaults

- `read(n)`
- `main()`

## backtesting/renko_supply_demand_review/study.py

[Owning source](../backtesting/renko_supply_demand_review/study.py)

Offline supply/demand tests. No broker, credentials or trading-setting writes.

### Callables and explicit defaults

- `checkpoint(status, **kw)`
- `requests()`
- `main()`

## backtesting/renko_supply_demand_review/verify_implementation.py

[Owning source](../backtesting/renko_supply_demand_review/verify_implementation.py)

Verify deployed helper against the saved 205-trade research candidate, offline.

### Callables and explicit defaults

- `main()`

## backtesting/renko_supply_demand_review/zones.py

[Owning source](../backtesting/renko_supply_demand_review/zones.py)

Use production strong-five-minute zones, with strictly causal timeline.

### Callables and explicit defaults

- `contexts(hosts)`
- `entry_distance(known, direction, price, atr)`
- `allowed(known, direction, price, atr, minimum)`

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

## backtesting/simple_brick_40_20261106/check_history_access.py

[Owning source](../backtesting/simple_brick_40_20261106/check_history_access.py)

### Literal payload and lookup fallbacks

- `DHAN_CLIENT_ID` → `''`

## backtesting/simple_brick_40_20261106/fetch.py

[Owning source](../backtesting/simple_brick_40_20261106/fetch.py)

Read-only research downloads; no runner or order methods.

### Callables and explicit defaults

- `status(**values)`
- `work(task)`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## backtesting/simple_brick_40_20261106/fyers_options.py

[Owning source](../backtesting/simple_brick_40_20261106/fyers_options.py)

Read-only FYERS exact-contract repair and wider premium surface.

### Callables and explicit defaults

- `get(path, query, name)`

### Literal payload and lookup fallbacks

- `contracts` → `{}`
- `message` → `''`
- `options` → `[]`

## backtesting/simple_brick_40_20261106/plan_repairs.py

[Owning source](../backtesting/simple_brick_40_20261106/plan_repairs.py)

## backtesting/simple_brick_40_20261106/probe_option.py

[Owning source](../backtesting/simple_brick_40_20261106/probe_option.py)

## backtesting/simple_brick_40_20261106/replay.py

[Owning source](../backtesting/simple_brick_40_20261106/replay.py)

Offline causal sampled-price replay of production Simple Brick rules.

### Callables and explicit defaults

- `day(ts)`
- `clock(ts)`
- `minute(ts)`
- `load_underlying()`
- `load_options(first, last)`
- `refs(days)`
- `simulate(mode, rows, days, sizing, quotes, surface)`
- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `response` → `{}`
- `symbol` → `''`
- `timestamp` → `[]`

## backtesting/simple_brick_40_20261106/verify.py

[Owning source](../backtesting/simple_brick_40_20261106/verify.py)

Independent ledger and framework validation; no broker access.

## backtesting/simple_brick_40_5m_20261106/replay.py

[Owning source](../backtesting/simple_brick_40_5m_20261106/replay.py)

Offline completed-five-minute-candle replay of production Simple Brick rules.

### Callables and explicit defaults

- `day(ts)`
- `clock(ts)`
- `minute(ts)`
- `load_underlying()`
- `load_options(first, last)`
- `refs(days)`
- `simulate(mode, rows, days, sizing, quotes, surface)`
- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `response` → `{}`
- `symbol` → `''`
- `timestamp` → `[]`

## backtesting/simple_brick_40_5m_20261106/verify.py

[Owning source](../backtesting/simple_brick_40_5m_20261106/verify.py)

Independent ledger and framework validation; no broker access.

## backtesting/simple_brick_40_true_1m_20261106/replay.py

[Owning source](../backtesting/simple_brick_40_true_1m_20261106/replay.py)

Offline causal sampled-price replay of production Simple Brick rules.

### Callables and explicit defaults

- `day(ts)`
- `clock(ts)`
- `minute(ts)`
- `load_underlying()`
- `load_options(first, last)`
- `refs(days)`
- `simulate(mode, rows, days, sizing, quotes, surface)`
- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `response` → `{}`
- `symbol` → `''`
- `timestamp` → `[]`

## backtesting/simple_brick_40_true_1m_20261106/verify.py

[Owning source](../backtesting/simple_brick_40_true_1m_20261106/verify.py)

Independent ledger and framework validation; no broker access.

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

## scripts/activate_fyers_execution_bundle_20261119.py

[Owning source](../scripts/activate_fyers_execution_bundle_20261119.py)

Apply the explicitly approved four-file FYERS bundle and guarded worker reload.

### Callables and explicit defaults

- `critical_snapshot(paths)`
- `main()`

### Literal payload and lookup fallbacks

- `message` → `''`

## scripts/activate_handoff_auto.py

[Owning source](../scripts/activate_handoff_auto.py)

Validate an owned Handoff policy; --activate-live enables already-authorized Auto.

### Callables and explicit defaults

- `main()`

## scripts/activate_manual_multi_20261030.py

[Owning source](../scripts/activate_manual_multi_20261030.py)

Explicitly approved dashboard activation; existing guards remain authoritative.

### Callables and explicit defaults

- `guard()`
- `snapshot()`

### Literal payload and lookup fallbacks

- `message` → `''`
- `rows` → `[]`

## scripts/activate_swing_breakout_fyers_20261103.py

[Owning source](../scripts/activate_swing_breakout_fyers_20261103.py)

Operator audit/activation for the explicitly approved FYERS Renko swing gate.

### Callables and explicit defaults

- `audit()`

### Literal payload and lookup fallbacks

- `netPositions` → `[]`
- `netQty` → `0`
- `orderBook` → `[]`
- `settings` → `{}`
- `status` → `0`
- `symbol` → `''`

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

## scripts/audit_chart_entry_labels_20261103.py

[Owning source](../scripts/audit_chart_entry_labels_20261103.py)

Read-only exact-account chart marker evidence; no strategy/order mutation.

## scripts/audit_dhan_chart_catalog.py

[Owning source](../scripts/audit_dhan_chart_catalog.py)

Read-only catalog membership audit against the current broker master.

### Literal payload and lookup fallbacks

- `SEM_EXPIRY_DATE` → `''`
- `SEM_SMST_SECURITY_ID` → `''`

## scripts/audit_fyers_chart_catalog.py

[Owning source](../scripts/audit_fyers_chart_catalog.py)

Read-only audit of an exact workspace's cached native chart catalog. No network.

### Callables and explicit defaults

- `main()`

## scripts/audit_fyers_crude_restart.py

[Owning source](../scripts/audit_fyers_crude_restart.py)

Read-only account-scoped restart preflight; never submits orders.

### Callables and explicit defaults

- `audit()`

### Literal payload and lookup fallbacks

- `netPositions` → `[]`
- `netQty` → `0`
- `orderBook` → `[]`

## scripts/audit_motilal_chart_catalog.py

[Owning source](../scripts/audit_motilal_chart_catalog.py)

Read-only native master and real chart-handler membership audit. No login renewal or orders.

### Callables and explicit defaults

- `save()`

### Literal payload and lookup fallbacks

- `MO_CLIENT_ID` → `''`

## scripts/audit_motilal_public_chart_master.py

[Owning source](../scripts/audit_motilal_public_chart_master.py)

Read-only public broker catalog audit; never updates account/order masters.

### Callables and explicit defaults

- `fetch(exchange)`

## scripts/audit_motilal_saved_catalog.py

[Owning source](../scripts/audit_motilal_saved_catalog.py)

Real chart-handler pagination against saved native catalogs; no broker traffic.

### Callables and explicit defaults

- `SavedMaster.rows(self, exchange, **kwargs)`
- `SavedMaster.indices(self, exchange)`
- `page(segment, offset)`
- `save()`

## scripts/audit_position_history_metadata.py

[Owning source](../scripts/audit_position_history_metadata.py)

Read-only exact-contract historical valuation evidence, no broker API calls.

### Literal payload and lookup fallbacks

- `order_history` → `[]`

## scripts/bind_runner_chart_source.py

[Owning source](../scripts/bind_runner_chart_source.py)

## scripts/build_chart_order_worker_candidates.py

[Owning source](../scripts/build_chart_order_worker_candidates.py)

Build unactivated, selective FYERS/Delta chart-order integration candidates.

### Callables and explicit defaults

- `sha(value)`
- `entry_changes(original, shared)`
- `once(text, old, new)`
- `integrate_web(text)`
- `integrate_guard(text)`
- `add_frontend(candidate, accounts, manifest)`
- `main()`

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

## scripts/compare_chart_candles.py

[Owning source](../scripts/compare_chart_candles.py)

Compare candle or ordered Renko OHLC exports from Sector Pulse and TradingView.

### Callables and explicit defaults

- `timestamp(value, zone, fractional=False)`
- `read_bars(path, zone, date, studies=(), renko=False)`
- `utc(time)`
- `compare(sector, tradingview, tolerance)`
- `compare_renko(sector, tradingview, tolerance)`
- `compare_studies(sector, tradingview, mappings, tolerance)`
- `main()`

## scripts/configure_server.py

[Owning source](../scripts/configure_server.py)

Provision Ubuntu/Debian or Oracle/RHEL HTTPS hosting without changing broker settings.

### Callables and explicit defaults

- `domain_name(value)`
- `run(*args, **kwargs)`
- `write_managed(path, content, mode=420, backups=BACKUPS)`
- `apache_config(domain, tls=True, debian=False)`
- `unit_quote(value)`
- `app_service(user, home, root)`
- `renewal_service(domain)`
- `port_open()`
- `native_login(user, domain)`
- `preserve_running_policy(user)`
- `allow_debian_web_ports()`
- `restore_labels(*paths)`
- `install_certbot()`
- `configure(args)`
- `main()`

### Literal payload and lookup fallbacks

- `ID` → `''`

## scripts/correct_combined_quality_label.py

[Owning source](../scripts/correct_combined_quality_label.py)

Correct this newly published digest in place; creates no additional message.

## scripts/diagnose_fyers_index_history.py

[Owning source](../scripts/diagnose_fyers_index_history.py)

Read-only FYERS history diagnostic for sector-index symbols.

### Callables and explicit defaults

- `client()`
- `main()`

## scripts/diagnose_handoff_evidence_20261030.py

[Owning source](../scripts/diagnose_handoff_evidence_20261030.py)

Read-only diagnosis of owned Handoff evidence transport; never submits.

## scripts/diagnose_handoff_evidence_detail_20261030.py

[Owning source](../scripts/diagnose_handoff_evidence_detail_20261030.py)

Read-only diagnosis of owned Handoff evidence transport; never submits.

## scripts/diagnose_renko_study_timeframes.py

[Owning source](../scripts/diagnose_renko_study_timeframes.py)

Read-only Renko timeframe diagnostic from previously captured Delta OHLC.

### Callables and explicit defaults

- `read_lower(path)`
- `main()`

## scripts/ema_band_historical_check.py

[Owning source](../scripts/ema_band_historical_check.py)

Read-only reconstruction of an EMA-band decision at an IST timestamp.

### Callables and explicit defaults

- `main()`

## scripts/finish_confirmed_feed.py

[Owning source](../scripts/finish_confirmed_feed.py)

### Callables and explicit defaults

- `edit(name, changes)`

## scripts/finish_confirmed_fyers_reload.py

[Owning source](../scripts/finish_confirmed_fyers_reload.py)

### Callables and explicit defaults

- `CalculationRepair.save(self)`
- `CalculationRepair.event(self, *args)`
- `NoTrading.stop(self)`

### Literal payload and lookup fallbacks

- `history_recoveries` → `[]`

## scripts/fix_confirmed_publication.py

[Owning source](../scripts/fix_confirmed_publication.py)

## scripts/fyers_day_net_snapshot.py

[Owning source](../scripts/fyers_day_net_snapshot.py)

Read-only, account-scoped FYERS day P&L and option-cost snapshot.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `symbol` → `''`

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

## scripts/fyers_read_day_positions.py

[Owning source](../scripts/fyers_read_day_positions.py)

Read-only current FYERS identity and day positions.

## scripts/generate_source_reference.py

[Owning source](../scripts/generate_source_reference.py)

Generate a secret-free module/settings map from source without imports or execution.

### Callables and explicit defaults

- `source_files()`
- `render()`

## scripts/implement_confirmed_feed.py

[Owning source](../scripts/implement_confirmed_feed.py)

### Callables and explicit defaults

- `edit(name, changes)`

## scripts/implement_qualified_chart_replay_20261103.py

[Owning source](../scripts/implement_qualified_chart_replay_20261103.py)

## scripts/install_confirmed_feed.py

[Owning source](../scripts/install_confirmed_feed.py)

Install the reviewed FYERS source candidate without restarting any process.

## scripts/live_source_snapshot.py

[Owning source](../scripts/live_source_snapshot.py)

Preserve source-only deployed variants without touching services or credentials.

### Callables and explicit defaults

- `digest(data)`
- `safe(path)`
- `source_file(path)`
- `baseline(revision, modes=None)`
- `verify(folder)`
- `capture(folder)`
- `restore(folder, workspace, destination)`

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

## scripts/optimize_confirmed_feed.py

[Owning source](../scripts/optimize_confirmed_feed.py)

### Callables and explicit defaults

- `edit(name, old, new)`

## scripts/package_release.py

[Owning source](../scripts/package_release.py)

Build and validate a source-only deployable from an exact Git commit.

### Callables and explicit defaults

- `build(ref='HEAD', output=None)`

## scripts/post_sector_summary.py

[Owning source](../scripts/post_sector_summary.py)

Post exactly one authorized latest sector card to the existing shared channel.

### Callables and explicit defaults

- `identity(snapshot)`
- `main()`

## scripts/preview_trade_advisory.py

[Owning source](../scripts/preview_trade_advisory.py)

Isolated UI fixture preview. GET-only server; no broker or OpenAI calls.

### Callables and explicit defaults

- `Handler.do_GET(self)`
- `Handler.log_message(self, *args)`

## scripts/probe_chart_reload_exposure.py

[Owning source](../scripts/probe_chart_reload_exposure.py)

Read-only exposure gate for a selected FYERS/Delta dashboard reload.

### Callables and explicit defaults

- `number(value)`
- `inspect(workspace)`
- `main()`

## scripts/probe_delta_chart_channels.py

[Owning source](../scripts/probe_delta_chart_channels.py)

Isolated public WebSocket ingestion sample; no credentials, runners or orders.

### Literal payload and lookup fallbacks

- `ts` → `0`
- `type` → `''`

## scripts/probe_delta_chart_order_schema.py

[Owning source](../scripts/probe_delta_chart_order_schema.py)

Read-only selected-workspace Delta schema probe; never submits or alters orders.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `created_at` → `''`

## scripts/probe_dhan_nse_commodity_data.py

[Owning source](../scripts/probe_dhan_nse_commodity_data.py)

Bounded read-only profile/master/history probe; never constructs an order.

### Callables and explicit defaults

- `save()`

### Literal payload and lookup fallbacks

- `DHAN_CLIENT_ID` → `''`
- `SEM_EXPIRY_DATE` → `''`
- `SEM_INSTRUMENT_NAME` → `''`
- `SEM_TRADING_SYMBOL` → `''`
- `candles` → `0`
- `errorMessage` → `''`
- `timestamp` → `[]`

## scripts/probe_fyers_chart_calendar_history.py

[Owning source](../scripts/probe_fyers_chart_calendar_history.py)

Selected-worker FYERS calendar history validation; no order endpoints.

### Callables and explicit defaults

- `main()`

## scripts/probe_fyers_chart_history_schema.py

[Owning source](../scripts/probe_fyers_chart_history_schema.py)

Read-only schema probe for one saved FYERS workspace. Never places orders.

### Callables and explicit defaults

- `main()`

## scripts/probe_fyers_custom_hour_volume.py

[Owning source](../scripts/probe_fyers_custom_hour_volume.py)

Read-only, exact-owner FYERS 30m query-window volume audit; no order paths.

## scripts/probe_fyers_one_minute_availability.py

[Owning source](../scripts/probe_fyers_one_minute_availability.py)

Read-only availability probe for FYERS NIFTY one-minute history.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## scripts/probe_rsi_table_history.py

[Owning source](../scripts/probe_rsi_table_history.py)

Read-only provider resolution diagnosis; sanitized metadata only.

### Literal payload and lookup fallbacks

- `candles` → `[]`

## scripts/profile_recorded_price_renko.py

[Owning source](../scripts/profile_recorded_price_renko.py)

Profile a recorded price-Renko producer in an isolated output folder.

### Callables and explicit defaults

- `main()`

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

## scripts/reconcile_confirmed_crude.py

[Owning source](../scripts/reconcile_confirmed_crude.py)

Offline reconciliation of proven historical fill; deliberately has no order API.

### Callables and explicit defaults

- `ReadOnlyEvidence.__init__(self, client, evidence)`
- `ReadOnlyEvidence.positions(self)`
- `ReadOnlyEvidence.orders(self)`
- `ReadOnlyEvidence.stop(self)`
- `RepairRunner.save(self)`
- `RepairRunner.snapshot(self)`
- `prepare(state_path, evidence_path, client)`

## scripts/reconcile_crude_restart_fyers.py

[Owning source](../scripts/reconcile_crude_restart_fyers.py)

Authorized offline historical-fill reconciliation and account-only reload.

### Callables and explicit defaults

- `main()`

## scripts/reconcile_delta_no_send.py

[Owning source](../scripts/reconcile_delta_no_send.py)

Operator-approved orphan reconciliation. Broker access is GET-only.

### Callables and explicit defaults

- `read_only(method, *pos, **kw)`

## scripts/reconcile_handoff_pre_submit.py

[Owning source](../scripts/reconcile_handoff_pre_submit.py)

Resolve only a receipt proven to have stopped before the durable submit intent.

### Callables and explicit defaults

- `main()`

## scripts/recover_delta_stopped_orphan.py

[Owning source](../scripts/recover_delta_stopped_orphan.py)

Approved one-time recovery of this exact stopped orphan; no broker mutations.

## scripts/refresh_official_weights.py

[Owning source](../scripts/refresh_official_weights.py)

Validate and atomically install a reviewed monthly NSE weight dataset.

### Callables and explicit defaults

- `install_candidate(candidate_path, destination=DATA_DIRECTORY, check_only=False)`
- `main()`

## scripts/reload_dhan_native_route_20261030.py

[Owning source](../scripts/reload_dhan_native_route_20261030.py)

### Literal payload and lookup fallbacks

- `message` → `'Guarded bounce failed'`

## scripts/reload_fyers_parser_cash_20261030.py

[Owning source](../scripts/reload_fyers_parser_cash_20261030.py)

### Literal payload and lookup fallbacks

- `message` → `'Guarded bounce failed'`

## scripts/reload_native_parser_routes_20261030.py

[Owning source](../scripts/reload_native_parser_routes_20261030.py)

### Literal payload and lookup fallbacks

- `message` → `'Guarded bounce failed'`

## scripts/reload_parser_verified_20261030.py

[Owning source](../scripts/reload_parser_verified_20261030.py)

### Literal payload and lookup fallbacks

- `message` → `'Guarded bounce failed'`

## scripts/render_sector_notification_draft.py

[Owning source](../scripts/render_sector_notification_draft.py)

Draft visual only. Values are illustrative; no market fetch or message delivery.

### Callables and explicit defaults

- `font(size, bold=False)`
- `text(x, y, s, size=28, color='#203B55', bold=False)`
- `box(rect, fill, r=22, outline=None)`
- `right(x, y, s, size=28, color='#203B55', bold=False)`

## scripts/render_user_functional_guide.py

[Owning source](../scripts/render_user_functional_guide.py)

Build user-facing HTML and contextual-help data from one maintained help catalog.

### Callables and explicit defaults

- `render()`

### Literal payload and lookup fallbacks

- `options` → `[]`

## scripts/restart_handoff_verified_20261030.py

[Owning source](../scripts/restart_handoff_verified_20261030.py)

Approved Handoff coordinator restart with policy and order-state preservation.

## scripts/restore_telegram_subscriber.py

[Owning source](../scripts/restore_telegram_subscriber.py)

Restore a verified legacy reader into exactly one owner's Delta workspace; never starts.

### Callables and explicit defaults

- `main()`

## scripts/run_price_publication_candidate.py

[Owning source](../scripts/run_price_publication_candidate.py)

Load staged publication modules in this isolated test process only.

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

## scripts/setup_trade_notifications.py

[Owning source](../scripts/setup_trade_notifications.py)

Owner-run secure prerequisite collection; never starts services or trading.

### Callables and explicit defaults

- `prompt(label, default)`
- `telegram(token, method)`
- `owner_accounts()`
- `private_destination(updates, challenge=None)`
- `wait_private_destination(token)`
- `save_private(path, value)`
- `main()`

### Literal payload and lookup fallbacks

- `first_name` → `'Private chat'`
- `text` → `''`
- `username` → `''`

## scripts/stage_confirmed_feed.py

[Owning source](../scripts/stage_confirmed_feed.py)

### Callables and explicit defaults

- `change(name, old, new)`

## scripts/stage_forming_reference_fix.py

[Owning source](../scripts/stage_forming_reference_fix.py)

Stage a guarded forming-reference patch and rebase pending frontend candidates.

### Callables and explicit defaults

- `transform(text)`

## scripts/stage_motilal_fyers_history.py

[Owning source](../scripts/stage_motilal_fyers_history.py)

Stage read-only FYERS candles for an exact Motilal underlying, without activation.

### Callables and explicit defaults

- `main()`

## scripts/stage_nifty50_two_years_fyers.py

[Owning source](../scripts/stage_nifty50_two_years_fyers.py)

Resumable, data-only FYERS archive; never calls order or runner APIs.

### Callables and explicit defaults

- `save(p, d)`
- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## scripts/stage_nse_contract_master.py

[Owning source](../scripts/stage_nse_contract_master.py)

Archive primary NSE daily contract evidence for historical research only.

### Callables and explicit defaults

- `main()`

## scripts/stage_pine_apply_recovery.py

[Owning source](../scripts/stage_pine_apply_recovery.py)

## scripts/stage_pine_auto_recovery.py

[Owning source](../scripts/stage_pine_auto_recovery.py)

Stage bounded, scope-safe Pine reference recovery on fresh owner snapshots.

### Callables and explicit defaults

- `change(text)`

## scripts/stage_price_execution_timing.py

[Owning source](../scripts/stage_price_execution_timing.py)

Add diagnostic timings to the already-staged price-publication candidates.

## scripts/stage_renko_signal_label_control.py

[Owning source](../scripts/stage_renko_signal_label_control.py)

Stage a display-only simulated-signal control across existing owner variants.

## scripts/stage_twap_study.py

[Owning source](../scripts/stage_twap_study.py)

### Callables and explicit defaults

- `replace(s, a, b)`

## scripts/suggest_high_conviction_spreads.py

[Owning source](../scripts/suggest_high_conviction_spreads.py)

Read-only FYERS defined-risk spread proposals for current bullish candidates.

### Callables and explicit defaults

- `requested_candidates(argv)`
- `main()`

### Literal payload and lookup fallbacks

- `data` → `{}`
- `optionsChain` → `[]`

## scripts/verify_adr_study.py

[Owning source](../scripts/verify_adr_study.py)

Independent Decimal50 native-range averages for standard ADR.

## scripts/verify_chart_advanced_oscillators.py

[Owning source](../scripts/verify_chart_advanced_oscillators.py)

Independent Decimal50 checks; external TradingView seeding is a separate gate.

### Callables and explicit defaults

- `mean(v, n, weights=False)`
- `roc(v, n)`
- `reference(b, c)`

### Literal payload and lookup fallbacks

- `longRocLength` → `14`
- `provisional` → `'0'`
- `shortRocLength` → `11`
- `signalLength` → `9`
- `wmaLength` → `10`

## scripts/verify_chart_comparison_studies.py

[Owning source](../scripts/verify_chart_comparison_studies.py)

Independent two-symbol arithmetic and missing-reference checks.

### Callables and explicit defaults

- `price(row, field)`
- `main()`

## scripts/verify_chart_core_indicators.py

[Owning source](../scripts/verify_chart_core_indicators.py)

Compare current chart studies with independent Decimal calculations on an exported OHLC CSV.

### Callables and explicit defaults

- `average(values, length)`
- `exponential(values, length)`
- `wilder(values, length)`
- `main()`

## scripts/verify_chart_directional_channels.py

[Owning source](../scripts/verify_chart_directional_channels.py)

Independent Decimal50 DMI/ADX, Keltner and Donchian formulas.

### Callables and explicit defaults

- `bar(h, l, c=Decimal(100))`
- `sma(v, n)`
- `ema(v, n)`
- `rma(v, n)`
- `ranges(b)`
- `rounded(v)`
- `dmi(b, n, smoothing)`
- `reference(b, spec)`

### Literal payload and lookup fallbacks

- `provisional` → `'0'`

## scripts/verify_chart_momentum_indicators.py

[Owning source](../scripts/verify_chart_momentum_indicators.py)

Independent Decimal50 momentum formulas on completed broker candles.

### Callables and explicit defaults

- `smooth(v, n)`
- `reference(b, n)`
- `main()`

### Literal payload and lookup fallbacks

- `provisional` → `''`

## scripts/verify_chart_pine_revision.py

[Owning source](../scripts/verify_chart_pine_revision.py)

Read-only release check for the private canonical V1 and picker revision badges.

### Callables and explicit defaults

- `digest(path)`
- `main()`

## scripts/verify_chart_reference_levels.py

[Owning source](../scripts/verify_chart_reference_levels.py)

Independent Decimal checks of six pivot methods and 52-week source selection.

### Callables and explicit defaults

- `pivot(method, b, opening)`
- `source(b, key)`
- `main()`

## scripts/verify_chart_trend_indicators.py

[Owning source](../scripts/verify_chart_trend_indicators.py)

Independent Decimal50 Supertrend and displaced Ichimoku checks on broker-exported candles.

### Literal payload and lookup fallbacks

- `provisional` → `'0'`

## scripts/verify_chart_trix_reference.py

[Owning source](../scripts/verify_chart_trix_reference.py)

Independent Decimal50 native log-change TRIX reference on positive prices.

### Literal payload and lookup fallbacks

- `provisional` → `'0'`

## scripts/verify_chart_volume_indicators.py

[Owning source](../scripts/verify_chart_volume_indicators.py)

Independent Decimal50 volume-indicator calculations on completed broker candles.

### Callables and explicit defaults

- `ema(v, n)`
- `reference(rows, n)`
- `main()`

### Literal payload and lookup fallbacks

- `provisional` → `''`

## scripts/verify_confirmed_feed_baseline.py

[Owning source](../scripts/verify_confirmed_feed_baseline.py)

Reproduce broad-suite pre-existing failures using the saved pre-change runner.

## scripts/verify_dhan_calendar_parity.py

[Owning source](../scripts/verify_dhan_calendar_parity.py)

Compare adapter calendar OHLC against independently grouped broker daily rows.

### Callables and explicit defaults

- `Capture.__init__(self)`
- `Capture.request(self, method, path, payload)`

## scripts/verify_execution_provisioning.py

[Owning source](../scripts/verify_execution_provisioning.py)

Exercise public provisioning in an isolated directory; never opens an account.

## scripts/verify_fyers_custom_hour_exports.py

[Owning source](../scripts/verify_fyers_custom_hour_exports.py)

Compare exported custom-hour bars with separate completed 30m chart exports.

### Callables and explicit defaults

- `read(f)`
- `dt(r)`

### Literal payload and lookup fallbacks

- `provisional` → `'0'`

## scripts/verify_fyers_execution_bundle.py

[Owning source](../scripts/verify_fyers_execution_bundle.py)

Offline combined FYERS candidate checks; no live broker or credential access.

## scripts/verify_fyers_shared_master_memory.py

[Owning source](../scripts/verify_fyers_shared_master_memory.py)

Tiny offline cache fixtures. Never loads actual broker masters or credentials.

### Callables and explicit defaults

- `MasterCacheTests.setUp(self)`
- `MasterCacheTests.broker(self, folder=None)`
- `MasterCacheTests.write(self, folder=None, name='NSE_FO', value='A')`
- `MasterCacheTests.test_multiple_adapters_share_one_immutable_parse(self)`
- `MasterCacheTests.test_atomic_file_replacement_invalidates_current_version(self)`
- `MasterCacheTests.test_stale_missing_or_changed_masters_never_use_old_cached_rows(self)`
- `MasterCacheTests.test_different_owner_paths_cannot_alias_same_segment(self)`
- `MasterCacheTests.test_bounded_cache_evicts_paths_without_mutating_existing_readers(self)`
- `MasterCacheTests.test_replacement_during_parse_fails_closed_and_does_not_cache_mixed_rows(self)`
- `MasterCacheTests.test_parallel_adapters_parse_only_once(self)`

## scripts/verify_handoff_analysis.py

[Owning source](../scripts/verify_handoff_analysis.py)

Read-only native Dhan/Motilal Handoff integration verification; no reports or orders.

### Callables and explicit defaults

- `main()`

### Literal payload and lookup fallbacks

- `cards` → `[]`
- `exclusions` → `[]`
- `scope` → `{}`
- `source` → `{}`

## scripts/verify_handoff_automation.py

[Owning source](../scripts/verify_handoff_automation.py)

Read-only account verification. Never starts a runner or submits an order.

### Callables and explicit defaults

- `main()`

## scripts/verify_heikin_study_export.py

[Owning source](../scripts/verify_heikin_study_export.py)

Independent Decimal50 HA, Open-SMA5 and ATR14 audit of hosted study exports.

### Callables and explicit defaults

- `transform(rows)`
- `plots(rows)`
- `audit(history_path, export_path, frames_path=None)`

### Literal payload and lookup fallbacks

- `rows` → `[]`

## scripts/verify_hosted_renko_close_export.py

[Owning source](../scripts/verify_hosted_renko_close_export.py)

Independent Decimal reference for fixed-size, close-driven, two-brick-reversal Renko.

### Callables and explicit defaults

- `read(path)`

## scripts/verify_manual_multi_activation_20261030.py

[Owning source](../scripts/verify_manual_multi_activation_20261030.py)

### Literal payload and lookup fallbacks

- `message` → `'Guarded bounce failed'`

## scripts/verify_motilal_atm_analysis.py

[Owning source](../scripts/verify_motilal_atm_analysis.py)

Read-only native ATM analysis; no ticket, runner start or broker order.

### Callables and explicit defaults

- `main()`

## scripts/verify_motilal_order_routes.py

[Owning source](../scripts/verify_motilal_order_routes.py)

Read-only native ATM resolution and preflight. Never submits an order.

### Callables and explicit defaults

- `main()`

## scripts/verify_motilal_segments.py

[Owning source](../scripts/verify_motilal_segments.py)

Read-only exchange coverage audit; history staging never authorizes trading.

### Callables and explicit defaults

- `main()`

## scripts/verify_native_renko_timeframe_exports.py

[Owning source](../scripts/verify_native_renko_timeframe_exports.py)

Audit captured native TradingView Renko CSVs against the current-library diagnostic.

### Callables and explicit defaults

- `main()`

## scripts/verify_pine_request_guards.py

[Owning source](../scripts/verify_pine_request_guards.py)

Exercise real Pine worker request guards without network or production changes.

## scripts/verify_price_execution_timing.py

[Owning source](../scripts/verify_price_execution_timing.py)

Check bounded timing diagnostics without brokers or execution mutations.

### Callables and explicit defaults

- `TimingTests.setUp(self)`
- `TimingTests.test_queue_measurement_uses_monotonic_publication_and_preserves_event(self)`
- `TimingTests.test_identity_distinguishes_same_timestamp_bricks_and_generation(self)`
- `TimingTests.test_cache_and_durable_timings_are_bounded(self)`
- `TimingTests.test_a_new_run_cannot_inherit_prior_queue_timing(self)`
- `TimingTests.test_missing_or_future_receipt_does_not_report_false_positive_age(self)`

## scripts/verify_price_publication_candidate.py

[Owning source](../scripts/verify_price_publication_candidate.py)

Regression checks for staged incremental immutable price-row publication.

### Callables and explicit defaults

- `PublicationTests.setUp(self)`
- `PublicationTests.publish(self, engine=None)`
- `PublicationTests.test_exact_legacy_publication_values(self)`
- `PublicationTests.test_reuses_only_unchanged_row_objects(self)`
- `PublicationTests.test_reader_mutation_is_isolated(self)`
- `PublicationTests.test_run_change_discards_row_cache(self)`
- `PublicationTests.test_mutable_default_does_not_use_row_cache(self)`
- `PublicationTests.test_offline_continuation_keeps_exact_durable_history(self)`

## scripts/verify_price_publication_compatibility.py

[Owning source](../scripts/verify_price_publication_compatibility.py)

Offline publisher interface compatibility checks; no broker access.

### Callables and explicit defaults

- `CompatibilityTests.test_cached_legacy_signature(self)`
- `CompatibilityTests.test_new_signature_uses_immutable(self)`
- `CompatibilityTests.test_internal_type_error_not_replayed(self)`
- `CompatibilityTests.test_variadic_publisher(self)`

## scripts/verify_pring_special_k.py

[Owning source](../scripts/verify_pring_special_k.py)

Independent Decimal audit of Pring Special K's documented12 cycles.

### Callables and explicit defaults

- `mean_finite(values, n)`
- `price(bar, source)`
- `reference(case)`

## scripts/verify_redbar_zones.py

[Owning source](../scripts/verify_redbar_zones.py)

Independent Python reference for the checked-in Red Bar Pine zone algorithm.

### Callables and explicit defaults

- `reference(candles, symbol, tick)`

## scripts/verify_twap_study.py

[Owning source](../scripts/verify_twap_study.py)

Independent Decimal50 anchored source averages, calendar boundaries and absent anchors.

## scripts/verify_volume_index_timeframe_export.py

[Owning source](../scripts/verify_volume_index_timeframe_export.py)

Audit NVI/PVI higher-timeframe chart exports against captured broker OHLCV.

### Callables and explicit defaults

- `audit(history_path, export_path)`

## scripts/verify_volume_indices.py

[Owning source](../scripts/verify_volume_indices.py)

Independent Decimal reference for the staged NVI/PVI and EMA plots.

## scripts/verify_woodies_cci.py

[Owning source](../scripts/verify_woodies_cci.py)

Independent Decimal50 CCI values and documented Woodies histogram regimes.

### Callables and explicit defaults

- `prices(bars)`
- `cci(data, n)`
- `colors(values, inputs)`

## scripts/wire_confirmed_feed_health.py

[Owning source](../scripts/wire_confirmed_feed_health.py)

### Callables and explicit defaults

- `edit(name, old, new)`

## sector_heatmap/__init__.py

[Owning source](../sector_heatmap/__init__.py)

Local Fyers-powered NSE sector heat-map application.

## sector_heatmap/account_parser.py

[Owning source](../sector_heatmap/account_parser.py)

Private broker-native recommendation mapping, quotes and reviewed tickets.

### Callables and explicit defaults

- `normalized(v)`
- `expiry_matches(expiry, hint)`
- `AccountParser.__init__(self, account, execution)`
- `AccountParser.contracts(self, parsed)`
- `AccountParser.parse(self, payload)`
- `AccountParser.exact(self, payload)`
- `AccountParser.quote(self, payload)`
- `AccountParser.analysis(self, payload)`
- `AccountParser.prepare(self, payload, csrf)`
- `AccountParser.submit(self, payload, csrf)`

### Literal payload and lookup fallbacks

- `SEM_EXPIRY_DATE` → `''`
- `SEM_INSTRUMENT_NAME` → `''`
- `daily_loss_limit` → `5000`
- `idea_risk_limit` → `2000`
- `instrument` → `''`
- `lots` → `1`
- `mode` → `'LIVE'`
- `quote_currency` → `'USD'`
- `risk_reserve` → `1000`

## sector_heatmap/advisory_jobs.py

[Owning source](../sector_heatmap/advisory_jobs.py)

In-memory bounded read-only work queue; never wraps order operations.

### Callables and explicit defaults

- `AdvisoryJobs.__init__(self, capacity=4, ttl=600)`
- `AdvisoryJobs.request(self, payload, calculate)`

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
- `coverage` → `{}`
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

## sector_heatmap/broker_diagnostics.py

[Owning source](../sector_heatmap/broker_diagnostics.py)

Process-local, administrator-controlled broker diagnostics; never records arguments.

### Callables and explicit defaults

- `source_location(depth=1)`
- `utc(ms)`
- `require_admin(user)`
- `BrokerDiagnostics.__init__(self)`
- `BrokerDiagnostics.active(self, broker)`
- `BrokerDiagnostics.configure(self, broker, enabled, minutes=15)`
- `BrokerDiagnostics.begin(self, broker, operation, source=None, request_id=None)`
- `BrokerDiagnostics.end(self, event, outcome='ok')`
- `BrokerDiagnostics.span(self, broker, operation, source=None, request_id=None)`
- `BrokerDiagnostics.call(self, broker, operation, function, *args, **kwargs)`
- `BrokerDiagnostics.mark(self, broker, operation, source=None)`
- `BrokerDiagnostics.report(self, broker)`
- `broker_for_host(host)`
- `install_http_timing()`

## sector_heatmap/chart_catalog.py

[Owning source](../sector_heatmap/chart_catalog.py)

Read-only chart catalogs under the chart section's permission boundary.

### Callables and explicit defaults

- `serve_delta_chart_catalog(handler, workspace_guard, delta)`

## sector_heatmap/chart_feed_recovery.py

[Owning source](../sector_heatmap/chart_feed_recovery.py)

Bounded recovery for read-only chart sockets; never changes runner state.

### Callables and explicit defaults

- `safe_stream_error(message)`
- `ChartFeedRecoveryMixin.__init__(self, *args, **kwargs)`
- `ChartFeedRecoveryMixin._chart_token_hash(self)`
- `ChartFeedRecoveryMixin.start(self)`
- `ChartFeedRecoveryMixin._recover_chart(self, symbol, now)`
- `ChartFeedRecoveryMixin.tick(self, symbol)`
- `ChartFeedRecoveryMixin.subscribe_all(self)`
- `ChartFeedRecoveryMixin.stream_status(self)`

## sector_heatmap/chart_trade_admission.py

[Owning source](../sector_heatmap/chart_trade_admission.py)

Cross-process entry admission and durable account entry revision.

### Callables and explicit defaults

- `_after_fork_child()`
- `_before_fork()`
- `_after_fork_parent()`
- `_path(broker, folder=None)`
- `entry_lock(broker, *, blocking=True, folder=None)`
- `_revision(fd)`
- `entry_revision(broker, *, folder=None)`
- `mark_entry_attempt(broker, *, folder=None)`
- `serialized_fyers_entry(method)`
- `serialized_chart_entry(method)`
- `serialized_runner_entry(method)`
- `serialized_delta_request(native_method)`
- `place_fyers_entry(sender, payload)`
- `serialized_fyers_strategy_entry(method)`
- `assert_dhan_chart_entry_allowed(service, *, client_order_id=None)`
- `mark_dhan_entry_attempt(service, *, client_order_id=None)`
- `serialized_dhan_entry(method)`
- `serialized_dhan_strategy_entry(method)`

### Literal payload and lookup fallbacks

- `DRY_RUN` → `True`

## sector_heatmap/chart_trade_delta.py

[Owning source](../sector_heatmap/chart_trade_delta.py)

Delta chart entries with broker-attached exits; staged, not HTTP-activated.

### Callables and explicit defaults

- `DeltaChartAdapter.__init__(self, account, execution, *, clock=time.time)`
- `DeltaChartAdapter.live_enabled(self)`
- `DeltaChartAdapter._flat_lifecycle(self, product_id)`
- `DeltaChartAdapter._contract(self, symbol)`
- `DeltaChartAdapter._quote(self, symbol)`
- `DeltaChartAdapter._wallet(self, product)`
- `DeltaChartAdapter.prepare(self, payload)`
- `DeltaChartAdapter.refresh(self, plan)`
- `DeltaChartAdapter.submit_bracket(self, plan, *, idempotency_key)`
- `DeltaChartAdapter.reconcile(self, plan, *, preview_id, entry_order_id=None)`
- `DeltaChartAdapter._timestamp(value)`
- `DeltaChartAdapter._pages(self, path, params)`
- `DeltaChartAdapter._exit_snapshot(self, plan, parent)`

### Literal payload and lookup fallbacks

- `timestamp` → `0`

## sector_heatmap/chart_trade_delta_exits.py

[Owning source](../sector_heatmap/chart_trade_delta_exits.py)

Reconcile a Delta chart position against complete native fills and bracket records.

### Callables and explicit defaults

- `number(value)`
- `verify_delta_exits(plan, parent, orders, fills, position)`

## sector_heatmap/chart_trade_dhan.py

[Owning source](../sector_heatmap/chart_trade_dhan.py)

Staged Dhan chart adapter. Not registered for hosted live submission.

### Callables and explicit defaults

- `DhanChartAdapter.__init__(self, account, execution, *, clock=time.time, session_validator=None, submission_enabled=False, tick_reader=None, activation_check=None)`
- `DhanChartAdapter.live_enabled(self)`
- `DhanChartAdapter._journals(self)`
- `DhanChartAdapter._contract(self, symbol)`
- `DhanChartAdapter._exposure(self, client, contract)`
- `DhanChartAdapter._plan(self, client, payload, account, contract, *, triggered=False)`
- `DhanChartAdapter.prepare(self, payload)`
- `DhanChartAdapter._prepare(self, payload, *, triggered=False, own_token=None)`
- `DhanChartAdapter.warm_live_feed(self, plan)`
- `DhanChartAdapter.refresh(self, plan)`
- `DhanChartAdapter._durable_intent(self, plan, preview_id)`
- `DhanChartAdapter._trigger_context(self, plan, preview_id, intent)`
- `DhanChartAdapter.refresh_triggered(self, plan, *, preview_id)`
- `DhanChartAdapter.submit_bracket(self, plan, *, idempotency_key)`
- `DhanChartAdapter.reconcile(self, plan, *, preview_id, entry_order_id=None)`

### Literal payload and lookup fallbacks

- `SEM_EXPIRY_DATE` → `''`
- `expires_at` → `0`
- `filled_quantity` → `0`
- `quantity_multiplier` → `1`

## sector_heatmap/chart_trade_dhan_conditions.py

[Owning source](../sector_heatmap/chart_trade_dhan_conditions.py)

Durable conditional-entry state in the private chart preview database.

### Callables and explicit defaults

- `DhanChartConditions.__init__(self, path, *, clock=time.time)`
- `DhanChartConditions.connection(self)`
- `DhanChartConditions._row(self, db, owner, preview_id)`
- `DhanChartConditions.inspect(self, owner, preview_id)`
- `DhanChartConditions._result(preview_id, plan, state)`
- `DhanChartConditions.arm(self, owner, preview_id, confirmation, *, tick, expires_at, mode, enabled=False)`
- `DhanChartConditions.observe(self, owner, preview_id, tick)`
- `DhanChartConditions.claim(self, owner, preview_id, *, tick)`
- `DhanChartConditions.cancel_unclaimed(self, owner, preview_id)`
- `DhanChartConditions.pending(self, account_id)`
- `DhanChartConditions.require_review(self, owner, preview_id, reason)`
- `DhanChartConditions.outcome(self, owner, preview_id, claim_token, result)`

## sector_heatmap/chart_trade_dhan_controller.py

[Owning source](../sector_heatmap/chart_trade_dhan_controller.py)

Conditional chart controller, installed only by an explicit service factory.

### Callables and explicit defaults

- `DhanConditionalController.__init__(self, service, *, tick_reader, expiry_resolver, enabled, worker_factory=DhanConditionalWorker)`
- `DhanConditionalController.arm(self, owner, payload, adapter)`
- `DhanConditionalController.cancel(self, owner, preview_id)`
- `DhanConditionalController.recover_waiting(self)`
- `DhanConditionalController.close(self)`

## sector_heatmap/chart_trade_dhan_evidence.py

[Owning source](../sector_heatmap/chart_trade_dhan_evidence.py)

Strict read-only account evidence for the staged Dhan chart adapter.

### Callables and explicit defaults

- `account_identity(account, client_id, profile, ips, egress, *, segment, product)`
- `no_contract_exposure(client_id, segment, security_id, positions, orders)`
- `margin_coverage(client_id, funds, margin, *, minimum_required=0)`

## sector_heatmap/chart_trade_dhan_exits.py

[Owning source](../sector_heatmap/chart_trade_dhan_exits.py)

Pure Dhan chart exit-fill proof from complete native day snapshots.

### Callables and explicit defaults

- `reconcile_dhan_exits(plan, contract, parent, *, client_id, preview_id, orders, trades, positions)`

## sector_heatmap/chart_trade_dhan_reconciliation.py

[Owning source](../sector_heatmap/chart_trade_dhan_reconciliation.py)

Read-only Dhan Super entry/registration evidence for chart-owned levels.

### Callables and explicit defaults

- `reconcile_dhan_super(plan, contract, *, preview_id, broker_client_id, rows, entry_order_id=None)`

## sector_heatmap/chart_trade_dhan_sessions.py

[Owning source](../sector_heatmap/chart_trade_dhan_sessions.py)

Contract-aware Dhan entry session gate; independent of chart history access.

### Callables and explicit defaults

- `validate_session(contract, now)`
- `conditional_expiry(plan, preflight, now)`

## sector_heatmap/chart_trade_dhan_trigger.py

[Owning source](../sector_heatmap/chart_trade_dhan_trigger.py)

Pure, serializable Dhan stop-limit trigger state; never submits an order.

### Callables and explicit defaults

- `DhanTriggerState.terms(self)`
- `wire_tick_price(value, tick)`
- `_tick(plan, tick, now)`
- `arm_trigger(plan, tick, *, now, expires_at)`
- `evaluate_trigger(state, plan, tick, *, now)`

## sector_heatmap/chart_trade_dhan_worker.py

[Owning source](../sector_heatmap/chart_trade_dhan_worker.py)

Explicitly started Dhan conditional worker; no automatic restart submissions.

### Callables and explicit defaults

- `DhanConditionalWorker.__init__(self, account, conditions, *, adapter_factory, tick_reader, enabled)`
- `DhanConditionalWorker.run_once(self)`
- `DhanConditionalWorker._run(self)`
- `DhanConditionalWorker.start(self)`
- `DhanConditionalWorker.close(self)`

## sector_heatmap/chart_trade_fyers.py

[Owning source](../sector_heatmap/chart_trade_fyers.py)

FYERS chart-order adapter using fresh native reads and sync TPSL submission.

### Callables and explicit defaults

- `FyersChartAdapter.__init__(self, account, execution, *, client_factory=None, quote_reader=None, margin_reader=None, history_reader=None, clock=time.time)`
- `FyersChartAdapter.live_enabled(self)`
- `FyersChartAdapter._client(self)`
- `FyersChartAdapter._rows(response, key)`
- `FyersChartAdapter._contract(self, symbol)`
- `FyersChartAdapter._margin(self, client, body)`
- `FyersChartAdapter.prepare(self, payload)`
- `FyersChartAdapter.refresh(self, plan)`
- `FyersChartAdapter.submit_bracket(self, plan, *, idempotency_key)`
- `FyersChartAdapter.reconcile(self, plan, *, preview_id, entry_order_id=None)`
- `FyersChartAdapter._history(self, name, params)`
- `FyersChartAdapter.reconcile_record(self, plan, *, record)`
- `FyersChartAdapter._read_reconciliation_snapshot(self)`
- `FyersChartAdapter.begin_reconciliation_batch(self)`

### Literal payload and lookup fallbacks

- `lot_size` → `1`

## sector_heatmap/chart_trade_fyers_history.py

[Owning source](../sector_heatmap/chart_trade_fyers_history.py)

Read-only FYERS report evidence; historical rows never establish exit linkage.

### Callables and explicit defaults

- `read_reports(reader, *, symbol, identity_hash, started_at, now, page_size=100, max_pages=20)`
- `reconcile_archived_entry(plan, reports, entry_order_id)`

### Literal payload and lookup fallbacks

- `orderNumber` → `''`

## sector_heatmap/chart_trade_monitor.py

[Owning source](../sector_heatmap/chart_trade_monitor.py)

Account-owned background broker reads; never places, modifies or cancels orders.

### Callables and explicit defaults

- `ChartTradeMonitor.__init__(self, service, *, clock=time.monotonic)`
- `ChartTradeMonitor.run_once(self)`
- `ChartTradeMonitor._run(self)`
- `ChartTradeMonitor.start(self)`
- `ChartTradeMonitor.close(self)`

## sector_heatmap/chart_trade_native.py

[Owning source](../sector_heatmap/chart_trade_native.py)

Broker-native payloads for reviewed chart levels; no network requests.

### Callables and explicit defaults

- `_number(value)`
- `native_bracket_order(plan, contract, *, client_order_id, broker_client_id=None)`
- `dhan_super_margin_payload(plan, contract, *, broker_client_id)`
- `dhan_triggered_bracket_order(plan, contract, *, client_order_id, broker_client_id, claim, tick, now)`

### Literal payload and lookup fallbacks

- `sequence` → `0`

## sector_heatmap/chart_trade_ownership.py

[Owning source](../sector_heatmap/chart_trade_ownership.py)

Read-only admission guard for durable chart-order ownership.

### Callables and explicit defaults

- `assert_no_chart_entry_conflict(path, account_id, broker, *, client_order_id=None)`
- `assert_workspace_chart_entry_allowed(broker, *, client_order_id=None)`

## sector_heatmap/chart_trade_plan.py

[Owning source](../sector_heatmap/chart_trade_plan.py)

Exact chart level plans. Pure validation; this module cannot submit orders.

### Callables and explicit defaults

- `positive(value, name)`
- `exact_price(value, tick, name)`
- `ChartTradePlan.terms(self)`
- `ChartTradePlan.fingerprint(self)`
- `build_plan(payload, *, account, contract, quote, now, triggered_dhan_entry=False)`
- `confirm_plan(reviewed, refreshed, confirmation, *, expires_at, now)`

### Literal payload and lookup fallbacks

- `exit_trigger_method` → `'last_traded_price'`
- `products` → `[]`

## sector_heatmap/chart_trade_previews.py

[Owning source](../sector_heatmap/chart_trade_previews.py)

Durable, account-bound confirmation of chart order previews.

### Callables and explicit defaults

- `ChartTradePreviews.__init__(self, path, *, clock=time.time)`
- `ChartTradePreviews.connection(self)`
- `ChartTradePreviews.prepare(self, owner, plan)`
- `ChartTradePreviews.inspect(self, owner, preview_id)`
- `ChartTradePreviews.arm(self, owner, preview_id, confirmation, *, mode, adapter, enabled=False)`
- `ChartTradePreviews._unclaimed_condition(self, owner, preview_id)`
- `ChartTradePreviews.reconcile(self, owner, preview_id, adapter)`
- `ChartTradePreviews.pending(self, account_id, broker)`
- `ChartTradePreviews.record_read_failure(self, owner, preview_id)`

## sector_heatmap/chart_trade_reconciliation.py

[Owning source](../sector_heatmap/chart_trade_reconciliation.py)

Read-only FYERS order-book reconciliation for one owned chart order.

### Callables and explicit defaults

- `_number(value)`
- `reconcile_fyers(plan, rows, preview_id, entry_order_id=None)`

### Literal payload and lookup fallbacks

- `limitPrice` → `0`
- `stopLoss` → `0`
- `stopPrice` → `0`
- `takeProfit` → `0`

## sector_heatmap/chart_trade_stream.py

[Owning source](../sector_heatmap/chart_trade_stream.py)

Read-only Delta public-trade capture for seconds and transaction-count charts.

### Callables and explicit defaults

- `trade_bars(trades, interval, coverage_start, now, *, delta_width=None)`
- `DeltaChartTrades.__init__(self, symbol='BTCUSD')`
- `DeltaChartTrades.run(self)`
- `DeltaChartTrades.stop(self)`
- `DeltaChartTrades.archive(self, through)`
- `DeltaChartTrades.disconnect(self, now)`
- `DeltaChartTrades.reset(self, stamp)`
- `DeltaChartTrades.ingest(self, packet)`
- `DeltaChartTrades.drain(self, watermark)`
- `DeltaChartTrades.snapshot(self, interval, now=None, *, delta_width=None)`

### Literal payload and lookup fallbacks

- `channels` → `[]`

## sector_heatmap/chart_trading.py

[Owning source](../sector_heatmap/chart_trading.py)

Account-scoped chart trading controller; broker adapters never cross sources.

### Callables and explicit defaults

- `dhan_chart_enabled()`
- `broker_active(broker)`
- `ChartTradingService.__init__(self, account, path, adapter_factory, *, clock=None, conditional_factory=None)`
- `ChartTradingService._authorize(self, user, payload)`
- `ChartTradingService.prepare(self, user, payload)`
- `ChartTradingService.arm(self, user, payload)`
- `ChartTradingService.cancel_condition(self, user, payload)`
- `ChartTradingService.status(self, user, payload)`
- `ChartTradingService.start_monitor(self)`
- `ChartTradingService.close(self)`
- `handle(handler, path, payload, *, workspace_guard, fyers_execution, delta_execution=None, dhan_execution=None, dhan_tick_reader=None)`
- `get_service(server, guard, account, fyers_execution, delta_execution=None, *, dhan_execution=None, dhan_tick_reader=None)`
- `resume_existing(server, guard, fyers_execution, delta_execution=None, *, dhan_execution_factory=None, dhan_tick_reader=None)`
- `close_services(server)`

## sector_heatmap/chart_workspace.py

[Owning source](../sector_heatmap/chart_workspace.py)

Selected-broker candle history and WebSocket aggregation for chart analysis.

### Callables and explicit defaults

- `chart_minutes(interval)`
- `trade_interval(interval)`
- `chart_interval(interval)`
- `calendar_bounds(stamp, interval, nse)`
- `calendar_history(daily, interval, now, after, nse=True, *, daily_close=55800, first_trading_day=None, session_day=None, period_closed=None)`
- `fyers_nse_period_closed(start, end, parts, now)`
- `calendar_live(daily, interval, nse=True)`
- `history_payload(result)`
- `nse_daily(rows, now, session_end=55800)`
- `combine_bars(rows, minutes, native, now=None, cursor=None, nse=True, *, session_open=33300, session_seconds=22500, utc_daily=False)`
- `require_chart(user, store, path)`
- `serve_pine_worker(handler, local_auth, worker_path)`
- `validate_chart_cursor(value, now=None, *, max_age_days=CHART_CALENDAR_LOOKBACK_DAYS + 366)`
- `chart_auth_failure(handler, error, broker)`
- `_fyers_master_rows(lines)`
- `_cached_fyers_master(path, version)`
- `_fyers_master_tickers(path, version)`
- `fyers_extra_session(symbol)`
- `search_cached_fyers_chart_symbols(paths, query='', offset=0, limit=100)`
- `search_fyers_chart_symbols(master_contents, query='', offset=0, limit=100)`
- `_search_fyers_catalogs(catalogs, query, offset, limit)`
- `requested_chart_symbol(query, broker)`
- `serve_history(handler, local_auth, workspace_guard, load_fyers, load_delta, load_dhan=None)`
- `FyersChartBars.__init__(self, symbol=SYMBOL, *, currency=False, mcx_bounds=None)`
- `FyersChartBars.ingest(self, tick, now=None)`
- `FyersChartBars.reset_coverage(self)`
- `FyersChartBars.snapshot(self, interval, connected)`
- `chart_session_exception(broker, symbol, moment=None)`
- `serve_live(handler, local_auth, workspace_guard, bars, feed, delta_snapshot, dhan_snapshot=None)`
- `fyers_mcx_session_bounds(symbol, stamp)`
- `mcx_history_bars(rows, minutes, native, now, cursor, *, include_current=False, coverage_since=None, symbol='', session_bounds=None)`
- `fetch_fyers_history(client, interval, now=None, after=None, *, symbol=FyersChartBars.SYMBOL, include_forming=False, before=None)`
- `fetch_delta_history(delta, interval, after=None, *, symbol=DELTA_SYMBOL, before=None)`
- `subscribe_delta_chart(stream, activity, symbol, now)`
- `delta_live_snapshot(stream, minutes, *, symbol=DELTA_SYMBOL)`
- `motilal_eod_candle(service, exchange, token, now, close_offset)`
- `motilal_chart(service, interval, after=None, live=False, *, symbol=None, before=None)`
- `require_dhan_data(client)`
- `dhan_mcx_chart_bounds(stamp)`
- `search_dhan_chart_symbols(master, query, now, limit=100, *, offset=0, segment_filter='')`
- `resolve_dhan_chart_symbol(master, symbol, now)`
- `fetch_dhan_history(client, interval, after=None, now=None, *, before=None, security_id='13', exchange_segment='IDX_I', instrument='INDEX')`
- `dhan_rows(raw)`
- `DhanChartStream.__init__(self, client, *, symbol=None, account_id=None, clock=time.time)`
- `DhanChartStream.send_subscription(socket, segment, security_id)`
- `DhanChartStream.subscribe(self, symbol)`
- `DhanChartStream.ingest(self, socket, packet)`
- `DhanChartStream.execution_tick(self, symbol)`
- `DhanChartStream.snapshot(self, minutes, *, symbol=None)`
- `DhanChartStream.stop(self)`

### Literal payload and lookup fallbacks

- `SEM_CUSTOM_SYMBOL` → `''`
- `SEM_EXPIRY_DATE` → `''`
- `SEM_INSTRUMENT_NAME` → `''`
- `SEM_SMST_SECURITY_ID` → `''`
- `SEM_TRADING_SYMBOL` → `''`
- `before` → `[]`
- `chart-workspace` → `False`
- `dataPlan` → `''`

## sector_heatmap/closed_pnl.py

[Owning source](../sector_heatmap/closed_pnl.py)

Read-only dated realised reports. No execution or runner dependencies.

### Callables and explicit defaults

- `report_range(period, today, start=None, end=None)`
- `master_types(master_dir)`
- `category(row, types)`
- `range_report(app_id, token, period, today, fetcher, master_dir=None, start=None, end=None)`

### Literal payload and lookup fallbacks

- `buy_qty` → `0`
- `buy_rate` → `0`
- `data` → `[]`
- `realized_pnl` → `0`
- `segment_name` → `'Unclassified'`
- `sell_qty` → `0`
- `sell_rate` → `0`
- `summary_data` → `{}`
- `supported` → `False`
- `symbol_name` → `'—'`

## sector_heatmap/codex_handoff.py

[Owning source](../sector_heatmap/codex_handoff.py)

Isolated, cancellable Codex account analysis of public broker evidence only.

### Callables and explicit defaults

- `settings(workspace)`
- `failure_reason(event)`
- `check_event(event)`
- `review(workspace, evidence, instructions, schema, timeout=120)`

### Literal payload and lookup fallbacks

- `usage` → `{}`

## sector_heatmap/combined_handoff_worker.py

[Owning source](../sector_heatmap/combined_handoff_worker.py)

Fresh, account-isolated Handoff reporting. No ticket preparation or submission.

### Callables and explicit defaults

- `run(request_path, output_path)`
- `main()`

### Literal payload and lookup fallbacks

- `candidates` → `[]`
- `cards` → `[]`
- `exclusions` → `[]`

## sector_heatmap/combined_reports.py

[Owning source](../sector_heatmap/combined_reports.py)

Shared sector + Handoff + screener digest. Read-only sources, Telegram only.

### Callables and explicit defaults

- `number(value)`
- `grade(row)`
- `slot(now, interval_ms=900000)`
- `freshness(value, now, max_age=1800)`
- `stamp(value)`
- `level(value)`
- `scope(config)`
- `screener_source(root=ROOT)`
- `intraday_asof(rows)`
- `screen_section(value, now)`
- `handoff_section(report, completed, now)`
- `select_handoff_outcome(matches)`
- `collect(config, now, screener=None, root=ROOT, mtf=None, handoff_report=None)`
- `render(snapshot, target)`
- `CombinedOutbox.__init__(self, *args, **kwargs)`
- `CombinedOutbox.deliver(self, config, sender=None, only_event=None)`
- `CombinedOutbox.settle(self)`
- `enqueue(box, config, snapshot, key, completed_run=False)`
- `deliver_card(channel, config, event)`
- `send_text(config, event, audit)`
- `launch(config, request, output, worker_module='sector_heatmap.combined_screener_worker')`
- `read_sector_mtf(config, output, timeout=210, progress=None)`
- `main()`

### Literal payload and lookup fallbacks

- `analyzed` → `0`
- `broker` → `'FYERS'`
- `cards` → `[]`
- `combined_reports` → `{}`
- `direction` → `'Unavailable'`
- `recover` → `True`
- `refresh_interval_ms` → `900000`
- `results` → `[]`
- `status` → `'UNAVAILABLE'`
- `symbol` → `'Instrument'`
- `telegram` → `{}`
- `total` → `0`

## sector_heatmap/combined_screener_analysis.py

[Owning source](../sector_heatmap/combined_screener_analysis.py)

Read-only reuse of dashboard screener analysis; no ticket or execution paths.

### Callables and explicit defaults

- `analyze(payload, service)`

### Literal payload and lookup fallbacks

- `score` → `0`

## sector_heatmap/combined_screener_worker.py

[Owning source](../sector_heatmap/combined_screener_worker.py)

Account-isolated, rate-paced completed-candle screener; never trades.

### Callables and explicit defaults

- `owned_token(request)`
- `build_service(token, output_path)`
- `run(request_path, output_path, pace=3)`
- `main()`

### Literal payload and lookup fallbacks

- `timeframe_states` → `{}`

## sector_heatmap/combined_sector_worker.py

[Owning source](../sector_heatmap/combined_sector_worker.py)

Read-only sector MTF collector using dashboard calculations; no execution imports.

### Callables and explicit defaults

- `collect(service)`
- `run(request_path, output_path)`
- `main()`

## sector_heatmap/company_fundamentals.py

[Owning source](../sector_heatmap/company_fundamentals.py)

Bounded, cached public NSE filing evidence. No technical-to-fundamental inference.

### Callables and explicit defaults

- `Rows.__init__(self)`
- `Rows.handle_starttag(self, t, a)`
- `Rows.handle_data(self, d)`
- `Rows.handle_endtag(self, t)`
- `norm(s)`
- `numeric(s)`
- `parse_filing(html, symbol, period)`
- `Provider.__init__(self, workspace, clock=time.time, get=None)`
- `Provider.db(self)`
- `Provider.download(url)`
- `Provider.etf_evidence(self, symbol, underlying)`
- `Provider.evidence(self, underlying)`

### Literal payload and lookup fallbacks

- `data` → `[]`

## sector_heatmap/config.py

[Owning source](../sector_heatmap/config.py)

### Callables and explicit defaults

- `public_origin()`
- `_read_env_file(path)`
- `_normalize_aliases(values)`
- `_user_config_files()`
- `_read_token_cache()`
- `_workspace_profile()`
- `load_config()`
- `_atomic_private_write(path, content)`
- `save_access_token(token)`

### Literal payload and lookup fallbacks

- `FYERS_APP_ID` → `''`
- `HEATMAP_PORT` → `'8080'`
- `SECTOR_PULSE_PUBLIC_ORIGIN` → `''`
- `public_origin` → `''`

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

- `DeltaIPv4Adapter.init_poolmanager(self, connections, maxsize, block=False, **kwargs)`
- `delta_request_session()`
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
- `DeltaIndia._record_runner_job(self, new=False)`
- `DeltaIndia.status(self)`
- `DeltaIndia.configure(self, payload)`
- `DeltaIndia._private(self, method, path, params=None, body=None, credentials=None)`
- `DeltaIndia.verify_auth(self)`
- `DeltaIndia._number(value)`
- `DeltaIndia.account(self, payload=None)`
- `DeltaIndia._write(self, path, data)`
- `DeltaIndia._save_live(self)`
- `DeltaIndia.catalog(self, *, chart=False)`
- `DeltaIndia._metadata(self, r)`
- `DeltaIndia.product(self, symbol, *, chart=False)`
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
- `runner_job` → `{}`
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

## sector_heatmap/dhan_account_login.py

[Owning source](../sector_heatmap/dhan_account_login.py)

Owner-scoped Dhan API-key consent; no execution or runner operations.

### Callables and explicit defaults

- `request_json(path, credentials, query, method='GET')`
- `login(store, runtime, user, aid, token_id=None)`

### Literal payload and lookup fallbacks

- `created` → `0`
- `dhanClientId` → `''`

## sector_heatmap/dhan_account_reports.py

[Owning source](../sector_heatmap/dhan_account_reports.py)

Account-native positions and conservative historical realized-P&L reconstruction.

### Callables and explicit defaults

- `number(value)`
- `period_start(period, now)`
- `trade_time(value)`
- `checked_rows(rows, client_id)`
- `DhanAccountReports.__init__(self, execution, now=lambda: datetime.now(IST))`
- `DhanAccountReports.report_lock(self)`
- `DhanAccountReports.client(self)`
- `DhanAccountReports.positions(self)`
- `DhanAccountReports.history(self, c, start, end)`
- `DhanAccountReports.realized(self, period)`
- `reconstruct(rows, client_id, start, now)`

### Literal payload and lookup fallbacks

- `complete` → `False`
- `exchangeTradeId` → `''`
- `instrument` → `''`

## sector_heatmap/dhan_execution.py

[Owning source](../sector_heatmap/dhan_execution.py)

Account-owned Dhan v2 manual LIMIT tickets; no strategy or protective-order routing.

### Callables and explicit defaults

- `number(value, label, positive=False)`
- `DhanAPIError.__init__(self, message, definitive_rejection=False, reauthentication_required=False, rate_limited=False)`
- `contract_underlying(row)`
- `fresh_quote_snapshot(client, segment, security_id, clock=time.time, max_age=15)`
- `DhanClient.__init__(self, credentials)`
- `DhanClient._quote_slot(self, category='quote', interval=1.1)`
- `DhanClient.request(self, method, path, payload=None)`
- `DhanClient._request(self, method, path, payload=None)`
- `DhanMaster.__init__(self)`
- `DhanMaster.load(self, now)`
- `DhanMaster.resolve(self, payload, now)`
- `DhanExecutionService.__init__(self, account, folder, client_factory=DhanClient, master=None, now=None, egress=None, execution_halt=None, execution_allowed=None)`
- `DhanExecutionService._egress()`
- `DhanExecutionService._client(self)`
- `DhanExecutionService.capabilities(self)`
- `DhanExecutionService.status(self)`
- `DhanExecutionService._fresh_preview_quote(self, client, segment, security_id)`
- `DhanExecutionService._preflight(self, payload)`
- `DhanExecutionService.prepare(self, payload)`
- `DhanExecutionService._submission_lock(self)`
- `DhanExecutionService.submit(self, preview_id, confirmation)`
- `DhanExecutionService._send(self, preview_id, fresh)`
- `DhanExecutionService.prepare_batch(self, payload)`
- `DhanExecutionService.submit_batch(self, preview_id, confirmation)`
- `DhanExecutionService.reconcile(self)`
- `DhanExecutionService.reconcile_protection(self, preview_id)`

### Literal payload and lookup fallbacks

- `SEM_EXPIRY_DATE` → `''`
- `SEM_INSTRUMENT_NAME` → `''`
- `broker` → `''`
- `daily_loss_limit` → `5000`
- `data` → `{}`
- `dataPlan` → `''`
- `exit_plan_mode` → `'FIXED_TARGET'`
- `idea_risk_limit` → `2000`
- `max_simultaneous_positions` → `5`
- `netQty` → `0`
- `orderStatus` → `'PENDING'`
- `order_ids` → `[]`
- `order_route` → `'NORMAL'`
- `order_type` → `'LIMIT'`
- `quantity` → `1`
- `quantity_multiplier` → `1`
- `realizedProfit` → `0`
- `risk_controls_enforced` → `True`
- `risk_reserve` → `1000`
- `transaction_type` → `'BUY'`

## sector_heatmap/dhan_form_routes.py

[Owning source](../sector_heatmap/dhan_form_routes.py)

Compatibility reads for existing strategy forms, bound to one private Dhan account.

### Callables and explicit defaults

- `config(service, payload)`
- `snapshot(service)`
- `chart(service, query)`
- `read(service, action, query)`
- `write(service, action, payload)`

### Literal payload and lookup fallbacks

- `allow_reclaims` → `'true'`
- `bars` → `500`
- `ema_length` → `21`
- `events` → `[]`
- `execution_mode` → `'OPTIONS'`
- `order_history` → `[]`
- `timeframe` → `'5 minutes'`

## sector_heatmap/dhan_handoff.py

[Owning source](../sector_heatmap/dhan_handoff.py)

Broker-native, read-only Dhan evidence for the shared Analysis Handoff.

### Callables and explicit defaults

- `DhanHandoff.__init__(self, execution, sectors)`
- `DhanHandoff.folder(self)`
- `DhanHandoff.cash_master(self)`
- `DhanHandoff.candidates(self, mode)`
- `DhanHandoff.positions(self)`
- `DhanHandoff.orders(self)`
- `DhanHandoff.funds(self)`
- `DhanHandoff.quote(self, symbol)`
- `DhanHandoff.tick(self, symbol)`
- `DhanHandoff.options(self, symbol, direction, risk)`

### Literal payload and lookup fallbacks

- `candidates` → `[]`
- `constituent_movers` → `[]`
- `legs` → `[]`
- `proposals` → `[]`
- `sectors` → `[]`

## sector_heatmap/dhan_indicator_runners.py

[Owning source](../sector_heatmap/dhan_indicator_runners.py)

Dhan runners reuse the application's completed-candle signal functions.

### Callables and explicit defaults

- `configuration(payload)`
- `IndicatorRunner.signal_key(self, sig)`
- `IndicatorRunner.signal(self)`
- `IndicatorRunner.fresh_cross(self, sig)`
- `IndicatorRunner.exit_signal(self, sig, direction)`
- `IndicatorRunner.exit_reason_for(self, sig, position)`
- `IndicatorRunner.validate_entry_authorization(self, position)`
- `IndicatorRunner.complete_pending(self, filled, price)`
- `IndicatorRunner.step(self)`

### Literal payload and lookup fallbacks

- `kama_exit_times` → `{}`
- `resistance_volume_exit` → `False`

## sector_heatmap/dhan_mcx.py

[Owning source](../sector_heatmap/dhan_mcx.py)

Dhan-native MCX contract discovery.

### Callables and explicit defaults

- `current(row, now)`
- `commodity(row)`
- `futures(rows, now, text='')`
- `host(rows, symbol, now)`
- `option_series(rows, future, now)`
- `paired_options(options)`
- `search(rows, now, text='')`
- `valuation(row)`
- `session(now)`
- `expiry_at(row)`
- `entry_cutoff(row)`
- `trading_bounds(now)`
- `session_open(now)`

### Literal payload and lookup fallbacks

- `SEM_TRADING_SYMBOL` → `''`

## sector_heatmap/dhan_protection.py

[Owning source](../sector_heatmap/dhan_protection.py)

Read-only native Dhan Super Order registration reconciliation.

### Callables and explicit defaults

- `number(value)`
- `reconcile(ticket, protection, order_id, correlation, rows, tick)`

## sector_heatmap/dhan_recovery.py

[Owning source](../sector_heatmap/dhan_recovery.py)

Read-only evidence for a fully closed, externally managed Dhan position.

### Callables and explicit defaults

- `external_close_evidence(broker, position, pending, history)`
- `_reconcile_external_close(runner, payload)`
- `reconcile_external_close(runner, payload)`

### Literal payload and lookup fallbacks

- `entry_side` → `1`
- `losses` → `{}`
- `netQty` → `0`
- `order` → `{}`
- `order_history` → `[]`
- `quantity_multiplier` → `1`
- `realized_pnl` → `0`

## sector_heatmap/dhan_screener.py

[Owning source](../sector_heatmap/dhan_screener.py)

Account-owned Dhan Screener research. No execution or shared credentials.

### Callables and explicit defaults

- `DhanScreener.__init__(self, execution)`
- `DhanScreener.quotes(self, symbols)`
- `DhanScreener.refresh(self, payload, fetch_source, sectors)`
- `DhanScreener.analyze(self, payload)`

### Literal payload and lookup fallbacks

- `NSE_EQ` → `{}`
- `candidates` → `[]`
- `data` → `{}`
- `score` → `0`

## sector_heatmap/dhan_sector_analysis.py

[Owning source](../sector_heatmap/dhan_sector_analysis.py)

Read-only sector analysis using one owned Dhan account's Data API.

### Callables and explicit defaults

- `normalized(value)`
- `DhanCandleHistoryProvider.__init__(self, execution, now=None)`
- `DhanCandleHistoryProvider.prepare(self)`
- `DhanCandleHistoryProvider.resolve(self, symbol)`
- `DhanCandleHistoryProvider._request(self, path, payload)`
- `DhanCandleHistoryProvider.parse(raw)`
- `DhanCandleHistoryProvider._download(self, symbol, resolution, lookback_days)`
- `DhanCandleHistoryProvider.constituent_moves(self)`
- `DhanSectorAnalysisService.__init__(self, execution, provider=None, now=None)`
- `DhanSectorAnalysisService.refresh(self)`
- `DhanSectorAnalysisService.snapshot(self, mode='intraday', sector_id=None)`

### Literal payload and lookup fallbacks

- `NSE_EQ` → `{}`
- `data` → `{}`
- `dataPlan` → `''`

## sector_heatmap/dhan_strategy_broker.py

[Owning source](../sector_heatmap/dhan_strategy_broker.py)

User-owned Dhan adapter for durable option strategy runners.

### Callables and explicit defaults

- `whole(value, label)`
- `Broker.__init__(self, service, clock=time.time)`
- `Broker.live_enabled(self)`
- `Broker.authenticated_client(self)`
- `Broker._rows(self)`
- `Broker._segment(row)`
- `Broker._meta(self, row)`
- `Broker.underlying(self, symbol)`
- `Broker.search(self, text, market=None)`
- `Broker.host_tick_size(self, symbol)`
- `Broker.session_policy(self, config)`
- `Broker.route_availability(self, config)`
- `Broker.validate_config(self, config)`
- `Broker.subscribe(self, symbol, seconds=None)`
- `Broker.start(self)`
- `Broker.stop(self)`
- `Broker.stream_status(self)`
- `Broker.contract(self, symbol)`
- `Broker._market(self, meta, depth=True)`
- `Broker.quote(self, symbol)`
- `Broker.premium_quotes(self, contracts)`
- `Broker.live_price(self, config, now)`
- `Broker.resolve(self, config, direction)`
- `Broker.warm_options(self, config)`
- `Broker.history_lock(self, path)`
- `Broker.candles(self, config)`
- `Broker.forming_for_stream(self, config, now)`
- `Broker.forming(self, config, rows, now)`
- `Broker.order(self, symbol, qty, side, quote)`
- `Broker.validate_order(self, order)`
- `Broker._account_rows(self, path)`
- `Broker.positions(self)`
- `Broker._order_row(self, r)`
- `Broker.orders(self)`
- `Broker.reconcile_position(self, symbol, qty)`
- `Broker.preflight(self, order, config)`
- `Broker._native(self, order, client)`
- `Broker.place(self, order)`
- `Broker._place_checked(self, order, attempt)`
- `Broker.cancel(self, order_id)`

### Literal payload and lookup fallbacks

- `SEM_EXPIRY_DATE` → `''`
- `averageTradedPrice` → `0`
- `costPrice` → `0`
- `dataPlan` → `''`
- `dhanClientId` → `''`
- `filledQty` → `0`

## sector_heatmap/dhan_strategy_service.py

[Owning source](../sector_heatmap/dhan_strategy_service.py)

Account-bound Dhan strategy services; no global credential fallback.

### Callables and explicit defaults

- `renko_configuration(payload)`
- `rsi_config(payload)`
- `DhanRenkoRunner.event(self, code, message)`
- `DhanRenkoRunner.session_bounds(self, c)`
- `DhanRenkoRunner.deadline(self)`
- `DhanRenkoRunner.step(self)`
- `DhanRenkoRunner.snapshot(self)`
- `DhanRenkoRunner.record_order(self, pending, status, filled=0, price=None)`
- `DhanRsiRunner.event(self, code, message)`
- `DhanRsiRunner.record_order(self, pending, status, filled=0, price=None)`
- `Service.__init__(self, execution, root, instance='default', strategy='renko')`
- `Service.chart_config(self, query)`
- `Service.chart(self, query)`
- `Service.get_action(self, handler, action, query)`
- `Service.post_action(self, handler, action, payload)`

### Literal payload and lookup fallbacks

- `execution_route` → `'OPTIONS'`
- `order_history` → `[]`
- `underlying` → `''`
- `validity` → `'IOC'`

## sector_heatmap/equity_exit_plan.py

[Owning source](../sector_heatmap/equity_exit_plan.py)

Planning-only cash-equity exit plans; contains no broker mutations.

### Callables and explicit defaults

- `build_equity_exit_plan(direction, quantity, entry, target, mode='FIXED_TARGET')`
- `advance_exit_plan(plan, event, candle=None)`

## sector_heatmap/exposure_guard.py

[Owning source](../sector_heatmap/exposure_guard.py)

Selected-broker symbol/underlying exposure; never combines broker accounts.

### Callables and explicit defaults

- `symbol_key(symbol)`
- `same_underlying(first, second)`
- `open_exposures(positions, orders=())`
- `matches_exposure(symbol, rows, contract_symbols=())`
- `exclude_exposure(candidates, positions, orders=())`
- `exclude_handoff_cards(candidates, cards, positions, orders=())`
- `broker_exposures(broker)`

### Literal payload and lookup fallbacks

- `orderStatus` → `''`
- `symbol` → `''`

## sector_heatmap/file_lock.py

[Owning source](../sector_heatmap/file_lock.py)

OS-backed cross-process locks; never silently fall back to thread-only locks.

### Callables and explicit defaults

- `lock_file(fd, blocking=True)`
- `unlock_file(fd)`

## sector_heatmap/fundamental_feedback.py

[Owning source](../sector_heatmap/fundamental_feedback.py)

AI-selected, report-only financial context shared by Handoff and Holdings.

### Callables and explicit defaults

- `schema(base)`
- `compact(e)`
- `report(e, feedback=None)`
- `holdings(result, payload, workspace)`

### Literal payload and lookup fallbacks

- `missing` → `[]`
- `rows` → `[]`

## sector_heatmap/fyers_execution.py

[Owning source](../sector_heatmap/fyers_execution.py)

FYERS-only, confirmation-gated ticket preparation and reconciliation.

### Callables and explicit defaults

- `_PreviewReads.__init__(self, client, clock=None, sleep=None)`
- `_PreviewReads.__getattr__(self, name)`
- `_review_terms(preview)`
- `PreviewChanged.__init__(self, preview)`
- `_contract_identity(instrument)`
- `_reviewed_instrument(current, reviewed)`
- `_ticket_terms(preview)`
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
- `FyersExecutionService._preflight(self, payload, read_client=None, reviewed=None)`
- `FyersExecutionService._archive_entry_evidence(self, preview_id, stored, refreshed)`
- `FyersExecutionService._reconciled_protection(self, result)`
- `FyersExecutionService.reconcile_protection(self, preview_id)`
- `FyersExecutionService._archive_entry_result(self, result)`
- `FyersExecutionService.prepare(self, payload)`
- `FyersExecutionService._store_preview(self, payload, preview)`
- `FyersExecutionService._budget_equity_batch(self, payload, items)`
- `FyersExecutionService._batch_preflight(self, payload)`
- `FyersExecutionService.prepare_batch(self, payload)`
- `FyersExecutionService._store_batch_preview(self, payload, preview)`
- `FyersExecutionService._linked_exit_fields(preview, leg)`
- `FyersExecutionService._refresh_reviewed_batch(self, payload, reviewed)`
- `FyersExecutionService.submit_batch(self, preview_id, confirmation)`
- `FyersExecutionService._submit_option_batch(self, preview_id, refreshed)`
- `FyersExecutionService.submit(self, preview_id, confirmation)`

### Literal payload and lookup fallbacks

- `broker` → `''`
- `contracts` → `[]`
- `contracts` → `[{}]`
- `data` → `[]`
- `data` → `{}`
- `execution_entry_order` → `{}`
- `handoff_product_attempt` → `1`
- `instrument` → `{}`
- `items` → `[]`
- `margin` → `{}`
- `net_qty` → `0`
- `optionsChain` → `[]`
- `order_ids` → `[]`
- `proposal` → `{}`
- `protected_quantity` → `0`
- `quote` → `{}`
- `realizedProfit` → `0`
- `warnings` → `[]`

## sector_heatmap/fyers_history.py

[Owning source](../sector_heatmap/fyers_history.py)

Bound FYERS read-only candle requests; never retry a broker mutation.

### Callables and explicit defaults

- `FyersHistoryRateLimited.__init__(self, retry_after)`
- `_retry_seconds(response)`
- `_history_budget_key(client)`
- `_check_history_cooldown(key)`
- `_limit_history(key, response)`
- `history(client, data)`
- `quotes(client, data)`
- `account_read(client, method)`

## sector_heatmap/fyers_oauth_routing.py

[Owning source](../sector_heatmap/fyers_oauth_routing.py)

Notification-free OAuth routing; worker validates the full one-time state.

### Callables and explicit defaults

- `account_from_state(value)`

## sector_heatmap/fyers_protection.py

[Owning source](../sector_heatmap/fyers_protection.py)

Read-only FYERS protection reconciliation; never creates or changes orders.

### Callables and explicit defaults

- `number(value)`
- `reconcile(preview, order_ids, book)`

### Literal payload and lookup fallbacks

- `filledQty` → `0`

## sector_heatmap/fyers_transport.py

[Owning source](../sector_heatmap/fyers_transport.py)

Per-client IPv4 transport for the synchronous FYERS SDK; no global network patches.

### Callables and explicit defaults

- `IPv4Adapter.init_poolmanager(self, connections, maxsize, block=False, **kwargs)`
- `client(*args, **kwargs)`

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
- `fetch_fyers_chain(client, underlying_symbol, strike_count=8, *, now=None)`
- `_leg(chain_item, master, *, require_greeks=True)`
- `_spread(identifier, label, direction, strategy, long_leg, short_leg, width, scenario)`
- `_nearest_pair(legs, spot, long_higher=False)`
- `build_defined_risk_spreads(chain_payload, expiry, master_records, direction, risk=None)`
- `build_long_option_proposals(chain_payload, expiry, master_records, direction, risk=None, *, require_greeks=True)`
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

## sector_heatmap/handoff_ai.py

[Owning source](../sector_heatmap/handoff_ai.py)

Bounded AI commentary on supplied broker evidence; no order tools.

### Callables and explicit defaults

- `HandoffAI.__init__(self, workspace, sender=None, key_reader=None, model=None, provider='RULES_ONLY', explicit_selection=False)`
- `HandoffAI.from_payload(cls, workspace, payload)`
- `HandoffAI.review(self, evidence)`
- `HandoffAI.validate(value, evidence, provider, model, usage)`
- `stock_evidence(card)`
- `review_stock_handoff(result, payload, workspace)`

### Literal payload and lookup fallbacks

- `candidate` → `{}`
- `candidates` → `[]`
- `cards` → `[]`
- `recommendations` → `[]`

## sector_heatmap/handoff_allocation.py

[Owning source](../sector_heatmap/handoff_allocation.py)

Broker-independent Handoff ranking, bounded allocation and durable claims.

### Callables and explicit defaults

- `amount(value)`
- `normalized_score(row)`
- `identity(row)`
- `validate(row)`
- `rank(rows, *, exposed=(), seen=(), top=5)`
- `allocate(rows, *, capital=100000, used=0, funds=None, exposed=(), seen=(), top=5)`
- `Claims.__init__(self, path)`
- `Claims.db(self)`
- `Claims.reserve(self, account, plan, cap=100000)`
- `Claims.not_submitted(self, account, fingerprint)`
- `Claims.confirmed(self, account, fingerprint, notional=None)`
- `Claims.unsettled(self, account)`
- `Claims.settle_confirmed(self, account, exposed_underlyings)`
- `Claims.uncertain(self, account, fingerprint)`

### Literal payload and lookup fallbacks

- `lot_size` → `1`
- `rating` → `''`

## sector_heatmap/handoff_analysis.py

[Owning source](../sector_heatmap/handoff_analysis.py)

Read-only Handoff analysis engine, reusable without starting dashboard runners.

### Callables and explicit defaults

- `join_unique_reasons(items)`
- `instrument_route(payload)`
- `opportunities(payload, provider, analysis_runs)`
- `size(payload, analysis_runs)`

### Literal payload and lookup fallbacks

- `candidates` → `[]`
- `exclusions` → `[]`
- `legs` → `[]`
- `method` → `'structure'`
- `screener` → `{}`
- `source_failures` → `[]`

## sector_heatmap/handoff_authorization.py

[Owning source](../sector_heatmap/handoff_authorization.py)

Revocable account-owned schedule grants, independent of browser sessions.

### Callables and explicit defaults

- `save(store, account, user, enabled)`
- `identity(store, account, folder, user_id)`

## sector_heatmap/handoff_bridge.py

[Owning source](../sector_heatmap/handoff_bridge.py)

Owned loopback adapter. Analysis and previews are separate from submissions.

### Callables and explicit defaults

- `bounded_preview(bridge, payload, card, quantity, limit)`
- `NoRedirect.redirect_request(self, *args, **kwargs)`
- `OwnedBridge.__init__(self, root, store, user, account, token, clock=time.time)`
- `OwnedBridge.identity(self)`
- `OwnedBridge.request(self, operation, payload=None)`
- `OwnedBridge.read_worker(self, action='state', preview_id=None)`
- `OwnedBridge.exposure(self, policy)`
- `OwnedBridge.auto_ready(self)`
- `OwnedBridge.analysis(self, route, policy)`
- `OwnedBridge.collect(self, policy)`
- `OwnedBridge.normalized(preview, card, payload)`
- `OwnedBridge.execute(self, plan, policy)`
- `OwnedBridge.process_entry_triggers(self, schedule)`
- `OwnedBridge._execute_now(self, plan, policy)`
- `OwnedBridge.submit_prepared(self, plan, preview)`
- `OwnedBridge.reconcile_intent(self, preview_id, plan)`

### Literal payload and lookup fallbacks

- `candidate` → `{}`
- `candidates` → `[]`
- `cards` → `[]`
- `exclusions` → `[]`
- `features` → `[]`
- `fingerprint` → `''`
- `mode` → `'MANUAL'`
- `provenance` → `[]`
- `rating` → `''`
- `recommendations` → `[]`
- `report_card` → `{}`
- `source` → `{}`

## sector_heatmap/handoff_broker_read.py

[Owning source](../sector_heatmap/handoff_broker_read.py)

Isolated read-only account evidence for Handoff automation.

### Callables and explicit defaults

- `finite(v, label, nonnegative=False)`
- `canonical(symbol)`
- `fyers_fills(book)`
- `fyers_state(positions, orders, funds, holdings)`
- `dhan_state(client_id, positions, orders, funds, holdings, resolve)`
- `read_dhan()`
- `motilal_state(positions, orders, holdings, margin, resolve)`
- `read_motilal()`
- `read()`
- `public_read_error(error)`
- `main()`

### Literal payload and lookup fallbacks

- `averageTradedPrice` → `0`
- `filledQty` → `0`

## sector_heatmap/handoff_cards.py

[Owning source](../sector_heatmap/handoff_cards.py)

Images for newly completed owner-scoped Analysis Handoff jobs; no analysis execution.

### Callables and explicit defaults

- `owner_id(config, root=ROOT)`
- `scheduled_report(account, state, updated, saved, error=None)`
- `completed_jobs(config, root=ROOT)`
- `summary(result, broker, completed, historical=False)`
- `direction_palette(direction)`
- `render_handoff(snapshot, target)`
- `HandoffOutbox.enqueue_job(self, account, jobid, completed, result, historical=False)`
- `main()`

### Literal payload and lookup fallbacks

- `cards` → `[]`
- `data_quality` → `'UNAVAILABLE'`
- `enabled` → `False`
- `exclusions` → `[]`
- `handoff_cards` → `{}`
- `instruments` → `[]`
- `mode` → `'analysis'`
- `payload` → `{}`
- `source` → `{}`

## sector_heatmap/handoff_entry_conditions.py

[Owning source](../sector_heatmap/handoff_entry_conditions.py)

Explicit recommendation entry semantics, never inferred from arbitrary prose.

### Callables and explicit defaults

- `condition(symbol, direction, level)`
- `reached(c, q, now)`
- `stop_limit_before_trigger(c, q, traded_symbol, action, tick, limit)`
- `order_fields(payload, leg)`

### Literal payload and lookup fallbacks

- `proposal` → `{}`

## sector_heatmap/handoff_entry_queue.py

[Owning source](../sector_heatmap/handoff_entry_queue.py)

Persistent waiting entries. Only an authenticated owned bridge may submit.

### Callables and explicit defaults

- `Queue.__init__(self, folder)`
- `Queue.db(self)`
- `Queue.enqueue(self, plan, policy)`
- `Queue.release(self, schedule, key, reason)`
- `Queue.process(self, bridge, schedule)`

### Literal payload and lookup fallbacks

- `provider_at` → `0`
- `received_at` → `0`

## sector_heatmap/handoff_errors.py

[Owning source](../sector_heatmap/handoff_errors.py)

Boundary errors: only the owned adapter can prove no submit call began.

### Callables and explicit defaults

- `IncompleteAnalysis.__init__(self, message, report)`

## sector_heatmap/handoff_execution_worker.py

[Owning source](../sector_heatmap/handoff_execution_worker.py)

Private owned-account ticket worker; no network listener and no runner startup.

### Callables and explicit defaults

- `Worker.__init__(self)`
- `Worker.policy(self)`
- `Worker.live_gate(self)`
- `Worker.halt(self, reference, reason)`
- `Worker.submit_gate(self, preview_id, fingerprint)`
- `Worker.analyze(self, payload)`
- `Worker.call(self, operation, payload)`
- `main()`

### Literal payload and lookup fallbacks

- `candidate` → `{}`
- `execution_entry_order` → `{}`
- `expires_at` → `0`
- `payload` → `{}`
- `report_card` → `{}`
- `ticket_payload` → `{}`

## sector_heatmap/handoff_exit_broker.py

[Owning source](../sector_heatmap/handoff_exit_broker.py)

Owned FYERS adapter: exact-position exits only, streamed price triggers.

### Callables and explicit defaults

- `Broker.__init__(self, folder, account_id, registry)`
- `Broker.allowed(self, p)`
- `Broker.client(self)`
- `Broker.snapshot(self)`
- `Broker.session_open(self)`
- `Broker.entry_result(self, preview)`
- `Broker.subscribe(self, symbols)`
- `Broker.quote(self, symbol)`
- `Broker.preflight_takeover(self, r, pos)`
- `Broker.cancel_entry(self, r)`
- `Broker.detach(self, r, pos, parent)`
- `Broker.exit_position(self, r, pos)`
- `Broker.release(self, r)`
- `Broker.close(self)`
- `start_owned()`

## sector_heatmap/handoff_exit_monitor.py

[Owning source](../sector_heatmap/handoff_exit_monitor.py)

Durable, exit-only coordinator for explicitly authorized FYERS Handoff receipts.

### Callables and explicit defaults

- `numeric(v)`
- `integer(v)`
- `stamp()`
- `parent_id(row)`
- `cleared(row)`
- `Store.__init__(self, folder)`
- `Store.db(self)`
- `Store.policy(self)`
- `Store.authorize(self, account_id, user_id, at=None)`
- `Store.pause(self, enabled)`
- `Store.rows(self)`
- `Store.save(self, r)`
- `Store.event(self, key, kind, body)`
- `Store.beat(self, **kw)`
- `Store.status(self)`
- `Store.guard_new_entry(self)`
- `Monitor.__init__(self, store, broker, clock=time.time)`
- `Monitor.state(self, r, state, reason, **kw)`
- `Monitor.sync(self)`
- `Monitor.action(self, r, key, call)`
- `Monitor.inspect(self, r, s)`
- `Monitor.step_trade(self, r, s, enabled)`
- `Monitor.cycle(self)`
- `Service.__init__(self, folder, broker)`
- `Service.start(self)`
- `Service.close(self)`

### Literal payload and lookup fallbacks

- `at` → `0`
- `cash_product` → `'INTRADAY'`
- `created` → `0`
- `created_at` → `0`
- `enabled` → `False`
- `entry_filled` → `0`
- `entry_order` → `{}`
- `execution_entry_order` → `{'type': 'LIMIT'}`
- `exit_order_ids` → `[]`
- `expires_at` → `0`
- `filledQty` → `0`
- `netQty` → `0`
- `order_ids` → `[]`
- `preview_id` → `''`
- `price` → `0`
- `product_attempts` → `[]`
- `provider_at` → `0`
- `received_at` → `0`
- `state` → `'STARTING'`
- `ticket_payload` → `{}`

## sector_heatmap/handoff_freshness.py

[Owning source](../sector_heatmap/handoff_freshness.py)

Report provenance, independent from run update times and execution state.

### Callables and explicit defaults

- `report_freshness(output, source_slot, latest, now)`

## sector_heatmap/handoff_fyers_analysis.py

[Owning source](../sector_heatmap/handoff_fyers_analysis.py)

Isolated FYERS read-only provider for scheduled Handoff analysis.

### Callables and explicit defaults

- `Provider.__init__(self, account, folder, *, state_dir=None)`
- `Provider.refresh_session(self)`
- `Provider.candidates(self, mode)`
- `Provider.live_sectors(self)`
- `Provider.positions(self)`
- `Provider.orders(self)`
- `Provider.quote(self, symbol)`
- `Provider.tick(self, symbol)`
- `Provider.options(self, symbol, direction, risk)`

### Literal payload and lookup fallbacks

- `optionsChain` → `[]`

## sector_heatmap/handoff_levels.py

[Owning source](../sector_heatmap/handoff_levels.py)

Report-only price-basis schema. Never changes order or sizing inputs.

### Callables and explicit defaults

- `positive(x)`
- `horizon_levels(candidate, contract, proposal, horizon, entry, rr, now)`
- `report_levels(card, policy, mode, now=None, broker=None, selected_lots=None, lots_supplied=False)`

## sector_heatmap/handoff_manual.py

[Owning source](../sector_heatmap/handoff_manual.py)

Explicit owner-reviewed scheduled Handoff tickets; no submit on selection.

### Callables and explicit defaults

- `Manual.__init__(self, runtime, clock=time.time)`
- `Manual.prepare(self, user, aid, token, selected)`
- `Manual.submit(self, user, aid, ident, confirmation)`

### Literal payload and lookup fallbacks

- `recommendations` → `[]`

## sector_heatmap/handoff_observer.py

[Owning source](../sector_heatmap/handoff_observer.py)

Read-only Handoff fill journal and private position snapshots.

### Callables and explicit defaults

- `positive(value)`
- `Observer.__init__(self, folder, account, clock=time.time)`
- `Observer.update(self, state)`

### Literal payload and lookup fallbacks

- `filled_orders` → `[]`
- `last_positions` → `[]`
- `order_history` → `[]`
- `order_ids` → `[]`
- `positions` → `[]`

## sector_heatmap/handoff_outcomes.py

[Owning source](../sector_heatmap/handoff_outcomes.py)

Report-only INR scenarios from bought-option premiums, not underlying moves.

### Callables and explicit defaults

- `number(x)`
- `whole(x)`
- `money(x)`
- `sizing(contract, lots, source)`
- `scenario_costs(entry, exit_price, quantity, broker, symbol, clock)`
- `outcomes(horizon, contract, selected_lots, broker, clock, lots_source='Captured report-lots input')`

### Literal payload and lookup fallbacks

- `expiry` → `''`
- `symbol` → `''`

## sector_heatmap/handoff_priority.py

[Owning source](../sector_heatmap/handoff_priority.py)

One ranking rule for analysis, option budget, allocation and entry order.

### Callables and explicit defaults

- `priority_key(row)`

### Literal payload and lookup fallbacks

- `maximum_score` → `1`
- `score` → `0`

## sector_heatmap/handoff_product_retry.py

[Owning source](../sector_heatmap/handoff_product_retry.py)

One narrowly classified product correction, never a generic rejection retry.

### Callables and explicit defaults

- `restriction(row)`
- `eligible(preview, result, book, positions)`

### Literal payload and lookup fallbacks

- `contracts` → `[]`
- `filledQty` → `-1`
- `instrument` → `{}`
- `netPositions` → `[]`
- `netQty` → `0`
- `orderBook` → `[]`
- `order_ids` → `[]`
- `order_policy` → `{}`
- `qty` → `-1`
- `remainingQuantity` → `-1`

## sector_heatmap/handoff_runtime.py

[Owning source](../sector_heatmap/handoff_runtime.py)

Notification-sidecar coordinator; unrelated dashboards and runners stay owned.

### Callables and explicit defaults

- `Runtime.__init__(self, store, root, bridge_factory=OwnedBridge)`
- `Runtime.now()`
- `Runtime.owned(self, user, aid)`
- `Runtime.entry(self, user, aid)`
- `Runtime.status(self, user, aid)`
- `Runtime.diagnose(self, user, aid, token)`
- `Runtime.configure(self, user, aid, token, payload)`
- `Runtime.start(self, item, account)`
- `Runtime.restore(self)`
- `Runtime.watch(self, item)`
- `Runtime.observe(self, item, account)`
- `Runtime.close(self)`

### Literal payload and lookup fallbacks

- `analysis_scopes` → `[]`
- `candidate_scope` → `'MERGED'`
- `exclusions` → `[]`
- `executions` → `[]`
- `features` → `[]`
- `recommendations` → `[]`

## sector_heatmap/handoff_schedule.py

[Owning source](../sector_heatmap/handoff_schedule.py)

Account-owned 15-minute Handoff coordinator with injected owned broker adapters.

### Callables and explicit defaults

- `confirmed_notional(result)`
- `verified_daily_loss(state)`
- `slot_at(now)`
- `Schedule.__init__(self, path, account_id, broker, collect, exposure, execute=None, auto_ready=None, clock=time.time, recover_interrupted=True)`
- `Schedule.db(self)`
- `Schedule.policy(self)`
- `Schedule.configure(self, payload)`
- `Schedule.status(self)`
- `Schedule.loss_halted(self, state, now, limit)`
- `Schedule.reconcile_receipts(self, reader)`
- `Schedule.step(self, now)`

### Literal payload and lookup fallbacks

- `allow_duplicate_reports` → `False`
- `candidate_scope` → `'MERGED'`

### Configuration literals

- `DEFAULTS = dict(enabled=False, mode='AUTO', interval_minutes=15, capital=100000, top=5, candidate_scope='MERGED', option_lots=1, broker='FYERS', ai_provider='RULES_ONLY', daily_loss_limit=10000, cash_product='INTRADAY', amo=False, entries_halted=False, allow_duplicate_reports=False)`

## sector_heatmap/handoff_screener.py

[Owning source](../sector_heatmap/handoff_screener.py)

Owned selected Screener -> Handoff evidence. No order methods or authority.

### Callables and explicit defaults

- `parse_time(value)`
- `ticker(value)`
- `source_url(value)`
- `owned_folder()`
- `check_permissions(folder, broker='FYERS')`
- `Store.__init__(self, folder, broker='FYERS', *, state_dir=None)`
- `Store.db(self)`
- `Store.get(self)`
- `Store.save(self, payload)`
- `Store.cached(self, key, max_age, clock=time.time)`
- `Store.retain(self, key, value, clock=time.time)`
- `Store.progress(self, cycle, value, clock=time.time)`
- `Store.status(self)`
- `_fetch_source_once(url, session_factory=None)`
- `fetch_source(url, session_factory=None)`
- `evidence_current(frames, now)`
- `fresh_saved_evidence(folder, now)`
- `merge(collection, sectors, folder=None, *, auto=False, now=None, fetcher=fetch_source, master=None, state_dir=None)`
- `guard_entry_source(candidate, folder, now=None, broker='FYERS')`
- `guard_separate_submission(underlyings)`

### Literal payload and lookup fallbacks

- `SECTOR_PULSE_WORKSPACE_BROKER` → `'FYERS'`
- `candidates` → `[]`
- `provenance` → `[]`
- `results` → `[]`
- `sources` → `[]`
- `symbols` → `[]`

## sector_heatmap/handoff_ticket_client.py

[Owning source](../sector_heatmap/handoff_ticket_client.py)

Private persistent stdin/stdout client. A timed-out submission is never replayed.

### Callables and explicit defaults

- `TicketClient.__init__(self, root, store, account)`
- `TicketClient.call(self, operation, payload)`

## sector_heatmap/holdings_actions.py

[Owning source](../sector_heatmap/holdings_actions.py)

Explicit reviewed Dhan holding exits; never an entry or automatic trailing runner.

### Callables and explicit defaults

- `digest(value)`
- `decimal(value)`
- `grid(value, tick, rounding=ROUND_FLOOR)`
- `HoldingActions.__init__(self, execution, clock=time.time)`
- `HoldingActions._plan(self, report, row, payload, managed=None, monitor_path=None)`
- `HoldingActions.prepare(self, report, row, payload)`
- `HoldingActions.submit(self, preview_id, confirmation)`

### Literal payload and lookup fallbacks

- `availableQty` → `0`
- `netQty` → `0`
- `tradingSymbol` → `''`

## sector_heatmap/holdings_analysis.py

[Owning source](../sector_heatmap/holdings_analysis.py)

Read-only portfolio review. Deterministic hypotheses, never an order interface.

### Callables and explicit defaults

- `number(value)`
- `ema(values, period)`
- `indicators(rows)`
- `review(row, candles, expected_session, now=None)`
- `review_linear(row, candles, now)`
- `FyersHoldings.__init__(self, client)`
- `FyersHoldings.inventory(self)`
- `FyersHoldings.enrich(self, rows)`
- `FyersHoldings.candles(self, row, now)`
- `DeltaHoldings.__init__(self, delta)`
- `DeltaHoldings.inventory(self)`
- `DeltaHoldings.enrich(self, rows)`
- `DeltaHoldings.candles(self, row, now)`
- `HoldingsAnalysis.__init__(self, clock=time.time)`
- `HoldingsAnalysis.pace(self)`
- `HoldingsAnalysis.batch(self, adapter, capture_id=None, offset=0, limit=5, inventory_only=False)`

### Literal payload and lookup fallbacks

- `d` → `[]`
- `v` → `{}`

## sector_heatmap/holdings_chart.py

[Owning source](../sector_heatmap/holdings_chart.py)

Chart evidence from the exact validated completed rows used by review.

### Callables and explicit defaults

- `chart_evidence(rows)`
- `current_chart(adapter, row, now)`

## sector_heatmap/holdings_native_trailing.py

[Owning source](../sector_heatmap/holdings_native_trailing.py)

Native trailing protection ports. Reads never adopt a manual/strategy stop.

### Callables and explicit defaults

- `rows(reply, key)`
- `normalize(row, broker)`
- `Port.__init__(self, account, folder, client=None, service=None, delta=None, allowed=lambda: False, clock=time.time)`
- `Port._submission_lock(self)`
- `Port.adapter(self)`
- `Port.inventory(self)`
- `Port.protection(self)`
- `Port.identity(self, r, symbol, meta)`
- `Port.active(self, r)`
- `Port.order_id(self, r)`
- `Port.confirmed(self, ticket, order_id, tag)`
- `Port.mutate(self, ticket, old, tag)`
- `Actions.__init__(self, port, clock=time.time)`
- `Actions._plan(self, report, row, payload, managed=None, monitor_path=None)`
- `NativeTrails.__init__(self, port, store, clock=time.time)`
- `NativeTrails.normalize(self, row)`
- `NativeTrails.adapter(self)`
- `NativeTrails.preview(self, owner, report, row, payload)`
- `NativeTrails.managed(self, row, owner)`
- `NativeTrails.confirm_stop(self, state, ticket, order_id, correlation)`
- `NativeTrails.transmit(self, state, plan, create=False)`

### Literal payload and lookup fallbacks

- `buyorsell` → `''`
- `buyquantity` → `0`
- `clientId` → `''`
- `fy_id` → `''`
- `meta` → `{}`
- `netQty` → `0`
- `orderduration` → `''`
- `orderstatus` → `''`
- `ordertype` → `''`
- `products` → `[]`
- `producttype` → `''`
- `qtytradedtoday` → `0`
- `sellquantity` → `0`

## sector_heatmap/holdings_sectors.py

[Owning source](../sector_heatmap/holdings_sectors.py)

Exact public cash-symbol classifications. Never transmit portfolio values.

### Callables and explicit defaults

- `lookup(root, rows)`

### Literal payload and lookup fallbacks

- `captured` → `0`
- `data` → `[]`
- `symbol` → `''`

## sector_heatmap/holdings_sessions.py

[Owning source](../sector_heatmap/holdings_sessions.py)

Local exchange calendar gates: no broker work outside the applicable session.

### Callables and explicit defaults

- `window(segment, now, commodity_group=None)`

## sector_heatmap/holdings_trailing.py

[Owning source](../sector_heatmap/holdings_trailing.py)

Explicit-consent, durable Dhan holding-stop ratchet. Never auto-resumes.

### Callables and explicit defaults

- `interval(value)`
- `HoldingTrails.__init__(self, execution, actions, store, clock=time.time)`
- `HoldingTrails.path(self, mid)`
- `HoldingTrails.save(self, state)`
- `HoldingTrails.event(self, state, event, **fields)`
- `HoldingTrails.lock(self, security, segment)`
- `HoldingTrails.load(self, owner, mid)`
- `HoldingTrails.list(self, owner)`
- `HoldingTrails.managed(self, row, owner)`
- `HoldingTrails.preview(self, owner, report, row, payload)`
- `HoldingTrails.enable(self, owner, pid, confirmation, consent)`
- `HoldingTrails.stopped(self, state)`
- `HoldingTrails.assert_live(self)`
- `HoldingTrails.confirm_stop(self, state, ticket, order_id, correlation)`
- `HoldingTrails.transmit(self, state, plan, create=False)`
- `HoldingTrails.check(self, state)`
- `HoldingTrails.run(self, context, state, stored, fd)`
- `HoldingTrails.change_interval(self, owner, mid, minutes)`
- `HoldingTrails.stop(self, owner, mid)`

### Literal payload and lookup fallbacks

- `currency` → `'INR'`
- `interval_minutes` → `60`
- `interval_revision` → `0`
- `payload` → `{}`

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

## sector_heatmap/investment.py

[Owning source](../sector_heatmap/investment.py)

Public NSE EQ investment discovery; no execution or API keys.

### Callables and explicit defaults

- `number(v)`
- `options(p)`
- `download(session, url, payload=None)`
- `assess(raw, p, now)`
- `analyze(workspace, payload)`

### Literal payload and lookup fallbacks

- `d` → `[]`
- `mode` → `'RULES_ONLY'`
- `reviews` → `[]`
- `symbols` → `''`
- `totalCount` → `0`

## sector_heatmap/investment_entry.py

[Owning source](../sector_heatmap/investment_entry.py)

Account-owned NSE delivery entry monitoring over Dhan's native LIMIT route.

### Callables and explicit defaults

- `session_slot(now)`
- `received_quantity(value)`
- `DhanEntry.__init__(self, execution, account_lookup)`
- `DhanEntry.contract(self, symbol, now)`
- `DhanEntry.plan(self, row, ratio, quantity, now)`
- `DhanEntry.verify_enabled(self)`
- `DhanEntry.journal_rows(self)`
- `DhanEntry.own_order(self, client, path, record)`
- `DhanEntry.snapshot(self, client, plan)`
- `DhanEntry.check(self, plan, monitor_id, context, now, slot)`
- `DhanEntry.send(self, client, context, plan, monitor_id, quantity, slot, exposure)`
- `DhanEntry.symbol_lock(self, plan)`
- `DhanEntry.run(self, context, plan, monitor_id)`
- `DhanEntry.monitor(self, context, plan, monitor_id)`

### Literal payload and lookup fallbacks

- `filled` → `0`
- `filledQty` → `0`
- `tradingSymbol` → `''`

## sector_heatmap/investment_plan.py

[Owning source](../sector_heatmap/investment_plan.py)

Conditional volatility-based investment plans; no order authority.

### Callables and explicit defaults

- `plan(row, tick, now)`

### Literal payload and lookup fallbacks

- `metrics` → `{}`

## sector_heatmap/investment_returns.py

[Owning source](../sector_heatmap/investment_returns.py)

Calendar-year price returns from completed public daily bars.

### Callables and explicit defaults

- `anniversary(day, years)`
- `daily_quotes(data, provider_symbol)`
- `valid_price(value)`
- `calculate(data, provider_symbol, cutoff)`
- `daily_pullback(data, provider_symbol, cutoff)`
- `load(row, cache, now)`
- `enrich(workspace, result, now)`

### Literal payload and lookup fallbacks

- `annual_returns` → `{}`
- `close` → `[]`
- `daily_pullback` → `{'reason': 'Completed daily market history could not be loaded.'}`
- `indicators` → `{}`
- `meta` → `{}`
- `symbol` → `''`
- `timestamp` → `[]`

## sector_heatmap/investment_rs.py

[Owning source](../sector_heatmap/investment_rs.py)

Transparent sector peer-group and stock strength versus Nifty 500.

### Callables and explicit defaults

- `classify(values)`
- `calculate(rows, benchmark, now)`
- `collect(session, rows, now)`

### Literal payload and lookup fallbacks

- `d` → `[]`
- `data` → `[]`
- `metrics` → `{}`
- `missing` → `[]`

## sector_heatmap/job_http.py

[Owning source](../sector_heatmap/job_http.py)

Durable jobs around existing authenticated analysis and runner workflows.

### Callables and explicit defaults

- `operation(path)`
- `runner_routes(path)`
- `install(handler_class, root, local_auth=None, workspace_guard=None, analysis_runs=None, market_factory=None, runner_factory=None, trailing_factory=None)`

### Literal payload and lookup fallbacks

- `Host` → `''`
- `ai_review` → `{}`
- `analyzed` → `0`
- `candidates` → `[]`
- `cards` → `[]`
- `error` → `'Workflow failed.'`
- `inventory_only` → `False`
- `investment` → `True`
- `job_id` → `''`
- `limit` → `1`
- `offset` → `0`
- `recommendations` → `[]`
- `results` → `[]`
- `risk_policy` → `{}`
- `rows` → `[]`

## sector_heatmap/kama_strategy.py

[Owning source](../sector_heatmap/kama_strategy.py)

Independent completed-candle KAMA V6 signal engine.

### Callables and explicit defaults

- `kama_exit_state_machine(signal, completed_candle, broker_state='UNKNOWN')`
- `kama_entry_policy_decision(signal, policy, account_position_exists=False)`
- `_in_session(timestamp, session)`
- `kama_series(candles, kama_length=10, fast_length=2, slow_length=30)`
- `kama_v6_signal(candles, position=0, last_long_exit_bar=None, last_short_exit_bar=None, kama_length=10, fast_length=2, slow_length=30, minimum_efficiency=0.35, breakout_bars=5, cooldown_bars=2, allow_reclaims=True, slope_lookback=8, minimum_slope_atr=0.1, entry_session='0915-1510', squareoff_session='1515-1530')`

## sector_heatmap/local_dashboard_auth.py

[Owning source](../sector_heatmap/local_dashboard_auth.py)

Owner sign-in for an existing dashboard; never changes broker or runner state.

### Callables and explicit defaults

- `LocalDashboardAuth.__init__(self, root, port, store=None)`
- `LocalDashboardAuth.configured(cls, root, port)`
- `LocalDashboardAuth.token(self, headers)`
- `LocalDashboardAuth.portal(self, handler, mutation=False)`
- `LocalDashboardAuth.local(self, headers, mutation=False)`
- `LocalDashboardAuth.authorize(self, headers, mutation=False)`
- `LocalDashboardAuth.setup_required(self)`
- `LocalDashboardAuth.json(self, handler, code, value, token=None)`
- `LocalDashboardAuth.get(self, handler)`
- `LocalDashboardAuth.post(self, handler)`
- `LocalDashboardAuth.context(self, headers)`
- `LocalDashboardAuth.check(self, handler, mutation=False)`

### Literal payload and lookup fallbacks

- `Host` → `''`
- `features` → `[]`
- `username` → `''`

## sector_heatmap/market_brief_delivery.py

[Owning source](../sector_heatmap/market_brief_delivery.py)

Durable ordered panel delivery. Unknown sends stop; accepted panels never replay.

### Callables and explicit defaults

- `initialize(box, recover)`
- `deliver_panels(box, channel, config, event, legacy_sender)`

### Literal payload and lookup fallbacks

- `telegram` → `{}`

## sector_heatmap/market_brief_panels.py

[Owning source](../sector_heatmap/market_brief_panels.py)

Ordered, phone-sized market panels. No private report fields are rendered.

### Callables and explicit defaults

- `render_panels(snapshot, target)`

### Literal payload and lookup fallbacks

- `horizons` → `[]`
- `rows` → `[]`

## sector_heatmap/market_brief_visual.py

[Owning source](../sector_heatmap/market_brief_visual.py)

Public market-only executive brief. Strict projections; never render raw reports.

### Callables and explicit defaults

- `numeric(v)`
- `positive(v)`
- `metric(v)`
- `date(v)`
- `status_label(v)`
- `symbol(v)`
- `quality(rows, now)`
- `sector_mtf_public(value, now)`
- `sector_public(snap, history, mtf=None, now=None)`
- `handoff_public(report, now)`
- `public_snapshot(snapshot)`
- `caption(snapshot)`
- `fallback_text(snapshot)`
- `render(snapshot, target)`

### Literal payload and lookup fallbacks

- `15m` → `{}`
- `alignment` → `'UNAVAILABLE'`
- `data_quality` → `''`
- `evidence` → `'INCOMPLETE'`
- `freshness` → `'UNAVAILABLE'`
- `horizons` → `[]`
- `intraday` → `{}`
- `modes` → `{}`
- `recommendations` → `[]`
- `rows` → `[]`
- `sectors` → `[]`
- `strong` → `0`
- `weak` → `0`

## sector_heatmap/market_calendar.py

[Owning source](../sector_heatmap/market_calendar.py)

NSE capital-market trading sessions used to interpret data freshness.

### Callables and explicit defaults

- `_as_ist(moment)`
- `is_trading_day(day)`
- `previous_trading_day(day)`
- `next_trading_day(day)`
- `market_session(moment=None)`
- `trading_elapsed_seconds(start, end)`

## sector_heatmap/market_data.py

[Owning source](../sector_heatmap/market_data.py)

### Callables and explicit defaults

- `is_token_error(message)`
- `provider_tick_timestamp(tick)`
- `tick_timestamp_iso(value)`
- `_percentage_change(ltp, previous)`
- `configure_websocket_ca_bundle()`
- `FyersLiveFeed.__init__(self, access_token, chart_bars=None)`
- `FyersLiveFeed.chart_bars_for(self, symbol)`
- `FyersLiveFeed.start(self)`
- `FyersLiveFeed.stop(self)`
- `FyersLiveFeed.snapshot(self)`

### Literal payload and lookup fallbacks

- `message` → `''`
- `x509_ca` → `0`

## sector_heatmap/market_handoff.py

[Owning source](../sector_heatmap/market_handoff.py)

Broker-backed index/commodity ATM option plans and bounded AI review.

### Callables and explicit defaults

- `native_adapter(base, service)`
- `instrument_kind(meta)`
- `catalog(broker, broker_name, clock=time.time)`
- `indicators(rows, seconds, now)`
- `_wait(read, seconds=8, clock=time.monotonic)`
- `premium_plan(broker, config, direction, clock=time.time)`
- `analyze(payload, broker, ai, broker_name, account_id, clock=time.time)`

### Literal payload and lookup fallbacks

- `matches` → `[]`
- `symbols` → `[]`

## sector_heatmap/master_cache_maintenance.py

[Owning source](../sector_heatmap/master_cache_maintenance.py)

Maintain public FYERS symbol masters without starting or stopping runners.

### Callables and explicit defaults

- `validate(text, segment)`
- `atomic(path, text)`
- `maintain(roots, fetch, now=None)`
- `main()`

### Literal payload and lookup fallbacks

- `segments` → `{}`

## sector_heatmap/motilal_analysis.py

[Owning source](../sector_heatmap/motilal_analysis.py)

Native captured-candle providers for existing Sector Rotation and Handoff.

### Callables and explicit defaults

- `native_liquidity(quote, now)`
- `Provider.__init__(self, execution)`
- `Provider.prepare(self)`
- `Provider.resolve(self, symbol)`
- `Provider.get(self, symbol, timeframe)`
- `Sectors.__init__(self, execution)`
- `Sectors.refresh(self)`
- `Sectors.snapshot(self, mode='intraday', sector_id=None)`
- `Handoff.__init__(self, execution, sectors)`
- `Handoff.candidates(self, mode)`
- `Handoff.positions(self)`
- `Handoff.orders(self)`
- `Handoff.funds(self)`
- `Handoff.quote(self, symbol)`
- `Handoff.tick(self, symbol)`
- `Handoff.chain(self, symbol, direction)`
- `Handoff.options(self, symbol, direction, risk)`

### Literal payload and lookup fallbacks

- `constituent_movers` → `[]`
- `legs` → `[]`
- `proposals` → `[]`
- `sectors` → `[]`

## sector_heatmap/motilal_api.py

[Owning source](../sector_heatmap/motilal_api.py)

Bounded, account-scoped Motilal Oswal Open API transport.

### Callables and explicit defaults

- `MotilalError.__init__(self, message, *, uncertain=False, auth_required=False, code=None)`
- `positive(value, label)`
- `session_deadline(now)`
- `Client.__init__(self, credentials, *, requester=None, live_enabled=False, clock=time.time)`
- `Client.headers(self, *, access_token_call=False)`
- `Client.request(self, operation, payload=None)`
- `Client.profile(self)`
- `Client.quote(self, exchange, token)`

### Literal payload and lookup fallbacks

- `scripcode` → `-1`
- `userid` → `''`

## sector_heatmap/motilal_calendar.py

[Owning source](../sector_heatmap/motilal_calendar.py)

MCX non-agricultural session calendar, independent of any data broker.

### Callables and explicit defaults

- `trading_bounds(now)`

## sector_heatmap/motilal_execution.py

[Owning source](../sector_heatmap/motilal_execution.py)

Account-native reviewed LIMIT tickets. Acceptance is never reported as a fill.

### Callables and explicit defaults

- `Tickets.__init__(self, folder, client, master, feed, account_id, *, clock=time.time)`
- `Tickets.db(self)`
- `Tickets.validate(self, payload)`
- `Tickets.preview(self, user_id, payload)`
- `Tickets.submit(self, user_id, ticket_id, confirmation)`
- `Tickets.reconcile(self, user_id, ticket_id)`
- `Tickets.list(self, user_id)`

### Literal payload and lookup fallbacks

- `clientcode` → `''`
- `clientid` → `''`
- `duration` → `'DAY'`
- `exchanges` → `[]`
- `products` → `[]`
- `usertype` → `''`

## sector_heatmap/motilal_feed.py

[Owning source](../sector_heatmap/motilal_feed.py)

Native MO broadcast packets with independent exchange/receipt freshness.

### Callables and explicit defaults

- `login_packet(client_id)`
- `subscription_packet(exchange, token, subscribe=True)`
- `decode_packet(packet)`
- `QuoteFeed.__init__(self, client, *, clock=time.time, socket_factory=None, on_tick=None, on_disconnect=None)`
- `QuoteFeed._send_subscription(self, socket, generation, exchange, token)`
- `QuoteFeed.subscribe(self, exchange, token)`
- `QuoteFeed.subscribe_index(self, exchange, token)`
- `QuoteFeed.price(self, exchange, token, index=False)`
- `QuoteFeed.ingest(self, message, generation=None)`
- `QuoteFeed._disconnected(self, generation)`
- `QuoteFeed.start(self)`
- `QuoteFeed.quote(self, exchange, token)`
- `QuoteFeed.stop(self)`

## sector_heatmap/motilal_history.py

[Owning source](../sector_heatmap/motilal_history.py)

Reusable captured MO candles. Gaps are retained and never fabricated.

### Callables and explicit defaults

- `History.__init__(self, path, clock=time.time)`
- `History.db(self)`
- `History.invalidate(self)`
- `History._persist(self, symbol, bar)`
- `History._flush_elapsed(self, symbol)`
- `History.ingest(self, tick, coverage_since)`
- `History.candles(self, symbol, minutes=1, limit=500, session_open=None, *, session_minutes=None, session_bounds=None, before=None)`
- `History.save_daily_snapshot(self, symbol, row)`
- `History.daily_snapshots(self, symbol)`
- `History.session_candles(self, symbol, session_open='09:15', minutes=375, limit=3000)`

### Literal payload and lookup fallbacks

- `volume_verified` → `False`

## sector_heatmap/motilal_history_seed.py

[Owning source](../sector_heatmap/motilal_history_seed.py)

Explicit owner-bound FYERS history; never an execution or native capture source.

### Callables and explicit defaults

- `source_settings(payload)`
- `exact_history_symbol(native, rows)`
- `verified_minutes(raw, now, rejected=None)`
- `aggregate(minutes, interval, session_open, now)`
- `Seed.__init__(self, store, user, target, clock=time.time, client_factory=None)`
- `Seed.account_id(self, selected='')`
- `Seed.candles(self, config, native, interval, session_open)`

### Literal payload and lookup fallbacks

- `fyers_history_enabled` → `False`
- `rejected_candles` → `[]`

## sector_heatmap/motilal_login.py

[Owning source](../sector_heatmap/motilal_login.py)

Encrypted, account-bound saved login; OTP stays user-entered, no trading calls.

### Callables and explicit defaults

- `SavedLogin.__init__(self, service)`
- `SavedLogin.cipher(self)`
- `SavedLogin.write(self, path, value)`
- `SavedLogin.read(self, path)`
- `SavedLogin.binding(self)`
- `SavedLogin.status(self, user, token)`
- `SavedLogin.save(self, payload)`
- `SavedLogin.forget(self)`
- `SavedLogin.digest(token)`
- `SavedLogin.client(self, auth='LOGIN')`
- `SavedLogin.request(self, client, operation, payload)`
- `SavedLogin.start(self, user, token, require_otp=False)`
- `SavedLogin.resend(self, user, token)`
- `SavedLogin.verify(self, user, token, otp)`
- `SavedLogin.finish(self, client, auth)`
- `SavedLogin.disconnect_rechallenge(self, user, token)`

### Literal payload and lookup fallbacks

- `at` → `-100000`
- `status` → `''`

## sector_heatmap/motilal_master.py

[Owning source](../sector_heatmap/motilal_master.py)

Last-good account-native MO master data; tokens never cross brokers.

### Callables and explicit defaults

- `contract(row, exchange)`
- `Master.__init__(self, folder, client, clock=time.time)`
- `Master.indices(self, exchange)`
- `Master.rows(self, exchange, refresh=False, *, market_data=False)`
- `Master.exact(self, symbol, *, market_data=False)`
- `Master.search(self, query, exchange)`

### Literal payload and lookup fallbacks

- `observed_at` → `0`

## sector_heatmap/motilal_server.py

[Owning source](../sector_heatmap/motilal_server.py)

Loopback-only, account-owned Motilal dashboard and native order route.

### Callables and explicit defaults

- `handler_factory(guard, service)`
- `main()`

### Literal payload and lookup fallbacks

- `Content-Length` → `'0'`
- `Content-Type` → `''`
- `after` → `[None]`
- `before` → `[None]`
- `broker` → `True`
- `features` → `[]`
- `interval` → `['5']`
- `offset` → `['0']`
- `q` → `['']`
- `segment` → `['']`
- `symbol` → `[None]`

## sector_heatmap/motilal_service.py

[Owning source](../sector_heatmap/motilal_service.py)

Private Motilal account session, native data and reviewed execution service.

### Callables and explicit defaults

- `server_mac(local_ip)`
- `network_identity()`
- `Service.__init__(self, folder, account, *, client_factory=Client, feed_factory=QuoteFeed, clock=time.time, execution_allowed=lambda: True)`
- `Service.credentials(self)`
- `Service.login_start(self, user, session_token)`
- `Service.login_complete(self, user, session_token, auth_token)`
- `Service.install(self, client)`
- `Service.ready(self)`
- `Service.status(self)`
- `Service.eod_snapshot(self, exchange)`
- `Service.quote(self, symbol)`
- `Service.book(self, operation)`

### Literal payload and lookup fallbacks

- `exchanges` → `[]`
- `expires_at` → `0`
- `message` → `''`
- `products` → `[]`
- `session_digest` → `''`

## sector_heatmap/motilal_shared_routes.py

[Owning source](../sector_heatmap/motilal_shared_routes.py)

Owner-bound routes reused by Renko, Screener, Handoff and Sector Rotation.

### Callables and explicit defaults

- `Routes.__init__(self, root, allowed=lambda: True)`
- `Routes.execution(self, store, user, aid)`
- `Routes.sector(self, execution)`
- `Routes.handoff(self, execution)`
- `Routes.renko(self, execution, handler, action, query, payload)`
- `Routes.screener(self, execution, payload)`
- `Routes.screener_options(self, execution, payload)`

### Literal payload and lookup fallbacks

- `proposals` → `[]`
- `score` → `0`
- `sizing` → `{}`
- `symbol` → `''`
- `timeframe_states` → `{}`

## sector_heatmap/motilal_shared_tickets.py

[Owning source](../sector_heatmap/motilal_shared_tickets.py)

Reviewed native tickets from the existing Handoff/Screener controls.

### Callables and explicit defaults

- `Batches.__init__(self, execution, clock=time.time)`
- `Batches.db(self)`
- `Batches.capabilities(self)`
- `Batches.position_slots(self)`
- `Batches.exclude_duplicate(self, symbol)`
- `Batches.booked_loss(self)`
- `Batches.prepare(self, user, payload)`
- `Batches.submit(self, user, payload)`

### Literal payload and lookup fallbacks

- `broker` → `''`
- `cash_product` → `'INTRADAY'`
- `mode` → `'LIVE'`

## sector_heatmap/motilal_strategy_broker.py

[Owning source](../sector_heatmap/motilal_strategy_broker.py)

Native Motilal execution and captured candles for the shared strategy engine.

### Callables and explicit defaults

- `cash_row(row)`
- `normalized(value)`
- `whole(value, label, zero=True)`
- `account_lock(folder)`
- `Broker.__init__(self, service, clock=time.time)`
- `Broker.db(self)`
- `Broker.connected(self)`
- `Broker.live_enabled(self)`
- `Broker.ready(self)`
- `Broker.start(self)`
- `Broker.stop(self)`
- `Broker.stream_status(self)`
- `Broker.underlying(self, symbol)`
- `Broker.search(self, text, market=None)`
- `Broker.subscribe(self, symbol, seconds=None)`
- `Broker.live_price(self, config, now)`
- `Broker.host_tick_size(self, symbol)`
- `Broker.session_policy(self, config)`
- `Broker.candles(self, config)`
- `Broker.forming(self, config, rows, now)`
- `Broker.contract(self, symbol)`
- `Broker.option_rows(self, symbol)`
- `Broker.route_availability(self, config)`
- `Broker.resolve(self, config, direction)`
- `Broker.quote(self, symbol)`
- `Broker.warm_options(self, config)`
- `Broker.validate_config(self, config)`
- `Broker.order(self, symbol, qty, side, quote)`
- `Broker.validate_order(self, order)`
- `Broker.positions(self)`
- `Broker.reconcile_position(self, symbol, qty)`
- `Broker.orders(self)`
- `Broker.funds(self, exchange)`
- `Broker.preflight(self, order, config)`
- `Broker.place(self, order)`
- `Broker.cancel(self, order_id)`

### Literal payload and lookup fallbacks

- `history_start` → `0`
- `totalqtytraded` → `0`
- `usertype` → `''`

## sector_heatmap/motilal_strategy_service.py

[Owning source](../sector_heatmap/motilal_strategy_service.py)

Motilal Renko component inside the existing strategy UI; no separate screen.

### Callables and explicit defaults

- `configure(payload)`
- `MotilalRunner.event(self, code, message)`
- `MotilalRunner.record_order(self, pending, status, filled=0, price=None)`
- `MotilalRunner.save_preferences(self, payload)`
- `MotilalRunner.snapshot(self)`
- `Service.__init__(self, execution, root, instance='default')`
- `Service.history_source(self, payload)`
- `Service.chart_config(self, query)`
- `Service.chart(self, query)`
- `Service.manual_brick(self, query)`
- `Service.get_action(self, handler, action, query)`
- `Service.post_action(self, handler, action, payload)`
- `Registry.__init__(self, execution, root)`
- `Registry.service(self, key)`
- `Registry.dispatch(self, handler, action, query, payload=None)`

### Literal payload and lookup fallbacks

- `cash_product` → `'INTRADAY'`
- `fyers-history-account-id` → `''`
- `fyers-history-enabled` → `False`
- `trade_history` → `[]`
- `underlying` → `''`

## sector_heatmap/multi_account_ticket.py

[Owning source](../sector_heatmap/multi_account_ticket.py)

Owner-bound, amount-sized manual orders across explicitly selected accounts.

### Callables and explicit defaults

- `positive(value)`
- `reserve(preview)`
- `identity(contract)`
- `sized_parser_review(account, payload, amount, call)`
- `sized_review(account, payload, amount, call)`
- `Tickets.__init__(self, path)`
- `Tickets.db(self)`
- `Tickets.get(self, owner, key)`
- `Tickets.history(self, owner)`
- `Tickets.prepare(self, owner, items, resolve, call, feature='handoff')`
- `Tickets.submit(self, owner, key, confirmation, resolve, call)`
- `native_route(account, action, portal_port)`
- `handle(auth, handler, mutation=False)`
- `native_description(service, payload)`

### Literal payload and lookup fallbacks

- `Cookie` → `''`
- `_submit_action` → `'submit-batch'`
- `allocation_mode` → `'EQUAL_ALLOCATED_FUNDS'`
- `daily_loss_limit` → `5000`
- `error` → `'Native account validation failed.'`
- `feature` → `'handoff'`
- `idea_risk_limit` → `2000`
- `mode` → `'LIVE'`
- `order_type` → `'LIMIT'`
- `risk_reserve` → `1000`
- `submit_action` → `''`
- `submit_action` → `'submit-batch'`

## sector_heatmap/native_holdings.py

[Owning source](../sector_heatmap/native_holdings.py)

Read-only Dhan and Motilal holdings; native identities and data never cross brokers.

### Callables and explicit defaults

- `quote_time(value)`
- `complete_cash_session(rows, session)`
- `DhanHoldings.__init__(self, execution)`
- `DhanHoldings.inventory(self)`
- `DhanHoldings.enrich(self, rows)`
- `DhanHoldings.candles(self, row, now)`
- `MotilalHoldings.__init__(self, execution)`
- `MotilalHoldings.inventory(self)`
- `MotilalHoldings.enrich(self, rows)`
- `MotilalHoldings.candles(self, row, now)`

### Literal payload and lookup fallbacks

- `SEM_EXM_EXCH_ID` → `''`

## sector_heatmap/ncdex_calendar.py

[Owning source](../sector_heatmap/ncdex_calendar.py)

NCDEX trading sessions in minutes from midnight Asia/Kolkata.

### Callables and explicit defaults

- `trading_bounds(timestamp, underlying)`

## sector_heatmap/network_policy.py

[Owning source](../sector_heatmap/network_policy.py)

Process-wide IPv4-only DNS policy for broker HTTP and WebSocket clients.

### Callables and explicit defaults

- `install_ipv4_only()`

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
- `NiftyStraddleService.stop(self, expected_started_at=None)`

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

## sector_heatmap/notification_admin.py

[Owning source](../sector_heatmap/notification_admin.py)

Small authenticated User Master notification API; no dashboard/runner lifecycle.

### Callables and explicit defaults

- `handler_factory(store, port=8090, runtime=None, reports=None)`
- `main()`

### Literal payload and lookup fallbacks

- `Content-Length` → `'0'`
- `Content-Type` → `''`

## sector_heatmap/notification_controls.py

[Owning source](../sector_heatmap/notification_controls.py)

Owner-only notification preferences and Telegram controls. Never changes trading.

### Callables and explicit defaults

- `preferences(path=None)`
- `set_paused(scope, channel, paused, path=None, clock=time.time)`
- `gate(channel, event, created, path=None)`
- `menu(data=None)`
- `owner_update(update, chat_id)`
- `api(config, method, body)`
- `handle_update(update, config, request=api, path=None, minimum_date=0)`
- `main()`

### Literal payload and lookup fallbacks

- `data` → `''`
- `date` → `0`
- `paused` → `False`
- `resumed_at` → `0`
- `text` → `''`

## sector_heatmap/notification_destinations.py

[Owning source](../sector_heatmap/notification_destinations.py)

Separate personal executions from shared market reports.

### Callables and explicit defaults

- `telegram_destination(config, event, created)`

### Literal payload and lookup fallbacks

- `combined_reports` → `{}`

## sector_heatmap/notification_recipients.py

[Owning source](../sector_heatmap/notification_recipients.py)

Validated per-user email destinations; never changes sender authorization.

### Callables and explicit defaults

- `validate_email(value, allow_empty=False)`
- `recipient(config, root=ROOT)`
- `subscribers(config, root=ROOT)`
- `notification_accounts(config, root=ROOT)`
- `publisher_configs(config, root=ROOT)`

### Literal payload and lookup fallbacks

- `owner_username` → `''`

## sector_heatmap/notification_sessions.py

[Owning source](../sector_heatmap/notification_sessions.py)

Telegram market updates require an open, identified exchange session.

### Callables and explicit defaults

- `segments(event)`
- `gate(event, created, now=None)`

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

## sector_heatmap/persistent_jobs.py

[Owning source](../sector_heatmap/persistent_jobs.py)

Account-owned durable work; never replay interrupted execution on startup.

### Callables and explicit defaults

- `checkpoint(message=None, output=None)`
- `JobContext.__init__(self, store, owner, job_id)`
- `JobContext.cancelled(self)`
- `JobContext.checkpoint(self, message=None, output=None)`
- `JobStore.__init__(self, path, workers=3, capacity=12, clock=time.time)`
- `JobStore.db(self)`
- `JobStore._decode(self, row)`
- `JobStore.get(self, owner, job_id)`
- `JobStore.list(self, owner, limit=100)`
- `JobStore.page(self, owner, before=None, limit=25)`
- `JobStore._update(self, job_id, status=None, message=None, output=None, error=None)`
- `JobStore.submit(self, owner, kind, feature, label, request, work, request_key, stop=None)`
- `JobStore._run(self, owner, job_id, work)`
- `JobStore.cancel(self, owner, job_id)`
- `JobStore.close(self, wait=True)`

### Literal payload and lookup fallbacks

- `path` → `''`
- `payload` → `{}`
- `sleep_until` → `0`

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

## sector_heatmap/premium_exit_mapping.py

[Owning source](../sector_heatmap/premium_exit_mapping.py)

Instantaneous constant-IV premium scenarios; no predicted fill or time horizon.

### Callables and explicit defaults

- `premium_exits(*, spot, stop, target, premium, strike, expiry, option_type, tick, now)`
- `cash_exits(*, entry, stop, target, action, tick)`
- `premium_stop_from_greeks(*, spot, stop, premium, strike, expiry, option_type, tick, greeks, now, level_kind='STOP')`
- `premium_target_from_greeks(*, target, **kwargs)`

## sector_heatmap/recommendation_text.py

[Owning source](../sector_heatmap/recommendation_text.py)

Broker-independent recommendation extraction; no execution.

### Callables and explicit defaults

- `parse_text(text)`

## sector_heatmap/report_delivery.py

[Owning source](../sector_heatmap/report_delivery.py)

Owner-bound controls for shared Telegram analysis reports. No trading imports.

### Callables and explicit defaults

- `ReportDelivery.__init__(self, root, store, service=None, clock=time.time)`
- `ReportDelivery._service(self, action)`
- `ReportDelivery._config(self)`
- `ReportDelivery.authorize(self, user, section, config)`
- `ReportDelivery.status(self, user, section)`
- `ReportDelivery.configure(self, user, payload)`

### Literal payload and lookup fallbacks

- `all` → `{}`
- `combined` → `{}`
- `combined_reports` → `{}`
- `features` → `[]`
- `refresh_interval_ms` → `900000`
- `telegram` → `{}`
- `title` → `'Shared analysis channel'`

## sector_heatmap/report_wait.py

[Owning source](../sector_heatmap/report_wait.py)

Wait for a read-only report worker without abandoning it on elapsed time.

### Callables and explicit defaults

- `wait_for_report(process, progress, interval=15, notify_after=60, notify_every=300, clock=time.monotonic)`

## sector_heatmap/resource_monitor.py

[Owning source](../sector_heatmap/resource_monitor.py)

Read-only Linux telemetry. No broker requests, credentials, or process arguments.

### Callables and explicit defaults

- `command(args)`
- `parse_sar(text, kind)`
- `history()`
- `cpu_sample()`
- `cpu_delta(first, last)`
- `snapshot()`

### Literal payload and lookup fallbacks

- `Cached` → `0`
- `SwapFree` → `0`
- `SwapTotal` → `0`

## sector_heatmap/restart_state_read.py

[Owning source](../sector_heatmap/restart_state_read.py)

Bounded, read-only validation of canonical restart state; no recovery writes.

### Callables and explicit defaults

- `_pairs(pairs)`
- `_large_schema(value)`
- `read_runtime_state(path, source)`

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

## sector_heatmap/runner_job_audit.py

[Owning source](../sector_heatmap/runner_job_audit.py)

Durable, run-bound reporting from execution evidence; never creates a fill.

### Callables and explicit defaults

- `timestamp(value)`
- `identity(state)`
- `audit(snapshot, previous=None, observed_at=None)`
- `attach(snapshot, previous=None, observed_at=None)`

### Literal payload and lookup fallbacks

- `events` → `[]`
- `job_audits` → `[]`
- `orders` → `[]`
- `trades` → `[]`

## sector_heatmap/runner_job_history.py

[Owning source](../sector_heatmap/runner_job_history.py)

Per-submission history beside the owned runner state; never authorizes execution.

### Callables and explicit defaults

- `record(state_path, state)`
- `read(state_path)`
- `record_legacy(state_path, state)`

## sector_heatmap/screener_auto.py

[Owning source](../sector_heatmap/screener_auto.py)

Screener-only execution scope; no order or activation authority.

### Callables and explicit defaults

- `eligible_rows(rows, report)`

### Literal payload and lookup fallbacks

- `analysis_scopes` → `[]`
- `provenance` → `[]`
- `scope` → `{}`
- `screener` → `{}`

## sector_heatmap/screener_paging.py

[Owning source](../sector_heatmap/screener_paging.py)

Validated paging for advisory scans; never silently drops requested symbols.

### Callables and explicit defaults

- `page_request(payload)`

## sector_heatmap/screener_routes.py

[Owning source](../sector_heatmap/screener_routes.py)

Three execution choices for verified screener underlyings; advisory only.

### Callables and explicit defaults

- `join_unique_reasons(items)`
- `option_underlyings(content, now=None)`
- `analyze(candidates, client, master, fetch_chain, risk)`
- `budget_slices(items, budget)`

### Literal payload and lookup fallbacks

- `allocation_weight` → `1`
- `data` → `{}`
- `optionsChain` → `[]`
- `score` → `0`

## sector_heatmap/seasonality.py

[Owning source](../sector_heatmap/seasonality.py)

Read-only seasonal price returns. No portfolio P&L or execution authority.

### Callables and explicit defaults

- `symbol_options(payload)`
- `period_key(day, mode)`
- `next_key(key, mode)`
- `calculate(candles, as_of, timezone='Asia/Kolkata')`
- `fetch_public(root, payload, now=None)`

### Literal payload and lookup fallbacks

- `chart` → `{}`
- `exchangeTimezoneName` → `'Asia/Kolkata'`
- `fetched_at` → `0`
- `meta` → `{}`
- `symbol` → `''`
- `timestamp` → `[]`

## sector_heatmap/section_permissions.py

[Owning source](../sector_heatmap/section_permissions.py)

Admin-assigned dashboard sections, enforced before account API dispatch.

### Callables and explicit defaults

- `allowed(user, path)`

### Literal payload and lookup fallbacks

- `features` → `[]`

## sector_heatmap/sector_cards.py

[Owning source](../sector_heatmap/sector_cards.py)

Scheduled sector cards from the owner's persisted dashboard analysis; read-only source.

### Callables and explicit defaults

- `parse_time(value)`
- `schedule_slot(now)`
- `history_path(config, root=ROOT)`
- `snapshot_from_history(history, now, mode='intraday', initial=False)`
- `render_card(snapshot, target)`
- `media_bytes(event)`
- `caption(event)`
- `email_message(config, event, data)`
- `send_card(channel, config, event, audit=None)`
- `SectorOutbox.__init__(self, *args, **kwargs)`
- `SectorOutbox.settle(self)`
- `SectorOutbox.enqueue(self, config, now, initial=False)`
- `main()`

### Literal payload and lookup fallbacks

- `direction` → `''`
- `enabled` → `False`
- `modes` → `{}`
- `rows` → `[]`
- `sector_cards` → `{}`

## sector_heatmap/sector_detail_bridge.py

[Owning source](../sector_heatmap/sector_detail_bridge.py)

Authenticated read-only sector-detail compatibility bridge.

### Callables and explicit defaults

- `NoRedirect.redirect_request(self, *args, **kwargs)`
- `_authorized(store, user, account_id, token)`
- `_get(account, token, path)`
- `chart_series(candles, asof)`
- `completed_series(payload)`
- `details(root, store, user, account_id, token, sector_id, mode='intraday')`
- `main()`

### Literal payload and lookup fallbacks

- `daily` → `[]`
- `features` → `[]`
- `sectors` → `[]`
- `timeframe_states` → `{}`

## sector_heatmap/sector_service.py

[Owning source](../sector_heatmap/sector_service.py)

FYERS-backed candle caching and bounded sector rotation snapshot service.

### Callables and explicit defaults

- `completed_weekly(candles, current)`
- `rank_directional_drivers(drivers, direction)`
- `CandleHistoryProvider.__init__(self, client, now=None)`
- `CandleHistoryProvider.get(self, symbol, timeframe)`
- `CandleHistoryProvider.participation_daily(self, symbol)`
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
- `daily` → `[]`
- `drivers` → `[]`
- `phase` → `'CONNECTING'`
- `refresh_state` → `{}`
- `sectors` → `[]`
- `timeframe_states` → `{}`
- `volume` → `0`

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
- `SensexStraddleService._job_history(self)`
- `SensexStraddleService.snapshot(self)`
- `SensexStraddleService._capture_output(self, process)`
- `SensexStraddleService.start(self, mode='live', exit_mode='supertrend', lots=1, entry_start='09:15', entry_end='11:30', confirmation='', paper_capital_inr=100000)`
- `SensexStraddleService.start_paper(self)`
- `SensexStraddleService.snapshot_unlocked(self, message=None)`
- `SensexStraddleService.stop(self, expected_started_at=None)`

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

## sector_heatmap/service_restart.py

[Owning source](../sector_heatmap/service_restart.py)

Durable, administrator-only dashboard restart; never starts a strategy.

### Callables and explicit defaults

- `_path(store)`
- `_admin(user)`
- `_service()`
- `status(store, user)`
- `runtime_states(source)`
- `stopped_state_paths(source)`
- `stopped_runtime(source)`
- `begin(store, runtime, user, request_id)`

### Literal payload and lookup fallbacks

- `MainPID` → `'0'`

## sector_heatmap/stock_expiry_policy.py

[Owning source](../sector_heatmap/stock_expiry_policy.py)

New stock-option entries are equity-only on near-month expiry and prior day.

### Callables and explicit defaults

- `stock_symbol(symbol)`
- `expiry_day(value)`
- `require_options_allowed(expiries, now=None)`
- `guard_fyers_rows(rows, ticker, now)`

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

## sector_heatmap/telegram_execution.py

[Owning source](../sector_heatmap/telegram_execution.py)

One account-bound Paper/Live execution controller for fresh Telegram recommendations.

### Callables and explicit defaults

- `ExecutionPipeline.__init__(self, tickets, polling, path, clock=time.time, feed=None, guard=None)`
- `ExecutionPipeline.signature(settings)`
- `ExecutionPipeline.validate(settings)`
- `ExecutionPipeline.save(self)`
- `ExecutionPipeline.status(self)`
- `ExecutionPipeline.require_owner(self)`
- `ExecutionPipeline.check_revision(self, p)`
- `ExecutionPipeline.proposed(self, p)`
- `ExecutionPipeline.configure(self, p)`
- `ExecutionPipeline.start(self, p)`
- `ExecutionPipeline.stop(self, reason='USER_STOP', message='New recommendation entries stopped; reception and owned Renko exits continue.')`
- `ExecutionPipeline.fresh_row(self, row)`
- `ExecutionPipeline.reject_override(self, p, cfg)`
- `ExecutionPipeline.preview(self, p)`
- `ExecutionPipeline.claim(self, key, text, revision, cfg, stamp)`
- `ExecutionPipeline.submit_ticket(self, ticket, cfg)`
- `ExecutionPipeline.finish(self, record, ticket, cfg)`
- `ExecutionPipeline.submit_manual(self, p)`
- `ExecutionPipeline.step(self)`
- `ExecutionPipeline.run(self, event)`
- `action_routes(execution, parser, polling, connect, disconnect, retired, verify)`

### Literal payload and lookup fallbacks

- `execution` → `{}`
- `status` → `'RESPONSE_RECEIVED'`
- `text` → `''`

## sector_heatmap/telegram_lifecycle.py

[Owning source](../sector_heatmap/telegram_lifecycle.py)

Private, bounded transport/pipeline lifecycle evidence. No credentials or posts.

### Callables and explicit defaults

- `synchronized(method)`
- `Lifecycle.__init__(self, path, clock=time.time)`
- `Lifecycle.save(self)`
- `Lifecycle.record(self, state, reason, message)`
- `Lifecycle.heartbeat(self)`
- `Lifecycle.status(self)`

### Literal payload and lookup fallbacks

- `events` → `[]`

## sector_heatmap/telegram_managed.py

[Owning source](../sector_heatmap/telegram_managed.py)

New Telegram recommendations -> trigger watch -> owned Renko option entry.

### Callables and explicit defaults

- `OptionTickets.__init__(self, delta, parse, runner_factory, template, clock=time.time, polling=None)`
- `OptionTickets.preview(self, p)`
- `OptionTickets.submit(self, p)`

## sector_heatmap/telegram_migration.py

[Owning source](../sector_heatmap/telegram_migration.py)

Owner-verified legacy subscriber restoration; never starts a reader or runner.

### Callables and explicit defaults

- `private_write(path, value)`
- `migration_plan(root, username, account_id)`
- `restore(plan, legacy_stopped=False, client_factory=None)`

### Literal payload and lookup fallbacks

- `telegram` → `{}`

## sector_heatmap/telegram_options.py

[Owning source](../sector_heatmap/telegram_options.py)

Telegram underlying recommendations → long ATM-option plans, never orders.

### Callables and explicit defaults

- `recommendation_plan(parsed, underlying)`
- `trigger_satisfied(plan, price, exchange_at, now)`
- `resolve_at_trigger(delta, plan, price, exchange_at, now)`

## sector_heatmap/telegram_paper.py

[Owning source](../sector_heatmap/telegram_paper.py)

Explicitly armed, new-post-only PAPER option pipeline; inert after restart.

### Callables and explicit defaults

- `PaperPipeline.__init__(self, tickets, polling, path, clock=time.time, feed=None)`
- `PaperPipeline.save(self)`
- `PaperPipeline.status(self)`
- `PaperPipeline.configure(self, p)`
- `PaperPipeline.start(self, p)`
- `PaperPipeline._start(self, p)`
- `PaperPipeline.stop(self, reason='USER_STOP', message='New Paper entries stopped explicitly; owned position exits remain managed by their Renko owner.')`
- `PaperPipeline.run(self, event)`
- `PaperPipeline.step(self)`

### Literal payload and lookup fallbacks

- `gold_proxy` → `False`
- `options` → `{}`
- `recommendations` → `{}`

## sector_heatmap/telegram_parser.py

[Owning source](../sector_heatmap/telegram_parser.py)

Separate broker-selected recommendation tickets; execution only on explicit submit.

### Callables and explicit defaults

- `TelegramParser.__init__(self, parse, fyers_preview, fyers_submit, delta, guard, polling, clock=time.time)`
- `TelegramParser.parse(self, p)`
- `TelegramParser.submit(self, p, automatic=False)`
- `TelegramParser.auto(self, row, execution)`
- `TelegramParser.reconcile(self, p)`

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
- `TelegramPolling._start(self, p=None)`
- `TelegramPolling.loop(self)`
- `TelegramPolling.stop(self)`

### Literal payload and lookup fallbacks

- `auto` → `False`
- `broker` → `'DELTA_INDIA'`
- `channel` → `''`
- `interval` → `30`
- `quantity` → `1`

## sector_heatmap/telegram_subscriber.py

[Owning source](../sector_heatmap/telegram_subscriber.py)

Receive-only selected-channel MTProto transport. No sending or broker callbacks.

### Callables and explicit defaults

- `TelegramSubscriber.__init__(self, path, clock=None, client_factory=None)`
- `TelegramSubscriber.running(self)`
- `TelegramSubscriber.status(self)`
- `TelegramSubscriber.dependency(self)`
- `TelegramSubscriber.configure(self, p)`
- `TelegramSubscriber._worker(self, ready)`
- `TelegramSubscriber.call(self, coro)`
- `TelegramSubscriber.connect(self)`
- `TelegramSubscriber.authenticate(self, p)`
- `TelegramSubscriber.login(self, p)`
- `TelegramSubscriber.verify_async(self)`
- `TelegramSubscriber.verify(self)`
- `TelegramSubscriber.ingest_message(self, message, edited=False, missed=False)`
- `TelegramSubscriber._ingest_message(self, message, edited=False, missed=False)`
- `TelegramSubscriber.on_message(self, event)`
- `TelegramSubscriber.on_edit(self, event)`
- `TelegramSubscriber.reconcile_loop(self)`
- `TelegramSubscriber.start_async(self, p)`
- `TelegramSubscriber._start_async(self, p)`
- `TelegramSubscriber.start(self, p=None)`
- `TelegramSubscriber.stop(self)`
- `TelegramSubscriber.disconnect_async(self)`
- `TelegramSubscriber.disconnect(self, p=None)`
- `TelegramConnections.__init__(self, path)`
- `TelegramConnections.save_route(self)`
- `TelegramConnections.active(self)`
- `TelegramConnections.status(self)`
- `TelegramConnections.configure(self, p)`
- `TelegramConnections.select(self, p)`
- `TelegramConnections.start(self, p=None)`
- `TelegramConnections.stop(self)`
- `TelegramConnections.__getattr__(self, name)`

### Literal payload and lookup fallbacks

- `route` → `'BOT'`

## sector_heatmap/telegram_trade_format.py

[Owning source](../sector_heatmap/telegram_trade_format.py)

Readable Telegram HTML for private trade updates; no transport or brokers.

### Callables and explicit defaults

- `units(text)`
- `numeric(value, places=2, signed=False)`
- `money(value, currency='INR', signed=False)`
- `stamp(value)`
- `line(label, value)`
- `text_lines(text)`
- `parts(event)`

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

## sector_heatmap/trade_notifications.py

[Owning source](../sector_heatmap/trade_notifications.py)

Read-only fill observer and durable outbound notifications. Never imports brokers.

### Callables and explicit defaults

- `number(v)`
- `identity(account, row)`
- `ledger_rows(data, filename)`
- `sources(root, accounts)`
- `paper_journal_rows(records, filename)`
- `pnl_for(row, rows, quantity, price)`
- `render(event)`
- `Outbox.__init__(self, path, clock=time.time, recover=True)`
- `Outbox.ingest(self, account, rows, config, baseline=False)`
- `Outbox.ingest_summaries(self, account, summaries, config, baseline=False)`
- `Outbox.scan(self, root, config, baseline=False)`
- `Outbox.test_event(self)`
- `Outbox.route_emails(self, config, only_event=None)`
- `Outbox.deliver_telegram(self, config, event, sender)`
- `Outbox.deliver(self, config, sender=None, only_event=None)`
- `Outbox.status(self)`
- `send(channel, config, event)`
- `main()`

### Literal payload and lookup fallbacks

- `exit_fills` → `[]`
- `filled` → `0`
- `order_history` → `[]`
- `orders` → `{}`
- `pnl` → `'Unavailable'`
- `position_summaries` → `[]`
- `reduce_only` → `False`
- `side` → `''`
- `side` → `1`
- `trades` → `[]`

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
- `select_ema_atm_option(rows, underlying, direction, spot, now_epoch, *, stock_equity=False)`
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
- `broker` → `''`
- `buy_qty` → `0`
- `buy_rate` → `0`
- `candidates` → `[]`
- `candles` → `[]`
- `config` → `{}`
- `confirmation` → `''`
- `data` → `{}`
- `drivers` → `[]`
- `entry_end` → `'11:30'`
- `entry_start` → `'09:15'`
- `exclusions` → `[]`
- `exit_mode` → `'supertrend'`
- `features` → `[]`
- `filledQty` → `0`
- `id` → `''`
- `idea_risk_limit` → `2000`
- `kill_switch_engaged` → `False`
- `legs` → `[]`
- `lots` → `1`
- `method` → `'structure'`
- `mode` → `'PAPER'`
- `mode` → `'live'`
- `netPositions` → `[]`
- `netQty` → `0`
- `net_qty` → `0`
- `offset` → `['0']`
- `optionsChain` → `[]`
- `ord_status` → `0`
- `orderBook` → `[]`
- `orders` → `{}`
- `paper_capital_inr` → `100000`
- `period` → `'daily'`
- `pl` → `0`
- `positions` → `[]`
- `preview_id` → `''`
- `q` → `['']`
- `qty` → `0`
- `reconciliation` → `'NOT_APPLICABLE'`
- `resistance_volume_exit` → `False`
- `results` → `[]`
- `retry_at` → `0`
- `retry_attempts` → `0`
- `rows` → `[]`
- `runner` → `{}`
- `score` → `0`
- `screener` → `{}`
- `sectors` → `[]`
- `segment` → `''`
- `segment` → `['']`
- `segment_name` → `'—'`
- `sell_qty` → `0`
- `sell_rate` → `0`
- `side` → `0`
- `source_failures` → `[]`
- `stoploss` → `15`
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

## sector_heatmap/workspace_bounce.py

[Owning source](../sector_heatmap/workspace_bounce.py)

Admin-only account dashboard bounce, without provisioning or arming runners.

### Callables and explicit defaults

- `stopped_states(source)`
- `reload_states(source, broker)`
- `_account(store, user, aid)`
- `status(store, user, aid)`
- `begin(store, runtime, user, aid)`
- `_bounce(store, runtime, account, pid, initial)`
- `main()`

### Literal payload and lookup fallbacks

- `orderstatus` → `''`
- `updated_at` → `0`

## sector_heatmap/workspace_disconnect.py

[Owning source](../sector_heatmap/workspace_disconnect.py)

Stop an idle Motilal connection service only after verified account exposure.

### Callables and explicit defaults

- `idle_states(source)`
- `check_flat(service, folder)`
- `stop_connection(runtime, account)`
- `stop_for_disconnect(runtime, account)`

## sector_heatmap/workspace_guard.py

[Owning source](../sector_heatmap/workspace_guard.py)

Authenticate every request made to an isolated account dashboard.

### Callables and explicit defaults

- `WorkspaceGuard.__init__(self, store, account_id, port, portal_port)`
- `WorkspaceGuard.from_environment(cls)`
- `WorkspaceGuard.authorize(self, headers, mutation=False)`
- `WorkspaceGuard.validate_account_binding(self, account, path, payload=None)`
- `WorkspaceGuard.validate_action(self, account, path, payload)`
- `WorkspaceGuard.context(self, user, account)`
- `WorkspaceGuard.check(self, handler, mutation=False)`

### Literal payload and lookup fallbacks

- `account_id` → `[]`
- `broker` → `'MOTILAL_OSWAL'`
- `features` → `[]`

## sector_heatmap/workspace_portal.py

[Owning source](../sector_heatmap/workspace_portal.py)

Authenticated localhost setup portal for separate users and broker accounts.

### Callables and explicit defaults

- `handler_factory(store, runtime, port)`
- `main()`

### Literal payload and lookup fallbacks

- `Content-Length` → `'0'`
- `Content-Type` → `''`
- `FYERS_REDIRECT_URI` → `''`
- `MO_PUBLIC_IP` → `''`
- `account_ref` → `''`
- `label` → `''`
- `live_enabled` → `False`
- `username` → `''`

## sector_heatmap/workspace_proxy.py

[Owning source](../sector_heatmap/workspace_proxy.py)

Same-origin transport to an authenticated user's loopback-only workspace.

### Callables and explicit defaults

- `bootstrap(prefix)`
- `proxy(auth, handler, mutation=False)`

### Literal payload and lookup fallbacks

- `Accept-Encoding` → `''`
- `Content-Length` → `'0'`

## sector_heatmap/workspace_supervisor.py

[Owning source](../sector_heatmap/workspace_supervisor.py)

External Delta dashboard liveness supervisor. Never arms runners or sends orders.

### Callables and explicit defaults

- `decide(*, enabled, disconnected, owner_alive, port_busy, maintenance, attempts, now, next_attempt)`
- `Supervisor.__init__(self, registry, root, account_id, portal_port=8080, clock=time.time)`
- `Supervisor.emit(self, value, event=False)`
- `Supervisor.tick(self)`
- `main()`

### Literal payload and lookup fallbacks

- `attempts` → `[]`
- `next_attempt` → `0`
- `updated_at` → `0`

## sector_heatmap/workspaces.py

[Owning source](../sector_heatmap/workspaces.py)

Local user registry and isolated broker workspaces. Never starts a strategy.

### Callables and explicit defaults

- `password_hash(password, salt)`
- `private_write(path, content)`
- `WorkspaceStore.__init__(self, path, clock=time.time)`
- `WorkspaceStore._scope_account_uniqueness(self)`
- `WorkspaceStore.sidebar_visibility(self)`
- `WorkspaceStore.set_sidebar_visibility(self, actor, settings)`
- `WorkspaceStore.renko_visibility(self)`
- `WorkspaceStore.set_renko_visibility(self, actor, settings)`
- `WorkspaceStore.db(self)`
- `WorkspaceStore.create_user(self, username, password, actor=None, bootstrap=False)`
- `WorkspaceStore.login(self, username, password)`
- `WorkspaceStore.session(self, token)`
- `WorkspaceStore.renew_session(self, token)`
- `WorkspaceStore.logout(self, token)`
- `WorkspaceStore.change_password(self, user, current_password, new_password)`
- `WorkspaceStore.users(self, actor)`
- `WorkspaceStore.set_notification_email(self, actor, username, email, enabled=False)`
- `WorkspaceStore.set_features(self, actor, username, features)`
- `WorkspaceStore.accounts(self, user)`
- `WorkspaceStore.account(self, user, account_id)`
- `WorkspaceStore.rename_account(self, user, aid, label)`
- `WorkspaceStore.create_account(self, user, broker, label, account_ref)`
- `WorkspaceStore.folder(self, account)`
- `WorkspaceStore.configure(self, user, aid, fields, live_enabled=False)`
- `cookie_token(headers)`
- `isolated_environment(account, folder, registry, portal_port)`
- `WorkspaceRuntime.__init__(self, store, source, portal_port=8079)`
- `WorkspaceRuntime.running(self, aid)`
- `WorkspaceRuntime.configure(self, user, aid, fields, live_enabled)`
- `WorkspaceRuntime.disconnect(self, user, aid)`
- `WorkspaceRuntime.delete(self, user, aid, confirmation)`
- `WorkspaceRuntime.reconnect(self, user, aid)`
- `WorkspaceRuntime.provision(self, account)`
- `WorkspaceRuntime.start(self, user, aid)`

### Literal payload and lookup fallbacks

- `Cookie` → `''`
- `user_id` → `''`

## sector_heatmap/yahoo_chart.py

[Owning source](../sector_heatmap/yahoo_chart.py)

Yahoo Finance historical OHLC for the analytical chart.

### Callables and explicit defaults

- `regular_sessions(periods)`
- `aggregate_regular_sessions(rows, periods, minutes, native_seconds, now)`
- `aggregate_calendar(rows, interval, exchange_timezone, now, crypto, regular_close=None)`
- `history(symbol, interval, now=None, *, before=None)`
- `search_symbols(query)`
- `serve(handler, auth)`

### Literal payload and lookup fallbacks

- `before` → `[]`
- `description` → `''`
- `meta` → `{}`
- `quotes` → `[]`

### Configuration literals

- `INTERVALS = {'1': ('1m', '5d', 60), '2': ('2m', '1mo', 120), '5': ('5m', '1mo', 300), '15': ('15m', '1mo', 900), '30': ('30m', '1mo', 1800), '60': ('60m', '1mo', 3600), '1D': ('1d', '5y', 86400), '1W': ('1wk', '5y', 604800), '1M': ('1mo', '5y', None)}`

## sector_heatmap/yahoo_snapshot.py

[Owning source](../sector_heatmap/yahoo_snapshot.py)

Provider-stamped, provisional calendar snapshots; never completed history.

### Callables and explicit defaults

- `calendar_snapshot(timestamps, values, interval, source_interval, metadata, now, *, before=None)`

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

## sitecustomize.py

[Owning source](../sitecustomize.py)

Apply the trading application's IPv4 policy in standalone child runners.

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

### Callables and explicit defaults

- `_master_signature(stat)`
- `_shared_fyers_master_rows(path, signature)`
- `IndependentDataSocket.__new__(cls, *args, **kwargs)`
- `IndependentDataSocket._FyersDataSocket__symbol_conversion(self, symbols)`
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

## strategies/ema_crossover/external_close.py

[Owning source](../strategies/ema_crossover/external_close.py)

Read-only evidence check for a broker-flat, externally closed FYERS position.

### Callables and explicit defaults

- `confirmed_close(position, positions, orders)`

### Literal payload and lookup fallbacks

- `entry_side` → `1`
- `filledQty` → `0`
- `netQty` → `0`
- `qty` → `0`
- `side` → `0`
- `status` → `0`
- `tradedPrice` → `0`

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
- `Runner.valuation_quote(self, symbol)`
- `Runner.snapshot(self)`
- `Runner.preview(self, payload)`
- `Runner.start(self, payload, background=True)`
- `Runner.release(self)`
- `Runner.request_stop(self, payload=None)`
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
- `Runner.reconcile_external_stop(self)`
- `Runner.reconcile(self)`
- `Runner.step(self)`

### Literal payload and lookup fallbacks

- `broker` → `'FYERS'`
- `count_on_fill` → `False`
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

## strategies/ema_crossover/spread_policy.py

[Owning source](../strategies/ema_crossover/spread_policy.py)

Optional percentage spread gate; quote validity remains mandatory.

### Callables and explicit defaults

- `enabled(config)`

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

## strategies/nifty_ai_options/__init__.py

[Owning source](../strategies/nifty_ai_options/__init__.py)

Standalone Nifty AI Renko options strategy.

## strategies/nifty_ai_options/audit_recorded_data.py

[Owning source](../strategies/nifty_ai_options/audit_recorded_data.py)

Audit preserved raw data offline. No FYERS/network calls.

## strategies/nifty_ai_options/chart_source.py

[Owning source](../strategies/nifty_ai_options/chart_source.py)

Durable exact close series consumed by one AI runtime; no broker requests.

### Callables and explicit defaults

- `series_key(symbol, frame)`
- `ChartSource.__init__(self, directory)`
- `ChartSource.path(self, symbol, frame)`
- `ChartSource.persist(self, path, value)`
- `ChartSource.seed(self, symbol, frame, rows, brick)`
- `ChartSource.append(self, event, frame)`
- `read_source(data, owner, run_id, symbol, frame, *, after=None)`

### Literal payload and lookup fallbacks

- `_verification_only` → `False`

## strategies/nifty_ai_options/compare_native_parents.py

[Owning source](../strategies/nifty_ai_options/compare_native_parents.py)

Offline exact-parent input comparison; never writes a usable sizing reference.

### Callables and explicit defaults

- `compare(source, tv)`

## strategies/nifty_ai_options/confirmed_close.py

[Owning source](../strategies/nifty_ai_options/confirmed_close.py)

Provider-history confirmation for close-source decisions; GETs only.

### Callables and explicit defaults

- `fyers_reader(api)`
- `delta_reader(delta)`
- `ConfirmedClose.__init__(self, reader, directory)`
- `ConfirmedClose.confirm(self, event, symbol, frame, now=None, *, previous=None, continuous=True, opening_minutes=None)`

### Literal payload and lookup fallbacks

- `candles` → `[]`

## strategies/nifty_ai_options/core.py

[Owning source](../strategies/nifty_ai_options/core.py)

Deterministic strategy core; no broker imports or inherited entry filters.

### Callables and explicit defaults

- `positive(value, name)`
- `sizes(reference, delta, market='NSE', asset=None)`
- `select_contract(rows, side, expiry, target=40)`
- `SMAExit.__init__(self)`
- `SMAExit.update(self, timestamp, close)`
- `Strategy.__init__(self, config)`
- `Strategy.indicator(self, size)`
- `Strategy.reset_contract(self, contract, delta)`
- `Strategy.update(self, event)`
- `Strategy.selected_gate_entry(self)`
- `Strategy.exit(self, at, reason)`

### Literal payload and lookup fallbacks

- `entry_gate` → `'underlying_flip_premium_bullish'`
- `exit_supertrend` → `'premium'`
- `indicator_brick_mode` → `'Manual'`
- `market` → `'NSE'`
- `premium` → `-1`
- `sma_exit_enabled` → `False`
- `timeframe` → `1`

## strategies/nifty_ai_options/delta_adapter.py

[Owning source](../strategies/nifty_ai_options/delta_adapter.py)

Exact-owner Delta adapter; construction is inert except its isolated cache DB.

### Callables and explicit defaults

- `bound_delta(account, directory)`
- `select_option(delta, underlying, side, target=40, now=None)`

### Literal payload and lookup fallbacks

- `DELTA_INDIA_ENABLE_LIVE_ORDERS` → `'1'`

## strategies/nifty_ai_options/delta_execution.py

[Owning source](../strategies/nifty_ai_options/delta_execution.py)

Own AI ledger around the existing native Delta order/reconciliation boundary.

### Callables and explicit defaults

- `DeltaExecution.__init__(self, delta, owner, state_dir, *, live=False, contracts=None, native=None)`
- `DeltaExecution.save(self)`
- `DeltaExecution.close(self)`
- `DeltaExecution.submit(self, action, quote)`
- `DeltaExecution._submit(self, action, quote, entry, side)`

### Literal payload and lookup fallbacks

- `exchange_at` → `0`
- `expiry` → `0`
- `expiry_epoch` → `0`
- `filledQty` → `0`
- `reason` → `'AI_RENKO_CONFIRMED_FLIP'`

## strategies/nifty_ai_options/delta_live.py

[Owning source](../strategies/nifty_ai_options/delta_live.py)

Selected Delta instrument runtime. Paper default; explicit Live opt-in only.

### Callables and explicit defaults

- `history(delta, symbol, frame, out)`
- `inspect(config, delta)`
- `live_readiness(delta, symbols)`
- `preflight(args)`
- `SourceBroker.__init__(self, delta, out, on_tick)`
- `SourceBroker.__getattr__(self, key)`
- `SourceBroker.unsubscribe(self, symbol)`
- `stream(args)`

### Literal payload and lookup fallbacks

- `contracts` → `{}`
- `product_id` → `-1`
- `sma` → `0`
- `target_premium` → `40`

## strategies/nifty_ai_options/direct.py

[Owning source](../strategies/nifty_ai_options/direct.py)

Selected-instrument direct AI Renko signals; no premium series or delta.

### Callables and explicit defaults

- `DirectStrategy.__init__(self, config)`
- `DirectStrategy.reset_contract(self, contract, delta=None)`
- `DirectStrategy.update(self, event)`
- `DirectStrategy.selected_gate_entry(self)`
- `DirectStrategy.exit(self, at, reason)`

### Literal payload and lookup fallbacks

- `sma_exit_enabled` → `False`

## strategies/nifty_ai_options/direct_execution.py

[Owning source](../strategies/nifty_ai_options/direct_execution.py)

Direct stock/futures execution with durable ownership and explicit Live opt-in.

### Callables and explicit defaults

- `DirectExecution.__init__(self, api, account, state_dir, *, live=False, lots=None, product=None, master=None, account_folder=None, margin=None)`
- `DirectExecution.close(self)`
- `DirectExecution.save(self)`
- `DirectExecution.submit(self, action, quote, now=None)`
- `DirectExecution._submit(self, action, quote, entry, side, now)`

### Literal payload and lookup fallbacks

- `expiry_epoch` → `0`
- `filledQty` → `0`
- `fund_limit` → `[]`
- `netQty` → `0`
- `orderBook` → `[]`
- `timestamp` → `0`

## strategies/nifty_ai_options/direct_live.py

[Owning source](../strategies/nifty_ai_options/direct_live.py)

Explicitly user-started FYERS direct stock/future runtime; Paper by default.

### Callables and explicit defaults

- `market_open(api, meta)`
- `history(api, config, meta, frame, directory)`
- `inspect(config, api, master)`
- `preflight(args)`
- `stream(args)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `sma` → `0`
- `underlying` → `0`

## strategies/nifty_ai_options/execution.py

[Owning source](../strategies/nifty_ai_options/execution.py)

Isolated account-scoped write-ahead order journal; never retries a submission.

### Callables and explicit defaults

- `Execution.__init__(self, api, account, state_dir, live=False, lots=None, product=None, master=None, account_folder=None)`
- `Execution.close(self)`
- `Execution.save(self)`
- `Execution.exposure(self)`
- `Execution.submit(self, action, quote, now=None)`
- `Execution._submit(self, action, quote, now=None)`

### Literal payload and lookup fallbacks

- `filledQty` → `0`
- `fund_limit` → `[]`
- `netQty` → `0`
- `orderBook` → `[]`

## strategies/nifty_ai_options/indicator.py

[Owning source](../strategies/nifty_ai_options/indicator.py)

Direct sequential recurrence of ai-renko-supertrend.pine (ADX disabled).

### Callables and explicit defaults

- `RMA.__init__(self, length)`
- `RMA.update(self, value)`
- `AIRenko.__init__(self, length=5, factor=3.0, manual_brick=None, tick=0.05, pine_series_precision=False)`
- `AIRenko.q(self, value)`
- `AIRenko.update(self, bar)`
- `Traditional.__init__(self, size)`
- `Traditional.grid(self, price)`
- `Traditional.update(self, price)`

## strategies/nifty_ai_options/instrument_search.py

[Owning source](../strategies/nifty_ai_options/instrument_search.py)

Read-only exact-symbol AI search, isolated from legacy preferences.

### Callables and explicit defaults

- `master_rows(folder, segment)`
- `search_fyers(folder, query, market, route='OPTIONS', now=None)`

## strategies/nifty_ai_options/live.py

[Owning source](../strategies/nifty_ai_options/live.py)

Explicitly opted-in live or default paper WebSocket runtime; no dashboard calls.

### Callables and explicit defaults

- `underlying(config)`
- `exposure_prefix(config)`
- `Reads.__init__(self, api)`
- `Reads.__getattr__(self, name)`
- `Master.__init__(self, directory)`
- `Master.__call__(self, symbol)`
- `history(api, symbol, frame, start, end, audit_dir=None)`
- `validate_config(config, api)`
- `nearest_expiry(data, now=None)`
- `choose(api, master, config, side, require_reference=True)`
- `preflight(args)`
- `Bars.__init__(self, frame, *, confirmed_closes=False)`
- `stream(args)`

### Literal payload and lookup fallbacks

- `accept_close_source_renko_approximation` → `False`
- `candles` → `[]`
- `expiryData` → `[]`
- `market` → `'NSE'`
- `netQty` → `0`
- `optionsChain` → `[]`
- `sma` → `0`
- `sma_exit_enabled` → `False`
- `symbol` → `''`
- `target_premium` → `40`

## strategies/nifty_ai_options/markets.py

[Owning source](../strategies/nifty_ai_options/markets.py)

Selected-market metadata and completed source bars. No execution side effects.

### Callables and explicit defaults

- `FyersInstrumentMaster.__init__(self, directory)`
- `FyersInstrumentMaster.__call__(self, symbol)`
- `margin_reader(raw)`
- `SourceBars.__init__(self, frame, *, continuous=False, opening_minutes=None, closing_minutes=None, zone=IST, confirmed_closes=False)`
- `SourceBars.update(self, stamp, price)`

## strategies/nifty_ai_options/native_bootstrap_research.py

[Owning source](../strategies/nifty_ai_options/native_bootstrap_research.py)

Cached first-valid ATR bootstrap observed in the public chart-library client.

### Callables and explicit defaults

- `BootstrapContext.__post_init__(self)`
- `CachedATRBootstrap.__init__(self, context)`
- `CachedATRBootstrap.update(self, bar, *, closed)`
- `CachedATRBootstrap.snapshot(self)`

## strategies/nifty_ai_options/native_reference.py

[Owning source](../strategies/nifty_ai_options/native_reference.py)

Identity-bound verified native reference lookup. Never substitutes raw OHLC ATR.

### Callables and explicit defaults

- `choose_reference(references, symbol, market, asset=None, *, expected_session=None, now=None)`
- `resolve_reference(owner, symbol, market, asset=None)`

### Literal payload and lookup fallbacks

- `observed_at` → `''`
- `status` → `''`

## strategies/nifty_ai_options/process_state.py

[Owning source](../strategies/nifty_ai_options/process_state.py)

Exact-process recovery for user-started AI jobs; never starts a process.

### Callables and explicit defaults

- `fingerprint(pid, proc=Path('/proc'))`
- `identity(pid, directory, *, proc=Path('/proc'))`
- `RecoveredProcess.__init__(self, record, directory)`
- `RecoveredProcess.poll(self)`
- `RecoveredProcess.terminate(self)`
- `recover(owner, data)`
- `assert_stopped(source, root=Path('/home/trading/sector-heatmap'))`

### Literal payload and lookup fallbacks

- `execution_mode` → `'PAPER'`

## strategies/nifty_ai_options/readiness_audit.py

[Owning source](../strategies/nifty_ai_options/readiness_audit.py)

Read-only process ownership and durable runner inventory; no service actions.

## strategies/nifty_ai_options/readiness_broker_data.py

[Owning source](../strategies/nifty_ai_options/readiness_broker_data.py)

Explicit-owner broker GETs and bounded CE candle repeat audit; no mutation paths.

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `netQty` → `0`
- `size` → `0`

## strategies/nifty_ai_options/readiness_current.py

[Owning source](../strategies/nifty_ai_options/readiness_current.py)

Use owning restart guard's CURRENT states, exclude backups; never reload.

## strategies/nifty_ai_options/readiness_exact_history.py

[Owning source](../strategies/nifty_ai_options/readiness_exact_history.py)

Direct bounded FYERS HTTP GET verification, bypasses SDK response handling.

### Literal payload and lookup fallbacks

- `candles` → `[]`

## strategies/nifty_ai_options/replay_native_feedback_control.py

[Owning source](../strategies/nifty_ai_options/replay_native_feedback_control.py)

Research control: source true range referenced to prior constructed Renko close.

### Callables and explicit defaults

- `replay_feedback(bars, length)`

## strategies/nifty_ai_options/replay_native_sizing_hypotheses.py

[Owning source](../strategies/nifty_ai_options/replay_native_sizing_hypotheses.py)

Offline hypotheses for native ATR box update rules. NOT a sizing provider.

### Callables and explicit defaults

- `parents(rows, step)`
- `normalize(value, rule)`
- `replay_rebuild(bars, length, rule)`
- `replay(bars, length, rule, update)`
- `load_parents()`

## strategies/nifty_ai_options/run.py

[Owning source](../strategies/nifty_ai_options/run.py)

Selected-instrument AI Renko Supertrend runner. Never activates legacy dashboard runners.

### Callables and explicit defaults

- `atomic(path, value)`
- `client(account)`
- `ok(reply)`
- `normalize(rows, price_only=False)`
- `normalize_closes(rows)`
- `six_hour(rows)`
- `probe(args)`
- `replay(args)`
- `main()`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `data` → `{}`
- `netQty` → `0`
- `optionsChain` → `[]`
- `symbol` → `''`

## strategies/nifty_ai_options/sizing_policy.py

[Owning source](../strategies/nifty_ai_options/sizing_policy.py)

User-selected parent durations are strategy inputs, never exchange session hours.

### Callables and explicit defaults

- `parent_hours(market, asset=None, tokenized_gold=False, explicit_category=None)`
- `reference_window(market, completed_session=None, completed_parent_end=None)`
- `scale_reference(reference, market, asset=None, *, delta=None, tokenized_gold=False, explicit_category=None)`
- `size_instrument(instrument, reference, *, delta=None)`

## strategies/nifty_ai_options/stage_ui_sources.py

[Owning source](../strategies/nifty_ai_options/stage_ui_sources.py)

Stage ONLY this feature's targeted edits in account-owned source snapshots; never reload.

### Callables and explicit defaults

- `replace(text, old, new, label)`
- `run(folder)`

## strategies/nifty_ai_options/tradingview_native.py

[Owning source](../strategies/nifty_ai_options/tradingview_native.py)

Official TradingView read-only Pine transport. No chart, trading or cache writes.

### Callables and explicit defaults

- `decode_reply(response, request_id)`
- `NativePineClient.__init__(self, token_provider, session=None)`
- `NativePineClient._post(self, payload)`
- `NativePineClient._rpc(self, method, params)`
- `NativePineClient.connect(self)`
- `NativePineClient.run_probe(self, symbol, *, timeframe='30m', return_bars=50, diagnostic=False, native_depth=300)`
- `NativePineClient.close(self)`

### Literal payload and lookup fallbacks

- `Content-Type` → `''`

## strategies/nifty_ai_options/tradingview_oauth.py

[Owning source](../strategies/nifty_ai_options/tradingview_oauth.py)

Explicit one-shot TradingView OAuth PKCE connection; never starts trading.

### Callables and explicit defaults

- `private_write(path, value)`
- `connect()`
- `access_token()`

### Literal payload and lookup fallbacks

- `code` → `[]`
- `error` → `'Authorization timed out'`
- `state` → `[]`

## strategies/nifty_ai_options/ui_bridge.py

[Owning source](../strategies/nifty_ai_options/ui_bridge.py)

Explicit UI-to-standalone bridge. No process is launched by import or preview.

### Callables and explicit defaults

- `owner_broker(owner)`
- `live_capability(owner)`
- `configuration(payload, owner)`
- `option_preview(owner, reference)`
- `Service.__init__(self, owner, legacy)`
- `Service.snapshot(self)`
- `Service.chart_source(self, query)`
- `Service.search(self, query, market, route='OPTIONS')`
- `Service.prepare(self, payload)`
- `Service.start(self, payload)`
- `Service._launch(self, directory, live)`
- `Service.stop(self, payload)`

### Literal payload and lookup fallbacks

- `DELTA_INDIA_ENABLE_LIVE_ORDERS` → `'1'`
- `ai_accept_chart_basis` → `False`
- `ai_execution_route` → `'OPTIONS'`
- `ai_sma_exit_enabled` → `False`
- `frame` → `'0'`
- `market` → `'NSE'`
- `mode` → `'PAPER'`
- `native_box` → `0`
- `source` → `''`
- `status` → `''`
- `target_premium` → `40`
- `url` → `''`

## strategies/nifty_ai_options/verify_chart_parity.py

[Owning source](../strategies/nifty_ai_options/verify_chart_parity.py)

Persistent offline comparison fixture for exact NEW chart Renko + Pine runtime.

## strategies/nifty_ai_options/verify_data.py

[Owning source](../strategies/nifty_ai_options/verify_data.py)

Read-only 1/5/30m source audit and signal replay; never an executable-fill backtest.

### Literal payload and lookup fallbacks

- `candles` → `[]`

## strategies/nifty_ai_options/verify_native_fixed_geometry.py

[Owning source](../strategies/nifty_ai_options/verify_native_fixed_geometry.py)

Verify local fixed-box geometry against retained native research data.

### Callables and explicit defaults

- `verify()`

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

## strategies/renko_engine/__init__.py

[Owning source](../strategies/renko_engine/__init__.py)

## strategies/renko_engine/rules.py

[Owning source](../strategies/renko_engine/rules.py)

Independent Renko Engine rules shared by execution and historical replay.

### Callables and explicit defaults

- `epoch(value)`
- `minute(t)`
- `inside(t, session)`
- `settings(raw)`
- `replay(candles, raw=None, tick=0.05, seconds=300, commission=0.0003, slippage_ticks=2, capital=1000000)`

### Configuration literals

- `DEFAULTS = dict(mode='Percentage', percent=0.66, fixedBox=50, basis='Current close', stepping='Whole bricks', reversalBricks=1, roundBrick=False, anchorTime='2026-09-01T09:15', seedLevel=0, seedTrend=0, rule='EMA cross + Renko direction', direction='Both', sessionOnly=True, session='0915-1505', flatHour=15, flatMinute=10, endTime='2026-12-31T23:59', showCPR=True, showRange=True, rangeSession='1245-1300', showFR=True)`

## strategies/renko_engine/runner.py

[Owning source](../strategies/renko_engine/runner.py)

Independent Renko Engine signals on the existing broker execution lifecycle.

### Callables and explicit defaults

- `configuration(payload, broker='FYERS')`
- `cutoff(now, config)`
- `IndependentSignals.entry_preflight(self, order, contract, quote)`
- `IndependentSignals.signal_key(self, sig)`
- `IndependentSignals.signal(self)`
- `IndependentSignals.fresh_cross(self, sig)`
- `IndependentSignals.exit_reason_for(self, sig, position)`
- `IndependentSignals.exit_signal(self, sig, direction)`
- `IndependentSignals.activate(self, payload, background=True)`
- `IndependentSignals.start(self, payload, background=True)`
- `IndependentSignals.override_entry(self, payload)`

### Literal payload and lookup fallbacks

- `engine_settings` → `{}`
- `execution_route` → `'OPTIONS'`

## strategies/renko_engine/service.py

[Owning source](../strategies/renko_engine/service.py)

Account-bound Renko Engine service. Reads never activate trading.

### Callables and explicit defaults

- `Service.__init__(self, runner, chart_broker, account_id, broker)`
- `Service.identity(self, p)`
- `Service.candles(self, p)`
- `Service.snapshot(self)`
- `Service.read(self, action)`
- `Service.write(self, action, p)`

### Literal payload and lookup fallbacks

- `engine_settings` → `{}`
- `execution_route` → `'OPTIONS'`
- `history_days` → `45`

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
- `market_event_at` → `0`
- `netQty` → `0`
- `orderTag` → `''`
- `status` → `0`

## strategies/renko_supertrend/anti_chop.py

[Owning source](../strategies/renko_supertrend/anti_chop.py)

Optional, completed-host-candle, entry-only anti-chop checklist.

### Callables and explicit defaults

- `settings(payload)`
- `standalone_rules(payload)`
- `compatible(payload)`
- `observe(state, candle, config, direction, seconds=300)`
- `apply(entry, gate)`
- `generate_entry(entry, gate, state)`
- `combine(checks, ready, combination)`

### Literal payload and lookup fallbacks

- `count` → `0`
- `mandatory` → `True`
- `timeframe` → `'5 minutes'`

### Configuration literals

- `DEFAULTS = dict(anti_chop_enabled=False, anti_chop_combination='All', anti_chop_role='Filter', anti_chop_mode='Adaptive', anti_chop_atr_length=14, anti_chop_atr_average_length=20, anti_chop_ema_fast_length=20, anti_chop_ema_slow_length=50, anti_chop_adaptive_window=200, anti_chop_slope_percentile=60.0, anti_chop_gap_percentile=60.0, anti_chop_overlap_percentile=40.0, anti_chop_slope_bars=3, anti_chop_slope_atr=0.15, anti_chop_gap_atr=0.2, anti_chop_cross_bars=6, anti_chop_structure_bars=3, anti_chop_overlap_percent=50.0)`

## strategies/renko_supertrend/backtest.py

[Owning source](../strategies/renko_supertrend/backtest.py)

Isolated Renko research using fixed historical contracts and actual premiums.

### Callables and explicit defaults

- `period(request, today=None)`
- `framework_trade(rows, entry_at, exit_at, quantity, direction='BULLISH')`
- `metrics(trades, capital)`
- `run(request, source, now=None)`

### Literal payload and lookup fallbacks

- `additional_slippage_points` → `0`
- `broker` → `'FYERS'`
- `ema_exit_length` → `10`
- `period` → `'1m'`
- `volume` → `0`
- `zone_entry_rearm` → `True`

## strategies/renko_supertrend/backtest_data.py

[Owning source](../strategies/renko_supertrend/backtest_data.py)

Research-only market archive access. No order or runner interfaces.

### Callables and explicit defaults

- `valid_rows(rows)`
- `session(symbol)`
- `in_session(stamp, policy)`
- `aggregate(rows, minutes, policy)`
- `Archive.__init__(self, root, token=None, allow_download=False)`
- `Archive.get(self, path, params)`
- `Archive.underlying(self, symbol, first, last, minutes)`
- `Archive.select(self, symbol, stamp, direction, spot)`
- `Archive.premiums(self, contract, first, last, minutes)`

### Literal payload and lookup fallbacks

- `contracts` → `{}`
- `data` → `{}`
- `expiry_dates` → `{}`
- `options` → `[]`

## strategies/renko_supertrend/batch.py

[Owning source](../strategies/renko_supertrend/batch.py)

Explicit multi-instrument activation with durable, non-replaying batch IDs.

### Callables and explicit defaults

- `Batch.__init__(self, path, create, lookup)`
- `Batch.save(self, file, data)`
- `Batch.start(self, payload, background=True)`

## strategies/renko_supertrend/binding.py

[Owning source](../strategies/renko_supertrend/binding.py)

Authoritative broker/instrument scope for settings and runner actions.

### Callables and explicit defaults

- `normalize_settings(values, broker=None, instrument=None)`
- `validate_request(payload, broker, instrument=None, account_id=None)`

## strategies/renko_supertrend/brick_basis.py

[Owning source](../strategies/renko_supertrend/brick_basis.py)

Confirmed close-based uniform Renko events. No invented intrabar ordering.

### Callables and explicit defaults

- `update(engine, candle)`

### Literal payload and lookup fallbacks

- `basis_host_filter_rows` → `[]`
- `brick_direction` → `0`
- `count` → `0`
- `ema_exit_enabled` → `False`
- `ema_exit_length` → `10`

## strategies/renko_supertrend/brick_entry.py

[Owning source](../strategies/renko_supertrend/brick_entry.py)

Automatic Renko entry direction is owned by its completed signal brick.

### Callables and explicit defaults

- `allowed(config, signal, direction)`

## strategies/renko_supertrend/calibrated.py

[Owning source](../strategies/renko_supertrend/calibrated.py)

Optional calibrated entry overlap and frozen per-position underlying ATR plan.

### Callables and explicit defaults

- `settings(payload)`
- `compatible(config)`
- `check(rows, config, seconds=300)`
- `plan(config, price, atr, direction, tick=0.05, signal_at=None)`
- `effective(config, position)`

### Configuration literals

- `DEFAULTS = dict(calibrated_enabled=False, calibrated_overlap_pairs=6, calibrated_overlap_max=0.4, calibrated_stop_atr=3.0, calibrated_target_atr=1.5)`

## strategies/renko_supertrend/candle_patterns.py

[Owning source](../strategies/renko_supertrend/candle_patterns.py)

Explicit body-based patterns for completed host-candle retests.

### Callables and explicit defaults

- `matches(rows, bullish, config)`

### Literal payload and lookup fallbacks

- `retest_engulfing` → `True`
- `retest_harami` → `True`
- `retest_star` → `True`

## strategies/renko_supertrend/chart_destinations.py

[Owning source](../strategies/renko_supertrend/chart_destinations.py)

Read-only entry study selection and source preparation for chart replay.

### Callables and explicit defaults

- `query_settings(query)`

## strategies/renko_supertrend/chart_history.py

[Owning source](../strategies/renko_supertrend/chart_history.py)

Bounded, durable fixed-contract OHLC history for read-only chart research.

### Callables and explicit defaults

- `selected_range(preset='45', start='', end='', now=None)`
- `candle_issue(row)`
- `ChartHistory.__init__(self, path, min_interval=0.35, tail_provider=None)`
- `ChartHistory.history_lock(self, key)`
- `ChartHistory.wait_request_slot(self)`
- `ChartHistory.load(self, client, symbol, timeframe, preset='45', start='', end='', config=None, tick=0.05, now=None)`

### Literal payload and lookup fallbacks

- `candles` → `[]`
- `deferred_completed` → `set()`
- `ema_third_enabled` → `True`
- `forming_retry_count` → `0`
- `message` → `'invalid response'`
- `next_retry` → `0`
- `refreshed_at` → `0`
- `repair_after` → `0`
- `rows` → `[]`

## strategies/renko_supertrend/chart_recovery.py

[Owning source](../strategies/renko_supertrend/chart_recovery.py)

Recover display calculations only; execution history remains strictly guarded.

### Callables and explicit defaults

- `analyze_chart(candles, config, tick, saved=None, retain=5000)`

## strategies/renko_supertrend/confirmed_feed.py

[Owning source](../strategies/renko_supertrend/confirmed_feed.py)

Account-local candle refresh and immutable confirmed-indicator publication.

### Callables and explicit defaults

- `SharedCandleFeed.__init__(self, clock=time.time)`
- `SharedCandleFeed.register(self, key, owner, config)`
- `SharedCandleFeed.read(self, key, seconds, loader, with_revision=False)`
- `SharedCandleFeed._refresh(self, key, seconds, loader)`
- `SharedCandleFeed.health(self, key)`
- `feed_for(loader)`
- `confirmed_export(state, include_rows=False)`
- `publish_confirmed(runner, *, engine=None, config=None, immutable_rows=False)`
- `bind_confirmed(runner, requested_run, symbol, timeframe)`
- `SharedQuoteHub.__init__(self, transport)`
- `SharedQuoteHub.join(self, owner)`
- `SharedQuoteHub.leave(self, owner)`
- `SharedQuoteHub.publish(self, raw)`
- `SharedQuoteHub.tick(self, owner, symbol)`
- `quote_hub_for(owner)`

### Literal payload and lookup fallbacks

- `rows` → `[]`

## strategies/renko_supertrend/costs.py

[Owning source](../strategies/renko_supertrend/costs.py)

Explicit FYERS NSE/BSE-options cost estimates from owned cumulative fills, never broker bills.

### Callables and explicit defaults

- `rounded(x, unit='0.01')`
- `valid(x)`
- `settings(payload)`
- `exchange_rate(row)`
- `applicable(row)`
- `fee(turnover, side, brokerage=20, stt=None, stamp=None, exchange_rate=None)`
- `ledger_costs(orders)`
- `trade_costs(trade, ledger)`

### Literal payload and lookup fallbacks

- `additional_slippage_points` → `0`
- `submitted_at` → `0`
- `symbol` → `''`

### Configuration literals

- `RATES = dict(exchange=0.000325, clearing=9e-05, ipft=1e-09, sebi=1e-06, stt_sell=0.0015, stamp_buy=3e-05, gst=0.18)`

## strategies/renko_supertrend/delta_broker.py

[Owning source](../strategies/renko_supertrend/delta_broker.py)

### Callables and explicit defaults

- `history_file_lock(path, symbol, resolution)`
- `Broker.__init__(self, delta, history_path, on_tick=None)`
- `Broker.live_enabled(self)`
- `Broker.session_policy(self, config)`
- `Broker._master_row(self, product)`
- `Broker.rows(self, segment)`
- `Broker.underlying(self, symbol)`
- `Broker.host_tick_size(self, symbol)`
- `Broker.contract(self, symbol)`
- `Broker.validate_saved_paper_stop(self, config, position)`
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
- `Broker._place(self, order)`
- `Broker.cancel(self, order_id)`

### Literal payload and lookup fallbacks

- `exchange_at` → `0`
- `execution_route` → `'OPTIONS'`

## strategies/renko_supertrend/delta_contracts.py

[Owning source](../strategies/renko_supertrend/delta_contracts.py)

Delta-native Renko boundary types. No network or execution side effects.

### Callables and explicit defaults

- `decimal(value, name, positive=False)`
- `whole(value, name, positive=False)`
- `configuration(payload)`
- `option_contract(product, now)`
- `perpetual_contract(product, require_entry=True)`
- `contract_metadata(product, now)`
- `position(row, product, now)`
- `order_intent(symbol, size, side, quote, product, now, reduce_only=None)`
- `owned_order(owned, expected_account)`

### Literal payload and lookup fallbacks

- `carry_policy` → `'CONTINUOUS'`
- `execution_route` → `'OPTIONS'`
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
- `Execution.submit(self, symbol, size, side, quote, token, signal_symbol, reason, reduce_only=None)`
- `Execution.cancel(self, request_id)`

## strategies/renko_supertrend/delta_external_close.py

[Owning source](../strategies/renko_supertrend/delta_external_close.py)

Conservative attribution of an existing Delta external close; never submits.

### Callables and explicit defaults

- `confirmed_close(position, fills, active_orders, broker_size)`
- `read_evidence(delta, execution, position, account_identity, clock)`
- `stopped_external_identity(source, state)`

### Literal payload and lookup fallbacks

- `entry_side` → `1`
- `product_id` → `-1`

## strategies/renko_supertrend/delta_no_send.py

[Owning source](../strategies/renko_supertrend/delta_no_send.py)

Recover proven pre-submission rejections, never unknown broker acknowledgements.

### Callables and explicit defaults

- `fingerprint(order)`
- `receipt_path(delta, tag)`
- `record(delta, order, account_identity, *, basis='SAME_CALL_BEFORE_NATIVE_INTENT', evidence=None)`
- `verify(runner)`
- `prove_absent(adapter, p, expected_account)`
- `recover(runner)`

## strategies/renko_supertrend/delta_runner.py

[Owning source](../strategies/renko_supertrend/delta_runner.py)

Shared Renko rules with explicit Delta policy and native accounting labels.

### Callables and explicit defaults

- `DeltaRunner.step(self)`
- `DeltaRunner.reconcile_external_stop(self)`
- `DeltaRunner.recover_requested_external_stop(self, background=True)`
- `DeltaRunner.recover_unsubmitted_intent(self)`
- `DeltaRunner.reconcile(self)`
- `DeltaRunner.entry_preflight(self, order, contract, quote)`
- `DeltaRunner.override_entry(self, payload)`
- `DeltaRunner.telegram_entry(self, payload)`
- `DeltaRunner.preferences_path(self)`
- `DeltaRunner.binding_scope(self)`
- `DeltaRunner.read_preferences(self)`
- `DeltaRunner.save_preferences(self, payload)`
- `DeltaRunner.deadline(self)`
- `DeltaRunner.submit(self, order, position, reason)`
- `DeltaRunner.record_order(self, pending, status, filled=0, price=None)`
- `DeltaRunner.snapshot(self)`

### Literal payload and lookup fallbacks

- `execution_route` → `'OPTIONS'`
- `trade_history` → `[]`

## strategies/renko_supertrend/delta_service.py

[Owning source](../strategies/renko_supertrend/delta_service.py)

Delta Renko HTTP component: shared chart math, isolated execution ownership.

### Callables and explicit defaults

- `Service.__init__(self, delta, root, instance_key='default', instrument=None)`
- `Service.chart_config(self, query)`
- `Service.manual_brick(self, query)`
- `Service.confirmed_chart(self, query, requested_run)`
- `Service.chart(self, query)`
- `Service.get(self, handler, path)`
- `Service.post(self, handler, path, payload)`
- `Service.stream(self, handler, query)`

### Literal payload and lookup fallbacks

- `trade_history` → `[]`

## strategies/renko_supertrend/destinations.py

[Owning source](../strategies/renko_supertrend/destinations.py)

Chart destinations are stored separately; existing switches own execution.

### Callables and explicit defaults

- `settings(payload)`
- `chart(payload)`

## strategies/renko_supertrend/dhan_costs.py

[Owning source](../strategies/renko_supertrend/dhan_costs.py)

Dhan retail option fee estimates, not contract-note charges.

### Callables and explicit defaults

- `fee(turnover, side, exchange_rate=None)`
- `order_cost(row)`
- `trade_costs(trade, ledger)`
- `mcx_fee(turnover, side)`

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
- `check(config, price, ema10, confirmed_atr, signal=None, direction=None)`
- `momentum_signal(sig, direction)`
- `new_entry_defaults(payload)`
- `migrate_preferences(fields)`

### Literal payload and lookup fallbacks

- `ema_fast_length` → `10`
- `ema_momentum_enabled` → `False`
- `ema_proximity_distance` → `0.5`
- `ema_proximity_enabled` → `False`
- `ema_proximity_mode` → `'ATR'`
- `intrabar_entries` → `False`

## strategies/renko_supertrend/entry_pipeline.py

[Owning source](../strategies/renko_supertrend/entry_pipeline.py)

Bounded read-only execution checks; never submits, retries or relaxes entry age.

### Callables and explicit defaults

- `_schedule(fn)`
- `bounded_read(fn, deadline)`
- `broker_preflight(adapter, order, config)`

### Literal payload and lookup fallbacks

- `netQty` → `0`
- `status` → `0`

## strategies/renko_supertrend/entry_qualification.py

[Owning source](../strategies/renko_supertrend/entry_qualification.py)

Read-only final signal checks shared by entry authorization and chart replay.

### Callables and explicit defaults

- `check(config, signal, direction, *, external=True)`
- `events(rows, config)`

### Literal payload and lookup fallbacks

- `adx_threshold` → `20`
- `brick_events` → `[]`
- `count` → `0`
- `sides` → `{}`
- `sma_length` → `5`
- `supertrend_slope_bars` → `1`
- `supertrend_slope_min_atr` → `0`
- `trend_reentry_enabled` → `True`

## strategies/renko_supertrend/execution_audit.py

[Owning source](../strategies/renko_supertrend/execution_audit.py)

Display owned fills against a candidate's candle, retaining the first assessment.

### Callables and explicit defaults

- `entry_orders(event, orders, seconds)`

## strategies/renko_supertrend/exit_indicators.py

[Owning source](../strategies/renko_supertrend/exit_indicators.py)

Opt-in completed-candle exit criteria independent of entry selections.

### Callables and explicit defaults

- `settings(payload)`
- `sma_reason(config, event, direction)`
- `reason(config, sig, direction)`

### Literal payload and lookup fallbacks

- `adx_exit_enabled` → `False`
- `adx_threshold` → `25`
- `brick_exit_events` → `[]`
- `ema_slow_exit_enabled` → `False`
- `ema_slow_length` → `30`
- `ema_widening_exit_enabled` → `False`
- `market_structure_exit_enabled` → `False`
- `rsi_exit_enabled` → `False`
- `sma_length` → `5`
- `supertrend_exit_enabled` → `True`

### Configuration literals

- `DEFAULTS = dict(renko_brick_exit_enabled=False, supertrend_exit_enabled=True, ema_slow_exit_enabled=False, rsi_exit_enabled=False, ema_widening_exit_enabled=False, adx_exit_enabled=False, market_structure_exit_enabled=False)`

## strategies/renko_supertrend/historical_lots.py

[Owning source](../strategies/renko_supertrend/historical_lots.py)

Exact-contract daily FYERS master evidence. No lot defaults or forward-fill.

### Callables and explicit defaults

- `digest(blob)`
- `atomic(path, blob)`
- `archive_master(root, segment, body, observed_at, timestamp_basis='broker-download-completed')`
- `verified_period(root, manifest, contract, lot)`
- `checked_lot(contract, stamp)`
- `HistoricalLots.__init__(self, root)`
- `HistoricalLots.resolve(self, contract, stamp)`

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

## strategies/renko_supertrend/indicator_families.py

[Owning source](../strategies/renko_supertrend/indicator_families.py)

Master strategy gates; stored subordinate choices and chart destinations stay independent.

### Callables and explicit defaults

- `restore(payload)`
- `apply(payload)`

### Literal payload and lookup fallbacks

- `sma_exit_enabled` → `False`
- `strategy_mode` → `'SUPERTREND'`
- `supertrend` → `True`
- `supertrend_family_enabled` → `True`

### Configuration literals

- `DEFAULTS = {name + '_family_enabled': True for name in FAMILIES}`

## strategies/renko_supertrend/indicator_selection.py

[Owning source](../strategies/renko_supertrend/indicator_selection.py)

Independent entry indicators; defaults preserve the existing combined setup.

### Callables and explicit defaults

- `validate(c)`
- `qualify(c, close, fast, slow, direction, allowed, widening, reversal, rsi, third=None)`

### Literal payload and lookup fallbacks

- `ema_third_enabled` → `False`

### Configuration literals

- `DEFAULTS = dict(supertrend_enabled=True, ema_fast_enabled=True, ema_slow_enabled=True, ema_third_enabled=True, ema_widening_enabled=True, ema_fast_length=10, ema_slow_length=30, ema_third_length=100, rsi_slope_length=14)`

## strategies/renko_supertrend/journal_export.py

[Owning source](../strategies/renko_supertrend/journal_export.py)

Presentable, immutable journal export; spreadsheet generation has no order route.

### Callables and explicit defaults

- `export_xlsx(data, root)`

## strategies/renko_supertrend/journal_scope.py

[Owning source](../strategies/renko_supertrend/journal_scope.py)

Select journal evidence within one already authenticated workspace registry.

### Callables and explicit defaults

- `journal_scope(instances, broker, instance='all', mode='ALL')`

### Literal payload and lookup fallbacks

- `instance_key` → `''`
- `instance_key` → `'default'`
- `trade_history` → `[]`
- `trade_id` → `''`

## strategies/renko_supertrend/line_entry.py

[Owning source](../strategies/renko_supertrend/line_entry.py)

Optional Bull/Bear line entry filter on actual completed Renko bricks.

### Callables and explicit defaults

- `valid_line(line)`
- `settings(payload)`
- `level(line, at)`
- `observe(state, config, signal, run_id)`

### Literal payload and lookup fallbacks

- `line_entry_definition` → `''`
- `line_entry_enabled` → `False`

### Configuration literals

- `DEFAULTS = dict(line_entry_enabled=False, line_entry_definition='')`

## strategies/renko_supertrend/live_chart.py

[Owning source](../strategies/renko_supertrend/live_chart.py)

Account/broker-local chart recurrence. Never calls a runner or order API.

### Callables and explicit defaults

- `LiveChart.__init__(self, broker)`
- `LiveChart.seed(self, key, engine, config, tick_size, replace=False)`
- `LiveChart.accept(self, raw, received)`
- `LiveChart.poll(self, config)`
- `LiveChart.revision(self, key)`
- `LiveChart.apply(self, key, response=None, revision=None)`
- `chart_for(broker)`

### Literal payload and lookup fallbacks

- `brick_events` → `[]`

## strategies/renko_supertrend/loss_range.py

[Owning source](../strategies/renko_supertrend/loss_range.py)

Post-loss entry lock using completed Renko bodies, never forming prices.

### Callables and explicit defaults

- `settings(payload)`
- `enabled(config)`
- `finite(value)`
- `bricks(signal, seconds)`
- `observe(position, signal, config, now, seconds, seed=False)`
- `freeze(position, signal, config, net, now, seconds, run_id, trade_id)`
- `breakout(lock, signal, direction, now, seconds)`

### Literal payload and lookup fallbacks

- `buffer_bricks` → `0`
- `last_timestamp` → `-1`
- `renko_loss_range_buffer` → `0`
- `renko_loss_range_enabled` → `False`
- `renko_loss_range_enabled` → `True`
- `timestamp` → `0`

## strategies/renko_supertrend/manual_brick.py

[Owning source](../strategies/renko_supertrend/manual_brick.py)

Read-only reference ATR sizing; independent of display/runner timeframe.

### Callables and explicit defaults

- `rule(symbol, session=None, *, atr_length)`
- `calculate(rows, specification, source_seconds, now)`
- `reference_result(bars, specification, now)`
- `calculate_sessions(rows, specification, now)`

### Literal payload and lookup fallbacks

- `master_regular_session` → `''`

## strategies/renko_supertrend/manual_trend.py

[Owning source](../strategies/renko_supertrend/manual_trend.py)

Optional entry-only price-marker confirmation on completed host candles.

### Callables and explicit defaults

- `settings(payload)`
- `check(rows, config, direction, seconds)`
- `apply(entry, gate)`

### Configuration literals

- `DEFAULTS = dict(manual_trend_enabled=False, manual_trend_bullish=None, manual_trend_bearish=None, manual_trend_closes=2)`

## strategies/renko_supertrend/market_structure.py

[Owning source](../strategies/renko_supertrend/market_structure.py)

Optional directional structure gate from confirmed actual host pivots.

### Callables and explicit defaults

- `settings(payload)`
- `check(rows, direction, seconds, event_at)`

### Literal payload and lookup fallbacks

- `market_structure_enabled` → `False`

## strategies/renko_supertrend/mtf_rsi.py

[Owning source](../strategies/renko_supertrend/mtf_rsi.py)

Optional completed-bar RSI confirmations, with independent slot levels.

### Callables and explicit defaults

- `enabled(config)`
- `settings(payload)`
- `validate_levels(levels, label)`
- `slot_levels(config, slot)`
- `query_settings(query)`
- `matches(value, direction, config)`
- `frames(config)`
- `_continuous(previous, current, seconds, config)`
- `prepare(sources, config)`
- `assess(prepared, config, direction, at)`
- `check(sources, config, direction, at)`

### Literal payload and lookup fallbacks

- `rsi_family_enabled` → `True`
- `rsi_slope_length` → `14`
- `timeframe` → `'5 minutes'`
- `times` → `[]`

## strategies/renko_supertrend/mtf_supertrend.py

[Owning source](../strategies/renko_supertrend/mtf_supertrend.py)

Optional selected host/higher-timeframe Supertrend agreement; no order routing.

### Callables and explicit defaults

- `settings(payload)`
- `latest(candles, config, tick_size, seconds, at)`
- `agreement(one, five, direction)`
- `check(one_rows, five_rows, config, tick_size, direction, at)`

### Literal payload and lookup fallbacks

- `atr_length` → `5`
- `higher_timeframe_enabled` → `False`
- `supertrend_timeframe` → `'5 minutes'`
- `timeframe` → `'1 minute'`

## strategies/renko_supertrend/nse_contract_lots.py

[Owning source](../strategies/renko_supertrend/nse_contract_lots.py)

Read-only, checksum-retained NSE daily MII contract evidence for research.

### Callables and explicit defaults

- `source_url(day, host='nsearchives.nseindia.com')`
- `contract_date(value)`
- `archive(root, day, blob, url)`
- `resolve(root, contract, day, cache)`

## strategies/renko_supertrend/option_premium.py

[Owning source](../strategies/renko_supertrend/option_premium.py)

Optional FYERS index-option premium selection using fresh executable asks.

### Callables and explicit defaults

- `index_option(config)`
- `native_option(config)`
- `native_option(config)`
- `settings(payload)`
- `candidates(adapter, config, atm)`
- `choose(adapter, config, atm)`
- `choose_native(adapter, config, contracts, spot)`

### Literal payload and lookup fallbacks

- `broker` → `'FYERS'`
- `execution_route` → `'OPTIONS'`
- `symbol` → `''`

## strategies/renko_supertrend/preferences.py

[Owning source](../strategies/renko_supertrend/preferences.py)

### Callables and explicit defaults

- `read(path)`
- `write(path, payload, now, scope=None)`

### Literal payload and lookup fallbacks

- `cash-product` → `'INTRADAY'`
- `chart-view` → `'host'`
- `commodity-holding` → `'INTRADAY'`
- `delta-execution-route` → `'OPTIONS'`
- `history-preset` → `'45'`
- `manual_brick` → `0`
- `market` → `'ALL'`
- `mode` → `'PAPER'`
- `symbol` → `''`

## strategies/renko_supertrend/price_basis.py

[Owning source](../strategies/renko_supertrend/price_basis.py)

Confirmed Renko from ordered live price observations, independent of host close.

### Callables and explicit defaults

- `observe(export, config, tick_size, tick, received, generation)`
- `_price_event_identity(row)`
- `_remember_price_publication(runner, rows, timing)`
- `_record_price_execution_timing(runner, row, started, elapsed, decision)`
- `_publish_price_confirmed(publisher, runner, *, engine, config)`
- `produce(runner, tick, received, generation, *, config=None)`
- `producer(runner, run_id)`
- `retain_opposite_exit(runner, row)`
- `run_step(runner)`

### Literal payload and lookup fallbacks

- `count` → `0`
- `ema_exit_enabled` → `False`
- `ema_exit_length` → `10`
- `rows` → `[]`
- `source` → `'BROKER_PRICE_OBSERVATION'`
- `status` → `'UNKNOWN'`
- `timestamp` → `0`

## strategies/renko_supertrend/recovery.py

[Owning source](../strategies/renko_supertrend/recovery.py)

One watchdog per active Renko runner. A living worker is never duplicated.

### Callables and explicit defaults

- `Recovery.__init__(self, runner, monotonic=time.monotonic)`
- `Recovery.beat(self)`
- `Recovery.snapshot(self)`
- `Recovery.check(self)`
- `Recovery.start(self)`

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

- `ema_slow_enabled` → `True`
- `ema_third_enabled` → `False`
- `retest_bars` → `[]`
- `retest_ready` → `False`

## strategies/renko_supertrend/risk.py

[Owning source](../strategies/renko_supertrend/risk.py)

Underlying price hard boundaries, independent of completed entry candles.

### Callables and explicit defaults

- `levels(payload)`
- `hard_exit(price, direction, config)`

## strategies/renko_supertrend/rsi_level.py

[Owning source](../strategies/renko_supertrend/rsi_level.py)

Optional strict RSI level entry gate; never changes exits.

### Callables and explicit defaults

- `apply(entry, state, observation, direction, config)`
- `matches(value, direction, config)`

### Literal payload and lookup fallbacks

- `rsi_bearish_max` → `40`
- `rsi_bearish_min` → `35`
- `rsi_bullish_max` → `80`
- `rsi_bullish_min` → `60`
- `rsi_level_enabled` → `False`
- `rsi_level_mode` → `'THRESHOLD'`

## strategies/renko_supertrend/rsi_slope.py

[Owning source](../strategies/renko_supertrend/rsi_slope.py)

Wilder RSI14 of host closes, identical seeding/flat convention to chart display.

### Callables and explicit defaults

- `observe(state, close, length=14)`
- `apply(entry, state, observation, direction, enabled)`

### Literal payload and lookup fallbacks

- `count` → `0`
- `gain` → `0`
- `loss` → `0`
- `rsi_host` → `{}`

## strategies/renko_supertrend/runner.py

[Owning source](../strategies/renko_supertrend/runner.py)

### Callables and explicit defaults

- `start_history(rows, config)`
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
- `Broker.start(self)`
- `Broker.tick(self, symbol)`
- `Broker.subscribe_all(self)`
- `Broker.stop(self)`
- `Broker.__init__(self, *args, on_tick=None, **kwargs)`
- `Broker.observe(self, c, rows)`
- `Broker.candles(self, c)`
- `Broker.candle_revision(self, c)`
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
- `Runner.warm_price_options(self, c)`
- `Runner.handle_step_error(self, error)`
- `Runner.entry_preflight(self, order, contract, quote)`
- `Runner.loop(self)`
- `Runner.preferences_path(self)`
- `Runner.binding_scope(self)`
- `Runner.validate_binding(self, payload)`
- `Runner.read_preferences(self)`
- `Runner.drain_position_ticks(self)`
- `Runner.observe_position_tick(self, tick, received_at=None, persist=True)`
- `Runner.observe_renko_loss_range(self, signal)`
- `Runner.renko_loss_entry_gate(self, signal=None, direction=None)`
- `Runner.sideways_entry_gate(self)`
- `Runner.indicator_snapshot(self, sig=None, reason=None)`
- `Runner.save_preferences(self, payload)`
- `Runner.set_spread_filter(self, payload)`
- `Runner.set_trend_reentry(self, payload)`
- `Runner.preview(self, payload)`
- `Runner.activate(self, payload, background=True)`
- `Runner.recover_requested_paper_stop(self, background=True)`
- `Runner.resume_position(self, payload, background=True)`
- `Runner.valuation_quote(self, symbol)`
- `Runner.stop(self)`
- `Runner._chart_identity(self, payload)`
- `Runner.chart_stop(self, payload)`
- `Runner.chart_timeframe(self, payload)`
- `Runner.apply_pending_timeframe(self)`
- `Runner.chart_mode(self, payload)`
- `Runner.prepare_zone_target(self, position, config)`
- `Runner.session_bounds(self, c)`
- `Runner.valuation_identity(state)`
- `Runner.snapshot_valuation(self, result)`
- `Runner.snapshot(self)`
- `Runner.signal_key(self, sig)`
- `Runner.entry_session_open(self, config)`
- `Runner.wait_for_entry_session(self)`
- `Runner.deadline(self)`
- `Runner.step(self)`
- `Runner._candle_step(self)`
- `Runner.record_order(self, pending, status, filled=0, price=None)`
- `Runner.complete_pending(self, filled, price)`
- `Runner.override_entry(self, payload)`
- `Runner.manual_trend_entry_gate(self, direction)`
- `Runner.calibrated_entry_gate(self, direction)`
- `Runner.zone_entry_gate(self, direction)`
- `Runner.swing_entry_gate(self, direction)`
- `Runner.validate_entry_authorization(self, position)`
- `Runner.anti_chop_entry_gate(self, direction)`
- `Runner.submit(self, order, position, reason)`
- `Runner.record_entry_assessment(self, sig, eligible, code, reason)`
- `Runner.fresh_cross(self, sig)`
- `Runner.remember_execution_signal(self, sig, eligible, reason=None)`
- `Runner.exit_reason_for(self, sig, position)`
- `Runner.exit_is_later(self, sig, position)`
- `Runner.exit_signal(self, sig, direction)`
- `Runner.exit_ema(self, rows, c)`
- `Runner.history_rows(self, rows)`
- `Runner.current_analysis(self, rows, c, tick)`
- `Runner.rsi_agreement(self, direction, at)`
- `Runner.supertrend_agreement(self, direction, at, host_rows=None)`
- `Runner.signal(self)`

### Literal payload and lookup fallbacks

- `_chart_higher_rows` → `[]`
- `_chart_rsi_rows` → `{}`
- `_chart_zone_rows` → `[]`
- `accepting_entries` → `False`
- `additional_slippage_points` → `0`
- `brick_exit_events` → `[]`
- `broker` → `'FYERS'`
- `cash_product` → `'INTRADAY'`
- `count` → `0`
- `eligible_since` → `0`
- `ema_exit_enabled` → `False`
- `ema_exit_enabled` → `True`
- `ema_exit_length` → `10`
- `ema_fast_length` → `10`
- `ema_gaps` → `[]`
- `ema_slow_enabled` → `True`
- `ema_slow_length` → `30`
- `ema_third_enabled` → `False`
- `ema_third_enabled` → `True`
- `ema_third_length` → `100`
- `entry_side` → `1`
- `event_at` → `0`
- `execution_route` → `'OPTIONS'`
- `execution_signals` → `[]`
- `filled` → `0`
- `fingerprints` → `{}`
- `has_completed_brick` → `True`
- `higher_timeframe_enabled` → `False`
- `history_recoveries` → `[]`
- `intrabar_entries` → `False`
- `last_exit_bar` → `0`
- `last_traded_time` → `0`
- `ltp` → `0`
- `master_regular_session` → `''`
- `master_regular_session` → `'0915-1530'`
- `message` → `'No confirmed order intent or fill.'`
- `mode` → `'PAPER'`
- `netQty` → `0`
- `order_history` → `[]`
- `position` → `{}`
- `price_fingerprints` → `{}`
- `quantity` → `0`
- `quantity_multiplier` → `1`
- `reason` → `'Confirmed market structure unavailable; entry blocked.'`
- `reason` → `'Current anti-chop assessment unavailable.'`
- `reason` → `'Current completed anti-chop evidence is unavailable.'`
- `reason` → `'Higher-timeframe RSI evidence unavailable; entry blocked.'`
- `reason` → `'One-minute/five-minute Supertrend agreement unavailable; entry blocked.'`
- `reconciliation_events` → `[]`
- `renko_confirmation` → `'CLOSE'`
- `renko_loss_range_buffer` → `0`
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
- `supertrend_timeframe` → `'5 minutes'`
- `swing_breakout_bricks` → `2`
- `telegram_valid_until` → `0`
- `timestamp` → `0`
- `trades_used` → `0`
- `trailing_basis` → `'OPTION_PREMIUM_PERCENT'`
- `trend_reentry_enabled` → `True`
- `underlying` → `''`
- `zone_entry_rearm` → `True`

## strategies/renko_supertrend/session_auto.py

[Owning source](../strategies/renko_supertrend/session_auto.py)

Versioned reference sizing. No network, runner lifecycle or order access.

### Callables and explicit defaults

- `positive(value, label)`
- `selected(config)`
- `session_spec(symbol, broker, policy)`
- `session_bounds(stamp, spec)`
- `completed_reference_bars(rows, windows, *, source_seconds, available_at)`
- `reference(session_bars, *, length, factor, available_at, input_basis)`
- `scale(ref, timeframe_seconds, spec, tick)`
- `FrozenReferences.__init__(self, path)`
- `FrozenReferences._key(self, spec, start, ref)`
- `FrozenReferences.freeze(self, spec, session_start, ref)`
- `_store_path(adapter, broker, symbol, instrument_identity=None)`
- `_dated_spec(adapter, config, day)`
- `_load_reference_inputs(adapter, config, begin, now)`
- `prepare(adapter, config, host_rows=())`
- `candle_source(original)`
- `for_observation(config, stamp, tick)`
- `apply_observation(state, config, stamp, tick)`

### Literal payload and lookup fallbacks

- `broker` → `'FYERS'`
- `count` → `0`
- `master_regular_session` → `''`

## strategies/renko_supertrend/sideways.py

[Owning source](../strategies/renko_supertrend/sideways.py)

Quick losing-position range lock; no swing history, entry signal or order route.

### Callables and explicit defaults

- `settings(payload)`
- `observe(exposure, entry_at, price, stamp, now, exit_at=None)`
- `candle_count(entry_at, exit_at, seconds)`
- `freeze(exposure, exit_at, realized, seconds, config, trade_id, underlying, cost_evidence=None)`
- `breakout(lock, price, stamp, now)`

### Literal payload and lookup fallbacks

- `sideways_enabled` → `False`
- `sideways_max_candles` → `3`

## strategies/renko_supertrend/signals.py

[Owning source](../strategies/renko_supertrend/signals.py)

### Callables and explicit defaults

- `settings(payload)`
- `supertrend_slope_observe(state, config, value, direction, atr)`
- `completed(candles)`
- `rma(state, key, value, length)`
- `ema_setup(state, close, direction, allowed, window, config=None, reversal=None, rsi=None)`
- `project_lifecycle(state, timestamp, entry_direction, reversal_direction, seconds=300, close=None, ema10=None, deadline='15:15', reset_qualification=True)`
- `Engine.__init__(self, config=None, tick_size=0.05, state=None)`
- `Engine.update(self, candle)`
- `Engine._update_candle(self, candle)`
- `series(candles, config=None, tick_size=0.05)`

### Literal payload and lookup fallbacks

- `_chart_higher_rows` → `[]`
- `_chart_rsi_rows` → `{}`
- `_chart_zone_rows` → `[]`
- `calibrated_rows` → `[]`
- `chart_host_rows` → `[]`
- `direction` → `'NEUTRAL'`
- `ema_exit_enabled` → `False`
- `ema_exit_enabled` → `True`
- `ema_exit_length` → `10`
- `ema_gaps` → `[]`
- `exit_structure_rows` → `[]`
- `intrabar_entries` → `False`
- `manual_trend_rows` → `[]`
- `renko_brick_exit_enabled` → `False`
- `session_deadline` → `'15:15'`
- `sma_closes` → `[]`
- `strategy_basis` → `'LEGACY'`
- `supertrend_timeframe` → `'5 minutes'`
- `underlying` → `''`

### Configuration literals

- `DEFAULTS = dict(**swing_breakout.DEFAULTS, **line_entry.DEFAULTS, sma_entry_enabled=False, sma_exit_enabled=False, sma_length=5, strategy_mode='SUPERTREND', spread_filter_enabled=False, trend_reentry_enabled=True, supertrend_slope_enabled=False, supertrend_slope_bars=1, supertrend_slope_min_atr=0.0, strategy_basis='LEGACY', renko_brick_exit_enabled=False, **anti_chop.DEFAULTS, **zone_entry.DEFAULTS, **calibrated.DEFAULTS, **manual_trend.DEFAULTS, **indicator_families.DEFAULTS, **INDICATOR_DEFAULTS, atr_length=5, factor=3.0, auto_sizing_policy='legacy-history-seed-v1', brick_mode='Auto', manual_brick=12.8, use_adx=False, adx_threshold=20.0, adx_length=14, adx_smoothing=14, widening_window=2, rsi_slope_enabled=True, rsi_level_enabled=False, rsi_level_mode='THRESHOLD', rsi_bullish_min=60.0, rsi_bullish_max=80.0, rsi_bearish_min=35.0, rsi_bearish_max=40.0, rsi_bullish_above=50.0, rsi_bearish_below=40.0, retest_enabled=False, retest_engulfing=True, retest_harami=True, retest_star=True)`

## strategies/renko_supertrend/source_reference.py

[Owning source](../strategies/renko_supertrend/source_reference.py)

Test-only evaluator of the arithmetic statements in the supplied Pine source.

### Callables and explicit defaults

- `ternary(expression)`
- `rma(values, length)`
- `reference(candles, config, tick=0.05)`

### Literal payload and lookup fallbacks

- `direction` → `1`

## strategies/renko_supertrend/stop_recovery.py

[Owning source](../strategies/renko_supertrend/stop_recovery.py)

Fail-closed identity for continuing an already-authorized Paper Stop only.

### Callables and explicit defaults

- `paper_stop_identity(state)`
- `eligible(state)`

### Literal payload and lookup fallbacks

- `execution_route` → `'OPTIONS'`
- `order_history` → `[]`

## strategies/renko_supertrend/stream.py

[Owning source](../strategies/renko_supertrend/stream.py)

Read-only browser stream and isolated FYERS order notifications.

### Callables and explicit defaults

- `IndependentOrderSocket.__new__(cls, *args, **kwargs)`
- `IndependentOrderSocket._FyersOrderSocket__on_open(self, ws)`
- `IndependentOrderSocket._FyersOrderSocket__on_close(self, ws, close_code=None, close_reason=None)`
- `QuietLogger.__getattr__(self, name)`
- `OrderNotifications.__init__(self, runner, wake, log_path)`
- `OrderNotifications.start(self)`
- `OrderNotifications.recover(self)`
- `OrderNotifications.snapshot(self)`
- `BrowserSnapshotCache.__init__(self, snapshot, clock=time.time)`
- `BrowserSnapshotCache.refresh(self)`
- `BrowserSnapshotCache.read(self, now)`
- `recover_chart_candles(broker, config, now)`
- `browser_snapshot(runner, now)`
- `browser_managers(runners, now)`
- `browser_frame(runner, broker, config, order_stream, now=None)`

### Literal payload and lookup fallbacks

- `intrabar_entries` → `False`
- `master_regular_session` → `''`

## strategies/renko_supertrend/swing_breakout.py

[Owning source](../strategies/renko_supertrend/swing_breakout.py)

Causal Renko close swings, confirmed by two completed closes on each side.

### Callables and explicit defaults

- `enabled(config)`
- `settings(payload)`
- `observe(state, brick, config)`
- `check(config, signal, direction)`

### Literal payload and lookup fallbacks

- `last` → `{}`
- `reason` → `'WAITING_CONFIRMED_RENKO_SWING'`
- `sides` → `{}`
- `swing_breakout_bricks` → `2`

### Configuration literals

- `DEFAULTS = {'swing_breakout_bricks': 2}`

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

## strategies/renko_supertrend/trend_reentry.py

[Owning source](../strategies/renko_supertrend/trend_reentry.py)

Promote a fresh completed trend brick after Start or an actual exit.

### Callables and explicit defaults

- `apply(state, signal, *, allow_pending_entry=False)`

### Literal payload and lookup fallbacks

- `eligible_since` → `0`
- `last_exit_bar` → `0`
- `order_history` → `[]`
- `started_at` → `0`
- `timestamp` → `0`
- `trend_reentry_after` → `0`
- `trend_reentry_enabled` → `True`
- `updated_at` → `0`

## strategies/renko_supertrend/zone_entry.py

[Owning source](../strategies/renko_supertrend/zone_entry.py)

Completed-five-minute opposing-zone entry clearance; no execution calls.

### Callables and explicit defaults

- `settings(payload)`
- `compatible(c)`
- `check_known(known, config, direction, price, atr)`
- `assess(rows, config, direction, price, atr, now, signal_at=None)`

### Configuration literals

- `DEFAULTS = dict(zone_entry_enabled=False, zone_entry_min_atr=1.0, zone_entry_rearm=True)`

## strategies/renko_supertrend/zone_target.py

[Owning source](../strategies/renko_supertrend/zone_target.py)

Optional completed-5m opposing-zone exit. Pure OHLC evidence; no execution.

### Callables and explicit defaults

- `settings(payload)`
- `validate(rows)`
- `zones(rows, timeline=None)`
- `assess(rows, position, now)`
- `assess_known(c, previous, known, position, now)`

### Literal payload and lookup fallbacks

- `zone_target_enabled` → `False`

## analysis-jobs.js

[Owning source](../analysis-jobs.js)

### Named functions

`accountID`, `accountName`, `button`, `cancel`, `createClient`, `eligible`, `isLatest`, `jobsURL`, `jobsViewAllowed`, `loadOlder`, `mount`, `openJobs`, `read`, `references`, `refresh`, `remember`, `render`, `renderSavedAnalysis`, `restore`, `savedOutputOrder`, `showOutput`, `visibleRecords`, `watch`

### UI field and toggle identifiers

`runner-jobs`, `saved-analysis-report-style`, `saved-job-report`, `saved-jobs-fullpage-style`

## analysis-trailing.js

[Owning source](../analysis-trailing.js)

### Named functions

`account`, `eligible`, `endpoint`, `mount`, `owns`, `protectable`, `refreshAccounts`, `render`, `restore`, `source`, `start`, `supported`

## broker-account-options.js

[Owning source](../broker-account-options.js)

### Named functions

`accountSelection`, `apply`, `attempt`, `choices`, `fill`, `load`, `preferredChartAccount`, `retryInventory`, `sectorSelection`

### UI field and toggle identifiers

`configured-broker-accounts`

## broker-connection-status.js

[Owning source](../broker-connection-status.js)

### Named functions

`alreadyPrompted`, `clearPrompt`, `connectionSelection`, `fyersConnect`, `offerReauthentication`, `promptKey`, `selection`, `update`

### UI field and toggle identifiers

`broker-status-hidden-style`, `selected-broker-connect`, `selected-broker-connection`

## broker-connection-test.js

[Owning source](../broker-connection-test.js)

### Named functions

`testConnection`

## broker-form-routing.js

[Owning source](../broker-form-routing.js)

### Named functions

`account`, `brokerSwitchUrl`, `initial`, `kind`, `onChange`, `presentation`, `remember`, `renkoSwitchUrl`, `route`, `scopedFetch`, `setAccounts`

### UI field and toggle identifiers

`ema-band-max-trades`

## chart-renko-sizing.js

[Owning source](../chart-renko-sizing.js)

### Named functions

`renkoPercentageSize`

## chart-renko-study-alignment.js

[Owning source](../chart-renko-study-alignment.js)

### Named functions

`alignRenkoStudyPlots`, `applyConfirmedRenkoStudyTail`, `applyRenkoStudyPublication`, `calculateRenkoTimeframeStudy`, `closeRenkoProjection`, `renkoStudyClock`, `renkoStudyPublication`

## chart-renko-volume.js

[Owning source](../chart-renko-volume.js)

### Named functions

`withRenkoVolume`

## chart-trade-ticket.js

[Owning source](../chart-trade-ticket.js)

### Named functions

`aligned`, `canonical`, `checkStatus`, `compare`, `configurePriceUnit`, `decimal`, `equal`, `format`, `fromTicks`, `invalidate`, `level`, `mount`, `parts`, `payload`, `publishStatus`, `rewardRisk`, `setBusy`, `showCancellation`, `showLevel`, `snap`, `stopStatus`, `summarize`, `ticks`

## chart-trading.js

[Owning source](../chart-trading.js)

### Named functions

`cancelPick`, `clearLines`, `markerState`, `mount`, `paint`, `refreshButtons`, `release`, `request`

## chart-workspace-studies.js

[Owning source](../chart-workspace-studies.js)

### Named functions

`accumulateVolumeDelta`, `accumulationDistribution`, `aggregatePivotCandles`, `alignRenkoStudyPlots`, `alma`, `anchoredTwap`, `anchoredVwap`, `annualizedDailyVariance`, `applyConfirmedRenkoStudyTail`, `applyRenkoStudyPublication`, `atr`, `autoVwapStart`, `bollinger`, `calculateRenkoTimeframeStudy`, `cci`, `chartCsv`, `closeRenkoProjection`, `closeVolatility`, `cmo`, `cog`, `compilePine`, `directionalMovement`, `ema`, `fixedRangeVolumeProfile`, `gridPosition`, `hma`, `linearRegression`, `macd`, `median`, `mergeLiveCandles`, `moneyFlowIndex`, `movingAverage`, `movingAverageCross`, `movingAverageOscillator`, `obv`, `pairedPriceStudy`, `percentRank`, `pineArguments`, `pineArithmetic`, `pineConditional`, `pineExpression`, `pineInputStatusLine`, `pineKeltner`, `pineLength`, `pineLogic`, `pineNamedInputStatusLines`, `pinePlotOptions`, `pineString`, `pineVwap`, `pivotValue`, `previousShadowPeriods`, `pringSpecialK`, `publish`, `rangePercent`, `renko`, `renkoAtrSize`, `renkoPercentageSize`, `renkoStudyClock`, `renkoStudyPublication`, `rma`, `rollingDeviation`, `rollingExtreme`, `rollingPearson`, `rsi`, `shadowOscillators`, `shadowRangeHistory`, `shadowRanges`, `shiftStudyPlots`, `sma`, `smaWithGaps`, `smoothedStudy`, `standardPivotLevels`, `standardPivotPeriods`, `stochastic`, `supertrend`, `swma`, `technicalRatings`, `tradeDeltaPlots`, `trueRange`, `v1ExtraZones`, `v1ReferenceRanges`, `v1TargetPrices`, `v1TargetStates`, `volumeDeltaPlots`, `volumeIndex`, `vwapPeriodKey`, `vwma`, `withRenkoVolume`, `wma`, `woodiesCciColors`, `woodiesCciValues`, `zigZagPlots`

## chart-workspace.js

[Owning source](../chart-workspace.js)

### Named functions

`activeComparisons`, `addBuiltInIndicator`, `addCatalogPineIndicator`, `addChart`, `addLevel`, `addNavigation`, `addPaneCaption`, `addSingleAnchorLine`, `addSymbolPageButton`, `addWatchlistEntry`, `advanceBarReplay`, `aggregateYahooMonths`, `aiRenkoPineSource`, `alignConfirmedStudyPlots`, `alternatePineReferenceSymbol`, `alternateStudyCandleEnd`, `alternateStudyLiveCandle`, `alternateStudySymbol`, `appendPineTables`, `applyAiRuntimeMarkers`, `applyCalendarDatePreset`, `applyCanvasColors`, `applyChartTemplateStudies`, `applyDatePreset`, `applyHorizontalVisibility`, `applyPineBottomHeight`, `applyPineFloatingBounds`, `applySelectedLineStyle`, `areaSeriesStyle`, `armBarReplay`, `arrowMarkerDimensions`, `attachDemonstrationCursor`, `attachMainPaneResize`, `attachPinePriceOverlay`, `attachRatingsTable`, `attachSessionBreaks`, `attachStudyProjection`, `attachTargetBands`, `balancePaneHeight`, `barStyle`, `baselineSeriesStyle`, `baselineStyle`, `beginStudyTabNavigation`, `beginTemporaryMeasurement`, `bindCompactDrawingControls`, `bindDrawingDockHandle`, `bindSecondaryPaneResize`, `bindYahooTickerSearch`, `boundary`, `bringDrawingPricesIntoView`, `brokerJson`, `calculationInterval`, `calendarLiveWithPrefix`, `calendarPresetStart`, `canReplacePineDraft`, `canSetStudyDefaults`, `cancelDhanSymbolSearch`, `cancelPendingPineStudy`, `candleEnd`, `candleHistoryDetail`, `candleStyle`, `canvasColor`, `catalogTickSize`, `change`, `changePineFontSize`, `channelBounds`, `channelExtendsRight`, `chartCanvasLayout`, `chartDisplayTicker`, `chartExportName`, `chartGestureActive`, `chartGridMode`, `chartGridOptions`, `chartHistoryRetryAfter`, `chartQuery`, `chartRangeToLatest`, `chartRenkoBricks`, `chartSettings`, `chartSymbol`, `chartTableCells`, `chartTickSize`, `chartTickTimestamp`, `chartTime`, `chartToolbarIcon`, `chartTypeFavoritesKey`, `chartWatermark`, `clearChartLiveTimer`, `clearCharts`, `clearComparisons`, `clearDataWindowPin`, `clearFavoriteDropTarget`, `clearInstrumentData`, `clearIntervalDropTarget`, `closeStudySettings`, `compactChartDraft`, `compactDeltaInstrumentDescription`, `comparisonClose`, `comparisonCursorReading`, `comparisonDisplay`, `comparisonHidden`, `comparisonLineOptions`, `comparisonMode`, `comparisonReturn`, `comparisonStroke`, `comparisonStyleControl`, `comparisonSymbols`, `comparisonUsesPanes`, `completedRenkoCandles`, `configuredCalculationInterval`, `configuredRatingInterval`, `coordinateTime`, `createPanel`, `crosshairAppearance`, `crosshairMode`, `cumulativeDeltaAnchor`, `currentManualPriceRange`, `cursorMode`, `cursorOptions`, `dateAt`, `defaultChartStudy`, `deltaBucketStart`, `deltaCandleConfirmationExpired`, `deltaExpiryDate`, `deltaFormingFromNative`, `deltaPineInstrumentType`, `deltaPineReferenceSymbol`, `deltaReplayHistoryWindow`, `dhanPineHostTicker`, `dhanPineInstrumentType`, `discover`, `displayMask`, `distinctDrawingBricks`, `downloadChart`, `draw`, `drawAnchoredShape`, `drawArc`, `drawArrowMarker`, `drawCurve`, `drawFibChannel`, `drawFibSpeedArcs`, `drawFibSpeedFan`, `drawFibSpiral`, `drawFibTimeZones`, `drawFlatChannel`, `drawGannBox`, `drawGannFan`, `drawGannSquare`, `drawLegend`, `drawPineBoxText`, `drawPineLabel`, `drawPineMarker`, `drawPinePolyline`, `drawPitchfan`, `drawPitchfork`, `drawRotatedRectangle`, `drawSegments`, `drawShadow`, `drawSineLine`, `drawStandardPivots`, `drawTimeCycles`, `drawTriangle`, `drawV1ExtraZones`, `drawingCoordinateEditors`, `drawingDockBounds`, `drawingDockOffset`, `drawingEndpoint`, `drawingExtensionEnabled`, `drawingExtensionUpdate`, `drawingFavorites`, `drawingFavoritesKey`, `drawingForecastState`, `drawingIntervalPreset`, `drawingManagerAction`, `drawingNumberEditor`, `drawingPrice`, `drawingShownOnCurrentInterval`, `drawingSnapshot`, `drawingStrokeColor`, `drawingStyleDefaults`, `drawingStyleToolbarBottom`, `drawingVisibleOnInterval`, `duplicateDrawings`, `editDrawing`, `editPineBrackets`, `ensureSources`, `exitBarReplay`, `exportChart`, `fetchOlderHistory`, `fibArcLevelStyle`, `fibFanGridStyle`, `fibLabelHorizontalPosition`, `fibLevelPrice`, `fibWedgeAngles`, `filterCommands`, `filterDrawingList`, `finish`, `finishStudyTabNavigation`, `finishVertexDrawing`, `focusChartSymbolSearch`, `focusFavorite`, `focusIndicatorSymbolInput`, `focusYahooTicker`, `forecastAnchor`, `forecastDrawingLogical`, `forecastEndpoint`, `forecastLabelStyle`, `formatBarCountdown`, `formingVolumeDeltaIntrabar`, `freehandStyle`, `freezePriceRange`, `fyersFormingLiveBar`, `fyersHistorySnapshot`, `gannSquareLine`, `gannSquareSettings`, `ghostFeedDefaults`, `ghostFeedPath`, `goToDate`, `gridOpacity`, `gridStroke`, `hasDrawings`, `heikinAshiBar`, `heikinTailUpdateAllowed`, `highlightPine`, `historyIntervals`, `hlcColor`, `hlcStyle`, `horizontalLevelStyle`, `horizontalRaySpan`, `horizontalVisibility`, `hydratePineRevisions`, `importWatchlist`, `indentPineLines`, `indexAt`, `indicatorArguments`, `indicatorAvailable`, `indicatorFavoritesKey`, `indicatorLegendCollapsed`, `indicatorLineStyleControl`, `indicatorOpensInPane`, `indicatorPaneAt`, `indicatorReferenceLevels`, `indicatorSearchScore`, `insertPineNewline`, `insertPineSymbol`, `inspect`, `inspectComparisonLegend`, `interpolatedBarCoordinate`, `intervalUnavailableReason`, `intervalUnit`, `isPineArrowPlot`, `isPinePriceLabel`, `jumpToPineLine`, `kagiBars`, `kagiFixedReversal`, `latestCompletedChartTime`, `layoutAction`, `layoutMessage`, `legendPlotReadings`, `levelMessage`, `lineBreakBars`, `lineBreakCount`, `lineExtension`, `lineSeriesStyle`, `lineStyleTargets`, `liveFeedAge`, `liveFeedPresentation`, `load`, `loadAlternatePineReference`, `loadBrokerSymbolResults`, `loadComparison`, `loadDhanInstrumentMetadata`, `loadFyersTickSize`, `loadHistory`, `loadHistoryBefore`, `loadMissingStudyHistory`, `loadMotilalInstrumentMetadata`, `loadOlderHistory`, `loadOlderVolumeDeltaHistory`, `loadPineCandles`, `loadPineLiveFrame`, `loadReferencedHistoryThrough`, `loadReplayComparison`, `loadYahooCapabilities`, `localDayStart`, `localMinute`, `locateDrawing`, `locateHorizontalLine`, `lockedPriceRatio`, `mainPaneHeight`, `matchIndicator`, `matchWatchlistCatalog`, `matchingChartBars`, `mcxSessionEnd`, `measurementDuration`, `measurementPrice`, `measurementTime`, `measurementVolume`, `mergeComparisonHistory`, `mergeLatestChartDrawings`, `mergePineOverlayPlots`, `mergeSavedDrawings`, `motilalPineHostTicker`, `motilalPineInstrumentType`, `motilalSearchSegment`, `mountMainChart`, `moveFavorite`, `moveHorizontalLevel`, `moveIntervalFavorite`, `movePatternProjection`, `moveWatchlistSymbol`, `nextCandleStart`, `normalizePineDrawingCoordinates`, `normalizedDrawingShortcut`, `open`, `openAiRenkoSupertrend`, `openAppliedPineScript`, `openAuthorized`, `openChartContext`, `openChartQuickSearch`, `openHorizontalLineStyle`, `openIndicatorSymbolPicker`, `openPicker`, `openPineGoToLine`, `openRenkoSettings`, `openYahooPineReference`, `organizeDrawingSettings`, `outsideRegularChartHours`, `paint`, `paintAnnotationMark`, `paintBarReplay`, `paintBarsPattern`, `paintChartTable`, `paintComparisonReading`, `paintDrawingLabel`, `paintDrawingSelection`, `paintFanRays`, `paintFreehand`, `paintGhostFeed`, `paintGhostFeedPath`, `paintLinkedAnnotation`, `paintPattern`, `paintSector`, `paintSnapshotTables`, `paintStyledTrendLine`, `paintTrendLineMarkers`, `paintWatchlistQuote`, `parseIntervalShortcut`, `pauseBarReplay`, `permitted`, `persistLayouts`, `persistWatchlists`, `pineApplyTarget`, `pineBoundedCalendarPrefix`, `pineCanReplay`, `pineCandleRowsForWindow`, `pineCandleWindowForEvaluation`, `pineChartFrame`, `pineChartRestriction`, `pineChartType`, `pineDiagnosticLine`, `pineDraftState`, `pineDrawingStyleControls`, `pineEditorCompletion`, `pineFloatingBounds`, `pineIndicatorFavoriteKind`, `pineIndicatorLibraryKey`, `pineIndicatorOptions`, `pineIntradayWindow`, `pineLabelTooltipGroup`, `pineLegendMessage`, `pineLiteralAt`, `pineLiveResetRequired`, `pinePlotEntries`, `pinePlotMetadata`, `pinePlotsChangeAtTail`, `pineReferenceRetryDelay`, `pineRevisionDatabase`, `pineRevisionTitle`, `pineSelectedLines`, `pineStylePlotEntries`, `pineSymbolInfo`, `pineSyntheticHostBar`, `pineTableScrollPosition`, `pineUsesPricePane`, `pineUsesWorkerFeatures`, `pineWorkerUsesPane`, `pivotTimeframe`, `placementSelect`, `plainTextStyle`, `plotColorInputValue`, `plotColorSwatch`, `plotStyleControls`, `point`, `pollComparison`, `pollLive`, `positionDrawingFavorites`, `positionDrawingStyleToolbar`, `positionForecastState`, `positionPineTables`, `positionSizing`, `prefetchPineHistory`, `prepareChartImage`, `preserveCopiedPineStudies`, `priceHistoryDetail`, `pricePaneDockPlacement`, `pricePoint`, `priceRangeContext`, `priceRangeForRatio`, `priceScaleMargins`, `priceScaleMode`, `profileBarSegment`, `profileColor`, `profileHitTest`, `profileResolution`, `profileSourceCandles`, `projectionIntervalSeconds`, `provisionalStatus`, `publishActiveSource`, `publishWorkerPineResult`, `ratingTableIntervals`, `ratingTableUsesForming`, `ratingTimeframeChoices`, `readDrawingClipboard`, `reconcileHistory`, `recordDrawingEdit`, `recordWatchlistFrame`, `redrawDrawings`, `redrawKeepingViewport`, `redrawSyntheticSettings`, `referenceLevelControls`, `refreshAlternateStudyBars`, `refreshCompletedHistory`, `refreshDeltaCatalog`, `refreshLiveStudyBars`, `refreshSavedDrawings`, `refreshSharedPineCatalog`, `refreshTickDelta`, `refreshWatchlistQuote`, `rememberAppliedPineIndicators`, `rememberManualPriceRange`, `rememberMotilalPineInstrument`, `rememberNcdexSessions`, `rememberReplayPosition`, `removablePickerIndicator`, `removeHorizontalLevel`, `removePickerIndicatorButton`, `removeSelectedLines`, `removeUnlockedDrawings`, `removeUnlockedLevel`, `removedPickerIndicators`, `render`, `renderBrokerSymbolResults`, `renderDrawingFavorites`, `renderFavoriteChartTypes`, `renderFills`, `renderIntervals`, `renderLiveRows`, `renderPicker`, `renderRecentSymbols`, `renderStudyTemplates`, `renderSymbolResults`, `renderWatchlist`, `renkoAnchorAtIndex`, `renkoAnchorIndex`, `renkoBoxSize`, `renkoBrickStatus`, `renkoCalculationRestartRequired`, `renkoOrderedPath`, `renkoPercentClose`, `renkoProjectedAnchor`, `renkoProjectionReplaced`, `renkoProjectionStyle`, `renkoSourceGeometryChanged`, `renkoVolumeProfileCandles`, `renkoWicksVisible`, `reorderDrawing`, `replacePineText`, `replayCandleEnd`, `replayEarlierHistoryMessage`, `replayFromDate`, `replayFromFirstBar`, `replayFromRandomBar`, `replayPausesStudy`, `replayPineCandles`, `replayPineHistory`, `replayPositionKey`, `reportAppliedPine`, `requestChartHistory`, `requestOlderChartCandles`, `requestPaint`, `requestedComparisonMode`, `reselectReplayBar`, `reserveStudyLegendValue`, `resetBarReplay`, `resetChartPaneHeights`, `resetDrawingHistory`, `resetStudyTemplateReplacement`, `resolveWallTime`, `resolveWatchlistEntry`, `restore`, `restoreChartTypeFavorites`, `restoreComparisonPaneLayout`, `restoreDeltaCatalog`, `restoreDrawingEdit`, `restoreDrawingStyleDefaults`, `restoreIndicatorFavorites`, `restoreIntervalList`, `restoreLayouts`, `restorePineDraftTarget`, `restoreSharedViewport`, `restoreStudyDefaults`, `restoreWatchlists`, `restoreWorkerPine`, `restoredManualPriceRange`, `resumeBarReplay`, `retryChartAuthWhenVisible`, `revealStudyPlacement`, `runChartPine`, `runChartPineOnce`, `sameCandle`, `sameRenkoBrick`, `save`, `saveChartImage`, `saveDrawingFavorites`, `saveIndicatorFavorites`, `saveIntervalList`, `saveScriptRevision`, `saveSharedDrawings`, `saveVisibleViewport`, `saveWatchlistEntries`, `savedChartDraft`, `savedReplayPosition`, `scheduleChartAuthRetry`, `schedulePineMinimap`, `scriptRevisions`, `secondaryPaneCollapse`, `secondaryPaneDivider`, `selectChartSettingsTab`, `selectChartSymbol`, `selectInterval`, `selectLineStyle`, `selectReplayBar`, `selectTypedInterval`, `selectedPriceSource`, `selectedStudyTemplate`, `sessionBreakStyle`, `setChartSymbol`, `setControls`, `setDrawingStyleDefaults`, `setFeedStatus`, `setFrame`, `setHorizontalVisibility`, `setLinePlacement`, `setPickerIndicatorRemoved`, `setReplayTimer`, `setStudyPlacement`, `shadowHistory`, `sharedComparisonScale`, `sharedSectorPulseV1`, `showBrokerPineScripts`, `showLayouts`, `showLevels`, `showScriptDiagnostic`, `showScriptRevisions`, `singleStudyPlotColor`, `snapshotLayout`, `sortWatchlistRows`, `sourceInterval`, `sourceSelect`, `startChartFyersReconnect`, `stopWatchlistQuotes`, `studyAllowsPlacement`, `studyCalculationBars`, `studyCalculationChoices`, `studyCalculationLiveBar`, `studyCanAffectPriceScale`, `studyCanUseFormingBar`, `studyDefaultFields`, `studyDefaultsKey`, `studyEnabledOnInterval`, `studyInSeparatePane`, `studyInputs`, `studyIntervalControls`, `studyIntervalGroup`, `studyLabel`, `studyLegendPlotsForPane`, `studyLegendValuesVisible`, `studyMinimumHistoryNotice`, `studyPaneTargets`, `studyRequiresVolume`, `studySymbolHistory`, `studyTemplates`, `studyTimeframeLabel`, `studyUsesFormingBar`, `studyVisible`, `styledPricePoint`, `switchDatePresetInterval`, `switchReplayInterval`, `syncCanvasControls`, `syncEditor`, `syncEditorWrap`, `syncHlcControls`, `syncInstrumentDescription`, `syncInstrumentTitle`, `syncLineColorMode`, `syncNavigationButtons`, `syncPaneButtons`, `syncPaneSeparator`, `syncPineApplyButton`, `syncPineEditorPlacement`, `syncPineFontSize`, `syncPineMinimap`, `syncPineTableControls`, `syncPriceScaleButtons`, `syncPriceScaleMenu`, `syncSelectedLineStyle`, `syncSessionBreakControls`, `syncSourcePicker`, `syncStatusLine`, `syncStudyTemplateActions`, `syncSymbolFilterReset`, `syncWatchlistColumns`, `targetControls`, `tickDeltaSupported`, `timeChartRenkoAnchorLogical`, `togglePineComments`, `togglePriceScaleMode`, `toggleSelectedLineLock`, `tradeChartWaitingMessage`, `translateDrawing`, `trendLineSegment`, `trendStatsText`, `twapAnchor`, `twapBrokerAnchorKey`, `twapReferenceInterval`, `update`, `updateActiveWatchlistQuote`, `updateBarCountdown`, `updateChartClock`, `updateChartVenue`, `updateComparisonLegend`, `updateComparisonSeries`, `updateCursorControls`, `updateDataWindowPin`, `updateDrawingFavoriteStar`, `updateDrawingGroupControl`, `updateDrawingStyles`, `updateDrawingToolbar`, `updateHorizontalStyle`, `updatePineMinimapWindow`, `updatePineTables`, `updatePreview`, `updatePriceChartLegend`, `updateReferenceTableVisibility`, `updateRenkoBoxReadout`, `updateReplayControls`, `updateReplayStatus`, `updateScriptPosition`, `updateScriptRevisions`, `usesTickDelta`, `v1SessionBounds`, `validComparisonSymbols`, `validDrawings`, `validFlatChannel`, `validGhostFeedPath`, `validatePine`, `viewportAnchor`, `visiblePlotColor`, `visiblePriceBounds`, `visibleWatchlistColumns`, `volumeDeltaInterval`, `volumeDeltaIntrabarUsable`, `volumeProfileOptions`, `volumeProfileStyleControls`, `volumeUnavailable`, `waitForChartRetry`, `wantsFormingWeeklyRange`, `watchlistQuotePrices`, `withDrawingIntervalPreset`, `workerInputControls`, `workerPineSymbolInfo`, `writeStudyTemplates`, `yahooPineReferenceClose`, `zoneFormat`, `zoneOffset`

### UI field and toggle identifiers

`sp-chart-active-indicators`, `sp-chart-drawing-list`, `sp-chart-drawing-toolbar`, `sp-chart-feed-details`, `sp-chart-pine-draft`, `sp-chart-settings-canvas`, `sp-chart-settings-renko`, `sp-chart-settings-status`, `sp-chart-settings-symbol`, `sp-chart-settings-tab-canvas`, `sp-chart-settings-tab-renko`, `sp-chart-settings-tab-status`, `sp-chart-settings-tab-symbol`, `sp-chart-template-preview`, `sp-fib-level-help`, `sp-pine-suggestions`, `sp-pine-yahoo-status`, `sp-pine-yahoo-symbols`, `sp-pitchfork-level-help`, `sp-reference-tables`, `sp-symbol-search-title`, `sp-yahoo-search-status`, `sp-yahoo-symbols`

## closed-pnl.js

[Owning source](../closed-pnl.js)

### Named functions

`build`, `children`, `draw`, `label`, `load`, `pump`, `render`, `setTotal`, `table`

## dashboard-enhancements.js

[Owning source](../dashboard-enhancements.js)

### Named functions

`renderPaperFunds`

### UI field and toggle identifiers

`account-state`, `add-screener`, `ai-review-state`, `allocate-screener-selected`, `analysis-board`, `analysis-exclusions`, `analysis-panel`, `analysis-refresh-interval`, `analysis-status`, `analyze-screener-options`, `analyze-screeners`, `auto-ack`, `auto-completed`, `auto-cooldown`, `auto-daily-loss`, `auto-enabled`, `auto-end`, `auto-idea-risk`, `auto-index-underlyings`, `auto-kill`, `auto-limit-buffer`, `auto-max-dte`, `auto-max-orders`, `auto-max-positions`, `auto-max-spread`, `auto-min-dte`, `auto-min-rr`, `auto-mode`, `auto-option-evidence`, `auto-order-type`, `auto-planning-capital`, `auto-preview`, `auto-review`, `auto-risk-defined`, `auto-risk-reserve`, `auto-segments`, `auto-signals`, `auto-stale`, `auto-start`, `auto-status`, `auto-strategies`, `auto-symbols`, `auto-target`, `auto-uncertain`, `auto-universe`, `broker`, `broker-dot`, `broker-state`, `candidate-batch-actions`, `candidate-list`, `candidate-status`, `cash-product-choice`, `clear-candidate-selection`, `closed-pnl`, `closed-pnl-label`, `closed-positions`, `closed-summary`, `collect-candidates`, `confirm-funds`, `confirm-nifty-straddle-squareoff`, `confirm-straddle-squareoff`, `constituent-workflow`, `copy-packet`, `daily-loss-limit`, `download-packet`, `ema-band`, `ema-band-broker-chart`, `ema-band-chart-bars`, `ema-band-chart-timeframe`, `ema-band-confirmation`, `ema-band-contract`, `ema-band-cooldown`, `ema-band-direction`, `ema-band-execution-log`, `ema-band-length`, `ema-band-lots`, `ema-band-master-refresh`, `ema-band-master-status`, `ema-band-minimum-slope-atr`, `ema-band-mode`, `ema-band-mode-status`, `ema-band-paper-capital`, `ema-band-pnl-chart`, `ema-band-position-cards`, `ema-band-profit-protection-pct`, `ema-band-resistance-volume-exit`, `ema-band-resistance-volume-lookback`, `ema-band-resistance-volume-multiple`, `ema-band-runner-status`, `ema-band-runner-toggle`, `ema-band-search`, `ema-band-segment`, `ema-band-session`, `ema-band-slope-lookback`, `ema-band-status`, `ema-band-stop-pct`, `ema-band-strategy-direction`, `ema-band-target-pct`, `ema-band-ticket-preview`, `ema-band-timeframe`, `ema-band-tracked-positions`, `ema-band-underlying`, `ema-band-underlying-picker`, `ema-band-underlying-search`, `enforce-risk-controls`, `estimated-charges`, `estimated-charges-note`, `estimated-net-pnl`, `external-open-risk`, `funds`, `handoff`, `handoff-allocation-budget`, `handoff-batch-broker`, `handoff-batch-confirmation`, `handoff-batch-external-risk`, `handoff-batch-panel`, `handoff-batch-preview`, `handoff-batch-review`, `handoff-batch-status`, `handoff-budget-label`, `handoff-option-lots`, `handoff-option-lots-field`, `idea-risk-limit`, `include-funds`, `kama`, `kama-breakout`, `kama-capability`, `kama-chart`, `kama-chart-type`, `kama-cooldown`, `kama-efficiency`, `kama-events`, `kama-execution-mode`, `kama-exit-session`, `kama-fast`, `kama-idea-risk`, `kama-invalidation`, `kama-invalidation-help`, `kama-length`, `kama-minimum-slope-atr`, `kama-mode`, `kama-paper-capital`, `kama-policy`, `kama-quantity`, `kama-reclaims`, `kama-refresh-interval`, `kama-runner-status`, `kama-runner-toggle`, `kama-size-help`, `kama-slope-lookback`, `kama-slow`, `kama-state`, `kama-timeframe`, `kama-trade-rows`, `kama-trade-summary`, `kama-underlying`, `kama-underlying-search`, `kama-underlying-status`, `live-pnl`, `market-overview`, `max-positions`, `minimum-rr`, `nifty-premium-chart`, `nifty-straddle`, `nifty-straddle-action-status`, `nifty-straddle-contract`, `nifty-straddle-entry-end`, `nifty-straddle-entry-start`, `nifty-straddle-lots`, `nifty-straddle-options`, `nifty-straddle-output`, `nifty-straddle-position`, `nifty-straddle-runner-state`, `nifty-straddle-squareoff-confirmation`, `nifty-straddle-squareoff-preview`, `nifty-straddle-squareoff-review`, `nifty-straddle-stoploss`, `nifty-straddle-tab`, `nifty-straddle-target`, `nifty-straddle-trades`, `nifty-straddle-updated`, `open-count`, `open-positions`, `order-type`, `packet-panel`, `packet-preview`, `packet-status`, `parser-lifecycle-refresh`, `parser-lifecycle-status`, `parser-native-budget`, `parser-native-confirm`, `parser-native-confirm-field`, `parser-native-mode`, `parser-native-mode-fields`, `parser-native-preview`, `parser-native-review`, `parser-native-submit`, `parser-protect`, `parser-protection-target`, `pipeline-kicker`, `pipeline-message`, `pipeline-track`, `planning-capital`, `policy-impact`, `policy-validation`, `premium-chart`, `premium-chart-updated`, `prepare-handoff-batch`, `prepare-packet`, `prepare-screener-order`, `prepare-ticket`, `preview-auto-policy`, `reauth`, `reauth-help`, `refresh-pipeline`, `refresh-screeners`, `risk-reserve`, `risk-strip`, `save-auto-draft`, `save-auto-policy`, `screener`, `screener-allocation-budget`, `screener-analysis`, `screener-analysis-next`, `screener-analysis-results`, `screener-analysis-status`, `screener-batch-selection`, `screener-bulk-selection`, `screener-clear-selection`, `screener-label`, `screener-options`, `screener-options-results`, `screener-options-status`, `screener-order`, `screener-order-broker`, `screener-order-confirmation`, `screener-order-external-risk`, `screener-order-preview`, `screener-order-product`, `screener-order-review`, `screener-order-status`, `screener-route-preview-groups`, `screener-select-all`, `screener-selected-count`, `screener-sources`, `screener-status`, `screener-url`, `screener-watchlist`, `screener-watchlist-results`, `sector-body`, `sector-detail`, `sector-filter`, `sector-sort`, `sectors`, `select-all-candidates`, `sensex-straddle`, `sensex-straddle-tab`, `settings`, `settings-content`, `squareoff-nifty-straddle`, `squareoff-straddle`, `start-nifty-straddle`, `start-straddle`, `stop-basis`, `stop-nifty-straddle`, `stop-straddle`, `straddle-action-status`, `straddle-contract`, `straddle-entry-end`, `straddle-entry-start`, `straddle-lots`, `straddle-options`, `straddle-output`, `straddle-position`, `straddle-runner-state`, `straddle-squareoff-confirmation`, `straddle-squareoff-preview`, `straddle-squareoff-review`, `straddle-trades`, `straddle-updated`, `straddles`, `strongest-stocks`, `submit-handoff-batch`, `submit-screener-order`, `submit-ticket`, `ticket-broker`, `ticket-capability`, `ticket-confirmation`, `ticket-lots`, `ticket-panel`, `ticket-preview`, `ticket-proposal`, `ticket-review`, `ticket-status`, `trade-parser`, `trade-parser-ai-result`, `trade-parser-clear`, `trade-parser-entry-help`, `trade-parser-entry-mode`, `trade-parser-input`, `trade-parser-limit-price`, `trade-parser-lots`, `trade-parser-ltp`, `trade-parser-order`, `trade-parser-order-status`, `trade-parser-refresh-ltp`, `trade-parser-result`, `trade-parser-run`, `trade-parser-status`, `trade-parser-submit-order`, `trade-parser-trigger-price`, `user-sections-empty`, `weight-source`

## dashboard-help.js

[Owning source](../dashboard-help.js)

## dashboard-login.js

[Owning source](../dashboard-login.js)

### Named functions

`renew`

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

## dhan-orders.js

[Owning source](../dhan-orders.js)

### Named functions

`api`, `invalidate`, `render`

## dhan-strategies.js

[Owning source](../dhan-strategies.js)

### Named functions

`base`, `bind`, `init`, `invalidate`, `payload`, `request`, `status`, `sync`

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

## fundamental-report.js

[Owning source](../fundamental-report.js)

### Named functions

`html`, `prose`

### UI field and toggle identifiers

`fundamental-report-style`

## handoff-exit-monitor.js

[Owning source](../handoff-exit-monitor.js)

### Named functions

`load`, `mount`

## handoff-level-report.js

[Owning source](../handoff-level-report.js)

### Named functions

`complete`, `html`, `legacy`, `outcomesHtml`, `rejectionHtml`, `reveal`, `rows`

### UI field and toggle identifiers

`handoff-level-report-style`

## handoff-schedule.js

[Owning source](../handoff-schedule.js)

### Named functions

`api`, `invalidateManual`, `mount`, `policyPayload`, `refresh`, `render`, `renderManualPreview`, `renderOpportunities`, `reportDeliveryText`, `request`, `save`

### UI field and toggle identifiers

`handoff-schedule-layout`

## handoff-screener.js

[Owning source](../handoff-screener.js)

### Named functions

`csrf`, `load`, `mount`, `paint`, `refreshAuto`, `request`, `save`, `scheduleRequest`, `scopeScreener`, `showAuto`

## holdings-portfolio.js

[Owning source](../holdings-portfolio.js)

### Named functions

`aggregate`, `apply`, `choose`, `load`, `mount`, `pie`, `save`, `state`, `update`

### UI field and toggle identifiers

`holdings-allocation`, `holdings-sector-filter`

## holdings-review-tools.js

[Owning source](../holdings-review-tools.js)

### Named functions

`closeAll`, `dialog`, `dispose`, `draw`, `holdingEmaSeries`, `line`, `openAction`, `priceChart`, `request`, `showChart`, `showInvestmentChart`

## holdings-review.js

[Owning source](../holdings-review.js)

### Named functions

`compareHoldingsPnl`, `filterHoldings`, `holdingPnlValue`, `mount`

### UI field and toggle identifiers

`holdings-analyse`, `holdings-analysis-mode`, `holdings-broker`, `holdings-cancel`, `holdings-counts`, `holdings-coverage`, `holdings-export`, `holdings-filter`, `holdings-pnl-filter`, `holdings-progress`, `holdings-rows`, `holdings-scope`, `holdings-status`

## holdings-trailing.js

[Owning source](../holdings-trailing.js)

### Named functions

`call`, `matches`, `open`, `paint`, `refresh`, `status`

### UI field and toggle identifiers

`holding-trailing-dialog`

## investment-exports.js

[Owning source](../investment-exports.js)

### Named functions

`chart`, `download`, `fields`, `report`, `workbook`, `zip`

### UI field and toggle identifiers

`rId1`

## investment.js

[Owning source](../investment.js)

### Named functions

`activate`, `card`, `clearEntryPreview`, `deliveryChoices`, `detail`, `entryRequest`, `fillDefaultBroker`, `fillDeliveryBrokers`, `growth`, `jobEvent`, `mount`, `planCell`, `pullbackCell`, `refreshEntry`, `refreshEntryControls`, `render`, `renderEntryJob`, `returnsText`, `sectorCell`, `selectionStatus`, `setBrokerOptions`, `start`

### UI field and toggle identifiers

`investment`, `investment-ai-summary`, `investment-asof`, `investment-audit`, `investment-audit-rows`, `investment-broker`, `investment-broker-status`, `investment-cap`, `investment-clear`, `investment-coverage`, `investment-default-broker`, `investment-detail`, `investment-detail-body`, `investment-detail-close`, `investment-detail-title`, `investment-distance`, `investment-entry-actions`, `investment-entry-confirmation`, `investment-entry-enable`, `investment-entry-fields`, `investment-entry-level`, `investment-entry-phrase`, `investment-entry-preview`, `investment-entry-quantity`, `investment-entry-status`, `investment-entry-stop`, `investment-entry-terms`, `investment-export`, `investment-form`, `investment-holding-account`, `investment-mode`, `investment-next`, `investment-page`, `investment-period`, `investment-prev`, `investment-report`, `investment-report-status`, `investment-rows`, `investment-run`, `investment-saved`, `investment-search`, `investment-selection`, `investment-sort`, `investment-status`, `investment-stop`, `investment-symbols`, `investment-turnover`, `investment-xlsx`

## market-handoff.js

[Owning source](../market-handoff.js)

### Named functions

`button`, `el`, `load`, `mount`, `organizeHandoff`, `render`, `request`, `restoreMarketOutput`, `run`, `savedProvider`, `stopAnalysis`

### UI field and toggle identifiers

`handoff-market-analysis`, `handoff-market-symbols`, `handoff-stock-analysis`

## motilal-oswal.js

[Owning source](../motilal-oswal.js)

### Named functions

`api`, `connect`, `renderConnection`, `run`, `savedStatus`, `status`

## multi-account-orders.js

[Owning source](../multi-account-orders.js)

### Named functions

`api`, `boot`, `invalidate`, `mount`, `populate`, `prepare`, `render`, `serviceReady`

## navigation-polish.js

[Owning source](../navigation-polish.js)

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

## renko-ai-chart-markers.js

[Owning source](../renko-ai-chart-markers.js)

### Named functions

`markers`

## renko-ai-chart-source.js

[Owning source](../renko-ai-chart-source.js)

### Named functions

`context`, `request`, `verify`

## renko-ai-options.js

[Owning source](../renko-ai-options.js)

### Named functions

`chartContracts`, `chartView`, `clearInstrumentReference`, `configuration`, `drawCharts`, `hydrate`, `mount`, `refreshStatus`, `request`, `restore`, `searchAiInstruments`, `show`, `sizingContext`, `verifiedReference`

## renko-assessment.js

[Owning source](../renko-assessment.js)

### Named functions

`assessment`, `exitAssessment`

## renko-backtest.js

[Owning source](../renko-backtest.js)

### Named functions

`accept`, `download`, `draw`, `fields`, `json`, `label`, `mount`, `report`, `valueText`, `visibility`

### UI field and toggle identifiers

`rbt-download`, `rbt-from`, `rbt-period`, `rbt-to`, `renko-backtest`

## renko-engine.js

[Owning source](../renko-engine.js)

### Named functions

`applyPlots`, `canStartRunner`, `inside`, `invalidate`, `latest`, `load`, `mount`, `paintRunner`, `payload`, `request`, `resizePlot`, `route`, `search`, `selected`, `settings`, `simulate`, `startRunner`, `status`, `updateRunControl`

### UI field and toggle identifiers

`engine-account`, `engine-capital`, `engine-chart`, `engine-chart-refresh`, `engine-chart-shell`, `engine-chart-source`, `engine-chart-title`, `engine-diagnostics`, `engine-download`, `engine-earlier`, `engine-events`, `engine-execution-mode`, `engine-execution-note`, `engine-fit`, `engine-full`, `engine-history`, `engine-hover`, `engine-later`, `engine-latest`, `engine-load`, `engine-lots`, `engine-max-trades`, `engine-message`, `engine-mode-badge`, `engine-run`, `engine-runner-journal`, `engine-runner-ledger`, `engine-save`, `engine-search`, `engine-settings`, `engine-state`, `engine-stop`, `engine-symbol`, `engine-timeframe`, `engine-workspace`, `renko-engine`

## renko-supertrend.js

[Owning source](../renko-supertrend.js)

### Named functions

`acceptInspectionHover`, `activeRunnerFields`, `antiChopSettings`, `applyNamedFields`, `applyStatus`, `assessedHigherRows`, `bindChartInspection`, `bindDisplayedInstrument`, `boundChartContext`, `candleInspection`, `cashEquity`, `chartAnalysisAvailable`, `chartCandles`, `chartChoice`, `chartControl`, `chartControlState`, `chartDisplaySelection`, `chartEditorSelection`, `chartEntrySettings`, `chartFold`, `chartHistoricalEvents`, `chartHistoryBehind`, `chartPreviewPolicy`, `chartReplayAudit`, `chartSelectionForInstrument`, `chartSessionBreaks`, `chartSettings`, `chartSettingsFailure`, `chartSimulationMarkers`, `chartSourceContext`, `chartStreamHealth`, `chartStreamStatus`, `chartWheelPolicy`, `chooseBrokerRunner`, `chooseConfiguration`, `clearAnalysis`, `closeConfigOptions`, `coalescedHover`, `compactHistoryLiveHandoff`, `configurationComparisonRows`, `configurationLibrary`, `configurationState`, `configurationText`, `confirmStartConfiguration`, `connectStream`, `controls`, `costPnlValues`, `currentScopeKey`, `deleteConfiguration`, `deltaFutures`, `deltaNative`, `deltaPnl`, `deriveManualBrick`, `disclosure`, `displayedAlreadyActive`, `drawTradeTable`, `effectiveChartChoice`, `effectiveFamilySettings`, `embeddedRenkoChartUrl`, `emit`, `entryDecisionText`, `erase`, `eventTable`, `executionMarkers`, `familyControls`, `familySettings`, `feedHealthSummary`, `feedPresentation`, `fiveMinuteSupertrendPoints`, `fiveMinuteZoneRows`, `historyDelay`, `hostZones`, `indicatorControls`, `inheritRsiHtfFields`, `initializeRsiHtf`, `initializeSelectedRunner`, `inrPolicy`, `instanceList`, `invalidate`, `journalQuery`, `jumpNavigation`, `jumpToRule`, `lastKnownIndicator`, `liveChartEnabled`, `load`, `loadNamedConfiguration`, `lockActiveRunnerForm`, `managerTable`, `manualBrickKey`, `mapExecutionMarkers`, `matchInstrumentConfiguration`, `mergeChartRows`, `migrateAtrProfile`, `migrateDestinations`, `mount`, `mountChartDrawings`, `mountChartHistoryNavigation`, `mountRunnerStartPointer`, `mountSessionBreaks`, `nativeCashSessionClosed`, `onScroll`, `overrideState`, `ownedEntryPrice`, `paint`, `paintAssessment`, `paintBrickPreview`, `paintChartBasis`, `paintChartControls`, `paintConfigOptions`, `paintEntryPrice`, `paintLineEntry`, `paintLossRange`, `paintMarkers`, `paintPnl`, `paintPriceStyle`, `paintRsi`, `paintSelectedIndicators`, `paintSideways`, `paintSpreadFilter`, `paintStreamHealth`, `paintStudyHover`, `paintSupertrendPointers`, `paintThumb`, `paintTradingSessionHours`, `paintTrendReentry`, `paintUnderlyingPrice`, `paintZones`, `persistDraft`, `persistSessionSelection`, `pnlValues`, `positionAssessment`, `premiumSelectionAvailable`, `preserveJournalView`, `preservePreviousDraft`, `priceChartNeedsRefresh`, `provisionalRenkoBricks`, `readCandle`, `readDrawings`, `readableChartViewport`, `rebuildSma`, `reconcileBrokerClosure`, `recoverSilentStream`, `refreshBroker`, `refreshChartViewport`, `refreshJournal`, `releaseActiveFormLocks`, `renderCandleInspection`, `renderTradeTable`, `renderTrades`, `renkoChartSeries`, `renkoStudyPoints`, `replayQuerySettings`, `request`, `requireRsiHtfSupport`, `requireSmaSupport`, `restore`, `restoreChartStyle`, `restoredConfigurationFields`, `rsiHistory`, `rsiHtfSettings`, `rsiHtfSummary`, `rsiSma`, `rsiStep`, `rsiZone`, `runSessionAction`, `runnerChartAlignment`, `runnerChartContext`, `runnerResponseMatches`, `runnerScopeKey`, `runnerStartContext`, `save`, `saveBatchSelection`, `scopedFormFields`, `searchInstruments`, `selectedStartPayload`, `selectedStudy`, `sessionJob`, `setSimulationLabels`, `settingRow`, `sharedRunnerCharts`, `showSessionCharts`, `signalNavigation`, `signalSettings`, `smaPeriod`, `status`, `stopAllRenko`, `storeConfiguration`, `strategyEntryCheck`, `studyHoverValue`, `sync`, `syncActiveStartButtons`, `syncBatchCharts`, `syncCalibratedControls`, `syncChartControl`, `syncChartDisplay`, `syncDisplayedChartSelection`, `syncManualBrickFrames`, `syncManualTrendControls`, `syncRsiHover`, `syncSessionCharts`, `syncStudyPanes`, `syncThirdEmaControls`, `synchronizeActiveRunnerForm`, `table`, `testedNiftyDefaults`, `toggleRunner`, `toggleState`, `uniformRenkoBricks`, `universalStrategyDefaults`, `updateSessionActions`, `valid`, `volumePoints`, `writeLibrary`, `zoneBandPrimitive`, `zoneBandRect`

### UI field and toggle identifiers

`renko-`, `renko-action-error`, `renko-active-settings-note`, `renko-add-batch`, `renko-additional-slippage-points`, `renko-adopt`, `renko-adopted-managers`, `renko-adoption-reentry`, `renko-adoption-status`, `renko-adx-exit-enabled`, `renko-adx-length`, `renko-adx-smoothing`, `renko-adx-threshold`, `renko-aligned-settings-style`, `renko-anchor`, `renko-anti-chop-adaptive-window`, `renko-anti-chop-atr-average-length`, `renko-anti-chop-atr-length`, `renko-anti-chop-badge`, `renko-anti-chop-combination`, `renko-anti-chop-cross-bars`, `renko-anti-chop-ema-fast-length`, `renko-anti-chop-ema-slow-length`, `renko-anti-chop-enabled`, `renko-anti-chop-gap-atr`, `renko-anti-chop-gap-percentile`, `renko-anti-chop-mode`, `renko-anti-chop-overlap-percent`, `renko-anti-chop-overlap-percentile`, `renko-anti-chop-panel`, `renko-anti-chop-role`, `renko-anti-chop-slope-atr`, `renko-anti-chop-slope-bars`, `renko-anti-chop-slope-percentile`, `renko-anti-chop-status`, `renko-anti-chop-structure-bars`, `renko-apply-calibrated`, `renko-assessment`, `renko-assessment-wire`, `renko-atr-length`, `renko-batch-charts`, `renko-batch-help`, `renko-batch-result`, `renko-batch-summary`, `renko-batch-symbols`, `renko-box`, `renko-brick-mode`, `renko-brick-preview-status`, `renko-broker`, `renko-broker-note`, `renko-broker-orders`, `renko-broker-positions`, `renko-broker-refresh`, `renko-calibrated-enabled`, `renko-calibrated-overlap-max`, `renko-calibrated-overlap-pairs`, `renko-calibrated-status`, `renko-calibrated-stop-atr`, `renko-calibrated-style`, `renko-calibrated-target-atr`, `renko-candle-inspection`, `renko-candle-readout`, `renko-carry-policy`, `renko-cash-note`, `renko-cash-product`, `renko-cash-product-field`, `renko-chart`, `renko-chart-action-error`, `renko-chart-basis`, `renko-chart-basis-note`, `renko-chart-control-note`, `renko-chart-controls`, `renko-chart-currency-note`, `renko-chart-description`, `renko-chart-mode`, `renko-chart-mode-state`, `renko-chart-rail`, `renko-chart-reconcile-close`, `renko-chart-scroll-body`, `renko-chart-stack`, `renko-chart-stop`, `renko-chart-toggle`, `renko-chart-toolbar`, `renko-chart-view`, `renko-commodity-holding`, `renko-commodity-holding-field`, `renko-config-dropdown`, `renko-config-name`, `renko-config-option-`, `renko-config-options`, `renko-config-state`, `renko-configuration-choice`, `renko-daily-budget`, `renko-delete-configuration`, `renko-delta-execution-field`, `renko-delta-execution-route`, `renko-direction`, `renko-ema-exit-enabled`, `renko-ema-exit-length`, `renko-ema-fast-enabled`, `renko-ema-fast-length`, `renko-ema-momentum-enabled`, `renko-ema-policy-profile`, `renko-ema-proximity-distance`, `renko-ema-proximity-enabled`, `renko-ema-proximity-mode`, `renko-ema-slow-enabled`, `renko-ema-slow-exit-enabled`, `renko-ema-slow-length`, `renko-ema-third-enabled`, `renko-ema-third-length`, `renko-ema-third-status`, `renko-ema-widening-enabled`, `renko-ema-widening-exit-enabled`, `renko-entry-audit`, `renko-event`, `renko-events`, `renko-events-page`, `renko-exit-ema-periods`, `renko-exit-fullscreen`, `renko-export-settings`, `renko-factor`, `renko-family-`, `renko-feed-health`, `renko-fit-chart`, `renko-fold-`, `renko-full-chart`, `renko-fyers-history-account-id`, `renko-fyers-history-enabled`, `renko-higher-timeframe-enabled`, `renko-history-from`, `renko-history-health`, `renko-history-preset`, `renko-history-range`, `renko-history-to`, `renko-indicator-exits`, `renko-inr-policy-note`, `renko-inspection-style`, `renko-instance-count`, `renko-instances`, `renko-intrabar-entries`, `renko-journal-mode`, `renko-journal-scope`, `renko-latest-signal`, `renko-line-entry-definition`, `renko-line-entry-enabled`, `renko-line-entry-note`, `renko-live-pnl`, `renko-loss-range-note`, `renko-lots`, `renko-manual-brick`, `renko-manual-brick-reference`, `renko-manual-trend-bearish`, `renko-manual-trend-bullish`, `renko-manual-trend-closes`, `renko-manual-trend-enabled`, `renko-manual-trend-group`, `renko-manual-trend-status`, `renko-market`, `renko-market-policy-note`, `renko-market-structure-enabled`, `renko-market-structure-exit-enabled`, `renko-market-structure-state`, `renko-max-premium`, `renko-max-trades`, `renko-mode`, `renko-mode-note`, `renko-named-config-note`, `renko-new-instance`, `renko-newer-events`, `renko-older-events`, `renko-order-terms`, `renko-orders`, `renko-override-direction`, `renko-override-entry`, `renko-override-note`, `renko-paper-capital`, `renko-paper-funds`, `renko-parameter-tooltip`, `renko-pnl`, `renko-policy`, `renko-price-source`, `renko-primary-label-caption`, `renko-provisional-status`, `renko-readable-chart`, `renko-reconcile-close`, `renko-recovery-status`, `renko-renko-brick-exit-enabled`, `renko-renko-loss-range-buffer`, `renko-renko-loss-range-enabled`, `renko-reset-chart`, `renko-reset-settings`, `renko-retest-enabled`, `renko-retest-engulfing`, `renko-retest-harami`, `renko-retest-star`, `renko-retest-status`, `renko-rsi-bearish-below`, `renko-rsi-bearish-max`, `renko-rsi-bearish-min`, `renko-rsi-bullish-above`, `renko-rsi-bullish-max`, `renko-rsi-bullish-min`, `renko-rsi-chart`, `renko-rsi-exit-enabled`, `renko-rsi-hover`, `renko-rsi-htf-`, `renko-rsi-htf-active`, `renko-rsi-htf-chart`, `renko-rsi-length`, `renko-rsi-level-enabled`, `renko-rsi-level-mode`, `renko-rsi-readout`, `renko-rsi-slope-enabled`, `renko-rsi-slope-status`, `renko-rsi-sma-enabled`, `renko-rsi-sma-period`, `renko-rsi-sma-readout`, `renko-runner-message`, `renko-runner-panel`, `renko-runner-timeframe`, `renko-running-pnl`, `renko-save-settings`, `renko-search`, `renko-session-action-result`, `renko-session-clear`, `renko-session-deadline`, `renko-session-history`, `renko-session-refresh`, `renko-session-select-all`, `renko-session-select-running`, `renko-session-selection-count`, `renko-session-show-charts`, `renko-session-start-selected`, `renko-session-stop-selected`, `renko-show-five-minute-label`, `renko-show-one-minute-label`, `renko-show-simulated-signals`, `renko-sideways-enabled`, `renko-sideways-max-candles`, `renko-sideways-status`, `renko-signal-label-legend`, `renko-signal-range`, `renko-sma-entry-enabled`, `renko-sma-entry-help`, `renko-sma-exit-enabled`, `renko-sma-length`, `renko-sma-settings`, `renko-spot-stop`, `renko-spot-target`, `renko-spread-filter-enabled`, `renko-spread-filter-note`, `renko-st`, `renko-start-selected`, `renko-state`, `renko-status`, `renko-stop-all`, `renko-stop-all-result`, `renko-strategy-basis`, `renko-strategy-mode`, `renko-stream-status`, `renko-supertrend`, `renko-supertrend-continuation-enabled`, `renko-supertrend-enabled`, `renko-supertrend-exit-enabled`, `renko-supertrend-pointers`, `renko-supertrend-timeframe`, `renko-supertrend-visuals`, `renko-swing-breakout-bricks`, `renko-swing-breakout-enabled`, `renko-swing-breakout-settings`, `renko-swing-breakout-state`, `renko-swing-levels`, `renko-swing-levels-visible`, `renko-symbol`, `renko-target-premium`, `renko-target-premium-field`, `renko-target-premium-help`, `renko-timeframe`, `renko-timeframe-state`, `renko-toggle`, `renko-trades`, `renko-trading-session-hours`, `renko-trailing-basis`, `renko-trailing-distance`, `renko-trailing-enabled`, `renko-trailing-status`, `renko-trend-reentry-enabled`, `renko-trend-reentry-note`, `renko-underlying-price`, `renko-use-adx`, `renko-use-baseline`, `renko-volume-enabled`, `renko-widening-window`, `renko-workspace`, `renko-zone-entry-enabled`, `renko-zone-entry-min-atr`, `renko-zone-entry-rearm`, `renko-zone-status`, `renko-zone-target-enabled`, `renko-zone-target-state`, `rsi-htf-`

## resource-monitor.js

[Owning source](../resource-monitor.js)

### Named functions

`charts`, `hide`, `mount`, `refresh`, `render`, `show`

### UI field and toggle identifiers

`resource-alerts`, `resource-cards`, `resource-charts`, `resource-coverage`, `resource-method`, `resource-processes`, `resource-range`, `resource-refresh`, `resource-status`

## resource-restarts.js

[Owning source](../resource-restarts.js)

### Named functions

`api`, `mount`, `probe`, `progress`, `rejectedRestart`, `render`, `report`, `save`, `schedule`, `start`

## runner-job-details.js

[Owning source](../runner-job-details.js)

### Named functions

`epoch`, `identity`, `installStyle`, `lifecycle`, `render`, `rows`, `tradePnl`

### UI field and toggle identifiers

`runner-detail-styles`

## runner-jobs.js

[Owning source](../runner-jobs.js)

### Named functions

`approveStarts`, `configurationKey`, `configureRefresh`, `inventoryGroup`, `link`, `mount`, `netPnl`, `normalize`, `readSources`, `refresh`, `refreshAll`, `refreshDetail`, `render`, `renderDetails`, `runIdentity`, `savedAudit`, `sessionChartLink`, `showSession`, `sources`, `startJob`, `startRows`, `startSpec`, `stopJob`, `stopRows`, `unwrap`, `updateActions`, `visibleJobs`

## seasonality.js

[Owning source](../seasonality.js)

### Named functions

`button`, `displayedScope`, `frame`, `open`, `preferences`, `progress`, `render`, `save`, `shell`

### UI field and toggle identifiers

`seasonality-dialog`

## sector-dashboard-model.js

[Owning source](../sector-dashboard-model.js)

### Named functions

`analysisStatusText`, `exposeSectorDashboardModel`, `filterAndSortSectors`, `latestDataTimestamp`, `qualityText`, `refreshPhaseState`, `riskPolicyPreview`, `rotationDisplay`, `rotationOverviewValue`

## sector-detail-client.js

[Owning source](../sector-detail-client.js)

### Named functions

`read`

## telegram-parser.js

[Owning source](../telegram-parser.js)

### Named functions

`action`, `api`, `clearPreview`, `controls`, `doPreview`, `refresh`, `render`, `resultText`, `save`

### UI field and toggle identifiers

`telegram-parser`, `tg-api-hash`, `tg-api-id`, `tg-capability`, `tg-channel`, `tg-channel-label`, `tg-code`, `tg-code-submit`, `tg-connect`, `tg-disconnect`, `tg-ema`, `tg-ema-length`, `tg-execution`, `tg-gold-proxy`, `tg-live-consent`, `tg-live-consent-label`, `tg-login`, `tg-message`, `tg-mode`, `tg-outcomes`, `tg-owner`, `tg-password`, `tg-password-submit`, `tg-phone`, `tg-preview`, `tg-preview-result`, `tg-product`, `tg-quantity`, `tg-queue`, `tg-reception`, `tg-route`, `tg-run`, `tg-save-settings`, `tg-source-save`, `tg-st`, `tg-stop`, `tg-submit`, `tg-text`, `tg-timeframe`, `tg-token`

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

## workspace-context.js

[Owning source](../workspace-context.js)

## workspace-portal.js

[Owning source](../workspace-portal.js)

### Named functions

`api`, `bind`, `completeDhanLogin`, `confirmAccountDelete`, `edit`, `message`, `notificationApi`, `refresh`, `runConnectionTest`, `saveAccountCredentials`, `testConnection`, `updateAccountLabelHint`, `updateChartTicker`

### UI field and toggle identifiers

`delete-account-title`
