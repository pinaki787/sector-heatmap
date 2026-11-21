# Nifty five-minute anti-chop backtest

**Result: this test does not establish a profitable trading edge.** The main illustrative strategy made **16.70 points before costs**, but lost **499.30 points after a hypothetical two-point round-trip deduction**. Profit factor was **0.79** across **258 closed trades**. This is one explicit interpretation of a discretionary filter, not a claim that every strategy using the checklist will lose.

## Data and integrity

Period: **24 October 2025–23 October 2026**, the latest complete year in the reusable archive; it ends before the current date. Instrument: **FYERS NIFTY 50 spot index**, not futures or options. **247 sessions / 18,525 five-minute bars**, regular session 09:15–15:30 IST. More than a year of earlier bars provides indicator warmup. All accepted sessions contain 75 five-minute and 375 one-minute bars. No candles were forward-filled. Aggregating the one-minute archive reproduced five-minute OHLC exactly (36,900 compared bars across the full eligible archive; zero discrepancies). Exchange holiday-calendar completeness has not been independently certified. Off-hours and incomplete special-session data are excluded.

Source hashes, exact coverage and provenance are in `audit.json`; indicator library is OpenAlgo ta, portfolio simulator VectorBT. The reproduction script and package lock are included. No broker requests, production settings, runners or orders were changed for this research.

## Rules translated from your checklist

The wording describes a filter rather than a complete strategy. You selected a filter study plus a clearly labelled example strategy. Only the ATR condition is numerically specified in the original wording; the following thresholds are **research assumptions**, not optimized values or your supplied rules.

| Check | Main interpretation |
|---|---|
| Volatility | ATR(14) strictly greater than SMA(20) of ATR(14) |
| EMA20 slope | `(EMA20[t] - EMA20[t-3]) / ATR14[t]` at least +0.15 for long, at most -0.15 for short |
| EMA separation | Absolute EMA20–EMA50 gap at least 0.20 ATR; no EMA20/50 cross during the latest six bars; EMA20 above EMA50 for long, below for short |
| Clean structure | Three same-session candles with two successive higher-high AND higher-low steps for long, or lower-low AND lower-high steps for short; mean adjacent range-overlap no greater than 50% |

Overlap equals the intersecting price range divided by the smaller adjacent candle range. Zero-range candles fail this structure check. Structure does not span overnight gaps. ATR and EMAs use continuous regular-session history rather than resetting daily.

The looser version uses slope 0.10 ATR, separation 0.10 ATR, one directional step and overlap ≤65%. The stricter version uses slope 0.25 ATR, separation 0.30 ATR, two steps and overlap ≤35%. A separate **literal zero-overlap** case keeps the main slope/separation/two-step settings and requires no adjacent range intersection. These are sensitivity scenarios, not a search for the best parameters.

## Filter coverage

| variant      |   pass_bars |   pass_percent |   long_bars |   short_bars |
|:-------------|------------:|---------------:|------------:|-------------:|
| loose        |         973 |           5.25 |         391 |          582 |
| main         |         355 |           1.92 |         147 |          208 |
| strict       |         135 |           0.73 |          55 |           80 |
| zero_overlap |           0 |           0.00 |           0 |            0 |

**Literal zero overlap produced zero qualifying bars and zero trades.** Thus, the relaxed 50% overlap assumption materially changes what is being tested.

Main gate funnel:

| stage                              |   standalone_pass_percent |   cumulative_pass_bars |   cumulative_pass_percent |
|:-----------------------------------|--------------------------:|-----------------------:|--------------------------:|
| ATR14 > SMA20(ATR14)               |                     40.90 |                   7577 |                     40.90 |
| EMA20 slope direction              |                     60.46 |                   4837 |                     26.11 |
| EMA separation and no recent cross |                     85.65 |                   3832 |                     20.69 |
| Structure and overlap              |                      6.19 |                    355 |                      1.92 |

The structure/overlap condition is the main bottleneck: after ATR, slope and separation, 20.69% of all bars remain; adding structure reduces that to 1.92%. A clean-looking candle sequence often lasts only one qualifying bar. This is why using the filter itself as an immediate exit rule can create short holding periods and cost sensitivity.

## Filter-only forward study

At a qualifying completed bar, evaluate entry at the next bar open and direction-adjusted movement through the close 15, 30 or 60 minutes later. Long and short moves are signed consistently. Any sample that would cross a session boundary is excluded. These samples overlap and are not statistically independent; no statistical-significance claim is made.

Main results against controls matched by calendar month, half-hour time slot and EMA trend direction:

|   horizon_minutes |   samples |   filtered_mean_points |   matched_baseline_mean_points |   difference_points |
|------------------:|----------:|-----------------------:|-------------------------------:|--------------------:|
|             15.00 |    338.00 |                   1.13 |                           2.07 |               -0.94 |
|             30.00 |    301.00 |                  -1.56 |                           2.40 |               -3.97 |
|             60.00 |    259.00 |                   3.42 |                           0.79 |                2.63 |

The main filter does not consistently outperform the matched baseline: it is weaker over 15 and 30 minutes and stronger over 60 minutes. This does not by itself define a tradeable system.

## Example strategy — assumed entry and exit rules

