# October 6 paper trading review

As of15:59 IST, served Renko runner is not running, flat, with no pending order. Its status text is SIDEWAYS_LOCKED (not proof of active execution). Latest run uses5-minute candles, intrabar entry, EMA10 tick exit, ADX off, quick-loss lock on/max3 buckets and2 lots/40 units. Latest run5 trades: gross−₹1,988; estimated net−₹2,332.37. Whole day20 paper trades: gross−₹4,660; estimated net−₹6,085.36; estimated charges₹1,425.36. Five gross winners become only three net winners. All20 exits are EMA10_INTRABAR_BREACH. Median hold153.67 seconds. No open trade needs an exit.

Previous corrections are deployed, not pending restart: PID3124 was started in the recorded guarded deployment; current APIs respond and return first_assessment/fill separation. Correctness fixes do not establish profitability. No deployment, restart, activation, settings or order action was performed during this review.

## Findings and ranked hypotheses

1. **Direction-specific recovery after a losing Call.** Five observed lock releases were downside breaks; this legitimately unlocks the existing either-side policy, but permits another bullish entry later without price clearing the losing Call high. The5-minute sequence repeats this three times. Evaluate retaining a bullish prohibition until a fresh break above that Call's high, while evaluating bearish entries separately. Require a fresh completed setup or separate tested qualification-reset condition. This is a policy candidate, not a diagnosed implementation failure. Tick history is needed to evaluate missed rallies and actual releases; saved extremes alone cannot reconstruct every alternative entry.
2. **Reduce intrabar entry/exit churn.** Current qualification can appear provisionally; the tick-based EMA exit can reverse rapidly. Compare completed-entry plus tick-exit and confirmation/hysteresis candidates on the same periods, including drawdown and late-exit sensitivity. Today's5 completed entries lost₹1,764.60 net and15 intrabar entries lost₹4,320.76; these occurred at different times/settings and cannot establish a causal winner. The later5-minute run lost₹2,332.37 and all5 trades were net losers, so merely switching to5 minutes is not supported. A27-minute holding loss also means the problem is not exclusively very short trades.
3. **Cost-aware opportunity and liquidity gate.** Mean estimated round-trip charges₹71.27/40 units≈1.78 option-premium points. Small moves cannot reliably cover that hurdle. Two gross winners (+₹8,+₹50) became net losses. Observed entry spreads0.45–1.20 premium points; sum(quantity×entry spread)₹718 is a descriptive entry-quote hurdle, already embedded in ask/bid fills, NOT an additional measured cost to deduct. Test expected movement against executable premiums/spreads with conservative slippage; a simple cheaper-fees explanation fails because gross day P&L is already negative.
4. **Persistent day-level loss/churn limit across run restarts.** Four5-entry runs produced20 entries; max5/run is not max5/day. No daily budget is configured. A persisted daily loss/trade limit would bound further losses without proving positive expectancy. Select such risk policy explicitly rather than tuning it to today's losses.

## Already tested or contradicted

Retrospectively retaining today's trades with entry ADX>20 leaves7 trades/net−₹2,979.43; ADX>25 leaves2/net−₹1,377.67. These selected-trade arithmetic checks are not strategy replays: alternative eligibility, quotas, locks and future entries would change. ADX by itself has no demonstrated profitable remedy. Distance<5 points toEMA selects two tiny-duration losses/net−₹200.39, but larger-distance entries also lost substantially, including latest-run margins7.96–24.93; no buffer threshold has been promoted.

The previously archived completed strict-onset candidate produced identical baseline trades on development and holdout, so it was not repeated. Previous held-out underlying proxy was highly cost-sensitive and does not prove executable option profitability. No historical tick ordering or contemporaneous alternative-option bid/ask dataset exists for a faithful candidate lifecycle replay. Saved actual tick extremes and journal snapshots support diagnosis of actual events, not invention of counterfactual fills.

## Next validation

Record underlying ticks, contemporaneous option bid/ask and candidate reason codes in shadow mode; freeze the above candidate definitions before testing. Compare on chronological development sessions and untouched later sessions, with exact broker lot/multiplier, fees, conservative slippage, maximum drawdown and missed-trade sensitivity. Require net out-of-sample improvement before changing the established strategy. Today's20 trades are assessment evidence, not a training-and-validation split.

## Current-day trade evidence

| Entry IST | Host frame | Entry mode | Hold seconds | Gross ₹ | Estimated net ₹ | Entry ADX |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 10:43:02 | 1 minute | CONFIRMED | 219.85 | -496.00 | -570.27 | 18.21 |
| 10:50:01 | 1 minute | CONFIRMED | 35.07 | -132.00 | -205.25 | 21.95 |
| 11:02:02 | 1 minute | CONFIRMED | 667.69 | 366.00 | 291.59 | 15.03 |
| 11:16:01 | 1 minute | CONFIRMED | 32.83 | -624.00 | -694.30 | 20.46 |
| 11:20:01 | 1 minute | CONFIRMED | 119.36 | -516.00 | -586.37 | 17.87 |
| 11:38:02 | 1 minute | INTRABAR | 256.73 | 8.00 | -63.20 | 9.59 |
| 11:43:02 | 1 minute | INTRABAR | 457.28 | 386.00 | 314.28 | 12.11 |
| 11:54:11 | 1 minute | INTRABAR | 18.02 | 120.00 | 47.33 | 20.37 |
| 11:56:37 | 1 minute | INTRABAR | 0.14 | -36.00 | -107.73 | 18.76 |
| 11:57:02 | 1 minute | INTRABAR | 115.63 | -20.00 | -92.66 | 17.18 |
| 12:03:32 | 1 minute | INTRABAR | 171.98 | -468.00 | -539.85 | 17.83 |
| 12:12:44 | 1 minute | INTRABAR | 201.61 | -662.00 | -731.93 | 15.78 |
| 12:24:36 | 1 minute | INTRABAR | 79.40 | -554.00 | -625.93 | 17.92 |
| 12:26:04 | 1 minute | INTRABAR | 128.35 | 50.00 | -22.83 | 19.01 |
| 12:29:02 | 1 minute | INTRABAR | 242.72 | -94.00 | -165.87 | 19.51 |
| 13:40:39 | 5 minutes | INTRABAR | 155.85 | -810.00 | -881.38 | 29.71 |
| 13:50:14 | 5 minutes | INTRABAR | 1638.51 | -426.00 | -496.29 | 28.33 |
| 14:42:09 | 5 minutes | INTRABAR | 18.21 | -206.00 | -274.34 | 23.29 |
| 14:47:51 | 5 minutes | INTRABAR | 169.46 | -408.00 | -475.20 | 21.85 |
| 14:55:19 | 5 minutes | INTRABAR | 151.49 | -138.00 | -205.16 | 19.18 |
