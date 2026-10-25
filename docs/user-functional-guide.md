# Sector Pulse user guide

Updated 17 October 2026

## Start here · accounts and dashboard navigation

Choose a saved broker account before reviewing instruments, holdings, funds or orders. FYERS, Dhan, Motilal Oswal and Delta India have separate data and execution routes. Connection status, market-data permission, runner status and order-stream status are different checks.

Configuration → Brokers manages saved connections and account dashboards. User Master manages users and section access for administrators. Sidebar visibility preferences and permissions determine which sections you can open; a hidden section is not proof that its server job stopped.

Use the search box in this guide to find a setting by its on-screen name, strategy or purpose. The parameter reference lists allowed options and form bounds. These are UI constraints, not guarantees of broker support. The broker master, fresh data and server validation remain authoritative.

## Sector rotation and stock cards

Sector rotation ranks available sector observations using the selected mode, score components, relative strength, momentum, breadth, volume and timeframe alignment. Filter narrows the visible set; Sort changes ranking. Missing observations are disclosed rather than treated as zero.

Open a sector or stock card to inspect contributors, indicator evidence and historical observations. A sector leader or historical BUY label is not an accepted order. Official constituent weights can be partial or dated. Stock-card broker-candle and rule-based analysis makes no OpenAI call.

## Analysis handoff · stock, index and commodity analysis

Select the broker account and instruments, planning preferences and analysis path. Broker candles and rule-based analysis uses no AI call. Codex / ChatGPT-account analysis uses the configured account workflow rather than an OpenAI API key. AI or broker data unavailability must remain visible; it does not establish a login failure by itself.

The index/commodity panel accepts one to six broker-native symbols. Eligible results can include the actual ATM option contract, premium entry, premium target, premium stop, lot size and reward/risk; missing or stale contract/quote evidence leaves the idea ineligible. Existing open exposure can exclude an instrument to avoid duplicate entries.

Analysis submissions run as background jobs. The page releases submission controls after acceptance, renders results when available, and retains completed or partial output for later retrieval. Stop targets the selected analysis job. Recommendations remain research until a separate explicit trading action passes current validation.

Planning capital, daily and per-idea limits, reserve, concurrent positions, reward/risk and declared external risk constrain planning when enabled. Fresh funds inclusion is optional. Exporting a packet or downloading settings does not send an order.

## Runner jobs and saved analysis outputs

Each submitted job/run has an independent identity. Active jobs are listed separately from optional stopped/saved history. Completed, failed, cancelled, running, pending reconciliation and stalled are different states; stalled/unresponsive requires heartbeat evidence.

Open a job to inspect its account, captured settings, chart link, status, trade journal and audit evidence. Entries and exits show recorded reasons, quantities, times, prices and P&L where supplied. Missing older evidence is unavailable, not fabricated. P&L refreshes independently of the background work.

Results persist across section changes, page reloads and navigation. Use saved jobs to retrieve them later. Stop is job-specific. Cancellation can preserve partial analysis output; stopping a trading runner follows its own position and pending-order policy, so verify terminal status and broker reconciliation.

## Renko Supertrend · setup, entries and exits

Select the instrument, Runner timeframe, Paper/Live mode, quantity, capital and trade limit in Trade setup. The launch timeframe mirrors the chart timeframe. One saved editable preset is retained per instrument in the saved-configuration library. Save settings updates it; autosave retains the working draft separately.

When Start finds different parameters, the popup lists saved versus form values. Use form parameters submits the edited values; Use saved configuration applies that record, including its shown execution mode; Cancel submits no Start. Batch Start resolves each instrument choice before submitting. An already running job keeps its captured settings.

Family masters govern their strategy and chart children. OFF disables the family while retaining subordinate choices for ON. Strategy selections affect entries/exits; Indicator/chart selections affect studies and historical replay. Independent enabled entry gates must satisfy their supported rules. A disabled control can mean the loaded runtime does not support it.

Completed-candle mode waits for verified host closes. Intrabar mode evaluates a provisional state using verified current-candle OHLC and fresh market evidence; a provisional signal may disappear. A signal before arming, reconnection or lock release is skipped rather than replayed as an old entry.

Renko/Supertrend uses ATR, factor and Auto/Manual brick settings. Manual reference brick stays fixed across live ticks and chart timeframes. Broker-verified session duration drives its reference policy; do not substitute assumed NSE/MCX/crypto hours. EMA, RSI, ADX, structure, zones, proximity and optional retest/manual-marker filters have separate settings below.

Enabled exit criteria can act independently. Absolute underlying target/stop values are PRICE LEVELS, not distances or option premium points. Optional trailing is application monitoring, not automatically an exchange-resting stop. Entry filters do not imply that all exit checks are disabled.

Quick-loss protection counts host intervals touched by actual entry/exit fills, including both endpoint candles. A qualifying quick losing exit locks new entries within the recorded position range; a fresh strict breakout releases it. The window is not a forced exit timer. Missing net-cost/exposure evidence can retain a protective review lock.

Stop Runner requests the strategy’s stop/reconciliation/owned-exit workflow. A Stop click or order acknowledgement does not establish a fill. Check pending orders and any residual position. A new configuration must not silently adopt unexplained broker exposure.

## Renko Engine · research and execution modes

Renko Engine is a separate strategy/replay workflow. Select its broker account, exact instrument, host timeframe, lots/contracts and maximum entries. Historical replay evaluates the selected history and engine parameters; its chart markers are simulated events.

Paper and Live engine runs require the selected broker’s supported runtime and fresh source data. Engine ATR/Supertrend, EMA, rule, direction, session and anchor settings are defined by the engine form; they are not automatically interchangeable with Renko Supertrend settings. Replay does not authorize promotion or start a Live runner.

## EMA Band, RSI / MA crossover and KAMA

EMA Band calculates its chosen EMA independently on candle High and Low. The supported completed-candle signal selects the current eligible ATM Call/Put; entry session and same-direction cooldown restrict entries. Its chart timeframe/history are display-only. Optional option-premium stop/target percentages supplement the supported indicator exits.

The RSI / MA crossover runner smooths RSI with the selected SMA or EMA. RSI length and RSI-MA length are distinct from price EMA periods. A future completed crossover can produce the supported bullish Call or bearish Put entry. Trade limit, lots, premium cap, daily budget and Paper capital apply to that run.

The crossover runner’s underlying hard target/stop settings have their own exit semantics; when either is configured, its displayed workflow suppresses the EMA exit. Its optional percentage/point step trail differs from Renko’s full-position trailing policy. Read the module’s active journal and settings before interpreting a shared label.

