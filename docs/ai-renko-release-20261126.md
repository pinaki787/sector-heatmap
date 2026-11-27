# AI Renko release — 26 November 2026

The release implements the requested AI Renko lifecycle and chart changes. It does not activate trading.

| Requirement | Implementation and verification |
| --- | --- |
| Motilal analysis and execution separation | FYERS supplies analytical prices/history and chart data. Motilal retains execution identifiers, orders, fills and positions. Read-only checks matched equity, index futures, commodity futures and option contracts. |
| Opposite option entries | Independently persisted Call/Put ownership permits the new contract while the old owned closing leg reconciles. Partial/unknown outcomes and multi-leg Stop are covered offline. |
| Futures/equity reversals | Retain the qualifying signal, close the exact owned net position, confirm broker-flat, then enter the opposite side. FYERS, Delta and Dhan retain their market-order boundaries. Motilal uses the approved protected LIMIT IOC alternative. |
| Failed-exit notices | Exact unresolved legs remain flagged until broker-confirmed closure. Production-renderer fixtures cover persistence, clearing and account isolation. |
| Settings restoration | User, broker account and exact instrument scope; hosted switching/refresh verified. Manual parent validity is not renewed by restoration. |
| Instrument filters/defaults | Separate MCX Futures/Options, Renko by default unless a saved choice exists, and editable Intraday defaults for eligible direct routes. Hosted controls verified. |
| Entry and current P&L lines | Arrow-only fills, fixed entry and moving price lines; exact-position gross money P&L where reliable, otherwise directional points. Existing quote/journal data is reused. Actual open-position trading was not exercised. |
| Parent sizing | Persistent once-per-instrument/session acquisition and deduplication, including failures. A same-scope current-session user parent value supplies the explicit manual fallback. Provider availability is not guaranteed. |
| Candle ingestion/recovery | Identical duplicates are idempotent; committed completed OHLC is immutable and persists across restart. Contradictions are quarantined. A single unresolved minute receives two independent narrow refetches within a bounded incident budget. No arbitrary first/last selection or alternate data account is used. |

## Motilal protected execution

The default protective buffer is **one native tick** beyond fresh ask for buys or bid for sells. The captured policy supports 1–5 ticks; the dashboard default is one. Both direct entry and exit are LIMIT IOC and may remain unfilled. The original limit/bound is persisted before submission. Unknown acceptance never causes a blind retry.

Intraday maps to native VALUEPLUS; futures Margin maps to NORMAL. Cash direct shorts require Intraday. Until a per-order leveraged-margin estimator is verified, the local preflight requires full economic contract value plus a 1% reserve. This conservative check can reject an order that the broker might otherwise permit on leveraged margin.

## Verification boundaries

- The staged release snapshot passes 616 AI strategy tests, 119 focused frontend tests, and the separate chart-access/quote checks reported with the release.
- Guarded dashboards were loaded for FYERS, Delta India, Motilal and the selected Dhan account. Six maintained source copies and future provisioning include the dependencies.
- Desktop and narrow hosted Motilal controls were checked without initiating a runner.
- The captured Sensex Call and Put history incidents recovered to validated completed regular-session histories through 15:29 IST. The anonymized regression fixture contains public instrument/OHLC data only.
- No initial runner activation or real test order was performed. Live fill quality, real simultaneous option legs and real-position overlays require a user-started run.
- A broader legacy frontend sweep has failures outside the focused AI release checks; this release does not claim the entire application's test suite is green.
- Account credentials, owner snapshots, journals, runtime ledgers and private audit records are excluded from Git.

Delta remains available for the user's own test on a supported instrument, subject to normal sizing, fresh-data, ownership, funds and session checks. No settings or positions are changed by this release report.

## Strategy selection on section entry
The actual Strategy mode defaults to AI Renko Supertrend on every section entry/re-entry and refresh, ignoring legacy saved generic-mode values. A deliberately chosen alternative remains selected for the current visit. Account-context hydration cannot reinstate an old generic default. This client-only selection never activates or changes a running strategy. Hosted Delta re-entry/refresh and narrow layout checks passed; the focused frontend suite now contains 119 passing checks.

## Start admission correction
Start validates the actual captured broker/execution route against the release allowlist, rather than an empty configuration. A permitted route can proceed to the explicit user-Start gates; unreleased routes and a global hold remain blocked. No Start is replayed during deployment. Historical manual-request errors are contextualized when the stopped strategy ledger retains no exposure or intent, without deleting or altering their records.

## Delta source-health correction — 27 November

