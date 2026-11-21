> Superseded sizing policy: see `renko-dated-master-lot-sizing.md`. Manual lot assumptions described in the original implementation history below are withdrawn and prohibited by backtest v2. The original assumption-based validation report is SUPERSEDED; its sized metrics are not valid current results.

# Renko third EMA and historical backtest — staged 25 October 2026

Third EMA defaults to enabled with period 100 for new/draft configurations. Explicit saved values are retained. A restored runner configuration without the new fields uses third EMA disabled, preserving its original two-EMA policy. UI, validation, selected-family masks, chart destinations, signal snapshots, assessments, retests and historical replay include the third EMA. Existing runner/settings state files were not rewritten by this implementation.

Backtest is a separate research mode. It captures the visible strategy configuration and uses the existing account-owned persistent ANALYSIS job service; no runner is created or armed. Jobs persist inputs, progress, partial trade audits and final reports. Stop requests settle at bounded checkpoints, including around broker history reads. Saved reports are retrieved by job ID and owner. Exports retain calculation precision; display numbers use at most two decimal places.

Periods: 1/3/6 months, 1 year or custom completed dates, at most 366 days. The staged NIFTY archive is reused before any download. Missing provider history downloads are opt-in and use only the selected FYERS workspace session. Public market-response cache entries identify their exact request and response hash. No login, token refresh or purchase is attempted.

Signals use the existing Renko Engine with the captured settings, including EMA 3 and supported HTF gates. Completed host bars schedule next-open entry/indicator exits. A separate actual one-minute underlying and held-contract grid enforces 15:10 NSE/BSE intraday cutoff even on longer signal timeframes. Candle gaps are not filled. Fixed hard/trailing boundaries are sampled at minute opens; intraminute ticks are unavailable.

Options use broker-reported historical expiry lists and exact returned option symbols. The nearest strike in the nearest reported unexpired expiry is selected once at entry; lower strike breaks ties. Bullish buys CALL; bearish buys PUT. That identical symbol is retained through exit. backtesting.py 0.6.6 executes the actual historical premium bars and quantity at the requested exact opens. Underlying entry/exit prices remain reference columns and are never option P&L. Quantity requires historical lot metadata or an explicit user-supplied units-per-lot assumption; today's lot size is not silently substituted.

Report: priced net/gross/estimated charges, win rate, profit factor, closed-trade net-equity drawdown, winning/losing streaks, observed trading hours/sessions, settings, assumptions, skipped entries, evidence gaps and exact-contract trade audit. A full-period metric set is withheld for detected missing underlying/option history, insufficient warmup, unresolved exposure, missing quantity or unsupported selected execution behavior. Priced subsets are labeled separately. Equity drawdown is closed-trade drawdown, not intratrade drawdown. A no-loss profit factor is labeled, not exported as infinity.

Current limits are explicit:

- Verified session execution is NSE/BSE regular intraday. Other markets receive an incomplete-session result, not a fabricated calendar.
- The NSE 2026 holiday calendar is verified; earlier years use broker-returned weekdays. Special-session completeness is not certified.
- Selected intrabar timing and runtime continuation policy require unavailable tick/runtime evidence and block a completed replay. They are not silently disabled.
- Expired-contract history cannot supply an option that has not expired yet. Missing current-expiry data is reported.
- Historical lot metadata is often absent from FYERS responses; an explicit quantity assumption may be needed.
- Verified option cost estimates cover NSE/BSE from 1 April 2026; other asset/date cost schedules are withheld. Costs are estimates, not contract notes. Slippage is a sensitivity; historical candles are not executable bid/ask fills.
- Captured runner trade limit applies across the complete backtest run. It is not silently reset daily.

Read-only provider validation on 25 October IST: the archived underlying at 16 October 10:00 selected NSE:NIFTY26O1923050CE expiring 19 October. FYERS returned 385 one-minute premium bars and no historical lot size. Evidence is private in `.private/renko-backtest-provider-validation.json`.

Validation includes exact premium P&L, fixed contract identity, quantity assumptions, gaps, no same-candle execution, 30-minute signal/15:10 cutoff, cancellation propagation, legacy restore without state-file writes, mounted settings capture/ownership/stop, escaping and two-decimal display. Hosted controls and a clearly marked synthetic report were visually reviewed on desktop and at 390 CSS pixels. Synthetic preview figures are not market performance.

User explicitly authorized service restarts as needed for this task. The FYERS worker on 127.0.0.1:8102 was reloaded through the guarded account bounce, without starting any runner. Hosted backtest job 8499522df11000a2f0f8f3eeb1caf9d4 completed and was retrieved after a page reload. Its 16 October NIFTY 5-minute run used the selected EMA 3 enabled at period 100, exact contract NSE:NIFTY26O1923100CE, premiums 103.8 to 90.85, and an agent-entered unverified 65-unit research assumption. Gross -841.75 INR; estimated net -904.63 INR. This is functional verification, not validated strategy performance or verified historical sizing. Saved evidence is private in .private/renko-backtest-hosted-validation.json. The full strategy suite has four unrelated pre-existing failures/errors documented separately; do not claim the entire suite is green.

Final checkpoint: 15 backtest tests passed, including durable cancellation/partial retention and legacy restore without file mutation. Mounted UI and six settings/EMA tests passed. Full strategy run: 478 tests with the same three failures and one error reproduced before these changes (Delta signal formula, Delta route scope, manual-brick session fixture, conservative unknown-net sideways fixture). All root/account backtest sources match and compile. Eight FYERS runner-state hashes stayed unchanged. Readiness check at 2026-10-24 20:32:49 UTC found zero broker open positions, zero pending/transit orders and zero running saved Renko instances. Synthetic public preview moved back to private storage after visual review.

Cash CNC/carry-forward is explicitly blocked pending a verified overnight/corporate-action policy; it is never silently converted to intraday. Other broker workers remain staged and were not restarted.

Final activation: FYERS worker PID 1580484, guarded READY. The completed saved validation job survived the final guard reload and was retrievable. Final read-only broker check at 2026-10-24 20:42:46 UTC: zero open positions, zero pending/transit orders, eight stopped saved Renko instances without recorded positions/pending submissions. No runner was armed and no broker order endpoint was called.
