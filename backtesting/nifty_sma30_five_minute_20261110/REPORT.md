# Five-minute strategy timeframe versus corrected one-minute baseline

Single unchanged October2026 test, no tuning. Actual dates1–30October2026,20 regular sessions. Two lots=130 option units initially, partial65 and remaining65. Real FYERS historical option-minute premiums.

## Result: helped within this sample
|Metric|Corrected1m|Corrected5m|
|---|---:|---:|
|Whole entries|591|102|
|Whole-entry net wins|189|49|
|Whole-entry net win rate|31.98%|48.04%|
|Whole-entry profit factor|1.06|1.19|
|Gross P&L INR|71,613.75|28,141.75|
|Estimated costs INR|55,609.56|10,006.13|
|Net P&L INR|16,004.19|18,135.62|
|Maximum minute-marked drawdown INR|30,121.27|23,208.75|
|First target reached entries|191|52|
|First target hit rate|32.32%|50.98%|
|Separate partial exits|188|49|
|Pre-target SMA flip final exits|392|45|
|Median pre-target flip holding,minutes|2|10|

5m improves net byINR2,131.42 and reduces drawdown byINR6,912.53,with489 fewer entries. Costs declineINR45,603.42; gross profit declinesINR43,472.00. Thus lower churn/fees are the direct accounting explanation for the net improvement, not higher gross profits. This single month does not establish future superiority.

5m still suffers45 pre-target SMA exits,44 net losers.22 of45 flip in their first five-minute entry bar(execution5minutes after entry),31 within first two bars(execution within10minutes). Flip losses are fewer but larger on average: group net-80,460.06/45=-1,788.00 per flip,versus corrected1m-217,990.86/392=-556.10. A higher timeframe does not remove whipsaw risk.

## Exit attribution, entire entries
|Final reason|Entries|%of102|Gross INR|Costs INR|Net INR|
|---|---:|---:|---:|---:|---:|
|Pre-target SMA flip,both lots|45|44.12|-76,875.50|3,584.56|-80,460.06|
|Midpoint stop after partial|49|48.04|104,685.75|5,693.82|98,991.93|
|15:29 EOD|8|7.84|331.50|727.75|-396.25|

Midpoint-final P&L includes earlier target partial; do not add partials again.52 entries reach target;49 have a separate partial,3 target confirmations coincide withEOD and net into final order.204 lot legs,94 winning legs,46.08% net leg win rate,PF1.18952; these are not204 independent signals.253 actual orders,including102 buys,151 sells. Fees allocate one130-unit entry and one65/130-unit sale per real order, without doubling brokerage for combined closures.

## What changed
SMA30 is over30 COMPLETED FIVE-MINUTE NIFTY closes,continuous regular-session candles across days,not SMA30 on one-minute data. Five-minute bars align09:15,09:20,etc. Each aggregates exactly5 genuine regular-session minute candles. September2026 warms the SMA before October. October has1500 five-minute candles/7500 minute bars.

Entry uses completed5m crossover,nearest-expiry ATM contract chosen from signal close,then next actual one-minute option OPEN. Before first target,exit both lots on completed opposite5m SMA30 cross,next option-minute OPEN. Eligible reversal sells old contract before opposite130-unit buy at same open;45 reversals. No previous-candle touch stop.

The daily V1 reference grid construction is UNCHANGED: first completed bearish5m candle after opening09:15 candle,freeze itsH/L at entry,centersH+nR,L-nR,n1..10. Skip before current grid is available. Original44/50/56 ratios/defaults untouched. SMART visibility is treated as display; the formula-known grid is available causally at reference completion. No mixed historical,Shadow Candle or extra30m grids.113 eligible candidate signals reconcile:102entries,10pre-grid skips,1ignored while post-target;0no-target skips.

Existing grid targets and already-active midpoint stops are monitored using ONE-MINUTE underlying OHLC,not only5m endpoints. A target touch in a completed minute sells65 at next option-minute OPEN. The remainder's first stop waits for the FULL FIVE-MINUTE TARGET CANDLE to complete; then midpoint=(5mH+5mL)/2 becomes active next minute. No initial or SMA stop is retained during this post-target waiting phase. Waiting after actual partial fill is0..4minutes,mean2.22minutes. This wait is a necessary consequence of using a completed5m full-candle midpoint and is explicitly part of this interpretation.

After that,update midpoint only on each completed5m candle,CALL=max(old,midpoint),PUT=min(old,midpoint). Apply only NEXT minute. An existing stop touch during the5m candle exits at next positive-volume option-minute OPEN,using its prior active stop; the later5m close cannot retroactively change that trigger. Post-target SMA flips are ignored.

## Collision audit
Zero first-target-touch/close-confirmed SMA collisions in the SAME one-minute bar; target/flip priority sensitivity would be identical for these0 cases. One five-minute candle both touched target and finished on an opposite SMA cross,but the one-minute stream shows target occurred earlier. Partial was therefore scheduled before the5m-close flip; post-target rule applies and the fresh midpoint is still delayed until5m close. This event has observed ordering at our minute resolution and does not require an invented5m intrabar path. No optimistic retroactive midpoint stop fill.

EOD scheduled15:29 OPEN. Eligibility cutoff remains executable entry<=15:28,but5m-boundary signals make actual latest permitted entry15:25;the15:25–15:30 signal candle cannot open a new position. Session09:15–15:30 IST; no overnight holdings.

## Costs, data, limitations, verification
Same FYERS cost schedule as preserved1m study:20/order,exchange0.0355299%,clearing0.009%,SEBI10/crore,IPFT0.01/crore,GST18%,buy stamp0.003%,sell STT0.15%. Model costs10,006.13,35.56%of gross versus77.65%for1m. No spread/slippage/latency/impact,not actual contract-note rounded fees. Historical positive volume does not certify executable quotes. One-month sample and a modestINR2,131.42 advantage do not establish robust out-of-sample improvement. This is a research comparison,not live trading readiness.

Fixed immutable option contracts retained. Existing cached historical option data reused;two additional missing contracts downloaded read-only to this directory raw/. No modeled premiums or synthetic missing bars. All executed stop/target exits had the next option-minute bar available,zeroextra delayed exit bars. Equity is marked to option one-minute closes,with actual per-order cost timing; reported drawdown is not intrabar worst case. User capital unspecified,so no percentage-capital returns/drawdown.

Verification passes: complete aligned5mOHLC,5m SMA/entry confirmations,5m source full-candle midpoints/next-minute activation,tighten-only trail,minute-level touch monitoring,causal grid availability,partial/order/leg reconciliation,45same-open reversals sell-before-buy,noovernight,no overlapping inventory,all113signals accounted,independent every-minute cash+held-inventory equity maxerror2.91e-11 INR,independent VectorBT terminal-P&L replay,eight synthetic rule checks. VectorBT's terminal cross-check places total leg fees at entry;authoritative minute equity retains actual order fee timing.

## Reproduce
From /home/trading/sector-heatmap:
FYERS_RESEARCH_TOKEN_FILE=<approved existing account token path> backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_five_minute_20261110/backtest.py
backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_five_minute_20261110/verify.py

Cached reruns need no token when all raw contracts exist. Artifacts:backtest.py,verify.py,spot_5m.csv,candidate_signals.csv,entries.csv,legs.csv,orders.csv,events.csv,equity.csv,results.json,verification.json,analysis.json,exit_attribution.csv,comparison.csv,comparison.html,provenance.json andraw/. Existing1m andolder variants remain intact. No runner,settings,order,deployment or service changed.

