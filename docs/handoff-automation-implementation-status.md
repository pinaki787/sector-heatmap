# Handoff automation — historical implementation checkpoints

For current links and daily workflows, use [current operations](current-operations.md). The process IDs, account state and verification results below are historical evidence from their stated dates.

Verified on remote Ubuntu, 21 October 2026, after the 10:00 IST slot and approved Auto activation.
This file distinguishes source, active services, and broker-confirmed outcomes.

## Authorized requirements

- Fifteen-minute market-session analysis in both Manual and Auto; FYERS default and owned broker selection.
- Top five unique underlyings, strict normalized high-conviction ranking, unchanged-plan suppression and existing/pending exposure exclusion.
- Shared Rs100000 full-notional/premium pool: one lot per bought option first; equally distribute remaining capital across equities.
- Rs10000 current-day realized-plus-unrealized loss cutoff: halt new entries only; analysis, reconciliation, existing exit management and notifications continue.
- Validated recommended entry, stop and target, fresh exact contract/master/quote/funds checks, and exact broker protection reconciliation.
- Manual select-all by default, explicit review of exact tickets and confirmation, owner/account/revision/expiry/replay checks.
- Shared market reports go to Sector Pulse Trade Alerts. Confirmed fills/exits and periodic positions/PnL use private Sector Pulse Updates. Email remains own-account opt-in; empty/WAIT-only Handoff emails suppressed.
- Do not restart active unrelated managers, weaken broker gates, fabricate protective exits, or send a live test order.

## Current active state

- Root notification-admin sidecar reloaded at PID 963733. Main trading parent remains PID 205601; FYERS and other trading managers were not restarted.
- FYERS schedule is enabled in AUTO with live_authorized=true, shared capital 100000 and daily cutoff 10000. The real account session remains bound. Explicit authorized activation used scripts/activate_handoff_auto.py --activate-live after a successful live-data diagnostic; activation itself submitted zero orders.
- Slots through 09:45 completed. The first 10:00 isolated check entered REVIEW before market analysis because its initial heatmap HTTP read hit the legacy snapshot import bug; the bridge now uses the working owned /api/sector-analysis endpoint. No Handoff receipts/orders existed at activation. The next scheduled Auto slot is 10:15; do not claim its result before checking.
- Shared and private notification routing, independent card publisher, private fill observer and periodic private summaries are active. Two private position summaries were confirmed SENT earlier in the current session.
- Hosted Manual/Auto settings, select-all, exact-preview controls, pool and cutoff are visible. New Manual review API is loaded.
- New FYERS isolated analysis and sizing are loaded in the notification sidecar; the owned private worker imports current source without starting a dashboard runner.
- Dhan isolated analysis support is prepared in current sidecar/source using native Dhan candles and quotes; live Dhan scheduled analysis has not been exercised in this turn.
- Motilal account selection remains scoped; native protected Auto is explicitly unsupported pending a verified broker integration. No API capability is fabricated.

## Latest verified diagnosis and fixes

The earlier zero-result runs scanned zero stocks. Sector freshness used elapsed wall-clock time, marking the previous session's final hourly candle stale at the opening after a holiday.
- Intraday freshness now counts trading-session time, preserving stale blocks for genuine missing sessions and intraday gaps.
- Read-only FYERS verification confirms FMCG's last completed hourly candle from 19 October is valid on 21 October before the first current-day hour completes.
- Weekly Handoff evidence excludes the forming week. The latest completed weekly candle is 16 October. Legacy dashboard compatibility charts deliberately match their served snapshot anchors and are not consumed by the new Handoff engine.
- The isolated engine rechecks current broker exposure before and after analysis; it cannot place orders.
- FYERS state reads confirmed two existing bought stock options, used premium Rs11861.25, no pending orders at preflight, funds about Rs78121.93, daily loss below Rs10000. These are transient observations, not durable assertions.
- Multiple pending orders now reserve cumulative notional; commodity valuation requires a positive native multiplier. Unknown evidence fails closed.
- Per-route scan scopes and exclusion evidence are retained for explaining zero-result reports; the latest status/UI enhancements and read-only diagnostic endpoint are loaded.

## Implemented components