KAMA uses completed-close efficiency, adaptive fast/slow smoothing, breakout or reclaim, slope and cooldown rules. Choose quantity, invalidation and per-idea risk. WAIT remains WAIT when its signal is absent; account eligibility does not create an entry. Live requires the module’s supported broker/runtime gate.

## Delta India · tickets, options, futures and research

Read-only analysis, Paper, Live and research backtest workflows have different side effects. Select the exact listed contract or supported ATM option route, native quote currency, whole contracts, order type, limit premium and IOC/GTC terms. A perpetual signal instrument and an option execution contract are different instruments.

Bought-option mode buys a Call for bullish signals or a Put for bearish signals. The supported perpetual route uses long/short exposure and its own collateral policy. Native contract units, tick, expiry and multiplier come from the selected broker master; INR display follows the verified conversion policy.

Manual tickets and strategy runners are separate intents. Manual orders do not inherit a runner’s trail automatically. Stop behavior is module-specific: the legacy Delta runner can stop entries while leaving exposure; use its explicit close/reconciliation path and verify residuals. The Renko Stop flow has different behavior.

Research grids compare RSI/MA, ADX, momentum and squeeze variants with explicit fee, spread, slippage, funding, contracts and capital assumptions. Chronological holdout is separate from training. Backtest profit is not evidence of option fills or permission to promote a configuration.

## NIFTY / SENSEX long straddles

A long straddle buys both supported ATM Call and Put legs. Lots per leg, entry window, combined-premium stop and target belong to that straddle workflow, not to a one-leg Renko option runner.

Paired legs are not an atomic exchange transaction. Inspect each leg’s accepted, filled and remaining quantities. Process Stop is not proof of broker square-off; use the module’s explicit managed close flow and reconcile both legs. Paper and Live scripts/configurations must be identified in the displayed runtime evidence.

## Holdings review, live feed and positions

Holdings review selects a saved broker account, fetches that broker’s holdings and shows the available review categories. It is not a combined unlabelled portfolio. Missing permissions, session failures or unavailable holdings routes must be shown for that account.

Live feed & positions separates ticks, candles, order stream, positions, orders and fills. Fresh ticks do not prove the current candle has a verified open. Fresh receipt time does not prove a fresh exchange quote. An accepted order, a partial fill, a full fill and an unresolved submission are distinct.

Existing-position Renko adoption is a separate explicit live-management action. Eligible owned quantities and pending orders must be verified; adopting a filled position does not submit an initial buy. Pause monitoring can preserve exposure, unlike a stop-and-close action. Reconcile/resume does not invent missing historical fills or ticks.

## Screener, trade parser, Telegram and WhatsApp

Save a screener label and supported Chartink URL, evaluate candidates, then inspect account-native instruments and analysis. Cash product, quantity and external risk belong to the reviewed order flow. A screener row is not a submitted trade.

Paste or load recommendation text, parse it, inspect exact contract, side, quantity, entry/trigger/limit, stop and targets, then explicitly Submit. Edits invalidate stale tickets. Network uncertainty requires reconciliation rather than duplicate submission. An open position/order can block a redundant symbol entry.

Telegram channel label is only a display name. Bot access and exact channel identity are separate. Poll interval controls discovery; Auto submission is an explicit separate policy. Startup backlog and duplicate/edit evidence do not authorize replayed orders. Stop polling does not cancel already accepted broker orders.

The Telegram bought-option route can attach selected Renko exits after the reviewed mapping/quantity choice. XAUUSD-to-XAUT is an explicit proxy, not the same instrument. WhatsApp polling requires the native helper and exact chat; unavailable source/unread evidence blocks automatic ingestion.

## Charts, timeframe, viewport and freshness

Runner timeframe is the host interval for the next Start and is synchronized with the chart control. Timeframe changes on an active job require the explicit supported workflow; ordinary draft edits do not silently change its captured run. EMA Band has a separately labelled display-only chart interval.

Host candles use broker OHLC. Synthetic Renko bodies and historical entry/exit arrows are calculations. Actual trade markers use recorded order/fill evidence. Full screen changes layout; Reset view restores readable scale and recent bars. Deliberate historical scrolling should remain distinct from following latest.

History range, initialization anchor and warmup affect path-dependent replay. Missing or invalid OHLC can withhold indicators while valid candles remain displayed. Tick-live/candle-delayed means price observations exist but verified candle data is incomplete. Chart differs from active runner means compare instrument/timeframe/settings, not assume a login failure.

## Server resources, restart progress and recovery

Server resources shows resource samples and retained history. Admin restart controls for the dashboard and broker services are grouped here. Restart requests have independent identities and reported outcomes; a browser/network timeout does not establish restart failure.

The progress indicator shows Request, Restart, Readiness and Complete, with elapsed time and frequent probes. It does not invent an estimated percentage. READY requires the applicable readiness evidence. FAILED and UNKNOWN are explicit; do not automatically resend an uncertain restart request.

Before a restart, inspect active runners, retained positions and pending orders. A service can return while a retained strategy remains stopped. Never infer that exit monitoring resumed from a green page badge; check the specific job and broker state. Access controls and account isolation remain in force.

## P&L, journals, exports and troubleshooting

Gross P&L, estimated costs, estimated net and broker-reported values are separate. Fresh executable valuation and known fills are required; missing fees, funding or prices can leave net unknown. Zero must not replace unavailable evidence.

Job detail journals retain actual entry criteria, settings snapshot, requested/filled/remaining quantity, entry/exit prices and times, exit reasons and recorded P&L. Older missing evidence remains missing. Configuration TXT records settings; journal exports record execution evidence; neither export sends an order.

Start blocked: read the exact account, instrument, data, runtime or exposure reason. Feed delayed: distinguish tick freshness, candle verification and order connectivity. Stopping or UNKNOWN: reconcile the selected job and broker orders before another action. Some jobs unavailable: other jobs can still be running; a partial inventory is not proof of termination.

Expired session: renew the same saved account through its supported connection workflow, then test it. A slow analysis or market-data request alone does not prove login failure. Inspect Server resources and the affected job rather than repeatedly starting or submitting.

## Renko Supertrend parameters

### Broker view

Select the broker workspace whose instruments, market data, account and execution routes will be used. Account selection does not move another broker’s positions.

### Market

Restrict instrument search and session/product rules to the selected exchange segment.

### Holding

Choose intraday cash or delivery (CNC). Delivery does not permit a new bearish short entry; broker sell authorization may be required.

### Holding

Intraday follows the selected MCX contract session cutoff. Carry Forward uses the supported overnight MARGIN route and expiry controls.

### Use FYERS history for Motilal

