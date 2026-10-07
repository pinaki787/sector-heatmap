# Renko Supertrend Strategy

The preserved [source.pine](source.pine) supplies the synthetic Renko/Supertrend recurrence, initialization, ATR regimes and optional ADX calculation. Source-text arithmetic parity is checked across 1,720 states. Protected-indicator and TradingView exported-runtime parity are not established. Market host candles and calculated synthetic bodies are separate chart views.

## User functional guide

The [Renko Support and Strategy user guide](../../docs/user-functional-guide.md) covers refreshing broker orders/positions, selecting filled long MARGIN options, **Apply Renko · start LIVE management** without an initial BUY, existing exits, optional re-entry, pause/resume and restart recovery. It also explains actual host-volume bars, unavailable versus zero volume and forming-volume snapshot limits. [Open the browser guide](../../docs/user-functional-guide.html).

## Existing FYERS positions and chart volume

Refresh the broker inventory in the Renko strategy view. Select already filled,
long MARGIN options on the chosen underlying, then use **Apply Renko · start LIVE
management**. The button applies the visible settings to each selected position.
It never submits an initial BUY. Each manager has a separate durable journal,
quota, signal state and ownership claim. The adopted position counts as the first
trade; subsequent entries use the configured lots and remaining trade quota.
Re-entry is an explicit option, off by default.

The existing Renko runner manages EMA, opposite confirmed signal, configured
hard boundaries, optional trailing and session square-off. Its existing fresh
signal rules govern later entries. Each manager shows broker average, quantity,
gross unrealized and realized P&L, and saved adoption/order evidence. Historical
entry time, fees and pre-adoption tick exposure are not fabricated. The original
adopted lifecycle is not retrospectively classified as a quick-loss trade; its
true exposure age is unavailable. Subsequent runner entries retain normal
journal and sideways-range behavior.

Pending/partial-entry orders, partial-lot positions, shorts, other products,
unmapped options, another strategy's claim and outstanding protective orders
block adoption. Symbol, quantity, average, product, account and current master
are checked again before ownership is saved. Broker order statuses are displayed
separately from positions. Batch managers initialize before any monitoring loops
start; initialization failure preserves stopped ownership for review.

A restart leaves every adopted manager stopped, preserving exposure and pending
intent. **Reconcile / resume** verifies broker ownership before resuming. An
owned pending order resumes its original reconciliation rather than resubmitting.
External quantity/average/side/product changes or unavailable broker evidence
pause management and preserve the claim. A fresh confirmation of external full
closure releases the claim without inventing an exit fill or starting re-entry.
Changed, ambiguous exposure requires manual reconciliation. **Pause monitoring**
stops monitoring and preserves ownership; it does not request a square-off.

Volume uses actual FYERS host-candle volume on a separate lower chart scale and
shares the exact candle timestamps. Missing volume is a whitespace gap, with an
unavailable readout; real zero remains zero. Forming volume is a broker snapshot,
not a value inferred from LTP ticks. Synthetic display volume remains explicitly
host volume rather than fabricated per-brick volume.


## Entry rules

EMA10 and EMA30 use real underlying host closes with Pine-style first-value EMA seeding. A bullish/green Supertrend permits only a bullish setup: EMA10 > EMA30, price above EMA10 and a strictly increasing positive EMA10−EMA30 gap. Bearish/red requires the exact inverse and permits only the bearish setup. BUY purchases nearest-expiry ATM Call; SELL purchases nearest-expiry ATM Put, never writes an option. Current-master contracts, lots, tick size and multiplier are validated; unsupported routes have no futures fallback.

Defaults: widening window **2** (one increase), ADX **off**, Paper mode. Stricter widening windows and ADX remain available. Intrabar entries are explicitly opt-in. A fresh forming candle is evaluated from a **cloned confirmed state**, using fresh underlying exchange-timestamped updates. Ticks never cumulatively advance ATR, EMA or synthetic Renko state. The candidate can disappear. Fresh regime/alignment/qualification is rechecked at submission. Saved candle identity, ownership, intent and reconciliation prevent duplicate/flapping orders. No same-candle re-entry is permitted.

## Exit and session rules

An owned Call exits when fresh underlying price is strictly below provisional EMA10; a Put exits strictly above. Equality alone is not a breach. Already-adverse restored positions do not require another crossing. EMA10 exits are independent of ADX, widening and opposite-entry eligibility. Opposite **confirmed** Supertrend reversal is an additional exit and honors the optional ADX filter.

EMA exit can be disabled or use an editable period (1–1000, default 10). Optional absolute underlying target/stop prices also trigger on fresh ticks. These settings apply on the next Start; they do not change an armed run.

