# Sector Pulse User Functional Guide

Audited 7 October 2026. Start with [technical formulas](technical-guide.md), [deployment and private restore](deployment-guide.md), and [complete settings/source catalog](source-reference.md). This guide describes controls and expected behavior, not the current account or a trading recommendation.

Updated 7 October 2026 · Renko Support and Strategy

This section explains the deployed Renko chart and management of existing FYERS positions. For other dashboard areas, use the [project documentation](../README.md), [Delta India guide](delta-india.md) and [Trade Parser guide](telegram-trade-parser.md).

## Renko Support and Strategy

Open **Renko Supertrend Strategy** from **Trading Strategies**. Choose the broker-master underlying, host timeframe and visible strategy settings before applying them. The selected settings are copied into the new manager; changing the form later does not change an active manager.

### Paper runner versus existing FYERS positions

**Start Runner** uses the form's selected Paper or Live mode to start a new strategy run. Paper trades are simulated; a chart BUY/SELL marker is not a confirmed broker fill. Historical chart events are also separate from actual positions.

**Apply Renko · start LIVE management** manages positions already filled in the connected FYERS account. This button starts LIVE management even if the main runner's form shows Paper. It does not convert a paper trade into a broker position. The original Paper runner remains separate.

### Refresh orders and open positions

Use **Refresh FYERS positions and orders** in **Existing FYERS positions · Renko management**. The list shows broker symbol, net quantity, broker average and product. The broker order book is shown separately, with requested and filled quantities and statuses such as pending, filled, rejected and cancelled.

An accepted or pending order is not an open filled position. A partially filled entry with an outstanding remainder cannot be adopted while that order is still pending. If there are no open positions, the dashboard says **No open FYERS positions** and the Apply button stays disabled.

### Select positions and start management

1. Choose the underlying, timeframe and Renko settings you want to apply.
2. Refresh FYERS positions and orders.
3. Select eligible positions. Currently supported positions are filled, long, whole-lot **MARGIN options** on the chosen underlying: long Calls or long Puts. Shorts, futures, shares and other products are not supported by this adoption workflow.
4. Choose **Re-entry after adopted exit** if you want subsequent strategy entries. It is off by default.
5. Click **Apply Renko · start LIVE management**. The dashboard checks fresh account, contract, quantity, average, product, pending orders and ownership before taking control.

The already-filled position becomes the managed position. **No initial BUY is submitted.** Each selected position gets its own manager, with its own saved settings, exposure, order audit and trade quota. The adopted position counts as the first trade; later entries use the configured lots and remaining quota.

### Exit rules after adoption

The selected existing Renko exit rules become active when management starts. An already adverse EMA or configured underlying price boundary does not require another entry or a new crossing. Trailing starts from fresh observations after adoption; it does not invent an earlier price peak. Execution still requires the relevant fresh price and broker reconciliation; starting monitoring does not guarantee an immediate fill.

- With the EMA exit enabled, a Call exits on an adverse underlying move below the selected EMA; a Put exits above it. Equality alone is not a breach. EMA exit is independent of the entry widening rule and ADX filter.
- An opposite **confirmed Supertrend reversal** is an additional exit, subject to the selected ADX gate.
- Configured underlying stop/target levels and optional trailing stops apply when enabled.
- Session square-off uses the instrument's broker-master segment and verified session policy. Current source uses 15:10 IST for NSE/BSE and the verified regular-session end for MCX, subject to holding/expiry policy. New adoption is unavailable after its cutoff.

Only the confirmed managed quantity is eligible for an exit. An exit order's acceptance is not a confirmed closure; partial fills and outstanding remainder are reconciled before another action.

### Optional re-entry

With **Re-entry after adopted exit** off, the manager completes after the adopted position closes. With it on, later entries must meet the existing Renko signal and execution rules, including the selected filters, trade quota, fresh prices and session cutoff. Re-entry is not unconditional, and there is no same-candle re-entry after a strategy exit. Subsequent entries use the existing nearest-expiry ATM Call/Put selection; they need not reuse the adopted strike.