Explicitly permit the selected FYERS account to supply labelled history for Motilal analysis. Execution remains on the selected Motilal account.

### FYERS history account

Choose the history-only FYERS account. Its identifiers must never be used to submit Motilal orders.

### Underlying search

Find instruments using the selected broker’s current master. Search text alone is not a selected contract.

### Instrument

Exact selected underlying. Signals use this underlying; the execution route determines whether orders use options, futures or shares.

### Execution mode

Paper simulates fills. Live can submit real broker orders when you explicitly Start. Changing this selector does not change an already running job.

### Runner timeframe

Candle interval used for the next runner Start. For example, 5 minutes evaluates five-minute host candles. It stays synchronized with the chart timeframe; an active runner retains its Start settings.

### Lots

Position size for the next Start. Indian derivatives use whole lots; Delta uses whole contracts; cash equities use whole shares.

### Virtual Paper capital · INR

Virtual INR capital available to Paper execution. This does not add funds to a broker account.

### Trade limit

Maximum number of new entry trades allowed for this runner run. Exits and protective position management remain separate.

### Configuration name

Name of the single saved configuration for this instrument. Save settings updates that record; renaming does not create a duplicate.

### Selected instruments

Instruments selected for independent runner submissions. Differences from each saved configuration are resolved before batch submissions start.

### Intrabar entries and EMA exits

OFF evaluates completed candles. ON allows fresh provisional live entry and EMA-exit evaluation; provisional signals can change before candle close.

### Sideways filter · quick after-cost loss

After a quick loss, blocks new entries inside the recorded position high–low range until a fresh strict breakout. The window uses host candles touched by the actual trade; incomplete exposure evidence stays locked for review.

### Quick-loss window · host candles touched

Maximum host candle intervals touched between the actual entry and exit fills for a quick-loss lock. Both entry and exit candles count. With a limit of 3 on five-minute candles, a losing trade spanning at most three candle intervals can lock new entries until a fresh price breaks its recorded position range. This is not a forced exit after three candles.

### Enable Renko Supertrend strategy rules

Master switch for this indicator family. OFF disables its strategy/chart controls while retaining subordinate choices for ON. A running job keeps its captured Start settings.

### Allow continuation entries

Optional continuation entries require the supported runtime and selected higher-timeframe agreement. A disabled control means that runtime capability is unavailable; it does not imply the rule is active.

### Trading session hours

Read-only broker contract session duration used by reference sizing. Crypto and exchange sessions differ; missing verified policy is shown explicitly.

### Renko Supertrend · Strategy

Include Renko Supertrend direction in strategy entry evaluation when its family master is enabled.

### Renko Supertrend · Indicator

Chart-only selection: Include Renko Supertrend direction in strategy entry evaluation when its family master is enabled. This controls the study/replay display and does not enable the corresponding strategy rule.

### ATR length

Number of candles used for the ATR calculation. In manual reference sizing this also selects the reference ATR period.

### Base factor

Multiplier applied by the Supertrend calculation. Changes apply to the next Start.

### Brick size mode

Auto derives brick size from the strategy calculation. Manual uses the verified fixed reference brick shown below.

### Manual brick size

Fixed reference brick size, retained across live ticks and chart timeframes. Recalculate reference brick explicitly to refresh it.

### Higher timeframe check · Strategy

Requires agreement with the selected higher timeframe for new strategy entries when enabled. OFF removes that entry check.

### Higher timeframe check · Indicator

Chart-only selection: Requires agreement with the selected higher timeframe for new strategy entries when enabled. OFF removes that entry check. This controls the study/replay display and does not enable the corresponding strategy rule.

### Supertrend timeframe (HTF)

Higher candle interval used by the optional higher-timeframe Supertrend check or chart study.

### Enable EMA strategy rules

Master switch for this indicator family. OFF disables its strategy/chart controls while retaining subordinate choices for ON. A running job keeps its captured Start settings.

### EMA 10 · first EMA · Strategy

Require the first EMA entry criterion when EMA strategy rules are enabled.

### EMA 10 · first EMA · Indicator

Chart-only selection: Require the first EMA entry criterion when EMA strategy rules are enabled. This controls the study/replay display and does not enable the corresponding strategy rule.

### First EMA period

Number of host candles in the first exponential moving average.

### EMA 30 · second EMA · Strategy

Require the second EMA entry criterion when EMA strategy rules are enabled.

### EMA 30 · second EMA · Indicator

Chart-only selection: Require the second EMA entry criterion when EMA strategy rules are enabled. This controls the study/replay display and does not enable the corresponding strategy rule.

### Second EMA period

Number of host candles in the second exponential moving average.

### EMA gap widening · Strategy

Require the signed EMA gap to widen across the configured window before a normal entry.

### EMA gap widening · Indicator

Chart-only selection: Require the signed EMA gap to widen across the configured window before a normal entry. This controls the study/replay display and does not enable the corresponding strategy rule.

### EMA gap widening window

Number of recent host candles inspected by the EMA gap-widening criterion.

### EMA proximity · first EMA · Strategy

Entry-only filter that rejects a price too far from the first EMA. It does not close a held position.

### EMA proximity · first EMA · Indicator

Chart-only selection: Entry-only filter that rejects a price too far from the first EMA. It does not close a held position. This controls the study/replay display and does not enable the corresponding strategy rule.

### EMA10 distance basis

Measure absolute distance from the first EMA as native price points or as a multiple of completed host ATR.

### Entry distance limit · |price − EMA10| / completed ATR, or points

Maximum allowed absolute price-to-first-EMA distance in the selected basis. This limits new entries only.

### EMA10 retest entries · Strategy

Optional first-EMA pullback touch and confirmed bounce entry path. Other selected entry gates still apply.

### EMA10 retest entries · Indicator

Chart-only selection: Optional first-EMA pullback touch and confirmed bounce entry path. Other selected entry gates still apply. This controls the study/replay display and does not enable the corresponding strategy rule.

### Retest: bullish / bearish engulfing

Allow the bullish or bearish engulfing geometry as a retest confirmation.

### Retest: bullish / bearish harami

Allow the bullish or bearish harami geometry as a retest confirmation.

### Retest: morning / evening star

Allow the intraday morning/evening-star retest geometry; a market-opening gap is not required.

### Enable RSI strategy rules

Master switch for this indicator family. OFF disables its strategy/chart controls while retaining subordinate choices for ON. A running job keeps its captured Start settings.

### RSI level entry filter · Strategy

Require the configured directional RSI level or inclusive RSI range for new entries.

### RSI level entry filter · Indicator

Chart-only selection: Require the configured directional RSI level or inclusive RSI range for new entries. This controls the study/replay display and does not enable the corresponding strategy rule.

