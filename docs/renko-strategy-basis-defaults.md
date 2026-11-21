# Renko strategy basis and universal defaults

Implemented on 28 October 2026 at the user's request. No runner is automatically started.

## New setups and Reset to strategy defaults

- Strategy basis: **Renko bricks**. Host candle interval remains the user's selected execution timeframe; no fixed one- or five-minute requirement.
- Entries: confirmed brick colour agrees with Supertrend and the selected EMA condition (EMA 10 by default).
- Exits: selected Supertrend direction flip, opposing completed Renko brick, or selected EMA breach. EMA period is editable, including 10 and 30. Any enabled exit may close a position.
- Single timeframe by default. Higher-timeframe checks and their chart labels are optional and off.
- Anti-chop, calibrated setup, manual trend, RSI/ADX/structure/zone/retest/widening/proximity gates, trailing and intrabar timing are off.
- Reset saves a Paper draft with size 1 and clears optional selections. It retains the current broker, symbol and selected timeframe. Existing named configurations, drawings, journals and trading evidence are not deleted. Reset refuses a running runner, position or pending order.
- Existing saved profiles without a strategy basis retain **Legacy synthetic** semantics. They are never silently converted. Explicit Reset or a basis selection adopts the new behavior.

## Execution and chart semantics

**Renko:** sequential completed source closes generate separate uniform bricks with the standard two-box reversal. Supertrend and entry/exit EMAs advance for every emitted brick, including multiple bricks from one source candle. Manual mode uses the saved size. Auto freezes the first calibrated full-precision box at the history anchor, preventing historical bricks from resizing. This is disclosed rather than claiming a tick-exact TradingView reconstruction.

All bricks from one source candle become knowable at that source candle's close. Fractional timestamps only position separate bricks on the chart. They do not imply intrabar execution. Protective exits inspect all newly available bricks; exits consume that source observation, preventing same-observation re-entry. Broker quotes, ownership, sessions, limits and order checks still govern execution.

**Candlestick:** Supertrend uses actual completed OHLC and ATR; EMA uses completed candle closes. No Renko colour or opposing-brick exit is imposed in this basis.

**Chart view** is display-only and separate from **Strategy basis**. Renko display uses the actual engine brick sequence in Renko execution mode. Supertrend and EMA plots use the brick-level values rather than repeating one host-candle value across all bricks.

The forming preview has a target outline and a separate fill layer. Fill height and percentage follow live price, including two-box reversal progress and multi-brick candidates. It is explicitly provisional, can shrink/disappear, and never enters engine state or creates an entry/exit. Stale market evidence clears the preview.

BUY, SELL, BUY EXIT and SELL EXIT are retained as chart text. Historical labels say SIGNAL; recorded fills include Paper/Live and FILLED. A historical label is not proof of a fill.

Optional anti-chop, manual-trend and calibrated filters retain their completed-host-candle semantics when explicitly enabled. They do not learn from the visual preview. New Renko Supertrend/EMA recurrences remain brick based.

## Runtime and bounded history

The shared Renko package and controls are installed in all six hosted account source snapshots. Dhan and Motilal use the shared native chart parser; Delta uses the same engine and retains its own execution route. FYERS remains separately routed. No credential, broker assignment or live-order permission is changed.

Native chart calculations serialize identical work without blocking quote/preview context access, reuse the confirmed recurrence, and return at most 5,000 completed source candles. Full selected history remains initialization evidence. The hosted history note discloses this display bound; use a narrower custom date range for older periods.

Recoverable source backups and activation/test evidence are under `.private/change-backups/renko-basis-20261028/`. Activation used the existing stopped-runtime guard and managed per-broker bounce. Runners stayed stopped/flat with no pending orders.

Focused tests cover brick size/reversal, every-brick EMA 10/30, no-brick/forming safety, intermediate-brick exits, no same-host re-entry, recurrence continuation, candlestick OHLC, prior-only host filters, complete native query parsing, bounded chart caching, reset persistence/runner exclusion, progressing preview fill, and visible signal/fill distinctions.

Two broader pre-existing assertions were encountered: cross-symbol complete-output equality differs only in broker-specific Auto-box diagnostics; the pre-change engine reproduces it. Another older Delta perpetual test expects a sideways-policy rejection that the current implementation no longer raises. Neither was changed as part of this work.
