# Sector Pulse project instructions

## Remote Ubuntu is the authoritative project workspace

User standing instruction, recorded 18 October 2026:

- Make all project code, configuration, and project-instruction changes only on the remote Ubuntu server, in `/home/trading/sector-heatmap` and the relevant hosted account/workspace source directories beneath it. Do not edit the local checkout or local project configuration, and do not implement or test project changes by modifying local copies.
- A local-only implementation, test result, commit, or prepared patch is not completion and is not deployment. Do not conclude that a requested change is completed or deployed until the requested code/configuration has actually been updated in the remote Ubuntu project and the relevant hosted behavior has been verified.
- Distinguish remote source updates, deployment/activation, and hosted verification in status reports. If any required step or verification is blocked or incomplete, state the exact limitation and keep the change described as incomplete or unverified; do not substitute a local result for remote/hosted evidence.
- This instruction applies throughout this project, including its isolated account/workspace source snapshots. Before changing a hosted feature, identify the source directory and process that actually own it; updating an unused remote copy alone does not establish deployment.
- Existing authorization boundaries remain in force. Do not infer permission to reload/restart services, start/resume/rearm runners, enter credentials or OTPs, or submit/modify/cancel orders from this workspace rule. Obtain the specific authorization required for those actions and preserve runner, position, order, and journal state unless the user explicitly authorizes a change.
- This instruction does not authorize resuming paused feature work or migrating previously prepared local changes. Resume or migrate such work only within the user’s explicit authorization.

## UI presentation and numeric display — standing user preference

Explicit user instruction, 24 October 2026. Apply to the entire project, all broker/account source snapshots, and future UI work.

- Every user interface change must be polished, presentable and executive in appearance in its first delivered version. Presentation is an acceptance requirement alongside functionality; the user must not need to repeat it.
- Reuse the established dashboard visual language. Plan clear information hierarchy, restrained typography/colour, consistent spacing, aligned controls, balanced proportions and responsive layouts.
- Place related actions in a deliberate toolbar or dedicated action column with consistent button sizes and primary/secondary hierarchy. Do not crowd buttons into recommendation/data cells, scatter controls, use awkward wrapping, or expose implementation jargon in user-facing labels.
- Review the actual rendered/hosted screen at desktop and narrow widths. Correct visible layout, alignment, clipping, overflow, spacing and interaction problems before claiming completion. Include meaningful visual verification for UI changes.
- Display decimal values with at most two decimal places throughout the UI: tables, chart labels/tooltips/legends, summaries, dialogs and new features. Whole-number quantities can remain integers.
- Retain full precision for calculations, stored data, risk logic, broker tick validation and order values. Apply rounding in display formatters; do not change trading behaviour to satisfy presentation rules. If an exact executable value cannot be represented faithfully under the display convention, resolve that explicitly instead of silently changing or hiding the order.

## Reusable FYERS NIFTY 50 historical archive

User requested project-wide persistence of these details on 25 October 2026.

- Authoritative remote archive: `/home/trading/sector-heatmap/data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/`.
- Symbol: `NSE:NIFTY50-INDEX`; provider: FYERS; timezone: Asia/Kolkata. These are index OHLCV candles, not constituent-stock or option data.
- Requested window: 25 October 2024–24 October 2026 inclusive. Actual returned coverage: 25 October 2024–23 October 2026, 494 sessions.
- Direct broker downloads: 1 minute = 184,638 candles; 5 minutes = 36,929; 30 minutes = 6,405. All 27 chunk requests succeeded at staging.
- Files: `nifty50_1m.csv/json`, `nifty50_5m.csv/json`, `nifty50_30m.csv/json`; original responses under `raw/`; `manifest.json` includes coverage and SHA-256 checksums; `audit_1m.json`, `audit_5m.json`, `audit_30m.json` include validation details; `README.md` explains reuse.
- Staged size approximately 44.43 MB including raw and merged copies. Resumable downloader: `scripts/stage_nifty50_two_years_fyers.py` (run from project root with `PYTHONPATH=. .venv/bin/python scripts/stage_nifty50_two_years_fyers.py`).
- Staging checks found zero duplicate timestamps, conflicting timestamps, invalid OHLC rows or within-session gap candidates. Off-hours candles were preserved and flagged (2024-11-01 and 2026-09-07/08/09); they are not all verified special sessions. Full exchange-calendar completeness and cross-timeframe price agreement were not verified. Do not present this as a certified gap-free market dataset.
- Reuse this archive for relevant research before downloading again. Read its current manifest/audits and apply session filtering suitable to the task. Preserve raw evidence; never fabricate missing candles or silently overwrite the archive. A rerun uses cached raw responses and is not a freshness update.