### RSI entry mode

Choose a single bullish/bearish threshold or an inclusive allowed RSI range.

### Bullish RSI minimum

Lower inclusive RSI bound for bullish entries in Between mode.

### Bullish RSI maximum

Upper inclusive RSI bound for bullish entries in Between mode.

### Bearish RSI minimum

Lower inclusive RSI bound for bearish entries in Between mode.

### Bearish RSI maximum

Upper inclusive RSI bound for bearish entries in Between mode.

### Bullish RSI strictly above

Strict bullish RSI threshold in Threshold mode; equality does not pass.

### Bearish RSI strictly below

Strict bearish RSI threshold in Threshold mode; equality does not pass.

### RSI slope filter · Strategy

Require rising RSI for bullish entries and falling RSI for bearish entries. Flat or unready RSI does not satisfy slope.

### RSI slope filter · Indicator

Chart-only selection: Require rising RSI for bullish entries and falling RSI for bearish entries. Flat or unready RSI does not satisfy slope. This controls the study/replay display and does not enable the corresponding strategy rule.

### RSI period

Number of host candles used to calculate RSI.

### Enable ADX strategy rules

Master switch for this indicator family. OFF disables its strategy/chart controls while retaining subordinate choices for ON. A running job keeps its captured Start settings.

### Choppy filter · Strategy

Enable the ADX strength/choppiness entry gate; compare ADX with the configured threshold.

### Choppy filter · Indicator

Chart-only selection: Enable the ADX strength/choppiness entry gate; compare ADX with the configured threshold. This controls the study/replay display and does not enable the corresponding strategy rule.

### ADX threshold

Minimum ADX value required when the ADX strategy filter is enabled.

### ADX DI length

Period used to calculate directional movement for ADX.

### ADX smoothing

Smoothing period used by the ADX calculation.

### Enable Market structure strategy rules

Master switch for this indicator family. OFF disables its strategy/chart controls while retaining subordinate choices for ON. A running job keeps its captured Start settings.

### Directional swing structure entry filter · selected host timeframe · Strategy

Require confirmed directional swing structure on the selected host timeframe for normal entries.

### Directional swing structure entry filter · selected host timeframe · Indicator

Chart-only selection: Require confirmed directional swing structure on the selected host timeframe for normal entries. This controls the study/replay display and does not enable the corresponding strategy rule.

### Enable Supply / demand zones strategy rules

Master switch for this indicator family. OFF disables its strategy/chart controls while retaining subordinate choices for ON. A running job keeps its captured Start settings.

### Enable

Enable the manual price-marker and consecutive-completed-close entry filter. This does not submit an immediate manual order.

### Bullish marker

Underlying price marker used by the bullish manual-trend completed-close test.

### Bearish marker

Underlying price marker used by the bearish manual-trend completed-close test.

### Consecutive completed closes

Number of consecutive completed host closes required by the enabled manual price-marker filter.

### Volume · chart only

Show broker volume on the chart. Missing volume is not inferred, and this visual switch does not enable strategy entries.

### RSI moving average · chart only

Show the moving average of RSI in the chart study. It is independent of strategy entry selection.

### Enable ema exits

Enable or disable this exit section as a whole. Child selections are retained for re-enabling. Changes apply to the next Start, not silently to the active run.

### EMA breach · configurable exit period · Strategy

Allow an adverse breach of the configurable exit EMA to close an owned position. Completed/intrabar timing follows the selected timing rule.

### EMA breach · configurable exit period · Indicator

Chart-only selection: Allow an adverse breach of the configurable exit EMA to close an owned position. Completed/intrabar timing follows the selected timing rule. This controls the study/replay display and does not enable the corresponding strategy rule.

### Exit EMA period · host candle close

Period of the EMA used by the enabled EMA breach exit.

### Second EMA breach · Strategy

Allow an adverse second-EMA breach as an independent exit criterion.

### Second EMA breach · Indicator

Chart-only selection: Allow an adverse second-EMA breach as an independent exit criterion. This controls the study/replay display and does not enable the corresponding strategy rule.

### EMA gap contraction · Strategy

Allow EMA-gap contraction to close a position when the associated exit family is enabled.

### EMA gap contraction · Indicator

Chart-only selection: Allow EMA-gap contraction to close a position when the associated exit family is enabled. This controls the study/replay display and does not enable the corresponding strategy rule.

### Enable supertrend exit

Enable or disable this exit section as a whole. Child selections are retained for re-enabling. Changes apply to the next Start, not silently to the active run.

### Supertrend reversal · Strategy

Allow a confirmed Supertrend reversal to close the owned position when its exit family is enabled.

### Supertrend reversal · Indicator

Chart-only selection: Allow a confirmed Supertrend reversal to close the owned position when its exit family is enabled. This controls the study/replay display and does not enable the corresponding strategy rule.

### Enable rsi exit

Enable or disable this exit section as a whole. Child selections are retained for re-enabling. Changes apply to the next Start, not silently to the active run.

### RSI slope against the position · Strategy

Allow RSI slope against the held direction to trigger an independent exit.

### RSI slope against the position · Indicator

Chart-only selection: Allow RSI slope against the held direction to trigger an independent exit. This controls the study/replay display and does not enable the corresponding strategy rule.

### Enable adx exit

Enable or disable this exit section as a whole. Child selections are retained for re-enabling. Changes apply to the next Start, not silently to the active run.

### ADX below the selected threshold · Strategy

Allow ADX below the configured threshold to trigger an independent exit.

### ADX below the selected threshold · Indicator

Chart-only selection: Allow ADX below the configured threshold to trigger an independent exit. This controls the study/replay display and does not enable the corresponding strategy rule.

### Enable market structure exit

Enable or disable this exit section as a whole. Child selections are retained for re-enabling. Changes apply to the next Start, not silently to the active run.

### Opposing confirmed swing structure · Strategy

Allow confirmed swing structure opposing the position to trigger an exit.

### Opposing confirmed swing structure · Indicator

Chart-only selection: Allow confirmed swing structure opposing the position to trigger an exit. This controls the study/replay display and does not enable the corresponding strategy rule.

### Enable supply / demand targets

Enable or disable this exit section as a whole. Child selections are retained for re-enabling. Changes apply to the next Start, not silently to the active run.

### Opposing strong 5m supply/demand target exit · optional · Strategy

Optional exit at an opposing strong five-minute supply/demand zone. Zones and target eligibility depend on verified data.

### Opposing strong 5m supply/demand target exit · optional · Indicator

Chart-only selection: Optional exit at an opposing strong five-minute supply/demand zone. Zones and target eligibility depend on verified data. This controls the study/replay display and does not enable the corresponding strategy rule.

