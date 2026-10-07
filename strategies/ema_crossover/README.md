# RSI based SMA / RSI based EMA

The selected MA type controls both the strategy label and RSI smoothing. Wilder RSI defaults to14, and its SMA or EMA defaults to14; SMA is the default. The saved implementation enters only on a fresh completed RSI crossover: previous RSI <= previous MA and current RSI > current MA buys Call; the inverse buys Put. A later opposite crossover exits; equality holds. Forming candles never authorize orders. Existing sizing, FYERS routing, intent/fill reconciliation, Stop Runner and no re-entry on the exit candle remain.

The chart displays websocket ticks every second and aggregates forming OHLC from received ticks. History bootstraps once, then reconciles at candle boundaries using shared caching and30-second error backoff. REST quote fallback is cached10seconds. The runner targets a one-second scan and acts only on provider-confirmed completed candles. Provider publication latency still applies.

Indicators are selected from a compact dropdown. Wilder RSI/selected MA and volume have synchronized panes. Source-ported Red Bar zones retain the Pine defaults and completed-close invalidation, contiguous retest counting, fading and age expiration. Sessions use IANA opening times with DST. Fixed/session and floating red5m Fibonacci, CPR and period references are optional. Manual lines/rectangles are editable, removable and saved per symbol/timeframe. Fullscreen has an explicit exit button.

The original Pine remains untouched. Ported logic is independently checked on identical OHLC; active TradingView parity requires matching feed, contract, history and settings. Private Dr Devendra Renko formulas are unavailable. No profitability or live-order validation is claimed. Restart does not auto-start it. See the deployment boundary below for the active paper runner.

## Contract valuation and funds repair (2026-10-01)

Every selected option is validated against FYERS CSV and named JSON master metadata: symbol/token, expiry, option type, strike, API lot size and tick must agree. `qtyMultiplier` is required for every exchange; no symbol-specific multiplier table or default of 1 is used. JSON masters are cached in memory for 15 minutes. Missing/conflicting metadata blocks entry with a refresh instruction.

API quantity = requested lots × `minLotSize`. Rupee premium = API quantity × quoted ask × `qtyMultiplier`. The same multiplier is persisted with the owned position and used for unrealized P&L, realized partial-fill P&L and daily realized losses. API order quantities remain in broker units. Premium limits, daily budgets and the 1% premium reserve use rupees. Legacy positions lacking a verified multiplier show unavailable P&L and require reconciliation; values are never guessed.

Funds come from the existing Available Balance parser, reflecting FYERS' shared equity/commodity pool. The independent broker margin calculator remains mandatory. A read-only MARKET calculation with zero limit price returned zero incremental margin; this does not waive the premium-plus-reserve check or guarantee order acceptance. Broker cash/collateral restrictions and final margin eligibility still apply.

Validation: 57 runner/broker/valuation tests, 13 shared execution tests and 3 chart-signal tests pass. Fresh public CSV/JSON validation covered 14,934 MCX, 79,012 NSE and 7,446 BSE unexpired options with no mismatches. These are calculation and metadata checks, not live-order validation.

Reproduce without broker mutations:
```
PYTHONPATH=.:strategies .venv/bin/python -m unittest discover -s strategies/ema_crossover -p 'test_*.py'
.venv/bin/python -m unittest tests.test_fyers_execution
node --test tests/ema-crossover.test.cjs
PYTHONPATH=. .venv/bin/python strategies/ema_crossover/check_master_valuation.py
PYTHONPATH=. .venv/bin/python strategies/ema_crossover/audit_contract.py EXACT_MASTER_SYMBOL
```