The original broker entry time, fees and price ticks before adoption are unavailable. They are not invented. The adopted trade is therefore not retrospectively classified as a quick-loss sideways trade; later runner-generated entries retain the normal sideways-range behavior.

### Pause, resume and restart recovery

**Pause monitoring** stops that manager and preserves its position and ownership claim. It does not send a square-off order. This differs from the main runner's **Stop Runner**, which follows its existing stop-and-close workflow.

After a dashboard restart, adopted managers remain stopped with saved exposure and pending intent. Use **Reconcile / resume** to verify the same broker account and exposure before resuming. An owned pending order is reconciled using its saved ID or tag; it is not replaced with another entry order.

External quantity, average, side or product changes, or unavailable broker evidence, pause management before further orders and preserve the claim for manual reconciliation. If the broker confirms the position was fully closed externally, **Reconcile / resume** acknowledges that closure and releases the claim without inventing an exit price or starting re-entry.

### When adoption is unavailable

- No eligible position is selected, or no position is open.
- The selected position changed or closed since the inventory was refreshed.
- The position has an unsupported side/product, a partial-lot quantity, an unavailable average, or a contract that cannot be verified against the current master and selected underlying.
- A pending entry/remainder exists, another strategy owns the position, or an outstanding protective order conflicts with management.
- FYERS authentication, account identity, ownership verification or broker evidence is unavailable.
- The live execution gate is disabled, the strategy revision requires a dashboard reload, or the session cutoff has passed.

If protective-order ownership cannot be verified, the inventory can remain visible but adoption stays disabled. Refresh again after the broker response recovers. Do not treat an unavailable check as permission to start.

### Manager information and saved evidence

The manager table shows contract, quantity, broker entry average, status, re-entry setting, and gross unrealized and realized P&L. **Broker adoption / order evidence** expands the saved adoption snapshot, selected settings and subsequent order audit. Live adopted-position unrealized P&L also appears in the chart overlay; unavailable or disconnected quotes do not appear as live profit. Earlier fill times and full historical costs remain unknown.

## Candlestick volume bars

The strategy chart shows **actual FYERS host-candle volume** in the lower band, on its own scale so it does not compress the price candles. Each volume bar uses exactly the same opening timestamp as its host candle and follows the chart's visible time range.

- Green volume corresponds to a host candle closing at or above its open; red corresponds to a close below its open. This shows candle direction, not buy/sell volume decomposition.
- Missing provider volume leaves a gap and an unavailable readout. It is not replaced with zero.
- A genuine provider value of zero remains zero and has no visible bar height.
- Hovering a candle shows its volume in the chart readout.
- Forming-candle volume is a broker OHLC snapshot. It updates when that candle snapshot is refreshed; LTP WebSocket ticks do not by themselves refresh or calculate volume. Price may therefore move while the displayed forming volume stays unchanged.
- In Synthetic Renko view, the histogram still represents real host-candle volume. It is not volume inferred for individual Renko bricks.

Candles, volume and the RSI zone pane remain together in **Full screen**. RSI zones are 0–40, 40–60, 60–80 and 80–100. These chart displays do not add volume or RSI entry/exit conditions to the strategy.

## Further reference

Read the [Renko strategy rules](../strategies/renko_supertrend/README.md) for full signal and session details, or the [position-adoption lifecycle notes](renko-position-adoption.md) for implementation and verification scope. Live adoption was validated with fake-broker lifecycle tests; browser checks used read-only actual FYERS inventory and did not start live management or submit an order.

## Compact Renko workspace and independent instances

The Renko page keeps broker, market, instrument search, timeframe, execution mode, sizing and **Start selected** together. **Selected instance** shows its status, P&L, trailing state and Start/Stop control. Active and saved instances use compact rows. Signal settings, risk/exit settings, order audit, chart history, existing-position management and the Excel journal expand when needed. Candles, actual volume and the four RSI zones remain together.

Choose **FYERS** for NSE indices, BSE indices, NSE/BSE stock-option underlyings and MCX commodities. The **Market** selector lists matching underlyings from actual broker masters; search narrows that category. A category with no listed option underlyings shows an explicit empty result. Listed instruments still need a currently available Call/Put route, valid expiry, fresh executable quotes and broker preflight before an entry. Ordinary equities without listed options are not offered as option routes.

