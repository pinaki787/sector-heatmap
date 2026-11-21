# Loss analysis — corrected two-lot SMA exit, October2026

The latest corrected run is NET PROFITABLE overall:INR16,004.19, not an overall loss. There are402 losing whole entries and189 winners across591 entries.

## Where losses came from
|Whole-entry final exit|Entries|%|Wins/losses|Gross INR|Costs INR|Net INR|
|---|---:|---:|---:|---:|---:|---:|
|Pre-target opposite SMA30 flip|392|66.33|31/361|-184,567.50|33,423.36|-217,990.86|
|Post-target midpoint trail|188|31.81|154/34|255,128.25|21,226.45|233,901.80|
|15:29 EOD|11|1.86|4/7|1,053.00|959.75|93.25|
|Total|591|100|189/402|71,613.75|55,609.56|16,004.19|

Midpoint-final category includes the first lot partial sale and remaining lot result. Do not add partial profit again. Lot-ledger/order-ledger sums independently reconcile. This analysis concerns the corrected SMA-flip rule, NOT the earlier previous-candle touch-stop simulation.

## Main evidence-backed findings
1. Rapid pre-target opposite crossings are the dominant losing-trade group.361 of402 losing entries(89.80%) finish on pre-target SMA exits. Of392 such exits,154(39.29%) trigger during the entry minute and286(72.96%) trigger in the first5 candles. Median option holding time is2 minutes and median SMA-trigger elapsed time1 minute. This is consistent with frequent short-lived SMA crossings/whipsaws; it is not proof of an independently measured market regime.
2. Only191/591 entries(32.32%) touch the first grid target.188 execute separate one-lot partials;3 coincide withEOD and are netted into the final order.
3. Charges are large relative to edge:INR55,609.56 of71,613.75 gross P&L,77.65%, leaving16,004.19. Average cost94.09 per entry versus only27.08 average net expectancy.24 gross-positive entries become net losses after costs. Brokerage27,400.00,STT13,539.49 andGST6,376.49 are the largest individual cost items.
4. Fewer, larger winners offset frequent smaller losers:189 winners total276,791.24;402 losers total-260,787.04. Average winner1,464.50 versus average loser-648.72,ratio2.26. The resulting whole-entry PF is only1.06 despite positive net profit.
5. CALL306 entries net-16,524.00;PUT285 entries net+32,528.19. This is historical attribution, not evidence that future CALLs should be disabled.
6. Profit concentration is material:11 profitable days,9 losing days. Best3 days(October22,27,28) together+26,036.41; the other17 days together-10,032.21. Best dayOctober22+9,584.85,worstOctober21-6,739.09. Removing top days is descriptive concentration analysis, not a valid counterfactual strategy or parameter recommendation.

## Timing and uncertainty
Pre-target exits require confirmed opposite spot SMA30 crosses; no previous-candle wick stop remains. Post-target midpoint stop only tightens after completed candles and becomes effective next minute. Executions use real archived next option-minute OPENs. A spot-triggered exit can be profitable or lose money depending on premium change and execution timing. There is no modeled bid/ask spread, slippage, latency or impact. The previously reported11 target-touch/SMA-flip collision cases yield a conservative-priority net13,551.71 versus main16,004.19; this existing sensitivity is not rerun here.

Read-only analysis of existing entries.csv,legs.csv,orders.csv,events.csv. No strategy simulation rerun, optimization, live system or settings changes. Reproduce with .venv/bin/python backtesting/nifty_sma30_two_lot_sma_exit_20261110/analyze_losses.py. Data artifacts:loss_analysis.json,loss_exit_attribution.csv,daily_attribution.csv,side_attribution.csv.