handoff_allocation.py: Decimal allocation, normalized conviction, durable claims.
handoff_schedule.py: durable session slots, no replay, report-before-order publication, daily-loss latch, entry-only halt, read-only receipt recovery, next-open fresh-analysis intent.
handoff_analysis.py: reusable real rule engine and fresh structural sizing; no dashboard/runner startup.
handoff_fyers_analysis.py: account-isolated native history, master, depth, positions, orders and option chains.
handoff_bridge.py: real-session ownership, independent reports, native worker tickets; no session minting.
handoff_execution_worker.py / handoff_ticket_client.py: private stdin/stdout, durable reservation and exact preview guards, no automatic retry after uncertain response.
fyers_protection.py / dhan_protection.py: exact IDs, contract, side, product, quantities, fills and registered stop/target; acknowledgement alone is not a confirmed fill or guaranteed exit.
handoff_manual.py: mixed-pool exact selected-ticket review and consumed confirmation.
handoff_observer.py: exact linked confirmed fills only; position disappearance never proves an exit.
handoff-schedule.js: mode, allocation, selected recommendations, prominent select-all, exact confirmation, pause/resume entry controls.
scripts/verify_handoff_automation.py: repeatable read-only real-account checks, optional completed-candle evidence, zero test orders.
scripts/activate_handoff_auto.py: read-only default; explicit authorized activation flag, native gate checks, no in-flight-run interruption and durable activation audit. Never sends a test order.

## Broker restrictions and remaining verification

- FYERS API/algo AMO is prohibited by its published rules. The enabled scheduler queues a clearly labelled next-open fresh-analysis intent and can submit a regular protected order after revalidation. It never claims broker-accepted AMO or reuses an old-price order.
- Verify the first Auto scheduled run, including actual scan/exclusion counts and shared delivery for any new eligible plans. A completed read-only diagnostic already verified 2 eligible sector scans, 6 stocks examined and 2 alignment matches per route. VBL was excluded for existing exposure; BAJAJFINSV produced validated cash and bought-option route plans. These are route-specific, not two distinct stocks; the scheduler enforces one underlying.
- Approved FYERS Auto policy is now enabled and hosted UI confirms AUTO plus account-session bound. No additional permission was requested. The isolated entry adapter was fixed to use sized.fresh_quote.price, not a nonexistent active_invalidation.entry field; a real-engine-to-adapter regression test passes.
- No live Handoff submission or broker-confirmed Handoff protection has yet occurred; do not claim either.
- Dhan native analysis/execution is implemented and unit-tested. Current read-only Dhan positions, orders, funds, holdings and Live capability passed with zero orders submitted; the scheduled integration remains unverified.
- Motilal native protected Auto remains incomplete. Preserve native captured-history restrictions and owner authentication; never substitute another broker's data or independent unlinked exit orders.
- Existing FYERS legacy Renko unresolved retained state remains untouched.

## Verification in this turn

- 98 Handoff tests pass, including allocation, schedule, Manual replay/owner checks, broker reads, isolated analysis and observer behavior.
- 47 sector tests pass, including holiday reopening, missing sessions, true intraday gaps and forming-week exclusion.
- 34 notification tests pass.
- Manual selection/preview/exact-confirmation JSDOM test passes; schedule payload test passes.
- Isolated analysis tests exercise the real bearish rule engine, fresh structural stop/target, and exposure appearing during analysis.
- Real read-only account/master/history/depth capability checks pass; no broker order was submitted by verification.


The hosted "Diagnose current scan" action is read-only, does not consume a schedule slot, does not publish reports, and never submits an order. It shows per-route scan counts and exclusions. It uses a separate owned private worker so it cannot consume or overwrite the scheduler ticket previews. Diagnostic workers close after completion. Do not restart notification-admin while an Auto run or uncertain broker receipt is in flight.

Additional source safeguard: Schedule(recover_interrupted=False) lets the authorized activation utility validate policy without marking the running service's slots interrupted. Default service startup recovery remains enabled.

## Checkpoint after 10:20 IST

