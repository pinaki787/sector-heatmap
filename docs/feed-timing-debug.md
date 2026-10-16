# Administrator broker delay diagnostics

After deploying this source during a normal authorized maintenance window, sign in as an administrator and expand **Admin · broker delay diagnostics** at the bottom of the dashboard. Select **FYERS** or **Delta India**, choose 5–60 minutes and click **Enable capture**. Reproduce the slow screen update, click **Refresh report**, then **Export JSON**. **Disable capture** stops recording; captures also expire automatically. Switching on/off does not restart a feed, reauthenticate, start a runner, or issue broker requests. This is process-local: use the dashboard process for the affected account; isolated workspaces only permit their assigned broker. Dhan diagnostics are not included in this implementation.

The server checks authenticated administrator status on both reads and writes. Writes require the dashboard's same origin. Without configured authentication the diagnostic endpoint refuses access. Capture settings and reports stay in bounded memory (1,000 backend events per broker, 1,000 browser events). A new capture replaces the preceding capture for that broker. Reports contain source paths and should be treated as private diagnostic files. Arguments, tokens, headers, query strings, response bodies, error messages and status text are omitted.

## Report fields

| Field | Meaning |
| --- | --- |
| `capture_id`, `span_id`, `parent_span_id` | Capture and nested invocation identifiers |
| `request_id` | Correlates a browser response to its backend request; child spans can be joined through their parent |
| `command_invocation` / `operation` | Safe operation name; command arguments are deliberately omitted |
| `script_path`, `line`, `function` | Absolute executing Python source path and actual call-site line; HTTP spans include an upstream caller chain |
| `start_utc`, `end_utc` | Wall-clock start/end timestamps in UTC |
| `elapsed_ms` | Monotonic invocation duration; null while an invocation is still running |
| `elapsed_since_capture_ms` | Monotonic time since capture was enabled |
| `time_from_preceding_step_start_ms` | Interval from the preceding event's start, across this broker capture |
| `gap_from_preceding_step_ms` | Gap since the previous completed step in the same thread and parent/request context; null if none |
| `thread`, `outcome` | Executing thread and running/ok/error result |
| `slowest_spans`, `findings` | Ranked durations and evidence-qualified bottleneck candidates |

Browser events include full source URLs and export mapped filesystem paths for same-origin scripts, line numbers where the call stack exposes them, start/end times, elapsed durations and preceding-event gaps. The explicit FYERS account-status writer records its actual source line and response request ID. MutationObserver status observations have no exact writer line or guaranteed request correlation; these are identified as observations instead of inventing source locations. Browser gaps can be negative when invocations overlap. The process section reports the Python executable and entry script, without raw command arguments.

## What is measured

- Existing FYERS/Delta `requests` HTTP calls, including failures and upstream caller locations, across threads. No additional broker polling is introduced. Transports that bypass `requests` are not covered.
- Dashboard GET handling through response writing, with request identifiers in response headers. The current generic route classifier treats `/api/delta-india/` and `/api/renko-delta/` as Delta; other dashboard routes are FYERS. Shared multi-broker Renko Engine routes are excluded from this generic classifier; their broker HTTP calls are still classified by host.
- FYERS account positions, funds, tradebook and local P&L snapshot publication as separate invocations.
- FYERS feed lifecycle markers, CA setup, SDK construction, subscribe/connect calls and first tick storage. Only events occurring **after enabling capture** are available. Enabling never reconnects an existing socket, so startup stages can be absent. Initial markers are not a reconnect-cycle history.
- Browser fetch-to-headers, body read/JSON, status DOM updates and next paint opportunity. The browser wrapper begins after an administrator enables capture; it does not retroactively reconstruct page startup. An existing server capture does not automatically enable browser recording in a newly opened tab.

Nested spans overlap: do not add a request's total duration to its child HTTP durations. Compare source locations and caller chains to identify where time is spent. Do not subtract browser and backend timestamps across machines: their clocks may differ. Neither next animation-frame timing nor SDK `connect()` return proves physical screen paint or first live prices. DNS, TCP, TLS and FYERS internal processing remain combined within the transport interval.

## Source-based finding, awaiting a live capture

The current **“FYERS connected” / “Broker feed connected”** labels are written by `refreshAccount` in `dashboard-enhancements.js` from `/api/account`. That endpoint sequentially waits for `positions()`, `funds()`, `tradebook()` and `publish_live_pnl_snapshot()` before replying. Any slow call there delays the status even if the WebSocket is already connected. This is an established dependency, not a measured diagnosis of today's delay. The ranked report can show which call dominates during reproduction. Sector analysis also relies on completed-bar history and is a separate path.

## Legacy browser-only switch

`?feedTiming=1` still enables the earlier browser observer (`feedTimingDebug.report()` / `.download()`). Prefer the administrator panel; avoid enabling both browser wrappers simultaneously. `FYERS_FEED_TIMING=1` retains initial lifecycle collection internally but no longer exposes diagnostics in public heatmap payloads. The protected administrator report is the supported export path.
