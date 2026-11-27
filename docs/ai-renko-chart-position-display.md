# AI Renko chart position display

Position P&L is a compact row outside the price plot and before the indicator legend. Its Show/Hide preference is scoped to the selected account and instrument. The entry and current-price lines remain; monetary text no longer extends into the candle plot. Closed positions remove the row. The existing exact-position, entry-order, quantity and quote-freshness checks still determine whether gross money P&L or directional points can be shown. This UI change neither requests additional broker data nor changes trading.

The P&L row consumes the existing current-line result, keeps at most two display decimals, and updates existing elements only when their visible values change. Prices and order/calculation precision are unchanged. The separate PRST Pine table retains its controls and placement.

## Confirmed-brick updates

The chart now holds a snapshot of the authoritative run signal bars, rather than sharing their append-mutated cache array. When captured signal data adds bricks while completed candle rows remain unchanged, the existing price series appends those confirmed bricks. The provisional projection continues using the current confirmed tail and never becomes a strategy signal by itself.

The captured PAXGUSD regression covers confirmed indices 5592 and 5593, descending from 3660.3260869565215 to 3658.695652173913 and 3657.065217391304. The renderer replay appends each exactly once without replacing the chart or requiring a new minute candle. A chart gesture can defer rendering; the next normal synchronization catches up without changing the worker.

27 November verification used the hosted active PAXGUSD chart at desktop and 390px width. The P&L row was outside the plot, clear of the indicator legend, and its visibility persisted through refresh. The hosted confirmed tail matched the worker at index 5597. Only static UI assets were deployed; no service/worker restart or order action was performed. The normal two-brick reversal convention remains unchanged.