Choose **Delta India** for public perpetual traded-price signals with long nearest-expiry ATM Call/Put execution. Perpetual signals do not authorize perpetual orders. Instruments without listed Call/Put options are blocked explicitly. Delta supports 1/3/5/15/30-minute and 1-hour host candles, seven-day eligibility, an explicit daily IST cutoff, marketable IOC limits and reduce-only exits. Quantity means whole native option contracts; P&L stays in the verified native currency. Fee estimates use native commission or product-rate/index evidence, estimated GST and the premium fee cap; unavailable costs stay unavailable rather than becoming zero.

Use **Add displayed instrument** for each choice, select the instruments in the multi-select, then **Start selected**. The shared visible settings apply separately to each broker/instrument instance. Every result identifies STARTED, BLOCKED, ALREADY_RUNNING or REVIEW_REQUIRED; partial success is shown per instrument. An uncertain activation is not silently retried. **Save displayed instrument as an instance** creates or opens a stopped configuration without starting it.

Switching broker or instance changes the displayed controls and chart; other runners retain their own position, trade quota and settings. **Stop & close** targets only its row's runner. Existing-position adoption remains separate and requires explicit application; pausing an adopted manager preserves exposure. On service restart, saved instances remain stopped and require reconciliation before renewed activity.


## Dashboard orientation and broker connection

Open the local Sector Pulse dashboard after setup. Choose the broker and module explicitly. FYERS Indian equity/index/commodity routes and Delta India crypto routes remain independent, including saved instances, positions and journals. A broker picker or green status does not start a runner. Sector rankings and handoff packets are analysis; research screens are simulations. Dhan-labelled choices do not prove a connected production Dhan execution route.

Connect FYERS with the supported private application configuration/browser login. Verify the account, token validity and requested master/history. Delta Connection settings take India key/secret through masked fields and verify a signed wallet read; destination IP and permissions matter. Credential fields clear on save. Configure Telegram only with an actual bot/channel token; native WhatsApp requires macOS helper and OS permissions. See the deployment guide rather than copying secrets into notes.

## Sector heatmap and analysis workflow

Choose Intraday or Swing mode, inspect score, timeframe alignment, relative strength, ADX, rotation and data quality together. Open a sector for timeframe/history and stock-contribution detail. Official weights are dated and may cover only the published top ten; missing constituents are not renormalized into a full index. A strong contributor is not automatically a valid stock entry.

Refresh returns available snapshots, not necessarily a new completed bar. Rotation needs distinct completed-history observations; unavailable or warming-up is expected when history is insufficient. Missing breadth/volume is explained and their scoring weight is redistributed across available components. Sort/filter the heatmap to inspect candidates. Use planning capital, risk limits, stop/invalidation choice and order preference to build a handoff packet; review contract, whole quantity, quote age, spread, OI/volume and R:R before any separate execution ticket. Exporting a handoff does not send an order. A partial-target/ST equity plan is planning-only where labelled NOT_IMPLEMENTED.

## Initial Renko setup and dated configuration export

In the main initial setup UI, select broker/instance, market, underlying, Paper/Live and timeframe. Enter option lots or cash whole shares, max trades and optional daily risk budget. Choose holding policy where supported. ATR length/factor, Auto/Manual brick, widening window, ADX, RSI slope, retest/patterns, EMA exit, target/stop, proximity, sideways lock, trailing and slippage/capital controls apply to the next Start, not silently to an armed run.

**Save settings** and **Download settings .txt** are in the main setup UI. Optionally name the configuration. The dated IST export includes visible draft values, false checkboxes and blank optional fields, broker/instance, requested Start configuration, and separately recorded active configuration from the last runner snapshot. Draft edited/save pending/unconfirmed and last confirmed save status are shown. Saving/exporting does not apply changes to a running position. The text file is a configuration record, not an import, credential backup, order journal or proof of fill.