### Quoted premium cap

Optional quoted option-premium cap for entry selection. It is not an underlying stop or a total-account capital amount.

### Daily loss budget

Optional strategy loss-budget limit in the displayed native currency. Blank disables this optional limit; broker affordability checks still apply.

### Additional slippage · option premium points per side

Additional cost allowance in option-premium points per side. Actual fill slippage is already reflected in fill prices; an allowance is not a guaranteed fill adjustment.

### Enable trailing stop-loss

Enable application-managed trailing exits using fresh observations after entry. This does not place an exchange-resting protective stop by itself.

### Trailing stop basis

Choose percentage or underlying-point distance for the full-position trailing policy.

### Trailing distance · percent or underlying points

Distance used by the enabled trailing exit in the selected trailing basis.

### Hard target · underlying price

Optional absolute underlying target PRICE, not a number of points gained and not an option-premium target. Direction and tick validation apply.

### Hard stop-loss · underlying price

Optional absolute underlying stop PRICE, not a loss distance, percentage or option premium. Direction and tick validation apply.

### Trade product

Choose bought ATM options or supported perpetual futures. Options buy a Call/Put; futures use the supported long/short contract route.

### Optional daily strategy cutoff · IST

Optional crypto daily strategy cutoff in IST. Continuous mode has no daily cutoff; held contract expiry and risk rules still apply.

### Price source

Broker price/candle source used for the selected Delta signal instrument. Do not mix another broker’s prices into execution evidence.

### Order terms

Supported broker order execution terms. An IOC can fill partly and cancel the remainder; acceptance is not a completed fill.

### Crypto trading schedule

Continuous crypto trading runs across days. A daily cutoff is an explicit optional strategy policy; it does not mean crypto has an exchange close.

### Chart view

Host view displays broker OHLC. Synthetic view displays calculated Renko bodies. Historical chart signals remain simulations.

### History review range

Historical display/replay range. Changing the replay anchor can change path-dependent indicators; it does not rewrite an active runner’s captured settings.

### From · IST

Beginning of the custom historical chart range, interpreted in IST.

### To · IST

End of the custom historical chart range, interpreted in IST.

### Show one-minute Supertrend label

Show or hide the one-minute Supertrend chart label. Chart display only.

### Show five-minute Supertrend label

Show or hide the five-minute Supertrend chart label. Chart display only.

### Chart & runner timeframe

Authoritative chart and next-Start host candle interval. The Runner timeframe selector mirrors this same value.

### Override entry direction

Explicit direction for a separate override-entry action. Requires the active matching runner, fresh evidence, available quota and no conflicting exposure.

### SMA of RSI period

Number of usable RSI observations averaged by the chart-only SMA of RSI.

### Re-entry after adopted exit

After an adopted existing position exits, allow later qualifying strategy entries. OFF completes management after that position closes.

### Mode

Filter displayed journal records by Paper or Live. Filtering does not delete trades or change execution mode.

### Manual brick reference

Reference sizing value retained by the manual-brick workflow; the displayed verified calculation and selected contract policy govern its use.

## Sector analysis, handoff, screener and planning parameters

### Filter

Limit the displayed sector rows to the chosen rank, rotation, alignment or relative-strength category. This is a view filter, not an entry order.

### Sort by

Choose the metric used to order sector rows. A ranking is analysis rather than a confirmed trade signal.

### Sector analysis refresh interval

How often sector analysis is refreshed. A new response is not necessarily a new completed market candle.

### Lots per legBuys this many lots of both the ATM call and put. Confirm available funds before live use.

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Start time

Earliest time at which a new entry may qualify, in IST. It does not guarantee an entry at that time.

### End time

Latest time at which a new entry may qualify, in IST. Exit management follows the strategy’s separate rules.

### Lots per leg

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Hard stop (premium points)

Combined option-premium stop distance in points for the straddle. Both legs and residual orders must be reconciled separately.

### Target (premium points)

Combined option-premium profit target in points for the straddle, distinct from an underlying-price target.

### Entry start (IST)

Earliest time at which a new entry may qualify, in IST. It does not guarantee an entry at that time.

### Entry end (IST)

Latest time at which a new entry may qualify, in IST. Exit management follows the strategy’s separate rules.

### Apply these capital limits to analysis and ticket sizing

Apply the optional capital and risk constraints to analysis and ticket sizing. Turning this off does not disable independent broker or strategy checks.

### Planning capital (₹)

INR capital used for planning position sizes; it is separate from actual broker cash.

### Maximum daily loss (₹)

Maximum planned daily loss in INR when optional planning controls apply.

### Per-idea risk allocation (₹)

Maximum planned risk allocated to one trade idea in INR.

### Reserved risk buffer (₹)

INR buffer withheld from the planning risk allocation.

### Maximum simultaneous positions

Maximum simultaneously planned positions when the planning policy is enforced.

### Optional minimum reward:risk (0 = no gate)

Minimum planned reward divided by planned risk. Zero disables this optional planning gate.

### Stop / invalidation basis

Specify an exact invalidation price or a percentage distance when preparing an analysis plan.

### Order-type preference

Preferred ticket order type; actual route support and the preview determine whether submission is available.

### Include freshly read selected-broker available funds

Request that freshly read funds from the selected broker be included in the analysis packet.

### I confirm funds may be included in this local packet

Consent to including the selected account’s funds in the local analysis packet; it does not authorize an order.

### Broker

Select the saved broker account used by this workflow. Data, funds, instruments and execution stay scoped to that account.

### Defined-risk proposal

Choose a proposal from the current analysis packet for a separate reviewed ticket. A proposal is not a broker fill.

### Quantity / lots

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Declared external open risk (₹)

Manually declare INR risk from exposure outside the positions known to this workflow.

### Enable policy after acknowledgement

Policy activation choice. Saving an enabled flag alone does not bypass acknowledgement, runtime availability or broker validation.

### Kill switch engaged

Engage the policy kill switch to block new automatic activity covered by this policy. Already accepted orders need reconciliation.

### Halt on uncertain order status

Halt new policy actions when a previous order has an uncertain outcome.

### Completed candles required

Require completed-candle evidence for policy signals.

### Full option chain/master/liquidity/Greeks/lot/tick evidence required

Require verified option master, chain, liquidity, Greeks, lot and tick evidence for an option proposal.

### Stop or defined-risk spread required

Require a stop or supported defined-risk structure before a policy proposal is eligible.

### Target required

Require an explicit target in eligible policy proposals.

### Execution mode

Choose a Paper policy or the separately gated Live route. A saved draft is not proof that execution is running.

