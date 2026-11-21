# Motilal Oswal in the existing Sector Pulse workflows

Motilal has a private connection page, not a separate trading section. Select the saved Motilal account in Renko Supertrend, Analysis handoff, Screener or Sector rotation. The existing section permissions and visibility settings apply. Account credentials and daily login remain in Broker accounts / Broker connection.

## Market data and warmup

The selected policy is **Motilal data only**. Native index and instrument masters map the underlying to exact Motilal tokens. Native WebSocket ticks are retained in the private account SQLite archive. The capture tracks connection generation, exchange and receipt timestamps, uninterrupted opening coverage, and gaps. Higher-timeframe buckets align with the segment opening. An index code has its own namespace and cannot collide with a cash scrip code.

Missing history stays unavailable. No FYERS/Dhan candles, invented gap bars or guessed historical endpoint are used. Renko can warm up from captured completed candles. Manual reference brick sizing requires the configured number of fully completed reference sessions. Sector/Screener/Handoff require substantially longer daily/weekly history; these do not become ready just because the broker is authenticated. Volume-dependent evidence also requires native volume coverage.

The published EOD endpoint is a latest snapshot, not a dated intraday-history API. Its availability alone is not permission to treat it as a backfill. It is not connected to automatic signal history in this revision.

## Native execution

Renko uses the shared engine and persistent per-instrument runner records, with a Motilal execution adapter. Paper stays simulated; Live uses native LIMIT IOC orders after fresh depth, profile/segment/product checks, native whole-lot conversion, funds, pending-order and position checks. A strategy switch or selecting an account does not arm the runner.

Full runner intent tags map durably to unique native tags of ten characters. SQLite intent claims precede each broker mutation. Unknown acknowledgements cannot replay; reconciliation requires exact account, exchange, token, side, product, units, lot size and price evidence. An acknowledged order awaiting the book blocks new entries. A closing sell requires the exact confirmed owned quantity. Unrelated broker orders never acquire strategy ownership.

Shared Handoff/Screener reviewed tickets preserve the chosen account, allocation cap and quantities. They recheck executable depth and capability before submission and consume the review once. A requested Paper ticket is never upgraded to Live. Broker acceptance is not a confirmed fill. A partially completed batch is reported for reconciliation and does not resume automatically.

## Explicit limitations

- Native option analysis preserves the existing Greeks/liquidity gates. The current native feed supplies no complete Greeks; option analysis routes show the evidence unavailable rather than borrowing values or weakening the gates.
- Protected multi-leg spread submission is not enabled for Motilal. It must not become an uncovered short order. The three screener choices remain visible with route-specific eligibility reasons.
- Shared manual cash tickets currently support bought equity. Naked cash shorts are not inferred.
- MCX automatic option routing is blocked until exact option-to-futures-month linkage can be verified; no nearest-month guess is used.
- Motilal fees are not estimated using FYERS/Dhan rates. Gross fill evidence and after-cost P/L are distinct; unavailable costs remain unavailable.
- This integration has not been verified by placing a real order or arming a Live runner.

## Maintenance

Broker bounce checks canonical Motilal runner records outside the worker's source directory, native positions/pending orders, and unresolved durable intents. Runners are never automatically armed. Main-service deployment must also check these account-level records, and preserve unrelated broker worker PIDs.

Sessions expire daily at 06:00 IST. Credentials/tokens remain private and are omitted from logs and validation artifacts. Upstream callback logging must continue to redact the `authtoken` query.

## References

- [Motilal API documentation](https://invest.motilaloswal.com/moAPI/APIDocumentation/Introduction)
- [Official Python SDK](https://github.com/motradingapi/PythonSDK)

## Verification

    .venv/bin/python -m unittest sector_heatmap.test_motilal_api sector_heatmap.test_motilal_execution sector_heatmap.test_motilal_service sector_heatmap.test_motilal_server sector_heatmap.test_motilal_shared sector_heatmap.test_motilal_dispatch tests.test_motilal_workspaces -q
    node --test tests/motilal-order-route.test.cjs
    node tests/motilal-renko-mounted.cjs
    SCREENER_UI_SOURCE=outputs/motilal-oswal-integration/shared-route-patch/dashboard-enhancements.js node --test tests/screener-three-routes.test.cjs
