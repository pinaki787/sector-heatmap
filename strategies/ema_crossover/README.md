# RSI SMA / EMA strategy v1.0.0

Wilder RSI and a selectable SMA (default) or EMA of RSI, default lengths 14/14. Only fresh completed crossovers authorize entries: previous RSI <= previous MA, current RSI > MA buys nearest-expiry ATM Call; the inverse buys Put. A later opposite crossover exits. Equality, continued relationships, forming bars and old startup/reconnect crosses do not authorize trades. One owned position; no re-entry on its exit candle.

Trading is explicitly opt-in and never starts after a process restart. Existing FYERS routes, account gates, instrument validation, lot/tick/multiplier valuation, budget checks and durable order/fill reconciliation remain. Do not reload an active runner: stop and confirm flat/no pending orders first.

Optional long-option premium step trailing defaults OFF. Percentage defaults to 10%; points require a positive distance. Confirmed fill premium E fixes D=E*percentage/100 or selected points. Fresh executable bid E+D arms a tick-rounded stop at E; E+2D raises it to E+D, and so on. No initial stop before first step. Never lowers or compounds. Stale/reversed/duplicate bid updates cannot ratchet or trigger. The entry-price stop excludes fees and execution is not guaranteed. Trailing settings freeze per confirmed entry; opposite crossover exits remain available.

Charts include synchronized candle/RSI/volume panes, an optional seven-timeframe completed-RSI table, configurable optional SMA Bollinger Bands, optional Red Bar supply/demand and session/Fibonacci/period references, collision-spaced captions, persistent drawings and fullscreen. Original Pine source remains unchanged. Missing source coverage/history warm-up displays Unavailable. All chart additions are independent of order rules.

Position history uses verified ownership lifecycle links and confirmed matched fills. It preserves entry and exit IDs, historical strategy labels, mode, reasons, requested/filled quantities, verified bought lots, entry premium cost before fees, weighted fill prices, pre-fee realized P&L/percentage and timestamps. Missing legacy links remain unpaired. External fill time is unavailable unless verified. Full raw order ledger remains accessible; new history is not truncated. Recent crossover events appear separately as readable signal-only rows.

Private local valuation/ownership audit records are optional read-only evidence and are not part of this release. No credentials, runtime state, actual trading records or screenshots are committed.

Validation:

```sh
PYTHONPATH=.:strategies python -m unittest discover -s strategies/ema_crossover -p 'test_*.py'
python -m unittest tests.test_web tests.test_rsi_table
node --test tests/ema-crossover.test.cjs tests/ema-cloud-chart.test.cjs tests/redbar-overlays.test.cjs tests/position-history.test.cjs
```

No backtest profitability or live execution validation is claimed. The historical EMA research helpers are separate from the RSI runner.

When optional trailing is enabled, whole-lot partial targets share the same fixed step in both points and percentage modes. Nominal split is 30%/30%/40%; for >=3 original filled lots, first and second each use max(1,floor(0.30*lots)), remainder trails. Three lots split 1/1/1, two split 1/0/1, one splits 0/0/1. First step sells the first allocation and arms residual stop at entry; second step sells second allocation and raises stop by one step. Later milestones ratchet only the remaining quantity. A hit exits all confirmed residual quantity. Preview displays actual whole-lot percentages; partial fills, outstanding intents and stage fills are reconciled without duplicate sales. Non-whole confirmed lot quantities have no partial-target allocation. Trailing OFF disables all partial targets and stop effects.