1. Observe only completed five-minute candles. Long when all checks pass with bullish EMA alignment; short for bearish alignment.
2. Enter at the **next five-minute open**, once per fresh qualifying episode. No same-close fills.
3. Signal exits when any checklist condition fails or EMA direction changes; execute at the following bar open. An opposite entry closes the current position; it does not instantly reverse at that same fill.
4. Entry signal windows are 09:25–15:10 IST. The 15:20 candle forces an exit at the 15:25 open, so there is no overnight position.
5. One spot-index point unit, no leverage/margin modelling. Initial bookkeeping cash is twice the first index open. Percentage returns and daily risk ratios depend on this normalization and are not deployable futures returns.
6. Compare zero, two and five **hypothetical index points per round trip**; these are sensitivity deductions, not verified broker fees. No extra slippage, bid/ask, futures basis, rolls, expiry, lot size or option premium dynamics are modelled.

## Strategy comparison

All rows below use the two-point round-trip deduction. The unfiltered baseline trades EMA20/50 direction with the same session, entry/exit execution and sizing rules, but without the four anti-chop gates.

| variant                  |   trades |   net_points |   win_rate_percent |   profit_factor |   max_drawdown_points |   daily_sharpe_proxy |   daily_sortino_proxy |
|:-------------------------|---------:|-------------:|-------------------:|----------------:|----------------------:|---------------------:|----------------------:|
| Unfiltered EMA direction |      317 |      -434.40 |              42.27 |            0.97 |               2274.95 |                -0.27 |                 -0.40 |
| Loose checklist          |      667 |      -925.85 |              41.38 |            0.83 |               1329.25 |                -1.57 |                 -2.20 |
| Main checklist           |      258 |      -499.30 |              39.15 |            0.79 |                614.60 |                -1.32 |                 -1.82 |
| Strict checklist         |      113 |       -49.80 |              51.33 |            0.95 |                253.35 |                -0.21 |                 -0.31 |
| Literal zero overlap     |        0 |         0.00 |             nan    |          nan    |                  0.00 |               nan    |                nan    |

Cost sensitivity:

| variant      |   roundtrip_cost_points |   trades |   net_points |   mean_trade_points |
|:-------------|------------------------:|---------:|-------------:|--------------------:|
| baseline     |                       0 |      317 |       199.60 |                0.63 |
| baseline     |                       2 |      317 |      -434.40 |               -1.37 |
| baseline     |                       5 |      317 |     -1385.40 |               -4.37 |
| loose        |                       0 |      667 |       408.15 |                0.61 |
| loose        |                       2 |      667 |      -925.85 |               -1.39 |
| loose        |                       5 |      667 |     -2926.85 |               -4.39 |
| main         |                       0 |      258 |        16.70 |                0.06 |
| main         |                       2 |      258 |      -499.30 |               -1.94 |
| main         |                       5 |      258 |     -1273.30 |               -4.94 |
| strict       |                       0 |      113 |       176.20 |                1.56 |
| strict       |                       2 |      113 |       -49.80 |               -0.44 |
| strict       |                       5 |      113 |      -388.80 |               -3.44 |
| zero_overlap |                       0 |        0 |         0.00 |              nan    |
| zero_overlap |                       2 |        0 |         0.00 |              nan    |
| zero_overlap |                       5 |        0 |         0.00 |              nan    |

The buy-and-hold Nifty spot reference lost **-3335.10 points**, with **4181.35 points** of marked drawdown. It holds overnight and is not a like-for-like intraday benchmark. The intraday EMA baseline is the more relevant comparison.

Normalized comparison (same initial bookkeeping notional; not futures margin returns):

| series                  |   normalized_return_percent |   daily_sharpe |   daily_sortino |   max_drawdown_points |   win_rate_percent |   trades |   profit_factor |
|:------------------------|----------------------------:|---------------:|----------------:|----------------------:|-------------------:|---------:|----------------:|
| Main example            |                       -0.96 |          -1.32 |           -1.82 |                614.60 |              39.15 |      258 |            0.79 |
| Nifty spot buy and hold |                       -6.43 |          -0.95 |           -1.29 |               4181.35 |               0.00 |        1 |            0.00 |

## Stability and limitations

Main strategy by chronological half, with the same fixed parameters: first half **-413.70 points**, second half **-85.60 points** after the two-point round trip. No parameter was selected on the first half and then validated on untouched later data. Treat this as a descriptive one-year historical study, not walk-forward validation.

Twenty-seven prefix-invariance checks confirmed that EMA20, EMA50 and ATR14 values do not change when later data are removed. All accepted trade entry and exit prices reconcile to archived opens; all trades are flat by session end. The independent verifier checks the prior-bar signal and reconstructs every trade P&L. `verification.json` contains the evidence. Long/short and half-year breakdowns are in `breakdown.csv`; monthly results are in `monthly.csv`.

The strict case is closer to breakeven after costs but is still negative for this full year; do not treat its smaller sample as proof of superiority. The checklist can be evaluated as an entry filter for a separately defined setup without forcing an immediate exit on every filter failure. That would be a different backtest and may produce different results.

**Interpretation:** visually cleaner conditions are not automatically better entry locations. This particular interpretation is very restrictive and its illustrative trade edge does not survive modest hypothetical costs. Do not promote it to an automatic execution rule from this result alone.

## Included artifacts

- `equity.html`: interactive equity and drawdown chart, two-point round-trip scenario.
- `tearsheet.html`: OpenStatz daily return dashboard for the main spot proxy, with Nifty reference.
- `summary.png`: compact results chart.
- CSVs for trades, bar-by-bar gates, coverage, forward study, matched controls and monthly results.
- Reproducible script, package lock, audit and independent verification.
