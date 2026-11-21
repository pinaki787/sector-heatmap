# TradingView chart workspace: desktop study and Sector Pulse plan

Current requirement-by-requirement audit: [chart-workspace-acceptance.json](chart-workspace-acceptance.json). This document is a chronological ledger; early pending/deployment descriptions are historical, not current status. The full goal is not yet proven complete.

Reference: TradingView Desktop on macOS, NIFTY / Red Bar Floating Fib, 13 November 2026. Observed the Candles chart, favorite Renko/Candles/Line buttons, the full chart style menu, the searchable indicator picker, and the docked Pine Editor with Sector Pulse V1 open. The chart included Bollinger Bands, independently hidden SMA instances, RSI Zones in a lower pane, and an invite-only study with an on-chart table. No chart type was switched, script applied, or layout saved during the inspection.

| Workflow | Sector Pulse target | Boundary |
| --- | --- | --- |
| Symbol, interval, chart type | One chart-first toolbar. Pin Candles, Renko and Line; show the full supported chart type list separately. Keep drawings, study instances, and layout preferences when switching. | Sector Pulse uses its supported data feeds and exchange sessions. |
| Renko | Chart-specific brick method, size, source, wicks and projection settings. Validate completed bricks and projection independently. | TradingView builds historical bricks from resolution data and can redraw projections. Keep any TradingView-style view separate from the existing runner chart and execution policy. |
| Indicators | Search by name, category and favorites. Add independently configurable instances, with Inputs, Style and Visibility. Support overlays, separate resizable panes, scale labels, legend values, hide/show, remove and saved templates. | Maintain a published catalog of supported studies. Community and invite-only scripts cannot be assumed portable. |
| Script workflow | Dockable editor with new/open/save, version history, diagnostics and Apply/Update for verified supported code; make the execution capability clear before accepting a script. | TradingView Advanced Charts does not run Pine. Full Pine, TradingView community access and Invite-only fall back to the actual TradingView app. |
| Chart interaction | Crosshair, OHLC and indicator readouts, drag/zoom, range shortcuts, scale controls, drawing tools, object list, and saved layouts. | Compare interaction and desktop/narrow layout behavior before claiming parity. |

Remote source inventory: the repository already vendors Lightweight Charts 4.2.3. The independent Renko chart and the runner chart are in renko-engine.js and renko-supertrend.js. These provide reusable rendering and study plumbing, but the runner chart is coupled to runner settings and confirmed data. The proposed analytical workspace should be separate. The saved V1 and standalone Shadow Candle research scripts give us realistic fixtures; the inspected editor title does not prove the saved remote source equals the active chart version.

Delivery order:

1. Build the independent chart workspace with the current chart renderer and data routes. Add Candles, Line and Renko, chart navigation, layout persistence, and shared section visibility and per-user authorization. Validate that direct navigation/data access respects assignments and that study or chart settings cannot change any runner.
2. Add the indicator picker, settings and panes. Start with SMA, EMA, RSI, Bollinger Bands, Supertrend, Volume, MACD, VWAP and ATR. Run numerical comparisons against TradingView with matched source inputs, warmup, intervals and session settings; show differences separately when feeds differ.
3. Port and verify Sector Pulse V1 and Shadow Candle before designing any general script compatibility layer. Include labels, tables, fills, alerts if scoped, and regular-candle requests on Renko. Check X/R/M/E and the current V1 Fibonacci defaults against the actual reference. If an editor executes only a supported subset, surface unsupported functions and errors; do not silently accept arbitrary Pine or substitute approximate output.
4. Add a direct TradingView workflow for full Pine and TradingView-only indicators. Evaluate Advanced Charts only if licensing for this deployment is confirmed; it supplies 100+ built-in studies, JavaScript custom indicators and additional chart types, but does not solve Pine execution. Its advertised free availability is for public implementations with visible attribution.

Acceptance: compare chart switching, favorites, indicator add/edit/pane/hide/reload, drawings and layout recovery against the desktop flow. Compare NIFTY Candles, Line and Renko using matched data, timestamps and settings; for Renko include continuation, reversal, multiple bricks from one source bar, session rollover and the open interval. Inspect hosted desktop and narrow layouts and enforce at most two display decimals while preserving calculation precision. Treat replay, alerts, Strategy Tester and the community ecosystem as additional scope, and do not claim parity for untested behavior.

References: [Pine Editor](https://www.tradingview.com/support/solutions/43000763320-how-to-work-with-pine-editor/), [Advanced Charts introduction](https://www.tradingview.com/charting-library-docs/latest/introduction/), [Custom indicators](https://www.tradingview.com/charting-library-docs/latest/custom_studies/), [Renko construction](https://www.tradingview.com/support/solutions/43000502284-understanding-renko-charts/).

## Comparison evidence

The FYERS archive returned 75 regular five-minute NIFTY bars on 23 October 2026. Aggregating the separate one-minute download reproduced the open, high, low and close of all 75 bars. The first two five-minute bars opened at 09:15 and 09:20 IST. Their closes were 22,726.25 and 22,711.20. This establishes agreement between the two FYERS resolutions for that session. The matching TradingView export is still needed.

Use Go to date and Export CSV for the smallest visible range that covers the comparison session. Align regular candles by UTC source timestamp and compare OHLC before comparing indicators. Match the warmup window and indicator settings. For Renko, record the brick method, effective size, input interval, source and projection settings. Sector Pulse numbers bricks in creation order and retains the source candle timestamp. Several bricks can share that timestamp. Compare ordered OHLC sequences and report source-feed or warmup differences separately.

Ubuntu Chrome preview checks at desktop and narrow widths exercised the export action with a 60-bar fixture and SMA 20. The browser received the expected filename, 60 records and a final SMA of 150.50. Hosted activation and authenticated hosted verification are still pending.

## Selected broker data

The FYERS account workspace requests completed NIFTY candles from that account's broker history API. The broker WebSocket supplies prices for provisional bars. The browser reads an authenticated snapshot of the in-memory OHLC every two seconds. Completed history replaces provisional bars once FYERS publishes them. Live prices observed after subscription can miss earlier trades in a candle, so provisional OHLC and derived bricks may change at confirmation. Volume is unavailable on those provisional bars. The historical archive remains comparison evidence.

The chart routes read data from the selected workspace. The remote source supports custom minute and hour intervals up to 24 hours and custom calendar intervals up to 365 days, 52 weeks or 12 months. Calendar and intraday OHLC are aggregated from the selected broker where needed. Delta also supports seconds and transaction-count charts from in-memory WebSocket trade capture.

| Workspace | Historical OHLC | Live OHLC | Verification |
| --- | --- | --- | --- |
| FYERS NIFTY | Account history API | OHLC built from account WebSocket ticks | Fixtures cover history requests, interval boundaries and candle replacement. Authenticated hosted verification is pending. |
| Dhan NIFTY | Account history API. The chart builds 30m bars from complete 15m candles. | OHLC built from account WebSocket ticks | Fixtures cover identity, data subscription, candle aggregation and packet decoding. An authenticated feed check is pending. |
| Motilal Oswal NIFTY | Previously captured native WebSocket candles, limited to verified coverage | Current native WebSocket capture | Fixtures cover index selection and the shortened last NSE candle. An authenticated feed check is pending. |
| Delta India BTCUSD | Delta public history API | Delta public OHLC WebSocket | Direct broker probes on Ubuntu returned completed history and fresh OHLC at all three intervals. Browser checks used fixtures. |

The browser saves chart layouts and Pine draft revisions per broker account. The Pine subset supports indicator declarations, integer inputs, named OHLC series, arithmetic, historical offsets, comparisons, conditional plots, SMA, EMA, RMA, RSI, ATR, crossover and crossunder, and selected plot colors and styles. Full scripts, protected studies and TradingView's indicator catalog remain available through TradingView. The supplied Sector Pulse V1 script still requires a port.

The hosted service is still running its prior process. Loading the new server routes requires the separately authorized service restart described in AGENTS.md. Matching TradingView exports are still needed for the parity audit.

The chart can display provisional WebSocket OHLC during a history outage. It displays a separate history error and offers Retry history. An Ubuntu Chrome fixture returned HTTP 503 for history and supplied a WebSocket candle with a close of 172. After retry, broker history supplied the same timestamp with a close of 170. The chart showed 170 and cleared the error at both tested viewport widths. This fixture verifies the browser handoff.

## Archived TradingView comparison

An archived HCLTECH five-minute TradingView export overlaps the saved FYERS one-minute HCLTECH response on 6 November 2026, from 09:15 through 14:10 IST. Aggregating only groups with all five FYERS minutes produced 60 five-minute candles. Both saved TradingView five-minute exports gave the same comparison. At a tolerance of 0.01, 14 of 60 complete OHLC rows matched. Open differed on 18 rows, high on 14, low on 12 and close on 21. The maximum absolute differences were 1.20, 0.70, 0.60 and 1.80 respectively. These are source differences for this HCLTECH sample. The current NIFTY and BTCUSD chart workspaces still need matched TradingView evidence for candle, indicator and Renko parity.

## Live trade capture and reconnects

Delta BTCUSD supports 1–299 second bars and 1, 10, 100 and 1,000-trade bars. The WebSocket can deliver transactions out of timestamp order. A three-second buffer orders capture by execution timestamp. The hosted process keeps recent completed bars across reconnects, discards interrupted partial bars, and flags capture gaps. A process restart clears the capture. Delta's recent-trades REST response returned only 50 trades with timestamps rounded to whole seconds in the direct probe, so it cannot reconstruct the missing interval or safely join the prior transaction count to the new connection. NSE index adapters expose minute and longer charts. Their current feeds do not establish exchange transaction counts.

## Indicator comparison on identical candles

The archived TradingView CRUDEOIL MINI candle export contains 300 OHLC rows and plotted 10 EMA, 30 EMA and RSI values. Feeding those exact OHLC rows into the current Sector Pulse indicator functions isolates the calculations from broker-feed differences. The comparison used close as the source and length 14 for RSI. A difference of at most 0.01 counted as a match.

| Plot | All comparable rows | After 100 warmup bars | Last 50 rows, max absolute difference |
| --- | --- | --- | --- |
| EMA 10 | 260 of 300 | 200 of 200 | 0 |
| EMA 30 | 186 of 300 | 186 of 200 | 0.00000110 |
| RSI 14 | 200 of 286 | 200 of 200 | 0.000000295 |

The early divergence declines as the series warms up. The export does not include the preceding candles TradingView used to initialize its plots. This checks the three calculations on one fixed input series. Selected-broker feed matching, Renko parity, other studies, and authenticated hosted behavior still require verification.

## Renko comparison on identical archived candles

The current workspace Renko builder used the 300 archived TradingView CRUDEOIL MINI five-minute closes, a fixed 17-point brick, and two-brick reversal. Both the rebuilt and archived Renko series contained 84 bricks inside the regular candle export's timestamp span. Matching the host timestamp and all four prices, 83 bricks matched. The first unmatched workspace brick was an up brick from 9724 to 9741 at Unix timestamp 1793036400. The first unmatched TradingView brick was a down brick from 9741 to 9724 at 1793037300. This is a multiset comparison within the overlap and does not establish identical ordering or general Renko behavior. The archived export uses fractional timestamp suffixes to order bricks sharing a host candle. The comparison tool now accepts those suffixes in ordered Renko mode.

An ordered replay isolated the mismatch to initialization. The reference entered the candle window on a down brick from 9758 to 9741. With that confirmed preceding brick supplied to the replay builder, all 84 bricks matched in order by OHLC and source timestamp. The cold-start workspace chart matched the final 83 bricks in order. The optional replay seed is for matched-input verification. The live workspace still initializes from its selected broker history, and this result does not establish parity for other symbols, brick settings, or live projections.

## Supertrend on identical Renko bricks

The archived TradingView CRUDEOIL MINI fixed 17-point Renko export contains 300 ordered bricks and Supertrend up/down plots. Feeding the identical brick OHLC into Sector Pulse's Supertrend with ATR length 5 and factor 3 produced the same direction on all 296 comparable bricks. The initial four bricks are the local ATR warmup. Across all comparable bricks 283 of 296 values matched to 0.01, with maximum absolute difference 0.17990. After excluding the first 25 exported bricks, all 275 values matched to 0.01 and the maximum error was approximately 0.00207. The final 50 values were identical at exported precision. This comparison uses archived Renko OHLC directly. It covers the study on identical bricks, alongside the separate seeded brick-construction replay.

## Bollinger Bands on identical candles

The archived HCLTECH five- and fifteen-minute TradingView exports include Basis, Upper and Lower plots. A 30-close SMA reproduces the exported basis, and a multiplier of 2 reproduces both bands with the current Sector Pulse indicator. The export settings were identified from the series values. The default 20-bar setting produced different values.

All three plots matched within 0.01 on all 575 comparable five-minute bars and all 734 comparable fifteen-minute bars. Maximum absolute difference across the three plots and both exports was below 0.000000001. These comparisons use TradingView OHLC directly and cover the calculation with matched settings.

## Delta custom hour intervals

Direct Delta India BTCUSD REST verification from Ubuntu returned 165 complete 6-hour bars, 70 complete 14-hour bars, 44 complete 22-hour bars, and 42 complete 23-hour bars in the adapter's roughly 1,000-hour request window. For each interval, a separate request for the hourly candles in the newest completed bar reproduced all five OHLCV fields. Boundaries use a fixed UTC epoch anchor. This verifies broker history aggregation for the four requested intervals. It does not establish TradingView alignment or live feed parity.

A later direct Delta BTCUSD probe verified mid-interval startup for 14, 22 and 23 hours. The hourly WebSocket supplied the active candle and REST supplied respectively 13, 21 and 18 completed constituent candles from the start of those intervals. The resulting provisional OHLCV used every expected opening time and the current WebSocket close. The 6-hour chart now uses Delta's native 6-hour REST and socket candles. Hosted authentication and chart deployment are still separate verification gates.

## FYERS cross-resolution custom-hour check

The archived FYERS NIFTY 50 one-minute and independent thirty-minute downloads reproduced identical regular-session OHLC within 0.01 for 984 six-hour or shortened closing bars and 492 bars for each of 14h, 22h and 23h. Each interval had identical retained timestamps across the two source resolutions. The aggregation excludes off-session records and requires contiguous constituent bars. This confirms cross-resolution agreement within the retained archive. Exchange calendar completeness, current authenticated history and TradingView boundary alignment remain separate checks.

## Saved Pine scripts and native studies

The workspace exposes Sector Pulse V1 red-bar reference and Shadow Candle X/R/M ranges as native studies, with broker-sourced regular candles. They cover selected behavior from the saved scripts. The saved V1 Shadow release and standalone Shadow Candle revision 60 are 56,909 and 68,925 characters and the workspace rejects both at the 20,000-character editor limit. The V1 file also uses multi-timeframe requests, mutable arrays, boxes, labels and tables that the Pine subset cannot execute. Increasing the upload limit alone would not make either script runnable. Use the TradingView editor for the full scripts. Full visual and behavior parity for the native studies remains an open verification item.

## V1 source candle comparison

On the archived TradingView HCLTECH five-minute OHLC, the workspace selected the same locked red-bar high and low on all eight sessions where the publication timestamp was present in the export. The comparison used the native first-bearish-candle calculation and the export's LOCKED RED BAR HIGH and LOW at the source candle's close. It covers the red-bar source and its publication timing on identical input. It does not establish parity for the full V1 or Shadow Candle studies, Fibonacci settings, or broker-fed Renko.

The saved V1 Shadow release specifies 44%, 50%, and 56% for the red-bar reference and merged Shadow range levels. The workspace red-bar reference uses the same three ratios. Its separate standalone Shadow study uses 46%, 50%, and 56%. At the red-bar publication timestamp, all 24 V1 level values across the eight archived HCLTECH sessions matched within 0.01. The active TradingView layout's current settings were not inspected for this comparison.

## Hosted acceptance

The main service and six listening broker workers were still running their earlier processes at the deployment check. The updated source is staged in seven workspace directories. Desktop and narrow browser fixtures exercised chart types, studies, Pine diagnostics and layout restoration. The Dhan browser fixture also traversed the workspace proxy. These checks do not establish signed-in production behavior.

After approval and a fresh runner and order-state check, activate only the eligible dashboard services. Verify that authorized users can open the chart for their selected account, that hidden and unassigned workspaces deny history and live requests, and that switching accounts keeps OHLC requests scoped to the selected broker. Check desktop and narrow rendering, including layouts and the selected account's native history and live feed. Use matched TradingView exports to verify current NIFTY and BTCUSD behavior. The archived CRUDEOIL MINI and HCLTECH results above cover only their specific inputs and settings.

The current Delta adapter uses native 2h and 4h candles where available. With the native 2h input, a repeat request returned 142 complete 14h bars and 90 complete 22h bars. The 23h interval retained its hourly input and returned 42 bars. Independent hourly downloads reproduced the newest completed OHLCV for all three intervals.

## Delta India TradingView comparison setup

The previously open TradingView BTCUSD.P chart was BYBIT:BTCUSD.P. An independent chart tab confirmed that DELTAIN:BTCUSD.P is the Delta Exchange India contract and loaded the saved layout at 1 minute with Traditional Renko, brick size 24. The chart exposed all four requested long intervals in its favorites. This identifies the reference and its Renko settings. Exact OHLC and brick parity need timestamped regular candles and completed bricks from the Delta India chart, aligned against the selected-broker series. The saved layout was left as found.

## Delta India BTCUSD Traditional Renko replay

The TradingView one-minute Traditional Renko export (24-point bricks) and Delta India BTCUSD one-minute broker history were compared over source timestamps 1794580980–1794594840 UTC. Delta returned 353 consecutive one-minute candles including 120 minutes of warmup and one minute beyond the reference. The replay used the workspace chart builder with completed broker inputs. The CSV initially contained 309 rows and contained 310 at comparison time. All 310 reference rows matched in order by full brick OHLC and source minute after removing three extra workspace bricks. One extra preceded the first exported brick in the same minute. The two interior extras were at 1794585900 (68520 to 68496) and 1794585960 (68520 to 68544). The broker closes at those minutes were 68479 and 68596.5. A TradingView regular candle export for those minutes is needed to attribute the difference to input prices or brick construction. The comparison includes the final exported minute and its completed Delta broker candle. TradingView's CSV does not independently flag whether its last brick was provisional at export.

The regular TradingView candle export covered all 232 source minutes in the Renko window. Delta broker history matched complete OHLC on 213 of 232 candles. At 1794585900, TradingView closed at 68498.5 and Delta at 68479, crossing the 68496 brick threshold only on the broker input. At 1794585960, TradingView closed at 68596 and Delta at 68596.5. Replaying the available TradingView regular OHLC, with Delta supplying the earlier warmup, removed both interior extra bricks and matched all 310 exported bricks by source minute and OHLC. The only extra came immediately before the first exported brick in its source minute. No adjustment to the production broker data or calculation was made.

## TradingView session anchoring

TradingView documents that intraday candles open on the instrument's session grid and the final candle can end early at the session close. Its documentation describes 00:00 UTC as a typical crypto daily anchor. Sector Pulse's aggregated Delta intervals currently use a continuous epoch grid. A Delta chart export at 14h, 22h and 23h is needed to identify the contract's observed grid, including whether its shorter bars close at midnight. If Delta follows the documented daily reset, the expected UTC opens are 00:00 and 14:00, 00:00 and 22:00, and 00:00 and 23:00 respectively, with shorter bars lasting 10h, 2h, and 1h. A 6h export provides a control because it evenly divides a UTC day. Verify both bar timestamps and OHLC against Delta constituents before changing the adapter.
See [TradingView's bar construction rules](https://th.tradingview.com/support/solutions/43000796857/).

## ATR calculation on Delta India candles

An independent decimal-precision calculation on 305 consecutive completed one-minute candles from the Delta India TradingView export checked the workspace ATR study. True range was seeded with the first candle's high minus low. The initial ATR was the mean of the first length true ranges, followed by Wilder smoothing. All 292 ATR(14) and all 285 ATR(21) initialized values agreed within 0.000000000001. The final values were 49.92348739 and 49.49932816 respectively. The test used identical input OHLC and verifies the study calculation and warmup. A TradingView export with its ATR plot is still needed to quantify differences from its longer initialization history.

## Delta instrument selector verification

The source version extends the Delta chart to BTCUSD and ETHUSD. On Ubuntu, the chart history adapter requested actual Delta India REST candles for each instrument at 1m, 6h, 14h, 22h, and 23h. Each instrument returned respectively 998, 998, 142, 90, and 42 completed candles in strictly increasing timestamp order. This checks broker history through the source adapter. Workspace worker source copies have account-specific web.py differences, so deployment must preserve those differences. Signed-in selector, WebSocket and layout verification remain open.

## Current activation and acceptance status

The approved initial chart rollout was activated for the eligible workers. The signed-in Delta BTCUSD workspace displayed Candles, Renko and Line, restored a layout with ATR(21), ran a supported Pine plot, and retained the prior plot after rejecting an unsupported multi-timeframe request. The four requested long intervals displayed provisional live updates. FYERS and Dhan data checks were stopped by expired broker authentication. The Motilal worker's chart activation and live verification remain pending.

The later Delta ETHUSD selector is staged. The source endpoint tests cover access and symbol routing. Isolated Delta WebSocket checks returned native candles and completed 1-tick bars for both instruments. A separate ETHUSD replay checked continuity between the REST prefix and the live constituent for 14h, 22h and 23h, including 19 completed hourly candles plus the live hour in the 23h window. These checks did not exercise the hosted selector. The Delta worker restart request is pending. After authorization, recheck the runner and broker account, then verify the signed-in symbol switch, candle streams and layout restore. TradingView long-hour boundary exports and plotted ATR comparisons remain pending browser access.


## Drawing visibility audit — 18 November 2026

This checkpoint supersedes earlier source-version statements above for the drawing fixes only. It does not establish full TradingView parity.

- Root and six active account source pages reference chart-workspace.js v1926. All seven corresponding JavaScript files have matching hashes at publication.
- Manual trend, extended, ray, information, arrow, horizontal-ray, vertical and cross lines now paint in the foreground. The manual drawing primitive is registered after Pine overlays, including foreground overlays. Circle and ellipse shading remains on the background layer.
- The direct renderer regression checks verify paint layers and retained hit geometry. They do not exercise a signed-in chart, mouse selection, saved user settings or actual canvas pixels.
- Native Pine triangle-up/down, arrow-up/down, diamond, square, cross and x-cross labels now paint even with empty text. Shape and text colors remain separate, and tooltip bounds include captions. The actual Pine worker emitted all eight expected native style values in a ten-bar fixture.
- The chart JavaScript suites passed 114 tests. This is scoped regression evidence, not a comprehensive feature-parity certificate.
- Unauthenticated localhost requests to the dashboard workers did not provide the static asset. These requests do not prove authenticated serving or a loaded browser version.
- A fresh macOS screenshot was completely black and Chrome reported no windows. No hosted drawing or visual comparison was possible at this checkpoint.

Remaining acceptance checks:
1. Identify the user's affected broker, chart type and whether missing lines are manual drawings or Pine outputs.
2. Inspect the authenticated page's loaded asset version, drawing visibility and timeframe filters, saved coordinates and browser errors.
3. Reproduce missing lines before the fix where possible, then verify manual lines over opaque and translucent Pine fills, with both behind_chart settings.
4. Verify drawing placement, selection, dragging, color, width, opacity, left/right extensions, saved restoration and switching among Candles, Renko, Line and Heikin Ashi.
5. Compare native Pine labels against TradingView at matched styles, sizes, text, colors and anchors. Native shape rendering tests do not establish pixel parity.
6. Recheck desktop and narrow layouts, selected-broker history/live routing, all symbol catalogs, custom/calendar intervals, table sizing, editor save/apply and automatic session recovery in the authenticated application. Prior scoped checks remain evidence only for their recorded inputs.

The full chart goal remains active and incomplete. No runner, broker order, position, session credential or service restart was changed for these drawing updates.


## Authenticated drawing verification — 18 November 2026, 09:10–09:14 IST

Browser access was restored. A newly opened main-dashboard tab loaded chart-workspace.js v1926 and displayed the global Chart workspace. The existing FYERS runner-instance tab was left unchanged. In the main chart, a Yahoo MSFT daily trend line rendered visibly; changing its width to 3 px and extension to both sides updated the visible stroke and toolbar. The test drawing and its two style edits were undone.

Switching the chart source to Delta India loaded BTCUSD 30m with the saved Sector Pulse V1, SMA and OBV. The feed UI reported 998 completed candles and connected WebSocket updates. A temporary horizontal ray rendered above V1 filled zones, including a 3 px style change. Both temporary drawing actions were undone. Screenshots are /private/tmp/sector-pulse-visible-drawing.jpg and /private/tmp/sector-pulse-delta-drawing-visible.jpg on the macOS client. The main chart tab was kept open as the deliverable.

These observations verify those drawing flows only. A separate viewport defect remains: only about four latest candles appear at the left with excessive blank space despite 998 completed candles being reported. Reset chart view did not resolve it. The V1 table also describes some future candle endpoints as completed (09:15/09:30 at approximately 09:12 IST); its confirmation semantics require investigation. Full feature and visual parity remain unproven.


### Chart order controls checkpoint — 18 November 2026
- Staged remote-only `chart-trading.js` integration: BUY/SELL ticket, selected chart account prefix, click-to-mark and drag entry/stop/target, tick alignment, draft native price lines retained across redraws, source/symbol invalidation, replay submission block. Chart scripts are not yet included in the production index.
- Ticket invalidates confirmation immediately on input and refuses arming unless the server returns live_submission_enabled=true. Existing account and runner gates remain required server-side.
- Isolated browser test used synthetic candles with mocked preview responses and live submission disabled. Desktop drag changed entry 25.00 to 25.25. Narrow 390px layout hides the ticket during chart marking and restores it afterward; target marking returned 28.45. Corrected hidden entry-limit styling and immediate input feedback during rendered verification.
- Screenshot: /private/tmp/sector-pulse-chart-order-draft.jpg on the desktop test host. This is component evidence, not hosted broker acceptance.
- Not activated: no production reload, no broker order sent. Remaining: broker-owned parent/child status reconciliation, Dhan/Delta execution adapter wiring, Motilal linked-exit implementation, master coverage, production source inclusion, account-worker activation and hosted end-to-end preview checks. Broader visual parity, Delta viewport blank space and future-endpoint RSI issues remain open.


### Broker reconciliation checkpoint — 18 November 2026
- Staged FYERS read-only reconciliation using official order-book schema checked this turn: https://fyers.in/api-docs/v3/api/trading/order-book/get-orders/ .
- Correlates exact parent ID, or unique owned native orderTag after uncertain submission; verifies native account identity. Tracks pending entries, partial fills, both linked exit quantities, sibling cancellation and closure without inferring fills from chart prices or unrelated positions.
- Durable preview status updates compare the original record so an older broker read cannot overwrite concurrent state. A status failure never retries placement. The ticket reads broker status after submission, refreshes pending state every 15 seconds, and backs off read failures to 30 seconds; source change/close stops this UI refresh.
- Current automated evidence: 42 backend chart-order tests and 14 UI interaction tests pass. New tests cover linked exit ownership, price/quantity mismatch, partial fills, pending entry remainder after exits, native login mismatch, durable status, failed status reads and no duplicate placement.
- Still staged only. Production script inclusion, worker activation, real broker preview verification and other broker adapters remain incomplete. FYERS order book is current-day only; historical cross-day lifecycle reconciliation remains to be implemented.


### Delta native adapter checkpoint — 18 November 2026
- Added staged chart_trade_delta.py. Native exact product/tick/expiry, last-trade + executable quote timing, exact settlement wallet, lifecycle/exposure/pending orders and existing live/corrupt-ledger gates are checked under the Delta execution lock. Submit rechecks identity, contract, wallet, quote and exposure before the single attached-bracket request. Native reply prices are checked rather than assuming the requested price was accepted.
- Retains the existing 100,000-contract limit and blocks contract types whose native entry/exit verification is not implemented; chart analysis catalogs remain unchanged. No RSI exit settings are invented for the new marked-price workflow.
- No new-order margin-preview endpoint was found in the documented Delta API; current-product leverage/order-margin GET describes existing order margin, not an incremental estimate. Preview evidence therefore labels final margin as broker checked at submission/trigger, with native wallet currency shown and no conversion or leverage assumption.
- Docs: https://docs.delta.exchange/ ; https://mcp.delta.exchange/docs/tools/trading ; https://www.delta.exchange/support/solutions?articleId=80001177916 . Bracket API supports explicit trigger method, while older help text mentions mark-only; actual last-trade bracket behavior still needs native verification.
- Six Delta adapter tests pass using fake broker responses and no actual orders. Total chart-order backend suite now 48 passing tests. Delta adapter is not registered in the HTTP controller and no workspace capabilities were enabled; pending work includes durable chart-order ownership coordination with runner starts and reliable Delta position-bracket exit reconciliation.


### Delta ownership coordination checkpoint — 18 November 2026
- Staged chart_trade_ownership.py reads the private account's durable chart ledger without creating or modifying it. Pending, filled/protected and unknown chart states block competing new entries; previews and broker-confirmed terminal states do not. Only the exact persisted chart client-order token is exempt for its own native request.
- Integrated into Delta submit admission, LIVE RSI runner start and the native POST /v2/orders boundary. Reduce-only exits and cancellations are left available. Native-boundary enforcement also covers Renko submission through Delta.submit; it is still checked immediately before the financial request.
- Added outstanding legacy Delta owned-intent checks to chart preflight so a SUBMITTING/UNKNOWN native intent cannot be overlooked after a concurrent legacy submission.
- Delta read-only parent reconciliation now uses the stable client-order ID, verifies account/order/symbol/side/quantity, and distinguishes pending, cancelled-without-fills and confirmed partial/full entry fills. It deliberately does not infer position-bracket exit protection from the parent response. Cancelled unfilled quantity is not displayed as still pending.
- Validation: 57 chart-order backend tests pass, including six ownership-boundary cases and three new Delta native-status cases. Separately, 67 existing Delta tests pass across native India submission, strategy-managed submit, recovery, Renko execution, submission-boundary and no-send handling.
- Not activated: source staging only; account worker copies and running processes remain unchanged. Delta native position-bracket exit reconciliation, broader runner-start presentation/ownership, other broker execution adapters and hosted activation remain open.


### Delta exit reconciliation and native schema checkpoint — 18 November 2026
- Added chart_trade_delta_exits.py: complete, product-filtered active/history orders and fills since parent creation are checked against exact chart-owned entry quantities and the current signed position. Checks native market bracket type, reduce-only, marked prices, explicit trigger source, same native position parent group, full residual quantity, sibling cancellation and entry remainder.
- Delta native signed GET /v2/orders/history added to the read-only allowlist. Pagination repetition/caps fail verification rather than silently truncating. A changed parent while reads are in flight cannot produce a verified result.
- Staged Delta controller registration, exact account/broker route admission and MARGIN product selection. Production index still does not include the new chart-order scripts; no worker reloaded.
- Read-only native schema probe scripts/probe_delta_chart_order_schema.py verified the registered Delta workspace key binding before reads. No constructor/ledger initialization and no order mutation. BTCUSD sample: zero active orders; 40 history orders and 25 fills in the sampled 30-day window, no more cursor; 17 native bracket legs, all market_order/reduce_only=true/mark_price. meta_data.parent_type=position and parent_id existed on all 17. Fill new_position metadata did not expose a position id.
- Evidence file /tmp/delta-chart-order-schema-20261118.json contains field schemas/enumeration counts only, no credentials or order prices/ids.
- Added explicit Delta exit-trigger selector (Last Traded Price or Mark Price). It is part of the immutable reviewed plan and native payload; Mark is never substituted silently. Actual Last Traded Price bracket acceptance remains unverified; the native API documents it, while sampled historical legs used Mark.
- Remaining before activation: background reconciliation across closed tabs/restarts, account-wide FYERS ownership coordination, exact display for sub-paise executable prices, current hosted broker-preview checks, account source deployment and reload authorization. Dhan/Motilal execution adapters and the broader original visual/functional parity checklist remain open.


### Background chart-order reconciliation checkpoint — 18 November 2026
- Staged chart_trade_monitor.py plus server startup/shutdown hooks. Existing private chart ledgers resume native status reads after worker restart; creating an unsubmitted preview does not cause broker reads. Monitor never prepares, refreshes an entry, submits, changes or cancels broker orders.
- Active records reconcile every 15 seconds; read failures back off 30 seconds, persist status unavailable and clear protection_confirmed. Browser close does not own this server monitor. Terminal/previews are excluded. Per-service reconciliation lock prevents overlapping browser/monitor broker reads.
- FYERS monitor cycle shares one native profile/order-book snapshot across account records, with a five-second freshness check, instead of one account read per row.
- Fixed two race/merge issues exposed by realistic monitor tests: late native acknowledgement cannot overwrite newer reconciled status; adapter retry_allowed field no longer causes duplicate-keyword merging failure.
- Startup only resumes a ledger already present for the isolated registered account; root/global server does not open private broker sessions. Services are cached under a construction lock and close the daemon reader on shutdown.
- All changes remain in root staging. Current hosted account sources/workers have not been activated; no live order submitted. Remaining: exact sub-paise review display, FYERS legacy-entry ownership coordination and cross-day status, current native preflight verification, deployment/reload approval and rendered hosted checks; Dhan/Motilal execution work and broader chart parity remain open.


### Exact price review / FYERS ownership checkpoint — 18 November 2026
- Exact decimal helpers in chart-trade-ticket.js compare reviewed prices without Number coercion, preserve tick arithmetic with BigInt, and compute reward/risk from exact differences. Decimal/scientific inputs normalize without silent rounding; unsafe whole quantities are rejected before prepare.
- Instruments with verified tick precision beyond two places use explicit integer-tick fields and an exact rational tick-unit note. Broker-returned tick/lot metadata replaces stale display units while preserving executable prices. Small-price chart picking no longer uses toFixed(10).
- High-precision draft tags are rendered by a top pane primitive (exact tick counts, E/SL/TP and optional Mark marker). Native price-axis primitive labels initially clipped and shifted the current-price label in the rendered test; replacing them with pane tags fixed the observed problem. Normal-price lines retain native labels. Ticket header stays available while scrolling; review summary scrolls into view.
- Isolated browser evidence: synthetic small-price chart with entry 123 ticks, stop 100, target 150 and Mark trigger; mobile chart marking changed entry to exactly 126 ticks and invalidated its review. Normal-price mode retained 25/22/30 fields and native labels. No console errors observed. Screenshot on desktop host: /private/tmp/sector-pulse-exact-tick-draft.jpg . Test backend disabled all financial submission. Actual main-chart axis formatting for micro-price broker symbols still needs hosted verification; the isolated fixture axis used explicit tick units.
- FYERS ticket/basket entry admission and entry-evidence archival now check persisted chart ownership. Shared EMA/Renko LIVE entry branch also checks ownership before persisting intent; exit branch is not blocked. FYERS chart preflight and native submit use the same guard (the exact durable chart tag is exempt for its own request). Complete atomic coordination across all entry workflows is still pending before activation.
- Broader FYERS execution tests initially failed with expired August/September fixtures. Baseline execution with only the three new ownership guard insertions removed in memory reproduced the same 2 failures/5 errors. Fixed the underlying clock dependency by passing service.now() into both option-chain selection calls; production still uses the real default clock. The 13 execution tests and protection test then passed.
- Current verification: 84 chart-order backend tests; 19 chart-order UI tests; 13 FYERS execution + 1 protection; 47 EMA runner/external-close/spot-exit and 3 basket-limit tests pass. First EMA invocation lacked PYTHONPATH=strategies and was rerun successfully with the required path.
- All changes are still root staging. No account source rollout, production reload, runner change or live order occurred. Remaining: atomic FYERS/runner admission, FYERS cross-day reconciliation, other broker adapters, fresh actual-broker previews, deployment/reload authorization, hosted desktop/narrow validation, and the original broad TradingView parity checklist.


### Shared entry admission checkpoint — 18 November 2026
- Added chart_trade_admission.py: OS-backed, per-private-account entry lock with nested-call support and a durable revision updated before a broker placement attempt. Private account/broker binding and regular-file/no-symlink checks apply. Revision is an opaque consistency marker, not an order/fill/fee count.
- Chart arming holds admission across its final fresh preflight, durable intent and native submission. Delta keeps its existing execution lock outermost. FYERS ticket/basket submissions and LIVE EMA/Renko entry paths share admission; exits skip it. A revision change from an intervening entry invalidates an older preview before a new chart order can be sent.
- Added a distinct ChartOrderNotSent outcome only for checks before invoking native placement. It persists a terminal no-send rejection rather than leaving an account-owned unknown intent. Native transport errors, including BlockingIOError after sender invocation, remain uncertain and are never retried.
- Call-site audit found additional FYERS entry paths: Parser/protection, EMA Band, KAMA, long-straddle BUY legs, and the conditional credit basket. Their entries now share admission; paired straddle entry functions hold admission across both legs in live mode. DRY_RUN and SELL exits remain available. Parser rejects a failed entry admission before creating an unresolved lifecycle. Existing square-off / protective / exit calls were not placed under the entry lock.
- Financial-only helper acquisition is nonblocking so it cannot send a quote that aged while waiting for another process. Whole workflows with fresh preflight acquire admission before those reads. Native numeric JSON payloads reject prices whose decimal value would change during float serialization; Delta string prices retain exact values.
- Multiprocess tests cover spawned workers, forked workers and a nested fork. Inherited admission descriptors are closed in children without unlocking the parent; callback mutex state is rebuilt safely. Two deterministic thread tests cover both legacy-first and chart-first race directions. Other tests verify nested Delta admission, exit bypass, no-send versus uncertain handling, Parser/straddle paths and lossless numeric transport.
- Regression checks passed: 13 FYERS execution, 1 protection, 3 basket-limit, 10 Parser lifecycle, 4 native Parser activation; 47 EMA runner/external-close/spot-exit, 23 Delta Renko execution/boundary/no-send, 25 Delta India, 15 Delta submit strategy and 4 recovery. These use controlled test clients, not live financial orders.
- Still staged in root only: no account-source activation, dashboard reload, runner start/stop or live order. Remaining work includes FYERS cross-day reconciliation, Dhan/Motilal adapters, fresh native previews, live-order marker status presentation, scoped concurrent chart setups, account rollout/reload approval and hosted validation. The original broader TradingView parity objective remains incomplete.


### Broker-state chart marker checkpoint — 18 November 2026
- Staged chart level captions now follow submitted/reconciled broker state instead of retaining DRAFT after acceptance. Acknowledgement alone shows Verify status; pending, verified protection and terminal states are distinct. Losing protection verification clears the protected caption. Marked entry remains the requested price, never represented as a confirmed fill price.
- Added a controlled marker transition test, including stale protection and terminal precedence; 20 chart order UI tests pass. No native placement, account rollout or reload. Rendered hosted verification and the broader remaining scope are still outstanding.

### Failed-read marker checkpoint — 18 November 2026
- Fixed a stale protection display path: ticket status-read exceptions now notify chart markers with BROKER_STATUS_UNAVAILABLE and protection_confirmed=false. Previously only the text message changed. Lost arm acknowledgements publish SUBMISSION_UNCERTAIN rather than leaving draft captions; neither path retries placement.
- Added tests for protected-to-read-failure transitions and lost submission acknowledgement. All 22 chart order UI tests pass using controlled hooks. No account activation or live trading. Hosted rendering, broker adapters and broader parity remain incomplete.

### Protection freshness checkpoint — 18 November 2026
- A verified protection caption now expires after 20 seconds without another successful native reconciliation. This covers a subsequent read that stalls without returning an error; expiration changes display only and never cancels or resends a broker order. Source changes/close destroy the timer, and obsolete callbacks cannot alter another ticket.
- Added controlled-timer tests for stalled reads and source changes. All 24 chart-order UI tests pass. Root staging only; hosted rendering and activation still outstanding.

### Account-switch and Dhan registration checkpoint — 18 November 2026
- Replaced the ticket-wide status busy boolean with per-request identity. Invalidating/reopening a ticket detaches the old request; its late completion cannot block a new account read, unlock its in-flight button, or update its status. Added deterministic deferred-response coverage; 25 chart-order UI tests pass.
- Added read-only chart_trade_dhan_reconciliation.py for exact chart-owned current-day Super parents and server-held exit registration. Validates account/correlation/security/segment/side/product/order type/role/quantity and exact marked prices. Pending and partial fills are distinct; cancelled partial entry remains unresolved exposure; zero-trigger-quantity registered exits are accepted only for an exact fully filled parent.
- CLOSED Super state or TRIGGERED exit state is explicitly not accepted as exchange exit-fill proof. Missing/current-day-only evidence does not imply cancellation or authorize resubmission. Dhan adapter is not registered or enabled; actual trade-book/position closure, submission admission, native preflight and conditional entry still need implementation.
- Seven new Dhan evidence tests pass; all 104 chart-order backend tests pass. No account rollout, reload, native placement or runner mutation. Full goal remains incomplete.

### Dhan account evidence checkpoint — 18 November 2026
- Added strict read-only Dhan chart evidence helpers for registered account/credential/profile identity, Data API subscription, activated exchange segment, product eligibility, MTF status and native static-IP whitelist. NSE/BSE equity/derivative/currency and MCX commodity segment mappings are explicit; chart-only index symbols are not confused with tradable securities.
- Exposure checks require exact account and segment/security identity, known statuses and valid whole net quantities; an ID reused on another segment is not treated as the selected contract. Funds/margin require both native balances, positive finite required margin, and optional full-premium minimum; insufficientBalance sign is never treated as the funding decision.
- Five new evidence tests pass; these helpers are staged and not registered as an execution adapter. Resolution/session/expiry and fresh quote integration, native submission admission, trade-book closure and conditional entry still remain. No account rollout, reload, live submission or runner mutation.
- Rechecked official Dhan v2 Super and Conditional Trigger documentation: Super supports LIMIT/MARKET, while conditional triggers document equity/index conditions and ordinary order payloads without Super linked exits. Conditional alerts are therefore not a verified substitute for a marked breakout plus native Super protection. References: https://dhanhq.co/docs/v2/super-order/ and https://dhanhq.co/docs/v2/conditional-trigger/ .

### Read-only Dhan preview integration checkpoint — 18 November 2026
- Added staged DhanChartAdapter.prepare/refresh connecting exact segment:security chart symbols to the current native master, strict account/subscription/segment/IP checks, unresolved-journal checks, current positions/orders, two-sided snapshot quotes and native margin. Refreshes exposure and price after margin reads; no state is usable if an intervening position appears. Bought-option previews require full premium coverage as well as native margin. High-value previews retain an explicit order-value notice.
- Account identity hash, exact marked levels/ticks/lots and native security IDs are retained; native margin payload contains no order correlation or placement call. STOP_LIMIT never becomes LIMIT. The exact session/expiry validator is a required injected dependency: no guessed calendar fallback is accepted, and a default production session integration is still unfinished.
- This adapter remains unregistered and hard-disabled for submission. Calling submit_bracket produces ChartOrderNotSent before any broker call. Six integration tests use controlled REST responses and verify read-only endpoints, post-margin exposure race, account/master mismatch, missing expiry/session validation, breakout refusal and crossed depth/subscription checks. Actual broker preview, default session/expiry integration, admission/native placement, conditional entry and full closing reconciliation remain outstanding. No activation, reload, live order or runner change.

### Dhan default session foundation checkpoint — 18 November 2026
- Connected the staged preview default to contract-aware session validation. Existing verified NSE capital-market 2026 calendar handles exact open/close boundaries, January election holiday, ordinary holidays and Budget special session. Verified MCX non-agricultural metadata uses its partial-holiday session and exact entry_cutoff/expiry_epoch. Naive times, unknown years, expired dates and unverified MCX families are rejected. Historical chart access is unchanged.
- Default calendar coverage is still incomplete: NSE F&O, BSE and currency execution require their own verified integration; they currently return a precise missing-calendar error rather than borrowing equity hours/holidays. All selected symbols remain in chart analysis catalogs. Submission remains hard-disabled and the adapter unregistered.
- Research confirmed NSE/CD/71962 currency holidays include 19 February, 19 March, 1 April and 26 August, which differ from the equity list. NSE/FAOP/71777 and /72262 verify the F&O annual list and January election supplement. BSE official annual-calendar URLs returned HTTP 403; no unsupported assumption was coded. Sources: https://nsearchives.nseindia.com/content/circulars/CD71962.pdf , https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf , https://nsearchives.nseindia.com/content/circulars/FAOP72262.pdf .
- Four session test cases cover boundary/holiday/special-day sets, timezone conversion, unknown year, expiry, MCX partial holidays/cutoff and other-segment non-substitution. Ten session plus preview tests pass. No live broker mutation, production reload or activation.

### NSE Dhan derivative preview checkpoint — 18 November 2026
- Dhan native master resolution now retains instrument_name as additive metadata. Chart preview uses OPTIDX/FUTIDX/OPTSTK/FUTSTK classification instead of guessing from a ticker. Stock options resolve all listed same-underlying expiries from the current master and preserve the existing near-month expiry/preceding-day Equity-only policy, including when a later-month contract was selected.
- Added independent NSE F&O 2026 holiday/election supplement and Budget special-session gate. Exact session boundaries and valid derivative classification are required. BSE/currency session coverage is still incomplete and not substituted with NSE equity hours; no execution gate was enabled.
- Tests cover default F&O preview, missing classification, exact calendar boundaries/holidays, missing stock-expiry evidence and next-month policy bypass refusal. All 123 chart-order backend tests pass; the combined earlier session/preview plus existing Dhan execution invocation passed 47 tests before the two extra preview cases. No native financial calls, account rollout or reload occurred.

### BSE / NSE INR-currency preview checkpoint — 18 November 2026
- Added separate BSE equity/F&O holiday data, election closure and Budget session to the staged session validator. Verified annual BSE notice 20251212-8 through a broker-hosted copy of the exchange PDF after the BSE site returned 403. Budget hours are corroborated by the public broadcaster and broker session bulletin; historical source references remain separate from native current account state.
- Added NSE INR currency-pair validation for FUTCUR/OPTCUR native master symbols, 09:00–17:00 and the distinct currency holiday list from NSE/CD/71962 plus election closure. Preserves the descriptive native symbol alongside the opaque segment:security chart identity, including both pre-margin and post-margin validation. Budget Sunday is not opened for currency.
- Cross-currency and BSE currency session integration remain incomplete. NSE timing page shows a conflicting cross-currency table/footnote, so no extended-hours assumption was enabled. The same page displays an F&O 15:40 value while the verified regular/Budget references use 15:30; staged execution retains its verified 15:30 boundary pending resolution. No live gate is enabled.
- Added BSE boundary/holiday/Budget cases and currency extra-holiday/open/close/pair-classification tests. Session plus Dhan preview tests pass (16). References: https://www.steelcitynettrade.com/Circulars/BSE-Trading%20Holidays%20for%20the%20Calendar%20Year%202026%20for%20Equity%20and%20Equity%20Derivatives%20Segments.pdf ; https://www.nseindia.com/static/market-data/market-timings ; https://newsonair.gov.in/bse-nse-to-hold-special-trading-session-today-amid-union-budget-presentation/ . No account rollout, reload, order or runner change.

### Dhan exchange-fill reconciliation checkpoint — 18 November 2026
- Added pure chart_trade_dhan_exits.py and connected staged DhanChartAdapter.reconcile. Verifies selected native profile identity/hash, exact durable Super correlation/contract/side/product, three unique exchange-leg roles and exchange order IDs, actual unique exchange trade IDs/quantities, and selected-product net position. Repeated identical fills are deduplicated; conflicting duplicates, mixed account evidence, duplicate positions, overfills and contradictory statuses fail verification.
- Closure now requires actual owned exit trades covering entry fills, flat selected position and terminal linked exchange legs. CLOSED Super alone, triggered exits, missing trade data, active entry remainder/sibling, unrelated active orders or unrelated later fills cannot produce CLOSED. Earlier unrelated trades before this entry are not attributed to it. Open residuals do not imply current protection; server-held registration is retained only when independent native fill/position reads prove the complete unexited position.
- Adapter rereads the Super parent after orders/trades/positions to reject a changed snapshot, and rejects reads exceeding five seconds. Native reads use GET only; account credential selection remains through existing Dhan execution service. Cross-day historical reconciliation remains incomplete because the native day endpoints are not archival evidence. Actual native schema/hosted verification still required; this is not validation of a live trade.
- Eleven exit/reconciliation tests pass, including integration of the native read sequence, changed login/parent, slow snapshots, partial exit, missing fills, foreign fills, duplicate evidence, pending siblings and entry remainder. All 136 chart-order backend tests pass. Dhan execution remains hard-disabled/unregistered; no account rollout, restart, runner action or live order. Sources checked: https://dhanhq.co/docs/v2/orders/ and https://dhanhq.co/docs/v2/super-order/ .

### Dhan shared admission checkpoint — 18 November 2026
- Extended entry admission to explicit trusted account folders, including root services without worker environment variables. Explicit folders must exist, be canonical/non-symlink paths and match a worker binding when present. Dhan ownership checks read the selected account's chart ledger, not an unrelated foreground source. Durable revisions are shared by chart previews, manual tickets, strategy entries and Investment sends.
- Dhan lock order is execution.lock then account entry-admission file then existing native submission lock. Chart arming, manual submit, Investment check/send and BUY entries of the existing long-option strategy adapter share it. LIVE Dhan BaseRunner entry admission occurs before pending intent persistence; strategy direct-call guard failures return known no-send code 400. SELL exits and PAPER do not acquire this new entry guard. Rechecked all discovered Dhan native POST placement call sites in root source.
- Known pre-native guard failures do not become uncertain orders; actual broker transport failures keep existing unknown/no-retry behavior. Revisions are marked before durable native submission intents. Dhan chart submission remains explicitly hard-disabled pending its remaining adapter work.
- Added five admission tests for explicit-folder coordination, account isolation, mismatched worker binding, workflow blocking, strategy no-send rejection and exit/PAPER bypass. Updated test service fixtures to declare broker=DHAN, matching the real service contract. Existing Renko engine mock omitted ema30 consumed before admission; added that observation field to the fixture only, with no production trading-rule change.
- Verification: all 141 chart-order backend tests pass; targeted Dhan strategy/engine/lifecycle/Investment plus admission suite passes 69 tests; additional Dhan execution/indicator/recovery/protection, FYERS execution and Investment HTTP suite passes 90 tests. Controlled clients only, no live placement. No account-source rollout, production restart/reload, runner start/stop or settings mutation. Full chart parity, native adapter activation and hosted validation remain incomplete.

### Dhan gated native submission checkpoint — 18 November 2026
- Implemented staged Dhan LIMIT Super submission behind an internal constructor gate that defaults false. Dhan remains unregistered in the chart controller; hosted users cannot invoke this adapter yet. Existing account live capability and application execution policy are also required and rechecked immediately before placement.
- Native send requires the exact durable SUBMISSION_UNCERTAIN chart preview record, immutable fingerprint/account identity/entry revision, recent preflight, current exposure, current contract session and fresh two-sided quote. Uses the shared account admission and existing Dhan native submission lock; marks revision before invoking POST /super/orders. Exact entry, stop and target prices remain native absolute prices with trailingJump=0.
- Pre-invocation failures are ChartOrderNotSent. Native definitive rejection is terminal; native timeouts/socket errors retain uncertainty. No automatic retry or order-type substitution. Consumed durable previews return their existing receipt without another native call. Conditional breakout handling, remaining session coverage, cross-day status, actual native verification and hosted activation are still incomplete.
- Seven controlled submission integration tests pass: exact payload/one call, timeout, socket failure, definitive rejection, disabled gate, missing durable review and intervening revision. Simulated clients only; no live placement, account rollout or service reload.

### Dhan raw execution-tick evidence checkpoint — 18 November 2026
- Extended the existing selected-account Dhan chart WebSocket with a separate raw ticker evidence read. The web stream constructor binds the registered account ID; ticks carry broker/native-account hash, exact segment:security, unique stream instance ID, connection revision, receipt sequence and provider/receipt time. No chart OHLC is substituted for an execution tick.
- Same-second native ticker packets remain distinct via receipt sequence. Latest execution evidence rejects wrong/unsubscribed instruments, invalid or future prices/times, older out-of-order timestamps, disconnected sockets and unbound streams. Evidence ages out after two seconds; disconnect/reconnect/stop clears it. New stream instance IDs distinguish process/stream recreation from a reused revision counter. Returned tick dictionaries cannot mutate retained evidence.
- Native ticker floating-point wire prices are retained as received. Trigger comparison still requires verified native tick normalization; no rounding or trigger worker was silently enabled. Dhan managed conditional entry/worker durability, bounded native submission integration, cross-day history, remaining session coverage, actual broker schema and hosted verification remain outstanding.
- Six binary-packet tests use an inert fake WebSocket/thread, covering account identity, exact source, receipt sequencing, reconnect, stale/out-of-order ticks and invalid packets. All 154 chart-order backend tests pass. No live socket was opened for validation, no account rollout/reload, no runner action and no native order occurred.

### Dhan conditional trigger state checkpoint — 18 November 2026
- Added pure serializable DhanTriggerState/arm/evaluate logic for reviewed STOP_LIMIT plans. Arming requires an exact account/native identity, raw broker WebSocket source, fresh tick, pre-trigger baseline and valid unchanged entry/limit/stop/target geometry. Evaluation distinguishes waiting, expired, review-required and triggered; it never invokes a broker.
- Reconnect/new stream, stale/missing ticks, unobserved freshness gaps, out-of-order evidence, clock regression or changed plan require a new review. Whole-second Dhan LTT before the precise arm instant cannot establish a post-arm hit. Repeated sequence cannot retrigger. A price gap beyond the cap retains the original pending limit; it never chases market price.
- Float32 wire prices normalize only when exactly one current broker tick can be established within wire quantization error. Unmodified wire evidence is required; sub-wire tick ambiguity and genuinely off-tick prices fail verification instead of rounding arbitrary prices.
- Eleven deterministic trigger tests cover BUY/SELL, same-second/pre-arm/repeated ticks, stale/gapped/reconnected/mismatched evidence, expiry, serialization and float32 precision. Durable atomic trigger claiming, worker lifecycle, triggered native Super payload/refresh integration, actual broker evidence and activation remain unfinished. No executable trigger worker was enabled and no order sent.

### Durable conditional-entry claim checkpoint — 18 November 2026
- Added DhanChartConditions inside the existing private chart preview database. Explicit owner/LIVE confirmation consumes an unexpired preview into durable waiting state. Ticker observations update serialized state transactionally; concurrent workers can obtain only one claim token, and SUBMISSION_UNCERTAIN is committed before any future native invocation. A restarted worker cannot reclaim an already claimed setup.
- Fresh owned ticker/stream/sequence, unchanged plan, current trigger side and unexpired timing are checked again at claim. Invalid, stale or reconnected evidence cannot be claimed. Owner-authorized local cancellation is available only before a native claim; it never invokes broker cancellation and cannot clear claimed uncertainty. Waiting/review-needed conditions continue to own the account; cancelled/expired unclaimed conditions release it.
- Native broker reconciliation excludes unclaimed conditional states and returns their local status without querying for a nonexistent order. After claim, normal broker reconciliation resumes. Eight storage tests cover competing threads, restart, owner/gate checks, repeated arm, cancellation/expiry, stale/reconnected evidence and native-monitor exclusion.
- This is not wired to a running trigger worker or public route. Adapter STOP_LIMIT preview/triggered native payload integration and actual hosted/broker validation remain incomplete; no financial action, activation or reload occurred.

- Follow-up claim check: stale/reconnected/invalid evidence now transactionally persists REVIEW_REQUIRED (or EXPIRED at deadline) before returning a no-claim error. It cannot silently recover into a later claim. Nine conditional-storage tests pass, including sticky review state; account ownership remains until explicit local cancellation or expiry.

### Claimed Dhan stop-limit native transition checkpoint — 18 November 2026
- Added a dedicated read-only Super margin payload for conditional previews and an explicit claimed-trigger native builder. The general native builder still rejects STOP_LIMIT. The explicit transition requires matching immutable plan fingerprint, durable claim token, bounded claim age, fresh selected-account raw tick, unchanged stream/revision/sequence and currently satisfied entry trigger. Native price is the separately reviewed cap; the persisted plan remains STOP_LIMIT with its original trigger and fingerprint.
- Added internal triggered-price validation to plan reconstruction, scoped to Dhan. Ordinary review still requires a pre-trigger price. A triggered refresh cannot silently accept a reverted trigger or change contract/account/revision. No API request can set this internal validation phase through payload fields.
- Connected staged adapter conditional preview margin, durable-claim refresh and final native request validation. Reads the private conditional table and exact claim token/expiry; requires an injected selected-stream tick reader. Final quote/exposure/session/gate checks still run. Native receipt reconciliation compares a managed conditional order against its reviewed LIMIT cap without converting or resubmitting it.
- Six payload/plan tests plus three end-to-end controlled conditional adapter tests cover cap preservation, unchanged reviewed plan, no general fallback, calculator-only payload, wrong/stale/reconnected proof, post-refresh price reversal and one simulated placement. Persistent worker orchestration, public route/controller wiring, broker/hosted validation and remaining parity scope remain unfinished. Default submission gate remains false, Dhan stays unregistered; no live orders, account rollout or service reload.

### Conditional worker orchestration checkpoint — 18 November 2026
- Added explicitly started DhanConditionalWorker. Constructor is inert; no production caller starts it. Polls only this account's unclaimed waiting/triggered entries, checks enabled/live gates, obtains a new raw tick, and holds the existing execution/admission lock order across one durable claim, read-only refresh and one native adapter invocation. Claimed rows are never retried or rearmed on worker recreation.
- Disabled execution or invalid/reconnected evidence persists review-required. Failed read-only refresh is known no-send; a stop requested during refresh prevents native invocation. Exceptions after native invocation might have begun preserve uncertainty for broker reconciliation. No native cancellation is sent by this worker.
- Added transactional conditional receipt recording with claim-token/account/contract checks. Late native acknowledgement cannot overwrite newer order/fill/protection evidence; it can retain a returned native ID alongside a concurrently read unavailable status. Uncertain outcomes remain consumed.
- Seven controlled worker tests cover actual staged adapter flow with one simulated Super request, restart/no resend, timeout, gate changes, reconnect, preflight failure, stop-before-send and late acknowledgement race. Persistent public controller/startup wiring, actual broker schema checks, production account rollout/reload and hosted acceptance remain incomplete. No worker thread/socket/live order was started for these tests.

### Conditional shared-service controller checkpoint — 18 November 2026
- Added optional explicit conditional_factory to ChartTradingService and DhanConditionalController. No production factory installs it yet, so existing FYERS/Delta routing and hosted Dhan-disabled state remain. Controlled service integration now distinguishes Dhan STOP_LIMIT confirmation from immediate native submission.
- Confirmation rechecks immutable preview/owner/permissions/live gates under account admission, refreshes the native plan, takes a fresh selected-stream baseline and obtains expiry from a server-side resolver rather than request input. It persists waiting state before explicitly starting its worker. Repeated arm cannot reset/rearm an existing condition; start failure persists review-required rather than leaving a silent waiting entry.
- Local condition cancellation is owner-scoped and only available before a native claim; status reads do not query a nonexistent broker order. No public cancellation endpoint or native broker cancellation was added. Service close shuts down its optional worker. Preview responses retain high-value notice/notional data for the future rendered UI.
- Six controller tests cover explicit arm/start timing, server-selected expiry, repeated confirmation, local status/cancel, claimed cancellation refusal, owner/feature/live gates, changed tick and worker-start failure. Original shared-controller tests also pass. Public Dhan factory/route/startup integration, actual broker/session coverage and hosted validation remain unfinished. No real worker/thread/socket/order was activated.

### Dhan live-evidence and conditional deadline checkpoint — 18 November 2026
- Read-only native probe selected the registered personal Pinaki Dhan account and verified saved credential/client binding before any request. GET /profile returned the sanitized DhanAPIError: session expired or invalid. Probe stopped immediately; no downstream account-schema reads, authentication renewal or order mutation occurred. Actual Dhan schema/preflight verification is blocked on reconnecting that selected account through Broker Accounts. Other staging work remains possible; the full goal is not complete.
- Added server-side conditional_expiry resolver using the exact reviewed contract and verified current session. Equity/F&O ends at 15:30; supported NSE INR-currency session ends at 17:00; MCX expiry uses the earlier session, native contract entry_cutoff and expiry_epoch. Closed/unknown sessions do not produce a future arming deadline. Request-supplied dates remain ignored by the controller.
- Currency expiry-day previews now require explicit verified contract cutoff metadata instead of assuming the regular close from a date. Default master metadata does not yet supply that cutoff, so expiry-day currency execution remains unavailable pending verification; historical charts are unchanged.
- Three additional session/deadline tests cover contract matching, separate session ends, currency expiry cutoff and MCX pre-expiry protection. Eleven session tests pass. Public Dhan route/feed/factory activation and actual hosted verification remain unfinished; no production settings or worker reload changed.

### Conditional order UI / rendered simulation checkpoint — 18 November 2026
- Ticket now names Dhan stop-limit confirmation Arm conditional entry and explains Sector Pulse monitors the live trigger. High-value preflight notices render as plain text. After confirmation, redundant disabled placement/confirmation controls hide while the read-only review remains. Chart labels distinguish ARMED Entry from PLANNED Stop loss/Target; review-required and terminal states are separate.
- Added Cancel waiting trigger hook only for Dhan waiting/triggered/review-required states. It requests local unclaimed-trigger cancellation, invalidates older in-flight status responses, prevents duplicate cancellation clicks and refreshes status if a native claim won the race. It never invokes broker order cancellation or repeats entry placement. Public Dhan/cancel routing remains disabled/unregistered.
- Added four ticket tests and one chart marker test: cancellation/claim race, stale status after cancellation, one request, text-only notice and planned exits. All 30 order UI tests pass. Corrected stale footer instructions on status changes and misleading broker-monitored wording discovered during rendered inspection.
- Isolated Chrome fixture on temporary loopback server used synthetic candles and mocked all prepare/arm/status/cancel responses; no broker connection or real financial request. Desktop and narrow layout were inspected; narrow document width equalled viewport width (433 CSS px under the browser zoom). Simulated cancellation visibly removed its button and updated both status/footer. Viewport reset, test tab closed, HTTP server and SSH forward stopped.
- Screenshots on desktop host: /private/tmp/sector-pulse-conditional-armed.jpg ; /private/tmp/sector-pulse-conditional-narrow.jpg ; /private/tmp/sector-pulse-conditional-cancelled.jpg . One browser connection console message was observed, with no diagnosed app-stack provenance; the fixture flow/assets completed. This is component simulation evidence, not hosted or live-broker acceptance.
- Root staging only. Current production account sources/index still do not activate these controls; personal Dhan native verification remains blocked by its expired saved session. Original full TradingView parity goal remains incomplete.

### Gated hosted Dhan integration checkpoint — 18 November 2026
- Added explicit SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS=1 activation gate; absent/default is disabled. No environment/config value was set and no worker was reloaded. Shared route, private workspace guard and capability context agree on the gate. Motilal and other brokers cannot fall through to Dhan/FYERS. Local cancel-condition action is allowed only for the gated Dhan controller and exact private account.
- Staged factory binds the selected Dhan execution service, account folder and shared chart WebSocket tick reader. Existing Handler authentication/selection now reuses the same cached Dhan execution getter; startup receives an exact-account getter, not global credentials. Tick binding checks the active stream account. Feed warming is read-only and reuses the existing socket/subscription path.
- Dhan adapter checks the activation gate dynamically as well as account live capability/application policy, including its final native pre-send check. Startup converts recovered unclaimed conditions to review-required without starting a trigger worker; claimed native intents resume broker reconciliation only. No implicit rearm/resend after restart.
- Five factory/guard tests cover default off, explicit staged opt-in, selected feed/service binding, dynamic gate withdrawal, unclaimed startup handling and account/route mismatch. Two worker tests ensure read-only tick failures before/after admission persist review-required rather than a silent waiting state. All tests use temporary private databases and simulated clients; monitors/worker starts are inert in the factory tests.
- Actual live Dhan schema/preflight verification remains blocked by the selected personal account's expired session. Remaining calendar/contract coverage, actual hosted validation, production source rollout/reload approval and the full original chart parity scope remain incomplete.

- Packaging regression follow-up: fresh Dhan workspace provisioning initially failed because the explicit public-source overlay omitted chart_trade_admission.py. Added all staged chart trading/conditional modules and ticket assets to the reviewed inventory. Static import-closure inspection also found existing root dependencies omitted by the overlay (line_entry, swing_breakout, entry pipeline/qualification, option premium, journal scope, Delta close/no-send/chart recovery, multi-account tickets, restart reads, NCDEX calendar and Yahoo chart support). Added those module files without changing their strategy logic or defaults.
- Extended the fresh owned-workspace test to compare staged chart asset/module bytes and import Dhan/controller/worker dependencies from the isolated provisioned source. The provisioning test and Dhan form routes/chart access/execution regression group now pass (68 tests). All 206 chart-order backend tests passed before the inventory-only fix. Active account snapshots were not provisioned or changed; tests used disposable private registries/folders.

### Hosted chart navigation / blank-space fix — 18 November 2026
- Reproduced actual hosted Delta BTCUSD 30m chart with only four visible candles at the left and excessive future whitespace. Read-only developer trace proved 999 price candles were loaded, right margin was seven bars, and the stored range remained 995–1021. Navigation set a new range, immediately read the chart before its asynchronous render applied it, persisted the prior range, then Reset rebuilt the chart with that old viewport. This was not missing OHLC history.
- Fixed shared navigation to save the requested range before applying it, without synchronous stale readback. Reset, zoom, pan and Latest use the same corrected path. Two delayed-render tests cover Reset rebuilding/saving the requested recent-100-bar range and all other navigation directions; all 58 navigation/candle-study tests pass.
- Surgically applied only this navigation block and chart-workspace.js cache version 1927 to main plus six registered source copies. Did not copy the staged order modules, enable order assets, change broker flags, or restart/reload services. Verified all seven sources contain the fix/version and omit the order-ticket/bridge assets. Backup: /tmp/chart-navigation-20261118-fyeg_im5 .
- Actual hosted fresh-tab validation served chart-workspace.js?v=1927. Reset displayed roughly 100 recent candles; zoom then Reset worked; the corrected viewport remained after full Sector Pulse V1 plots/tables completed. Temporary debugger logpoints were removed and Debugger disabled; no foreground user tab reloaded and no financial/runner operation occurred.
- Screenshots: /private/tmp/sector-pulse-delta-viewport-before.jpg and /private/tmp/sector-pulse-delta-viewport-fixed.jpg . This verifies the Delta candle navigation fix, not full visual/runtime parity or all chart types. The broader goal and staged broker-trading activation remain incomplete.

### Hosted chart type verification — 18 November 2026
- Fresh authenticated Delta Algo BTCUSD 30m hosted tab: Line rendered ~100 recent closes after Reset; Heikin Ashi rendered transformed candles after selection and Reset; Renko ATR(7) Close bricks rendered and Reset/Zoom in changed the viewport. Restored original Candles 30m and Reset with the three original studies retained. No service reload, runner change, broker order or trading activation.
- Two early Heikin Ashi locator clicks left Line selected; exact accessible button selection from Renko succeeded. Cause not established; do not claim that interaction fully resolved. No app-stack exception was diagnosed from the observed browser extension connection messages.
- Actual restored screenshot: /private/tmp/sector-pulse-chart-types-verified.jpg . This is desktop type/render/navigation evidence only, not full live rollover persistence or narrow-screen acceptance. Broader visual/Pine/broker parity and staged order deployment remain incomplete.

### FYERS linked-exit reconciliation integrity — 18 November 2026
- Hardened staged FYERS reconciliation: active parent quantities must account for the reviewed order; filled parent status cannot retain pending units. Stop/target require nonempty distinct native IDs separate from the parent. Linked totals cannot exceed confirmed entry fills; active exit totals must reconcile and filled status requires full filled quantity/no remainder. Conflicting evidence cannot report POSITION_PROTECTED or CLOSED.
- Added five regression cases covering inconsistent active parent, conflicting exit IDs, oversized/mismatched exit totals, impossible quantities and partially filled status reported as complete. All 211 chart-order backend tests pass on authoritative Ubuntu. Existing terminal partial-fill and sibling-cancellation handling remains covered.
- Root staging only, no account rollout, reload, flags, worker start or native financial requests. Overnight archival reconciliation remains incomplete; missing current-day entry still reports unavailable without retrying. Full chart parity and hosted broker-order activation remain incomplete.

### FYERS historical entry reconciliation — 18 November 2026
- Read official FYERS Order History and Trade History API documentation (fyers.in/api-docs/v3/api/reports/order-history/ and trade-history/, modified October 2026). Reports use paginated data arrays and distinct historical field/product/status names. Historical order schema omits parentId and stopPrice, so it cannot prove linked exits on its own.
- Added read-only, bounded, fully paginated symbol/account-validated report reader. Detects failed/repeated/oversized/conflicting pages and does not accept a truncated maximum-page result. Entry reconciliation compares the already-owned native order ID, side/product/quantity/limit and exchange identity against deduplicated exchange trades. Only matching zero-fill cancelled/rejected entries become terminal; confirmed fills retain ENTRY_FILLED_EXITS_UNVERIFIED. Current open/exited quantities remain unknown rather than retaining stale values.
- Optional reconcile_record adapter hook passes server-owned preview creation scope (expiry minus fixed 120-second review window). FYERS falls back only when its known parent is absent, never when current conflicting parent evidence exists. Selected native account and current order book are rechecked after slow report reads. No history fallback for an uncertain entry without a known native ID, no synthetic child mapping, no resubmission.
- Ten new controlled history tests cover pagination, repeated/conflicting evidence, scope/account, exchange-fill mismatch, terminal/partial entry, quantity aliases, adapter identity change and current-book conflict. All 221 backend chart-order tests pass. Fresh disposable workspace provisioning/import test passes and includes the new module. No native account calls were made; official public documentation only. Root staging, no hosted activation/account rollout/reload/runner or order action. Actual broker schema/hosted acceptance and overnight linked-exit reconciliation remain unfinished.

### FYERS native report schema verification — 18 November 2026
- Added persistent read-only scripts/probe_fyers_chart_history_schema.py. Selected registered FYERS Algo workspace bf46fc364b610a0dfd338419e133cb41; validated credentials application, saved-token application, and registry credential_identity hash before creating the read-only client. No constructor execution service/ledger initialization. Native profile identity required; reports clientId must match it.
- Initial overly strict probe compared native fy_id to user-entered account_ref and stopped after profile. Source inspection confirmed FYERS configure binds registry credentials to application hash; account_ref is not enforced as native client ID (unlike Dhan/Motilal). Corrected probe to the actual selected-app binding, without changing registry/credentials or weakening production checks. Subsequent profile/report reads succeeded.
- Sampled two native rows each from order-history and trade-history over yesterday/today. Actual order rows use tradedqty, not camelCase; trade rows use string orderDateTime, int side, and the documented native exchange/order IDs. Neither sampled order row included parentId/stopPrice. All sampled report rows matched the selected native profile.
- Ran the actual staged read_reports against one exact symbol returned by native evidence with bounded full pagination (100/page, max5), yesterday-to-today scope, and rechecked profile identity afterwards. COMPLETE_SELECTED_SYMBOL: 2 order rows and 2 trade rows, identity unchanged. This verifies read-only report transport, parser schema/account and completion for this small selected symbol/window; not multi-page production coverage, chart-owned order lifecycle, native TPSL placement or linked-exit closure.
- Sanitized metadata-only evidence /tmp/fyers-chart-history-schema-20261118.json. No raw financial rows, native client IDs, tokens or credentials printed/persisted by probe. No orders, renewals, runner mutations, reloads, activation or account-source rollout. Goal remains active/incomplete.

### Mac/Control keyboard viewport persistence — 18 November 2026
- Found keyboard zoom/pan applied logical ranges without first persisting the requested range, unlike the corrected navigation buttons. Saved range before applying it and saved the view on both paths, covering Cmd/Ctrl Up/Down zoom, plain arrow pan and Cmd/Ctrl accelerated pan. Two delayed-render regression tests cover both modifier families; navigation+candle-study group passes all60 tests.
- Surgically deployed only the two keyboard handler snippets plus chart-workspace.js version1928 to main and six currently registered account sources. First preflight enumerated stale/deleted account sources and stopped on an anchor mismatch before any source mutation; corrected inventory to read-only accounts registry. Successful backup /tmp/chart-keyboard-20261118-3eqlmj40. All order ticket/bridge assets remain excluded; no backend staging rollout/reload/financialflags changed.
- Actual fresh hosted Delta BTCUSD30m: Cmd+Up zoomed; Cmd+Right panned; Cmd+K opened Quick Search showing favourite drawings with Option shortcuts. Selected original Candles/settings/studies retained, restored Reset. Desktop and temporary520x900 viewport visually checked; viewport reset. Read-only CDP scriptParsed confirms hosted chart-workspace.js?v=1928, Debugger disabled afterwards. No userforegroundtab reload, nativeorder or runner action.
- Screenshots /private/tmp/sector-pulse-mac-shortcuts-desktop.jpg and /private/tmp/sector-pulse-mac-shortcuts-narrow.jpg. This verifies navigation shortcuts, not full drawing-attribute/favourites acceptance or the original full parity goal. Trading activation remains staged/incomplete.

### Hosted drawing attribute verification / accessible names — 18 November 2026
- Actual Delta BTCUSD30m: Manage drawings exposed existing horizontal level65111.21, its color/width/style/opacity/caption controls. Option+T activated Trend line. Added a temporary two-anchor trend, opened selected Settings, applied width3px and Extend left/right; rendered continuous blue line visibly spanned both sides. Undid settings then addition; original single horizontal drawing retained.
- Exact accessible lookup for Line width initially failed. Source inspection corrected the diagnosis: controls were inside implicit labels, but select option text polluted their accessible names; labels were not absent. Added explicit concise aria-label for drawing width/style and dynamic line/text color, including the existing second style selector. No trading/render/math semantics changed.
- Static-only surgical rollout to main+six registered sources, version1929. Backup /tmp/chart-drawing-labels-20261118-x2cemo_f. Anchor preflight stopped once on the two existing style selectors before mutation; corrected expected count and verified all anchors. node --check passed; new order assets remain omitted; no service reload.
- Reloaded only own verification tab. Added second temporary trend and opened settings; exact Line width, Line style, Line color each resolved once. Desktop and temporary520x900 modal inspected; width/style reachable by keyboard Tab with lower settings scrolling into view. Cancelled draft setting and undid temporary drawing, restored desktop viewport and original single horizontal level. No user foreground reload, runner/broker/order mutation. Screenshots /private/tmp/sector-pulse-drawing-extensions-test.jpg (temporary testline, removed), /private/tmp/sector-pulse-drawing-settings-desktop.jpg, /private/tmp/sector-pulse-drawing-settings-narrow.jpg.
- Color control presence/label verified, native OS color selection not changed. Favourite drawing list/Option shortcuts observed in earlier quicksearch, but favourite add/remove/persistence still requires actual acceptance. Full chart parity and broker-trading activation remain incomplete.

### Hosted drawing favourites acceptance — 18 November 2026
- Fresh hosted Delta BTCUSD30m starts with four original favourite tools in order: Fib retracement, Horizontal ray, Parallel channel, Date and price range. Opened trend flyout via visible right-edge chevron; added Trend line via its star, immediately observed fifth floating shortcut, reloaded own verification tab and confirmed fifth tool persisted.
- Option+Shift+5 activated favourite Trend line drawing mode without creating a shape. Escape cancelled it. Option+Left moved focused Trend line before Date and price range; Option+Right restored its order. Removed temporary Trend line favourite via star and reloaded; exact original four tools/order persisted. No saved drawing, runner, broker or order altered; no user foreground tab reloaded.
- Desktop screenshot /private/tmp/sector-pulse-drawing-favorites-verified.jpg shows star controls and original four-tool floating toolbar. This verifies favourite add/remove/reload/keyboard ordering/activation in selected workspace/browser, not cross-user preference isolation or every tool type. Source version remains1929. Full goal and staged trading activation remain incomplete.

### FYERS reviewed entry integrity and native schema — 18 November 2026
- Rechecked official order-placement guide (fyers.in/api-docs/v3/getting-started/guides/order-placement-guide/): sync single-order supports absolute stopLoss/takeProfit for INTRADAY/CNC/MARGIN/MTF, while async does not. Existing builder remains sync. Explicitly set isSliceOrder=false so a reviewed single-parent setup cannot silently request multiple sliced parents.
- Current-order reconciliation now checks exact reviewed native entry type, limit cap and trigger price, in addition to account/contract/quantity. A broker-side changed entry cannot be shown as matching the original marked chart level. Two regression cases cover changed LIMIT fields and STOP_LIMIT trigger/cap preservation; all223 backend tests pass. Existing fixtures now include the documented native fields instead of omitting them.
- Extended read-only persistent FYERS schema probe with current order book metadata. Live selected saved account returned27rows, each containing type/limitPrice/stopPrice/id/symbol; no sampled row had a nonempty parentId. Therefore entry-schema compatibility is observed, but no native linked-child schema/lifecycle proof was obtained. Revalidated report reader for its selected symbol/window (2orders/2trades) and unchanged native profile. Sanitized /tmp/fyers-chart-history-schema-20261118.json contains metadata only.
- Root staging only, no native placement/modification/cancellation, activationflag, service reload, runner change or accountsource rollout. FYERS linked-exit lifecycle/overnight closure and full chart parity remain incomplete.

### Tabbed drawing settings visual update — 18 November 2026
- Reorganized the existing drawing form controls into Style/Text/Coordinates/Visibility tab panels, preserving the actual input/select nodes and values (no clones/reparse). Style puts color,width,stroke first, followed by extensions and drawing-specific controls; Text groups font/alignment/annotation; Coordinates groups name and native anchors; Visibility retains existing timeframe ranges. Tabs support arrow/Home/End navigation and proper tab/tabpanel ARIA. Invalid input in a hidden panel opens that panel synchronously for native validation.
- Added restrained matching tab styling, aligned attributes, consistent controls and narrow-width spacing with fixed Apply/Cancel footer. Initial hosted check found annotation still underStyle; corrected classification and rechecked Text. Final JS1931/CSS301. Static surgical deployment to main+six registered sources, without staged financial asset inclusion/backendrollout. Backups /tmp/chart-drawing-tabs-20261118-spstskbt and /tmp/chart-drawing-tabs-text-20261118-evidfw5n. node syntax check and3 existing drawing regressions pass.
- Hosted Delta BTCUSD30m acceptance: temporary trend edits width3+left/rightextension applied; reopened stored width3 and compared all coordinate input strings before/after byte-for-byte equal (full stored numeric precision retained). Cleared required StartPrice, selectedStyle, pressedApply; Coordinates selected automatically and modal stayed open. Restored input and applied; undone temporary settings/addition to original single horizontal drawing.
- Final desktop/narrow520x900 modal shows tabs/primaryattributes without clipping; keyboard ArrowRight selectedText; annotation/fontsettings and timeframeVisibility present. Cancelled final temporary draft, removed temporary shape, restored desktop viewport and original drawing. Own verification tabs only, no userforegroundreload/runner/nativeorder. Screenshots /private/tmp/sector-pulse-drawing-tabs-desktop.jpg and /private/tmp/sector-pulse-drawing-tabs-narrow.jpg. Verified trend modal; every complex drawing variant and full TVparity remain unproven. Trading activation remains staged.

### Hosted Fibonacci and rectangle tab acceptance — 18 November 2026
- Created disposable Fibonacci retracement in actual Delta BTCUSD30m via Option+F. Verified Style/Coordinates/Visibility tabs; added44/56 alongside0/23.6/38.2/50/61.8/78.6/100; applied and reopened saved exact level list. All coordinate input strings matched before/after. Undid setting and drawing to restore original.
- Created disposable Rectangle via Option+Shift+R. Verified allfour tabs, native centerline/left/right extensions/fill controls. Applied2px border,25percentfillopacity and annotation Drawing layout verification acrossStyle/Text; reopened and confirmed saved width/fill/annotation and unchanged exactcoordinates. Cancelled reopenedform and undidsetting/addition. Final Manage drawings contains original single horizontal level65111.21 only; no testshapes/preferences retained.
- Screenshot /private/tmp/sector-pulse-rectangle-tabs-verified.jpg records temporary verification drawing/settings (removed afterwards). No source changes, service reload, userforegroundtab reload, broker calls/orders/runnerchanges in this check. This broadens modal acceptance to trend/Fib/rectangle; remaining complexdrawingvariants, brokerorderactivation and fullparity remain incomplete.

### Chart trading deployment readiness/process audit — 18 November 2026
- Read-only current-state audit confirms root sector-heatmap.service MainPID3697650, cwd root, port8080, KillModecontrol-group. Registered Delta dashboardPID3697818 listens8101 and FYERSPID3697918 listens8102, both account-owned source directories in user session62875 rather than mainservicecgroup. Do not assume a shared-service restart reloads these workers.
- Same FYERS/Dhan workspace environment also appears on handoff_execution_worker PID2971939/2971941 under notification-adminservice, with no listening ports. Therefore selecting processes byworkspaceid alone would target unrelated execution workers. Future reload must confirm owned dashboard listener/PID/lock/state immediately, notkillallworkspaceprocesses.
- Both target worker snapshots still lack23 staged chart trading modules/assets. Root-to-workerweb.py differences include35Delta/40FYERSchangeblocks plus unrelated parser/research/history/strategy differences. Full rootfile overwrite is not a reviewed deployment. Selective source integration/dependency and entry-admission coverage remain required before concrete reload approval.
- Metadata-only SHA256/change-block/registered-source/currentprocess/listener audit saved docs/chart-order-rollout-readiness.json. No credentials/positions/orderpayloads recorded; no sourceworkerfiles, settings, runners, service, order or flags changed. No approval requested prematurely; rollout_readyfalse. Fullgoal remains incomplete and meaningful integrationwork remains possible.

### FYERS/Delta missing-module source staging — 18 November 2026
- Staged48new files (24per registered FYERS/Delta source) from reviewed shared chart-order modules and ticket/bridge assets. Created only previously absent files; no existing worker module, route/guard, index, settings, env, credential or runtime state overwritten. Corrected readiness inventory to include chart_trading.py explicitly: chart_trade*.py glob does not match that controller filename.
- Read-only imports of selected controller, FYERS/history/Delta adapters and monitor succeed from each actual worker source directory, using remote venv, without constructing services or starting threads/requests. Entry routes, UI asset inclusion and cross-entry admission integration remain absent; controls not activated. No worker reload/restart/nativeorder/runner action.
- Created-file SHA256 inventory /tmp/chart-order-module-stage-20261118-xfjty_41/manifest.json. Updated docs/chart-order-rollout-readiness.json module hashes/import flags; missing-module count now0 forboth. rollout_ready remainsfalse until selective integration, required guards and relevant validation completed. Broader original fullgoal remains active/incomplete.

### Selective worker integration candidates — 18 November 2026
- Added persistent scripts/build_chart_order_worker_candidates.py. Builds isolated candidates from each exact current FYERS/Delta worker source; selects chart entry-admission/ownership wrappers and required Delta read-only orders/history allowlist, adds reviewed exact-account prepare/arm/status route/context/monitor lifecycle and chart route guard. Existing unrelated worker history/parser/research changes preserved, including Delta catalogue capability flags. No UI index inclusion or active integration-file replacement.
- Candidate-ah86m90p compiled20Pythonfiles; imported nine affected modules per broker with socket.connect/thread.start blocked; allimports passed. Direct candidateguard checks accepted3ownedactions and rejected wrongaccount/broker/unexpectedaction; all10shared serialized-entry decorator identities retained perbroker.
- First regression run exposed testharness CWD reading old active workerstraddlefiles, and genuine missing serviceclock propagation to optionchain expiry in oldworkerFYERSexecution. Corrected harness to candidateCWD/baseimportfallback and included exact two existing root fetch_fyers_chain(now=self.now()) calls as dependency (production defaults samecurrentclock; injected clocks now consistent).
- Final candidate .private/chart-order-rollouts/candidate-s8_8me_b: 62 relevant admission/FYERSexecution/parser/FYERSchart/history/Deltachart tests pass perbroker. Logs/immutableoriginal/candidate SHA256manifest retained. Compared against firstcandidate: onlytwoFYERSexecutionfiles changed forclockdependency; exactguard/importartefacts identical, priorproof retained byhash. Rechecked all20activeoriginalfilehashes stillmatchprebuild; noneoverwritten. Readiness reportpointsnewcandidate, rollout_readyfalse until remainingintegrationacceptance/activationreview. No service/runnerflag/order/native mutation. Fullgoal remainsactive.

### Candidate loopback HTTP acceptance — 18 November 2026
- Added tests/test_chart_trade_candidate_http.py, requiring explicit CHART_ORDER_CANDIDATE (skips whenunset). Extracts actual candidate Handler POST/read_json/send_json/endheaders methods, uses actual candidate WorkspaceGuard, real temporary WorkspaceStore users/sessions/permissions/visibility and actual ChartTradingService/privatepreviewstore. Starts disposable loopbackHTTPservers with simulated-only adapters, patched factory; no productionclient/gates/registry/state or nativeendpoint used.
- Three tests with both FYERS/Delta subcases pass: previewonly never submits; missingconfirmation403; validconfirmation one simulatedsubmission; repeatconfirmation no secondsubmission; statusENTRY_PENDING/unprotected; missingcookie/wrongorigin/wrongaccount/wrongbroker/unsupportedaction rejected; malformedJSON andnonobjectJSON400; absentbroker/chartassignment and globallyhiddenchart403. Testserversclosed andthreadsjoined; tempregistries/databasesremoved.
- Initial fixture corrected completevisibility-map requirement (production setter rejects partialmaps) and gave simulatedDeltaadapter its required nativeexecutionlock. No production changes to bypass those checks. Final3tests passed4.49s. Candidate manifest records testhash/scope/proof; active sourceintegration stillunapplied, no reload/UIassetinclusion. Fullgoal remainsincomplete.

### Chart order frontend activation candidate / rendered preview — 18 November 2026
- Extended candidatebuilder to include only7insert-only chartTrading bridge hooks (24lines) in worker chart-workspace.js; rejects any unrelated JSdifference. Main and bothworker candidate index pages add ticketCSS and deferred ticketJS→bridgeJS→workspaceJS1932 in correct order; stylesCSS301 retained. Existing compactworker/head markup preserved via exacttaganchors. Candidate .private/chart-order-rollouts/candidate-ft5wic4o nowcontains34files incl3orderassets snapshotted for eachowner. Backend20files byte-identical to62tests-perbroker+HTTP-tested candidate-s8_8me_b; evidence retained byexactartifact equality.
- StaticHTMLparse verifies unique inclusion/defer/order/CSS for3pages; candidateJSsyntax passes. All30ticket/bridge UItests pass after finalcopy. Active main/worker index pages remain unchanged (noorderassets); noUIactivation/backendreload/liveflag.
- Rendered isolated loopback component using current staged assets, syntheticcandles, fetchmockonlyprepare and disabledsubmission. BUY1unit at25,SL22,TP30 produced exact blueentry/redstop/greentargetDRAFTlines,1.67reward/risk and readonlybrokerpreview; placementbuttondisabled. Desktop and520x900 narrowchecked; no actualbroker/accountconnected. Renamed misleading Review live order heading to Broker order preview, and concise pricefield ARIAlabels update between price/tickunits. Verifiednewlabels byexactbrowserlookup;30UItestsremainpassing. Updated onlyroot+already-stagedFYERS/Delta ticketassetcopies; activepages stillomitassets.
- Screenshots /private/tmp/sector-pulse-buy-preview-simulation.jpg and /private/tmp/sector-pulse-buy-preview-simulation-narrow.jpg. This is simulation evidence, nothostedorderactivation/lifecycleproof. Viewportreset, fixturetabclosed, localSSHforwardclosed, verifiedtemporaryremotehttp.serverPID3785896cwd/tmp/sector-pulse-chart-order-layout andstoppedit. Productionworkers/runners/ordersuntouched. Fullgoal/activationstillincomplete.

### Delta selective source staging / reload approval pending — 18 November 2026
- Canonical stopped_state_paths precheck passed14FYERSstates and3Deltastates. Added persistent scripts/probe_chart_reload_exposure.py with selected registry/credentialbinding, nativeprofile/orderaccount validation forFYERS, boundedfullDeltaopen-orderpagination, nativepositionquantities and sanitizedcountsonly. Freshread-onlyresults: FYERS3openpositions/0openorders (blocked), Delta0positions/0openorders (pass). No financialmutation.
- Staged11changed candidateintegrationfiles atomically in exact Delta source only, after every original/candidateSHAcheck and repeat3statestoppedguard. Current ownerlockPID3697818/cwdverified. This includes route/context/monitorlifecycle/entry-admissionguards and chartbridgehooks; existingassetfilesalreadymatchcandidate. MainandDeltaindexremainunchanged, noorderassetsincluded; runningworkerhasnotreloadednewwebcode. FYERSintegrationfilesnotchangedbecauseexposureblocked.
- Backup/hashmanifest .private/chart-order-rollouts/delta-source-stage-hgng2_gq/manifest.json (statusSOURCE_STAGED_NOT_RELOADED). Previouscandidate62tests/broker,3HTTPtestswithbothsubcases,30UItests andrenderedsimulationevidence retained. Candidatebackendnotchangedbythisstaging.
- Requested specificuserapproval viaasyncquestion to reload onlyDeltadashboard andactivateBUYSELL/confirmedmarkedlevelorders. Explained remoteAGENTSspecificreloadauthorization rule, freshstop/exposurechecks beforeaction and noactualtradeplacementunderthisapproval. Mainservice/FYERS/handoffexecutionworkersnotinrequestedreloadscope. StaticindexassetinclusionplannedafterDeltaactivation, no mainbackendrestartneededforselectedworkspaceproxy. Awaitinganswer; fullgoalremainsincomplete.

### Drawing tab data-integrity regressions while reload approval pending — 18 November 2026
- Added4DOMregressions usingactualorganizeDrawingSettingsfunction extractedfromcurrentremoteJS andexistingprivatejsdomruntime. Verify FormData retains all exactstrings/highprecision/nativecoordinates, duplicatecheckednames, disabledfieldexclusion, existingnodeidentity/changehandlers and nestedFiblevelsettings aftersectionmoves/tabchanges. Verify Control2/Vertex12 anchorplacement,annotation/fillgrouping, keyboardwrap/Home/End focus/singleselectedpanel and hiddeninvalidcoordinatevalidationopeningcorrectpanel; noemptyTexttab.
- All7drawingtestsgroup pass (new4+existing3). ProductionJS/CSS/indices/candidateartifactsunchanged; tests isolatedinmemoryDOM, noaccount/broker/runner/servicecalls. Delta reloadapproval remainspending; no inferapprovalfromgoalcontinuation. Fullgoalremainsactive/incomplete and independentchartworkpossible.

### Approved Delta chart-order activation — 18 November 2026
- User explicitly approved only Delta chart-order activation reload. Rechecked three stopped runner states, exact owner/process scope and native Delta zero positions/open orders before graceful reload. Delta dashboard PID 3697818 replaced by 3797692; main 3697650 and FYERS 3697918 unchanged. Activation audit: .private/chart-order-rollouts/delta-approved-activation-dujxud1l/result.json.
- Activated root and Delta static chart ticket/bridge assets with workspace JS1932. Hosted CSS specificity conflict corrected with ticket CSSv2; backup audit .private/chart-order-rollouts/chart-order-hosted-style-swgq78tu. FYERS execution activation remains staged; other brokers are not represented as active.
- Actual authenticated hosted Delta chart receives live data and exposes BUY/SELL. Read-only BTCUSD BUY1 LIMIT63000 / SL62500 / TP64000 preview returned selected Algo account and native contract/funds information. Confirmation remained unchecked; Place was never clicked. Desktop and 520x900 narrow layouts inspected; screenshots /private/tmp/sector-pulse-delta-chart-order-active.jpg and sector-pulse-delta-chart-order-narrow.jpg. Closed validation draft and reset viewport. Native postcheck again zero positions and zero open orders. No trades submitted.
- Existing manual price viewport is preserved, so out-of-range marked levels can remain outside the plotted price range; no automatic viewport reset was introduced. Full TradingView parity and full broker activation remain incomplete.

### FYERS history restriction classification staged — 18 November 2026
- Read-only calendar history probe encountered native HTTP429 on older daily history and stopped. Extended history availability is not established; quota versus account plan restriction is unresolved. No session renewal attempted.
- Root-only staged FyersHistoryRateLimited classification and token-scoped bounded Retry-After cooldown prevent immediate repeated calls and distinguish restrictions from expired authentication. Nine focused history tests pass. Probe now paces requests, memoizes queries, bounds calls and preserves partial failures. Not loaded into FYERS worker; no additional reload authorized/performed.

### Explicit marked-level visibility — 18 November 2026
- Added Show marked levels secondary action in the active Delta chart ticket. It expands only the price range to include Entry/SL/Target with padding, preserving time range and exact order values; no automatic fitting on ticks or order requests. Root and exact active Delta frontend updated (workspace1933, bridge2, ticketCSS3), no backend reload. Backup .private/chart-order-rollouts/chart-fit-levels-xz9bceh6.
- 31 ticket/integration tests pass including explicit-only fit, unchanged exact draft prices, no submission and source invalidation. JS syntax checks pass. Hosted desktop proves all three previously offscreen draft levels visible at 60000/59000/62000; narrow520x900 layout inspected with spaced full-width secondary/primary actions. Live quote advanced while range stayed expanded. Screenshot /private/tmp/sector-pulse-marked-levels-desktop.jpg and narrow counterpart. Closed validation draft/reset viewport; no preview or order submitted in this verification.
- Full goal remains active; other broker order activation, comprehensive Pine compatibility/performance and complete parity remain unproven.

### Hosted Pine completion and Renko construction audit — 18 November 2026
- Actual hosted Delta Sector Pulse V1 finished its prior calculation and displayed its plots and compact research/level tables; absence of a server Pine process is expected because evaluation is browser Worker based. This does not establish TradingView numerical parity or fast startup.
- Selected Renko chart, opened instrument-line Renko settings, exercised Traditional (10 points), reloaded and verified persisted Traditional label. Exercised Percentage (1%, tick-rounded 631 points from reference close 63078.5), changed Close to OHLC and observed updated label. Restored original ATR7/Close and original Candles chart. These changes affect chart presentation, not runner settings or orders. Screenshot /private/tmp/sector-pulse-renko-method-settings.jpg.
- Discovered chart-type dropdown Renko settings shortcut does not reveal settings when invoked from Candles; direct Chart Settings→Renko and Renko instrument badge work. Attempted deferred sibling-menu transfer did not resolve hosted symptom and was removed. Current JS1935 is restored original logic plus prior accepted changes; no speculative fix remains. Four navigation regressions and JS syntax check pass. Shortcut remains unresolved for follow-up. No service reload or broker mutation. Full goal active.

### Renko settings shortcut fixed and hosted verified — 18 November 2026
- Fixed the previously unresolved chart-type dropdown Renko settings action with a direct originating-control click listener and shared openRenkoSettings helper; stops delegated menu interception, opens construction tab and focuses method selector. Existing instrument badge uses same helper. Does not switch chart type or alter construction values. Applied only this targeted change across root and existing broker frontend snapshots, preserving their integration differences; cache version1936. Backup .private/chart-order-rollouts/renko-direct-settings-ao2qtrbl.
- Actual hosted Delta Candles→type menu→Renko settings now reveals ATR7/Close construction panel. Desktop mouse and narrow520x900 Enter-key activation verified, settings values unchanged. Screenshots /private/tmp/sector-pulse-renko-shortcut-fixed-desktop.jpg and narrow counterpart. Restored normal viewport/closed menus. Debugger event instrumentation removed/disabled; no production service reload or broker action.
- Six focused tests pass: direct action survives an ancestor delegated-menu interception, menu/tab/focus invariants, re-open retains method/length, plus four existing navigation regressions. This resolves the preceding shortcut finding; full TradingView objective remains active/incomplete.

### Pine table expand/compact readability — 18 November 2026
- Added an accessible per-table expand/compact control while preserving compact default overlays. Expanded stack may use75% pane height/80% width, with scroll fallback and untruncated cell text. Existing table body and keyboard scroll behavior remain; expansion is scoped to study+position slot and survives live table updates/reconstruction without enlarging unrelated studies. New controls preserve exact script text/data and do not modify indicator calculations.
- Root plus six maintained broker frontend snapshots updated with targeted table-renderer changes and CSS, versions JS1937/CSS303. Unmaintained snapshots with differing table blocks were not overwritten. Backup .private/chart-order-rollouts/pine-table-expand-y54yiyqg. Initial hosted expansion exposed a higher-specificity position height cap, corrected before acceptance.
- Actual hosted Delta V1 Levels table expanded from96px clipped content to224px scroll viewport for224px full table: all RSI, previous-day/week/month and history-footer rows visible. Desktop and520x900 narrow inspected; compact control returned table to small default, viewportreset. Screenshots /private/tmp/sector-pulse-expanded-pine-table-desktop.jpg and narrow counterpart. No backend reload or broker mutation.
- Three new DOM regressions cover preserved control identity through tick updates, expansion across narrow reconstruction, per-study isolation, changing captions/accessibility and return to compact. Nine expansion/Renko/navigation tests and12 drawing/trading regressions pass (21total); JS syntaxcheck passes. Full goal remains active/incomplete.

### Requirement audit and exact-worker FYERS catalog coverage — 18 November 2026
- Added explicit full-scope acceptance audit with13 original requirement groups, evidence/limits and next priorities. No broad completion claim. Registry contains129 built-in study definitions including ATR/ATR%; this does not cover all TradingView/community/protected studies.
- New read-only scripts/audit_fyers_chart_catalog.py audits exact source cache with no network/credential operations: native unique symbols, parser rejections, first/last pagination, hashes and freshness. Current FYERS owner source has180069 combined searchable symbols across seven segments, zero rejected native symbols. Separate hosted authenticated catalog request offset180068 returned total180069 and final NSE:ZYDUSWELL-EQ, confirming running endpoint coverage rather than only staging. Evidence docs/fyers-chart-catalog-audit-20261118.json. Does not prove historical/live data entitlement for every symbol.
- No code activation, process reload, runner change or order mutation. Next audits should cover other native broker catalogs and selected-broker chart data/type matrix.

### Delta exact-native catalog and Dhan coverage gap — 19 November 2026
- Delta public live products fully paginated in3pages:1364unique/live products,554calls/533puts/12MOVE/261perpetual/4spot. Actual authenticated hosted /api/delta-india/instruments?scope=chart exposes same1364 symbols, complete=true, PAXGUSD present. Sorted symbol-set SHA256 matches exactly:69d3e9bc9a8e9a078c9f366438e9ce38bd0a5b8e94c7783519a097f87f3aaebb. Evidence docs/delta-chart-catalog-audit-20261119.json. Chart-workspace/symbols generic route is not the active Delta API; initial404 was route mismatch, not missing native products. No per-symbol data entitlement claim.
- Dhan public master fetched read-only,227019rows. Exact Pinaki source parser totals:190indices,10094NSEcash,13675BSEcash,92824NSEFO,45211BSEFO,1NSEcurrency,0BSEcurrency,16680MCX. First/last reachability checked for nonempty segments. Currency eligibility/expiry filtering needs separate native review. Native master also includes24178NSE:M and4NSE:G rows that current adapter does not expose; verify official API segment/data support before mapping or adding. Evidence docs/dhan-chart-catalog-audit-20261119.json. No authenticated Dhan request/session renewal.
- Acceptance audit updated with substantive NSE-commodity mapping investigation priority. No production code/reload/runner/order changes. Full goal remains active/incomplete.

### Dhan NSE commodity API mapping investigation — 19 November 2026
- Read current official annexure exchange table: IDX_I0, NSE_EQ1, NSE_FNO2, NSE_CURRENCY3, BSE_EQ4, MCX_COMM5, BSE_CURRENCY7, BSE_FNO8. No NSE_COMM numeric feed segment documented. Official new documentation HTML links public OpenAPI https://docs.dhanhq.co/openapi/dhan-api-v2.yaml; downloaded read-only to/tmp and hashed in Dhan catalog evidence. History exchangeSegment schema is unconstrained string, so it does not prove NSE commodity support; quote schema examples are not complete capability lists.
- Third-party OpenAlgo maps NCO→NSE_COMM; that is corroborating research, not authoritative native acceptance. One credential-free GET https://api.dhan.co/v2/instrument/NSE_COMM returned404 Invalid instrument. This does not establish authenticated chart/feed impossibility, but prevents safely assuming a valid mapping or borrowing MCX segment5. No guessed routing added.
- Updated docs/dhan-chart-catalog-audit-20261119.json with exact sources/hash/probe and scope limits. No authenticated broker requests, credential renewal, process reload, runner change or orders. This sub-item remains unverified; other catalog/chart work can continue.

### Motilal cached catalog audit / hosted session expiry — 19 November 2026
- Exact Motilal owner cached schema2 masters include NSE10094, BSE13254, NSEFO92542(raw)/92012unexpired-unsuspended, BSEFO44735, NSECD11625, MCX17486(raw)/16693eligible, NCDEX2253. Public instrument metadata hashes retained in docs/motilal-chart-catalog-audit-20261119.json. Caches about30.9hours old; index masters are not persisted there. This is last-good evidence, not current completeness.
- Actual authenticated hosted chart-symbol GET returned Motilal session expired; sign in again. Stopped this broker probe; no credential entry/renewal, no broker account mutation, no service restart. Current Motilal catalog completeness remains unverified pending user reconnection. Other goal work can continue, so full goal remains active.

### Hosted Line / Heikin Ashi matched-source verification — 19 November 2026
- Current validation tab was FYERS NIFTY50 rather than prior Delta. Verified actual selected source before numerical claims. Browser connection changed during export; recovered availableChrome connection using documented inventory and fresh verification tab. Download event notification timed out but actual native CSV artifacts existed with current timestamps; no application export failure inferred.
- Regular chart restored to Candles before further checking through an explicit shared-view URL (FYERS/NIFTY50/30m/Heikin Ashi), which does not overwrite saved chart preferences. Export all loaded bars produced406completed candles in each Line/HA export, spanning5Oct–18Nov2026. Remote independent recurrence comparison: Line CLOSE maximum error0; HA open/high/low/close maximum errors all0. All406 overlapping source OHLC rows agree exactly. Evidence docs/chart-line-heikin-fyers-verification-20261119.json with CSV hashes. This is matched-input calculation evidence, not external TradingView feed parity or all-broker/live rollover proof.
- Actual HA desktop and520x900 narrow inspected, including separate Broker versus synthetic price labels. Shared Line view checked afterward. Screenshots /private/tmp/sector-pulse-heikin-ashi-fyers-30m.jpg, narrow counterpart and sector-pulse-line-fyers-30m.jpg. Reset viewport and closed temporary shared tab. No service/runner/order changes. Existing56candle/study regressions pass. Full goal remains active/incomplete.

### Hosted ATR calculation and width validation — 19 November 2026
- Isolated FYERS/NIFTY50/30m Candles shared view; added native Average True Range in separate pane with default14/RMA. Verified settings expose RMA/SMA/EMA/WMA and changed Default line width to4px through Style. Actual desktop/narrow pane shows the thick ATR line, accessible pane collapse/expand/maximize controls and native last-value label. This temporary study/style did not overwrite saved chart preferences; viewport reset and tabclosed.
- Export all loaded bars produced406completed broker candles. Remote independent true-range/Wilder seed/recurrence comparison checked13blank warmup rows and393ATRvalues; maximum absolute error4.263256414560601e-14. Evidence docs/chart-atr-fyers-verification-20261119.json includes CSVhash and scope. No external TradingView ATR export comparison claimed.
- Screenshots /private/tmp/sector-pulse-atr-four-pixel-desktop.jpg and narrow counterpart. No broker orders, runner changes or backend reloads. Full129study/all-broker parity remains incomplete; full goal active.

### Hosted Delta calendar history and pagination — 19 November 2026
- Read-only authenticated hosted Delta BTCUSD endpoint:1W142current+8older=150;1M32current+2older=34;12M1current+1older=2. Older pages reach1Jan2024 with no duplicate/overlapping timestamps. Follow-up terminal pages all returnrows0 andolder_history=false. This verifies loaded route behavior, not merely source/tests. Public response artifacts copied to remote/tmp for independent validation.
- Six current/older sampled aggregates compared with native1d endpoint. Weekly samples7days each, monthly samples31days and leap-Feb29days,2025annual365days all matchOHLCV exactly. Initial2024narrowquery gave357days and opening discrepancy2910; investigated rather than suppressing. Narrow Jan1–15request also omittedJan1–9. Exact worker999-day request returned full366days, including9flat zero-volume native opening bars, and reproduced hosted2024annualOHLCV exactly. Broker data is request-window-sensitive; external TradingView opening/launch parity remains unproven. Both checks preserved in docs/delta-calendar-hosted-verification-20261119.json. No generated candles or source substitutions added.
- API audit tabs closed. No financial mutation, runner changes, backend restart or saved chart preference changes. Full goal remains active/incomplete; other brokers and UI interval matrix still require acceptance.

### Global chart access audit / independent Delta catalog permission route staged — 19 November 2026
- Read-only actual registry:2users/1admin; sole regular user has chart-workspace assignment. Effective sidebar visibility merges registry defaults with saved choices and chart isvisible. require_chart passed for both actual users. No assignment/global visibility mutations performed. Raw saved visibility lacks a chart key but effective registered default istrue; do not misreport that as hidden.
- Found independent-access gap: chart frontend requests Delta catalog through /api/delta-india/instruments?scope=chart, whose workspace guard requires the Delta trading-section feature. A user assigned only chart-workspace cannot discover selected Delta symbols through that route. Root generic chart symbol route exists, but active private Delta worker does not implement it and the chart needs full native metadata.
- Added read-only sector_heatmap/chart_catalog.py and staged /api/chart-workspace/catalog GET dispatch in root+exactDelta web source. Enforces chart assignment AND global chart visibility, exact Delta workspace; returns full complete native chart metadata and rejects incomplete/wrong-provider responses. No trading capability granted. Four focused permission tests pass: chart-only succeeds; unassigned/Delta-only/global-hidden-admin denied before broker query; no workspace/wrong broker cannot fallback; partial provider payload notpublished. Both staged web modules compile.
- Frontend endpoint replacement staged in7targeted candidates, preserving divergent account integrations. Not activated before worker route isloaded. Backup/candidate/hashmanifest .private/chart-order-rollouts/chart-catalog-route-3byfgtsu/manifest.json. Activation needs onlyDelta dashboard worker reload plus static JS1938 inclusion; main service/FYERS/execution workers outside scope.
- Fresh preapproval safety checks:3canonicalDelta states stopped; nativeDelta0positions/0openorders. No reload or order sent. Separate specific reload authorization required by remoteAGENTS before activation. Full goal active; hosted chart-only route acceptance pending activation.

### Hosted Yahoo calendar history / cross-resolution verification — 19 November 2026
- While Delta catalog reload authorization remains pending, read-only hosted Yahoo ^NSEI history returned1W261current+262older,1M59current+60older,12M4current+5older. No overlapping or duplicate timestamps acrosspages. Weekly coverage7Nov2016–9Nov2026, monthlyDec2016–Oct2026, annual2017–2025. Validated exchange-zone anchors at Asia/Kolkata midnight, Mondays forweeks and firstday/month/Jan1 asappropriate.
- Independent aggregation of12native monthly bars for each of9annual candles2017–2025 reproduced allOHLCV fields exactly. Evidence docs/yahoo-calendar-hosted-verification-20261119.json with payloadhashes. No per-broker/live-WS claim; Yahoo calendar adapter intentionally excludes unfinished buckets and does not currently supply a forming period preview. That remains a distinct parity consideration.
- API audit tabclosed. No broker/runner/credentials changed and no reload inferred from pending approval. Full goal active/incomplete.

### Yahoo forming calendar snapshots backend staged — 19 November 2026
- Added sector_heatmap/yahoo_snapshot.py with provider-stamped provisional weekly/monthly/multi-month snapshots from Yahoo-native period OHLC. Requires exchange timezone, nonfuture provider regularMarketTime, contiguous source periods from bucketstart and valid OHLC; rejects conflicting duplicates/missing periods, appended quote rows and older-page queries. Uses real exchange-zone boundaries through DST and preserves unknown volume. It does not invent missing source candles or label snapshots live.
- Integrated separate forming_snapshot result field in root yahoo_chart.history; completed rows remain unchanged, older pages never receive current snapshots. Adds exact calendar close_time mapping for the provisional bucket. Root backend source only, not loaded production; no frontend integration yet, no main service reload requested/performed. Backup/hashmanifest .private/chart-order-rollouts/yahoo-calendar-snapshot-u14i2s78/manifest.json. Pending Delta catalog JS candidates and active frontend unchanged.
- Eight focused helper/integration tests plus28existing chart access/Yahoo regressions pass (36total), covering partialcurrentmonth inannual, quote-snapshot rejection, missing/invalid/conflicting data, historical isolation, provider age, unknownvolume, DST167-hour week and separate completed/snapshot output.
- Read-only staged source against current native Yahoo ^NSEI returned current weekly/monthly/annual snapshots distinct from261/59/4completed bars, with provider as_of1794996069 and exact future bucket boundaries; proof docs/yahoo-forming-calendar-staged-verification-20261119.json. This is native-source/staged verification, not hosted activation or rendered acceptance. Frontend/Pine cutoff integration and desktop/narrow validation remain next; only then request main reload authorization. Fullgoalactive.

### Yahoo snapshot frontend/Pine integration and rendered candidate — 19 November 2026
- Staged seven frontend copies (JS1939 candidate) normalize only explicitly provisional Yahoo forming_snapshot payloads into temporary calendar prefixes, retain provider observation/close timestamps, reject future/expired/invalid/cross-provider payloads, preserve native broker prefixes and label Historical snapshot/Yahoo Finance snapshot as of. Completed history store remains unchanged. Pine secondary and same-host requests exclude snapshot values before observation cutoff; exact observation timestamp is eligible without waiting until future period close.
- Four focused JS tests pass; isolated copy of actual candidate passes all64snapshot/candle/study/navigation regressions (test extractor updated to include actual new helpers, no identity stub). Backend36tests pass. All7frontend variants parse. Immutable combined Yahoo+Delta catalog variants recorded in both pending manifests to preserve either approved activation order; never overwrite newer active code without exact baseSHA match. Active production JS remains1937.
- Full candidate rendered through loopback-only fixture using captured native Yahoo2017–2025annual bars plus2026snapshot; all broker forwarding/submission blocked. Desktop and520x900 main-pane layouts show current annual candle and Historical snapshot badge with provider asof18Nov2026. Corrected fixture mounting to actual .sp-main-chart container (initial modal layout not used for acceptance). Screenshots /private/tmp/sector-pulse-yahoo-snapshot-preview-desktop.jpg and narrow counterpart. This is isolated preview, not hosted production acceptance.
- Closed preview tab/reset viewport. Terminated SSHforward, verified exact temporary http.serverPID3839272 command/directory, SIGINT stopped only that fixture server and verified no8877listener. No production service/broker state changes.
- Main restart precheck:sector-heatmap.service MainPID3697650, KillModecontrol-group, exactly1process in cgroup, cwdrootproject. All13canonicalrootstates stopped. Private broker workers outside service; FYERS native3positions/0orders remainsoutside requested restart and its worker is notto be restarted. Main-only authorization will be requested under remoteAGENTS, with scope/state recheck immediately before any action. Pending Delta-only catalog reload approval remains separate. Fullgoalactive.

### Independent core-indicator numerical checks across brokers — 19 November 2026
- Added reusable read-only scripts/verify_chart_core_indicators.py. It runs the current pure JavaScript indicator library and compares against independent Python Decimal50-digit SMA/EMA/WilderRSI/population-variance Bollinger/MACD/WilderATR calculations, including exact warmup-null alignment. No broker credentials/API calls or production state changes.
- Matched inputs:406completed FYERS NIFTY50 30m candles from actual hosted CSV export;150completed Delta BTCUSD weekly bars serialized losslessly from previously captured hosted current+older APIpages. SettingsSMA20/EMA20/RSI14/BB20×2/MACD12-26-9/ATR14RMA. All10plots per dataset pass, zero warmup mismatches. Maximum errors1.613647919603356e-11(FYERS) and2.5160504181433618e-11(Delta); reference input/libraryhashes retained.
- Evidence docs/chart-core-indicator-verification-20261119.json and docs/chart-core-indicator-delta-verification-20261119.json. These prove current-library calculations on matched native-input series, not live rendering for every study, external TradingView seeded-history parity or all129studies. Pending Delta catalog and main Yahoo snapshot reload approvals remain pending; no approval inferred from goal continuation. Fullgoalactive.


### Pine startup profiling — 19 November 2026

An isolated saved-FYERS-candle benchmark now records declaration, evaluation, serialization, provider timings and output hashes using the deployed worker bytes. Node VM measurements substantially overstate normal-context runtime (about 19/28 seconds versus 6/7 seconds for 100/400 host bars); these are diagnostic, not browser acceptance evidence. A series-constructor candidate preserves complete output hashes at both sizes, but speed results are mixed and no production runtime has changed. Browser verification is being performed separately. Evidence: `chart-pine-startup-profile-20261119.json`, `chart-pine-startup-cpu-profile-20261119.json`, `chart-pine-startup-native-context-20261119.json`, `chart-pine-series-candidate-20261119.json`.

Browser candidate verification completed with identical complete plot hashes on all four runs. Baseline 12.40/11.48 seconds; candidate 10.18/10.03 seconds (15.4% average improvement in this fixture). Not deployed; additional scripts and live update behavior still require verification. See `chart-pine-browser-performance-20261119.json`.

Pine series constructor optimization activated by atomic worker-file replacement without service reload. Seven focused fixture initial/reset/tail comparisons pass; standalone AI Renko Supertrend output matches. Sector Pulse V2 reproduces the same pre-existing Shadow Candle guard error on baseline and candidate, still unresolved. Actual hosted Delta BTCUSD 30m Sector Pulse V1 rendered both table overlays after startup. Exact browser network-body hash was not captured; disk SHA and dynamic no-store route were verified separately. Rollback and activation evidence are in `.private/chart-order-rollouts/pine-series-optimization-20261119/manifest.json`.

### Secondary-request chart guard defect

The standalone Shadow Candle script saved as `sector-pulse-v2.pine` fails on a valid 5-minute chart because request slices retain its unrelated top-level intraday guard when evaluating daily/weekly/monthly contexts. A minimal seven-line reproduction is preserved in `tests/fixtures/pine/chart-guard-secondary-request.pine`; active-runtime result in `chart-pine-secondary-guard-20261119.json`. This is not a source-script syntax failure. Correct repair requires dependency-aware request projection; blanket suppression of secondary runtime errors is not an acceptable fix. Unresolved.

Secondary guard candidate now calculates standalone Shadow Candle using saved FYERS candles. Nine AST boundary tests, four real-Pine guard cases and seven existing Pine fixtures pass. Sector Pulse V1 400-bar complete output matches fresh baseline execution; comparisons must use identical run order because runtime drawing IDs depend on earlier runs. Host errors, requested-function errors and mutation-bearing branches remain enforced. NOT active; browser/hosted verification remains. Evidence: `.private/chart-order-rollouts/pine-request-guard-20261119/manifest.json`.

Secondary-request guard fix activated without service restart. Browser fixture baseline reproduced failure; candidate completed in 977ms with 13 labels, 27 lines, 208 boxes and one table. Actual hosted Delta BTCUSD 5m shared view applied standalone Shadow Candle without runtime.error. Table reported source candle unavailable; execution is verified, value parity is NOT. Original Pine editor draft restored, regular chart preferences not overwritten, no order activity. Next: diagnose missing shortened reference candle.

Crypto Shadow Candle availability diagnosed: Pine time_tradingday incorrectly rolls a candle closing exactly at UTC midnight into the next day. Isolated crypto-only candidate uses the final instant inside the candle; non-crypto behavior is preserved. Boundary test fails on baseline and passes on candidate. Captured Delta public BTCUSD frames (three requests, no private/account calls) change standalone Shadow Candle from unavailable to populated, with selected source high/low exactly matching a native shortened reference. Completed-only replay does not include the forming reference period, so latest-session publication still needs coverage. Candidate NOT active. Evidence: `.private/chart-order-rollouts/pine-crypto-tradingday-20261119/manifest.json`.

Crypto trading-day candidate activated without reload. Public broker partial reference (19 consecutive completed 1h candles) makes the latest finished shortened candle publish: 17 Nov 23:00–18 Nov 00:00 UTC, H65243/L64695.5. Standalone script default 46/50/56 levels exactly equal 64947.35/64969.25/65002.10. Actual hosted chart was 30m (URL used 5m, which did not select 5-minute; earlier hosted 5m labels are corrected), and renders the same source/levels at desktop and 520px width. Original editor draft restored; shared view did not overwrite saved chart. Active boundary and request-guard semantics pass. Evidence: `.private/chart-order-rollouts/pine-crypto-tradingday-20261119/manifest.json`.

### Full registry default calculation coverage

All119 standalone indicator calculators produce finite output without exceptions or infinities on406capturedFYERS30m and150capturedDeltaweekly candles. Empty,1bar and10bar FYERS inputs also avoid crashes; warmup-only outputs are explicitly recorded. Ten context-dependent entries (reference zones, pivots, BollingerBars, volume delta, comparison studies and52-week levels) need separate chart-context acceptance. This is calculation coverage, not numerical/reference or visual parity. Evidence: `chart-indicator-default-coverage-20261119.json`; reusable auditor `scripts/audit_chart_indicator_defaults.cjs`. Acceptance ledger refreshed without marking any broad requirement complete.

### Reference-period indicator acceptance

Independent Decimal50 pivot checks cover six methods,897cases including all DM branches, plus49high/low source combinations for52-week levels.7557numeric values match within2.91e-11;51-week warmup returnsnull levels. Actual hosted DeltaBTCUSD1W shared view shows default close-source Highest93623/Lowest59556.5, matching captured completed weeks17Nov2025–9Nov2026; current forming week excluded. Desktop and520px scale labels verified. No regular preferences overwritten or trades placed. Pivot rendering and broader reference-feed parity remain. Evidence: `chart-reference-levels-verification-20261119.json`.

### Delta alternate Pine reference boundaries

Catalog-validated Delta cross-symbol requests already existed. Fixed alternate-reference adapter discarding utc_daily metadata, which incorrectly extended shortened14/22/23h bars. Active static assets1940 in seven maintained sources.65active regression checks pass; pending Yahoo/catalog frontend variants were rebased immutably and69Yahoo-candidate checks pass. Pending original manifests point to newer rebased manifests; approvals remain required for backend activation. Hosted BTCUSD30m requestedETHUSD1380: reference closes18Nov00:00UTC andH1835.55/L1813.8 exactly match native public data. Shared view only, editor draft restored. A separate direct time_tradingday[1] history defect was reproduced (no finite values versus correct assigned-variable history) and remains open; see `pine-tradingday-history-probe-20261119.json`.

### Direct trading-day history candidate

Direct time_tradingday[1] failed because built-in metadata was scalar-only. Series-backed candidate now preserves offsets0/1/3 and scalar comparisons. Six cache tests cover same-bar revisions, appended bars, truncation, metadata changes and independent secondary contexts. Actual worker refresh passes initial, revised timestamp, full reset and new-bar cases. Seven existing Pine fixtures, fullV1 400-bar output and standalone Shadow Candle native-fixture output remain unchanged. Candidate NOT active; hosted cross-symbol check remains. Evidence: `.private/chart-order-rollouts/pine-tradingday-history-20261119/manifest.json`.

Direct trading-day history fix activated without reload. Hosted BTCUSD30m cross-symbolETHUSD1380 script now shows close18Nov00:00UTC, trading day17Nov, H1835.55/L1813.8; missing history no longer formats as current date. Desktop and520px inspected; original editor draft restored and shared chart closed. Active history and live-tail tests pass. Evidence: `.private/chart-order-rollouts/pine-tradingday-history-20261119/manifest.json`.

### Dhan global chart/session verification

Fresh shared-view Dhan Pinaki chart opens globally for NSE_EQ:1333; history asks for reconnect. Saved token expiry4Nov2026 10:11:53IST is past; no newer consent session found. Metadata-only audit finds3registered Dhan workspaces with2client bindings and no unexpired saved credential tokens. No native profile/data request was forced outside the UI; no token renewed, credentials exposed, runner changed or order sent. User asked asynchronously to reconnect exact account once in Accounts, while independent chart work continues. Evidence: `dhan-chart-session-verification-20261119.json`.

### Two-symbol comparison arithmetic

Read-only Delta ETHUSD weekly capture142completed bars joined by exact timestamp with150BTCUSD weeks. Independent Decimal50 checks cover Spread, Ratio and20period Pearson Correlation across7price sources:994+994+861numeric checks plus301missing/warmup null checks pass; maximum errors1.46e-11/7.11e-15/5.56e-16. No forward fill of missing reference weeks. This is arithmetic/selection evidence, not hosted rendering or external TradingView parity. Evidence: `chart-comparison-studies-verification-20261119.json`. Dhan chart validation remains awaiting user reconnection; independent work continues.

### Hosted comparison study rendering/export

Spread, Ratio and Correlation selectedETHUSD through the broker-native symbol picker onDeltaBTCUSD1W. Separate panes render at desktop/520px. Export has150completed+1forming rows;407completed values independently match capturedETHUSD weekly data. Generic Plot/Plot(2) labels corrected toSpread/Ratio in7maintained study libraries (assetversionrenko-ohlc-2); fresh hosted export names verified,450completed field comparisons unchanged. Current forming-week comparison row is blank; live reference coverage remains open, not silently replaced by historical prices. Shared view closed without changing saved preferences. Evidence: `chart-comparison-hosted-export-20261119.json`.

### Forming alternate-reference studies fixed

Reference history previously discarded completed-day calendar prefixes; live weekly updates only carried the current day and were rejected. Retained per-symbol prefix/native/seed/session metadata and reused guarded composition. Same-close range/volume changes now trigger recalculation. Eleven focused coverage/freshness/gap checks plus active76regressions pass; pending Yahoo frontend rebase passes80checks. Static version1943 active in7sources, no service reload. Two actual hosted BTCUSD1W/ETHUSD1W exports now contain forming Spread/Ratio/Correlation, reference-derived close changes1749.8 to1750.4, ratios/correlations match independent consistency arithmetic,900completed fields unchanged. Current reference close is derived from spread, not an independently simultaneous native quote. Desktop inspected;520px current values visible but bottom pane needs height optimization. Shared view closed, saved regular chart unchanged. Evidence: chart-forming-comparison-verification-20261119.json.

### Narrow pane height optimization

CSS304 activated in7maintained sources. Ordinary indicator panes can shrink on viewports<=700px to90px minimum; explicit flex-basis sizes, expanded/collapsed/maximized states are excluded. Actual hosted BTCUSD30m OBV/RSI/MACD at520x900 override: stage537px, prior content598px, fixed content537px; price220px unchanged and indicator panes103.62/103.61/103.62px. Desktop124px defaults unchanged. Keyboard resize produced manual114/94px, preserved across viewport roundtrip and collapse34px/restore. Shared-view checks only; saved chart not overwritten. Calculations/orders unchanged. Evidence: .private/chart-order-rollouts/narrow-pane-fit-20261119/manifest.json. Existing user tabs need normal refresh to load new asset version.

### Current TradingView desktop visual measurement

Read-only signed-in TradingView BTCUSD.P5m reference showed SMA legend rows24px,13pxfont,weight400. SectorPulse BTCUSD30m baseline used28pxordinary/32pxPine calculation rows andweight700. CSS305 now gives ready rows24px/13px/400 at desktop fine-pointer widths; narrow28px bold rows remain. Actual SMA settings, hide/show and legend collapse/restore verified in shared view. No TradingView settings or regular SectorPulse preferences changed. Source intervals/studies/ranges differ, so no full pixel or price parity is claimed. Evidence: .private/chart-order-rollouts/desktop-legend-reference-20261119/manifest.json.

### Renewed Dhan source verified

User reported reconnection complete. Credential metadata shows renewedSubhalaxmi token; Pinaki remains separate/expired. Actual global SubhalaxmiNSE_EQ:1333 chart loads372valid unique completed30m candles, with Outside trading hours label; existing workerPID3698064 unchanged. HDFCBANK search524matches and pagination101–200 verified; MCXGOLD4526futures/options matches, no contract selected. No orders or credential changes by agent. All31exported sessions end14:45IST, omitting final15:15shortened30m candle; this is the next history investigation, not certified complete coverage. Reference-request failure cleanup meanwhile has79candidate/83rebasedYahoo passing checks and remains staged, not active. Evidence: dhan-renewed-chart-verification-20261119.json.


### Reference feed failure recovery — 19 November 2026

Activated static frontend v1946 across seven maintained sources with SHA-guarded backups; no worker/service reload. Focused 3 tests pass, previously staged regression set 79 passed. In an isolated hosted BTCUSD 30m shared view, ETHUSD Spread initially showed 60,759.60. Blocking only that tab reference live request cleared the forming value to —. Removing the block produced HTTP 200 on automatic retry and Spread 60,753.50 without manual refresh. Browser block removed, test tab closed, saved chart preferences preserved. Evidence: docs/chart-reference-feed-recovery-20261119.json. This proves one hosted feed-failure/recovery path, not complete TradingView parity.


### Drawing settings nested scroll — 19 November 2026

Hosted drawing-manager audit reproduced nested list/manager scroll conflict at narrow viewport. CSS306 removes the expanded level-list internal scroll, leaving the outer manager scroll. Activated seven maintained sources without process reload. Rechecked desktop/narrow, color #e53935 and 4px, final italic control reachable. Effective CSS width578 for520px override; expanded list643px client/scroll heights and overflow visible. Saved user preferences preserved by isolated shared view. Caption became empty after subsequent edits; persistence/rerender requires separate investigation. Full drawing extensions/favorites/tool matrix remains open. Manifest: .private/chart-order-rollouts/drawing-settings-scroll-20261119/manifest.json.


### Caption persistence followup — 19 November 2026

The earlier caption reset was reproduced with programmatic fill, but NOT with normal sequential typing and Tab or explicit Enter. Hosted shared BTCUSD30m: typed RESISTANCE - 65111.21 persisted after italic, width4px and narrow caption-size14 changes. Narrow screenshot saved. No runtime code change warranted. Correct the earlier general defect claim to test-harness commit limitation; regular saved workspace/reload persistence and complete drawing matrix remain open. Evidence: docs/chart-caption-persistence-20261119.json.


### Drawing catalog, favorites and extensions — 19 November 2026

Captured hosted grouped drawing catalog: 89 tools/eight groups, plus separate horizontal-line action. In isolated shared view, searched Trend line, favorited it and observed floating-strip insertion. Placed trend with two chart clicks, applied both left/right extensions and3px width, reopened editor and verified all retained. Agent test tab closed; regular saved preferences unchanged. Six drawing-settings/layer tests pass. Existence and one trend workflow do not establish all tool/TradingView parity. Evidence: docs/chart-trend-tool-hosted-verification-20261119.json.


### Trend geometry and click-placement defect — 19 November 2026

Drag construction verified distinct09:00/18:00IST anchors and sloped both-extended rendering. Single click prematurely completed same-bar10:30IST line with distinct prices. First pointer/chart-callback suppression candidate passed3focused simulations but FAILED actual hosted single-click check; all7static sources restored to JS1946, CSS306 retained. Candidate tests moved out of active suite into rejected rollout. This corrects any inference that previous two-click construction proved correct geometry. Pending frontend manifests flagged for CSS306 rebase. Full goal remains incomplete. Evidence: docs/chart-trend-geometry-20261119.json.


### Click placement fix verified — 19 November 2026

Actual browser trace disproved duplicate-callback hypothesis: same physical pointer450/500, pane-local Y326.46→333.79 caused false dragged=true. JS1951 uses physical client-coordinate distance with fallback for nonpointer callers. Seven static sources active, no service reload; temporary query-gated trace removed. Ten regression/settings/layer checks pass. Hosted first click now waits for second anchor; second completes10:30/18:00IST line. Drag regression09:00/20:00IST remains correct. Saved user preferences preserved. Pending catalog/Yahoo candidates explicitly flagged stale until rebased onto JS1951/CSS306. Manifest: .private/chart-order-rollouts/line-layout-shift-20261119/manifest.json.


### Pending candidate preservation — 19 November 2026

Rebased six unique catalog/Yahoo/combined frontend variants onto active JS1951 physical-pointer drag detection. New catalog/yahoo manifests under line-layout-shift-20261119 include CSS306 requirement, fresh active source SHA guards, updated conditional candidate base hashes and frontend versions1952/1953. Original and previous manifests point to latest manifests. Isolated test matrix: four Yahoo-enabled variants87pass/0skip; two non-Yahoo83pass/4Yahoo-onlyskip; zero failures. These remain staged and do not grant or perform worker/service reloads. Evidence: .private/chart-order-rollouts/line-layout-shift-20261119/pending-rebase-validation.json.


### Pine closed-reference timing defect — 19 November 2026

Hosted V1 expanded RSI table at02:59IST labels5m/15m/30m readings completed03:00IST. Exact minimal nested tuple helper reproduction returns previous_end=current_end in future under lookahead_off, including same-timeframe path. Simple lookahead_on previous tuple probe selects past timestamp. Candidate recursive Ta metadata unwrapping made no difference and was never activated. Runtime unchanged. Preserve fixture tests/fixtures/pine/closed-reference-nested-tuple.pine and rollout pine-closed-reference-20261119. This is a correctness gap, not full Pine parity. Trace tuple history/wrapper conversion next.


### Pine timestamp assignment fix — 19 November 2026

Root cause: Context.init stored the mutable time_close metadata wrapper in tuple variables; prior entries subsequently dereferenced latest context time. Snapshot its scalar current value during variable assignment. Candidate passed exact nested helper same/lower timeframe cases, seven existing fixture payload comparisons, crypto/stock trading day and four refresh checks. Fresh400bar historicalV1 payload SHA identical to baseline. Active worker SHA4d47c6fc404bc226da0c36d1abfcff69c22d4f799a4f7c8ae5c9283f44a0e639; served dynamic worker asset, no service reload. Hosted at03:06:14IST: completed5m03:05,15m03:00,30m03:00. Source/user preferences preserved. Broader Pine/live arithmetic still unproven. Manifest: .private/chart-order-rollouts/pine-metadata-snapshot-20261119/manifest.json.


### Dhan session-tail control matrix — 19 November 2026

Read-only native Nov16–19 request for equity1333: two returned sessions, each360one-minute rows09:15–15:14,72five-minute09:15–15:10,24fifteen-minute09:15–15:00. Index13 control returns50fifteen-minute rows/two sessions including15:15. This isolates sampled equity tail omission upstream of30m aggregation; do not synthesize missing prices. Native narrow response endsNov17 although earlier broad hosted export coveredNov18, so request-window/date coverage also remains unresolved. No runtime or broker changes. Evidence: docs/dhan-native-session-end-matrix-20261119.json.


### Docked Pine Editor pane fit — 19 November 2026

Manual406px price/144px indicator plus332px bottom editor previously produced stage253/scroll553. CSS308 permits temporary flex shrink only while bottom editor open; stage253/scroll253 with effective167.3/80. Closing editor restores406/144 exactly. Narrow520x900 override stage205/scroll205, effective126.86/72 with preferred416/134 retained. Desktop maximize/restore exercised. Seven maintained stylesheets active, no reload; pending manifests requireCSS308. Scope is single indicator pane, not arbitrary many-pane parity. Manifest: .private/chart-order-rollouts/bottom-editor-pane-fit-20261119/manifest.json.


### Bottom editor drawing rail containment — 19 November 2026

CSS309 active7maintained sources. Desktop bottom-docked editor previously had drawing icons spill over code. Rail now scrolls within chart row: top47.07/bottom475.56 equals editor top475.56, client428/scroll761. Keyboard reaches last tool at bottom475.17; group menu fixed/anchor positioning remains visible280px wide. Closing editor restores overflow visible/full748.49px rail. Narrow520x900 remains horizontal toolbar ending181.07 before editor680. Saved normal preferences unchanged; no service reload. CSS-anchor unsupported fallback not separately hosted-tested. Manifest: .private/chart-order-rollouts/bottom-editor-tool-rail-20261119/manifest.json.


### Extended Pine metadata history acceptance — 19 November 2026

Added scripts/verify_pine_metadata_history.cjs against actual worker.5m/15m/30m fixtures validate every timestamp plot, direct/assigned/tuple previous values, derived previous hour, persistent var/varip initial timestamps, and initial/same-bar metadata revision/reset/new-bar steps. All12frame/lifecycle combinations pass active worker. Pre-fix worker rejected, proving regression catches actual prior defect. No additional runtime change. Synthetic scope only; broader Pine compatibility remains unproven. Evidence: docs/pine-metadata-history-verification-20261119.json.


### PAXG four chart modes and construction controls — 19 November 2026

Hosted DeltaPAXGUSD30m renders Candles/Renko/Line/Heikin Ashi without unsupported error. Applied RenkoTraditional10pts/OHLC; Percentage1%37.21pts from3721.1reference; ATR7 10.24pts/OHLC. Narrow520x900 settings inspected. User normal preferences untouched via shared view; no runtime change. Sample OHLC values are asynchronous, not numerical parity evidence. Renko volume-dependent OBV correctly unavailable. Need independent Renko brick/reference and all-symbol matrix. Evidence: docs/paxg-four-chart-modes-verification-20261119.json.


### Renko Pine rebuild status — 19 November 2026

PAXGUSD30m Renko V1 inputs/style plots enabled. Export164ATR bricks contains164finiteAI Renko Supertrend and164Shakti Midline values. Switching to1% produces18bricks; old frame mismatch previously showed no values. JS1955 says recalculating for updated chart bars only while pendingSyntheticPlots owns the mismatch; notice clears when ready. Rebuilt export has18finite values for both overlays. Seven static sources active/no reload. Six pending catalog/Yahoo variants rebased1956/1957 and tested: four87pass; two83pass+4Yahoo-onlyskip, zero failures. Source preferences preserved. No independent Renko numerical parity claim. Manifest: .private/chart-order-rollouts/renko-pine-rebuild-notice-20261119/manifest.json.


### Independent hosted Renko arithmetic — 19 November 2026

Captured998completedPAXGUSD Delta30m source candles and3hosted Renko exports. Decimal50 independent state-machine reference uses floor grid and2brick reversals. Traditional10Close/projections+wicksOFF:162bricks648OHLC comparisons exact, all162source times exact. ATR10.24:164bodies328values max5e-13 and timestamps exact. Percentage37.21:18bodies36values max3e-13/timestamps exact. Percentage/ATR exports have wicks enabled: initial fullOHLC comparison correctly rejected differing high before scoping body-only; no wick parity claim. Independent WilderATR7 on998source candles10.242958683 rounds10.24 at.01tick, matching capturedhostedsize. Immutable CSV artifacts and hashes retained under paxg-renko-numeric-20261119. No runtime change; no externalTV seed/feed parity. Verifier: scripts/verify_hosted_renko_close_export.py.


### OHLC-source Renko numerical acceptance — 19 November 2026

Fresh matching PAXGDelta30m998completed candles and Traditional10/OHLC/projectionOFF/wicksOFF export234bricks independently reconstructed with Decimal50 reference. All936OHLC values and234source timestamps exact. Extended verifier accepts construction source;3prior Close configurations rerun/pass. Immutable source/export retained with hashes. OHLC traversal assumes risingO-L-H-C andfallingO-H-L-C; this validates configured rule consistency, not recovered tick path or externalTradingView parity. No runtime change. Evidence: docs/paxg-renko-traditional-ohlc-numeric-20261119.json.


### Mac shortcut hosted acceptance — 19 November 2026

Chrome shared BTC30m: OptionT selectsTrend, OptionShift1selectsfavoriteFib, OptionShiftIcollapses/restoreslegend, Escape cancelsplacement. CmdK opensChartquicksearch withstagefocused; workspacecontainerfocusalone didnot. Existing handler usesphysicalevent.code forOptionkeys. No code/preference changes. Scope is browser key events/Mac presentation, not exhaustive OS/browser keyboard-layout compatibility. Evidence: docs/chart-mac-shortcuts-verification-20261119.json.


### Workspace quick search shortcut focus — 19 November 2026

JS1958 adds guarded workspace bubbling handler forCmd/CtrlK outside editable/nested-dialog contexts. Chart-stage handler continues to consume its own events, avoiding double-open. HostedCmdKworkspace,CtrlKIndicatorsbutton,CmdKnarrowtoolbar verified. PineEditorCmdKdoesnotopenchartsearch or mutate109k script. Seven static sources/no restart. Six pending variants rebased1959/1960,CSS309 preserved,87pass eachYahoo variants and83+4skip nonYahoo;0failures. Previous sourcefocus limitation is resolved for normal workspace controls. Manifest: .private/chart-order-rollouts/chart-quick-search-focus-20261119/manifest.json.


### Standalone AI Renko direct add — 19 November 2026

Found catalog action opens Loadexample into occupied editor and refuses to add. JS1961 extracts the SAME standalone Pine source into shared helper; catalog action creates separate Pine worker study and restores it without changing editor draft. HostedPAXG30mRenko confirms1V1+1AIstudy,109kV1draft unchanged before/aftercalc,181ConnectedSupertrend values/181exportedbricks alongside181V1AIoverlay values. Desktop/narrow inspected. Existing library/source-equivalence test updated to actual helper extraction;56activecandle tests pass. Six pending variants rebased1962/1963 and pass applicable87/83tests. No worker/service reload, no script formula change, no external private-engine parity claim. Manifest: .private/chart-order-rollouts/ai-renko-direct-add-20261119/manifest.json.


### Stable Pine calculation legend rows — 19 November 2026

CSS310 extends desktop compact24px rule to Pine retry/restart button. Hosted calculating row31.9965→23.9931px, then ready23.9931px. Narrow touch row/button remains31.9965px. Chart stage top173.5417unchanged before/after, so this proves legend-row stability only, not root cause of all stage shifts or general flickering. Seven maintained sources active/no restart; pending candidate manifests requireCSS310. Manifest: .private/chart-order-rollouts/pine-legend-height-stability-20261119/manifest.json.


### Supertrend boundary and Ichimoku numeric validation — 19 November 2026

Independent Decimal50 reference checks8Supertrend parameter sets+3Ichimoku displacement sets on998PAXG and406FYERS. PAXGinitialfailure atNov3 21:00UTC: close3931.3 vsrawband3931.2999999999993 causedfalsebullflip. Investigated range was nonzero; exact equality boundary, not a zero-range candle. TradingView type-system documents float comparisons rounded9fractionaldigits. Chartlibrary now rounds only comparison operands, preservesrawband arithmetic, uses canonical previous-line/band directionbranch.22configs31178numeric+13448null checks pass(max1e-11);56regressions pass. Seven maintained libraries active v=supertrend-comparison-3,no restart. HostedATR1/factor1.5 PAXGexport confirmsbearish equality retained andall998complete points matchindependentreference. Ichimoku projection arrays and25bar default displacement mathematically verified, not full externalTVfeed/seed/render parity. Manifest: .private/chart-order-rollouts/supertrend-comparison-20261119/manifest.json. Officialrule: https://www.tradingview.com/pine-script-docs/language/type-system/.


### Pine worker Supertrend comparison boundary — 19 November 2026

Active Pine worker now rounds only ta.supertrend comparison operands to nine fractional digits, preserving band arithmetic. Sixteen configurations across PAXG/FYERS match chart implementation: 11120 numeric values, exact direction and warm-up masks. Seven prior fixture outputs, metadata-history checks and historical V1 400bar payload unchanged. Hosted PAXG30m script uses table to exercise worker path; applied study and table render. Export includes998completed candles; boundary Nov3 21:00UTC remains bearish at3931.3. Independent Decimal reference report passes hosted line/direction and existing trend references (24393 numeric/9092 null comparisons, max2e-12). Export retained with SHA in rollout. No service reload, regular preferences untouched. General Pine comparison semantics and full external TradingView parity remain unverified. Manifest: .private/chart-order-rollouts/pine-supertrend-comparison-20261119/manifest.json.


### Shared Pine float comparisons candidate — 19 November 2026

Confirmed shared runtime uses distance tolerance1e-10 instead of documented operand rounding9fractionaldigits. Candidate changes six numeric comparison operators only; ten positive/negative/equality/adjacent-bucket cases180checks pass, baseline rejects same-rounded-bucket equality. Seven existing script fixtures preserve initial/tail/reset output; metadata refresh checks pass. Candidate retained but NOT active pending V1 and hosted application checks. Manifest: .private/chart-order-rollouts/pine-float-comparison-20261119/manifest.json.


### Shared Pine comparisons active and hosted verified — 19 November 2026

Candidate activated as dynamic worker asset SHA f893d01a73feb876385ff2987c405a19d25ebecc5c3d1cd1bb62f28b3b03f458, no process reload. V1 historical400bar output SHA identical before/after. Hosted PAXG30m table-driven script exercises worker path and reports PASS for rounded equality and adjacent buckets. All999exportrows (including provisional row) have both expected1values:1998checks. Immutable export retained. Shared-view editor only; regular draft/preferences unchanged. Six comparison operators fixed; this does not establish all Pine semantics or external TradingView parity. Manifest: .private/chart-order-rollouts/pine-float-comparison-20261119/manifest.json.


### Independent volume studies and MFI boundary candidate — 19 November 2026

Decimal50 reference covers OBV,ADL,VWMA,CMF,MFI,EFI,CHO at lengths1/14/20 on998PAXG/406FYERS completed broker bars plus50flat zero-volume bars. Baseline FYERS passes; PAXG MFI differs up to13.01points and four length1null states. Exact equal HLC3 at PAXG indices123/702 becomes tiny signed JS change; sliding sums leave zero-flow residual. Candidate rounds comparison operands9digits and sums current MFI window directly. Both datasets and synthetic cases pass all84indicator/parameter/dataset checks. NOT active pending regressions and hosted desktop/narrow/export verification. Manifest: .private/chart-order-rollouts/mfi-price-boundary-20261119/manifest.json.


### MFI correction activated and hosted verified — 19 November 2026

All56candle regressions pass with candidate. Seven maintained libraries now active mfi-boundary-4; pending catalog/Yahoo manifests require new library version. No process reload. Hosted PAXG30m MFI14 pane renders desktop/narrow; exported998completed bars match Decimal50 reference with984numeric/14warmup values and maxerror2.0114845342286004752291235313974805E-14. Shared view only, regular preferences untouched. Screenshots retained locally. Reports docs/chart-mfi-hosted-verification-20261119.json and rollout mfi-price-boundary-20261119/manifest.json. External TradingView feed/seeding parity not claimed.


### Fibonacci drawing attributes and quick-color discrepancy — 19 November 2026

Hosted shared PAXG30m Fib two-anchor creation verified. Full settings apply/reopen retains0/44/50/56/100levels,3px andboth extensions. Quick toolbar initially displaysblue2962ff while actual/default modalpurple8757d7. Candidate extracts common drawingStrokeColor used by quicktoolbar and modal; NOT active pending regressions, seven-source update/rebase and hosted desktop/narrow confirmation. Source fixture tests MFI observed binary-equality/expired-flow cases added;58candle tests pass. Manifest drawing-toolbar-effective-color-20261119/manifest.json; hosted attributes report docs/chart-fibonacci-attributes-hosted-20261119.json.


### Drawing toolbar effective colors active — 19 November 2026

JS1964 common drawingStrokeColor now serves quicktoolbar and full modal. Seven maintained static sources active,71focused regressions pass. Six pending catalog/Yahoo variants rebased1965/1966 with syntax and3color cases each; prior backend activation approvals remain pending. Hosted new Fib toolbar/modal purple8757d7 agree desktop; narrow same default andcustomaa2233 reflected afterApply/select. Shared view only, no regular preferences changed. No process reload. Full tool/attribute matrix and complete visual parity remain. Manifest drawing-toolbar-effective-color-20261119/manifest.json.


### Drawing manager keyboard dismissal — 19 November 2026

Document-level Escape handler excludes inputs; drawing manager lacked local handler, so search Escape left popup covering chart. JS1967 adds local Escape handling, honors composing/defaultPrevented events, closes only manager and focuses its main trigger. Seven static sources active, no service reload. Hosted desktop/narrow Escape closes, aria-expanded false, focus Manage drawings and Fib query retained onreopen.74focused tests pass including state/focus guards. Six pending variants rebased1968/1969 and syntax+6focused cases each pass. Shared view only; drawings/preferences untouched. Manifest drawing-manager-escape-20261119/manifest.json.


### Hosted drawing families and standalone Text formatting gap — 19 November 2026

Shared PAXG30m channel3anchors,rectangle2anchors,date/price range2anchors andText1anchor render visibly. Channel4px/both extensions persist on narrowreopen. Rectangle customgreen20%fill andtypedcaption render. Measurement displays24bars/12h,-39.1/-1.04%/-3910ticks/volume; arithmetic not independently audited. Text tool only color/content: rendererhardcodes13px600. Candidate adds1-200size,bold,italic fields,canvasfont,hitboundsandtype-defaultpersistence; legacydefaultretained. Threeactualcanvas-block tests pass. NOTactive pending fullregressions,deployment/rebaseandhosteddesktop/narrow. Evidence docs/chart-drawing-families-hosted-20261119.json;manifesttext-annotation-formatting-20261119/manifest.json.


### Standalone Text formatting activated — 19 November 2026

JS1970 active in7maintained sources. AddsTextsize1-200,bold,italic;existing13pxsemibold remainsdefault whenfieldsabsent. Rendererhitbounds followfontsize;styledefaults whitelist includesnewfields.77focused tests pass. Sixpendingcatalog/Yahoovariants rebased1971/1972 with syntax+9focusedcases each pass. HostedText28pxitalic/nonbold renders; narrowreopenpreservesfields;newTextinherits savedstyle. Sharedviewonly,no processreload. Screenshots chart-text-format-desktop.jpg andchart-text-format-settings-narrow.jpg retainedlocally. Manifesttext-annotation-formatting-20261119/manifest.json. Fullvisual/toolmatrix remainsincomplete.


### Live delay audit and cross-channel ordering candidate — 19 November 2026

HostedPAXG30mLive48s→Updatesdelayedafter60s; same-tabrecoveryNOTverified. Shortpublicsample sparse; longer80.90ssample receives14events across1m/5m/30m,12acceptedframe revisions with0.157-1.529s age. Twoequaltimestampduplicateframesunchanged. Brokerfeedreceivingdata; no freshnessrelaxation/restart. Syntheticadaptercase demonstratesvalid30mstamp1801arrivingafter1mstamp1802discardedbeforeitsframeexists. Candidateusesper-frameorderingandretainsmonotonicsymbolticks/callbacks.4candidate tests pass;active3guards+1pendingfixskip. NOTactive,noproductionadapterchanged; observedhosteddelaycausenotproven. Manifestdelta-chart-channel-order-20261119/manifest.json;reportdocs/chart-live-delay-audit-20261119.json. Noorders/runners/credentials touched.


### Hosted live HTTP interruption recovery — 19 November 2026

IsolatedsharedPAXG30mtabinitialLiveclose3724.7. CDPblockedonly exact selectedbroker liveURL;nextpollFeedunavailable. RemovedblockwithoutUIrefresh/reconnect;automaticHTTP200returned,Liveclose3728.1,lastbrokerupdate2sago. Blockremoved/tabclosed. ProductionWebSocket/runners/ordersuntouched. ProvesbrowserHTTPfailure/retryrecovery,NOTserver-sideconnected-but-stalledstreamrecovery. Crosschanneladaptercandidate remainsinactive. Evidence docs/chart-live-http-recovery-20261119.json; screenshotchart-live-recovery-resumed.jpg.


### Delta channel ordering owner sources staged — 19 November 2026

Candidateingestpasses54tests acrossordering,papercapital,privatebrokerroutes,runnerjobcontrolandchartworkspaceaccess. ExistingrouteharnessbaselineNameErrorRenkoChartBroker reproducedandfixedbyaddingmissingfake dependency; no productionroutechanged. ExactingestfragmentstagedinrootandDeltaownersources only;privateexecutionpreflight/countdifferencespreserved. NOreload/runtimeactivation. PendingDeltaactivationalsoincludesalready-stagedchartcatalogpermissionroute;latestfrontendremains1971catalog/1972Yahoo variants. Specificworkerreloadapprovalandfreshrunner/exposureguardsrequired. Manifestdelta-chart-channel-order-20261119/manifest.json.


### Five default indicator pane fit — 19 November 2026

HostedPAXG30m OBV/RSI/MFI/ATR/MACD baseline stage578scroll846desktop,537scroll676narrow. CSS311autopanes shrink72pxmin andprice160minwith4+panes:desktop578scroll578(5x82.4),narrow537scroll537(5x74.17),nooverflow. Manual90pxpreferredsurvivesviewportroundtrip;Home resetreturnsfit. Maximizefillsstage;keyboardRestoreworks. PointerRestore repeatedlyre-maximizes:OPENdefect,notclaimedfixed. Dockededitor5panesminimaexceed277pxstage(526pxscroll);CSS312scopes160priceflooroutofeditor,pendinghostedfollowup. SevenstaticCSSsourcesactive;pendingcandidateCSSrequirement312. NoJS/servicechange. Manifestmany-pane-fit-20261119/manifest.json.


### OHLC header stability resolves pointer Restore miss — 19 November 2026

Query-gatedclick/doubleclicktrace: semanticpointerRestoremissfiresNEITHERhandler;directpointeratnewbuttonpositionworks. Causeobservedheader22pxshiftwhenLivecandlebadgehiddenonhistoricalhover,notdoubleclickre-maximization. TemporaryJS1973tracefullyremoved,JS1970restored. CSS313intermediate reducedshiftto1.44px;CSS314 reserves2lineheights+8pxbadgeallowance in<=1100pxchartcontainers. HostednarrowLive/historicalquoteheight39.1059px,stagetop420.6511pxunchanged;pointerRestoreworks. DesktopRestoreworks;5paneclient/scroll578/578desktop535/535narrow. SevenCSSsourcesactive;pendingcandidatesrequire314. Explicitbottomeditorverifieddata-bottomtrueprice120pxnarrow;available215vs486mincontentmeansscrollnecessary. Prior160pxeditorcasewasresponsiveRIGHTdock,notexplicitbottom. NoJSchanges/service reload. Manifestohlc-header-stability-20261119/manifest.json. Fullflicker/viewport/fontmatrixnotproven.


### Momentum audit and CCI flat-window correction — 19 November 2026

IndependentDecimal50 StochasticK/D,WilliamsR,CCI,ROC,Momentum,CMO checks126cases across998PAXG/406FYERS andflat/impulsetail datasets atlength1/14/20. BaselineCCIonebarfalsevalues968PAXG/321FYERS;flatwindowtailalsofalse. Centered-window mean/deviation removescancellationwithout epsilon andpreservesactualsmallmoves. Sevenlibrariesactivecci-window-5;61focusedtests pass. HostedCloseCCI20export998completed:979numeric/19warmupmatch;CCI1all998nullcorrectlyshown no values,reset20recovers. Desktop/narrowinspected. Fullbroker/externalTVseed/feedparitynotclaimed. Manifestcci-flat-window-20261119/manifest.json;docs/chart-cci-hosted-verification-20261119.json.


### Pine CCI runtime consistency — 19 November 2026

Separateworker ta.cci returned0onzero deviation andusedunstablemean. Centeredwindow/NaNonzerodeviation candidate passes18cases2752numeric andexactnullmasks acrossPAXG/FYERS+flat/impulse;activeworkerSHA98d44b5edefc9e54453dfaf9b3eec7d74618c04940a3082769ea2f596930b48e. Sevenexistingfixturesandmetadatahistorypass;historicalV1400barpayloadsame. Hostedtable-feature scriptPineCCIparitycheckappliesandCCI20plotrendersdesktop/narrow. Export998completed:979CCI20numeric/19warmupmatchDecimal50,maxerror6.3966770508826583592938733125649013499E-11;CCI1all998null. Tabletextnotobserved withoverlay=false; placementunverifiedandneedsfollowup. Noreload,sharedviewonly. Manifestpine-cci-flat-window-20261119/manifest.json;docspine-cci-hosted-verification-20261119.json. ExternalTradingViewfeed/seedparitynotclaimed.


### Separate-pane Pine objects and table layout — 19 November 2026

WorkeremittedtablebutbrowserDOMabsent. renderlocalmanualdrawingsshadowedglobalPinekindarray,breakingneedsDrawingPane. JS1974distinctpineDrawingKindsandobject-onlypanecreationgatesactive7sources.90focusedregressionspass;sixpendingvariantsrebased1975/1976withsyntax+18focusedcaseseach. Hostedplot+tableandtable-onlyscriptsnowcreatecorrectseparatepane. Initialtablebody2.5pxclippedunder26pxheading;tablez3alsooverlappedpanecontrolsz5. CSS315moves top tablesbelowcontrols36px,z6,allocatespanebodyheight. Hostedcellclient/scroll14/14desktop/narrow;Expanddoesnotremovestudy,compact/collapse/reopenverified. Priorclickremovedsharedteststudywhencontrols overlapped;regularsavedstateuntouched. Remainingline/box/label-onlyandlivecellupdatesneedhostedmatrix. Manifestpine-pane-objects-20261119/manifest.json. No service reload.


### Pine pane drawing-only objects, live tables and cell CSS — 19 November 2026

Hostedoverlay=false,noplotcombinedscriptcreatesblue3pxline,greenbox,bluePANELABELandBrokerclosetableinownpane. Visuallyconfirmed;livecell3736.9→3736.5→3736.9withoutrefresh/reapply. Narrowobserved. NativechartCSSdescendanttdresetoverrodePinecellpadding0;CSS316restrictsresetto directnative layouttable. SevenCSSsourcesactive;Pinepadding1px4pxandblueborderpresentdesktop/narrow;nativepadding0andcanvasesrender. Pending1975/1976requireCSS316. NoJS/servicechange. Combinedcaseonly;individualvariants/forceoverlay/allchartpositionsremain. Manifestpine-pane-table-padding-20261119/manifest.json;docspine-pane-objects-live-hosted-20261119.json.


### 19 November 2026 — mixed Pine overlay destinations
Activated browser normalization of forced object streams across seven maintained frontends (JS1977). Fixed worker table position ownership to distinguish forced price tables from ordinary pane tables. Baseline loses one of two same-position tables; candidate passes both cross-pane preservation and same-pane replacement checks. CCI and metadata-history regressions pass. Hosted shared PAXGUSD 30m view displays the forced price line/label/table and ordinary RSI/table in its pane. Desktop and narrow verified; price table updates 3734.30 to 3734.20 without reapplication. Six staged frontend variants pass forced-overlay and pane-object tests. No service reload or trading action. Full TradingView parity remains incomplete.


### 19 November 2026 — open Pine table visual footprint
CSS317 active across seven maintained sources. Open tables show script cells without a duplicated first-cell title row at rest. Controls appear on hover or keyboard focus; collapsed tables remain visible; hover:none retains static controls. Hosted mixed price/pane fixture reduces each open table from43.49px to16.39px. Desktop/narrow and keyboard collapse/reopen/expand/compact verified. Script table padding, colors and borders unchanged. Physical touch acceptance remains; full parity goal incomplete.


### 19 November 2026 — Pine drawing-family chart-mode acceptance
Actual worker integration fixture validates ordinary/forced object counts for boxes, lines, linefills and closed polylines. Hosted isolated shared PAXGUSD30m view renders blue boxes, orange fills and purple triangles in correct price and RSI panes on Candles, Heikin Ashi, Renko ATR7 Close and Line. Narrow Line inspected. No production restart, runner/order action or regular chart-preference mutation. Curves, exhaustive geometry and all-broker matrix remain unverified. Evidence: .private/chart-order-rollouts/pine-drawing-family-audit-20261119/manifest.json.


### 19 November 2026 — manual pane resize transition verification
Hosted Delta shared view:304pxprice and144pxadjacentOBV retaindimensions through interval, symbol, chart-type and narrow/desktop transitions. Actualpointerdrag-30px creates274pxprice/174pxOBV and survives5m-to30m rebuild. Measuredheights within0.01px. Noresize reset reproduced; no code change justified. Ordinarysavedworkspace reload persistence and general flicker remain unproven. Evidence:docs/chart-resize-transitions-hosted-20261119.json.


### 19 November 2026 — V1 Heikin Ashi startup/rollover performance gap
Hosted shared ETHUSD5mHA V1 completesstartup after observation at26s, withoutmanualrestart/browsererror. Readyformingupdates changeSMA/OBV withoutrestart. At05:40IST boundary,Updating observed+18s andready+49s; this bounds observed behavior, not exactCPUduration. runChartPine formingTailOnly permits incremental evaluation only for same-length formingtail; appendedHAbar forcesfullreplay. Next:prove incrementalappended-tail parity beforechanginggate. No runtimefix orrestart. Evidence:docs/pine-heikin-rollover-performance-20261119.json.


### 19 November 2026 — mutable Pine rollback correction
Actual-worker incremental/full comparison exposed mutable Pine array/UDT state retaining previous-tick mutations and raw MTF parameter series not truncating during rollback. Snapshot graph preserves object/array identity and aliases; raw cached arrays now restore prior length/value. Candidate/active4scenario full-output parity passes, including nestedUDT/aliases, RSI/EMA, MTFtuple and nativeintrabar arrays. variparrays retainintrabarupdates; metadata,CCI,180comparisonchecks,drawingfamilies/tablespass. Baselinefailuresretained. Historical400barV1payload1130468bytes/SHAefdb6b8e37f4f329f631d43e3ee1e9fe700e9f9036850158e5574cdad9e5764f identical. HostedsharedETH5mHAclose1771.81→1771.35→1770.90, samples999, array/UDTmismatchall0; desktop/narrowverified. Staticworkeractivatedwithoutservice reload. HAappendfrontendgate remainsfullreplay; rolloverlatencyfixnotclaimed. Evidence:.private/chart-order-rollouts/pine-mutable-rollback-20261119/manifest.json.


### 19 November 2026 — HA incremental append gate and hosted limitation
JS1980active7maintainedsources;pendingcatalog/Yahoo rebased1981/1982withCSS317/librarycci-window-5. Active78tests and6pendingvariants20cases eachpass. FullV1fixedclockinitial/sametick/revisedtail+append/twoappend allnumeric anddrawing/table outputs matchfresh400/401/403bars. Benchmarkoneappend270.11msvs21460.15msfull;twoappend379.22msvs22778.31msfull. Initialunfixedclockobjectcomparisonwasinconclusivebecausefixtureextendedintocurrenttime; retainedseparateevidence. HostedETH5mHAstillUpdatingat+12s,readyat+42s;NOhostedlatencyimprovementclaim. Existingguard excludesfinalization-onlyandconfirmedpriorappend; investigatewithrealtimeclock. Actualfallbacknotinstrumented. No service/runner/order actions. Evidence:.private/chart-order-rollouts/heikin-incremental-tail-20261119/manifest.json.


### 19 November 2026 — HA confirmation gate and actual forced-reset evidence
JS1983active7sources,pending1984/1985;80activechecks,sixpendingvariants22cases each pass. ActualworkerfullV1sixrealtimeclockstates(400–404bars)numeric/drawings/tablesmatchfresh. Confirmation191ms/appendafterconfirmation217ms. Hostedtemporaryquery-onlytrace at00:40:06.721UTC captures reset=true,replay=true,999→1000bars,firstchangedindex998(oldtail);workerEND33103.8ms. Thusupstreamforcedresetoverridesgate. renderLiveRows resetsforconfirmationChanged/referenceChanged/olderprefixchanges; separatewhichconditionsbeforechanging. TraceconsolecapturedviaCUA;root/DeltaalltemporarybytesremovedandJS1983restored. No hostedlatencyfixclaim. Evidence:.private/chart-order-rollouts/heikin-confirmation-tail-20261119/manifest.json.


### 19 November 2026 — hosted Heikin Ashi confirmation replay resolved
JS1987active7sources;pending1988/1989preserveCSS317/librarycci-window-5. Callerconfirmation-onlyresetnowexemptsHA;referencehistory/olderOHLC/olderconfirmation/shrinkingwindowsstillreplay.88activechecks,sixpendingvariants30cases eachpass. FullV1real-time6stateparityfrompriorrolloutretained. HostedETHUSD5mHA00:45UTCtrace:referenceChangedfalse,confirmationChangedtrue,olderChangedfalse;999barconfirmationreset/replayfalse3813.4ms;999→1000appendreset/replayfalse1157.4ms. Priorforcedfullreplay33103.8ms. ReadyUIdesktop/narrowverified. Alltemporaryquery-onlytracebytesremovedandroot/DeltaJS1987restored. No restart/runner/order actions. Broaderrollovermatrixandfullobjectiveincomplete. Evidence:.private/chart-order-rollouts/heikin-confirmation-reset-20261119/manifest.json.


### 19 November 2026 — V1 numeric plots restored after startup cohort race
HostedV1tables/drawingsworkedbutallnumericplotsexportedblank. NativeDelta30mfirstredaftercrypto02:30ISTreset:18Nov22:00UTChigh1767.45/low1762.10. Query-onlydiagnosticcapturescorrectworkerhigh1767.45andfiniteShakti;workerlimit998butlazysubmittedsnapshot999,firstpointindex0athostindex1timestamp. Strictsyntheticindexmappingdiscardedall. JS1994freezesinitialhostcohortandusesitscount.4delayedworkerHA/Renkoappend/trimcasesrejectbaseline;92activechecks,sixpending34eachpass. Hostedafterexport999bars:high/low945finite,nativeboundsmatch;Shakti999finite(last1766.0808748226),2mSMAhigh121finite. Beforeexportallthree0finite. Desktop/narrowvisualplots/valuesverified. Temporarypoint/requesttracefullyremoved;activeJS1994,pending1995/1996,CSS317/librarycci-window-5. No service/runner/order actions. Explicitcalc_bars_countpartialhistorymappingstillunverified. Evidence:.private/chart-order-rollouts/pine-host-snapshot-20261119/manifest.json.


### 19 November 2026 — calculation-history limit defect confirmed
100barPineworkerfixtureappliesinall4typesbutexportscalculateallloadedbars:1000Candles/Line/HA,209Renko. TradingViewdeclarationdocsdefineboundedinitialdataset,bar_index0andunavailableearlierhistory,Calculation/Calculatedbarsinput,andallsubsequentrealtimebars. Actualworkerregressionforliteral/arithmetic/namedconstant100fails;0/oversizedcontrolsretained. Standaloneprototypeusesactualcompiler/contextandinterceptsdeclarationafterresolvedarguments,beforebody:100/20*5/LIMITallresolve100,0resolves0. Noactivefix;boundedworkerwindowandcoordinate/drawingmappingplusinput/lifecyclemustbeimplementedtogether. Evidence:.private/chart-order-rollouts/pine-calculation-limit-20261119/manifest.json.


### 19 November 2026 — staged bounded Pine calculation implementation
Worker candidate (not active) probes actual compiled declaration before body, resolvesliteral/arithmetic/namedconstantlimits,validatesnonnegativeinteger,usesanchoredinitialhistorywindowandappendsallnewbars. SynthesizesCalculation/Calculatedbarsinputmetadataandoverride. Relativebar_indexvaluesremain0-based;serializedplotbarIndexanddrawingcoordinatesoffsettofullchartwithoutchangingPinevalues.7initial/overridecases,4lifecyclecasesand4Renko-duplicate-timecasespass;line/labelgeometryandolderhistoryanchorverified.6existingworkerregressionspass. Complete400barV1payload1108531bytesidenticalbaseline/candidate. FrontendcandidateaddsuniquechartTimemetadataforsyntheticanchors. Noactiveassetbyteschangedforthisfeature. Needcoordinatedfrontend/workeractivation,settingsinputand4typeexport/liverolloveracceptance. Evidence:.private/chart-order-rollouts/pine-calculation-limit-20261119/manifest.json.


### 19 November 2026 — bounded Pine history activated and hosted verified
Coordinatedworkerasset+JS1997active7sources,pending1998/1999,CSS317/librarycci-window-5.92activefrontendchecks/sixpending34eachpass. HostedETH5m4typeexports(Candles999,HA1000,Line1000,Renko197loaded)eachhave100calculatedcloses;allmatchappropriatebroker/HA/brickclose. Calculation/Calculatedbarsinputvisibledesktop/narrow;typed25exports25,typed0exportsall999,100restored. Initialprogrammaticfilldidnotnativecommitchange;actualtypedchanges26→25validated. ETH1mlive100→101withsamefirst18Nov23:43UTCandlast01:22→01:23UTC,demonstratinganchorretentionratherthanrollingreseeding. RawCSVsretained. Additionaldrawingfamilies,anchorloss/historytruncationandallbrokermatrixremain. No service/runner/order actions. Evidence:.private/chart-order-rollouts/pine-calculation-limit-20261119/manifest.json.


### 19 November 2026 — Pine text input and grouped settings presentation
JS2000(remainsinJS2003)removes80charPineinputmaxlength/saved-valuefallback;non-Pineboundedcontractsretained.4regressionscoverlongsaved/defaultstringsandattributeescaping. Hosted501charvalueproducesstr.length501,persistsclose/reopen,andmaxlengthabsent;desktop/narrowverified. Sequentialtypingtooltimedoutat74characters;subsequent500charfill+nativekeyedit+Tabcommitted501andactualscriptverifiedit. CSS318groupsfullwidth,restrainedtoprule/mutedlegend;desktopText/Calculationclient=scroll551,narrowinput148pxfits. JS2003accuratelylabelsfullproviderwindowCharthistory999besideCalculatedbars100.96focusedtests,andlatest6pendingvariantslonginputtestsPass;latestpending2004/2005,CSS318/librarycci-window-5. No service/runner/order actions. Broadlarge/specializedgroupmatrixremains.


### 19 November 2026 — bounded drawing geometry coverage
New actualworker verifier checks5families(line/box/label/linefill/polyline),ordinary/forced,bar_index/time acrossCandles/HA/Renkoinitialandolderhistoryprepend. Offset150→200with100calculatedbars/localindices0→99;timeanchorsunchanged;Renko duplicatesincluded. Hostedboundedfixtureall4typesblueboxes/orangefills/purpleclosedpolylinesrendercorrectprice/RSIpane;narrowLineinspected. No runtimechangejustified. Curves/fullinput/allbrokermatrixremain. Evidence:docs/pine-bounded-drawing-geometry-20261119.json.


### 19 November 2026 — bounded Renko reconstruction recovery
NormalreconcileHistorymergesexistingbrokerhistory;structuralRenkorebuildcanremovevirtualbrickanchorwhilebrokercandlesremain. Baselineactualworkerreproducescalculationstartunavailable. WorkerrestartCalculationprotocol+JS2006confirmedbrick-basischeckstartsnewboundedwindowforreconstruction;stableappends/projectedtailsretainanchorwherevalid. MissingRenkoanchorrecoversfromrebuiltchart;non-Renkomissinganchorstillerrors.8policycases(includingNaNvolume),4actualworkerlife,10workerregressionprograms,104frontchecksand6pending46eachpass. HostedETH5mATR7→Traditional5→Traditional2.5exports146/182/558bricks,exact100calculatedclosesallmatchsourcebricks;desktop/narrowready. Staticassetsactive,no service/runner/order action. Pending2007/2008,CSS318/librarycci-window-5. Evidence:.private/chart-order-rollouts/pine-renko-window-rebuild-20261119/manifest.json.


### 2026-11-19 — Dhan Pine catalog identity and fresh session verification

JS2009 active across seven maintained chart sources; six pending variants rebased to2010/2011. Pine receives catalog trading symbol and instrument type, while tickerid remains the native broker ID. Selected-host catalog aliases route back to the native ID for ticker.new/request.security. Thirty-nine focused frontend cases and six pending variants with seventeen cases each passed. Fresh hosted Dhan Subhalaxmi HDFCBANK30m rendered ticker HDFCBANK, type stock, native ID NSE_EQ:1333, and successful 60m reference close806.4. Desktop table compact; narrow table auto-collapsed. Derivative hosted rendering remains unverified. Read-only broker profile confirms Subhalaxmi valid/Active data plan, Pinaki rejected token. Previous statement that both accounts required reconnection was incorrect: changing the source select without submitting leaves the previous source active. No restart, runner, credentials, or order mutation. Evidence: .private/chart-order-rollouts/dhan-pine-metadata-20261119/manifest.json.


### 2026-11-19 — Hosted Dhan option and futures Pine verification

Fresh Subhalaxmi GOLD MCX_COMM:495213 30m: ticker GOLD-04Dec2026-FUT, type futures; ticker.new/request.security native60m close129880 equals latest chart close. NIFTY put NSE_FNO:64440: ticker NIFTY-Nov2026-25000-PE, type option; native60m close71.8. Option study calculation/rendering completed on Candles, Line, Heikin Ashi and Renko; narrow chart retained table auto-collapse. Hovered historical values differ from latest labels by design; no independent math parity asserted. No trade, runner, credentials, or reload action. Remaining: full catalog and broker/timeframe/live matrix, plus full feature acceptance. Evidence added to Dhan Pine metadata rollout manifest.


### 2026-11-19 — Full Sector Pulse V1 Dhan native-reference regression

Full109027-character V1 failed on Dhan option with cross-symbol equity restriction after catalog metadata update. Root cause: Pine strips the native exchange for some same-symbol security/lower_tf calls and emits bare numeric security ID; the new human ticker alias did not include it. JS2012 restores only the selected host security-ID alias to its broker-native ID. Seven maintained sources active; six pending variants rebased2013/2014. Thirty-nine targeted cases and six pending variants passed. Hosted full V1 now applies on Dhan Subhalaxmi NSE_FNO:64440 30m: locked64.85/56.60,2m SMA78.95/73.52,30mSMA75.06; zones/labels/compact research and SC tables rendered. Narrow tables automatically collapsed. No restart or trading mutation. Independent cross-market parity and full acceptance remain incomplete. Evidence: .private/chart-order-rollouts/dhan-pine-native-reference-20261119/manifest.json.


### 2026-11-19 — Full Dhan chart-catalog membership audit

Current broker master227019rows; independent published-segment membership set178675unique current IDs exactly equals chart search output: no missing/extra IDs. NSE_FNO92824,BSE_FNO45211,NSE_EQ10094,BSE_EQ13675,MCX_COMM16680,IDX_I190,NSE_CURRENCY1; other mapped currency groups contain no current rows.24162expired derivative rows excluded. Remaining unsupported/unverified mappings:24178NSE M commodity rows and4NSE G rows. Native NSE_COMM quote probe success/empty data; selected intraday probe rejected non-auth instrument/segment/permission. No guessed mapping activated. New repeatable read-only audit scripts/audit_dhan_chart_catalog.py; artifact .private/chart-order-rollouts/dhan-catalog-coverage-20261119/audit.json. This proves catalog membership across documented mappings, not full-universe data entitlement, hosted pagination, or complete broker support.


### 2026-11-19 — Dhan weekly/monthly/annual broker-data parity

Read-only HDFCBANK NSE_EQ:1333 broker daily capture1154bars. Independent calendar grouping matched all returned completed OHLCV:242weekly,55monthly,3annual candles; zero differences. Hosted1W/1M/12M loaded on Subhalaxmi. Annual older-history UI loaded4older candles and reached01Jan2019; current annual forming993.50/1006.40/669.20/808.15 matches latest native daily18Nov close808.15. Last intraday14:45close806.40 is not the full daily endpoint and is not a daily parity oracle. Script scripts/verify_dhan_calendar_parity.py; evidence .private/chart-order-rollouts/dhan-calendar-parity-20261119/result.json and native-daily.json. Selected-symbol verification only; all-symbol calendar/live coverage remains incomplete. NSE_COMM public instrument endpoint404; no unsupported mapping activated.


### 2026-11-19 — Dhan custom-hour missing native tail

HDFCBANK6h returns31completed candles;14h/22h/23h fail complete-history check. Native15minute data ends15:00. Candidate selecting25minute bars for session-sized intervals returned31bars and matched native aggregate, but independent native1minute audit ends18Nov15:14. Final25minute15:05bar has only10observed minutes, so candidate would disguise missing15:15–15:29. Rejected and NOT staged into active/owner sources; no reload. Evidence .private/chart-order-rollouts/dhan-custom-hours-20261119/manifest.json, native1/15/25data preserved. This is selected broker data incompleteness; allcustomhours support onDhan remains unresolved. Do not substitute daily OHLC silently or label the candidate a verified fix.


### 2026-11-19 — Dhan chart catalog display names

JS2015 replaces numeric broker-ID labels in chart ticker/title/toolbar with hydrated Dhan catalog trading symbols. Description mode remains respected; hover retains native ID; unresolved names fall back to ID. Catalog description used separately. Seven maintained chart sources active; six pending variants rebased2016/2017.18focused active cases and6pending variants22cases each passed. Hosted Subhalaxmi HDFCBANK/HDFC Bank desktop and520px verified; long NIFTY-Nov2026-25000-PE fits narrow toolbar/title. Native routing/Pine metadata retained. No restart or trading mutation. Evidence .private/chart-order-rollouts/dhan-chart-display-name-20261119/manifest.json. Full visual parity remains incomplete.


### 2026-11-19 — Broker history tooltip and footer menu layering

JS2021 adds latest completed broker candle opening timestamp/interval to feed badge hover, separate from last socket update. Existing details-panel history summary preserved without duplicate prose. Empty/projected-only history invents no timestamp. CSS319 raises open footer layout menu above floating drawing favorites; corrected overlap observed in hosted feed/timezone menu. Seven chart sources active; pending variants2022/2023 requireCSS319.20targeted active cases and6pending variants16cases passed. Hosted DhanHDFCBANK30m tooltip18Nov14:45, socket connected/no update outsidehours; desktop and520pxdetails unobstructed. Evidence .private/chart-order-rollouts/chart-history-tooltip-20261119/manifest.json. No backend reload or trading action. Missing native session data remains unresolved.


### 2026-11-19 — Hosted drawing attributes and Mac favorite shortcut

Isolated DeltaETH30m trendline: red#e53935,4px,dashed,both-sideextension matched toolbar, DrawingSettings and visible line. Favorite slot5 activated with focused OptionShiftDigit5 and first-anchor instruction.520pxsettings scrollable; Apply/Cancel footer visible. Native CUA shortcut attempt alone didnot prove activation; focused PlaywrightphysicalDigit5 did. Testdrawingremoved andfavoriteunstarred restoring4previousslots. No production source changes or trading action. Evidence docs/chart-drawing-attributes-hosted-20261119.json. Acceptance artifact refreshed with latest scoped Dhan/catalog/Pine/calendar/visual evidence;13groups remainpartial andfullgoalnotproven.


### 2026-11-19 — Ray/channel attributes and offset formatting

Hosted isolated DeltaETH30m horizontalray green3pxdotted,left-only extension verified against modal/toolbar/render. Mac OptionShiftDigit3 selectsfavoriteParallelchannel;3anchorsplaced,4pxboundaries/centerline/bothsideextensionsrender. Channeloffset raw18.73172073364276 exposed excessive precision. JS2024formats18.73while reader preserves original until input event.6helpertests cover positive/negative/tick values, explicit rounded-value edit and invalid emptyedit;26active tests and6pending variants22cases passed. Seven sources active; pending2025/2026requireCSS319.520pxstylemodal fits. Channeltestremoved; discardedsharedviewray nevercopiedregular. Evidence .private/chart-order-rollouts/channel-offset-display-20261119/manifest.json. Otherdrawingnumericfields/full89toolmatrix remainunverified.


### 2026-11-19 — Drawing coordinate price display

JS2027 applies two-decimal display and edit-aware full-precision readers to all anchor price fields generated by DrawingSettings, coveringStart/End/Third,curveControls andpatternVertices. Unedited original values preserved; actual input event commits editedvalue.32targeted activecases and6pendingvariants28cases passed; pending2028/2029requireCSS319. Hosted DhanHDFCBANKchannelStart788.43/End800.27 desktopand520pxverified. Width-onlyApplysucceeds; explicitEnd801.25 reopens801.25. Testchannelremoved, No drawings confirmed. Othernumericfields/fulltoolmatrix incomplete. Evidence .private/chart-order-rollouts/drawing-coordinate-display-20261119/manifest.json. No broker/runner/reload mutation.


### 2026-11-19 — Broad current/pending frontend regression and indicator style check

Thirty chartfrontend testfiles:218cases,214pass,0fail,4skip onactiveJS2027andall6pendingvariants.4skipsareYahoo snapshot helper tests gatedbyseparatecandidateenvironment; explicitlyexecuted4/4passwith0skiponeach4Yahoo variants. SevenmaintainedindexassetsverifiedJS2027/CSS319andSHAprovenancerecorded. Hosted isolatedDeltaETH30m SMA perplotblue4px rendered; V1LOCKEDHIGH perplotpurple2px controls verified with520pxStylepanel. No savedregularstylesmodified. Evidence .private/chart-order-rollouts/chart-regression-20261119/manifest.json and TAPlogs. Doesnotprovesubstantiveall129indicator/drawingmathorfullTradingViewparity.


### 2026-11-19 — Full V1 revision persistence and responsive Script menu

Saved109027characterV1asSectorPulseV1inDhanSubhalaxmi browserDraftrevisions; freshreload/Openrevision exactlyequals source. Sharedviewdraftitselfisephemeral; browserrevisionspersist. DefaultEMA20draftpreservedbyexistingrevisionflow. No explicitscriptcharcapfoundininspectededitor/savepath; quota/memorylimitsstillapply. NarrowbottomeditorScriptmenuextendedbelowviewport, hidingrevisionactions. CSS320boundsallScriptmenusandopensbottomeditormenuupward; sevenmaintainedsourcesactive, pendingJS2028/2029requireCSS320. Desktopmenu131.10–769.79;520x900menu146.31–785fits;520x600menu16.01–538.33scrolls521/638, Openrevisionreachableandexactsourceverified. Evidence .private/chart-order-rollouts/pine-script-menu-fit-20261119/manifest.json. No backendreloadortradingmutation. Fullgoalremainsincomplete.


### 2026-11-19 — Delta option Pine instrument type

JS2030usescurrentDelta catalog contract_type to pass option forcall_options/put_options/move_options; spot/perpetual retaincrypto. Previouslyallreportedcrypto. Sevenmaintainedsourcesactive; pending2031/2032requireCSS320. Broadactive225cases:221pass0fail4stagedYahooskips; sixpendingvariants0fail, fourYahoo225/225andtwoCatalog221pass4expectedskip. HostedC-ETH-1900-201126typeoption/close2; MV-BTC-64600-191126typeoption/close1794; ETHUSDcontroltypecrypto/liveupdates. Narrowcompacttableandpanesverified. UserregularV1notreplaced: isolatedsharedviewdiagnostic only. No reloadortradingmutation. Evidence .private/chart-order-rollouts/delta-pine-option-type-20261119/manifest.json. Fullscope remainsunproven.


### 2026-11-19 — FYERS futures Pine metadata and hosted session block

JS2033classifies nativeFYERSFUTsuffix asfutures ratherthanstock; index/options/equityunchanged. MCXmasterconfirmsGOLDM26DECFUTinstrument30. Eightmetadata testscoverMCX/NSE/BSE/currencyfutures,CE/PE,index,equity. ActualPineworkerreplay4types40barseachpasses; syntheticdataonly. Broadactive233cases229pass0fail4expectedYahooskips; all6pendingvariants0fail,fourYahoo233/233. Sevenmaintainedstaticsourcesupdated; pending2034/2035requireCSS320. FreshhostedGOLDMchartrequestsReconnectFYERS, sohostedmetadata/dataverificationNOTcomplete. No credentials/restart/tradingmutation. Evidence .private/chart-order-rollouts/fyers-pine-futures-type-20261119/manifest.json. Needfreshhostedvalidationafterconnectionrestored; fullgoalremainsactive.


### 2026-11-19 — Pine worker fallback and exact parser error navigation

JS2036recognizesworkertranspileratline:columnsyntaxforGotoline; runtimeerrorswithoutlocationremainunlinked. Hostedtestthenexposedvalidarray-onlyscriptrejectedbyfrontendLine3legacyerrorbecauseworkerfeaturewhitelistmissedarrays. JS2039allowdeclaredPine5/6indicatorsfallbacktofullworkerafterlegacyrejection; simplelegacy-successpathunchanged. Sevenmaintainedsourcesactive; pending2040/2041requireCSS320. Broad249cases:active245pass0fail4Yahooskips,all6pending0failfourYahoo249/249. HostedDhanHDFCBANKarray-onlyscriptapplies; badupdateUnexpectedEOF6:11retainsWorkingclose806.4/EMA809.47; Gotoline6selectsexactplot(close; correctedretryapplies. runtime.errorprobeproducesExpectedrecoveryprobe,0jumpbuttons,previousstudyretained,repairapplies. Desktop/narrowchecked. Temporaryworkererror-propertyinspectionexecutedVMcopyonly,neveractiveworker. FullPinebuiltin/strategy/externalrequestparitynotproven. Evidence .private/chart-order-rollouts/pine-worker-fallback-20261119/manifest.json.


### 2026-11-19 — Yahoo Pine native instrument metadata staged

YahoohistoryadapteralreadyreadsproviderinstrumentTypebutcapabilitiesdiscardedit. RootPythonstagedsourceaddsfield; sixpendingfrontendvariantsmapEQUITYstock,ETF/MUTUALFUNDfund,INDEXindex,CURRENCYforex,FUTUREfutures,CRYPTOCURRENCYcrypto,OPTIONoption; unknownstockfallback. ActiveJS2039unchanged. NativecapabilityrequestsverifiedAAPL/EQUITY,^NSEI/INDEX,EURUSD=X/CURRENCY,GC=F/FUTURE,BTC-USD/CRYPTOCURRENCYwithproviderzones. Backendmetadata1test9subcasesand8existingsnapshottests pass. Pending260cases:fourYahoo260pass0skip,twoCatalog256pass4expectedskip,all0fail. Freshhostedmaincapabilities^NSEIstillomitsinstrument_type, provingstagedcodeNOTloaded. Mainrestartapprovalalreadypending; no restartperformed. Newfrontendrebasemanifestsin.private/chart-order-rollouts/yahoo-pine-instrument-type-20261119; originalpendingbackendhash/pointersupdated. Catalog-onlyactivationdoesnotrequireYahoo metadata field. Evidence manifest/native-metadata/regressionJSON there. HostedPineYahoo-typeverificationremainsincomplete.


### 2026-11-19 — Fresh TradingView visual reference and compact Delta header

NativeTradingViewappdetectedrunningbutcapturefailed; separatebrowserreferenceBINANCE:ETHUSDT30musedread-onlyforheader/toolbarlayout. Referencehasdifferentfeedandstudies, notparityevidence. DeltaheaderpreviouslyrepeatedDelta/DeltaIndiaandlongsettlementdescription. JS2042showsETHUSD/Ethereum/30mDeltaIndia, retainingfullproviderdescriptioninhover; onlyknownperpetualdescriptionpatterncompacted,options/spot/unknowntextpreserved. Sevenmaintainedsourcesactive; pending2043/2044preserveYahooinstrumentmetadatastagingandCSS320. Broadactive256cases252pass0fail4expectedskip; pending267casesfourYahoo267pass,twoCatalog263pass4skip,0fail. Desktop/520pxhostedverified. Evidence .private/chart-order-rollouts/delta-compact-chart-header-20261119/manifest.json; screenshotsTradingViewreferenceandcompactheaderretainedlocally. Fullvisualparity/fullgoalremainincomplete.


### 2026-11-19 — Marked Entry/SL/TP read-only preview workflow

FreshisolatedDeltaETH30mBUYticketquantity1LIMIT1700entry1690stop1720target:RR2.00andnative-awarepreparepreviewdisplayintendedaccount/instrument/levels. Confirmunchecked,Placeentrydisabled; neverarmed/submitted. Showmarkedlevels plotsDRAFTlines. Entry1700.05invalidatespreviewandRR1.99. InvalidBUYTarget1680returnsBUYrequiresstop<entry<target;previewhidden.520pxpanel183.53–955fitswith770client/1217scroll. Ticketclosedhidden=true; nofinancialtransactionfromagent. Testticketmarkersnotriskpositiondrawingconversion. No trigger/fill/protectionlifecycle or otherbrokerexecutionverification. Evidence docs/chart-marked-order-preview-hosted-20261119.json. No source/service/runnerchanges.


### 2026-11-19 — Dismissible pending chart preview and late-response guard

Ticketv1ignoredClosewhileanybrokerrequestbusy. Ticketv2allowsclosingread-onlyprepare, invalidatesitsrequesttoken/revisionandletsnewdraftopen; oldcallbackcannotunlocknewpendingprevieworoverwriteit. Financialsubmission/status closeguardunchanged. Baseline3racefailuresreproduced; candidate27ticketcasespassincludingpendingfinancialsubmissionguard. Activefrontend260cases256pass0fail4stagedYahooskips. Root/Deltaassetsactivev2; FYERSmirrorupdatedbutnotincludedinitsindex, notactivated. ExistingJS2042/CSS320unchanged; pendingrebasemanifestsrequireticketv2. HostedDeltaETHclosewhileRefreshingstatusandEntrydisabled->hiddentrue;new1650/1640/1670drafteditable,R R2.00,reviewhidden/statusblankafterlaterresponse;520pxcheckedandticketclosed. NoConfirm/arm/order/restart/runneraction. Evidence .private/chart-order-rollouts/chart-preview-close-race-20261119/manifest.json.


### 2026-11-19 — Actual TradingView Delta feed comparison

Exported TradingView DELTAIN:ETHUSD.P30m300rows through native Download chart data UI; final forming row excluded. Hosted isolated sharedETHUSD30mCSV999rows,998completed:3992OHLC fields match fresh nativeDelta adapter/raw exactly.299completedTradingView overlap1196fields has5differences (4x0.05,1x0.40) across5candles. All5 native values repeat in narrow-window requests; no evidence of adapter transformation error. Hosted SMA5 compared on299overlapvalues maxerror recorded in report; sourceprice differences can propagate intoSMA. Preservebroker-source truth and do not fabricateTradingView prices. No private-engine parity claim. Export includes referenceprivate-study outputs but onlyOHLC/SMA5 compared. No charttype/indicator/layout setting changes expressly applied in referenceUI; URL usesmatchingDelta symbol withlogged-in savedlayout and may autosave symbolselection. Browserdownload wait timedout afterfilecompleted; localCSV andSHAverify. Evidence docs/chart-tradingview-delta-reference-20261119.json and private raw/exports. No service/runner/order actions.


### 2026-11-19 — Short viewport drawing menu and table controls

Isolated sharedDeltaETH30m at520x600requested(578x666DOM):Trendlines menu292client/594scroll overflowauto; lastHorizontal line OptionHreachable/activates thenCancel,nonewdrawing. InitialV1twoopentablesobscurechartbutbothhaveexplicit savedopenpreference(noautoattribute),notautocollapsefailure. Tablesbuttonhidesbothstacks(displaynone); chartstagefocusedOptionShiftKeyTtogglesfalse->true->false. Toolbarbuttonfocusdoesnottriggerstage-scopedshortcut; initialfailedprobeusedwrongfocus. Indicatorlegendcollapseworks. Userregularpreferencespreserved,viewportreset. No source/process/orderactions. Evidence docs/chart-responsive-tools-controls-20261119.json; localcompact screenshotretained. Fullgeometrymatrixnotverified.


### 2026-11-19 — Four chart-mode drawing availability matrix

FreshhostedDeltaETH30misolatedsharedview:Candles,Line,HeikinAshi91uniquetoolkinds all enabled(89drawings+eraser/zoom). RenkoTraditional5Closeexactly3disabled:GhostFeed,Sector,PositionForecast. SourceconfirmsintentionalrenkoDrawingKindsgate; removingaloneunsafe. forecastEndpointrejectsRenko; forecastlifecycleindexesrowswithplottedindices;Sector/forecast/ghosttimeorderingcannotdistinguishsamecandlebricks. Definedfuturebrickanchor/geometry/reconstructionrequirementsin docs/chart-drawing-mode-availability-20261119.json andacceptancepriority. No claimallenabledtoolscorrect; no codeactivation/reload/tradingmutation. Goalremainsincomplete.


### 2026-11-19 — Renko projected drawing anchor prototype

Privateanchorprototypeimplements geometry-matchedsource/brick resolution, futurebrickoffsetswithoutinventedfuturetimestamps, monotonicbidirectionalwaypointvalidation.10testcasespass:samecandle3bricks,zero/reversepathrejection,futureorigin,historyprepend,newbrickappend,reconstructioninsertion,removedgeometryfailclosed,nearestrepeatedgeometry,missingorigin,invalidinputs. CandidatefullJScontainshelpersbutnocalledintegration; nodecheckpasses. ActiveJS2042unchangedand3toolsremaindisabled. Fullrender/preview/drag/editorserialization/lifecycleall4modesstillrequired. Evidence .private/chart-order-rollouts/renko-projected-drawings-20261119/manifest.json. No service/runner/orderchanges.


### 2026-11-19 — Staged Renko forecast lifecycle integration

CandidatePositionForecast renderer nowuses completedplottedbricksforRenkoandsourcerowsforCandles. Extractedactualcandidatefunctions testedalongwithprivatehelpers:18casespass,including3000deterministiccandleoutcomesequivalencecomparisonsagainstoldvalid-historylogic. Samebrickentry/targettouchorderneverinferred;formingbricksdonotentry/hit/expire;outsideintervaltargetignored;futureendpointremainsPendinguntilcompleted. Counterexampleprovesusing2sourcerowsversus5brickswouldmisclassifyforecast. Placement/drag/serializationstillnotwiredand3toolsremaindisabled;JS2042activeunchanged. Evidence privateRenko projected drawingmanifest/candidate/verificationTAP. No restart/tradingactions.


### 2026-11-19 — Staged Renko future placement and waypoint integration

Privatecandidatewiresbrickfutureendpoint/anchorX/drawingLogical; new3familyrenderingresolvesbrickgeometryandrejectsmissingorigin. Ghostruntimeorderinguseslogicalbrickindicesforplacement/drag/paint; savedRenko pathsstructurallyvalidatedthenruntimeorderingcheckedagainstactualbricks. Sector/Forecastplacementandstyleorderingusebrickindicesinsteadofsametimestamps. Futuresdistinctfromsameoriginbrickacceptedwithoutfakefuturetimestamp.20casespass(including3000legacycandleforecastscenarios); actualcandidateextractionvalidatessamecandlepath,reversal,duplicate,removedgeometry,candlepathinvalidfirst. Gateunchanged,JS2042activeunchanged; markers/drag/fullfuturecoordinateediting/navigation/chartmodeconversionstillrequiresaudit/integrationandhostedverification. Evidence privateRenko projected drawingmanifest/integrationpatch/TAP. Notdeployed; no tradingaction.


### 2026-11-19 — Staged Renko drawing coordinate/selection/navigation integration

Candidateaddsbrick-numbercoordinatefieldsfornew3Renko drawingfamily,readonlyrealsourcetime,edit-awaregeometryretentionandexplicitrenkoAnchorAtIndexconversion. Selectionmarkers/translationusegeometryresolver;GoTousesallwaypointsandactualbrickbounds,missingoriginreportsconstructionunavailable. Fixedno-opguardwhichwoulddropeditbetweenequal-time/equal-pricebricks.28tests passincludingactualcandidatemarkup/JSDOM,coordinate-tabpreservation,save-identityguard,andprior3000candleequivalencecases. Crosschartmodefutureendpointmappingstillunsafe(nonRenkofallbackattachestoorigincandle); remainsrequiredand3toolsgated. ActiveJS2042hashunchanged. Evidence privateRenko projected drawingmanifest/candidate/verificationTAP. No restart/order/runnerchanges.


### 2026-11-19 — Staged cross-mode Renko projection mapping/editor

CandidateforecastDrawingLogical mapsRenko futurepointontotimechartasNplottedbarsfromknownsourcebucket; storedsourcetime/geometryunchanged. Originwithinbucketrequired; missingbucketfailclosed. Prependshiftsoriginindex,newbarsdonotdragendpoint;5m/10mchecked. NonRenkoeditorlabelsprojectionbarsandreadonlysource,edit-awareoffsetpreservesorigin,invalidoffsetrejected;no-opguardincludesoffset.33testspass(actualcandidateextraction/JSDOMplusprior3000candleequivalence); activeJS2042unchanged. ThisisprojectionsemanticsnotproofTradingViewmappingparity. CrossmodegesturethenreturnRenkoandsame-sourcewaypointcollapsehandlingstillpending;all3toolsgated. Evidence privateRenko projected drawingmanifest/candidate/verificationTAP. No broker/processmutation.


### 2026-11-19 — Broker-derived Renko anchor replay and ambiguity guard

Actualcandidatehelpersreplayed998capturednativeDeltaETH30mcandlesthroughcurrentRenkolibrary:Close/OHLCx5/10/25sizes6configs.2854completedprefixbricksunchangedonappend,533sampledanchors1599resolvechecks(initial/append/insertedolderbrickprefix)pass.18futureanchorresolvechecksand6same-sourcebidirectionaltriplets pass;533anchorsunresolvedwhenboxsizedoublesratherthanattachwronggeometry. ThisisanchorcontinuitynotindependentRenko numericalparity. Addedrecordedsourcebrickcount/geometrycount:changedcountwithrepeatedgeometryfailclosed;uniquegeometrycanretainshiftedsourceposition. Actualplacement/dragfactoriesnowrecordcountsfornew3familyonly;legacyotherfactoriesunchanged.35tests passincludingnewambiguityandactualfactorychecks. Stagedcandidateonly,activeJS2042unchangedand3toolsgated. Evidence privateRenko projected drawingmanifest/broker-replayJSON/verificationTAP. Fullcrossmodegestures/hostedactivationstillpending.


### 2026-11-19 — Staged candle-origin return to Renko

CandidateRenkoresolveracceptsnativecandleloaded/futureanchorformatsusingknownbroker sourceTimesnotserialbricktime. A no-brickcandlewithinthe representedrange mapstonext representedsource, matchingexistingchartdrawinglogicalpolicy; outside-rangeoriginremainsunresolved. CalendarfutureoffsetbecomesplottedbrickdistancefromoriginonRenko. Futurealiaswrapper/drawingLogical/anchorXusecorrectresolver. RenkoeditorreadonlysourceformatsnativeforecastOriginnottimechartcomputedfuturedate.37casespassincludingactualformattercallsandcrossmodeanchormapping;6brokerreplayconfigsstillpass. Fullpointergesture/waypointcollapse/broadregression/hostedvalidationremain;3toolsgatedandactiveJS2042unchanged. Evidence privateRenko projected drawingmanifest/candidate/verificationTAP/broker-replayJSON. No restart/tradingactions.


### 2026-11-19 — Staged same-source fractional rendering and hosted rollback

Candidateadds sourceInterval-awarefractional timechartcoordinates forsame-sourceRenkoanchors, GhostFeedfractionalsegmentpaint/hit-tests(integerbehaviorretained), andexplicitforecast Bricksequence/viewRenkodisclosurewhenentry/targetshareone sourcecandle. Settingsordering/Gotoalsofraction-aware. Oneexactfloatingtestexpectation5/6changedtotolerance1e-12; calculationprecisionunchanged.41focusedcasespass; sandboxcandidatebroad35files260cases256pass0fail4expectedstagedYahooskips. Candidateenablesall3Renkotools. TemporarymainstaticJS2045activated(no processreload); freshisolatedURLDeltaETHUSD30mRenkoinitialDOMall91toolkindsenabled,removed3studiesinsharedview. Nativecoordinateclicksdidnotconfirmfirstanchor. ScreenshotthenDOMshowedFYERSNIFTYLine/CandleswhileURLstillDeltaETHUSD/Renko;browser-target/app-sourcecauseunresolved. Stoppedcoordinateclicks;visibilitycapabilityunavailable,documentedCDPbringToFrontdidnotresolve mismatch. No drawn-objectsuccessclaimed. RestoredmainstaticJS2042andindex,baselinehashverified;other6sourcesneveractivated. Candidate/brokerreplayretained. Full41testsand6brokerconfigsscope remainsnonhostedgeometryproof. Evidence privateRenko projected drawingmanifest/TAP/brokerreplay. No service/runner/orderactions.


### 2026-11-19 — Renko three-tool static activation and authenticated delivery

FreshCUAsessionwithoutnativegetTabwrapper restoredmatchingURL/DOM/screenshotDeltaETH30mRenko. Documentedtab-scopedCDPmouseeventsplaceGhostFeed2anchors,Sector3anchors,PositionForecast2anchors;allrender. GhostEnd595/1825saved/reopened. Forecasthistoricalmissedthenfuture640/1830Pending;GoTolocatesandfuturehandlemoves634/1823.04confirmed. Drawingsretain/renderthroughCandles,Line,HA,Renkoreturn.520x900requestedsettingsrect58.89..518.89x213.70..786.30fits578x1000DOM,Applybottom775.75. Removed3testdrawingsonlysharedview;inheritedhorizontal1911.7060070940556and1992.057458714744retained,viewportreset. Noorders/runner/processreload. MainJS2045verifiedthen7sourcecopiespatched36unique-contexthunks;8uniqueactive/pendingvariants301testseach0fail(active/catalog4expectedYahooskips,Yahoo0). Pendingcatalog2046/Yahoo2047rebasepreservesCSS320,ticketv2,cci-window-5andYahoo/backendstaging;28pendingnodeshashverified. AuthenticatednormalpageNetworkresponsesbodiesmain+Delta+FYERS+MO+DhanPinaki+DhanSuballhashmatchnewcode. DhanAlgoproxy403correctownerboundary;sourcehashverifiedbutowner-sessionruntimeunverified. Unauthenticatedlocalhost401/403expected;directJSnavigationclientblocked;usednormallyloadedHTTP200scriptresponses(noauthbypass). SomeworkersretainHTMLquerytag1718butbodyhashmatchesnewcontent. Evidence privateRenko projected drawingmanifest/hostedJSON/served-authenticatedJSON/propagationregression/served-assetsJSON. Full89tool/allbroker/allusergeometry,Shiftwaypoint/Sectorstyle andcrossmodeactualdragremainpartial. Earlierrollbacksupersededbythisverifiedactivation;fullgoalnotcomplete.


### 2026-11-19 — Hosted Ghost Shift-waypoint and Sector attributes follow-up

FreshisolatedDeltaETH30mRenkoTraditional5CloseShiftmiddleanchorcreatesvisibleGhostFeedup/downwaypointpath;promptsfirst/Shiftanother/finalDrawingaddedverified. Sector3anchorsrender;red#e53935,4px,dashed,customgreen#00897bfill20%matchesrenderandreopenedfields;save-defaultunchecked. Sectorradiusdragdidnotregisterandfirstattemptpannedview;lateractiveintervalchanged30m->1mwithoutrequestedintervalactionwhileURLstill30. DOMandtab-scopedCDPscreenshotagree1m,causenotestablished. Askeduserwhetherconcurrentchartinteraction;answerpending. SourceReviewrefreshSavedDrawingsskipsSharedviewandcopiesonlydrawingfields,notinterval. No speculativesourcefix. Stoppeddragacceptance;cleanupremoved2testshapesbykeyboard,inherited2horizontalsretained. JS2045unchanged/all7sourceactivationretained;noorders/runner/servicechanges. Evidence privateRenko projected drawinghosted-followupJSONandscreenshots. Fullgoalremainsincomplete.

### 19 November — DMI decimal comparison correction

Equal decimal upward/downward moves no longer create a directional trend through binary rounding. Comparison operands use nine fractional digits; unrounded movement magnitudes are retained. Seven maintained static libraries and cache references updated to dmi-comparison-6, without process reload. Independent Decimal50 audit: 518 cases, 261328 numeric and 6640 unavailable-value checks, zero mismatches at 1e-8 tolerance. Covers DMI/ADX, Keltner and Donchian with captured broker and boundary fixtures; external TradingView parity and zero-range seed behavior remain unproven. Hosted Delta ETHUSD 30m DMI renders three finite plots; temporary study removed. Served-library body hash and browser equal-move boundary verification remain outstanding. Evidence: .private/chart-order-rollouts/dmi-channel-reference-20261119/activation.json.

### 19 November — full Pine DMI calculation consistency

The full Pine worker had the same decimal tie defect in ta.dmi: captured broker candle121 at DI length1 produced +DI10.5263157895 instead of0. Candidate fixes only comparison operands, retaining raw movement magnitudes. Actual worker parity:25 dataset/configuration cases,17191 numeric values and569 unavailable values; max error below5e-11 versus the independently validated built-in. Additional regression checks:180 Pine float comparisons,9 CCI and8 Supertrend configurations passed. Shared static worker updated without service reload; SHA958930fe6aec21aa1ab0745f26378f86fbebea97bdc11579b584ffccf999b4e2. Hosted authenticated Delta normal page delivered corrected study library with exact SHA5af349161f380bbfd2961ab9cb9a7283b52d87f8e73b53555ddaf95fb5452a13. Full worker download checksum and browser boundary computation still unverified; no broad runtime parity claim. Evidence: .private/chart-order-rollouts/dmi-channel-reference-20261119/worker-activation.json.

### 19 November — hosted full Pine DMI export validation

Actual hosted main chart selected Delta ETHUSD30m. New temporary v6 script includes an array declaration to exercise the full Pine worker and plots ta.dmi(1,1). Add to chart completed, three lines rendered. Native CSV export999rows:2991 completed numeric values and3 unavailable values match independently Decimal-validated built-in calculation, maximum error4.99e-11, zero mismatches. Temporary study removed and original109027-character V1 editor draft restored exactly through visible editor controls. No broker orders, runner or service mutations. Evidence: .private/chart-order-rollouts/dmi-channel-reference-20261119/hosted-pine-report.json. This proves this Pine workflow and dataset, not arbitrary Pine/external TradingView parity.

### 19 November — Sector handle drag viewport defect reproduced

Renko ETHUSD30m Traditional5Close shared view. Pointer hover exposes all three Sector handles; radius drag commits EndBrick601 while origin567/third593 remain. The chart subsequently jumps from Nov16-19 to Nov3-7 with same interval/construction. Reproduced user-visible defect; root cause not established and no speculative source patch applied. First clicks without prior pointermove were insufficient to expose handles and are not valid failure evidence. Temporary Sector removed. Investigation evidence: .private/chart-order-rollouts/renko-projected-drawings-20261119/hosted-sector-drag-issue.json.

### 19 November — Renko drawing viewport jump fixed

Temporary hosted range logging proved an unpaired stale anchor {index998,latest:true} survived initial616-brick rebuild without settings.range. A subsequent Go-to range caused this candle-axis anchor to shift the Renko viewport backward383 slots. Queued anchors are now consumed after every rebuild, even without a saved range. Baseline fails two behavioral regressions; fixed candidate passes all three including valid appended-brick follow. Main hosted ETHUSD30mTraditional5Close repeated three-anchor Sector create, Go-to, radius drag: EndBrick599 persisted and viewport remainsNov16-19, instead of jumpingNov3-7. Temporary Sector removed; temporary logs removed. JS2048 propagated seven maintained sources and six inactive catalog/Yahoo variants rebased to2049/2050. Eight unique variants pass focused viewport/drawing/coordinate/construction regression suite. Other-owner runtime, narrow/cross-mode gestures remain unverified. No services, runners or orders changed. Evidence: .private/chart-order-rollouts/sector-viewport-trace-20261119/manifest.json.

### 19 November — narrow Sector drag and cross-mode gap

Requested600x900 viewport (actual chart width624.67). Renko Sector radius401→460CSSpx drag commits and preservesNov16-19 view underJS2048. Converted same drawing toCandles thenLine: manager retains object, Go-to saysDrawing located, but shape not visibly rendered; verified both narrow and desktop. No console errors. Stored visible source coordinates17Nov14:00→19Nov05:00 withthird18Nov21:30IST; origin1841.54/third1861.11. Root cause remains unproven; no speculative patch. Temporary drawing removed, viewport override reset. This contradicts broad earlier cross-mode rendering claims and requires investigation. Evidence: .private/chart-order-rollouts/sector-viewport-trace-20261119/responsive-cross-mode.json.

### 19 November — Sector conversion diagnosis and held-open transient gap

Temporary root-only projection logging captured valid fractional candle coordinates after confirmed narrow radius drag: Renko550/603/591 maps candle892/979.5/968.5. ActualCandles/Line/HeikinAshi render the shape, narrow and desktop inspected. Earlier disappearance was not reproduced; no geometry source fix claimed or applied. Several pointer attempts missed handles and did not commit; only explicitDrawing anchor moved accepted. SourceJS2048 andindex restored byte-for-byte after temporary logging; test drawing removed andviewport reset. Prior negative conversion observation remains open pending reproduction, while these selected transitions are verified. Evidence: .private/chart-order-rollouts/sector-projection-trace-20261119/manifest.json.

### 19 November — Motilal native Pine metadata

Found token-only syminfo.ticker caused Motilal futures/options to fall through asstock. JS2051 caches native catalog name/exchange/instrument, hydrates exact selected ID within its own segment, classifiesOPT/FUT types, and aliases only the selected native ID (including canonical NSE/BSE prefixes). Preserves native tickerid/request routing; rejects mismatched exchanges and late symbol-change responses. LegacyNIFTY remainsindex. Seven static sources updated,58focused metadata/viewport/drawing cases pass for8unique active/pending variants. Pendingcatalog/Yahoo variants retained as2052/2053. Cached17Nov master audit:191989unique symbols across7segments;191849unambiguous types and383978selected-symbol aliases checked. 140COM/UNDIRC/UNDCUR type semantics unresolved; persisted index masters absent. No claim of fresh catalog/history/live completeness. HostedMO:MCX:495213 GOLD04Dec2026 stillrequestsreconnect, so native runtime acceptance pending. Separately identified Motilal catalog tick size is nothydrated into chartTickSize; not changed here. No process/runner/order changes. Evidence: .private/chart-order-rollouts/motilal-pine-metadata-20261119/manifest.json.

### 19 November — Motilal native chart and Pine tick size

JS2054 retains each validated native catalog tick in the instrument metadata and catalogTickSize reads only the selected Motilal identity. No quantity, order values, or explicit manual brick sizes changed. All191989cached native tick values reach worker metadata exactly; includes currencyincrements0.0025/0.0001 andcommodityticks1/2/5/10. Invalid/absent/non-numeric ticks rejected; another symbol cannot inherit the tick. ActualRenkoATR/percentage helpers use native tick in focused fixture, rawcandleprices/manualsize preserved. 62focused regressions pass across8unique active/pending variants; fullPine worker exactmintick at5tick configurations/15points. Sevenstaticowner sources updated, pendingcatalog/Yahoo versions2055/2056 retainchanges. Authenticated Motilal normalpageHTTP200JSbodySHA matches owner source d69dfa2e817064407e261275f70a12e0be14269eedbc5714b1008ba6a1f0bdd3. Broker session reconnect stillneeded; hostednativehistory/live/actualATRrollover unverified. Evidence: .private/chart-order-rollouts/motilal-chart-tick-20261119/manifest.json.

### 19 November — Motilal normalized native Pine reference routing

Full-worker probe exposed a gap introduced by native human-name metadata: ticker.standard(MO:MCX:495213) requestsMCX:495213, andnativeBSEindex requestsINDEX:BSE:1; frontend alias lookup lacked these stripped namespaces. JS2057 now resolves bare/qualified tokens andexactMO-strippedidentity only for selectedinstrument, plus knownlegacyNSE:NIFTY. Other token/exchange aliases stay unchanged. Full worker message path verifies24cases (6instrument/legacy classes x4chartType flags), each native andticker.new named5m request returns expectedconstantfixtureclose, type andtick. Uses synthetic candles; does not provebroker/session/brickmath parity. 64focused regressions pass across8uniquevariants. Sevenstaticsources updated; pendingcatalog/Yahoo2058/2059 preserved. AuthenticatedMotilal normalpageJSHTTP200SHA699ce431b06927a5984e27b7627224488fad9df1df309de297aa7fea762a2a20matchesownerfile. No broker session/runner/order/service changes. Evidence: .private/chart-order-rollouts/motilal-pine-native-alias-20261119/manifest.json.

### 19 November — fresh Motilal public master coverage and tick discrepancy

Official documented anonymousCSV downloads succeed for7contract exchanges and2index masters. Fresh193421unique native IDs:193316contract rows+105indices. Strict existingcontract parser accepts191846;1470NSECD rows have ticksize0.000. Of these1458match17Nov authenticatedcache IDs withtick0.0001;12lackthatpriorcomparison. Cross-date comparison cannot establish simultaneousproviderrounding parity or license inference fornewcontracts. PublicCSV fallback NOTactivated;7account/order-master hashes match prioraudits exactly. PublicJSON endpoint withoutcredentials producedrequiredheader errors, no usablemaster; noauthsettingschanged. COM/UNDCUR/UNDIRCclassification remainsunresolved (COMincludescommodityindices; UNDIRCincludesovernightMIBORandgovernmentbond references). Full publiccatalogcoverage isnotnativeOHLC/accounteligibilityproof. Primary docs: MasterDataAPI.html andIndexDataAPI.html underofficialMOFSLdocumentation; Pinev6reference confirmscommodity/forex/economic/bond types exist butdoesnotmapnativeMOclasses. Evidence: .private/chart-order-rollouts/motilal-public-master-20261119/manifest.json.

### 19 November — compact narrow drawing utility controls

JS2060/CSS321 groups existingMeasure/Zoom/Eraser/Keep/Lock controls underMore drawing controls atviewport<=760px. Reparents originalnodes usingpositionmarkers; no duplicate actions/listeners orchanges tofavorite/shortcutsettings. Desktop originals restored inexactorder; pressed/disabled andfocusedcontrol state preserved. Escape closesmenuandfocusessummary; choosingmeasurement/drawing modeclosesmenu. Nativegroupmenus excludeoverlap. Main isolatedDeltaETHUSD30m hosted520/600requested widths show52.04pxsingle-rowdrawingrail withallfiveutilitycontrols reachable. Keepfalse→true→desktoptrue→originalfalseverified; Measureactivates, menucloses, Escapecancels andchartstaysopen. Desktopcontrols andviewportrestored; V1removedonlywithinsharedtestview. SixDOMbehaviorcases+existing64focusedregressions pass across8uniqueactive/pendingvariants. SevenstaticJS/CSSsourcesupdated; pendingcatalog/Yahooversions2061/2062requireCSS321. No process/runner/order changes. Otherowner runtime, verysmall/mobile andshortheightlayoutsremain. Evidence: .private/chart-order-rollouts/compact-drawing-controls-20261119/manifest.json.


### 19 November 2026 — native TRIX formula correction

Native TradingView built-in TRIX export on DELTAIN:ETHUSD.P 30m exposed a percent-change mismatch. Corrected the standalone study to 10000 times the change of triple EMA of natural-log price. Seven maintained remote study libraries and HTML asset references updated to trix-log-7; no process restart, runner change or order action. Focused TRIX/DMI tests: 5 passed. Independent Decimal50 audit: 35 cases, 7515 numeric and 30 missing checks, maximum error 1.10e-11. Native export: 299 completed rows; last75 TRIX values agree within 3.37e-9 after cold-start warmup, while earlier errors remain recorded (last150 maximum 7.24e-6). Full earlier-history seed parity is not established. Fisher and trigger last150 agree within 2.23e-16. Hosted main shared Delta chart applied and rendered TRIX; downloaded CSV independently checked against its own OHLC. Evidence: .private/chart-order-rollouts/native-oscillator-reference-20261119/. Temporary TRIX removed from the shared test view; regular saved chart preferences unchanged. Other owner hosted delivery and narrow layout were not reverified for this calculation-only change. Overall TradingView parity remains incomplete.


### 19 November 2026 — five advanced oscillator formula audit

Independent Decimal50 standard-formula audit of UO, Vortex, KST, Coppock and Aroon: 80 cases across captured Delta OHLC, flat/trend, empty and one-bar datasets; 32228 numeric and2464 missing checks pass, maximum error1.01e-11. Default and selected custom periods covered. No further calculation changes were needed. Evidence: .private/chart-order-rollouts/native-oscillator-reference-20261119/advanced-reference.json; verifier scripts/verify_chart_advanced_oscillators.py. Native TradingView settings, warmup, and full broker/rendering parity are separate unproven gates.


### 19 November 2026 — labeled indicator parameter layout

Hosted Vortex Inputs exposed an unlabeled14 tiny input. JS2063/CSS322 gives all standard length/multiplier controls visible fallback labels, and labels source/color/pane selectors. Aligned scoped grid with30px controls; no calculation or order behavior change. Seven maintained source snapshots updated; six pending frontend variants rebased with forward pointers. Eight unique variants passed focused settings regressions. Hosted main shared DeltaETHUSD30m: UO/Vortex/KST/Coppock/Aroon panes render; Vortex length14→9 applies, VI+4px visibly thickens. Desktop/narrow settings inspected; actual narrow viewport578x1000, panel32..546x180..560, Style scroll379client/584content. Length input180x30. Viewport reset and all five temporary studies removed; regular saved chart preferences unchanged. Other owner hosted delivery not reverified. Evidence: .private/chart-order-rollouts/study-parameter-labels-20261119/.


### 19 November 2026 — FYERS main-workspace chart controls

Fresh main shared FYERS NIFTY50 30m displays changing live source price and Candles/HA/Renko/Line render. SMA Length/Source labels visible. Renko ATR14 62.45pts Close switches to Traditional25pts and back. Narrow578x1000 Renko panel bounds16.55..333.44x119.08..369.43 fits. Compact More drawing menu retains allfive utilities; Measure pressedtrue thenEscapefalse. Reset viewport and returned Candles. No regular saved preferences, broker orders or runners changed. This extends selected broker rendering/control acceptance, not independent chart-construction/feed parity or all-user assignment proof. Evidence: .private/chart-order-rollouts/study-parameter-labels-20261119/hosted-fyers.json.


### 19 November 2026 — FYERS drawing history and chart-mode persistence

Created one Trend line by pointer on main shared FYERS NIFTY50 30m:17Nov09:45IST25280.33→18Nov13:15IST25380.92. Applied4px andboth left/right extensions. Exact coordinate-field values retained onLine, HeikinAshi after390oldercandles loaded, and RenkoATR14 62.45pts Close roundtrip backtoCandles. Extended line visible inRenko; final width/extensions retained. GoTo completed. Narrow578x1000 drawing-settings bounds58.89..518.89x160..840 fit. Removed temporaryline andconfirmedNo drawings, viewportreset; regularsavedpreferences,brokers,runners untouched. Evidence:.private/chart-order-rollouts/fyers-drawing-persistence-20261119/hosted.json. One-tool selected-source workflow does not prove allgeometry,all-drag/all-broker/nativeTradingViewparity.


### 19 November 2026 — FYERS weekly/monthly/annual hosted pagination

Fresh main shared FYERS NIFTY50 Candles1W1M12M loads without history error. Seven exports checked: latest524completedweekly from31Oct2016,165monthly fromFeb2013,11annual2015–2025, plus separateformingrows. Uniqueorderedtimestamps,positivevalidOHLC. Four exported page transitions add262/55/4/4oldercompletedrows and preserve every priorcompletedOHLCVfield. Eleven annualOHLCVbars exactly match respective12monthlyexportbars (55fields). This is adapter-export calendar consistency; no separate rawprovider/dailysource/terminalhistory/all-symbol claim. AnnualUIolderstartJan2015. Evidence:.private/chart-order-rollouts/fyers-calendar-pagination-20261119/audit.json. No code/restart/runner/order mutation.


### 19 November 2026 — FYERS custom hours and provider volume variance

Hosted6h14h22h23h render. Regular31sessions:155completedcustombars620OHLCfields exactly match independent grouping of30mexport;16volumechecks differ across4sessions, so fullOHLCV audit remainsFAIL. Two fresh selected-owner nativeFYERS resolution30 requests04–19Nov vs12–18Nov reproduce historicalvolumevariance withidenticalprices. Customexportmatches50raw-widegroupedbars250OHLCVfieldsexactly. Preserve brokerresponses; no manufacturedvolumeparity. SpecialNov8threebarssessionandcurrentNov19excluded/listed. 23hUIbriefIncompletehistoryduringloadingthenLive, needsfollowup. Evidence:.private/chart-order-rollouts/fyers-custom-hours-20261119/audit.json andvolume-cause.json; scripts/verify_fyers_custom_hour_exports.py andprobe_fyers_custom_hour_volume.py. Noorders/restarts/runnermutations.


### 19 November 2026 — FYERS forming history snapshot label

23hloadingtransient tracedto complete-part FYERS RESTformingseed awaitingfirstliveupdate, not evidenceofmissingprices. JS2066 distinguishes matching sampledFYERSseed asHistorysnapshot withtimestamp/awaitingliveupdates tooltip; genuineunbound/missingseed retainsIncompletehistory. NohistoryOnlyflag,brokerprices,freshnessorconfirmationgatechanged. Sevenremotesourcesupdated; sixpendingvariantsrebasedto2067/2068 retainingCSS322/studiestrix-log-7. Eightuniquevariants passedfocusedtests including3newsemanticcases. Hosted22hmainsharedFYERS controlledtest blockedonlyagenttab exact-ownerchart-liveHTTP:Historysnapshotvisible;afterblockclearedautomaticLivecandlewithoutrefresh. Narrow578x1000badgefits422.87..521.86x218.30..235.07;viewportreset. Noactiveblock,restart,runnerororderchanges. Evidence:.private/chart-order-rollouts/fyers-history-snapshot-label-20261119/hosted.json.


### 19 November 2026 — current-user chart assignment audit

Read-only productionregistry lists2users:administratorimplicitChartworkspaceaccess,regularuserexplicitassignment. Globalchartvisibilitytrue. HostedAccountsglobalcheckboxandregularuserChartworkspacecheckboxbothchecked. No assignmentchangesneeded/performed. Threeisolatedregistrytests pass:chartAPIpermissionrefreshuponrevocation,currentassignmentpreservedbyglobalvisibilitychanges,chartpermissiondoesnotgrantotherusersbrokeraccountsincludingadministrator. No regular-userlogin/livehide/revoke/impersonation. Newusersretainexplicitassignmentpolicy. Evidence:.private/chart-order-rollouts/chart-permission-audit-20261119/audit.json;tests/test_chart_section_permissions.py. Fullruntimepermissionmatrixnotproven.


### 19 November 2026 — FYERS V1 realtime lower-timeframe reference gap

FreshmainsharedFYERS NIFTY50 30mV1readyafter~55s,but15mRSI/SMAblankwhile5m/30mfilled. Minimalworkerprobeexport shows406historical15mRSIpoints/399SMApointsbutforminghostrowmissing;hostRSIfinite. RootcausefrontendloadPineCandles onlyaddedformingsecondaryreferenceforDelta. JS2069usesFYERSnativeformingseed/freshcontinuousminuteframeonactivewindow;neveraddsconfirmedhistory,norusesexpired/future/missingseed. Eightuniquevariantsfocusedtestspassincluding4newcases. Sevenremotesourcesupdated,norestart;pendingcatalog/Yahoo206? rebased2070/2071,CSS322unchanged. HostedV1Candles/Linefilled15mRSI63.75/SMA57.38withtooltipcompleted13:00at13:01:16;5m63.24/SMA63.91end13:00,30m60.43/SMA48.42end12:45. Tablescompactdesktop/narrow,ExpandfullLevels tablefits578x1000. Originaleditor6876char-draftrestored,diagnosticremoved,viewportreset;finalCandlesdeliverable. Startup~50–55s remains;independentnumerical/nativeTV/HA/Renkoparityunproven. Evidence:.private/chart-order-rollouts/fyers-pine-forming-reference-20261119/hosted.json;baselineprobeCSV .private/chart-order-rollouts/fyers-v1-rsi15-20261119/diagnostic.csv.

### 19 November 2026 — actual FYERS SENSEX execution alignment and delay

User-reported BUY/SELL misalignment and untimely entry/exit investigated against
the actual FYERS SENSEX LIVE price-confirmed Renko run, not historical simulation.
Frozen run 5df35b1b4296e5885cbd contains two entries: signal-to-submit 8.52s/13.72s,
signal-to-fill 9.98s/18.89s; exits 6.82s/7.23s to submit and 14.11s/9.10s to fill.
PUT source tick arrived 1.20s after exchange time; assessment followed 10.16s
after local receipt. Its recorded entry preflight took 0.32s. This proves an
internal pre-assessment delay, without isolating all contributing stages.

Static marker fix active: confirmed-indicator reference time and coordinates
now belong to the same recorded brick. Recorded replay maps all four fills,
versus three previously. Four source variants passed 38 JS checks each. Hosted
runner-audit chart showed all four fill labels; overlapping simulated labels
still need visual work and narrow-width verification. No runner/order mutation.

Tested but NOT ACTIVE execution candidates: quote-selection clock freshness
correction (10 selection tests); immutable ordered-price publication cache
(6 focused tests plus 38 existing confirmed-feed/price/continuity tests).
Profiled 12-brick synthetic continuation: 9.36s baseline versus 1.57s candidate.
Without profiler, 24 bricks: 3.76s versus 1.45s; warm median 148.11ms versus
52.45ms. Durable history SHA-256 matches exactly, including all indicator
values. These are isolated offline results, not live latency guarantees.
First publication still copies the full window. The cache retains strong
references only for the current 500-row window and exact run, requires an
explicit immutable-row caller, and reader responses remain deep-copied.

Root and FYERS price_basis.py differ in existing stale-exit handling. The staged
FYERS candidate preserves its own source and changes only the publication
call; it does not silently import root-only execution rules. Reload approval
remains pending. No production Python replacement, reload, runner start or
order placement occurred. Execution timing and full goal remain incomplete.

Evidence: .private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119/
(latency-diagnosis.json, publication-benchmark.json, publication-regression.json,
execution-candidate-manifest.json). Reproducers:
scripts/profile_recorded_price_renko.py,
scripts/run_price_publication_candidate.py,
scripts/verify_price_publication_candidate.py.

### 19 November 2026 — distinguish simulated chart signals from confirmed fills

Added visible Show simulated signals checkbox beside the chart legend. Default
OFF removes SIM BUY/SELL/EXIT clutter while retaining FILL ledger glyphs and
swing annotations. Preference scoped by account and broker. Explicit Show latest
historical event enables its simulated marker before navigating. No calculation,
order policy, runner setting, entry protection or broker route changed.

Seven static owner JS/index assets updated without restart; four unique JS
variants each pass 40 checks, including immutable input and preserved/deduplicated
fill tests. Hosted FYERS SENSEX captured stopped-run chart verified: default off,
on restores SIM arrows, off removes them, confirmed fills retained. Narrow
577x1000 checkbox interactive; legend bounds31.09..546.68, scroll/client516;
desktop override reset. User's existing foreground tab not reloaded. Separate
review tab retained as deliverable. Right-edge fill/axis overlays can still
collide; no full marker-layout parity claim. Execution backend candidates remain
staged pending explicit FYERS reload approval. Evidence:
.private/chart-order-rollouts/renko-signal-label-control-20261119/manifest.json.

### 19 November 2026 — distinguish price queue delay from broker latency

Frozen FYERS run has six STALE_PRICE_EVENT entry assessments, including ticks
received promptly but assessed beyond the 15-second entry deadline. No stale
entry guard was relaxed. Staged price_basis candidates now add bounded timing
diagnostics: producer observation work, durable sidecar write, pending/completed
chart-publication work, monotonic queue wait, execution-step duration, and
receive-to-record age. Cache max2000 events, durable reports max120; exact
generation/sequence/index/timestamp identity and run reset prevent attribution
to another brick or run. Diagnostics add no broker calls or extra state writes
and do not change signal/quote timestamps, order rules or confirmation gates.

Five timing tests pass on root and FYERS candidates; six publication tests and
38 existing price/confirmed-feed/continuity tests pass with diagnostics. FYERS
owner-specific unprofiled24-brick continuation1.42s, warmmedian52.61ms; durable
history bytes exactly equal baseline (SHA98e0f28673ed0275e3a7b0aec02c4e0edf0d78297b51bb4ed2d19abf053b9b2e).
No live timing claim. Existing staging manifest candidate hashes refreshed,
active Python hashes checked unchanged. FYERS reload approval still pending.
Acceptance priority now records actual execution timing explicitly while all
13 original requirement groups remain partially verified; no scope reduction.
Evidence: execution-candidate-manifest.json, timed-publication-regression.json,
timed-publication-benchmark.json in the FYERS execution-alignment rollout.

### 19 November 2026 — open Renko Pine closing-time semantics

Official TradingView Pine Time documentation states open realtime price-based
bars have unknown time_close until they close. Current chart-workspace worker
input instead assigns every synthetic bar candleEnd(sourceTime, interval),
including provisional Renko projections. Offline probe confirms this exposes a
finite close while barstate.isconfirmed is false. The unchanged worker supports
NaN close correctly: na(time_close)=true and isconfirmed=false.

Staged, NOT ACTIVE frontend helper assigns unknown close only to provisional
Renko worker inputs, preserving source opening, chart coordinate, OHLC, known
historical source bounds and scheduled Heikin Ashi close/volume. Four focused
mapping cases and an end-to-end actual worker probe pass. No production assets
or pending manifests were changed. Do not activate this partial candidate until
full V1 MTF handling is validated: unknown host close affects source-close guards
and collectRenkoIntrabars currently requires a finite end. Also unchanged Renko
bar geometry currently short-circuits Pine refresh, a separate reference-update
gap. No fake timestamps or confirmed bricks introduced to make tables current.

Read-only inspection of the existing shared user tab found it now on FYERS
SENSEX5m Candles with a drawing in progress, not the earlier NIFTY Renko test
context. Left that live tab untouched; no stale-context reconfiguration. No
native chart session was available for exact rendered Renko parity. Offline
probe is semantic evidence only; historical close approximation and other
barstate semantics are not certified. Evidence:
.private/chart-order-rollouts/renko-pine-time-semantics-20261119/manifest.json,
baseline.json,candidate-worker-probe.json;
scripts/probe_pine_renko_close_time.cjs,
scripts/verify_pine_renko_close_time.cjs.

### 19 November 2026 — open Renko lower-timeframe compatibility candidate

Unknown-close probe reproduced request.security_lower_tf returning an empty
array. Staged worker uses evaluation clock only for an open unknown-close
Renko window, collecting completed intrabars and excluding future/forming bars.
Separate request.security previous-value lookup also returned na. Candidate
recognizes only the last unknown-close Renko context and selects the last
available lower-timeframe context, consistent with TradingView's documented
realtime behavior regardless of lookahead. Its higher-timeframe mapping receives
an evaluation bound while exposed host time_close remains unknown. Historical
selection paths remain unchanged. Frozen13:03 scenario returns six completed5m
intrabar values ending13:00; prior reference close28/end13:00 replaces na.
Eight collection-boundary and six realtime-index cases pass. Existing Renko
window, metadata-history and closed-reference checks pass. No active worker or
chart asset changed.

Full saved V1 offline archived FYERS replay was attempted using actual partial
source-period projected bricks and separate native/synthetic provider paths.
Not validated: host developed severe memory/IO pressure (16GB total,120MB
available,no swap; memoryfull avg10=31.35%,IOfull16.71%). New SSH banners timed
out. Initial termination attempts did not run; after connection recovered,
verified exact isolated node PID48347/script/cwd and requested SIGTERM. Original
session returned143 Terminated. Production workers/runners untouched. Added
120s deadline to the verifier; do not launch heavy replay under this pressure.

Read-only later process RSS: FYERS account worker4751.2MiB,main2489.2MiB,
Delta1053.2MiB. Available memory322008kB after isolated replay termination.
Current host pressure is material but does not prove earlier execution-delay
causality. Per-adapter public master parsing/history caches warrant review;
source inspection alone does not establish the dominant heap owner. No cache
flush, restart, production Python replacement, credentials or broker mutation.
Evidence: renko-pine-time-semantics-20261119/manifest.json,
open-reference-candidate-2.json,boundary-and-index-regression.json,
worker-regression.json. Full V1, realtime refresh and hosted parity remain open.

### 19 November 2026 — bounded shared public FYERS CSV master candidate

Read-only FYERS saved-instance inventory:13 configured instruments,0 running,
0 owned positions,0 pending. These are saved runner claims, not a fresh
broker-wide exposure check. Web constructs separate execution/chart/adoption
adapters per instrument. Each existing adapter parses/retains identical CSV
rows independently. Native NSE_FO CSV16.31MiB. Current worker4751.2MiB RSS is
observed; source duplication is a concrete allocation opportunity, not proof
that it dominates this process's current heap.

Staged broker candidate shares immutable tuple-of-tuples per absolute public
master path and exact inode/mtime_ns/size. One current version per path, bounded
16 paths, cold-parse lock prevents concurrent duplicates. Existing24h freshness
guard runs before cache lookup. Descriptor and current-path signatures checked
after parse; atomic replacement or mutation during read fails closed. Parsed
rows cannot be mutated; expired/missing inputs cannot reuse cached data.
No credentials, quotes, positions, sessions or orders shared in this cache.

Seven tiny fixture checks pass, including13adapters→oneCSVparse, parallel
singleflight, replacement invalidation, changed-during-read rejection, immutable
readers, distinct owner paths and eviction. Twenty existing broker-stream,
valuation and snapshot-valuation checks pass. Root/FYERS active source hashes
remain unchanged. No real memory reduction or hosted activation claim. Named
JSON instrument masters remain per-adapter and need separate review. This
candidate is not silently included in the earlier pending execution-fix reload
request. Evidence:.private/chart-order-rollouts/fyers-master-memory-20261119/
manifest.json,regression.json;scripts/verify_fyers_shared_master_memory.py.

### 19 November 2026 — explicitly approved FYERS combined worker activation

User approved "Approve combined FYERS worker reload" for four-file bundle:
quote freshness, immutable confirmed-price publication, bounded timings and
shared public CSV rows. Combined86fixture checks passed. Fresh14canonical
runner-state guard passed. NativeFYERS initially2positions/0openorders:
20SENSEX26N1983000CE MARGIN and20CUPID MTF. Strict native-flat probe correctly
reportedBLOCKED_EXPOSURE; no files or restart were changed at that first check.
Subsequent ownership review: no runtime/adoption claims, no Handoff exit trades,
no entry waits; Handoff scope is owned receipts only. The specifically approved
FYERS worker reload therefore used the existing reviewed workspace_bounce
application-ownership guard, retaining native unclaimed positions without any
close/adopt/order action. No active-runner guard was bypassed. Source hashes and
ownership scope recorded before handoff.

Four FYERS-owner files backed up/replaced. Guarded handoff3697918→54371 READY.
All14critical saved config/run/lifecycle/ledger hashes match before/after;
runners remain stopped. Canonical root remains staged; other workers and
unfinished Renko Pine candidate excluded. Source replacement and readiness
verified. Native postflight1position/0orders (external/native state changed;
this work submitted0orders and does not attribute that change). All14runtime
guards stillPASS.

RSS initial805520kB, later1111228kB (~1085MiB), versus4751.2MiB before; host
available3992952kB versus earlier120MiB. This proves current post-reload memory
relief, not sole attribution to CSV sharing or sustained growth prevention.
Existing user shared tab503427998 stayed SENSEX5m Candles with drawings/settings
untouched and no page reload. Live feed reconnected. V1 interrupted history
calculation required two explicit Retry Pine actions during verification;
tablevalues updated afterward. Observed native-source1W200/262rows,503,200;
1M503then200/55rows. Study remainsupdating; automatic transient recovery and
calendar-history request frequency need work. Do not call fullV1/weekly
recovery complete. No live entry/fill timing or profitability claim; no runner
started for validation.

Evidence: fyers-sensex-execution-alignment-20261119/fyers-activation-bundle.json,
approved-reload-1795080231155197136/result.json,
combined-reload-preflight.json,combined-reload-exposure-details.json,
combined-reload-postflight.json,combined-reload-hosted.json.
Screenshot:/private/tmp/fyers-execution-reload-hosted.jpg.

## 2026-11-19: bounded Pine transient recovery

Published static recovery v3 across all seven chart owners, preserving newer all-segment mapping. Initial Add and live worker reference failures share a bounded four-retry budget, honor Retry-After, and cancel on broker, input, symbol, interval, chart-type or workspace changes. Authentication and permanent script errors do not retry. Last good plots remain available. No backend restart, runner or order action.

Two unique source variants passed 56 focused checks each. Repaired missing mock helpers in an existing host snapshot fixture; its four failures also reproduced on baseline. Hosted v2 core proof: an isolated small request.security study encountered an injected FYERS 3m network failure, displayed automatic retry, then applied after clearing the fault with no second Add click. V3 adds context deduplication guards covered by fixtures; all seven source hashes and v3 index tags verified. Full V1 automatic recovery remains unproven.

At 578px viewport width the longer success status shared with recovery messaging had client/scroll widths 542/542, without overflow. This was layout verification, not a second injected-failure test. Temporary studies removed, network blocks cleared, viewport reset, original 6876-character editor draft restored. Original user chart not reloaded. Evidence: pine-auto-recovery-20261119/manifest.json and hosted-verification.json; screenshots /private/tmp/pine-recovery-{retrying,applied,narrow}.jpg.

Canonical backend execution files remain staged despite the active FYERS owner bundle. Future provision copies canonical sources; coherent promotion is needed to prevent regression, and hot mixing cached old modules with new source is unsafe. The canonical candidate passed 92 checks; no canonical backend publication or main restart performed. Older full-file chart candidates require fresh rebasing over all-segment mapping and recovery v3. Broad chart acceptance remains incomplete, including actual live execution latency.

## 2026-11-19: canonical backend compatibility preparation

Reconfirmed provision refresh copies canonical public files over account snapshots. Canonical execution bundle still staged, so future-launch durability is not established. Added an explicit publisher-capability check to the canonical price_basis candidate: immutable row optimization is passed only when supported by the loaded publisher signature; internal TypeError is propagated without retry/replay. Four compatibility cases passed (legacy, current, variadic and internal-error single-call), followed by 92 combined canonical regression checks. Corrected report scope to distinguish canonical from FYERS-owner candidates. Initial test invocation had missing PYTHONPATH/package identity; corrected invocation passed. No production backend file changed or service reloaded. Remaining: review other cached/new module boundaries, then coherent canonical publication and actual provision verification without disturbing existing runner state.

## 2026-11-19: canonical execution source publication

Reviewed module interfaces: broker cache and option selection retain existing signatures; confirmed publisher adds an optional default-false argument; canonical producer checks the loaded publisher capability before using it. Twelve synthetic continuation events using the new canonical producer and cached legacy publisher queued twelve bricks, with durable history JSON exactly equal to the recorded baseline continuation. No broker calls/orders. Canonical candidate retained existing opposite-exit handling and passed the earlier 92 checks plus four compatibility cases.

Published the four canonical files (broker, option_premium, confirmed_feed, price_basis) after exact baseline/candidate SHA checks, with backups under fyers-sensex-execution-alignment-20261119/canonical-publication-20261119/. Updated sources now supply future workspace provisioning. Actual provision() exercised twice in isolated filesystem fixtures with all four hashes/overlay hashes matching and journal retained; it did not provision a real account. No running dashboard worker restarted or runner started. Running main process may retain older cached modules, so source publication is not proof of process activation. Existing FYERS owner remains on its previously approved active bundle. Broad chart acceptance and real live execution latency remain incomplete.

## 2026-11-19: Renko Pine rebase and full-script resource failure

Rebased unknown-open-brick-close mapping onto all seven current recovery-v3 chart sources, retaining all-segment mapping. Both unique variants passed 60 checks covering recovery, host snapshots, worker fallback, FYERS forming references, Renko windows and four close-mapping cases. The host-snapshot fixture initially lacked the newly extracted helper; loading the actual helper fixed its four failures. Fourteen worker intrabar/index boundary cases also passed.

Full saved V1, frozen FYERS archive, projected Renko replay did not complete: first isolated run reached its 65s cap (exit124). An instrumented retry with 120s internal deadline, 125s outer timeout and 1GiB heap advanced through 26 reference requests but exhausted Node heap near121s (exit134). Native frames were supplied locally; zero broker calls or orders. Peak observed RSS1037064kB; host available memory before retry3571184kB. This proves failure under this explicit offline resource budget, not that every hosted browser will fail or that the time-semantics patch caused it. No result/table parity claim. Both isolated handles terminal; no production worker killed. Full-script runtime memory/performance diagnosis is the next dependency before activating this candidate. All seven active source hashes still match their pre-rebase values. Evidence: renko-pine-time-semantics-20261119/rebased-manifest.json, rebased-regressions.json, full-v1-rebased-120.log and its request progress JSON. No service reload, source activation, runner start or trading action.

## 2026-11-19: full V1 allocation diagnosis and array cache candidate

Instrumented local archive replay with Node inspector allocation sampling. Timer-only capture starved behind the promise chain and reached its external55s deadline; checkpoint-based capture completed normally at request12 and request25. Late sampled retained allocations total approximately749MB, with Pine array constructor G prominent. Each instance allocated42 context-bound method closures, despite factory functions immediately returning closures whose state is bound only to the execution context.

Staged a WeakMap of method tables per execution context. Kept array contents, type, context and method fields per instance; preserved the baseline uninitialized _includes own field after the first semantic comparison exposed its omission. Contexts remain separate, precision updates are observed, mutation/copy/bounds behavior compares equal to baseline, and1000 arrays share one get closure in one context. Six worker regressions passed: var/varip rollback, Renko window rebuilding, metadata history, Heikin incremental parity, calculation-limit lifecycle, bounded drawing geometry.

An initial Object.assign constructor saved little retained memory because object layout changed. Preserving the original field initialization layout reduced retained heap for10000 isolated three-element arrays from35797384bytes to4494480bytes; constructor time325.17ms to35.97ms in this one run. These are constructor microbenchmarks, not whole-chart memory or latency claims. Full V1 with this v2 cache still reached the125s external replay limit after26 reference requests, exit124, with no result. Earlier cache version also timed out. No OOM was logged for v2, but full-script memory completion is not proven. Further request-context computation profiling remains necessary before activation. All candidates remain staged, no chart worker/source activation, service reload, runner or broker action. All isolated test handles terminal.

Evidence: renko-pine-time-semantics-20261119/v1-allocation-summary.json, array-cache-staging.json, array-cache-worker-regression.json, full-v1-array-cache-v2.json.progress.json; scripts/profile_v1_pine_heap.cjs, measure_pine_array_allocation.cjs, verify_pine_array_method_cache.cjs.

## 2026-11-19: request dependency optimization activated and hosted checked

CPU profiling and generated request-body inspection showed later security() expressions inheriting nearly the full preceding script (one421573byte body). Prepared a conservative fixed-point dependency filter over transpiled statement facts, preserving declaration metadata, referenced functions/inputs, persistent writes, object/array aliases, namespace mutations and instance-method receivers. Iterations exposed over-retention from local bindings, readonly runtime/native identifiers and primitive assignment aliases. An additional semantic fixture caught optional-chain instance methods being omitted; unwrapping ChainExpression corrected it before publication. Nine baseline/candidate plot comparisons passed, including array instance mutation, no-argument global mutation, tuple histories, conditionals, aliases, transitive inputs/functions, independent requests and object fields. Seven existing worker regressions passed. One exploratory baseline fixture using chained array.last(a).v failed before optimization; replaced with supported explicit record access, without claiming that syntax fixed.

Complete unchanged V1 replay over18000 archive minutes,300 host Renko bars and one projected brick completed in16.28s, peakRSS224012KiB, with two tables and independent completed15m RSI/SMA display parity. A controlled6000-minute comparison against the same time-semantics/array-cache worker WITHOUT dependency filtering produced identical entire plots JSON SHA256 d858b6771e02fa8db48b501e6775ebd87be8d62a3f92864041d482aac0c2fc7c and identical tables. Time77.959→14.879s, peakRSS520240→210276KiB in those isolated runs. These are archive replay results, not live execution latency claims.

After baseline/candidate SHA guards and backups, published the worker and all seven rebased chart sources/index tags. Preserved recovery-v3 and all-segment mapping. No service reload. Hosted separate shared FYERS SENSEX30m Renko chart calculated Sector Pulse V1 and rendered both tables; observed RSI5/15/30=77.16/76.03/72.61, SMA=74.34/66.89/57.69. These hosted readings were not independently recomputed against a fresh broker export. Market closed (feed Disconnected); live unknown-close rollover remains unverified. Narrow table expansion measured287x210 client/scroll bounds, with all period rows available. Screenshots /private/tmp/v1-renko-optimized-hosted.jpg and /private/tmp/v1-renko-optimized-narrow.jpg. Reset viewport, compacted table, hid V1 again only in shared view, closed test tab; original user chart (AXISCADES1D Renko) not reloaded or changed. No editor draft modification, broker or runner action.

A first browser test tab disappeared from the session; a fresh named session succeeded. Shared URL initially displayed Investment until clicking Chart workspace; route/preference ordering requires investigation. Remaining known issue: unchanged Renko geometry short-circuits reference refresh. General TradingView visual/functional parity remains unproven. Evidence: rebased-manifest.json, hosted-verification-20261119.json, v1-request-dependencies-comparison.json, full-v1-request-deps-v9.json, request-deps-worker-regression.json and allocation/CPU profiles under renko-pine-time-semantics-20261119/. Older recovery manifest marked superseded with its behavior preserved.

## 2026-11-19: direct chart-link navigation fixed

Reproduced a startup race: chart-workspace mounted and activated the requested view, then investment.js activated its stale saved Investment preference later. Added a chart-specific startup guard so view=chart-workspace suppresses that preference restoration. Explicit Investment and normal/unknown-view fallback retain existing behavior. Hidden-section checks remain unchanged. Eight fixture cases passed; the prior source reproduces the chart-link override failure. Final scope refinement preserves unrelated view fallback; its chart branch is the same branch verified in the hosted test.

Published investment.js and cache-tag updates across all seven owners, with backups, baseline/candidate SHA guards and overlay hashes. Hosted test explicitly selected Investment first, then navigated directly to a FYERS SENSEX30m Renko shared link. At desktop and narrow widths it automatically selected Chart workspace and opened the chart without a navigation click; source/symbol/interval/type were retained. Narrow history loaded. Screenshots /private/tmp/chart-link-navigation-desktop.jpg and /private/tmp/chart-link-navigation-narrow.jpg. Restored Chart workspace as the selected navigation preference through the UI, reset viewport, closed test tab. Regular chart settings and original user tab untouched; no service reload, runner or order action. Hosted case used FYERS; other brokers were not separately browser-tested. Full acceptance remains incomplete.

Evidence: chart-link-navigation-20261119/manifest.json, baseline-failure.log, owner backups/candidates; scripts/verify_chart_link_navigation.cjs. Next chart dependency remains unchanged-brick multi-timeframe freshness and live forming-brick verification.

## 2026-11-19: incremental native-reference freshness activated and live checked

Reproduced two linked issues: unchanged synthetic geometry returned before Pine reference updates, and worker updateTail removed earlier numeric plot points sharing a Renko source open time. Added fresh-tick reference-only notification for actual reference-using studies on forming Candles/Line/Renko/Heikin Ashi hosts, with per-study duplicate-tick suppression, coalescing, context cancellation and stale/future/disconnected checks. Replay and confirmed-only hosts remain frozen. Stable Renko/HA geometry uses incremental tail rollback; native corrections/reset paths retain full replay. Numeric Renko plot rollback now removes points by barIndex when available, preserving older bricks in the same source window. Existing five-second live-frame cache remains. No extra broker REST quote polling or order path changes.

Both source variants passed60 related regressions plus12 scheduler cases each. Seven worker regressions passed. The eight-brick duplicate-source probe preserves host/state plot histories and the confirmed reference prefix while updating the final native reference. Initial full-V1 warm assertion expected latest completed5m RSI, but V1 sc_closedOsc explicitly selects previous source when time_close is unknown. Corrected the oracle to follow this supplied script rule; no script/timing spoof. The actual artifact preserves both failed diagnostic and corrected test. Full unchanged V1 with300 frozen Renko bricks updated in0.174s, retaining22 numeric plot prefixes and matching independent5/15/30 RSI/SMA for the selected prior source bars. This is a controlled reference/state test, not coherent host-price-path or profitability evidence.

Published worker and seven chart sources/index cache tags after SHA guards/backups. Hosted separate shared Delta BTCUSD30m Renko view: $100 size initially had no forming brick, correctly stayed frozen. Changed only this shared view to$10 to expose a forming brick. Unsaved Live reference refresh probe showed Native1m close63790.50→63798.50 between17:35:54 and17:35:56IST while displayed Renko O/H=63810,L/C=63800 remained unchanged. Calculated timestamp also advanced without a displayed brick change; Live status visible. Source prefix and brick count were not directly counted in hosted DOM; exact numeric-prefix preservation is covered offline. A narrow expanded probe table fit149x46 client/scroll bounds. Screenshots /private/tmp/renko-live-reference-refresh.jpg and /private/tmp/renko-live-reference-refresh-narrow.jpg.

Temporary probe removed; original109026-character draft restored exactly without Save, template/saved/applied selector labels remained as originally observed. Restored shared size100 and V1 visibility, reset viewport, closed test tab. Original user tab and regular chart settings untouched. One isolated scheduler test failed on undefined-vs-false reset representation and retained its test timer; exact node script/cwd/args verified before terminating only that probe (SSH exit143). Corrected boolean assertion and bounded rerun passed. No production process, runner, service or broker order action.

TradingView reference consulted for execution/rollback and unknown close semantics: https://www.tradingview.com/pine-script-docs/language/ and https://www.tradingview.com/pine-script-docs/concepts/time/. Live GUI validation is Delta Renko only; other types passed controlled scheduling tests. Overall acceptance remains incomplete, including historical Renko timing and real entry/exit execution. Evidence: renko-reference-freshness-20261119/manifest.json, hosted-evidence.json, full-v1-warm-guarded.json, frontend-regression.json and worker-regression.json.

### Dhan source ownership and NSE commodity verification — 19 November 2026

Read-only native checks verified the Algo workspace's own registered Dhan client binding and active data plan (profile HTTP 200). The fresh master contained 229,486 rows; all 25,504 current NSE commodity rows were OPTFUT, with no FUTCOM rows. Two distinct nearest-expiry contracts (COPPER and SILVERM) were rejected by native intraday history when requested with NSE_COMM and the master-provided OPTFUT instrument. This does not prove that every NSE commodity is unavailable; the mapping and entitlement remain unverified, so it has not been enabled or silently mapped to MCX.

The chart source picker calls /api/workspaces/accounts, whose store query restricts accounts to the current application user. The valid Algo account belongs to a different application owner from both other Dhan accounts and is not explicitly disconnected. Its omission follows ownership scope, rather than a hard-coded symbol or account limit. No token was copied across owners. The separate Subhalaxmi token had returned an explicit Invalid Token response despite future saved expiry metadata; the valid Algo token does not establish that session is usable.

Evidence: .private/chart-order-rollouts/dhan-algo1-nse-commodity-native-20261119/result.json and source-discovery.json; earlier selected-session failure remains separately preserved under dhan-nse-commodity-native-20261119. Probe script accepts a validated registered workspace ID and separate evidence directory. All requests were profile/master/history reads; no service reload, session renewal, runner change or order submission occurred.

### Hosted drawing catalog availability — 19 November 2026

Authenticated main Delta ETHUSD 30m Candles shared view: every category opened; 90 drawing tools (89 plus horizontal line) enabled, each with a favorite control. Four Gann tools are a nested group under Fibonacci and Gann. Existing horizontal-line settings expose color, width, stroke, opacity and caption controls. Desktop and 520px narrow layouts inspected; keyboard focus scrolls lower caption controls into view. No drawing, style or favorite values changed; viewport reset and isolated tab closed. Evidence: .private/chart-order-rollouts/drawing-catalog-hosted-20261119.json. This proves catalog availability and selected settings access only; full per-tool geometry, gestures, persistence and external TradingView parity remain incomplete.

### Motilal saved-master completeness — 19 November 2026

The actual chart handler's complete pre-pagination ordered catalog matches all 190,666 eligible identities from 191,989 normalized saved master rows across NSE, BSE, NSEFO, BSEFO, NSECD, MCX and NCDEX: zero missing, extra or duplicate identities. A further 1,323 suspended/expired entries are intentionally excluded. Each segment's first, early, middle, final and terminal boundary pages match the complete ordered list exactly; four all-segment boundary pages pass. Complete page enumeration also finished for six segments; the costly NSEFO enumeration was intentionally stopped after checking its exact probe PID/arguments/cwd, then replaced with complete handler-list membership and boundary validation. No production process was stopped.

These are saved snapshots dated 17 November. Fresh native profile/master checks require reconnection; the saved session deadline has elapsed, and no renewal was attempted. Cached index masters are absent, so index completeness is not audited. The canonical and registered Motilal worker source handlers have identical SHA-256, but this isolated audit does not prove currently loaded hosted-worker behavior or current native OHLC/live entitlement. User indicated they will reconnect Motilal; fresh native validation remains pending.

Evidence: .private/chart-order-rollouts/motilal-catalog-coverage-20261119/{audit.json,saved-pagination.json,saved-membership-boundaries.json,source-comparison.json}. Reproducible scripts: scripts/audit_motilal_chart_catalog.py and scripts/audit_motilal_saved_catalog.py. No credential mutation, service reload, runner action or order submission.

### Desktop header space — 19 November 2026

Compared the currently open TradingView SENSEX5m Traditional Renko36 view with an isolated hosted FYERS SENSEX5m Traditional Renko36 shared view. Indicator visibility and visible ranges differ; this is a layout comparison, not price or Pine parity. Sector Pulse's source control had wrapped into a separate39px row, pushing quote actions and legend downward. A chart-container-width-scoped CSS rule now places the source control beside quote actions at widths>=1101px, only when those actions exist. Hosted header height126.48→81.97px, recovering44.51px. Source popup remains within chart bounds. Requested520px narrow check (effective578px document at current browser zoom) retains static stacked source control and usable popup. All7maintained CSSsources and14HTMLentrypoints updated with cache suffix; no service restart. No saved chart preference, drawing, runner, order or reference TradingView page was changed. Viewport reset and isolated testtab closed. Evidence: .private/chart-order-rollouts/chart-header-spacing-20261119/manifest.json.

### Indicator catalog expansion: NVI and PVI — 19 November 2026

Added Negative Volume Index and Positive Volume Index, each with its EMA line, documented starting index1000 and default EMA length255. Existing plot color, width, stroke, visibility and timeframe controls are reused. Volume-direction compounding uses selected-broker close and volume only; equal volume holds the index. Missing/invalid data leaves gaps rather than inventing volume. That defensive gap behavior is not yet compared with TradingView.

The catalog now has131definitions. Seven maintained study libraries pass24independent Decimal50 cases each (10800numeric values/source; maximum absolute error1.92e-12), plus empty/missing-volume checks.58existing chart regressions pass. Hosted DeltaETHUSD30m Candles shared view: both separate panes and two plots each render at desktop and narrow widths; EMA255 visible and NVI4px styling verified. The browser CSV download observation timed out with no received file path; no hosted numeric-export parity is claimed. Temporary studies removed, viewport reset, testtab closed; no saved preference/order/runner/service reload action.

Published static libraries and cache suffix volume-indices=20261119-1 in all7maintained sources. Evidence: .private/chart-order-rollouts/volume-index-studies-20261119/{manifest.json,decimal-audit.json,regressions.tap}; verifier scripts/verify_volume_indices.py.

Primary reference: https://www.tradingview.com/support/folders/43000587405/; https://www.tradingview.com/support/solutions/43000773005-negative-volume-index-nvi/; https://www.tradingview.com/support/solutions/43000773006-positive-volume-index-pvi/. Catalog review also identifies remaining OHLC-based gaps such as TWAP, standard ADR, Chop Zone, Woodies CCI and Pring's Special K; fundamental/on-chain/market-breadth indicators require their own real data and must not be fabricated from OHLC.

### Standard ADR and volume-index input validity — 19 November 2026

Added standard Average Daily Range (132 catalog definitions), using average(high-low), equivalent to average(high)-average(low), on the selected chart bars. It remains distinct from ATR (which includes previous-close gaps) and ADR%. Default length14 follows existing project range-study defaults; exact native TradingView default-setting parity is not claimed. Existing line color/width/style/visibility controls apply. Seven sources each pass12Decimal50 cases (3652numeric and248warmup values; maximum error3.85e-12);58existing chart regressions pass.

Caught and corrected an input-default defect introduced with NVI/PVI: EMA255 exceeded the shared field's250 fallback maximum. Both definitions now explicitly permit up to2000; the mathematical calculation is unchanged. A reusable default-validation regression checks all catalog length defaults plus NVI/PVI255 across7sources. Hosted NVI field value255,max2000,validity.valid=true,rangeOverflow=false verified.

Hosted DeltaETHUSD30m shared chart: ADR14 renders at desktop/narrow widths,4px style applies. Temporary ADR/NVI studies removed, viewport reset and tab closed. No orders, runners or service restart. Selected-source CSV and native TradingView export numerical parity remain unverified. Settings-close instability was observed after changing line width (NVI and ADR): first close left the dialog open; a second isolated click closed it. Cause is not established; followup recorded rather than hidden or speculatively patched. Calculation-timeframe controls on the new studies also need review.

Evidence: .private/chart-order-rollouts/adr-study-20261119/{manifest.json,decimal-audit.json,default-validation.json,regressions.tap}. Current static query adr-study=20261119-2; prior header/NVI/PVI changes preserved. Reference: https://www.tradingview.com/support/solutions/43000695003-average-daily-range-adr-indicator/.

### Indicator settings close and new-study timeframes — 19 November 2026

Reproduced lost first close: after a field edit, focusout queues drawLegend, which replaces changed row markup between pointer-down and click. Extended the existing defaults-action pointer guard to the close action, retaining the focused field until click dispatch. The baseline fails the close-sequence regression; all7candidates pass4focused cases, and73related chart tests pass. Hosted ADR/NVI width-change then single-close passes at desktop and narrow widths; ADR calculation-timeframe-change then single-close also passes. Keyboard and other action-button coverage remain separate followups.

Added ADR/NVI/PVI to the existing selected-broker calculation-timeframe set. Hosted DeltaETHUSD30m ADR14 switched to1h with Wait for timeframe closes enabled. Display14.85 agrees with independent public Delta connector14completed-hour data: high-low sum207.95,mean14.853571428571428. Exact integer-cent sum20795 avoids an independent-reference floating-point summation assumption. This is one displayed-value check, not a full historical or native TradingView comparison. NVI/PVI higher-timeframe numeric/rendering matrix and existing Candles/Line restrictions remain explicit.

Static publication in7maintained JSsources/cache suffix settings-close=20261119-1; no service restart, runner or order action. Prior Pine/reference/header/indicator changes preserved. Temporary studies removed, viewport reset and testtab closed. Evidence: .private/chart-order-rollouts/study-settings-close-20261119/{manifest.json,tests.json,baseline.tap,regressions.tap,hosted-evidence.json,native-adr-hourly-reference.json}.

### Delta channel-order and chart-only catalog activation review — 19 November 2026

Current canonical and registered Delta-owner ingest classes each pass all4channel-order regressions. Removed the obsolete test skip so the cross-channel case always runs: an older exchange timestamp from a different candle channel must populate that channel without rewinding the executable symbol tick or emitting an older callback. Four chart-catalog permission tests pass. Fresh isolated public PAXGUSD1m/5m/30m65.19s sample retains all channels, callback timestamps monotonic. This is an isolated ingest sample, not hosted activation or evidence that the defect caused every earlier delay.

Fresh preflight:3canonical current Delta runtime states stopped; registered credential identity verified; native positions0,open/pending orders0,no further order page. WorkerPID3797692cwd matches Delta-owned source and has no direct children. The only production Python sources newer than process start are chart_catalog.py,web.py,delta_broker.py. No service/runner/order mutation occurred. Exact per-process loaded module hashing remains unavailable; source mtime and deployment evidence distinguish staged from activated.

Seven current frontend candidates rebased only the catalog URL to /api/chart-workspace/catalog, preserving all newer Pine/reference/layout/indicator fixes. Syntax passes; not published ahead of backend activation. Concrete bundle: .private/chart-order-rollouts/delta-chart-activation-ready-20261119/manifest.json. Specific Delta-only worker reload approval requested; recheck guards immediately before any approved action. AGENTS.md requires specific reload authorization. Main service and other broker workers are outside this request.


Delta chart reliability activation, 19 November 2026: specific user approval consumed once. Managed Delta-only worker reload reached READY (PID 116691); three stopped runner state files retained identical SHA-256 hashes. Fresh native postflight: zero positions and zero open/pending orders. Published the chart-scoped catalog URL in seven current frontend snapshots, rebased to preserve current TWAP/settings fixes. Hosted administrator chart search returned 1,318 catalog instruments and one PAXGUSD match; selecting it produced a Live 30-minute candle with OHLC. Regular-user permission matrix and exhaustive live-channel coverage remain unverified. Evidence: .private/chart-order-rollouts/delta-chart-activation-ready-20261119/.

TWAP verification, 19 November 2026: hosted Delta ETHUSD 30m Candles rendered custom 6h/14h/22h/23h anchors after native frames arrived without a cosmetic setting change. Desktop and narrow settings checked. 56 anchor regression cases across seven frontend sources passed, including first/new opening redraw and incremental price-only updates; 17 related default/settings/live-reference checks passed. Hosted CSV independently audited using Decimal50 for complete visible six-hour anchor groups; see twap-study-20261119/hosted-numeric-audit.json. Native TradingView export parity and all broker/chart-type matrices remain unproven. NVI/PVI hosted CSV audit also recovered and passed 3,996 numeric comparisons, see volume-index-studies-20261119/hosted-numeric-audit.json.

Current drawing attribute check, 19 November 2026: created an isolated temporary trend line with Option+T; applied purple #7b1fa2,4px,dashed,and both extensions. Reopened settings and verified every control value. Narrow modal client/scroll widths both459px. Option+Shift+2 selected favorite Horizontal ray. Removed only the temporary trend line and cancelled placement; inherited drawings retained. This is current single-tool settings/shortcut evidence, not full drawing geometry or native TradingView visual parity. Evidence: .private/chart-order-rollouts/drawing-attributes-current-20261119/hosted-evidence.json.

Indicator action fix, 19 November 2026: v8 published to all seven maintained JS sources and21 HTML entrypoints;84 focused checks passed. Pointer interaction keeps edited rows alive through click dispatch, commits fields after delegated actions without timer dependency, explicitly refreshes afterward, and preserves the More menu through summary default-action ordering. Hosted Delta ETHUSD30m Candles verifies first-click Hide and More→Style on desktop and narrow widths. Keyboard Tab after edited length separately loses focus to BODY and remains open; do not claim full settings accessibility complete. No service reload, runner or order action. Evidence: .private/chart-order-rollouts/study-action-focus-20261119/manifest.json.

Keyboard indicator focus fix, 19 November 2026: added native Tab dispatch guard so synchronous field-change redraw cannot remove the destination before navigation. Release on Tab keyup/window blur; leaving the legend flushes deferred markup. Generalized summary toggle ordering so settings reopen on first click after keyboard Escape. All7 maintained sources and21 HTML entrypoints published,126 focused checks pass,7 final JS hashes verified. Hosted desktop+narrow DeltaETH30m Candles SMA verifies Tab/ShiftTab, native typed Length/Offset retention, Escape and reopen; narrow keyboard reaches Close and Enter closes; pointer Hide-after-edit remains correct. Test used isolated shared preferences only, viewport reset and tab closed. Pine/all-broker/all-chart keyboard matrix remains incomplete. Evidence .private/chart-order-rollouts/study-keyboard-focus-20261119/manifest.json.

Hourly volume-index and header-menu verification, 19 November 2026: NVI/PVI255 on30m DeltaETHUSD independently checked using actual hosted998-hour broker response. Candles closed368values, one coherent live forming-hour snapshot4values, Line closed368values all match Decimal50 reference (max error2.32e-12). Actual Line selection exposed a responsive stacking defect: drawing toolbar intercepted the menu's Line button as Hide drawings. Conditional header z12 fixes it in7CSSsources/21HTML entrypoints. All4 type-menu centers now hit intended controls on desktop+narrow, actual Line/Candles selection verified. No runners/orders/restarts, temporary studies removed and saved preferences retained. Evidence .private/chart-order-rollouts/volume-index-timeframes-20261119/manifest.json and .private/chart-order-rollouts/chart-header-menu-stacking-20261119/manifest.json. Other intervals/brokers and synthetic-chart calculation semantics remain incomplete.

Pring Special K, 19 November 2026: added official documented12 weighted ROC/SMA components, default100/100 double-SMA signal,7sources,725-bar minimum notice,existing style/favorite/calculation-timeframe controls and0reference.134 builtin definitions now present. Independent Decimal50:46cases and30,765 numeric comparisons per7library, plus76,623 warmup nulls each; hosted999-bar export352 numeric values and1,646 nulls match independent reference. Hosted DeltaETH30m Candles default and1h Closed render, width4retention,7sources,and143-week insufficient-history notice validated; notice clears returning30m. Fixed shared tab label/radio activation after select edits,210checks anddesktop/narrow validation. No service restart/trading actions; tempstudy removed/savedpreferences intact. Native TradingView export and all broker/chart matrices remain incomplete. Reference https://www.tradingview.com/support/solutions/43000773011-pring-s-special-k/ . Evidence .private/chart-order-rollouts/pring-special-k-20261119/manifest.json and .private/chart-order-rollouts/study-settings-tab-focus-20261119/manifest.json.

Woodies CCI, 19 November 2026: added documented HLC3 CCI14/TCCI6 and slow histogram,4neutral/5thwarning/6thtrend palette,flat0handling,stylepalette and existing timeframe controls.135builtins now present. Fixed existing MTF color loss: closed alignment retains per-bar colors; main/alternate forming tails update value and color together. Three baseline color tests fail beforepatch. Independent Decimal50 across7libraries:16cases,15,447 numeric and7,100 color values each,5,853 nulls each. Hosted chart30m/hourly closed exports5,963plotvalues plus3coherent live-hour tail values match reference; maxclosederror3.38e-11. Source fixture and screenshot color checks, notCSV color export/nativeTVparity. Fixed first checkbox/control-label clicks after field edits; disabled controls never arm guard.434 related checks pass, desktop/narrow settings andlabel/control Closed/Forming transitions verified. No reload/orders/runners, sharedtemporary study removed andviewport reset. Evidence .private/chart-order-rollouts/woodies-cci-20261119/manifest.json and .private/chart-order-rollouts/study-checkbox-focus-20261119/manifest.json. Reference https://www.tradingview.com/support/solutions/43000594673-woodies-cci/ .

Heikin Ashi study timeframes, 19 November 2026: expanded builtin calculation controls from Candles/Line to HA. Each requested broker timeframe receives its own recursive HA transform; forming tail uses the final confirmed HA source candle. Native history is not mutated, Candles/Line retain raw data. Technical Ratings transforms off-chart source frames and leaves on-chart HA untouched.623 regression checks across7sources pass. Hosted DeltaETH30mHA SMA5 ofOpen and ATR14 RMA on1h:1,998closed values plus1,996unchanged historical forming-export values and2forming tail values independently match Decimal50 broker-derived reference. Every checkedvalue differs from native OHLC basis; maxerror2.71e-12.11forming frames share HAopen/high/low and match, not proof of every-tick responsiveness. Desktop/narrow controls and6/14/22/23hoptions inspected; HA→Candles→HA retains hour/source. Technical Ratings table numeric hosted acceptance, otherbrokers/customintervalvalues, Renko construction/alignment semantics andnativeTVexport parity remain incomplete. Static7JS/21HTML publication only,no restart/tradingaction; temporaryATRremoved andsharedviewclosed. Evidence .private/chart-order-rollouts/heikin-study-timeframes-20261119/manifest.json.


Renko reference investigation, 19 November 2026: explicitly approved separate TradingView layout https://www.tradingview.com/chart/a8i8XP9T/ created, existing layouts preserved. Reopened copy initially retained Candles, so Renko and new built-in SMA5 Close with Calculation1h and Wait for timeframe closes were explicitly saved; All changes saved observed. Native5m NIFTY ATR5 box20 renders hourly SMA25460. Native method options ATR/Traditional/Percentage LTP and full study timeframe menu observed. This establishes native control availability, not numerical parity. Offline actual-library diagnostic on captured Delta996half-hour/498hourly bars quantifies different brick counts and historical SMA states for a common candidate seed. Four scenarios each compare498source-availability snapshots; differing255/85/206/18, latestSMAequal. Source availability bounds must not be treated as native brick close times. Diagnostic script scripts/diagnose_renko_study_timeframes.py and .private/chart-order-rollouts/renko-study-timeframe-diagnostic-20261119/report.json. No production calculation controls enabled, no restart, runner or order changes. Next: fixed-box native exports and confirmed/forming alignment.


Native Renko numeric checkpoint,19November2026: two300-row TradingView exports from approved separate layout DeltaETHUSD.P Traditional10 Close wicksOFF, host30m and1h, SMA5Close Calculation1h WaitclosesON. Shared captured-broker window1793304000..1795096800 yields212+192native bricks:all1616OHLC values exactly match current-library diagnostic;404native timestamp sourcebins match. Independent Decimal50 native1hrollingSMA5 agrees296values exactly. Lower-chart hourlySMA includes74nulls in212rows; finalMA1790versus1hchart1794 atsame1795100400. Do not collapse multiple synthetic bricks bysourceTime or assume ordinary candleclose alignment. Native export wait timedout but actual downloaded files verified and preserved; no duplicate download. scripts/verify_native_renko_timeframe_exports.py and .private/chart-order-rollouts/native-renko-study-timeframe-20261119/audit.json preserve checksums/results/limits. Exact syntheticclock, startingseed/generalhistory, allmethods/brokers and confirmed/forming merge remain incomplete. No production changes/reloads/runners/orders; reference explicitly saved ETH1hTraditional10.


Native Renko historical merge checkpoint,19November2026: extended actual-export verifier with exact per-source duplicate clock reconstruction (sourceopen+1ms peradditional brick),404selected timestamps match. Historical requested-hourly SMA gaps/values follow next-brick-close event merging into host(open,nextbricktime];297comparable rows match196values+101nulls exactly. An ordinary fixed1h source-close alternative disagrees119rows, a meaningful regression counterexample. Finaltwohost/source rows deliberately excluded; live/projection finality notestablished, no extrapolation into production. Updated audit .private/chart-order-rollouts/native-renko-study-timeframe-20261119/audit.json. Nextverify formingtail then implementdedicatedRenko calculationcontrol path.


Renko history implementation checkpoint,19November2026: new canonical chart-renko-study-alignment.js stages pure syntheticclock/nextbrickclose study merging. Not imported/served or copied to brokerowners.12tests pass, including297actualnative exported historicalrows, multibrick colors/gaps, immutableinputs, collision/error guards, confirmedprefix stability and refusal to derive closes from projected source/hostbricks. No known-close inference from fixeddurations. Tests .private/chart-order-rollouts/native-renko-study-timeframe-20261119/helper-tests.tap;manifestrecordsSHA. Live/projection finality remains next required check before UIintegration. No production behavior change/reload/order/runner action.


Renko native confirmation switch checkpoint,19November2026: captured unchecked Waitfor timeframecloses export and refreshedchecked export; checkboxverified bothmodes, restoredchecked, AllchangesSaved observed.300rows each,1500OHLC/timefieldsunchanged.Offhas0gaps, refreshedchecked101gaps; all300offvalues equalcarryofrefreshedchecked values. Olderchecked differs onlyfinal2rows(empty/1790 becomes1790/1794), so tailcannotbe treated as immutablehistoricalproof. Stagedhelper now optional gapsfalse carrywithcolors,14tests including297native rows eachmode(594total); no fabricatednewsourcecloses. No UIactivation; live/projection finality remainsunproven. Evidence native-renko-study-timeframe-20261119/gap-mode-audit.json andhelper-tests.tap.


Saved pane reload checkpoint,19November2026: actual hosted main-dashboard Delta chart with inheritedV1/OBV, non-shared browser-persisted layout. Initial automatic price/OBV(no customstyles);ArrowUp divider changesprice480px andOBV134px. Full own-tabreload retains480.00003px/133.99306px andsaved480/134stylevaluesexactly. Home restoresoriginalautomaticpriceandOBV124px;secondreloadconfirmsno custompaneheight/flexbasis andOBV123.99306px. Temporarytabclosed. No resetreproduced onselecteddesktopcase; narrow/alllayouts/brokers notgeneralized. Evidence chart-pane-reload-persistence-20261119/hosted.json;screenshot /private/tmp/chart-pane-resize-survived-reload.jpg. No productioncode/restart/runner/order changes.


Indicator coverage reference checkpoint,19November2026: catalog135 current definitions;missing RobBookerReversal investigated before code. Official help43000599840 describesMACDzero-cross+stochasticKand6inputs, while nativepickercurrentresult isCommunity RobBookerReversalTabs byrobbooker with8inputs12/26/9/70/30/30/70/30,includingStochasticRSIPeriod. No basis to equatevariants or claim defaultparity. No guessedstudyadded; exactvariant/formula/nativeexportneeded. Temporarystudy removed from approvedtestlayout,AllchangesSavedobserved,tabclosed. Evidence reversal-study-reference-20261119/reference.json;notproductionimplementation.


Drawing reload checkpoint,19November2026: actual nonshared mainDeltaBTC30m testtrendline createdOptionT/twopointeranchors. Initialblue#2962ff1pxsolid/noextension; appliedpurple#7b1fa2,4px,dashed,left+right,Usefornewdrawingsunchecked. Fullpagereload thenmanagerEdit reopens exactcolor/width/style/bothextensions.520x900modal client/scrollwidthboth459,valuesunchanged. Cancelled,viewportreset,removedonlytemporaryTrendline1; inheritedhorizontal65111.21retained;tabclosed. No defaultstylechange/code/reloadservice/order/runner actions. One-toolselectedbrokerproofonly;favoritespersistencenotcovered. Evidence drawing-attribute-reload-20261119/hosted.json and /private/tmp/drawing-attributes-survived-reload.jpg,/private/tmp/drawing-attributes-reload-narrow.jpg.


Concurrent drawing-addition fix,19November2026: actual mergeSavedDrawings baseline3of6casesfail whenboth tabs append same-symbol or inactive-symboldrawings, losingremoteadditions. Preserveboth unambiguousappend-onlybranches withbaselineprefix unchanged;exactcopiesdeduplicated bymaximumobservedmultiplicity, originalarraysimmutable. Existing localconflictpolicy retained foredits/deletions/reorders;combined>100drawings fails explicitly ratherthan latertruncation.10focusedcases×7sources70pass,64candle/settings/layerregressionspass. Published7frontends+21HTML drawing-merge=20261119-1,overlaySHAupdatedwithentriespreserved. HostedmainDeltaBTC30m Debuggerloadedsourcecontainsnewmergeandlimitguard. Twoowntabs createone testtrendlineeach,bothpresentafterfirsttabfullreload;bothremoved,secondtabreloadconfirmsnocopies,inheritedhorizontal65111.21retained,tabsclosed. This issequentialhostretention,notforcedoverlap;racereproductionisactual-sourcefixtureproof. No service/workerreload,runner/orderaction. Evidence drawing-concurrent-additions-20261119/manifest.json and /private/tmp/two-tab-drawings-retained-after-reload.jpg.


Renko confirmed-tail timing,19November2026: source1h15UTC closes16UTC. Native30moldexportmtime15:58:56precedesclose;1hexport16:06andlater30m16:18/16:20followclose. Prior/currentnative5brickSMA1790/1794reconcileold/refreshedtail;freshpublicDelta1h confirms15UTCclose1781, producing1790reversalbrick on10grid. Earlierapparentmismatchnotstalenessproof. StagedapplyConfirmedRenkoStudyTail modelslatestconfirmedreferenceonlyonlasthostrow,requireslive/freshfeed/cutoffchecks, excludesprojections/historyonly, preservesearlierplotvalues/colorsandinputs.18tests passincludingcaptured1790to1794boundary;liveprojection/runtimeintegrationremainpending.No productionchange/reload/order/runner action. Evidence native-renko-study-timeframe-20261119/confirmed-tail-audit.json,fresh-broker-tail.json,helper-tests.tap.


Renko assembled frontend candidate,19November2026: isolatedcandidate basedoncurrentdrawing-mergefrontend integratesactualcalculateUnshifted withactualrenkoBoxSize, libraryrenko/SMA andnewclock/merge/tailengine. Full998nativebrokerhourlyprefix withoutmanualseed reconstructs192nativehourlybrickOHLC(768fieldsexact),210comparablelowerchartrowsmatch137values+73gaps.21tests pass including18helpercases andactualfrontendpath3cases. Projectionrequestedwithformingframeexplicitlyrejects(candidateonly)ratherthansilentlysubstitutingconfirmed. Notpublished/notenabled. NeedfreshupdatedAtproducer/closed-referencepolling,historyrolloverandprojectedsemantics,then7ownerintegration+hostedacceptance. Evidence renko-study-pipeline-candidate-20261119/manifest.json,tests.tap. No production/restart/tradingaction.


Renko polling candidate checkpoint,19November2026: closedRenko calculationreferencesnowtargetliveframes;actualnativetickupdatedAtretained evenidenticalcandlegeometry,incrementalupdatecalledwithoutforcedfullredraw. Invalid/stale/disconnectedframesclearfreshness. Helpergatealignedwithexistingchart60second/2secondskewrule(supersedesstaged15seconds). ActualhistoryIntervals/refreshCompletedHistory fixtureprovesselectedreferenceincludedandchangedreferenceforcesrecalculationwithoutnewhostbrick.27pipeline/helper/pollingchecks+61HA/TWAP/alternate/live/drawing/focusregressionspass. Candidateisolated,notpublished/controlsnotenabled. Remainingnativeprojectionsemantics,hostedrollover,moduleload+7ownerpublicationandfullmethod/brokercoverage. Evidence renko-study-pipeline-candidate-20261119/manifest.json,tests.tap,regressions.tap. No production/reload/runner/orderchange.


Renko actual rollover checkpoint,19November2026:31combined/helper/polling/rollovercases pass. ActualreconcileHistory exercisedwithcapturednative14/15UTCsourceOHLC at15:58/16:20:completedsourceprefixretained,fullconstructor/SMA/tail1790to1794whilehostbrickunchanged. Olderpagearrivinginflightpreserved;changedgeneration/providerfailureleavebaselineunchanged.61priorcandidate regressionsremainvalid(no candidate sourcechangeinthispass). NativeprojectionattemptfoundapprovedtestlayoutcurrentlyPAXG30mCandlesinsteadpriorETHRenko;brief1mrestored30m,saved/AllchangesSavedverified,tabclosed,newersymbol/typepreserved. Projectionsemanticsremainunverified;no activation. Evidence renko-study-pipeline-candidate-20261119/manifest.json,tests.tap and /private/tmp/reference-layout-restored-paxg30.jpg.


PAXG Renko reference expansion,19November2026: approvedtestlayouttemporarily1m/5mTraditional1and0.1Close/no-wicks,SMA5CloseCalculation5mwaitoff, shownfromoriginalhiddenstate. Nativeexports300/302rows:independentDecimal50SMA296+298=594valuesmatch(max5e-13). Native1m/ref5mhistoricalcarry290rowsmatchesstagedhelper. Currentconstructorfromcapturedfullbrokerprefixmatchesall302tenth-pointnativebrickbodies(1208OHLCfieldswithin1e-8).33focusedtestsnowpass,61priorregressionsunchanged. BrokerformingthresholdcrosswhileobservednativeSMA3666.16unchangeddoesnotproveprojectionsemantics(feedtimingnotcoherent);noactivation. OriginaltestlayoutrestoredPAXG30mCandles,Traditional10ClosewicksOFF,SMA5Close1hWaitONhidden;AllchangesSavedobserved,tabclosed. OfficialRenkohelp43000502284/43000480330clarifiesprojectionsrecalculateuntilsourcecloseandreloadlosesthem. Evidence renko-projection-reference-20261119/audit.json; screenshots /private/tmp/paxg-renko-projection-live-reading.jpg and /private/tmp/paxg-reference-restored-after-projection-check.jpg.


Broker/access refresh,19November2026: isolatedfreshMotilalnativeprofileattemptstillMotilalError auth_required=true;no renewal/masterupdate/credentialortradeaction. Prior evidencepreservedinownrefresh folder motilal-catalog-refresh-20261119T172228Z. Currentreadonlyregistry:2usersbothchartassigned,globalvisibletrue,12routepolicydecisionsallow6chartendpointsperuser.7isolatedassignment/ownership/catalogtests pass. All7maintainedsourcepermissionfunctionsallowchart-onlysixroutesanddeny unassignedsixroutes(84decisions),hashesrecorded. Thesearesource/currentregistrychecks,notloadedworker/authenticatedregularbrowserproof. Noassignment/session/servicechanges. Evidence chart-access-refresh-20261119/registry-policy.json,source-policies.json.

### 19 November: full V1 picker library and revision check

Seven maintained frontends now retain applied custom Pine in a per-user indicator library. Adding clones exact source and study settings; the red-bar reference remains separate. AI Renko and custom Pine favorites persist. Existing localStorage/IndexedDB storage supplies the library without a character cap.

Private canonical: .private/pine-unified-20261119/sector-pulse-unified.pine; normalized SHA-256 09e04cb55da6379d8102d710c39f1985b766eace90f2b6cab2bdf2d6bfd38a78. Picker rows expose source revisions. Run .venv/bin/python scripts/verify_chart_pine_revision.py on source or asset releases. This detects stale bundled revision metadata; it does not automatically update external platforms.

Fresh Delta-tab search/add, Favorites persistence/filtering and desktop/narrow picker passed. Canonical V1 rendered on original Delta tab, but its old loaded picker still lacks the full entry. Automatic approval review rejected original-tab refresh; explicit approval remains pending. Do not report original-tab picker fixed. TradingView saved Unified source matched after CRLF normalization, and its original unsaved V1 draft was restored. Dhan current list lacked Unified: canonical copy saved, privately published, applied and protected-source checkbox verified checked. Existing studies retained. No trades, runner changes or service reloads.

Evidence: .private/chart-order-rollouts/full-v1-indicator-picker-20261119/manifest.json. Overall parity remains incomplete and goal active.

### 19 November follow-up: original-tab picker verified; custom removal staged active

The original Delta tab 503428203 was refreshed after direct user approval. Its actual searched Indicators dialog showed Sector Pulse V1 + RSI Zones, Current V1 09e04cb5, and a checked favorite. AI Renko example and saved-script stars were also checked after that reload. Evidence screenshot: /private/tmp/original-delta-full-v1-indicators-search.jpg. This supersedes the earlier original-tab picker blocker.

A subsequent user request added recoverable custom-indicator removal. Trash controls cover saved Pine, the AI Pine example and application-specific reference presets. Removed entries are retained in a per-user browser Removed list; restoring retains source/settings/favorite identity. Applied studies, scripts and drawings are unchanged. The requested red-bar-reference preset was removed, restored to verify recovery, then removed again. Fresh-tab reload retained its removal while full V1 stayed visible and starred; narrow controls fit without horizontal overflow. Seven active maintained sources updated (the extra archived source folder has no current registry account). The original tab requires another separately reviewed refresh to load this later feature; approval requested. Do not claim that later removal control is already visible there.

### Follow-up: original tab removal verified and drawing name alignment corrected

After the user's separate approval, the original Delta tab was refreshed and its Indicators search verified: full V1 remains starred with a remove control; the requested red-bar reference is absent from the normal list and recoverable under Removed. This supersedes the additional-refresh blocker above.

Drawing manager names now use an ellipsized text wrapper next to a compact checkbox, centered in one non-wrapping row. Hosted checkbox/text center difference was 0.0044 pixels; the narrow list had equal client/scroll widths of 335 pixels. Edit still opens Drawing settings with left/right extensions. The one temporary test trend line was removed and chart view reset. Evidence: drawing-manager-name-alignment-20261119 under the private rollout directory. Desktop and narrow screenshots were captured; this is selective evidence, not full visual parity.

Fresh Motilal native coverage is also recorded in the acceptance ledger: 193421 eligible symbols across nine segments, exact native-to-handler membership, zero missing/extra/duplicate IDs. This replaces the earlier authentication-required state for native/handler checks; hosted full-catalog UI verification remains open. No runners, orders or services were changed.

### 20 November: Motilal hosted catalog and native index EOD gap

Authenticated hosted picker checks now cover the first page of all nine native segments, the second NCDEX page, and the first all-segment page: 193421 total instruments; all 1005 returned rows and metadata exactly match the fresh native snapshots in handler order. NCDEX page 2 shows 101–200 of 2261 with zero overlap with page 1. No segments report unavailable. This is sampled hosted pagination plus the earlier complete handler membership audit, not exhaustive UI traversal. Original GUARSEED1018DEC2026 selection restored, temporary tab closed.

Opening Nifty 50 exposed empty 1D history despite an exact native NSE EOD row. The calendar-history path explicitly excluded indices. A one-condition fix is staged in root and the dedicated Motilal owner; unrelated broker snapshots have older unused Motilal paths and were preserved. Seven new regressions pass against root and dedicated owner; 20 existing Motilal tests pass. Tests reject forming EOD, wrong-token substitution, incomplete weekly history, and expired authentication. A native NSE/BSE comparison checked 105 index masters: 81 published EOD rows matched OHLCV exactly; 24 had no native EOD row and remain unavailable. No historical backfill or live-price parity is claimed.

Evidence: .private/chart-order-rollouts/motilal-catalog-refresh-20261119T173234Z/hosted-catalog-comparison.json and .private/chart-order-rollouts/motilal-index-eod-20261119/. Current status SOURCE_STAGED_WORKER_RELOAD_REQUIRED. Read-only preflight: three stopped runner states, native positions/open orders zero, unresolved intents zero, worker PID 3517452 scoped to Motilal source at port 8105. Separate Motilal-only reload approval requested; no reload or trade performed.

### 20 November: Motilal index EOD activation verified

The user specifically approved the Motilal-only index-candle reload. Fresh preflight passed and the guarded workspace_bounce command replaced PID 3517452 with 203295 at the existing owner port 8105, portal port 8080. Readiness and postflight passed; all three runner-state hashes are unchanged, with zero native positions/open orders and zero unresolved strategy intents. No trade or runner activation occurred.

Hosted Nifty 50 MO:INDEX:NSE:26000 and Sensex MO:INDEX:BSE:999901 each now return the exact 19 November native EOD OHLCV row through the authenticated history route and render in the chart. These routes returned no index daily bars before the change. The original NCDEX GUARSEED1018DEC2026 selection was restored, and the temporary tab was closed.

Evidence: .private/chart-order-rollouts/motilal-index-eod-20261119/manifest.json and hosted-activation.json. This supersedes the pending-reload status above. It proves selected completed daily native index candles, not broad older-history, tick, or full TradingView parity. The 24 indices without a native EOD row are not filled from another source.


### 20 November: isolated native Close-source Renko projection evidence

The separate TradingView layout is saved as **Sector Pulse** (2aOvlIxx). The read-only capture and reproducible audit are in .private/chart-order-rollouts/renko-projection-isolated-20261120/. The staged, unserved closeRenkoProjection helper reproduces 83 native projection updates, including 71 partial final bricks, without mutating confirmed bricks. It is not yet connected to production charts or indicator calculations. Native five-minute study rollover and generalized ATR/percentage/OHLC behavior remain unverified. Later native events were evicted from the browser buffer; the audit claims only the preserved capture window.


### 20 November: native live five-minute reference close

Preserved 2,492 native chart/quote packets and 1,114 broker frames across the 19:10 UTC five-minute source close. All 26 published native SMA updates match the completed five-minute reference calculation on both sides of the boundary. The newly closed 62,755 candle remained inside the reference reversal gap and generated no new confirmed brick; SMA remained 62,760. This verifies the no-new-brick boundary case, not a value-changing live rollover. The staged wait-off path now carries confirmed reference values without rejecting a developing feed candle. All seven owner candidates are rebased onto their current source while preserving drawing controls and Pine library/removal. No production frontend or controls activated. Evidence: .private/chart-order-rollouts/renko-live-rollover-20261120/.


### 20 November: value-changing reference close and multi-row publication fix

A fresh native capture spans the 19:15 UTC five-minute close: broker close 62,693.50 added four confirmed reference bricks. Native SMA progressed 62,750, 62,740, 62,730, 62,720, exactly matching the constructed reference sequence. Captured native rows exposed a staged defect: only the last host row received the newest confirmed value, leaving prior newly published rows at 62,770 instead of 62,760. A request-and-settings-scoped publication cache now updates the previous current row and every newly appended row, retaining earlier published rows and colors. Replay bypasses the cache; stale data cannot create new publication values. The combined helper matches 47 row comparisons in two native captures; the actual extracted frontend path matches 12 value-changing rows. All 42 focused checks and seven candidate syntax checks pass. Source drift checks confirm production remains unchanged. Still staged, not served; generalized ATR/percentage/OHLC and hosted activation remain open. Evidence: .private/chart-order-rollouts/renko-value-change-20261120/.


### 20 November: Traditional OHLC calculation-timeframe native regression

Fresh native BTCUSD Renko size10 OHLC exports verify 276 completed five-minute bricks and 298 completed one-minute bricks against fresh broker OHLC (2,296 price fields and 574 source/synthetic clocks, zero mismatches). The five-minute chart SMA matches 276 values; the lower chart's five-minute calculation matches 246 confirmed historical rows. Partial initial source candles and developing/unclosed reference tails are excluded explicitly. This closes the selected Traditional OHLC historical case, not dynamic projections or all-method parity. The Sector Pulse layout was restored to 1m Traditional10 Close, wicks off, and All changes saved was verified. Evidence: .private/chart-order-rollouts/renko-ohlc-reference-20261120/. No production activation.


### 20 November: ATR14 Renko sizing mismatch identified, not resolved

Native BTCUSD five-minute ATR14/Close/wicks-off Renko exports contain 300 bricks of size250. A separate native standard-candle ATR14 export verifies all299 Wilder recurrence updates exactly. At the latest common completed candle, native ATR is169.16331941524496 and broker-derived ATR169.1633194786837, both rounded to169 on the native broker0.5tick. Current Renko ATR sizing therefore differs by81points; do not mark native ATR Renko parity achieved or replace the formula with250. Across298 older common candles,12 OHLC fields differ between native and broker snapshots (largest ATR difference2.5); these are preserved in the audit rather than reported as all-source agreement. Native ATR Renko sizing root cause remains open. Temporary ATR study removed, Sector Pulse restored to1m Traditional10 Close with All changes saved. Evidence: .private/chart-order-rollouts/renko-atr-reference-20261120/. Production unchanged.


### 20 November: Traditional higher-timeframe controls activated

Published35static assets across seven maintained sources and21HTML entry pages. The Renko engine is bundled into the existing chart-workspace-studies.js route, avoiding a backend reload. Traditional Renko now exposes supported higher calculation intervals, including6h14h22h23h, with closed/continuous publication modes. Fresh hosted Delta BTCUSD1m/SMA5/reference5m renders62560, matching a fresh public broker-history reconstruction. Both modes and fresh-tab persistence verified; settings fit desktop and577CSSpx viewport. Temporary study removed, four original studies andCandles30m restored, ATR7preference restored, viewport override cleared. Original user tab not refreshed. Fifty focused checks,43existing UI/study regressions and14syntax checks pass. ATR andPercentage remain excluded from this new path; full scope remains partial. Evidence: .private/chart-order-rollouts/renko-traditional-activation-20261120/manifest.json.


### 20 November: Percentage-LTP native sizing matrix

Captured36 completed native series calculations:17BTCUSD,12PAXGUSD and7ETHUSD cases. A candidate tick-aware significant rounding helper in chart-renko-sizing.js matches every captured box size, with no symbol-name branches. Equal raw price ranges prove a universal raw-price adjustment is insufficient: approximately625 becomes500forBTC and600forPAXG. Initial fast header samples showed stale sizes and are excluded; captures require a populated native series plus matching series_completed generation. The rule is inferred and staged only; full brick histories, projection/rollover and Percentage calculation-timeframe activation remain open. Sector Pulse native layout restored toBTCUSD.P1mTraditional10Close/wicks-off and saved. Evidence: .private/chart-order-rollouts/renko-percentage-reference-20261120/audit.json.


### 20 November 2026 — Percentage follow-through audit

Current root source passes10 focused tests covering36 sizing cases,1183 captured native bricks and1095 SMA values. Saved hosted comparison PAXGUSD1m Percentage0.01% box0.35 with SMA5/ref5m continuous shows3664.15, matching served-history and separate broker-history reconstruction. Earlier initial/rollover one-brick differences remain unexplained; the independently tested completed-reference guard is not proven to explain them. Final guard loaded-browser SHA remains unverified.

Subsequent root embedded-Renko isolation changes were observed and preserved; publication hash drift is listed in the continuation evidence rather than overwritten. Cleanup observed: PAXGUSD Candles/5m, four original indicators, ATR7, Percentage input1, temporary SMA5 removed, viewport reset, owned test tab closed. Desktop/narrow578CSSpx screenshots inspected; no document horizontal overflow in selected narrow view. Original user tab untouched. No reload or order. Final name: Sector Pulse. Full acceptance remains partial. Evidence: .private/chart-order-rollouts/renko-percentage-activation-20261120/continuation-verification.json.


### Fresh ATR reference probe

Completed native websocket generation s78 (ATR1, request verified) contains300 bricks of500 points; s79 (ATR14 observed in settings) contains300 bricks of250 points. This rules out relying on the stale250 header shown immediately after changing length: the header lagged the completed500 series. A subsequent300-candle native5m capture calculates ordinary ATR14 about201.85 on its last completed bar, but this source snapshot was later, so it is not a synchronized size-error comparison. Metadata buffers include older-generation updates. No inferred rounding rule or production ATR change is justified yet. Next: capture a synchronized complete source/ATR generation across lengths and tick scales. Native reference restored to the baseline observed on entry (BTCUSD.P Candles1m, inactive Traditional10/ATR14, wicks off); no save action or trade. Evidence: .private/chart-order-rollouts/renko-atr-reference-20261120/fresh-length-probe-audit.json.


### Same-bucket ATR source comparison

Fresh completed native BTCUSD.P5m generations s86 (ATR13) and s87 (ATR2) each contain300 bricks, of250 and350 points respectively. Their request inputs explicitly confirm length, ATR style, Close source and wicks disabled. Subsequent native candle generation s88 was captured within the same five-minute bucket. Using only its completed source bars through20:35 UTC, current ordinary Wilder/RMA ATR calculates207.8035 for13 and296.7122 for2; tick-rounded candidates208 and296.5 differ by42 and53.5. This proves the discrepancy survives fresh completed native series; stale UI alone cannot explain it. It does not prove which source bar/window native uses or establish a replacement quantizer.

The cached ATR14 attempt lacked a fresh completed generation and is explicitly excluded. Reproducible audit enforces same-bucket capture, request parameters and source finality: node .private/chart-order-rollouts/renko-atr-reference-20261120/synchronized-audit.cjs. Original Candles1m reference and inactive Traditional10/ATR14 settings restored; no production formula, service or order changed. Full goal remains incomplete.


### Close-source partial Renko display activated

Connected the existing native-verified projection helper to chartRenkoBricks for Close source with wicks off. Confirmed history is constructed separately; the projected suffix may end in a partial body at the developing source close. Projection-off and OHLC/wicks-on construction retain their prior paths. No broker/order or runner logic changed.

The old frontend fails the new native integration regression (missing projected brick). The staged frontend matches83 native updates including71 partial-body cases;57 focused/regression checks pass and7 source variants pass syntax validation. Published28 static assets with per-account overlay hashes/backups. Hosted shared Delta BTCUSD1m Traditional10 view displayed a projected62130→62132.5 body matching the source close. Desktop/narrow578CSSpx reviewed; no document horizontal overflow. Screenshots were later ticks and rollover, so their data window can show a prior confirmed brick while the header tracks the live projection. Existing narrow table crowding remains. Shared test view did not overwrite saved preferences; owned tab closed and viewport reset, original user tab untouched. No backend reload or trade. Cross-broker/method live acceptance and ATR sizing remain open. Evidence: .private/chart-order-rollouts/renko-close-projection-activation-20261120/manifest.json.


### Partial Renko tail update performance and settled tables

A changing final projected body with the same time/source/open now uses mainSeries.update for its existing point. Projection removal/reversal and reused geometry still replace the suffix and invalidate stale Pine frames. The extracted actual frontend15001-point fixture fails before the change and passes with one chart-point update afterward;120 relevant checks pass, including drawing, percentage-reference locking, projections and table expansion. Two stale fixtures now supply their missing position classifier/sizing library; the percentage lock fixture still exercises different load and replay/reload sizes. Published28 static assets across7 maintained sources; no backend reload.

Fresh shared Delta BTCUSD1m Traditional10 UI shows a projected62210→62200.5 brick matching source close62200.5. Desktop/narrow577CSSpx screenshots reviewed; no document horizontal overflow. Browser smoke does not quantify CPU or latency improvement. Indicators were hidden only in the unsaved shared view for readability; saved preferences remain intact. Test tab closed, viewport reset, original user tab untouched.

Table resize recheck shows automatic tables briefly remain open during desktop→narrow resize then collapse into three compact headings after the existing callback settles. Earlier crowding screenshot was transient, so no speculative table patch was applied. Solo-price unused vertical space after hiding studies remains a separate visual issue to investigate. Evidence: .private/chart-order-rollouts/renko-projection-tail-update-20261120/manifest.json. Full goal remains incomplete.


### Sole price pane fills unused space while preserving saved heights

Baseline hosted shared Delta chart had no indicator panes but retained custom548px price height inside897px stage, leaving an unused divider and blank space. CSS now lets the sole price pane flex to available height and hides its divider; the saved custom-height attribute/value and settings remain intact. When an indicator/comparison pane exists, prior multi-pane CSS resumes. Published28 CSS/HTML assets across7 maintained sources with overlay hashes/backups; no JS, service, runner or order change.

Hosted verification: desktop price896.91 of897px; narrow549.82 of550px, document/scroll width578px; both hide the unused divider. Showing indicators on Candles restored2 panes, price547.99px and saved548px, with divider visible. Reviewed desktop/narrow screenshots. All changes were in an unsaved shared test view; preferences unchanged, owned tab closed and viewport reset. Other owner rendering, editor docking and maximized/comparison combinations remain partial. Evidence: .private/chart-order-rollouts/solo-price-pane-layout-20261120/manifest.json. Full TradingView acceptance remains unproven.


### Fresh FYERS four-chart hosted matrix

Authenticated shared FYERS NIFTY50 30m loads without setup/reconnect and labels Outside trading hours. Candles, Line, Heikin Ashi and Renko each rendered on desktop and narrow;7 measured layouts have document width equal scroll width, with the additional narrow Renko screenshot reviewed. Line CLOSE25514.3 equals broker candle close; final session candle15:15→15:30 is shown. Selected13Nov11:45 HA close25129.04 matches broker OHLC average25129.0375; open25187.79 agrees with rounded preceding HA values25187.795 within0.011, and high/low match. Traditional10 final confirmed Renko brick25500→25510 links to broker source close25514.3. These are displayed-point/availability checks, not full source/native parity. AI Renko script intentionally excludes HA in its source guard. Market closed: FYERS live rollover/freshness remains unverified. All actions in an unsaved shared view; original tab/settings preserved, viewport reset and owned tab closed; no reload or trade. Reproducible audit: .venv/bin/python .private/chart-order-rollouts/fyers-four-mode-validation-20261120/audit.py. Full goal remains incomplete.


### Motilal native names and global-source follow-through

Global selected Motilal index chart opens with the saved connection. Reproduced a label defect: exact Nifty50 selection still showed MO:INDEX:NSE:26000. Frontend now uses remembered native metadata in selector/header, refreshes after asynchronous metadata, shows readable ticker without duplicated description, and retains exact broker ID in tooltip/API requests. Aborted or superseded responses cannot relabel another instrument.152 checks pass;7 syntax checks;28 static assets per revision published with overlay hashes/backups, no backend reload. One stale pre-percentage fixture now supplies the actual sizing library and checks the current tick-aware result; no sizing algorithm change.

Hosted desktop/narrow577CSSpx: header/selector Nifty50, tooltip MO:INDEX:NSE:26000·Nifty50; all5OHLCV fields remain equal to the saved native EOD row. Shared view only; preferences untouched, viewport reset and test tab closed. Broad catalog search Nifty50 returns6685 all-segment matches and5NSE-index matches, including the exact selected index. This is selective search availability, not full membership proof.

Material remaining data observation: Motilal native EOD reports19-11-2026 and close25227.95; FYERS19Nov displayed close25514.3. Date and values were retained exactly; neither provider is proven correct solely by this comparison. Investigate native source freshness/date semantics before any correction. Dhan Pinaki global shared chart reports ReconnectDhan for NSE_EQ:1333, but its transient test tab disappeared before native response inspection; do not claim verified token expiry or ask for credentials based on an assumed cause. No reconnect/order action performed. Evidence: .private/chart-order-rollouts/motilal-symbol-labels-20261120/. Full goal remains incomplete.


### Native EOD provenance and confirmed Dhan auth requirement

Official Motilal EOD documentation describes JSON/CSV endpoints with a date field but does not resolve publication-versus-session ambiguity for the observed discrepancy. Fresh public native NSE EOD CSV HTTP200 (Last-Modified19Nov19:40:10GMT) contains5731rows; Nifty50 date19-11-2026, close25227.949. Its date/volume agree with authenticated native JSON, and all4prices differ at most0.001 (CSV formatting precision). This corroborates SectorPulse's Motilal display25227.95; it does not prove FYERS25514.3 wrong or justify changing either date/value. Raw snapshot/hash retained.

Fresh authenticated browser request to exact DhanPinaki workspace history for NSE_EQ:1333 returns401 with auth_required:true and message reconnect in Accounts; its symbol endpoint returns200. This confirms an account authentication requirement rather than absent instrument catalog. Invalid/revoked versus expired native authorization not independently distinguished. User reconnect requested; no credential/reconnect action performed.

Authenticated browser mainJS HTTP200 SHA256 matches current Ubuntu root f17dcc306edaf8ccb8fad7fcb8acad339a59a4964b3bd9dfd76081e3ad7653d2. Current root includes reference-close guard, partial Close projections, single-point tail and native Motilal ticker. This closes the selected current-root loaded-asset proof gap, not all source-owner delivery or ATR/live parity. Owned tab closed. Evidence: .private/chart-order-rollouts/motilal-eod-provenance-20261120/manifest.json. Goal remains incomplete.


### Renko volume allocation research — not activated

Added authoritative remote source module chart-renko-volume.js and6 regressions. Captured BTCUSD/PAXGUSD1m/5m native volumes agree with accumulated broker source volume split equally over emitted source groups for197of204 comparable groups. First captured group is excluded because preceding native accumulation is unavailable. Seven native-versus-broker differences remain: adjacent one-unit/ten-unit transfers and3000-unit gaps; their cause is unproven, so no correction/substitution is applied. Native projection geometry287records explicitly carries zero volume; live study publication is a separate unverified requirement.

Allocator preserves price geometry/input objects, conserves available group volume, keeps missing/negative/overflow volume null, and rejects duplicate/missing source/finality mismatches. This module is not referenced by live chart assets yet: existing volume-study restrictions remain active. Next integrate chart/Pine/MTF construction coherently and verify session timestamps and volume-delta capability before exposing volume studies. No backend reload or order. Evidence .private/chart-order-rollouts/renko-volume-research-20261120/manifest.json. Full goal remains incomplete.

### 20 November: selected hosted Renko volume activation

Broker-source volume allocation is published across seven asset owners, with 20 volume studies eligible on Renko. Hosted Delta BTCUSD 1m Traditional10 Close verified Volume/OBV, VWAP rendering, and NVI 5m Closed. Three confirmed bricks display 2,497.67 each: (1,716 carried + 5,777 source) / 3. A projected brick displays zero. Desktop and narrow views were inspected; the577px document has no horizontal overflow. Saved preferences and original user tab were preserved.

Evidence: .private/chart-order-rollouts/renko-volume-integration-20261120/hosted-reconciliation.json. Prior checks:165 regressions,49 owner integration checks,14 syntax checks; two actual Pine worker volume tests additionally pass. Native price geometry1183 rows unchanged,197/204 volume groups match,287 native projected geometry records have zero volume. Seven volume differences, broader broker/study numerical coverage, alternate Pine contexts, and intrabar Volume Delta remain open. The full chart parity goal remains incomplete.

Independent Decimal50 study arithmetic audit subsequently passed306,938 values across27,918 broker-reconstructed bricks in fourBTCUSD/PAXGUSD1m/5m histories. Nine studies:Volume,NetVolume,OBV,ADL,PVT,NVI,PVI,VWMA,CMF. Twenty-period index EMA and rolling windows were compared. This is conditional on allocated volume and does not resolve native feed-volume differences or establish hosted live-publication parity. Reproducible numeric-capture.cjs and numeric-audit.py, auditvolume-study-numeric-audit.json in the activation folder.

### 20 November: Pine tables follow the final host width

Reproduced three automatic tables remaining open after resize to a542px price pane. Added table-position/disclosure refresh to the existing pane ResizeObserver, using the outer price host for main-chart tables and native chart hosts for separate panes. Preserves explicit user open/closed choices. Seven owner-specific patches retain concurrent runtime-marker changes;21HTML cache tags updated, no backend reload. Baseline failed the final-host-width regression;21current-owner resize checks and3existing expansion tests pass,7syntax checks pass. Hosted Delta shared view verifies all3automatic narrow tables closed, desktop automatic tables reopen, explicit opened/closed table choices persist. Indicator-name collapse remains effective. Original tab/saved preferences untouched, viewport reset and test tab closed. Evidence .private/chart-order-rollouts/pine-table-resize-20261120/sector-pulse-pine-tables-host-resize-evidence.json. Other brokers/docked-pane matrix and full parity remain open.

Volume discrepancy follow-up:105broker candles re-fetched around all7affected groups match originalOHLCV exactly. Existing native standardBTC5m CSV has82,596volume at1795115100 versus broker82,597; nativeRenko2×41,298=82,596 and broker2×41,298.5=82,597, so this one group is explained by captured source-feed volume difference. Seven groups remain numerically different; six still lack this source-level explanation. Underlying feed processing cause not identified; no production volume adjustment or provider substitution. SourceCSVcomparison excludes its last potentially forming candle, leaving299source candles. Evidence native-standard-candle-volume-audit.json andnative-volume-refetch-audit.json in activation folder.

### 20 November: FYERS drawing controls and Mac access

Fresh hosted FYERS NIFTY50 30m shared view verifies Option+T two-click Trend line placement. Applied red#f23645,4px,both extensions through toolbar/settings. Exact coordinate dates/prices survive Line→HeikinAshi→Renko; style persists in Renko. Option+Shift+2 selects favoriteHorizontalRay. Narrow577px document has no horizontal overflow; settings Apply/Cancel visible and color,width,left/right options available. Test tab closed, viewport reset, original tab/saved preferences untouched. No production patch required. Evidence .private/chart-order-rollouts/fyers-drawing-controls-20261120/hosted-evidence.json. One selected drawing, not complete89-tool/native construction parity or saved-layout reload.

### 20 November: keep every selected Fibonacci label visible

Hosted Renko44/50/56 example revealed the renderer deliberately skipped labels within15px, hiding50% despite drawing its price line. Replaced dropping with nearest available horizontal slot while preserving each exact price/y coordinate and label hitbox. When horizontal space is exhausted, retain label at its preferred bounded position instead of silently omitting it; extreme crowding can still overlap. Seven owners/28assets activated. Baseline actual-renderer tests fail4labels instead of5;14owner renderer checks,15existing drawing checks,7syntax checks pass. HostedDeltaBTCUSD5m Traditional50 Close verifies allfive0/44/50/56/100 labels on desktop and577px narrow screen, no document horizontal overflow. Decimal prices from62050→62736.92:44%=62352.24,50%=62393.46,56%=62434.68. Custom green44/red56 colors and right extension survive apply/reopen. Three-anchor channel placement and offset/stroke editing also exercised; not complete channel geometry parity. Test sharedview closed andviewport reset; savedpreferences/originaltab untouched. Evidence .private/chart-order-rollouts/fib-label-spacing-20261120/sector-pulse-fib-dense-hosted-evidence.json. Full goal remains incomplete.

Legend stability follow-up: fresh DeltaBTCUSD5m Traditional50 Close Renko shared view collapsed while Pine calculated; after calculation all4names remained hidden with display:none and Showindicatornames4. Narrow577px/desktop2133px resize, shared-only study visibility changes, and MacOptionShiftI expansion/collapse also preserve explicit choice. Earlier screenshot observation of names reappearing is not reproduced and remains unresolved; no code patch justified. Evidence .private/chart-order-rollouts/sector-pulse-legend-stability-evidence.json. Test tab closed andviewport reset, originaltab/savedpreferences untouched.

### 20 November: explicit adaptive pane-height reset

Added Chartsettings→Canvas→Panelayout→Resetpaneheights in seven maintained sources. It clears custom price/study/comparison heights and expanded-height overrides only when clicked. Collapsed/maximized states, colors, studies, chart data and viewport settings are retained. Saved explicit sizes remain untouched otherwise.14owner-focused checks and7syntax checks pass. HostedDeltaBTCUSD5m Traditional50 Renko/OBV sharedview: before price548px and unused156.70px; after price704.70px and unused0px. Narrow577px control usable, document nooverflow andpane bottom fillsstage. Screenshotcontrol inspected. Sharedtestchanges discarded, originaltab/savedpreferences unchanged, viewport reset. No backendreload/order. Evidence .private/chart-order-rollouts/reset-pane-heights-20261120/sector-pulse-pane-reset-hosted-evidence.json. Larger pane/comparison/editor matrix and fullgoal remain incomplete.

ATR follow-up: independent Decimal50 audit of three explicit source-bar hypotheses on the synchronized native capture excludes current minimum-tick RMA sizing at latestcompleted, includingforming, and lastemittedsource as a shared explanation for ATR13 native250 and ATR2 native350. ATR13 candidates208/195.5/194;ATR2 candidates296.5/171/352. Last-emitted ATR2 is close but still differs2points; this is not proof of a formula or permission to fit a coarser quantizer. Official TradingView documentation says ATR uses regular candles and describes higher-timeframe deep-history fallback, but does not specify a rule resolving this capture. Separate reference layout currently controlled by another session was left untouched. No production sizing change. Reproducible reference-hypotheses-audit.py/json in .private/chart-order-rollouts/renko-atr-reference-20261120.

Expanded reset validation on hostedFYERS NIFTY50 30m: threeRSI/ATR/MACD panes filldesktopstage, narrowprice220px andindicators108px with no documentoverflow. CollapsedATR survivesreset; maximizedRSI remainsmaximized duringreset and fillsstage; restore retainscollapsedATR, subsequentATRrestore works. Legendcollapse givesnarrowprice272px with3×124pxpanes. BottomPineEditor desktop/narrow opens; narrowprice120px/3×72px creates12px internalstage scroll and remains an explicit constraint. Editorclose/desktoprestore returns3×124pxpanes. Source/draft unchanged; shared-onlytemporarystudies discarded ontesttabclose, viewportreset, originaltabuntouched. Evidence sector-pulse-fyers-three-pane-matrix.json inresetactivationfolder.

### 20 November: docked editor adapts to pane minima

Resolved the captured12px narrow3-pane overflow by capping the displayed bottomeditor against actual visible pane minima, separators and collapsedstrips. Resize/pane-layout observation recomputes this cap. Saved320px preference remains intact on temporary fitting; explicituserdrag stillremembersits constrainedheight. Guard150px minimum editor for physicallyimpossiblemany-pane layouts, which retaininternalchartscrolling. Sevenowners/28assets activated; baselinefixturefails320vs308,70ownerregressions/7syntax pass. HostedFYERS NIFTY50 30m RSI/ATR/MACD: narroweditor308px,stage342/scroll342,document577/scroll577. Desktoprestoreseditor320px andstage514/scroll514. CollapsingATR restoreseditor320px withstage330/scroll330; restoringATR returns308px/342px withnooverflow. Source/draft/savedpreferences/originaltabunchanged; viewportreset andsharedtesttabclosed. Evidence .private/chart-order-rollouts/pine-editor-pane-fit-20261120/sector-pulse-editor-pane-fit-evidence.json. Larger/comparison/shortscreen matrix remains incomplete.

### 20 November: readable FYERS display tickers

Header and instrument-selector display remove FYERS exchangeprefix and terminal-EQ/-INDEX while retaining native tickerbody/expiry. Canonicalsymbol remains unchanged for lookup,data,orders; headertooltip carriesfullID anddescription. HostedNIFTY50 desktop/narrow andRELIANCE equity verified with exactnative IDs stillin brokerfeed details. Narrowdocument577/scroll577, screenshotsinspected. Sevenowners/28assets,7existingMotilallabel regressions and7syntax checks pass. No newtests for display-only formatting; no backendreload or orders. Savedpreferences/originaltab preserved, viewportreset,testtabclosed. Evidence .private/chart-order-rollouts/fyers-readable-ticker-20261120/sector-pulse-fyers-readable-ticker-evidence.json. Notallcontracts/nativevisualparity.

Dhan current-auth check20Nov04:15–04:20IST: global Pinaki NSE_EQ:1333 chart stillshowsReconnectbroker. Exact-ID catalog query returnsoneHDFCBANK/HDFCBank record; header eventuallyupdateswithnativeIDtooltip, so do notpatchmetadatafrominitialloadingframe. Switching throughvisibleOHLCselector toSubhalaxmi fd46… also requestsreconnectforIDX_I:13 andthelinktargetsfd46… correctly. EarlierSubhalaxmi renewedhistorysuccessis historicalanddoesnotestablishcurrentauth. No freshnativeprofile/HTTPresponse capturedthischeck, so causeexpiry/revocationnotdistinguished. No credentialsentered, noorders, no savedpreferencesororiginaltabchanges. Evidence .private/chart-order-rollouts/sector-pulse-dhan-current-accounts-evidence.json. ExistingPinakireconnectquestionpending; no duplicatequestion. Continue otherbrokerwork.

### 20 November: Renko volume-profile drawings follow selected bricks

Fixed-range and anchored profiles now select certified brick OHLCV through native Renko anchor resolution rather than whole source candles. This retains carried no-brick volume, supports reversed endpoints and anchored extension, and refuses uncertified volume instead of substituting raw candles. Legacy timestamp-only final endpoints include their full source group; ordinary candle behavior is preserved. Baseline middle-brick fixture returned50 instead of20; seven focused cases across seven owners now pass49 checks, with7 existing volume/drawing checks and7 syntax checks. All28 published asset hashes match tag renko-profile-volume=20261120-2. Hosted Delta BTCUSD5m Traditional50 Close Renko: fixed and anchored profile histograms/settings and finite12-row labels inspected desktop and narrow; both narrow document widths577/577. Settings describe estimated Renko brick prices/volume. Original tab and saved preferences untouched; owned shared tab closed and viewport reset. No backend reload or orders. Evidence .private/chart-order-rollouts/renko-volume-profile-bricks-20261120/sector-pulse-renko-profile-hosted-evidence.json and final-asset-audit.json. Fresh native numerical/POC/value-area parity remains unproven; seven source-volume differences persist. Anchored VWAP was not changed. Full goal remains incomplete.

### 20 November: FYERS V1 Heikin Ashi / Renko follow-up

Hosted NIFTY50 30m shared-only V1 finishes in both modes; AI Renko Supertrend also finishes on Renko and correctly rejects Heikin Ashi. Desktop tables compact; narrow577px auto-collapsed table headings preserve chart, no document overflow. All four screenshots inspected. Independent Decimal50 Wilder RSI14/SMA14 from780 completed15m broker-export candles matches HA75.71/66.77(up) at15:30 and Renko74.80/65.91(up) at15:15. Thus observed RSI divergence is source-endpoint selection, not arithmetic. Renko retains18NovSC versus19NovSC onHA; previous week/month also differ. Native TradingView Renko reference-context/end-of-history semantics remain unproven and require investigation; no speculative substitution or production patch. Original tab/preferences untouched; viewport reset and owned tab closed. No service reload/orders. Evidence .private/chart-order-rollouts/fyers-v1-four-mode-followup-20261120/hosted.json and reproducible rsi15-audit.py/json. Full goal remains incomplete.

### 20 November: bounded Pine calendar context fixes stale prior periods

Reproduced actual loadPineCandles exclusion: Renko15:15 cutoff dropped the current partial week, so high[1]/low[1] returned02Nov25131.85/23207.05 instead of09Nov25424.35/24838.75. Both match independently grouped broker15m candles. Added bounded context reconstruction from fully closed selected-broker intraday rows, with coverage/open/exact-cutoff guards; no later snapshot prices, no invented missing volume. Seven sources/28static assets active,42 focused and10 candidate existing checks,16 active regressions,7 syntax checks. Hosted FYERS NIFTY50 30m ATR14 Renko previous week now25424.35/24838.75 exactly; previous month23175.25/22179.9 matches priorHA. Desktop/narrow inspected;577px no document overflow, tables auto-collapsed, explicit expand exposes corrected values. Expanded summary overlaps part of upper row and remains a presentation issue. RSI15:15 and SC18Nov remain unchanged/open. Calendar/trade-count and insufficient-history contexts are not reconstructed; alternate-symbol loader not changed. No service reload/orders; originaltab/preferences preserved, viewport reset, ownedtab closed. Evidence .private/chart-order-rollouts/pine-bounded-calendar-context-20261120/manifest.json; baseline probe underfyers-v1-four-mode-followup-20261120/calendar-context-probe.json. Official Pine high[1]+lookahead_on semantics: https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/ . Full goal incomplete.

### 20 November: expanded Pine table controls no longer cover cells

Explicit expansion now places the summary controls in normal layout flow above the table. Ordinary compact tables retain their existing no-duplicated-title display. SevenCSS owners plus21cache references published; all28 asset hashes match. HostedFYERS NIFTY50 30m ATR14Renko V1 Levels table: desktop/narrow all five first-row headings readable; summary bottom and first-row top adjacent within0.1px subpixel rounding. Narrowdocument577/scroll577. Screenshots individually inspected and compact/expand roundtrip verified. No newtests for reversible CSS-only adjustment. Originaltab/preferences untouched; viewportreset,ownedtabclosed,no reload/orders. Evidence .private/chart-order-rollouts/pine-expanded-table-heading-20261120/sector-pulse-expanded-heading-hosted.json. Earlier bounded-calendar record overlap limitation is superseded for explicit expansion. Compact hover controls retain old behavior; broader table/placement matrix and fullgoal remain incomplete.

### 20 November: native Renko confirms references need not reach session close

Previously occupied separate parity-reference layout became available. Its nativeNSE:NIFTY Renko5m ATR5 was inspected, temporarily switched30m (native ATR5 brick100), then restored5m andsaved; final userSectorPulse layout untouched. Native V1 table showsSC18Nov, not19Nov, and native tooltip-confirmed latest closed RSI times5m15:10/15m15:00/30m14:45, all19Nov. Native priorweek25424.35/24838.75 andpriormonth23175.25/22179.9 agree with corrected hosted context. This changes the next action: forcing hostedRenko references to time-chart15:30 is not justified. Exact same-construction timing stillunproven (hostedpriorATR14/55.65, nativeATR5/100), feeds/seeds differ andnativefullsourcehash notfreshlycompared. Native view hadthree savedSMAhidden andSMA5on60m visible; studies preserved, no drawings/orders/reload. Screenshot and observation evidence .private/chart-order-rollouts/native-renko-reference-timing-20261120. Earlier wording suggesting every earlier Renko RSI/SC endpoint required a fix is superseded bythisnativeobservation. Fullgoal remains incomplete.

### 20 November: same brick construction exposes source-grid differences

Compared native andhostedNIFTY Traditional100/30m/Close/wicksoff. Latest confirmedbody25400→25500 agrees butnativeExtended timestamp15:00 vsbroker14:45. Native actual30mCandle export19Nov grid00/30, broker15/45. NativeRegular selection changesgrid15/45; capturedregularCSV ends14:45, broker15:15. Direct same-timestamp Regularsource comparison 298candles/1192OHLC fields has378differences; preserve providerdata. Independent Decimal15m→nativeExtended grid audit297candles1188fields has313differences. Wholecaptures alsoinclude specialsession5/35-minute anchors, not blanket00/30. ExistingnativePine editor showsUnsavedversion; leftsource/draftuntouched. Separatetimingprobe preparedbutunapplied; actualnativeRenko closeTime stillunmeasured, no fittedminus1ms/offsetpatch. Native originalATR5/5m/Close/wicksoff/Extended andhiddenTradsize36 restoredandsaved. Testhostedtabclosed,regularpreferences/originalfinalSectorPulselayoutuntouched,noorders/reload. Evidence .private/chart-order-rollouts/renko-matched-construction-timing-20261120/audit.json, fourCSVcaptures, source-grid-audit.py/json andnative-regular-candles.csv. Fullgoal incomplete.

### 20 November: all current user chart assignments revalidated

Fresh read-onlySQLite registry audit:2users(1admin,1regular),both chartassigned, globalchartvisible. HostedUserMasterglobalChartworkspacechecked andregularuserChartworkspacechecked; readonlyDOM evidence retains no usernames/emails. Actual require_chart functions withtheir ownerpermissionmodules pass140cases over7sources forhistory/live/instruments/Pineworker routes: assignedvisible/adminvisibleallowed,unassigned/hidden/adminhiddendenied. Seven existing section/catalog regressions pass, includingisolated existing-sessionrevocation andbrokerownership rejection. No productionsettings/users/sessions/credentials/orders/service changes. Existingnew-usercreation stillrequiresadminassignment. Actualnon-adminbrowserlogin/rendering notfreshlyverified; noimpersonation or credentialreads. Ownedadminaudit tabclosed. Evidence .private/chart-order-rollouts/chart-all-user-access-audit-20261120/audit.py/json andsector-pulse-all-user-chart-controls.json. Fullglobalworkspace/allbrokeracceptance andfullgoal remainpartial.

### 20 November: Yahoo forming-calendar activation bundle refreshed

Rebased Yahoo snapshot and nativeinstrumentType propagation onto all7currentfrontendvariants, preserving Motilalmetadata, FYERS historylabels, Renko volume/profiles andboundedcalendarcontext. Historicalsnapshot observation cutoff cannotborrow futureperiodprices; incomplete/malformedsourceperiods failclosed.329frontendchecks(47perowner),36backendtests and7syntaxchecks pass. Fresh^NSEI1W/1M/12Mnativecalls return260/59/4completedrows withseparateprovisionalhistory_onlysnapshots andmatchingclosemetadata. Isolatedlatestpreviewusingfresh12Mpayload rendereddesktop/narrow;Historicalsnapshotbadge/providerasof andDataWindowbounds inspected. Found1pxmodalborderoverflow andstagedborder-boxCSS; refreshedCSSquery verifies2133/2133desktop,578/578narrow.35JS/CSS/HTMLassets remainstaged, productionfrontendunchanged. Backendstagedhashesunchanged, runningmainstillold.8runnerguards pass(canonical20states), systemdcgroupcontainsmainPID3697650only,nobrokerworkers. Newmain-onlyrestartapproval required; recheckscope/runner/exposurebeforeaction. Previewserver,tunnel andownedtabclosed, viewportreset; noorders/prodservicereload. Evidence .private/chart-order-rollouts/yahoo-calendar-refresh-20261120/manifest.json, native-source-check.json, regressionsandpreviewevidence. Fixture doesnotprovehostedactivation/fullYahoohistoryorPinenumericalparity. Fullgoal incomplete.


### 20 November: remaining Renko volume arithmetic and VWAP bands

Eleven additional volume studies passed138independent Decimal50cases (1,032,490numeric values and433,806unavailable positions), complementing the prior nine-study audit. The first positive-volume VWAP observation now initializes its mean directly and its second moment to zero, avoiding a spurious opening band. Published7studyassets and21HTMLcacheupdates; all28currenthashes checked. Hosted Delta BTCUSD5m Traditional50Close VWAP/AutoVWAP bands reviewed at desktop and642CSS-pixel narrow width (scrollWidth642). AutoVWAP omits earlier bricks before its latest anchor, unlike resetting SessionVWAP. Native feed/seed parity, seven native volume differences, all-broker/live-rollover coverage and the full13requirement acceptance remain open. Evidence: ".private/chart-order-rollouts/renko-volume-remaining-studies-20261120/manifest.json".


20 November drawing restoration follow-up: 56 checks across seven maintained sources preserve representative drawing styles and geometry through JSON serialization and the actual restoration filter. This covers seven drawing kinds and invalid-geometry rejection; it does not establish hosted save/reload or complete drawing parity. Evidence: `.private/chart-order-rollouts/drawing-style-restoration-20261120/audit.json`. The FYERS seven-file chart-order bundle remains staged pending specific reload approval; its actual workspace-context response now has loopback regression coverage.


20 November: Correlation - Log added across seven maintained libraries and picker integrations. Decimal60 synthetic audit:24cases,3082numeric and1238missing positions; actual DeltaPAXGUSD5m/BTCUSD25-bar export:973completed values and25warmup positions, maxerror5.40e-14. Hosteddesktop4px andnarrowmaximize/restore verified; teststudy removed andoriginalfour retained. Native default/gap/seed parity andcross-broker/chart matrices remain unproven. Evidence: .private/chart-order-rollouts/correlation-log-study-20261120/manifest.json


20 November Chop Zone: fixed EMA34/30-bar range and nine angle-color bands implemented independently across seven libraries. Decimal65 audit3079column values and3079color assignments covers allnine colors on captured DeltaPAXG andsyntheticregimes. Hosted Delta5m palettecustomization anddesktop/narrowmaximize/restore verified; temporaryteststudy removed. Native same-feed seed/angle/palette parity andallbroker/chart coverage remain unproven. Evidence: .private/chart-order-rollouts/chop-zone-study-20261120/manifest.json
