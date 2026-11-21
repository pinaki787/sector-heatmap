# Relaxed-objective result

**Relaxing profit factor or streak length alone did not qualify any tested case while retaining at least 65% wins, the drawdown requirement and positive higher-friction results in both years.**

An additional tradeoff is available if win rate is also allowed to fall to roughly 52%. This was not one of the two initially proposed single-target relaxations; it is shown explicitly as a broader compromise.

## Historical compromise

- Keep the existing directional Renko entry setup.
- Require average overlap of the last six consecutive candle pairs to be at most **0.40**, using only completed five-minute candles from the same session. Pair overlap is the intersecting high/low range divided by the larger candle range.
- Use a **3-ATR5 initial underlying stop** and a **1.5-ATR5 underlying profit target**, both fixed from completed entry ATR. Tick-aligned levels; existing strategy/session exits may close earlier.
- Two modeled entries per day; no additional trailing rule.
- These are underlying-index research trigger levels, not option-premium order prices.

At hypothetical total two-point friction per completed trade:

| Metric | Existing baseline | Relaxed compromise |
|---|---:|---:|
| Positive trades | 33.73%  | 51.77%  |
| Profit factor | 1.01 | 1.20 |
| Longest losing streak | 13 | 5 |
| Longest non-winning streak | 13 | 5 |
| Realized drawdown, index points | 1747.75 | 403.85 |
| Net index points | 215.20 | 686.65 |
| Trades | 762 | 226 |

## Each year and friction sensitivity

| Year | Win rate | PF, 2-point drag | PF, 4-point drag | Maximum loss streak | Realized DD, 2-point drag |
|---|---:|---:|---:|---:|---:|
| Earlier | 51.28% | 1.22 | 1.09 | 5 | 354.75 |
| Latest | 52.29% | 1.18 | 1.04 | 5 | 288.80 |

**Interpretation:** this sacrifices the requested high win rate and near-zero losing streaks, but preserves a positive modeled result at both friction levels and lowers drawdown. Latest-year PF at four-point friction is only about 1.04, so the margin is thin. Nearby brick, target and overlap thresholds have not been audited for this exact fixed-target profile; the previously observed overlap sensitivity remains a concern. It is not ready for Live deployment.

**Suggested treatment:** retain this as a moderate-hit-rate paper comparator, alongside the risk-first efficiency/initial-stop profile. Do not call either a proven high-win strategy or change Live settings based on this calibration.

All figures are hypothetical underlying NIFTY lifecycle results, not actual option profits, rupee returns or broker fills. The data were repeatedly inspected and multiple alternatives tested; there is no untouched holdout. Four-point friction is a sensitivity assumption, not measured option transaction costs. Stops and targets touched in one minute use adverse stop-first ordering; touch fills remain assumptions without liquidity/latency evidence.

Scoring uses complete aligned regular-clock sessions after five-session initialization. Saved evidence: relaxed-selection.json, high-win-results.json and high-win-leaderboard.csv. No rerun was needed to change acceptance thresholds; the completed 80-scenario grid was re-scored. Live settings, runners and orders were not changed.
