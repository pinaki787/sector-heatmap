CURRENT NATIVE-SIZING STATUS —20 November2026: The contract uses the native chart ATR5 brick setting (observed400), not ATR5 computed over the resulting Renko bars (diagnostic451.0914845322309). These are distinct measures. No formula replacement is authorized or applied. The external400 observation is now WITHHELD_NATIVE_CONSTRUCTION_UNVERIFIED: it cannot authorize a new run under the clarified native-construction requirement. Local chart ATR5 box construction does not yet reproduce the observation; prior-parent reference freezing remains unverified. Earlier readiness/sizing statements below, and the intermediate statement that400 was the wrong requested measure, are superseded by this source-contract correction.

# Selected-instrument AI Renko Supertrend

Ubuntu source: /home/trading/sector-heatmap/strategies/nifty_ai_options.
The directory name is historical; the selected instrument determines the strategy.
The broader requested goal remains incomplete. See READINESS.md and evidence/final-status.json.

## Confirmed rules

Bought options enter on an underlying AI Renko flip with bullish selected-premium AI Supertrend. A bearish premium AI flip exits. The nearest future tradable provider expiry is resolved automatically; each side selects closest to premium40 in native quote currency. Provider delta, exact contract and brick sizes freeze per selection/trade.

Direct stocks, futures and perpetuals use the underlying AI flip for Long/Short and opposing flip for exit. CNC cash delivery permits Long only. No option delta is used for direct instruments.

Optional one-minute underlying SMA30 directional exit is OFF by default: Call/Long crosses below, Put/Short crosses above. Execution source1/5/30 minutes is independent of sizing.

Native Renko ATR5 parent policy: NSE/BSE6H regular trading session; crypto23H; Gold22H; other commodities14H. Fixed thirty-minute baseline divisors12/46/44/28. Options multiply the base by absolute provider delta. Forex parent is unconfigured; no default is invented. These are strategy reference durations, not exchange trading-session lengths.

## Native reference status

The only current independently measured reference is NSE:NIFTY regular6H RenkoATR5 Close/no-wicks400 for19November2026. Its base is400/12, not the superseded extended-session250. Ordinary6H ATR311.06 is not the native Renko box400 and is not substituted.

native_reference.py binds verified evidence to exact broker symbol, parent, ATR5, session and freshness. The server overrides browser-provided sizing values. Missing/stale references block Start while read-only price/delta previews remain available.

This is verified-cache lookup, NOT completed automatic native-reference acquisition or future-session refresh. native-reference-probe.pine is compiled and verified on TradingView: the native6H regular ATR5 box is400 on standard1/5/30/360-minute hosts and agrees with the native Renko chart. The user-authorized V1 draft was preserved as a separate private copy, with all1489 lines matching exactly. This verifies the native query, not dashboard ingestion or session freezing.

## Ubuntu setup and read-only commands

The strategy has its own Python3.12 virtual environment, installed dependencies and pinned lock. Existing system/global environments are untouched.

From /home/trading/sector-heatmap:

    strategies/nifty_ai_options/run.sh --help
    strategies/nifty_ai_options/.venv/bin/pip check
    strategies/nifty_ai_options/.venv/bin/python -m unittest discover -s strategies/nifty_ai_options -p 'test_*.py'
    node --test tests/renko-ai-context.test.cjs tests/renko-ai-options.test.cjs tests/renko-ai-chart-markers.test.cjs tests/renko-embedded-chart-isolation.test.cjs tests/test_broker_form_routing.cjs tests/renko-settings.test.cjs

Prepare the private config through the hosted AI mode after selecting an exact broker/instrument and explicit quantity/product. No credentials appear in the configuration. Read-only preflight:

    strategies/nifty_ai_options/run.sh preflight --config /absolute/private/config.json --output /home/trading/sector-heatmap/.private/nifty-ai-options/operator-preflight

To reproduce recorded chart comparison:

    strategies/nifty_ai_options/.venv/bin/python strategies/nifty_ai_options/verify_chart_parity.py
    node strategies/nifty_ai_options/verify_chart_parity.cjs

Do not run the retired stage_ui_sources.py migration script.

## Explicit operator activation

No runtime has been started by this implementation/verification work.

Only after reviewing configuration, a user may explicitly start PAPER monitoring:

    strategies/nifty_ai_options/run.sh stream --config /absolute/private/config.json --output /home/trading/sector-heatmap/.private/nifty-ai-options/operator-paper

Live requires explicit --live, AI_RENKO_LIVE_ORDERS=I_ACCEPT_REAL_ORDERS, the account's existing broker live capability, valid native reference, quantity/product and chart-basis review. Hosted Live additionally requires typing START AI RENKO LIVE. Authorization to implement Live capability is not authorization for an agent to start it or submit a real test order.

Runtime dispatch: FYERS options -> live.py; FYERS direct stock/futures -> direct_live.py; Delta direct/bought options -> delta_live.py. Dhan, Motilal and forex execution adapters are not implemented for this AI strategy.

## Ownership and recovery

Private durable state: /home/trading/sector-heatmap/.private/nifty-ai-options/runtime.
Identifiable runs/config/preflight/journal/heartbeat/markers/process identity: .private/nifty-ai-options/runs/ACCOUNT/RUN_ID.

