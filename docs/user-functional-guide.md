# Sector Pulse User Functional Guide

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
- Session square-off uses the instrument's broker-master segment and verified session policy. The usual cutoffs are 15:15 IST for NSE/BSE and 23:30 IST for MCX. New adoption is unavailable after its cutoff.

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