The candlestick/fullscreen chart adds only **Start Runner / Stop Runner**, using the same selected-instance lifecycle handler as the main control. Saving and exporting remain in the main setup UI. The chart button disables during an in-flight request/status failure; errors are displayed. Start applies the visible next-Start configuration with existing validation. Stop Renko seeks cancellation/reconciliation and owned closure; remain attentive while Stopping or UNKNOWN. No new order policy is created by moving the button into the chart.

## Renko settings explained

- Mode: Paper uses finite virtual INR capital; Live uses actual broker checks and explicit capability. Saved Paper settings never establish a live position.
- Instrument/market: options use nearest-expiry ATM call/put on a supported underlying; no fallback to futures. Cash uses exact shares; NSE/BSE cash search excludes indices. Delta underlying is crypto perpetual signal data with listed long option execution.
- Host timeframe: drives completed entry/indicator state. A synthetic chart view does not change the broker host bars. Changing history range/anchor can change path-dependent historical signals.
- ATR length/factor/brick: defaults5/3/Auto, manual12.8; volatility regime alters effective factor/Auto brick. Exact recurrences are in the technical guide.
- Widening: default2 requires one strict EMA10/30 signed-gap increase. Larger windows require consecutive increases across all selected completed observations.
- ADX: off by default; enabled requires strict threshold exceedance. RSI slope on by default requires rising bullish/falling bearish RSI14, blocks flat/unwarmed data.
- Retest: optional established trend touch/bounce with selected engulfing/harami/intraday-star geometry. Selecting it does not disable the other gates. At least one pattern is required.
- Intrabar entries: off by default; provisional cloned engine on verified current candle and fresh tick. A transient candidate can disappear. Missing open/history is a blocker even when tick status is green.
- EMA exit: runner default on/10; editable1–1000 or disabled. It reacts to fresh provisional underlying EMA breach independently of entry widening. Opposite confirmed ST remains a separate exit.
- Underlying stop/target: optional positive absolute underlying prices, not option premium points or percentages; direction/tick validation applies.
- EMA proximity: optional ATR/points maximum distance from entry EMA10, defaultATR/.5; prevents far-from-EMA entries only when enabled.
- Sideways: off by default; max3 host buckets. Quick finalized estimated net loss can freeze actual exposure range, blocking new entries until fresh strict breakout. It does not prevent exits.
- Renko trail: off by default; premium percent10 or underlying points, full-position monotonic post-fill stop without partial targets/profit activation. It is different from EMA/Delta step trailing and the research shortlist.
- Cash Intraday/CNC and MCX Intraday/Carry forward: read exact session/expiry policy in the runtime preview. CNC blocks new bearish shorts; carry does not waive ownership or expiry protection.
- Lots/shares/quota/capital: positive exact quantities. Insufficient capital rejects rather than downsizes; adopted exposure counts as first trade. Settings are saved independently from armed state.

## Live chart, LED, zones and history

A green chart-feed/order-stream LED requires a fresh snapshot, connected/fresh market, tick age0–15seconds and order-stream connection. Snapshot age over5seconds, missing tick time, closed market or errors change the status. Read tick age and candle readiness separately. A green LED does not certify broker fills, current candle-open recovery, future latency or profitability.

Five-minute strong supply/demand shaded bands come from completed broker OHLC, regardless of strategy timeframe. Two bars on either side confirm a strict pivot. Strength requires a close beyond the opposite pivot wick with at least one ATR14 departure within the following two closed bars. Shading starts retrospectively at origin; the region before confirmation was not known then. A later strict close beyond the outside boundary marks broken; a wick/equality alone does not. Latest qualifying band and origin/confirmation/break information remain visible until replaced. They are chart references, not automatic strategy entry/exit gates.

Choose host/synthetic, volume, RSI pane and its chart-only SMA period, overlays, historical range and fit/latest/fullscreen independently. Synthetic volume is real host volume, not generated volume per brick. Cloud overlays include EMA10/30, Bollinger, RSI ranges, session/Fib/CPR references and drawings; enabling a visual does not alter the armed strategy. Session timezone/start preferences are chart-only. Floating red-bar Fib applies to5m. Earlier/later history may require provider retrieval and replay; gaps/errors remain explicit.