The optional Sideways filter defaults **off**. A finalized trade with an estimated after-cost loss that touches at most three host candle buckets (editable 1–10) freezes only the underlying high/low observed during actual first-fill-to-final-exit exposure. Prior swings and historical candle extrema are excluded. New entries remain blocked inside or on that range; a fresh tick strictly beyond either boundary releases the lock and resets entry eligibility, without forcing entry or replaying an old signal. Exits and reconciliation continue normally. Extrema, duration, trigger and release evidence persist with the journal; old missing ticks remain unknown.

The authoritative FYERS master exchange/segment determines the requested session deadline: NSE/BSE **15:15 Asia/Kolkata**, MCX **23:30 Asia/Kolkata**. Commodity-sector NSE/BSE stocks remain equities. A stricter verified regular-session end takes precedence. New entries are blocked at/after the applicable cutoff. Wall-clock scans mark owned exposure for timed exit independently of underlying ticks or candle closure. Pending entry remainder is cancelled and terminal/partial fills reconciled before closing only owned quantity. Overdue exposure remains an exit obligation across the local date boundary. Fresh executable option quotes and broker acknowledgements determine fill timing; an exit intent is not a guaranteed fill by the deadline. Missing/holiday/stale market data cannot authorize an entry.

## Controls and persistence

One explicit **Start Runner / Stop Runner** toggle uses the selected visible Paper/Live mode. There is no visible preview or typed confirmation. The server atomically performs configuration revision, current-master/account/data validation, process ownership and existing live-gate checks internally. Start does not replay historical signals. Stop cancels remainder and closes owned exposure, displaying **Stopping…** until reconciled flat; requests and restart races are blocked. The assistant does not activate the actual runner during verification.

All controls, including false checkbox values, Manual brick size, selected instrument/timeframe, limits and mode, persist until deliberately edited. Versioned UI preferences have a separate durable file from armed runner state; restoring preferences never activates trading or mutates a running configuration.

Flat runs subscribe to both current ATM option directions ahead of entry. If the first subscription has no quote, only the still-fresh confirmed signal can retry before any order intent or deduplication key exists. Expired signals, other validation failures and uncertain broker acknowledgements never use this retry. Guarded same-run Paper recovery requires identical saved settings/account and no exposure; it preserves run ID, trade quota, realized P&L and journal while requiring fresh post-recovery signals.

## Chart and trade reporting

The historical chart/table simulates closed-candle BUY → BUY EXIT and SELL → SELL EXIT lifecycles, with EMA10/ST/deadline reasons. Active positions suppress repeated entry labels. Exit consumes its candle; later qualified setups can re-arm, including in the same Supertrend regime. Provisional live candidates are separate. OHLC-only history cannot prove intrabar fills.

The chart defaults to 45 calendar days (about 30 sessions where broker data exists), with 7/90-day and custom range controls. Fixed-contract history is requested in three-day chunks and cached atomically on disk; all selected candles remain scrollable, with a readable recent initial view. Seven preceding calendar days are requested for initialization. The available range, actual anchor and warmup count are displayed. Older ranges or completed candle revisions cause a full sequential replay and may change path-dependent signals. Response deltas are used only when the entire completed analysis revision matches. Review ranges are bounded to 91 calendar days and 150,000 bars; in-process range caches retain six entries. Historical simulation events are paged separately from actual trades.

Actual trade history uses durable owned option fills: contract, Call/Put, strike/expiry, stable Paper run/trade/order IDs or actual FYERS broker IDs, requested/filled/remaining quantity, multiple exit IDs, local fill-confirmation times, underlying entry/exit observations and option premium averages. Underlying observations are explicitly captured at local fill confirmation and may not equal the unavailable exact exchange-fill spot. Missing old values remain unavailable. Realized P&L uses confirmed premium fills × quantity × verified multiplier; executable option bid determines open unrealized P&L. Gross values are signed and colored before fees; estimated net values include the separately disclosed costs. The durable journal stores immutable entry/exit indicator and configuration snapshots at actual strategy events, confirmed reference state, gap history, anchor/revision, quote observations and partial/reconciliation event timestamps. The existing atomic runner state retains all order rows without truncation; journal schema version 1 leaves older absent snapshots unknown. Expand saved snapshots, filter Paper/Live, or export the formatted Excel workbook for review. Acceptance is not a fill. Signal simulations never fabricate contract/order/P&L values.

## Verification

