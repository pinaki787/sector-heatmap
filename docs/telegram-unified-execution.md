# Unified Telegram recommendation execution — 20 October 2026

## Implemented remotely, backend activation pending
The actual target is Telegram Trade Parser in the Delta India workspace used for BTC/ETH/gold-token recommendations. This does not add FYERS automatic execution or change the separate FYERS text parser. Other workspaces can retain their own receive/review context; Delta bought-option execution is account-bound.

One saved Paper/Live mode, whole-contract quantity, bought-ATM-option product and Renko exit configuration govern automatic recommendations and manual pasted text. BUY maps to a bought Call; SELL maps to a bought Put. Entry remains immediate at a fresh option quote, as in the existing Paper pipeline; recommendation underlying levels remain references. The UI states this and explicit Live consent covers quantity, immediate timing and Renko exits.

Connect starts reception only. Run explicitly arms the chosen configuration for new eligible posts. Stop prevents new entries while reception and owned Renko exits continue. Restart never rearms or imports backlog. Settings are preserved; migration does not activate execution.

Manual paste uses Parse / preview, then Submit labelled with that same mode and quantity. The backend captures configuration revision and rejects per-ticket mode/quantity/product overrides. Live requires explicit confirmation. Claims precede any order submission; duplicate, stale, edited, missed and uncertain recommendations are not replayed. Requested quantity stays distinct from confirmed partial fills.

The native Telegram submission bypass and legacy Bot Auto are retired. HTTP submit/option-submit/parse aliases use the same controller; old paper-start controls reject outdated clients. Existing native orders and submission audits stay readable and reconcilable. Selecting Paper does not convert, cancel or protect a pre-existing Live order.

## Validation and source staging
120 Telegram tests + 3 Delta Telegram tests + 20 workspace tests + 21 workspace-proxy tests + 4 mounted UI tests pass: 168 total. Tests cover automatic and manual Paper/Live dispatch under mocks, no native Live bypass, explicit Live consent, quantities, mode transitions, duplicates/backlog/edits, uncertain outcomes, partial fills, ownership, retained audit reconciliation and old-backend capability gating.
All changed Python source in the authoritative root and four owned workspace snapshots compiles; JavaScript syntax checks pass.
Protected originals and current audit snapshots are under .private/telegram-unified-backups. The source-only review patch is .private/telegram-unified-execution.patch and contains no credentials or production state.

## Activation boundary and preserved live state
No dashboard/service reload, polling start/stop, runner start/stop/rearm, or order mutation was performed for this implementation.
The Delta dashboard still runs PID 746619 with the user-started subscriber and legacy unattended Paper watcher. FYERS remains PID 205994; its active management was not interrupted.
The new static UI capability-checks the backend: while old code is running it displays the existing run and retained history but disables new unified submissions. No connection or execution starts on page load.
Activating the backend requires a controlled Delta account-dashboard reload, which would stop the current process-owned reader/watcher. Do not perform it while preserving the current run without a separately agreed handoff. The existing Live native order must be reconciled and handled explicitly, never cancelled or adopted automatically. The new start guard refuses unresolved owned orders.
Do not restart the parent sector-heatmap.service or the active FYERS manager. Only Delta is required for the crypto option executor; FYERS-specific prepared Telegram guard changes remain pending its own separately safe activation.
Live execution was tested only with mocks; no real Live run or order was authorized or started by this feature work.
