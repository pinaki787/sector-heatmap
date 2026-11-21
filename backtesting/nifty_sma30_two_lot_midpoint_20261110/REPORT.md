# Two-lot first-target partial and candle-midpoint trail

Actual window: 1–30 October 2026, 20 sessions. Real historical FYERS option premiums; no parameter optimization. Earlier results remain unchanged.

| Metric | 1-lot SMA flip | 1-lot grid trail | 2-lot partial + midpoint |
|---|---:|---:|---:|
| Whole entries |657|225|256|
| Net whole-entry win rate |19.03%|20.44%|37.89%|
| Net whole-entry profit factor |0.88|0.86|1.05|
| Gross P&L INR |20,221.50|1,530.75|32,613.75|
| Estimated costs INR |44,096.88|14,936.54|24,738.18|
| Net P&L INR |-23,875.38|-13,405.79|7,875.57|
| Maximum minute-marked drawdown INR |40,149.00|32,406.89|37,840.43|

The new variant was marginally profitable under the stated zero-slippage assumptions. It starts with 130 option units versus 65 in each previous version; these are unnormalized rupee comparisons, not equal-risk returns. Largest single entry premium debit including fees was INR26,220.17, not a complete capital requirement because accumulated losses also require funding. No trading-capital amount was supplied, so percentage returns/drawdown are not asserted.

256 whole entries produced 512 65-unit lot legs, 108 first-target partial exits and 620 actual executed orders (256 buys and364 sells). Whole-entry wins97/256,37.89%,PF1.04548. Leg wins195/512,38.09%,PF1.04514. Legs of a combined130-unit exit share one actual exit-order fee; each leg receives half of the single130-unit entry fee. The512 legs are accounting units, not512 independent entry signals. Final closure reasons:138 initial stops,108 midpoint stops,10 EOD.

## Exact interpretation
Use unchanged completed NIFTY one-minute SMA30 crossing signals, with regular-session SMA history carried across days. Enter one fixed nearest-expiry ATM contract at next-minute option open, quantity130 (2x65). ATM is chosen from signal-close spot, rounded nearest50,ties upward. CALL initial underlying stop is the LOW of the minute immediately preceding the SIGNAL candle; PUT initial stop is that prior candle HIGH. Validate against actual spot entry open; none of the eligible entries had invalid initial gaps.

Freeze the current-day V1 grid at entry: first completed bearish5-minute candle after the09:15 opening candle; R=H-L and centersH+nR,L-nR,n1..10. Select first favorable center strictly beyond actual spot entry. No historical, Shadow Candle or extra30-minute grids. Formula-known centers are usable before SMART draws them; SMART is treated as a display filter. Original44/50/56 ratios and Pine defaults are unchanged.

Sell65 units after the first favorable grid-center touch is confirmed at the NIFTY minute close, using the next positive-volume option-minute OPEN. The target is an underlying level; option premium proceeds are actual archived opens, not modeled target-price premiums.

When that first-target candle completes, compute midpoint=(full NIFTY high+low)/2, NOT candle body midpoint. CALL stop=max(old stop,midpoint); PUT=min(old stop,midpoint). Thereafter repeat on EVERY completed minute, whether favorable or unfavorable, only tightening. New stops become effective NEXT minute. No entry-price breakeven rule is substituted. The full target candle range cannot be used to fill a retroactive stop inside that candle.

The old stop governs each full minute. If old initial stop and first target touch in the same candle, stop-first and no partial target credit. Zero such ambiguous candles arose in this variant; seven synthetic checks include CALL/PUT ambiguous paths and monotonic midpoint updates.

When a stop is touched in completed minute OHLC, sell remaining quantity at next available positive-volume option-minute open. Opposite SMA crossings while held are ignored; a fresh later crossing is required after final exit. 375 candidate crossings were ignored while held;26 skipped before current-day grid availability. All657 baseline candidate signals reconcile. There were zero extra delayed exit bars or missing entry premiums.

IST session09:15–15:30; minute labels09:15..15:29. Latest entry15:28. Flatten all at15:29 OPEN. If first-target sale would coincide with scheduled EOD, remaining quantity is netted into one EOD sale order; no extra synthetic partial fee. Positions never carry overnight.

## Costs, limitations and validation
Same FYERS schedule as prior studies: INR20 PER ACTUAL ORDER, exchange0.0355299%,clearing0.009%,SEBI10/crore,IPFT0.01/crore,GST18%,buy stamp0.003%,sell STT0.15%. Total modeled costs24738.18, including brokerage12400.00,exchange2773.39,clearing702.52,SEBI7.81,IPFT0.01,GST2859.07,stamp116.60,STT5878.80. Contract-note daily rounding excluded. See baseline README for primary rate sources.

No slippage, spread, impact or latency modeled. Candle volume does not prove executable quotes. Because target and stop touches are only known at minute close, next-open pricing may differ materially from live intraminute fills. Maximum drawdown is minute-close marked option equity, not intrabar worst case.

The positive edge is small: there are66560 executed unit-sides; adverse slippage of about0.12 premium points per option unit on every execution would remove this net profit before adjusting fees. This is a direct sensitivity calculation, not another strategy test or optimized result.

Validation: entry quantities130;65/130-unit sells; no overlapping/overnight entries; exactly two65-unit leg ledgers per whole entry; all order fees reconcile without double brokerage; every target-and-later midpoint matches full candle high/low, stops only tighten and activate next minute. Independent cash-debit/credit plus held-premium inventory reconstruction matches every minute of primary equity to under1e-6 INR. Whole-entry, leg and order sums reconcile, and independent VectorBT terminal-P&L replay agrees. VectorBT charges total leg costs at entry solely for terminal verification; primary equity preserves actual fee timing.

## Reproduce
From /home/trading/sector-heatmap:
backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_two_lot_midpoint_20261110/backtest.py
.venv/bin/python backtesting/nifty_sma30_two_lot_midpoint_20261110/verify.py

Artifacts: entries.csv,legs.csv,orders.csv,events.csv,signal_decisions.csv,equity.csv,results.json,comparison.csv,comparison.html,provenance.json. Original raw broker candles are reused unchanged from adjacent baseline directory. No live runner, settings, order or deployment changes.