- First Auto slot 10:15 entered REVIEW with one SUBMITTING receipt for BAJAJFINSV equity, 47 shares, allocated Rs78880.10. It did not create the mandatory durable handoff-intents file. Fresh broker orderbook contains no BAJAJFINSV equity order; no broker exposure exists for that symbol. Native read-only re-preview succeeds. No order was retried.
- The claim is UNCERTAIN and blocks further Auto entries while analysis continues. The generic exception handler lost the original pre-submit reason. NEXT: distinguish provably pre-submit failures from uncertain broker responses, retain the exact safe error, release only proven-unsubmitted reservations without replay, and test this boundary. Do not mark an absent position as an exit or clear a possibly submitted intent.
- Root Auto coordinator PID963733, private ticket worker970732, main trading parent205601, FYERS205994. Do not restart the Auto coordinator while any run or actual broker submission is in flight. Broker-verified absence plus the durable-intent-before-mutation invariant establishes this current receipt never reached the submit boundary; preserve an audit when resolving it.
- New compact Telegram formatter is active in the isolated notification sender PID974059 after explicit user restart approval relayed by the notifications task. Only sector-pulse-notifications.service restarted; its unit has no trading PartOf/BindsTo dependencies. Dashboard, coordinator and trading PIDs unchanged. Source telegram_trade_format.py and durable telegram_parts tracking pass 6 tests; existing trade12 and notification34 tests pass. No unsolicited format test message or replay was sent. Verify next natural private POSITION_SUMMARY delivery at 10:30.
- Sector Pulse Updates is the configured PRIVATE trade/position channel. Sector Pulse Trade Alerts is the SHARED market-report channel. Names were verified from protected config without printing secrets or chat identifiers.
- A separately explicitly authorized one-off sector summary was posted to shared Sector Pulse Trade Alerts. Telegram accepted message11. The standard card covers all14 sectors, actual saved market data 21 October2026 09:45 IST, clearly labelled completed-candle snapshot. No email row/copy was created. Script scripts/post_sector_summary.py defaults read-only; --send-authorized posts once, deduplicates the actual source summary, atomically marks delivery SENDING so the running worker cannot duplicate it, and retains exact channel/message acknowledgement in the protected sector-cards audit.
- sector_cards.send_card gained optional audit callback; existing worker is not restarted. Nine sector-card tests pass. One-off event sector-manual-* is SENT in sector-outbox.sqlite3; protected *-telegram.json records message ID, channel, actual data time and image hash.
- docs/telegram-private-updates-preview.md is an earlier longer draft and must be refreshed to match the compact active formatter before presenting it.

## Current checkpoint — 21 October 2026, after 11:10 IST (supersedes earlier activation notes)

- The isolated notification-admin coordinator was reloaded only after checking zero RUNNING slots and exactly one NOT_SUBMITTED receipt. It is active as PID1001665; main trading parent remains PID205601. No sender or trading-service restart occurred in this checkpoint.
- Before-submit failures now use a typed boundary. Only provably unsubmitted reservations close; after-submit unknowns retain reconciliation holds and never replay. The earlier 10:15 receipt was independently audited against the mandatory durable-intent-before-submit invariant and fresh native orderbook, resolved NOT_SUBMITTED, and its fingerprint remains consumed.
- Report deduplication no longer prevents the first execution of a freshly revalidated, previously untraded idea. All claimed fingerprints remain excluded from execution, including closed claims.
- Options retain exactly one lot, execute first, and use only available pool capital. Cash sizing uses refreshed quotes, can shrink whole shares to the assigned allocation, then redistributes actual remaining capacity equally. Exact previews bind native action, quantity, price, stop and target before submission. Full broker fills release only actual unused reservation headroom.
- Manual review skips newly exposed selected underlyings and displays exclusions plus a readable exact-ticket table. Select-all remains prominent and selection does not submit.
- Remote verification: 112 Handoff tests pass; two Manual/schedule UI tests pass, including visible zero-capacity status. Existing sector50, FYERS protection16, notification34, trade12 and formatter6 checks passed in the preceding checkpoint.
- Real authenticated hosted FYERS UI shows Enabled / AUTO / account session bound / available for new entries Rs0. The authorized activation utility restored the Rs100000 pool and Rs10000 daily loss limit without placing any order.
- Fresh account verification immediately before activation showed used full-notional capital Rs207731.20, funds Rs55544.92 and exposed BAJAJFINSV, DMART and VBL. This exceeds the pool; new Handoff entries must remain blocked. Do not change/close outside positions to free capacity.
- Latest completed slot at this checkpoint: 11:00 IST, no error, zero executable plans, zero new reports, available capital zero, no Handoff execution. 10:45 completed with two recommendation cards. Await the first post-reload natural slot; do not claim it completed before inspecting it.
- Compact private position formatting was naturally delivered at10:30 to Sector Pulse Updates and verified through SENT part state and exact configured destination hash. The earlier draft document has been updated.
- Native Dhan read-only two-route analysis integration verification is running through scripts/verify_handoff_analysis.py; it cannot publish reports or submit orders, and does not enable another schedule. Its result remains pending.
- Motilal is selectable by ownership, but native protected Auto remains incomplete. Current official place-order documentation lists ordinary LIMIT/MARKET/STOPLOSS and normal product types; response fields called stoploss/squareoff alone do not establish a supported linked protective-order request. Source: https://invest.motilaloswal.com/moAPI/APIDocumentation/Introduction
- Goal remains incomplete: post-reload natural schedule evidence, Dhan native analysis verification and Motilal protected execution/analysis support still require work. No live Handoff fill or broker-confirmed Handoff protection is claimed.

