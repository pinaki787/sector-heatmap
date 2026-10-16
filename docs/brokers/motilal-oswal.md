# Motilal Oswal in the existing Sector Pulse workflows

Current option scope: **bought native ATM calls or puts only; no spreads**. Motilal Handoff/Screener single-leg analysis does not require Greeks. Native contract, nearest eligible expiry, ATM, fresh quotes, liquidity, lot sizing and full-premium risk checks remain required. The proposed FYERS Greeks switch was superseded by this user instruction; it was not implemented. Other brokers retain their existing Greeks gates.


Motilal has a private connection page, not a separate trading section. Select the saved Motilal account in Renko Supertrend, Analysis handoff, Screener or Sector rotation. The existing section permissions and visibility settings apply. Account credentials and daily login remain in Broker accounts / Broker connection.

## Market data and warmup

The default policy is **Motilal data only**, with an explicit per-instrument/account FYERS historical-candle switch in Renko. OFF uses native captures only. ON stages up to five recent session dates from an owner-matched FYERS account, validates the exact underlying and expiry, retains a checksummed private archive, and labels its provenance. Invalid OHLC is retained as rejected evidence; analysis starts after the latest rejected candle. BSE cash history matching validates the exchange scrip code, underlying name and ISIN; native BSE aliases never use guessed order symbols. Targeted bounded refetches repair invalid or conflicting OHLC only with a valid broker replacement; volume-only conflicts retain prices and mark volume unavailable. Native completed candles take precedence, and forming prices and all execution metadata remain Motilal-native. Edits change displayed analysis and the next Start, not an active runner configuration.

 Native index and instrument masters map the underlying to exact Motilal tokens. Native WebSocket ticks are retained in the private account SQLite archive. The capture tracks connection generation, exchange and receipt timestamps, uninterrupted opening coverage, and gaps. Higher-timeframe buckets align with the segment opening. An index code has its own namespace and cannot collide with a cash scrip code.

Missing history stays unavailable. When the history switch is OFF, no FYERS/Dhan candles are used. No invented gap bars or guessed Motilal historical endpoint are used. Renko can warm up from captured completed candles. Manual reference brick sizing requires the configured number of fully completed reference sessions. Sector/Screener/Handoff require substantially longer daily/weekly history; these do not become ready just because the broker is authenticated. Volume-dependent evidence also requires native volume coverage.

The published EOD endpoint is a latest snapshot, not a dated intraday-history API. Its availability alone is not permission to treat it as a backfill. It is not connected to automatic signal history in this revision.

## Native execution

Renko uses the shared engine and persistent per-instrument runner records, with a Motilal execution adapter. Paper stays simulated; Live uses native LIMIT IOC orders after fresh depth, profile/segment/product checks, native whole-lot conversion, funds, pending-order and position checks. A strategy switch or selecting an account does not arm the runner.

Full runner intent tags map durably to unique native tags of ten characters. SQLite intent claims precede each broker mutation. Unknown acknowledgements cannot replay; reconciliation requires exact account, exchange, token, side, product, units, lot size and price evidence. An acknowledged order awaiting the book blocks new entries. A closing sell requires the exact confirmed owned quantity. Unrelated broker orders never acquire strategy ownership.

Shared Handoff/Screener reviewed tickets preserve the chosen account, allocation cap and quantities. They recheck executable depth and capability before submission and consume the review once. A requested Paper ticket is never upgraded to Live. Broker acceptance is not a confirmed fill. A partially completed batch is reported for reconciliation and does not resume automatically.

## Explicit limitations

- Native option analysis preserves the existing Greeks/liquidity gates. The current native feed supplies no complete Greeks; option analysis routes show the evidence unavailable rather than borrowing values or weakening the gates.
- Protected multi-leg spread submission is not enabled for Motilal. It must not become an uncovered short order. The three screener choices remain visible with route-specific eligibility reasons.
- Shared manual cash tickets currently support bought equity. Naked cash shorts are not inferred.
- NSE/BSE/MCX options map through the native master’s explicit `ultoken` parent token, with OPTIDX/OPTSTK namespace checks for index and stock options. MCX futures are matched exactly. Mini and standard families, expiry ordering, lot size and paired Call/Put strikes are validated. Missing or ambiguous linkage stays blocked; no nearest-month guess or FYERS option token is used. Overnight commodity management remains unavailable.
- Motilal fees are not estimated using FYERS/Dhan rates. Gross fill evidence and after-cost P/L are distinct; unavailable costs remain unavailable.
- The user activated a native-only Live Renko runner; read-only state verified it watching with no owned position or pending order. No real order/fill has been submitted by the implementation checks. Order acceptance, fill and management verification remain distinct.

## Maintenance

Broker bounce checks canonical Motilal runner records outside the worker's source directory, native positions/pending orders, and unresolved durable intents. Runners are never automatically armed. Main-service deployment must also check these account-level records, and preserve unrelated broker worker PIDs.

Sessions expire daily at 06:00 IST. Credentials/tokens remain private and are omitted from logs and validation artifacts. Upstream callback logging must continue to redact the `authtoken` query.

## References