Paper and Live ledgers are separate. Account locks, chart ownership checks, exact broker exposure, daily metadata, provider-time quotes, funds/margin and durable intents protect submissions. Any retained pending/uncertain intent blocks another signal; FYERS direct/options cannot bypass retained same-mode ownership by switching route. Native Delta orders use existing signed-size/reduce-only reconciliation.

The dashboard can recover the exact AI child-process handle using Linux PID plus process-start ticks and command identity, without restarting it. Restart guards reject active AI jobs and retained exposure/pending intents. Stop terminates only that owned process and DOES NOT flatten a position. No order cancellation/replacement/retry is automatic.

Automatic position/order adoption and recovery, unattended overnight/session resume and reconnect history reconciliation remain unimplemented. Gaps/stale ticks/disconnects halt and preserve exposure.

Raw history is retained. Close-source Renko validates only timestamps and consumed close values; unused OHLC discrepancies are audited, not silently repaired or replaced with fabricated OHLC. Conflicting closes still halt.

## Hosted status and evidence

Only the isolated FYERS backend was approved and reloaded. Its current PID and exact source are in evidence/final-status.json. Latest FYERS hosted checks include exact RELIANCE direct/stock-option previews, Gold22H classification, Nifty spot/Call/Put charts, unchanged sizing across1/5/30, legacy-control restoration, desktop three columns and narrow stacked charts without overflow.

Delta files are prepared in its owning source; its backend was not reloaded. evidence/delta-activation-plan.json is the reviewable, approval-required plan. Shared and other broker processes remain untouched. Other account snapshots have earlier initial staging, not the current full generalized integration.

Evidence:
- evidence/tests.log:95 strategy Python checks, fake executions only.
- evidence/ui-tests.log:48 JavaScript checks.
- tests/test_restart_large_renko.py and tests/test_restart_state_read.py:13 restart checks.
- evidence/chart-parity.json:830 recorded closes ->349 bricks; actual Pine worker versus Python, maxerror0.
- evidence/timeframes/confirmed-close-audit.json:9/9 close-source files usable; raw CE open anomaly retained.
- evidence/hosted-generalized-verification.json and associated screenshots: current hosted results.
- evidence/readiness-current.json and evidence/readiness-provider/report.json: dated read-only guards and broker evidence.
- evidence/delta-activation-plan.json: exact target, command, rollback-source manifest and no-trading boundaries.

Fixture parity is not native TradingView tick parity or proof of actual fills. No valid historical option-fill backtest or P&L tear sheet is claimed.


## Captured runtime source update

confirmed_close.py confirms completed source bars with exact-timestamp provider history before decisions. Source OHLC is not fabricated. Provider/stream differences and raw replies are retained. Source history unavailable/conflicting fails closed; market-open handover and provider publication-lag behavior still require user-run verification.

The options gate waits for premium confirmation through the underlying flip's source bar. NSE/BSE thirty-minute stream buckets now start09:15, matching provider source labels.

chart_source.py persists the exact warm-up and subsequent consumed close series, fixed brick and seed fingerprint for each owned run/symbol/frame. Its authenticated read-only GET route feeds only run-linked AI charts. Those charts reject different account/run/symbol/frame/brick inputs and exclude independently reconstructed live broker candles. The original frozen source URL survives reload. Draft and standalone charts continue their usual broker data paths.

Only provider-confirmed close events append to that ledger. Markers use confirmed PAPER/LIVE events, never future/provisional bricks. When an actual signal bar creates no new Renko brick, its fill marker anchors to the latest preceding confirmed brick; source and confirmation timestamps remain in the audit. No actual live fill marker has been tested.

Verification-only ledger directories are excluded from process recovery and cannot start streams. They are not positions, intents or active workers. evidence/runtime-seed-parity.json records9 cases/148 bricks with zero numeric error against the actual Pine worker; short CE fixtures do not satisfy live warm-up. evidence/hosted-runtime-source-verification.json records hosted Nifty1/5/30 and CE/PE checks, reload preservation, screenshots and unchanged standalone Candles/SMA/AI Auto1.89.

    node strategies/nifty_ai_options/verify_runtime_seed.cjs

The broader goal stays incomplete: native acquisition/refresh and non-Nifty references, pending Delta approval/deployment, unsupported forex/other brokers, and first real user-started handover/fill/session behavior remain outstanding. No new runtime, monitoring, order or account-setting action was performed.


Warm-up handover now accepts the first tick interval only through mandatory complete provider-history confirmation, so partial tick coverage cannot silently skip a fully confirmed bar. A missing intraday/continuous source step halts before another decision. A regular-session opening may follow the prior completed session. The offline Delta feed test starts mid-minute and checks the exact consumed sequence and Long/exit/Short actions without broker requests.


## Native query probe — user-approved preservation completed

TradingView private copy: Sector Pulse V1 — Preserved unsaved draft 2026-11-20.
All1489 lines /110515 characters match the original unsaved editor text. No original saved V1 script was overwritten or published.

The separate private Sector Pulse Native Reference Probe compiled and produced the native6H regular-session ATR5 box400 using ticker.renko/request.security. Standard candle host1/5/30/360 minutes all retained400; the isolated layout was restored to6H native Renko ATR5/RTH and also shows400. Source remains in native-reference-probe.pine; evidence/native-probe-verified-20261120.json and screenshots record the test.

This removes the unsaved-draft preservation blocker. It does not complete authenticated dashboard acquisition/ingress, completed-session freezing, automatic future-session refresh or other-instrument native references. Delta backend approval is separate and no reload/trading action was performed in this probe task.