Entry assessment explains the selected completed/provisional candle, gates and evaluation time. Historical BUY/SELL/EXIT labels are simulations; actual execution markers use owned fill/order evidence. Do not infer option returns from host candle points. No next-candle re-entry is forced by a range breakout or a marker.

## FYERS RSI strategy and KAMA workflow

For RSI-based SMA/EMA choose underlying, host timeframe, lots, max trades, Paper/Live, RSI length/MA length/type, optional underlying hard levels and step-trail settings. Arm explicitly and wait for a future completed crossover. Bullish buys ATM call, bearish buys ATM put; these are long premium routes. Opposite completed cross exits. A price EMA10/30 cloud is visual context, not the RSI trigger. Confirm current master lot/multiplier/expiry and broker funds for Live. Stop/unknown/partial fills require reconciliation.

Optional step trailing uses entry-based premium percentage or points: at first favorable step the first allocation can exit and stop moves to entry; second step exits the second allocation and ratchets; residual follows. Whole filled lots determine allocation. No stop exists before first step in this mode. It differs from Renko's full-position best-price trail.

KAMA is separate from EMA/RSI: completed-close efficiency, breakout/reclaim, slope and cooldown rules. Choose its supported instrument/quantity/risk/stop settings and mode, inspect data readiness and policy blockers, then deliberately Start. A KAMA WAIT cannot be converted to an entry by eligibility checks. KAMA Live requires its own gate and FYERS capability. Entry09:15–15:10 and square-off15:15–15:30 are its source defaults, distinct from Renko cutoffs.

## Delta manual orders, strategy and monitoring

Choose Paper/Live, listed contract or current supported ATM strategy route, quantity in contracts, timeframe/RSI/MA and optional ADX/momentum/trailing. Manual exact-symbol tickets and ATM strategy-managed Submit have different intent; read the route shown. Legacy futures configurations retain their recorded Long-only/Both rules until explicitly stopped/replaced. Current ATM options buy long call/put from underlying signals and never write options or silently fall back to futures.

Manual limit uses tick-aligned price and IOC/GTC; market uses IOC without local limit. A direct Submit is deliberate authorization and internally validates contract, quotes, account/funds/ownership. Paper uses fresh ask/bid simulation without broker order; it does not simulate a resting limit queue. Bullish/bearish RSI crosses and EMA-only candle-extreme touches are completed-bar decisions. Touch evidence is inferred from OHLC, not recovered tick sequence. ADX/momentum are entry filters; exits still run.

Delta Stop Runner stops entry polling and can leave owned exposure. Use explicit Close runner position for verified remainder. Saved active monitoring intent can restore exit-only monitoring after restart and reconciliation; intentional stops remain stopped. IOC/limit exits can partly fill; protect/reconcile residuals. Trailing is application monitoring, not an exchange-resting stop. Step percentage/points has staged allocations; ATR mode is separate full-position contract-ATR stop. Manual orders do not automatically inherit a runner trail. INR display requires a current verified conversion policy and can be unavailable while native evidence remains intact.

Review Orders/fills, positions, lifecycle journal and saved history separately. Unknown network outcome is not permission to resubmit. Never attach a new strategy to an unexplained broker quantity. Research/history screens do not change execution settings. Details: [Delta guide](delta-india.md).

## NIFTY and SENSEX straddle workflow

Both bridges include bundled script fallback for fresh installs; existing configured/legacy scripts retain precedence. Choose module, lots, entry window and supported exit mode, then Paper or explicit confirmed Live Start. NumPy/pandas and valid paired contracts/credentials are needed; no process starts during setup. Paper uses isolated source and virtual capital. Live submits paired legs through the selected reviewed script; legs are not one atomic transaction.

Default signal is compressed rolling5m realised volatility below percentile50, entry09:15–11:30, one lot per leg, default stop15 combined-premium points, ST7/3 after+10 gain or selected fixed target30; EOD15:20. One same-day re-entry waits for a completed5m checkpoint. External/bundled source, actual selected configuration and broker lot evidence are authoritative; a static lot constant is not current contract proof.

