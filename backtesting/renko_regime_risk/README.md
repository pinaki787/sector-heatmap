> Subsequent high-win-rate testing did not meet the full joint objective. The risk-first profile below is an experimental tradeoff, not a completed solution. See HIGH_WIN_RESULT.md.

# Renko risk-first calibration: losing streaks and drawdown

## Recommendation

For the stated priority of **shorter losing streaks and lower drawdown**, freeze the following profile for a controlled paper comparison:

- Retain the existing directional entry setup.
- Require **18-candle directional efficiency >=0.15** on completed five-minute candles, within the same session.
- Require **ATR5 >= its preceding 60-value upper median** (31st sorted value of 60).
- Add an **initial underlying stop 1.5 times the completed ATR5 known at entry**. Fix that distance at entry; round long stops down and short stops up to 0.05-point increments.
- Keep the existing Supertrend/EMA30 and session exits. The stop may close earlier.
- Do not add a new trailing or breakeven rule to this primary profile. The tested trailing alternatives were more sensitive or harmed expectancy.
- This is an offline research profile, not an activated hosted setting. An underlying stop trigger is not an option-premium stop price.

This supersedes the earlier profit-oriented recommendation for the risk-first objective. Rising ADX plus volatility produced more total modeled points, but its losing streak/drawdown tradeoff was weaker for this priority.

## Main results

Current brick 27.71; at most two modeled entries per day; hypothetical total two-point friction per completed underlying trade. All P&L/drawdown units below are **index points**, not rupees or option profits.

| Profile | Earlier PF | Latest PF | Two-year PF | Trades | Net points | Realized DD | Longest loss streak | Longest non-winning streak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Existing baseline | 1.10 | 0.93 | 1.01 | 762 | 215.20 | 1747.75 | 13 | 13 |
| Rising ADX + volatility | 1.22 | 1.26 | 1.24 | 447 | 2367.40 | 850.15 | 10 | 10 |
| Efficiency + volatility, existing exits | 1.27 | 1.13 | 1.20 | 246 | 1034.50 | 689.40 | 7 | 7 |
| Overlap + 1.5-ATR trail | 1.32 | 1.16 | 1.25 | 226 | 764.60 | 377.20 | 6 | 6 |
| Recommended: efficiency + 1.5-ATR initial stop | 1.35 | 1.16 | 1.26 | 255 | 1236.55 | 610.65 | 9 | 9 |

The recommendation reduces the two-year realized drawdown from 1,747.75 to 610.65 points and longest loss streak from 13 to 9 in this replay. It does not imply those streak limits will hold in future trading.

## Each year separately

| Year / profile | PF | Net points | Realized DD | Minute-close DD | Longest loss streak |
|---|---:|---:|---:|---:|---:|
| Earlier year / Existing baseline | 1.10 | 801.35 | 1278.35 | 1359.70 | 13 |
| Earlier year / Recommended: efficiency + 1.5-ATR initial stop | 1.35 | 856.80 | 382.45 | 422.75 | 9 |
| Latest year / Existing baseline | 0.93 | -586.15 | 1113.85 | 1187.65 | 10 |
| Latest year / Recommended: efficiency + 1.5-ATR initial stop | 1.16 | 379.75 | 404.60 | 423.40 | 8 |

## Stop, trail and price-action tests

52 combinations crossed four entry profiles (baseline, rising ADX/volatility, efficiency/volatility, candle overlap) with 13 exit/risk choices: existing exits, 1/1.5/2 ATR initial stops, several ATR trails, breakeven triggers, combined trail/breakeven and 15/30/60-minute loss cooldowns.

29 further sensitivity replays varied candle-overlap thresholds 0.30/0.40/0.50, trail distances 1/1.5/2 ATR and brick sizes 20/27.71/35, and audited the recommended initial-stop profile at neighboring brick sizes.

The lowest historical drawdown came from low candle overlap plus a 1.5-ATR trail: longest loss streak 6 and realized DD 377.20 points. It was rejected as the primary suggestion because nearby overlap thresholds damaged the latest year; its latest-year four-point-friction PF was only about 1.01. Choosing that peak would risk overfitting.