- [Motilal API documentation](https://invest.motilaloswal.com/moAPI/APIDocumentation/Introduction)
- [Official Python SDK](https://github.com/motradingapi/PythonSDK)

## Verification

    .venv/bin/python -m unittest sector_heatmap.test_motilal_api sector_heatmap.test_motilal_execution sector_heatmap.test_motilal_service sector_heatmap.test_motilal_server sector_heatmap.test_motilal_shared sector_heatmap.test_motilal_dispatch sector_heatmap.test_motilal_history_seed tests.test_motilal_workspaces -q
    node --test tests/motilal-order-route.test.cjs
    node tests/motilal-renko-mounted.cjs
    SCREENER_UI_SOURCE=outputs/motilal-oswal-integration/shared-route-patch/dashboard-enhancements.js node --test tests/screener-three-routes.test.cjs

    node tests/motilal-history-seed-mounted.cjs

MCX session-calendar reference: [official trading holidays](https://www.mcxindia.com/market-operations/trading-surveillance/trading-holidays). The native Motilal adapter uses its own calendar helper and does not import a Dhan broker adapter.

## Source verification

The canonical local Renko UI now incorporates the deployed Motilal account routing and optional history source while retaining the existing Renko Engine hooks. Mounted-page tests read the canonical `renko-supertrend.js` and `broker-form-routing.js` directly. They verify account-bound Start, source transfer and draft isolation with mocked transport; these tests never submit broker orders. The earlier failed three-way reconciliation was corrected by bringing the RSI input declarations, serialization and control dependencies together. The hosted chart remains on its previously verified revision; local Engine integration is not deployed by these checks.

Backend integration tests pass 116 checks locally; the latest hosted calendar/routing subset passes 53. Actual live order-and-fill evidence remains outstanding.

Native daily analysis now aggregates complete sessions directly in SQLite rather than truncating to the latest 100,000 minute rows. A missing minute or interrupted opening coverage rejects that session; unavailable volume remains distinct from unavailable prices. This removes the retention ceiling but does not supply history that was never captured. The guarded main-service reload preserved 13 stopped records and all four broker workers; no trading runners restarted.

The canonical shared dashboard now carries Motilal account binding for Handoff/Screener, broker-specific capability labels, and review-to-submit account context. The local index includes the routing and account-inventory dependencies. `node --test tests/motilal-shared-preview.test.cjs tests/screener-three-routes.test.cjs tests/motilal-order-route.test.cjs` covers those paths with mocked transport. Native Greeks remain unavailable, so option-analysis eligibility gates and protected spreads remain blocked; these source-parity checks do not remove evidence requirements or establish live fills.

`node tests/motilal-dashboard-mounted.cjs` mounts the canonical shared dashboard, real account inventory/routing and Renko UI together in JSDOM; unrelated strategy widgets and HTTP responses are mocked. It asserts the requested Motilal account is selected and capability requests carry both the native broker and account. This caught and corrected a leftover fixed FYERS input in Handoff. It is initialization evidence, not rendered hosted-browser or live-order evidence.

Native option liquidity now retains cumulative traded volume and open interest from the LTP packet, following the [official SDK packet layout](https://github.com/motradingapi/PythonSDK/blob/main/MOFSLOPENAPI.py). Option analysis accepts these fields only while both LTP exchange and receipt timestamps are fresh; a depth update cannot refresh stale LTP evidence. Negative/missing values remain unavailable. Native Greeks are still unavailable, so this does not bypass the complete-Greeks eligibility requirement. The guarded reload preserved 13 stopped records and four broker workers.

Reviewed risk-controlled batches recheck the maximum-position allowance and current-session booked-loss allowance under the native account lock before each submission. A position opened after review blocks remaining orders; no automatic retry is performed. Regression verification uses mocked native transport and sends no live orders.

Native strategy reconciliation normalizes documented order-status and side casing (`Traded`/`Buy` as well as uppercase) before exact intent matching. Terminal-order checks on entry and exit use the same status normalization. Unknown statuses remain blocked, and account/contract/quantity/tag checks remain required. Mocked reconciliation regressions establish casing compatibility, not actual live-fill evidence.

The maximum-position allowance includes distinct pending native BUY contracts, including externally submitted orders. An existing position and pending buy in the same contract are not counted twice; terminal orders do not reserve a new slot. The allowance is checked at review and again before each submission. A pending buy arriving after review blocks the remaining batch before transport.

The ATM-only change is loaded in both hosted source copies. Tests cover bullish Call, bearish Put, the default Greeks requirement on other brokers, native liquidity failures, a missing ATM quote without nearby-strike substitution, and nearest eligible expiry before ATM selection. No active runner configuration or entry rules were changed; this updates Motilal Handoff/Screener analysis.

Native LONG_OPTION reviewed tickets now resolve direction, nearest eligible expiry and ATM at review. A non-ATM or wrong-expiry contract is rejected even when it belongs to the underlying. Before submission the same native resolution is repeated; a changed ATM contract invalidates the review rather than silently replacing the selected contract. Regression tests cover bought Call/Put sizing and both rejection paths. These changes are loaded; 161 local checks and 49 targeted hosted checks pass. Live order/fill verification remains separate.