### Universe

Restrict eligible instruments to the selected equity/option universe.

### Exact allowed FYERS underlyings, comma-separated

Exact allowed FYERS underlying symbols; entries outside this allowlist are ineligible.

### Supported index underlyings

Index underlyings permitted by the policy; a name still requires supported current contracts.

### Allowed segments, comma-separated

Comma-separated segment allowlist for the optional policy.

### Allowed strategies, comma-separated

Comma-separated strategy allowlist for the optional policy.

### Completed-candle signal conditions, one per line15m, 1h, Daily and Weekly completed candles must all be fresh Every timeframe must agree as exact FULL BULLISH ALIGNMENT or FULL BEA

Completed-candle alignment conditions required by the optional policy; unavailable or stale observations do not count as agreement.

### Planning capital (₹)

INR planning capital for this policy, separate from broker funds.

### Maximum daily loss (₹)

Maximum daily INR loss allowed by this policy.

### Per-idea risk (₹)

Maximum INR risk allocated to one idea by this policy.

### Reserved risk buffer (₹)

INR risk buffer retained by this policy.

### Maximum concurrent positions

Maximum concurrent positions permitted by this policy.

### Maximum concurrent orders

Maximum simultaneously outstanding orders permitted by this policy.

### Minimum reward:risk

Minimum expected reward-to-risk ratio for eligible policy proposals.

### Order type

Order type permitted by this policy; the shown policy supports limit-only submission.

### Maximum limit buffer (%)

Maximum percentage price buffer permitted around the policy reference quote.

### Maximum bid/ask spread (%)

Maximum permitted bid/ask spread percentage before an entry is vetoed.

### Trading start (IST)

Beginning of the policy entry window, in IST.

### Trading end (IST)

End of the policy entry window, in IST; existing exposure still needs its applicable exit management.

### Minimum DTE

Minimum days to expiry accepted by the option policy.

### Maximum DTE

Maximum days to expiry accepted by the option policy.

### Cooldown (minutes)

Minimum wait in minutes before another policy action covered by the cooldown.

### Stale-data veto (seconds)

Maximum permitted evidence age in seconds; older data vetoes the policy action.

### Exact policy acknowledgement

Acknowledgement required by this policy workflow after reviewing its complete preview. It is separate from the Renko configuration-choice popup.

### Recommendation textVerify the source independently. The ticket uses the FYERS master and a fresh FYERS quote.

Recommendation text to parse into a reviewed ticket. Verify its source, instrument and levels; parsing does not submit an order.

### Lots

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Segment

Exchange/product segment used to restrict broker-master search and supported execution routes.

### Broker-master instrument

Select the exact supported broker instrument for this workflow. Search results must be resolved to current master metadata before execution.

### Broker-supported symbol or option searchFor stock options, enter the underlying or exact master search. Expiry, strike, call/put, lot size and tick must be returned by broker metad

Search the selected broker’s supported instruments. Entering text does not select a verified execution contract.

### Research timeframe

Candle interval for this workflow’s signals or replay. Active jobs retain their captured Start interval unless an explicit supported change is applied.

### EMA band length (High / Low)Applies separately to High and Low, exactly as the Pine source.

EMA period applied independently to candle High and Low to form the EMA band.

### Chart timeframeDisplay only; this never changes the runner’s timeframe or trade logic.

Display-only chart timeframe; it does not change an active EMA Band runner’s trade logic.

### Chart historyControls the displayed FYERS history only.

Number of historical broker candles shown in the chart; this is a display setting.

### Same-direction re-entry cooldown (bars)

Minimum completed bars between repeated entries in the same direction.

### Entry session (IST)Optional Pine entry filter; exits remain active outside it.

Optional IST entry-session filter. The strategy’s exit monitoring remains separate.

### Signal confirmation

This EMA Band workflow uses completed-candle confirmation.

### Exact broker-master underlyingScreened against the current master only.

Select the exact supported broker instrument for this workflow. Search results must be resolved to current master metadata before execution.

### Timeframe

Candle interval for this workflow’s signals or replay. Active jobs retain their captured Start interval unless an explicit supported change is applied.

### KAMA efficiency length

Completed-close efficiency-ratio lookback used by KAMA.

### Fast / slow lengths

Fast smoothing length used in the adaptive KAMA calculation.

### Fast / slow lengths

Slow smoothing length used in the adaptive KAMA calculation.

### Minimum efficiency ratio

Minimum efficiency ratio accepted by the KAMA entry gate.

### Breakout / cooldown bars

Completed-bar lookback used to establish the KAMA breakout condition.

### Breakout / cooldown bars

Completed bars required between eligible KAMA entries.

### Allow KAMA reclaim entries

Permit qualifying completed-close KAMA reclaim entries in addition to the supported breakout path.

### Mode

Choose Paper simulation or explicitly authorized Live execution. Saving a setting does not start trading.

### Quantity

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Invalidation / stop price

Absolute invalidation/stop price for the KAMA idea; source direction and tick checks apply.

### Maximum idea risk (₹)

Maximum INR risk permitted for this KAMA idea.

### Friendly label (optional)

Optional display name for a saved screener; it does not change the query.

### Chartink screener URL

Chartink screener to evaluate. Results are analysis candidates; submission uses a separate broker-native ticket.

### Broker account

Select the saved broker account used by this workflow. Data, funds, instruments and execution stay scoped to that account.

### Cash product

Choose intraday cash or delivery CNC for eligible screener orders.

### Declared external open risk (₹)

Manually declare INR risk from exposure outside the positions known to this workflow.

### UnderlyingOnly current FYERS cash/index or commodity-future underlyings with listed options are shown.

Search the selected broker’s supported instruments. Entering text does not select a verified execution contract.

### UnderlyingChoose an underlying; the completed EMA Band signal chooses Call (CE) or Put (PE).

Select the exact supported broker instrument for this workflow. Search results must be resolved to current master metadata before execution.

### ModePaper/forward testing is active. No broker order route exists in this mode.

Choose Paper simulation or explicitly authorized Live execution. Saving a setting does not start trading.

### LotsQuantity for the automatic BUY entry order.

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Stop-loss (%) (optional)Optional extra safety net: auto-exit SELL is submitted early if the option price falls this % below entry. Leave blank to exit purely on the EMA Band indica

Optional option-premium percentage stop below the filled entry. Blank retains the normal indicator-based exit policy.

### Target (%) (optional)Optional extra safety net: auto-exit SELL is submitted early if the option price rises this % above entry. Leave blank to exit purely on the EMA Band indicator

Optional option-premium percentage target above the filled entry. Blank retains the normal indicator-based exit policy.

## Delta research parameters

