# Renko on Delta India — read-only feasibility assessment

Updated 7 October 2026. Delta Renko is now wired to the shared Renko engine through a separate broker adapter, backend public WebSocket, stable history anchor and independent runner/adoption state. FYERS and Delta instances can coexist, with per-instrument settings, ownership, quotas and targeted controls. Batch activation uses durable request identities and explicit per-symbol outcomes.

The compact dashboard exposes broker/market search, multi-selection, selected-runner status and disclosures for secondary details. FYERS categories come from actual NSE/BSE cash/index plus option masters and MCX futures/options; Delta signals use perpetual candles and require an actual listed long Call/Put route. No perpetual execution fallback exists.

Validation: 212 Renko tests, 77 shared EMA tests, 31 existing Delta lifecycle tests and 9 chart/RSI tests pass. The exact NIFTY Paper-position/BTC Paper-instance coexistence scenario is exercised with isolated fake brokers. Browser verification uses stopped production instances and live public market data; it does not establish real live fill performance. No live runner starts or real orders were made for validation. Native fees are estimates, open liquidation costs may remain unavailable, and adoption cannot invent historical fees or original entry-time evidence.

## Preserved engine and separate Delta workspace

The Renko strategy is implemented in `strategies/renko_supertrend/signals.py` and `runner.py`, with separate retest/pattern, proximity, trailing, sideways and adoption modules. These are the current preserved Sector Pulse rules, not a claim of parity with a protected external indicator.

The separate Delta India workspace retains its RSI-based strategy. Delta Renko is selected inside Renko Support and Strategy and uses the shared Renko engine rather than that RSI strategy or a display-only brick transformation. Selecting a chart or switching brokers does not activate either runner.

## Shared rules and broker-specific boundaries

| Area | Feasible approach |
| --- | --- |
| Signal calculations | Share the existing Renko engine: supplied synthetic Renko/Supertrend recurrence, Auto/Manual sizing, configurable ADX, host-price EMA10/30 alignment, strict widening and qualification rearming. Keep the existing seeding, warmup and history-revision recovery rules. |
| Retests and filters | Reuse the same completed-candle EMA10 retest/pattern modules, optional EMA proximity and quick-loss exposure-range filter. Do not substitute Delta's RSI candle-extreme touch or its separate ADX/momentum filters. |
| Exits and re-entry | Preserve the Renko EMA adverse exit, opposite confirmed Supertrend exit with its ADX policy, optional underlying levels, full-position trailing and no same-candle re-entry. Delta's existing stepped/partial-target trailing is a different rule set and must not replace Renko trailing. |
| Chart and live data | Reuse the candlestick/synthetic display, EMA/Supertrend lines, RSI zones, actual host volume, P&L overlay and fullscreen arrangement. Adapt Delta candle timestamps/resolution names and product tick metadata. Intrabar strategy evaluation needs an authoritative backend feed; browser-only WebSocket display is insufficient for independent management when the browser is closed. |
| Execution | Keep bullish = buy nearest-expiry ATM Call and bearish = buy nearest-expiry ATM Put as the closest existing Renko execution model. Reuse Delta's catalog and `chart_option` resolver, but adapt `product_id`, contract units, expiry, quote/settlement currencies, fresh executable quotes, margin and fill reconciliation. Perpetual long/short execution would be a separate execution choice. |
| Adoption | Reuse the user workflow and ownership/recovery principles, with a Delta-specific position/order adapter. FYERS's MARGIN label cannot be carried over as a Delta product classification. Initially support verified long options; preserve actual filled signed size, average, product identity and account. Separate claims, pending orders, external changes and restart recovery are required. |
| Order terms and P&L | Renko currently uses FYERS MARKET/MPP semantics; Delta's runner currently uses marketable IOC limits and reduce-only exits. These cannot be silently treated as identical execution. Use exact Delta contract valuation/currencies and recorded fills/fees; do not reuse the FYERS statutory-cost model or assume identical performance. |
| Schedule | NSE/BSE and MCX cutoffs are broker/session policy, not portable crypto rules. The daily cutoff/carry policy must be chosen explicitly and product expiry must still be honored. Do not silently remove the existing timed exit or assign an NSE/MCX segment to Delta. |

Delta Renko supports 1/3/5/15/30-minute and 1-hour candles. Unsupported 2/10-minute choices are removed in Delta view; no implicit resampling or fallback occurs.

Delta's current valuation adapter accepts verified linear vanilla contracts and rejects unverified inverse/quanto conversions. A first implementation should retain that constraint rather than invent conversion or margin assumptions.

## Explicit configuration controls

1. Select the Delta signal instrument and price basis: the existing perpetual-candle source versus an explicitly supported index/spot source. Different candle sources can produce different signals even when the formulas are identical.
2. Confirm long ATM Call/Put execution as the closest match; adding perpetual long/short trading expands the execution scope.
3. Choose the daily square-off/carry schedule for Delta, alongside the contract's actual expiry. Keeping the existing numerical cutoff is possible, but it must be an intentional policy rather than an inferred exchange closing time.
4. Choose Delta order terms explicitly if matching FYERS MARKET behavior is required rather than retaining Delta's existing IOC-limit execution.

Validation should compare the shared engine on identical normalized candles/settings, then separately exercise broker-specific Paper execution, adoption, partial/unknown fills, duplicate claims, external closure, stale feed/reconnect, restart, expiry and schedule boundaries. Formula reuse cannot make different market feeds, order fills or P&L identical.

## Primary API evidence

The [official Delta India API documentation](https://docs.delta.exchange/#place-order) defines product IDs, size, order types/time-in-force and reduce-only exits, and the [WebSocket documentation](https://docs.delta.exchange/#websocket-feed) provides public market and private account channels. The [Delta India overview](https://guides.delta.exchange/delta-exchange-india-user-guide) describes continuous crypto trading; expiry and schedule checks must still use the actual listed product and intended policy.

The [user functional guide](user-functional-guide.md) and its [browser version](user-functional-guide.html) are updated and browser-verified for the deployed FYERS adoption and volume features. The guide now covers independent instances, batch start, compact navigation and native Delta execution policy.