The Excel export contains an executive summary, trade register, saved indicators, order audit, estimated costs and position ranges. Gross and estimated net P&L appear inside the streamed chart. The Sensex-options cost model charges ₹15 once per executed BUY or SELL order, verified statutory charges and explicitly configured additional option premium points per side (default zero). Actual fill-price slippage is already embedded and is not deducted twice. Open liquidation separately deducts remaining entry costs and estimated exit costs using a fresh executable bid; stale marks remain unavailable. Live fees are fill-based estimates pending broker contract-note reconciliation. Rate sources, rounding and assumptions accompany each trade. The workbook is a static journal snapshot; historical chart simulations remain excluded.

Run `python3 -m unittest discover -s strategies/renko_supertrend -t . -p 'test_*.py'` and `node --test tests/renko-chart.test.cjs`. Tests cover source recurrence, warm-up, strict widening, late qualification, EMA exit symmetry and ADX independence, fresh cloned ticks, ownership, duplicate/partial/unknown orders, no-tick deadlines, master segment policies, rearming, preference roundtrips and option P&L/IDs. Shared lifecycle regression tests remain under `strategies/ema_crossover`.

`research_replay.py` is a cost-modeled closed-candle underlying proxy, not intrabar tick execution, ATM-option performance or promotion evidence.

## Investigation history and resume

Read the [Persistent churn investigation ledger](../../docs/renko-churn-investigation-ledger.md) before reassessing entry churn. It records every assessed hypothesis, reproduction, result and accepted/rejected/unresolved conclusion, and links archived evidence and the isolated correction patch. Documentation is not deployment; preserve original rules and refresh served process/state before further changes.
# Cash equity selection and sizing

The Renko Market picker includes **NSE cash equity** and **BSE cash equity**.
These routes search the broker cash master, including stocks without options,
and exclude indices. Quantity is an exact positive whole number of shares;
no option lot size is applied. Stock options retain lot-based ATM Call/Put
resolution and their existing product and signal rules.

Cash **Intraday** maps to FYERS `INTRADAY`: bullish entries BUY shares,
bearish entries SELL shares short, and exits close the held side. Broker
reconciliation compares signed quantities. Paper fills use the executable
ask for buys and bid for sells, including short entry and buy-to-cover.

Cash **Carry forward (overnight)** maps to FYERS `CNC`. Bought shares remain
owned across the 15:15 cutoff and overnight, with signal monitoring resuming
in regular market hours. New bearish CNC entries are blocked explicitly;
bearish signals still close existing long shares. Broker holdings/day-position
ambiguity blocks exits rather than borrowing external holdings. Delivery sell
authorization remains required by FYERS.

Cash gross P&L and owned-fill journals support both sides. Cash after-cost
estimates are unavailable until a verified cash fee model is supplied. The
optional after-cost sideways filter therefore cannot be enabled for cash.

References: [FYERS delivery products](https://support.fyers.in/portal/en/kb/articles/how-to-place-an-overnight-delivery-order-in-fyers),
[official API product mapping](https://github.com/FyersDev/fyers-skills/blob/master/skills/fyers-trading/references/orders.md).

### Market-aware cutoff policy

New Delta setups default to `CONTINUOUS`: seven-day signal monitoring has no daily cutoff or midnight forced exit. Saved `DAILY_SQUARE_OFF` configurations retain their selected IST cutoff. This route still executes dated ATM options from perpetual signal candles; it does not execute perpetual futures. Each held option requests an expiry protection exit 60 seconds before its exact broker `expiry_epoch`; entries inside that window are rejected. Fresh executable quotes and normal reconciliation remain required, so an exit fill is not guaranteed and exchange settlement remains authoritative.

New NSE/BSE intraday Renko configurations use a 15:10 IST strategy cutoff (normal market close is later). CNC positions retain overnight carry. MCX uses the selected current FYERS master regular-session end, including commodity and seasonal differences; unsupported or ambiguous session metadata fails closed. Existing armed configuration is not rewritten on deployment.

### MCX holding choice

MCX `INTRADAY` is a strategy session-end square-off policy; `CARRY_FORWARD` retains owned long options across session ends and local date rollover. Both use the established FYERS commodity option `MARGIN` product, never cash `CNC`. Lots, ATM CE/PE selection, stops, fresh-data gates and exact-product ownership reconciliation are unchanged. Outside verified regular sessions the carry runner waits without sending orders.

Carry entries require exact option expiry from the current master. The strategy requests an exit 30 minutes before the preceding weekday session ends and blocks new entries inside that window. This conservative rule avoids intentionally carrying into option expiry/devolution; it does not guarantee a fill, account for exceptional holiday closures, or supersede earlier broker RMS action. Broker/exchange ownership changes remain reconciliation failures, not permission to trade converted futures. Missing expiry blocks further entries and requests closing the owned option in an executable session.
