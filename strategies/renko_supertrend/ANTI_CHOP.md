# Renko Supertrend anti-chop entry filter

The filter is optional and off by default. It uses completed candles from the selected chart/runner timeframe; no five-minute restriction is imposed. Existing strategy EMA periods and exit rules are not changed.

Four entry gates must pass: ATR above its rolling average; directional fast-EMA slope; fast/slow-EMA separation with no recent cross; and higher-high/higher-low or lower-low/lower-high structure with limited price-range overlap.

## Modes

- Adaptive (the initial mode when adding the optional filter): thresholds are rolling percentiles of the instrument/timeframe's previous valid completed observations. Defaults are a 200-observation window, 60th percentile for absolute ATR-normalized slope, 60th percentile for ATR-normalized EMA gap, and 40th percentile for mean candle overlap. Thresholds are calculated before the current observation is appended. Incomplete calibration fails closed. This is distribution-based calibration, not profit optimization.
- Manual: explicit slope, gap and overlap thresholds. Defaults reproduce the documented Nifty five-minute filter study: 0.15 ATR fast-EMA slope over three bars, 0.20 ATR EMA separation, no cross in six bars, and three directional candles with mean overlap at most 50% of the smaller adjacent candle range.

ATR length, ATR-average length, EMA periods (including 10/30), slope lookback, crossover window, structure length, adaptive window/percentiles and manual thresholds are saved configuration fields. All remain configurable. Adaptive mode derives thresholds; it does not pick an EMA pair or silently change runner timeframe.

The independent filter calculations do not require the EMA entry family to be on. They use their own indicator state and never alter the main Supertrend or exit-indicator values. The filter does not create entries, skip broker checks, or trigger an exit when it fails. It only gates an otherwise eligible automatic entry; explicit manual override behaviour remains separate. Enabled intrabar entries are rejected for this completed-candle checklist.

Guarded entry submission checks the current matching filter revision, direction, completed-bar identity, readiness and freshness. The gate and its observed/required values are retained in entry assessments and trade indicator snapshots. Disabled filter checks are omitted from assessments and candle inspection.

Source and activation coverage: shared project and account-source copies; API chart/stream boolean parsing; saved preferences, configuration exports, runtime capabilities, native broker adapters through their shared chart configuration. Current workers require the `host-timeframe-anti-chop-v2-adaptive` capability before enabling/saving/starting with the filter.

Validation: 58 Python tests, 25 frontend tests; manual-mode parity against 18,525 five-minute study bars (355 accepted, zero gate mismatches, maximum numeric difference under 1e-7). Adaptive tests cover prior-only percentiles, warmup failure, scale invariance and configurable 10/30 periods. The earlier one-year profitability study applies to Manual 20/50 defaults, not the new Adaptive method or other instruments/timeframes. No profitability claim is made for Adaptive mode.

Standalone entry role: optional `anti_chop_role=Entry` derives direction from the configured fast/slow EMA ordering and emits on a new all-four-pass episode. Other entry rules must be disabled; EMA exit settings remain independent. Filter role remains the backward-compatible default. Adaptive learns thresholds, not indicator periods. Paper validation is not a profitability test.

Confirmation is configurable: All retains four mandatory checks. Trend requires slope AND separation AND (ATR OR structure); both alternative observations remain visible as informational rows, with an explicit combined confirmation row. Missing history and adaptive warmup still block entries. Exit math is unchanged.
