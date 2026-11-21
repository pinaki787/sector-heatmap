# Delta Simple Brick incident — 6 November 2026

Kernel evidence confirms global OOM killed Delta dashboard PID861774 at17:55:28 UTC (23:25:28 IST), approximately5.9GB resident anonymous memory. Port8101 stopped listening. No recovery/restart or runner action performed.

ETH instance b659338b2d1c8d4848e5, captured run RENKO-RUN-14a409d61680fc8cfbf7, was LIVE Simple Brick, flat with no pending order and zero trades. Price-confirmed sidecar contains qualified COMPLETED_BRICK_COLOR events. The execution assessment in the current run is STALE_PRICE_EVENT: expired during preflight; no replay. The earlier last_signal and indicator assessments belong to older runs and must not explain the current run. Precise source of preflight delay remains unproven.

Connected Delta production API read-only verification: no order history since run start, no open orders, no ETH positions. No order submitted by this investigation.

Prepared fixes in root and seven account sources: provisional Supertrend visibility now follows selected study; chart lines start hidden to avoid transient/unselected lines during interrupted asynchronous rendering. Live display engine keeps500 calculation rows while retaining full display history, avoiding a duplicate full history copy. Live chart settings cache bounded to4; Delta analysis contexts bounded to2, with same-anchor reconstruction when evicted. Calculation guards and runner execution rules unchanged. This reduces retained display memory; it does not prove the full OOM allocation cause.

Validation:29 Python live-chart/recovery tests,5 Node Simple Brick tests, mounted editor sync and no-execution-mutation check passed. Backup .private/delta-display-memory-1793987902. Backend activation and hosted verification remain pending: require explicit recovery approval because saved state was LIVE. Recovery must leave trading unarmed; no old event replay or Start.

## Approved recovery and transport correction

User approved recovery with trading stopped. Verified hosted runtime STOPPED and connected broker no open orders/ETH positions. Persisted stale pre-crash running flags as stopped under canonical lock, preserving config, orders, position and pending; evidence .private/delta-approved-recovery-1793988501. Guarded Delta-only reload reached READY.

Subsequent hosted inspection measured a52MB full-history SSE event, plus approximately649KB status-only events. Added incremental completed-brick delivery and5000-row browser display retention; no historical report truncation. On SSE startup advertise the revision rather than resend HTTP history. Reconnect/reseed/new-generation full recovery remains supported.38 Python tests,13 Node tests and mounted editor-sync passed. Final approved guarded reload reached READY; trading remains stopped. Backup .private/delta-chart-incremental-1793988617.

Automatic review rejected reloading the original tab because it has pending unsaved settings. That tab was preserved; validation continued in a separate agent-created view.

Final hosted verification: authenticated ETHUSD five-minute chart rendered completed Simple Brick observations, live ticks aged0–3s, studies unselected/hidden, runner stopped. Consecutive SSE frames remained fresh for20+seconds with no repeated52MB startup payload. Final serving process and stopped-state evidence: .private/delta-approved-recovery-1793988501/final-verification.json. A separate verified dashboard tab was left open; original pending draft preserved. Live order submission remains untested and was not authorized.
