# Investment screening

The Investment section discovers NSE EQ company shares from the public FYERS NSE master and joins public TradingView market data by ISIN. ETFs are excluded. It does not require a broker login, read account positions, or place orders.

## Modes

- Rule-based screening makes no AI call.
- Rules + AI uses the existing server Codex ChatGPT login through codex_handoff. It sends public company evidence only, strips API-key environment variables, disallows tools and has no API-key fallback. It reviews at most ten companies, requested symbol checks first.

Default discovery: within 5% of provider-reported ATH, market cap at least ₹1,000 crore, approximate daily turnover at least ₹1 crore, price above 50/200-day averages, positive 6/12-month returns, and a price timestamp within five calendar days. Turnover is 30-day average share volume multiplied by latest price, not historical average traded value. Thresholds are research defaults, not validated return predictions.

Quality review requires reported ROE ≥15%, revenue/EPS growth ≥10%, and positive P/E ≤60. More than 15% above SMA50 is marked Extended · wait. These rules need sector-specific review. Missing metrics never imply healthy finances.

ATH is a provider available-history high, not independently verified adjusted full history. Scanner fundamental reporting periods are unknown; public NSE filing evidence is collected for AI candidates. Cash flow, balance-sheet solvency, relative valuation, moving-average slopes and benchmark-relative strength are not certified. The application does not automatically assign high conviction or executable buy levels.

## Durable jobs and permissions

POST /api/investment/analyze uses the existing owner-scoped persistent jobs queue. Results and checkpoints persist; navigation does not cancel work. Stop uses /api/jobs/cancel. Interrupted jobs are not automatically replayed. Captured settings, source links, price timestamps, coverage gaps and symbol exclusion reasons are retained in exports and saved results.

Investment is a separate User Master section and sidebar visibility entry. Existing settings are merged by the existing settings store; no saved choice is reset. Hidden/unassigned sections reject new screening submissions. Saved jobs remain owner- and section-scoped.

## Verification on 25 October 2026

Remote tests cover rule boundaries, missing/stale metrics, symbol normalization, section permissions, HTTP visibility rejection, owner-isolated retrieval, safe HTML and decimal display. Hosted rule and Codex modes were exercised on the main dashboard. The observed scan matched 2,361 NSE EQ companies with zero missing market rows and seven default-filter candidates. These counts are a dated observation, not fixed expectations. PASHUPATI-EQ was evaluated and fell outside the default ATH distance.

Desktop and narrow layouts were visually inspected. No trading runner or order endpoint was invoked during feature verification. Existing isolated account source snapshots received targeted source changes; their runtime activation is separate from main-dashboard verification.


## Sector strength and conditional plans

Sector classification now has its own report column. Sector RS is the equal-weight current NSE EQ sector-peer return minus the Nifty 500 return, in percentage points, separately for 6 and 12 months. Only finite, matching-session returns are used; each sector window needs five peers. This is a current-peer-group comparison, not an official sector-index return, the Sector rotation index score, or a 0–100 percentile. Both positive windows mean Leading, both negative mean Lagging, otherwise Mixed; missing windows are Unavailable. Stock RS uses the same benchmark and periods.

Conditional entry is one master tick above the greater of reported ATH and reference price. Stop-loss is entry minus twice provider daily ATR14, rounded down to tick. Target is entry plus twice the resulting tick-rounded risk. Levels are unavailable without valid recent data, ATR, positive prices and a tick representable to two decimals. Outside-screen symbol checks retain an explicit outside-rules status. The stop is volatility-based, not independently verified chart structure; target is a 2R scenario, not a forecast. Fresh quote, close-confirmed breakout, volume/liquidity and adjusted ATH verification remain required. The report and AI evidence include the method, captured date, invalidation and limitations. No order route was added.

Old saved jobs retain their original evidence and show Not captured / Levels unavailable for these additions until a new screen is run. Existing AI text is never represented as a review of newly calculated levels.