### Dhan native integration result
Read-only scripts/verify_handoff_analysis.py completed successfully using the exact owned Dhan account. Both cash_equity and stock_options routes examined3 stocks, matched1, produced1 card and zero exclusions. No report was published and no order submitted; no Dhan schedule enabled. This verifies native two-route analysis in the same isolated worker used by scheduling, not an actual Dhan protected fill or full scheduled submission lifecycle.

### Post-reload scheduled verification — 11:15 IST
The natural11:15 FYERS AUTO slot completed without error after loading coordinatorPID1001665. It returned available capital0, zero eligible recommendations, zero new shared cards and zero executions. This proves the reloaded schedule runs; it does not prove a live Handoff fill/protective-exit lifecycle. MainPID205601 and FYERSPID205994 remain unchanged. The hosted UI displays AUTO, bound session and zero available capital. No remaining activation permission is needed; the outstanding scope is Motilal native protected integration and end-to-end fill/exit evidence when a genuinely eligible order exists within the configured pool.

### Motilal analysis preparation — 21 October, after 11:15 IST
The exact owned Motilal account has a saved but expired native session; fresh broker evidence is unavailable. No login, token refresh, service start or order was attempted. The existing native captured-candle Provider now removes forming intraday/daily/weekly bars and bars without real volume; three dedicated tests pass. The private Handoff worker can initialize the native Motilal Sectors/Handoff analysis provider and structural sizing while rejecting prepare/submit/reconcile before touching native order methods. Eight worker tests pass, including two Motilal boundaries. Updated source is copied to existing account snapshots, but scheduled Motilal bridge activation is not claimed: reauthentication and a verified native linked stop/target route remain outstanding. Existing FYERS schedule and trading processes were not restarted.

Motilal read diagnostics now emit a fixed safe sign-in/reconnect message for typed native authentication expiry, without exposing exception payloads; 18 broker-read tests pass. A live isolated read confirms the reconnect message. User was asked to reconnect the expired account. Dhan's second read-only verifier includes fresh structural sizing for the first recommendation of each route and remains in progress; it never prepares/submits an order or publishes reports.

### Dhan fresh sizing result
The read-only two-route native Dhan check with --size completed successfully: [{"route": "cash_equity", "cards": 2, "sized": 1, "scanned": 6, "matched": 2}, {"route": "stock_options", "cards": 2, "sized": 1, "scanned": 6, "matched": 2}]. One recommendation per route was freshly structurally sized using the native account quote. Orders submitted0; reports published0; no order preparation or submission occurred. The broad Handoff suite passed114 tests after the Motilal worker addition; the subsequent safe-error change passed all18 broker-read tests. Motilal expiry/live protected integration remain outstanding; FYERS AUTO remains bound to its existing active coordinator.

### Shared channel and saved-output repair — 21 October, around 11:30 IST
Direct authenticated Telegram inspection confirmed the exact configured shared Sector Pulse Trade Alerts channel contains Handoff posts at10:16,10:30 and10:46. The10:30 and10:46 retained reports contain bearish Bajaj Finserv and Varun Beverages findings. Generic captions obscured the stock names; future captions now list up to5 names with bullish/green or bearish/red markers and normalized conviction. Empty reports explicitly say no eligible recommendations. Eleven sector-card tests pass. Private trade formatting bypasses retained market images, tested separately (7 formatter/transport tests).
Open saved output previously populated a section below the long jobs list without scrolling or focusing it. Explicit open now reveals and focuses that section, while background runner updates preserve the reading position. Root and existing hosted snapshot assets/cache tags updated;2 feedback UI tests pass. Hosted authenticated verification confirmed focus and output position inside the visible dialog; no analysis/order/runner control clicked.
Reloaded only the isolated Handoff publisher after verifying zero SENDING deliveries and no trading service dependencies; newPID1013478. Main tradingPID205601 unchanged. Existing historical messages were not replayed or edited; no extra test post sent. The old user tab was not reloaded; verified in a separate current dashboard tab.