### Research underlying

Select the exact supported broker instrument for this workflow. Search results must be resolved to current master metadata before execution.

### Start date · IST

Beginning of the research history in IST.

### End date · IST · inclusive

Inclusive end date of the research history in IST.

### Held-out tail · %

Chronological tail percentage reserved for held-out evaluation instead of fitting.

### RSI lengths · comma-separated

Comma-separated RSI periods to compare in the research grid.

### RSI MA lengths · comma-separated

Comma-separated RSI moving-average periods to compare.

### Entry rules to compare

Compare the supported crossover-only or crossover-plus-EMA-touch entry rules.

### Futures direction

Research long-only, short-only or both futures directions. This does not change a live runner.

### Select ADX(14) entry filter

Include the ADX entry filter in the selected research configuration.

### Compare ADX off / on

Compare both enabled and disabled ADX variants in the research grid.

### Select previous-candle momentum filter

Include the previous-candle momentum entry filter in research.

### Compare momentum off / on

Compare both enabled and disabled momentum variants.

### ADX thresholds · comma-separated

Comma-separated ADX thresholds tested by the research grid.

### Bollinger lengths · comma-separated

Comma-separated Bollinger lookbacks used to study volatility squeeze.

### Standard deviations · comma-separated

Standard-deviation multipliers for the research Bollinger bands.

### Squeeze history · bars · comma-separated

Lookback bars used to rank historical squeeze observations.

### Squeeze percentiles · comma-separated

Percentile thresholds used to classify volatility squeeze.

### Release windows · bars · comma-separated

Bar windows over which a research squeeze release may qualify.

### Initial equity · native USD (engine input)

Initial equity in native USD for the research engine; not a broker deposit.

### Fixed contracts

Fixed contract quantity used by the research simulation.

### Fee allowance · bps / fill

Assumed fee basis points for each simulated fill.

### Slippage · bps / fill

Assumed slippage basis points for each simulated fill.

### Half-spread · bps / fill

Assumed half-spread basis points per simulated fill.

### Funding drag · bps / day

Assumed funding drag in basis points per day; actual funding can differ.

### Inspect period

Inspect training or chronological held-out research results.

## Delta trading parameters

### Broker

Select the saved broker account used by this workflow. Data, funds, instruments and execution stay scoped to that account.

### Workflow

Choose read-only analysis, Paper, explicitly authorized Live execution, or research backtesting. These modes have different side effects.

### Contract type

Filter the broker contract master by supported derivative type.

### Instrument search

Search the selected broker’s supported instruments. Entering text does not select a verified execution contract.

### Exact listed instrument

Select the exact supported broker instrument for this workflow. Search results must be resolved to current master metadata before execution.

### Timeframe

Candle interval for this workflow’s signals or replay. Active jobs retain their captured Start interval unless an explicit supported change is applied.

### RSI length

Number of completed price changes used to calculate the RSI that drives this workflow’s signal.

### RSI MA

Type of moving average applied to RSI, not to underlying price.

### RSI MA length

Period of the moving average applied to RSI.

### Manual Submit side

Direction for the next manual ATM option ticket: bullish buys a Call; bearish buys a Put.

### Quantity · contractsWhole Delta contracts; units shown above.

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Order type

Limit uses a price cap; market uses available executable prices. Both remain subject to supported broker terms.

### Option limit premium · native quote points

Limit premium for the exact option, in native quote units and aligned to its tick size.

### Time in force

IOC cancels an unfilled remainder; GTC can remain outstanding until filled or cancelled.

### Position control

Reduce-only restricts an order to decreasing existing exposure; it does not open a new position.

### Strategy executionUnderlying RSI signals · ATM options by default

Choose bought ATM options or supported futures long/short execution for the strategy.

### Runner signal direction

Allow both supported signal directions or restrict the runner to bullish calls.

### Runner trailing stop · optionalOff by default · application-managed

Enable the strategy’s optional application-managed trailing exit. Manual orders do not automatically inherit a runner’s trailing policy.

### Trailing step mode

Choose entry-based percentage/points step trailing or the separately supported full-position ATR trailing mode.

### Trailing step

Distance for the selected trailing policy, in percentage or native quote points as labelled.

### ADX entry filter

Enable the optional ADX strength entry filter. It does not disable independent exits.

### Minimum ADX · must exceed

Minimum ADX strength required by the enabled entry filter; the selected strategy’s strict comparison applies.

### Saved contract / timeframe

Choose a saved contract/timeframe view. Opening it is not Start authorization.

## RSI / MA crossover runner parameters

### Strategy label

Friendly label for this strategy instance; it does not alter signal calculations.

### Execution mode

Choose Paper simulation or explicitly authorized Live execution. Saving a setting does not start trading.

### Maximum trades per runCaps entry orders, including uncertain submissions. Exit orders remain allowed. Resets only on a new start while flat.

Maximum new entries per run. Exit orders remain allowed, and a new flat Start creates a new run quota.

### Virtual Paper capital · INR

Virtual Paper INR capital used for affordability and reservations; it does not alter live broker funds.

### Lots

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Underlying spot target (optional)When either spot level is entered, EMA exit is ignored.

Optional absolute underlying target. In this RSI/MA runner, setting either underlying hard level suppresses the EMA exit as described by the workflow.

### Underlying spot stop-loss (optional)Completed-close checks. Blank levels are unused.

Optional absolute underlying stop checked on completed closes. Blank leaves that level unused.

### Quoted premium cap per entry (₹, optional)Leave blank for no per-entry cap. Any configured daily budget still applies.

Optional per-entry quoted premium cap; blank disables that cap while any daily budget still applies.

### Daily loss budget (₹, optional)Leave blank for no daily budget. When set, realized losses plus new premium must fit; fees are additional.

Optional daily INR loss budget for this runner; realized losses and new premium are checked by its policy.

### Trailing stopOption premium · optionalOff

Enable the strategy’s optional application-managed trailing exit. Manual orders do not automatically inherit a runner’s trailing policy.

### Trailing mode

Choose a percentage of the filled option entry or a fixed premium-point step; it does not compound the base distance.

### Trailing stepPercentage defaults to 10%. Points require your positive distance. Fixed distance; never compounds.

Positive fixed trailing step. Percentage and premium-point units depend on the selected trailing mode.

## EMA Band and KAMA parameters

### Underlying search

Search the selected broker’s supported instruments. Entering text does not select a verified execution contract.

### Broker-master instrument

Select the exact supported broker instrument for this workflow. Search results must be resolved to current master metadata before execution.

### Signal timeframe

Candle interval for this workflow’s signals or replay. Active jobs retain their captured Start interval unless an explicit supported change is applied.