Authoritative sources: [FYERS shared funds](https://support.fyers.in/portal/en/kb/articles/can-i-use-the-same-funds-for-trading-on-both-nse-and-mcx), [MCX JSON master](https://public.fyers.in/sym_details/MCX_COM_sym_master.json), [NSE JSON master](https://public.fyers.in/sym_details/NSE_FO_sym_master.json), [BSE JSON master](https://public.fyers.in/sym_details/BSE_FO_sym_master.json).

## Read-only chart additions — 1 October 2026

Multi-timeframe RSI table contains exactly5m,15m,30m,6h,day,week,month. It uses selected Wilder RSI length and selected SMA/EMA RSI smoothing. Values exclude forming periods and carry completed-close timestamps; exact-expiry history is never spliced. Bootstrap then incremental provider caches are300s intraday,3600s daily and21600s weekly/monthly; display requests are at most once per minute and disabled when hidden. Errors back off60s. A conservative five-RSI-length plus MA history target avoids short seeding. Weekly/monthly confirmation uses next calendar period.6h aggregates contiguous30m bars from exchange open, including the shortened close bucket; unknown commodity schedules or incomplete source coverage show Unavailable.

Indicators → Multi-timeframe RSI table hides/shows in both normal/fullscreen; local preference persists. Bollinger Bands are independently optional, default off, with persisted length20/deviation2 defaults. SMA of closes and population standard deviation define the three lines and subtle fill. Forming-band display never affects strategy orders.

Fib opening/first-red caption overlap was caused by close legitimate prices with unspaced canvas text. Labels now share collision layout with zones/period references, retain exact horizontal price lines, and use opaque backgrounds and leader lines. Leaders paint before captions. The OHLC legend is protected.

Validation:63 strategy/runner tests,41 web tests,5 RSI table tests,16 JS tests pass (125 total). Table hide/show reload persistence and BB21/2.5 custom reload persistence verified, then default20/2 restored. Normal/fullscreen, pan/zoom and1024×900 resize checked. No browser warnings/errors. Current CRUDEOILM expiry has confirmed5m/15m/30m/day values;6h is unavailable for incomplete30m coverage and week/month have23/6 completed periods against84 target. Existing paper runner became active during review; final restart was cancelled before mutation and the active runner was left untouched.

Screenshots: output/rsi-table-bollinger-labels-fullscreen-20261001.jpg; output/chart-labels-zoom-pan-20261001.jpg; output/chart-labels-resized-20261001.jpg.

Data references: [FYERS market data](https://github.com/FyersDev/fyers-skills/blob/master/skills/fyers-trading/references/market-data.md), [MCX sessions](https://www.mcxindia.com/market-operations).

## Crossover, optional trailing and position history — saved implementation

Backend revision `rsi-crossover-trailing-v4` is saved and tested but not loaded. Server revision `cloud-shared-funds-multiplier-v2` remains active with PAPER CRUDEOILM8850CE quantity1 at408.20. No runner state/order mutation or process restart was performed. Deploy only after an explicit decision to stop/square off or wait until flat, then controlled restart and a separately authorized Start.

Crosses require both previous and current completed RSI/selected-MA values. Continued relationships and equality produce no event. Activation, restart, stream reconnect and failure recovery establish a new eligibility boundary, preventing old crosses from replaying. Each completed bar is consumed once; exits do not re-enter on their candle.

Optional step trailing defaults OFF. Percentage defaults10%; points require a positive user-entered distance. Filled long-option entry E fixes distance D=E×percentage/100 or selected premium points. Fresh executable bid high-water at E+D arms a tick-rounded stop at E; E+2D advances it to E+D, and so on, including gaps. No initial stop before the first step. Stops never decrease. Receive/exchange quote ages must each be <=15seconds; reversed/duplicate timestamps do not ratchet or trigger. Entry-price stop excludes fees and does not guarantee execution price or net breakeven. Frozen per-entry settings apply only after confirmed owned fills, never to the existing position. Durable exit intent, confirmed quantities and reconciliation prevent duplicate exits. Opposite RSI crossover remains available when trailing is off or unarmed.

Position history defaults to one row per verified ownership lifecycle, with both entry/exit IDs, weighted fill prices, matched-quantity pre-fee P&L/percentage, original strategy, mode, reasons, types, product, quantities and verified lots. New fills persist explicit lifecycle keys; all available raw orders remain in a drilldown. Legacy links are recovered only from retained ownership events or audited saved-position evidence, never contract adjacency. Exact JSON/CSV historical valuation evidence is in `output/position-history-valuation-evidence.json`; saved ownership proof is in `output/position-history-ownership-evidence.json`. The CRUDEOILM8800PE trade pairs at404.00/377.55, pre-fee loss264.50; SENSEX71600PE pairs at243.40/134.15, pre-fee loss2185.00, with external exit fill time unavailable. Earlier SENSEX72400PE records lack retained ownership proof and remain explicitly unpaired. Records already absent from the prior100-order ledger cannot be recovered by this view; the new runner no longer truncates history.

Completion audit at21:05 IST:75 strategy/runner tests +46 web/table tests +20 JavaScript tests =141 passing. Rendered history and disabled trailing/pending-deployment banner captured; browser warnings/errors absent. `output/rsi-completion-audit-20261001.json` records the read-only runtime boundary and evidence.