The first user-started PAXG test stopped after 30 seconds without a candle-price
callback. That timer did not distinguish a quiet trade stream from transport
failure; the old run did not archive transport heartbeats, so its precise
upstream cause cannot be reconstructed from that timer alone.

The public adapter now records real server heartbeats separately. During a
candle-price pause the worker waits, without manual or automatic entry decisions,
only while the selected symbol has a fresh executable quote and a fresh transport
heartbeat. Heartbeat freshness follows Delta's documented 30-second interval plus
5-second grace; executable quotes retain the existing 15-second bound. Stale
health permits at most three subscription repairs, spaced ten seconds apart.
Exhaustion or disconnection preserves exposure and blocks execution. Reconnection
still requires history reconciliation; it does not silently resume an old
indicator state. No heartbeat or book quote is converted into a trade or candle.
Pre-pause entry confirmations are cleared so resumed fresh data cannot replay a
retained entry signal. Stop/position-control polling remains available while
waiting.

All 624 AI strategy tests pass. This source is distributed for the next
user-started worker; the stopped PAXG worker was not restarted, and no orders were
placed. Browser chart health is independent of worker health.

## Embedded chart interaction correction — 27 November

Fullscreen now uses the browser fullscreen API on the chart section, with
explicit iframe permission. The chart's dialog is not itself a valid native
fullscreen target. Escape/button exit synchronizes layout and accessibility
state. Hosted desktop and 390-pixel checks confirm expansion and restoration;
horizontal/vertical dragging and wheel zoom were exercised without trading.
OHLC and order-preview controls share a compact header row, preserving the
indicator information. Fifteen focused UI checks pass. This static change adds
no broker requests or tick processing.

## Delta market-order reconciliation — 27 November

The fill normalizer now accepts the captured IOC market-order policy without
requiring a limit price. IOC remains a time-in-force setting, independent of
market versus limit order type, as documented by Delta India. Account identity,
requested/filled quantity, side, reduce-only intent and terminal-state validation
remain enforced. Direct perpetual market exits retain reduce-only; the existing
bought-option exit policy is preserved. Unknown and partial outcomes remain
retained rather than resubmitted.

A stopped-worker recovery utility validates complete selected-account order and
fill evidence, native/client-order identity, the exact full closing order and
current broker exposure before resolving an older intent. A separately verified
later manual holding remains external and is never attached or altered. Recovery
appends durable journal evidence and confirmed markers idempotently; decision
times are not substituted for known broker fill times. Unverified total costs and
net profit remain unavailable. Small contract multipliers display as exact
fractions instead of rounding to zero.

The hosted selected Delta dashboard was guarded-reloaded with trading stopped.
The recovered closed trade is visible, the matching obsolete recovery error is
historical, and Start eligibility is restored after a fresh flat/no-order check.
No live worker was started and no broker order was submitted, changed or cancelled.
The corrected real-order fill path has offline boundary coverage; it was not
exercised with a new live test trade.

Official references:
- https://docs.delta.exchange/#createorderrequest
- https://guides.delta.exchange/delta-exchange-india-user-guide/exchange-sop-and-policies/allowed-trading-bands

The P&L path also consumes an independent, incremental confirmed-fill receipt
stream. Delta persists a validated full fill and its position before downstream
worker callbacks; receipt ingestion is idempotent with the ordinary action log.
Unknown/partial outcomes never become full-fill evidence. Delta's recorded
quantity multiplier is included, so contract counts convert correctly to USD
gross P&L. Existing chart/journal quotes are reused with the existing freshness
and exact-entry-order matching checks; unrelated manual holdings are excluded.
Isolated browser fixtures verify gains, losses, stale fallback and zero lines
after close. This adds no broker request or per-tick history download. Real
open-position overlay validation remains unperformed while the account is flat.

## Recovered control mode on a subsequent user Start

A verified closed Delta direct trade no longer leaves a new user-started Live
worker inheriting RECOVERY_REQUIRED. Rearm requires the exact account's durable
closed-recovery proof, no retained ownership/order slots, and a fresh authenticated
selected-contract position/order-book check. It clears pre-existing entry signals
and records a management audit; management-only and attachment workers stay
paused. Empty local ownership alone is not accepted as broker-flat evidence.

The already-running older worker cannot hot-load this constructor correction.
A separately approved controlled restart reseeded history under unchanged captured
settings and a new runtime identity. The new worker acknowledged MANAGED with
entries unpaused and processed fresh broker prices; no entry was forced.
The UI also explicitly identifies an active recovery pause rather than implying
that a running process is ready to trade. Unknown exposure and failed broker
verification continue to block rearm.