### RSI length

Number of completed price changes used to calculate the RSI that drives this workflow’s signal.

### RSI smoothing

Use SMA or EMA as the smoothing of RSI for completed-candle crossovers.

### RSI MA length

Period of the SMA/EMA applied to RSI.

## Holdings review parameters

### Broker

Select the saved broker account used by this workflow. Data, funds, instruments and execution stay scoped to that account.

### Show${Object.entries(labels).map(([key, text]) =>

Filter the holdings review results by the displayed category. It does not sell or rebalance holdings.

## Renko Engine parameters

### Broker account

Select the saved broker account used by this workflow. Data, funds, instruments and execution stay scoped to that account.

### Execution mode

Historical replay, Paper or Live Renko Engine mode. Live requires its supported broker/runtime and explicit Start.

### Underlying search

Search the selected broker’s supported instruments. Entering text does not select a verified execution contract.

### Instrument

Select the exact supported broker instrument for this workflow. Search results must be resolved to current master metadata before execution.

### Timeframe

Candle interval for this workflow’s signals or replay. Active jobs retain their captured Start interval unless an explicit supported change is applied.

### Lots / Delta contracts

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Maximum entries per run

Maximum new entries per run. Exit orders remain allowed, and a new flat Start creates a new run quota.

### Paper capital · INR

Virtual Paper INR capital used for affordability and reservations; it does not alter live broker funds.

### History

Historical replay window; it is research input rather than an active-run reset.

### Deterministic anchor/start · IST

Deterministic IST start/anchor for the recurrence and eligible replay window.

### Percentage base hypothesis

Select the engine hypothesis for the price base used in percentage sizing.

### Directions

Permit long, short or both directions in the engine hypothesis.

### Research end · IST

End of the research/engine evaluation window in IST.

### Fixed box (points)

Fixed brick distance in native underlying price points.

### Flat hour · IST

Hour of the configured session flat boundary in IST.

### Flat minute · IST

Minute of the configured session flat boundary in IST.

### Brick calculation

Choose percentage or fixed-price brick calculation. This is the engine brick mode, not Paper/Live execution mode.

### Brick %

Percentage used to derive a brick from the selected percentage base.

### Range window · IST (HHMM-HHMM)

IST interval used to construct the displayed intraday range study.

### Reversal threshold (bricks)

Required opposing move in brick units before the engine changes direction.

### Round brick to symbol tick

Round the calculated brick to the selected symbol tick.

### Entry hypothesis

Choose the explicitly labelled entry hypothesis; these research rules are not interchangeable.

### Anchor level (0 = first close)

Initial synthetic level; zero seeds it from the first eligible close.

### Anchor direction (-1 / 0 / 1)

Initial direction: -1 bearish, 0 neutral or 1 bullish.

### Entry session · IST (HHMM-HHMM)

Permitted IST entry window in HHMM-HHMM form.

### NSE intraday session filter

Restrict entry eligibility to the configured IST session and enable its session flat rule.

### Previous daily HLC CPR

Show central pivot range calculated from previous daily high, low and close. Chart context only.

### Opening / first later red 44 / 56

Show opening/first-later-red 44/56 chart study. Chart context only.

### Intraday range 44 / 56

Show the selected intraday range 44/56 study. Chart context only.

### Step hypothesis

Select how the engine advances its synthetic level after a price move: whole bricks, one per bar, or price-minus-brick.

## Server resources parameters

### History

Time window for displayed retained resource samples. It does not change services or restart them.

### Service to restart

Choose the dashboard or selected broker service, inspect exposure requirements, then explicitly request its restart. Frequent probes report the result.

## Telegram parser parameters

### Channel display nameDisplay name only; channel ID and bot access are still required.

Friendly display name for a Telegram source; a valid channel identity and bot access are still required.

### Channel @username or -100 ID

Exact public channel handle or private numeric channel identity accessible to the configured bot.

### Polling interval · seconds

Polling interval in seconds. Polling discovers new evidence; it does not guarantee a fill or replay old submissions.

### Order broker

Select the saved broker account used by this workflow. Data, funds, instruments and execution stay scoped to that account.

### Quantity · whole Delta contracts

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Auto submission

Explicit optional automatic submission policy. It is separate from loading recommendations; startup backlog remains review-only.

### Telegram recommendation text

Recommendation text used for parsing and review. Text edits invalidate an existing ticket.

### Entry type

Limit or stop-limit entry. Stop-limit requires a valid trigger and limit relationship.

### Trigger price

Trigger price for a supported stop-limit order; triggering does not guarantee a fill.

### Limit price

Limit price for the ticket, aligned to the selected broker contract’s tick.

### Ticket product

Choose the supported bought-ATM-option Renko owner workflow or the explicitly labelled legacy exact-contract route.

### Option execution mode

Paper simulates the selected option route; Live can send a real option order on explicit Submit.

### Whole option contracts

Whole position quantity in the labelled lots, shares or contracts. Use the selected contract’s current lot and multiplier; sizing is not silently reduced.

### Renko timeframe

Candle interval for this workflow’s signals or replay. Active jobs retain their captured Start interval unless an explicit supported change is applied.

### Renko EMA exit period

EMA period for the selected completed-candle Renko exit.

### XAUUSD → XAUT bought options · explicit gold-token proxy

Explicitly permit the labelled XAUUSD-to-XAUT gold-token option proxy. This is not the same instrument as spot gold.

### Completed-candle EMA exit

Enable the selected completed-candle EMA exit for the option owner.

### Renko Supertrend exit

Enable the supported Renko Supertrend exit for the option owner.

### I reviewed the mapped option, entered quantity and selected Renko exits; enter now when I click Submit.

Explicit review of mapped option, quantity and selected exits before Submit. It does not make an old recommendation fresh.

## WhatsApp parser parameters

### Exact group name

Exact WhatsApp group/chat name used by the local native polling helper.

### Interval (seconds)

Polling interval in seconds. Polling discovers new evidence; it does not guarantee a fill or replay old submissions.

## Analysis handoff parameters

### AI analysis path

Choose broker candles/rule-based analysis with no AI call, or Codex / ChatGPT-account analysis. An API key is not required by these configured choices.

### Index and commodity instruments

Select one to six broker-native symbols for the asynchronous market analysis job.

## Runner jobs parameters

### Find a job

Filter visible jobs by the displayed account, instrument, strategy or status.

### Include stopped / saved

Include inactive saved instances/history in the job view. This does not restart them.

## Appearance and access parameters

### Visible dashboard sections

Choose which permitted sidebar sections are displayed. Hiding a section does not stop its jobs or grant missing permissions.