Stop process is not broker square-off confirmation. Managed LIVE square-off uses a fresh preview/account/position/order check and explicit confirmation. Verify both legs, pending orders and actual residual quantities. These Live starts have their own confirmation and are not universally controlled by EMA/KAMA/parser environment switches.

## Trade parser, WhatsApp and Telegram

Paste or Load recommendation, choose broker and exact lots/contracts, Parse, inspect contract/side/entry/stop/targets, then Submit deliberately. Text edits/broker changes invalidate tickets. Fresh quote/master/account and trigger/limit geometry checks can block submission. A trigger or accepted order is not a fill. Unknown outcome remains pending reconciliation rather than a blind retry.

Recommendation stops/targets are displayed plans. FYERS optional protective OCO requires explicit supported consent, selected full-position target and confirmed attributed fills; it never adopts unrelated positions. OCO may fail/trigger without filling; review actual broker status. Telegram plan levels do not automatically become protection. OpenAI advisory adds structured analysis; it cannot replace missing prices or silently submit.

WhatsApp polling requires native helper, selected chat, verified latest unread source and durable IDs; fail-closed unread/source errors are displayed. It is not guaranteed bulk ingestion. Telegram requires bot membership/access to selected channel; Verify reads bot/channel/webhook status without sending a message. Confirmation mode queues Load→Parse→Submit; tickets120seconds, recommendation5minutes. Auto is defaultoff and must be deliberately started with selected broker/quantity. Startup backlog is review-only, edits/duplicates do not auto-resubmit. Stop polling disables new discovery, not accepted broker orders. Restart does not rearm polling/Auto. [Telegram detail](telegram-trade-parser.md).

## Paper funds, trade history and exports

Virtual Paper capital defaults100000INR and remains independent of live balance. Available capital includes realized gross result, fee provision and open premium/notional reservation with1% headroom; no leverage or silent quantity reduction. Some brokers require a verified native-to-INR policy. Capital changes cannot silently rewrite an open lifecycle. Live affordability is separately broker-derived.

Review requested/filled/remaining quantities, actual broker/Paper IDs, contract/expiry, premium averages, reason, local fill-confirmation time and saved indicator/config snapshots. Gross and estimated net are distinct. Costs can be unknown for unsupported routes; old missing data is not zero. Actual slippage is already in fills. Saved closed-trade research and executable open P&L use different evidence.

Journal Excel export uses portable recorded Trades/Orders sheets and raw snapshot chunks. It is a static snapshot with full evidence; layout differs from older styled exports. Configuration TXT is separate from a trade journal. Keep exports private when they contain account/trade information.

## Research and operational recovery

Delta manual grid and adaptive cycles evaluate underlying futures proxies with cost/holdout assumptions. Select bounds/fees/slippage/funding/contracts/capital explicitly, examine data coverage and train-versus-held-out results, and stop/cancel research independently from trading. Adaptive scheduling and AI experiment proposals never authorize promotion. Trailing research found no optimum; apparent hybrid gains reversed under intraminute paths. Research-only Pine/replay/EMA variants are not active strategy settings.

Before update/restart, inspect every active instance and actual broker exposure. Renko Stop seeks flat; adopted Pause retains exposure; Delta Stop can retain exposure; straddle process Stop can retain both legs. Backups and ownership are essential. Restoring credentials does not restore active ownership safely. Use [deployment recovery steps](deployment-guide.md). Do not automatically rearm entries after restart; resolve account/quantity/order mismatches first.

## Troubleshooting by symptom

If data is stale or warming up, inspect missing component/history/master and await verified refresh; never reinterpret unavailable as neutral or zero. Green tick status with missing forming open blocks intrabar entries until recovery. If quote subscription is warming, the limited fresh-signal retry may recover before intent; UNKNOWN submission cannot be retried. A stopped button with owned quantity still requires module-specific reconciliation.

If capital insufficient, choose a deliberately revised quantity/capital after understanding its basis; rejected quantities are not silently changed. If contract not listed or expiry/units cannot be verified, the route is unavailable. If export fails, verify project dependencies and stored evidence. If native WhatsApp unavailable on your OS, use manual/Telegram routes. Broker token renewal, IP/permissions and platform limits are documented in deployment guidance.
