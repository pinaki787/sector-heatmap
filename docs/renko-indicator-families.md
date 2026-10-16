# Renko Supertrend indicator-family masters

Six grouped strategy families: Renko Supertrend, EMA, RSI, ADX, Market structure, Supply / demand zones.

Each master OFF masks every entry/retest/exit dependency owned by that family. EMA10 retest additionally requires both EMA and Supertrend masters. Subordinate choices and numeric settings are retained and restored on re-enable. Chart-only destinations remain independent. Changes are draft settings for the next Start; they do not alter an active runner.

Legacy configurations without masters retain their original recovery identity. Explicit master configurations persist raw subordinate choices plus applied-master metadata, so masked runtime flags can be restored without overwriting deliberate enabled-family updates.

## Validation

- 32 focused Python family, adoption/recovery and runner checks pass.
- 87 Node settings, destinations and family checks pass.
- Isolated jsdom mount checks pass with unavailable and loaded backend capabilities; six groups render, disabled masters are gated, OFF/ON retains choices, chart controls remain enabled, no uncaught UI errors. Mocked requests only; no production changes.
- Full Python discovery: 383 checks, 380 pass. Three failures also reproduce against untouched deployed Delta source: exact shared signal formula, old sideways prohibition, and unknown-net quick-loss expectation. These are not changed by this work.

Run DOM check from repo root with jsdom installed outside production:
RENKO_JSDOM_MODULE=/tmp/renko-family-dom/node_modules/jsdom .private/setup-tools/node/bin/node tests/renko-indicator-families-dom.cjs

## Deployment status

Backend source is staged only. Existing BTC Paper private worker does not contain indicator_families.py and has not loaded indicator-family-masters-v1. UI gates masters until that capability is reported. No worker was restarted, stopped or rearmed, and no orders or active settings were changed.

Latest read-only persisted BTC state during validation: running=true, WATCHING_NO_ENTRY, PAPER, position=null, pending=null. This is a snapshot, not a promise of future flatness.

Deployment requires refreshing worker state and a controlled worker-source update/restart, which is outside the current no-restart authorization. Unrelated staged changes must be reviewed before activation. The authenticated production UI was not refreshed or visually verified during this task; public asset inspection without a login returns HTTP 401.