Confirmed higher-high/higher-low and confirmed swing-breakout entry gates were also tested in 15 separate brick-sensitivity runs. They did not consistently improve both years. Pivots were accepted only after their right-side confirmation candles had completed.

## Recommended profile: sensitivity

| Brick / friction | Earlier PF | Latest PF |
|---|---:|---:|
| 20.00 / 2 points | 1.49 | 1.18 |
| 20.00 / 4 points | 1.36 | 1.07 |
| 27.71 / 2 points | 1.35 | 1.16 |
| 27.71 / 4 points | 1.23 | 1.05 |
| 35.00 / 2 points | 1.45 | 1.18 |
| 35.00 / 4 points | 1.33 | 1.06 |

The efficiency entry threshold remains sensitive: some neighboring thresholds failed in the earlier year during the entry-grid calibration. The recommendation is the steadier tested risk alternative, not a claim of a broad universal optimum.

## Why losing-streak numbers alone can mislead

An ordinary breakeven rule shortened some strict-loss streaks by inserting zero-net trades, while the non-winning streak reached 29 trades in one test. Ranking therefore includes consecutive non-positive trades, without resetting streaks at day boundaries. Lowering the reported loss streak by relabeling losses as breakevens is not enough.

## Data, chronology and evidence

The archived FYERS NIFTY one-minute and five-minute data were used together. Only complete aligned regular-clock sessions with 375 minute bars and 75 host bars were admitted; the short 21 October 2025 session and nonregular observations were excluded. Raw files were preserved. The first five complete sessions are warm-up; scoring starts 4 November 2024. Full exchange-holiday certification remains outside this audit.

The minute/host OHLC audit found no differing OHLC values beyond a tick wherever all constituent minutes existed. The no-stop minute replay exactly reproduces the cleaned five-minute lifecycle trades for all four entry profiles. This is model parity, not live order/fill verification.

Hard stops are active from modeled entry. An existing stop is checked against the next observed minute open/range before a new trail or breakeven level is calculated. New levels become effective only in the following minute. A gap beyond a stop uses the observed open, not an assumed better stop fill. Stop touches otherwise assume execution at the trigger level, without real liquidity or latency evidence. No within-minute tick order is invented to obtain an advantageous trail fill.

All 166 entry-grid variants and 37 shortlist robustness cases were rerun after the complete-session correction. Separate evidence includes 15 price-action runs, 52 risk combinations and 29 risk-sensitivity runs. The combined study contains repeated controls; these are not independent experiments.

53 focused tests cover lifecycle timing, costs, warm-up, causality, directional symmetry, price structure, stop-gap handling, delayed trailing updates, tick rounding and non-winning streak accounting.

## Limits and next action

These are underlying-index lifecycle proxies with retrospective fixed brick parameters. They are not option P&L, rupee portfolio returns or guaranteed executable stop prices. Actual premiums, spread, decay, dated contracts, fills, latency, funds and full runtime risk controls were not modeled. Two entries per day is a research assumption, not verified runtime per-run quota behavior. Friction values 0/2/4 points are sensitivities, not historical fees.

Many alternatives were explored on data already inspected; there is no fresh untouched holdout. Five-session block resampling of the recommended-versus-baseline PF difference has intervals including no improvement, even though point estimates are better. Research does not prove future profitability or eliminate every sideways interval. Minute-close drawdown is sampled and can miss deeper intraminute excursions.

**Next:** keep this profile frozen and implement/compare it in a controlled paper workflow using actual option quotes and execution-cost evidence alongside unchanged baseline. Judge both drawdown and non-winning/losing streaks while retaining a profitability floor. Review on a predeclared new-data window; passing it should not automatically enable Live.

No hosted Paper or Live runner was started, no strategy settings were activated, and no order was submitted by this research. The separate checkbox/help-icon UI repair was handled in its own task.

## Saved evidence

Source: model.py, run.py, select.py, robustness.py, tests and report.py. Results: specification.json, results.json, robustness.json, recommendation.json, selection.json, uncertainty.json, baseline-parity.json and trials/. Persistent progress is in job.json; create CANCEL to stop a running minute replay at its next checkpoint.
