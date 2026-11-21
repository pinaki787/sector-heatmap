# Joint high-win-rate calibration: requested outcome not achieved

**Conclusion: no tested strategy met the joint acceptance targets. No candidate from this research is approved as a solution to the requested high win rate, negligible losing streaks, good profit factor and low drawdown.**

The earlier 36%-win-rate risk candidate did not meet that objective. Calling its drawdown improvement a completed solution would be wrong.

## The additional test

80 combinations crossed four entry profiles with 20 fixed ATR stop/target pairs: stops of 1/1.5/2/3 ATR and targets of 0.25/0.50/0.75/1/1.5 ATR. Existing selected exits remain active. All entries use already completed information. Stops and profit levels are tick-aligned; if both touch inside one minute, the replay uses the adverse stop-first order.

Working acceptance targets, chosen for this calibration rather than supplied as exact numbers by the user:

- At least 65% positive trades in each year.
- Profit factor at least 1.30 in each year under two-point friction.
- At most three consecutive losses or non-positive trades across the complete record.
- At least 50% lower realized and minute-close drawdown in each year.
- At least 60 completed trades in each year, and positive net result under four-point friction.

**Passing combinations: 0 of 80.**

## What the high win rates concealed

| Example | Earlier win rate | Latest win rate | Earlier PF, 2-point drag | Latest PF, 2-point drag | Earlier PF, 4-point drag | Latest PF, 4-point drag | Longest loss streak |
|---|---:|---:|---:|---:|---:|---:|---:|
| Very small target / wide stop | 89.23% | 88.35% | 0.69 | 0.71 | 0.40 | 0.38 | 3 |
| Best worst-year PF among >=65% wins | 70.73% | 73.45% | 1.13 | 1.15 | 0.94 | 0.95 | 5 |

A high hit rate can be created by taking small profits while allowing larger losses. It does not establish a profitable strategy. The approximately 72%-win case produced two-year PF 1.14 at two-point friction, but 0.94 at four-point friction; it also had a five-loss streak. The higher-hit-rate example had PF below one even at the lower friction.

## What is established

The research found improvements to particular objectives, such as drawdown reduction or historical hit rate. It did not establish a parameter set that reliably achieves all requested objectives together. I do not recommend activating these changes in Live or presenting a selected historical peak as a robust strategy.

The saved risk-first recommendation remains an experimental tradeoff, not a qualifying high-win strategy. The complete leaderboards and rejected cases are retained so the result is reviewable. Further tuning on the same already-inspected data cannot by itself provide independent evidence that a new peak generalizes.

## Limits

All figures are underlying NIFTY price-model results, not actual option trades, rupee returns or verified fills. Friction values are sensitivities, not measured broker/option costs. Stop touches assume execution without liquidity/latency evidence. Both archive years were already explored; no fresh untouched holdout remains. Complete aligned sessions were used, with short/special observations excluded and the first five sessions reserved for initialization.

Raw evidence: high-win-specification.json, high-win-results.json, high-win-selection.json and per-trial records. Source: high_win.py and model.py. Four additional target/ordering tests passed, bringing the focused research test total to 57. No live parameters, runners or orders were changed.
