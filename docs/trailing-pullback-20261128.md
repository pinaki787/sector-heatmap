# Completed-brick trailing and continuation release — 28 November 2026

## Behavior
Under RENKO_BRICKS_ONLY, fresh prices can advance the target ladder, but cannot trigger a trailing exit alone. An eligible full completed adverse Renko brick must close at or beyond the active stop. Provisional, replay, stale and pre-entry bricks cannot confirm that exit.

The optional target-grid trailing control also captures completed-brick continuation for a new run. Following a qualifying trailing exit and confirmed flat state, wait for a completed counter-direction pullback brick, then a later completed original-direction brick strictly beyond the frozen prior completed low (short) or high (long). No fresh Buy/Sell flip is required. Quotes, equality at the reference, pending/partial positions and unknown outcomes do not qualify. Opposite-regime invalidation and the separate retained-support/retest path remain enforced. Existing captured runs are not retroactively changed; old exit events do not create a catch-up entry on a new Start.

## Draft chart
The stopped broker-chart path now extends the actual matching completed Supertrend value toward the provisional brick as a dashed display-only segment. Missing matching calculation output remains unavailable rather than fabricated. Completed-preview history is reused across provisional ticks and invalidated for completed/history/account changes.

Hosted BTCUSD verification: 5-minute source, 20-contract stopped draft, brick 54.34782608695652. Matching completed Supertrend 59271.7391304349 was preserved after loading 999 older candles (688 to 1586 completed bricks). Desktop and 600px layout checked; viewport restored. This verifies the stopped draft path, not a new live execution cycle.

## Validation and deployment
864 strategy tests and 68 focused frontend tests passed, including the recorded incident where a price touch previously bypassed Renko-only confirmation, both-direction continuation, duplicate/pending/recovery and draft projection/cache cases.

Canonical source and six maintained account source copies synchronized. Delta dashboard guarded reload completed around 16:38 IST with all Delta workers stopped. Eight protected configuration/state/ledger/control files retained identical hashes. Hosted Start is enabled and the continuation capability is loaded in the dashboard. Other broker worker processes were not restarted.

Read-only broker preflight around 16:38 IST confirmed BTCUSD flat and no BTCUSD open orders. No orders or worker starts were performed. BTCUSD remains OFF; the user will explicitly Start. The currently selected 5-minute draft was preserved. A newly started worker will load the repaired code; no new worker was activated for testing.

## Limits
No real-position exit/re-entry cycle was forced or tested. Broker execution/fill latency is not guaranteed. Source/cache regression checks do not establish millisecond cold Pine initialization or live-feed performance. Existing source publication can still take time; unmatched Supertrend output is shown truthfully rather than invented. This release does not change native broker stop placement or promise fee-inclusive break-even.