### Readable saved reports — 21 October, around 11:45 IST
Saved Handoff output now renders broker/route/time, scan counts, recommendation cards with direction color, normalized conviction and plan prices; exclusions and full JSON are collapsed. DOM construction uses textContent, not interpolated HTML. Unknown saved analysis gets a summary and scalar metadata with raw data collapsed. Three focused feedback UI tests pass, including readable currency, red bearish direction, escaped markup, collapsed raw data and focus/scroll. Root and hosted snapshot assets/cache tags updated without server restart. Hosted verification confirmed FYERS10:47 and Dhan10:29 saved reports render readable empty outcomes rather than JSON dumps. A broader independent runner-jobs test failed because its runner-only fixture had no tbody checkbox; it does not load analysis-jobs.js and was not modified. No claim that the entire runner suite passed.

### Latest-first saved output ordering — 21 October, around 11:50 IST
The job list previously sorted by job creation while displaying last-update timestamps. It now groups analysis first and sorts by updated/completion time descending, then creation time and stable identity. Runner history follows. Automatic restore selection still uses original job creation semantics so an old long-running job cannot silently replace a newer requested analysis. Four focused UI tests pass, including crossed start/completion order, runner separation and missing-update fallback. Hosted first rows verified10:47:14,10:29:10,09:45:30,09:45:26,09:45:18 in descending order. Root and existing hosted account assets/cache tags updated; no services or trading changed.


### Periodic Handoff silence diagnosis and status publishing — 22 October, pre-open
Authoritative run audit:21 October had20 COMPLETED and5 REVIEW slots. The15:15 completed slot had no recommendation cards because native preparation exclusions reported FYERS API request limits;14:45 and15:00 failed fresh orderbook reads. The publisher previously filtered out all scheduled reports with no cards, including empty/duplicate results and failed analysis, leaving no visible periodic status.
The notification publisher now surfaces each terminal scheduled slot: actual fresh cards remain unchanged; empty completed slots publish NO_NEW_SIGNALS; broker evidence/rate-limit failures publish sanitized DATA_UNAVAILABLE/RATE_LIMITED statuses. Private capital, positions, raw errors and order data are omitted. Empty email remains SKIPPED; slot-key dedup and stale/backfill guards remain intact. Failed checks are labelled check time rather than claiming fresh market-data time.
Seven new scheduled-status tests pass and11 sector-card tests pass. Reloaded only sector-pulse-handoff-cards.service after zero SENDING rows and no trading dependency were verified; publisherPID1050937. Trading205601 and coordinator1001665 unchanged. No historical notification replay or test post sent.
Hosted authenticated FYERS Handoff panel currently shows enabledAUTO but session unbound, with account-session expired/access-changed error. The scheduler cannot start new cycles until the human signs in and saves the schedule. No Auto browser-save, policy change, credential action or session rebinding was performed. Today was still before market-hours scheduling at verification; no actual new-day status delivery is claimed.


### Optional duplicate reports — 22 October
Added per-account allow_duplicate_reports, default false, strict boolean validation and an Allow duplicate reports checkbox. When enabled, reporting ignores the reported-fingerprint set for each new schedule slot; execution still filters every durable claim and existing/pending exposure. Repeated reporting never clears claims, retries a consumed order, bypasses broker gates or changes capital.
25 scheduler tests pass, including repeated report cards across two AUTO slots with only one execution call;3 UI/payload tests pass. Existing hosted account source snapshots and browser cache tags updated. Reloaded only the notification-admin coordinator after verifying zero RUNNING slots and only NOT_SUBMITTED receipts; newPID1054108, trading205601 unchanged.
Hosted checkbox is visible and initially unchecked. No Save schedule, account rebinding, reporting opt-in or trade-mode change was performed through the browser. Current hosted mode reads MANUAL; preserve that externally selected policy.

### Handoff presentation repair — 22 October
The scheduled-selection and prepare rows had no reliable vertical separation, and legacy market-handoff responsive selectors overrode button widths. Added scoped schedule presentation: three aligned setting fields, a separate reporting-options group, consistent action gaps, readable status treatment, section dividers and responsive full-width stacked buttons. Specificity explicitly matches the existing Handoff namespace; no trading logic or setting changes.
Hosted geometry verified all17 visible Handoff buttons have no pairwise desktop intersections and no horizontal page overflow. At320 physical viewport /400 CSS pixels with existing browser zoom, action buttons fill their327-pixel row with12-pixel button gaps and16-pixel row separation; no horizontal overflow. Temporary viewport override reset. Existing3 UI/payload tests pass. User-saved policy currentlyMANUAL, duplicate reporting enabled, real account session bound; preserved without browser Save or service reload. Root and hosted account assets/cache tag updated.
