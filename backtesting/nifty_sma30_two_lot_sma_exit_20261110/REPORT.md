# Corrected pre-target SMA30 exit — two-lot options

Correction requested by user, not parameter optimization. Actual window1–30 October2026,20 observed regular sessions. Earlier source/results remain intact.

## Changed exit logic
The prior previous-candle LOW/HIGH touch stop is REMOVED. There is no pre-target wick stop or previous-candle stop floor. Before first grid target:
- CALL: completed one-minute NIFTY close crosses BELOW SMA30 -> sell BOTH lots next positive-volume option-minute open.
- PUT: completed close crosses ABOVE SMA30 -> mirrored BOTH-lot exit.
A wick crossing SMA without confirmed close does not exit.
At that same next open, the opposite SMA crossing may establish a new eligible130-unit opposite option position. Old option sells BEFORE new option buys; same-open reversal is permitted only for pre-target SMA-flip exits.371 such reversals occurred. A midpoint-stop exit after target does not cause automatic reversal.

First favorable V1 grid center: retain existing rule to sell65 units next option-minute open and activate full target candle(H+L)/2 as the remaining stop NEXT minute. Every later completed candle tightens CALL stop=max(prior,midpoint),PUT=min(prior,midpoint). Subsequent SMA crosses are ignored after target. No retroactive target-candle stop.

Entry remains completed NIFTY1m SMA30 cross, nearest-expiry ATM selected from signal close, next-minute open,130 units(2x65), immutable contract. SMA30 spans regular-session candles continuously across days. The causal current-day V1 reference/targets are frozen at entry; skip before fresh grid forms. Existing Pine44/50/56 constants/defaults untouched. Target centersH+nR,L-nR,n1..10; SMART is a display filter rather than withholding formula-known levels. No Shadow Candle, extra30-minute or old-session grids. No favorable center within the fixed ten-level grid -> skip entry rather than invent an extension.

IST: data09:15–15:30, stamped09:15..15:29; last entry15:28; scheduled flatten15:29 OPEN. Target partials coincident with final flatten are netted into one EOD order.

## Main result, target touch before close-confirmed flip
|Metric|Prior two-lot previous-candle stop|Corrected two-lot SMA flip|
|---|---:|---:|
|Whole entries|256|591|
|Net wins|97|189|
|Whole-entry win rate|37.89%|31.98%|
|Whole-entry profit factor|1.05|1.06|
|Gross P&L INR|32,613.75|71,613.75|
|Estimated costs INR|24,738.18|55,609.56|
|Net P&L INR|7,875.57|16,004.19|
|Maximum minute-marked drawdown INR|37,840.43|30,121.27|

Main run:188 first-target partials;1370 actual orders.1182 lot legs,375 positive,31.73% net leg win rate,PF1.06096. Do not count1182 legs as independent entry signals. Whole-entry metrics combine both lots and allocate one130-unit entry fee across them. Combined130-unit closures incur one exit-order fee, not two. Starting exposure is twice the earlier one-lot baselines; no equal-risk return claim. Original one-lot flip:net-23,875.38; one-lot grid trail:net-13,405.79.

Final whole-entry closure reasons:
|Reason|Entries|% of591|Gross INR|Costs INR|Net INR|
|---|---:|---:|---:|---:|---:|
|Pre-target SMA flip,both lots|392|66.33|-184,567.50|33,423.36|-217,990.86|
|Midpoint stop after target|188|31.81|255,128.25|21,226.45|233,901.80|
|15:29 EOD|11|1.86|1,053.00|959.75|93.25|

Midpoint-terminal P&L includes preceding65-unit partial profit; do not add partials again. All657 original candidate entries reconcile:591 executed,26 skipped before daily grid availability,21 ignored while post-target/awaiting exit,19 without favorable center inside the existing maximum target grid. Zero extra delayed exit bars. No initial-stop exits exist.

## Eleven target/flip collisions and sensitivity
In11 candles, the first target was touched and the SAME minute closed across SMA. Main priority follows chronology: target was reached during the candle before the close-confirmed SMA flip, so book the partial next open and apply midpoint stop only next minute. The newly computed midpoint is NEVER applied inside its own candle. Although both executions are simulated at next open, no future midpoint touch is credited as an earlier fill.

A separate conservative override treats a close-confirmed SMA flip as exiting both lots even when that candle also touched the target, suppressing the partial:
|Metric|Target-touch priority(main)|SMA-flip override sensitivity|
|---|---:|---:|
|Entries|591|603|
|Whole-entry net win rate|31.98%|31.51%|
|Whole-entry profit factor|1.06|1.05|
|Gross INR|71,613.75|69,988.75|
|Costs INR|55,609.56|56,437.04|
|Net INR|16,004.19|13,551.71|
|Maximum marked DD INR|30,121.27|30,838.66|
|Same-open reversals|371|391|

Collision policy changes trade paths and net result byINR2,452.49. These are explicitly different timing interpretations, not an optimized parameter selection. The main interpretation follows the target's intrabar chronology; the override is retained for conservatism.

## Costs, execution and verification
Same FYERS modeled cost schedule as prior runs:20/order; exchange0.0355299%,clearing0.009%,SEBI10/crore,IPFT0.01/crore,GST18%,stamp0.003%buys,STT0.15%sells. Real archived option opens, zero modeled spread/slippage/latency/impact; positive-volume bars do not guarantee executable quotes. Contract-note rounding excluded. Stop/flip checks use completed NIFTY OHLC and exits use next available positive-volume option minute OPEN; no synthetic stop-price option premiums.

Maximum drawdown uses net minute-close marked option equity, not intrabar extrema. Capital was unspecified, so rupee outcomes are reported without percentage capital returns.

Both priority runs pass: previous-candle stop absent; all pre-target flip exits verified against completed spot SMA30 crosses; no pre-target stop level; midpoint stops match full completed candles, only tighten and activate next minute; same-open reversals sell the old contract before buying opposite; no overlapping inventory or overnight holdings; candidate reconciliation; leg/whole-entry/order fee reconciliation; independent minute-by-minute cash plus inventory reconstruction; independent VectorBT terminal-P&L replay; ten synthetic rule cases. VectorBT allocates total leg costs to entry solely for its terminal P&L check; authoritative minute equity pays actual order fees at their execution times.

## Reproduce and artifacts
From /home/trading/sector-heatmap:
backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_two_lot_sma_exit_20261110/backtest.py
backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_two_lot_sma_exit_20261110/backtest.py --conflict-priority flip
backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_two_lot_sma_exit_20261110/verify.py

Artifacts:entries.csv,legs.csv,orders.csv,events.csv,signal_decisions.csv,equity.csv,results.json,comparison.csv,comparison.html,exit_reason_summary.csv,leg_exit_summary.csv,verification.json,collision_sensitivity.json,provenance.json. Override outputs are isolated in sensitivity_flip_priority/. Raw option data is reused from preserved baseline.

No trading runner, live setting, order, restart, service or deployment changed.

