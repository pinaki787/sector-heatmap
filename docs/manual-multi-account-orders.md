# Broker-wise Live allocation

Activated and authenticated hosted verification completed on 30 October 2026. The main dashboard and currently running Dhan, FYERS and Delta dashboards are healthy on the correct 8080 portal binding. The authenticated endpoint serves manual-multi-v1.

## Amount and selection
Use Live broker-wise allocation is an explicit user-controlled option. Only the displayed broker is initially ticked. Each broker row binds exactly one explicitly displayed owned execution account; multiple accounts of the same broker do not create duplicate pools. Optional overrides apply to that broker's pool.

Example: Rs50000 and five selected stocks with Dhan and FYERS ticked creates a Rs50000 Dhan pool distributed across its five stocks and a separate Rs50000 FYERS pool distributed across its five stocks. Combined potential pools are Rs100000. The amount is not multiplied per stock or divided among brokers.

Existing flow amount is the default where present. Standalone Dhan adds an editable Rs50000 amount field. Stock allocation uses the flow's equal or conviction-weighted rule, whole shares/lots, native prices, available funds/margin and existing risk gates. Review displays each broker pool, bound account, per-stock instrument/quantity/price/cash or margin/product, total pools, and independent broker outcomes. Display values use at most two decimals; internal values retain precision.

## Covered user-driven flows
- Exact Analysis Handoff ticket.
- Analysis Handoff selected-stock basket.
- Screener selected-stock basket, retaining conviction-weighted allocation.
- Manual Trade Parser submission: selecting the new mode creates reviews instead of direct submission.
- Standalone Dhan security-ID ticket: resolves its native master identity before mapping the same instrument to each selected broker.

FYERS, Dhan and Motilal retain their own native reviewed-order adapters and grants. Cross-broker mapping requires the same exchange, underlying, expiry, strike and option type. Native symbol codes may differ. Native standalone futures/currency, unsupported products/order modes, unverified option protection or unavailable broker adapters return explicit blocks. Delta does not acquire new entry capability. Telegram automation, strategy runners and schedules retain their existing authority and account scope. Investment is read-only and has no order entry to expand.

## Freshness, caps and retry behavior
New FYERS parser amount reviews require current profile, executable fresh two-sided depth, positions, pending orders, verified funds and full order value plus provision within the amount. Those flags/caps persist for submit-time revalidation. Dhan parser amount caps persist into native preflight and submit. Motilal parser amount review uses its native preflight and repeats it before submission. Existing native live flags and risk/protection gates remain enforced.

Owner-scoped private SQLite stores independent broker reviews and outcomes. A committed SUBMITTING claim precedes each network send. Repeated or concurrent requests cannot resend consumed rows. Lost responses or crashes remain uncertain/consumed and block new reviews for the affected account until operator broker reconciliation; this version never automatically clears an uncertain claim. Successfully submitted brokers can be omitted when preparing a fresh review for a previously blocked broker. Recent broker results are discoverable. Order acceptance is not reported as a fill.

## Validation and artifacts
117 focused Python tests and 5 UI tests pass, including 13 bounded restart guard tests. Tests cover broker pools across multiple stocks, overrides, duplicate same-broker prevention, positive finite budgets, exact native symbol portability without expiry/strike substitution, Paper rejection, source security-ID normalization, fresh FYERS amount/funds/position gates, owner binding, partial failures, concurrent retries and persisted lost-response/crash claims.
All seven account source snapshots compile and pass JavaScript syntax and integration-hook checks. Fresh amount-preflight AST checks run against root and every snapshot without starting services or placing orders.
The broader FYERS suite has seven pre-existing failures (two failures, five errors) reproduced against the exact backed-up pre-change module: September stock-option expiry fixtures are expired against the current clock.
Hosted desktop and narrow design preview verified using clearly labelled demonstration data with submission disabled. Screenshots are /private/tmp/multi-account-ticket-desktop.png and /private/tmp/multi-account-ticket-narrow.png on the local Mac.
Evidence resides in output/manual-multi-20261030/.

## Completed activation and hosted evidence
The arbitrary 4 MB reload rejection was replaced with full read-only, bounded 16 MB validation for known Renko schema/history. Symlinks, file races, malformed/duplicate/nonfinite JSON, unknown large schema, excessive depth/collections and active exposure remain blocked. Retained 6.04 MB Delta history is byte-identical.
Legacy snapshot parser definitions were replaced with the canonical broker-independent parser. Explicit NSE cash amount review resolves NSE:INFY-EQ rather than the NSE ticker or an expiry-bearing future. Broker routing now uses Dhan's existing owned native amount endpoint, FYERS' owned parser endpoint and Motilal's owner-scoped portal parser adapter. Section permissions and Live grants remain enforced.
Authenticated actual forms show only the current broker ticked by default, one bound execution account per broker and a choice of the two owned Dhan accounts. Actual FYERS plus Dhan preflight shows independent Rs50000 pools, combined Rs100000, and disabled submission. FYERS has no valid fresh two-sided depth after hours; Dhan returns expired/invalid saved session. No verification row was submitted. Standalone Dhan shows Dhan only selected, Rs50000 default and quantity-first input disabled in amount mode.
Actual desktop and narrow forms checked without horizontal overflow. Screenshots: /private/tmp/broker-wise-live-actual-desktop.png, /private/tmp/broker-wise-live-actual-narrow.png and /private/tmp/broker-wise-live-dhan-form.png. Temporary text drafts were cleared.
Saved Live grants, schedule policies and runner configurations match the before snapshot. Runners remain stopped; offline broker dashboards were not started. Native filled/accepted order execution was not tested or claimed.
Final machine-readable evidence: output/manual-multi-20261030/activation-final-verification.json.
