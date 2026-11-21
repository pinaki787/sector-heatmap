# Holding Review charts and reviewed actions

Each analysed row exposes View analysis chart and the applicable reviewed action. Chart data is persisted with the portfolio output from the exact validated completed candles. The chart shows daily candles, EMA20/50, prior-week EMA20, previous 20-session range, five-session low, candidate stop and average cost, plus RSI14/ATR14. A prior-completed-week view shows weekly OHLC and weekly EMA20. The existing Holdings review section visibility and server permissions remain in force.

Dhan verified delivery/MTF equity supports TRAIL as a fixed Forever SINGLE protective SELL stop; EXIT and BOOK_PROFIT as regular-session LIMIT sells. It is not a continuously trailing runner. HOLD and REVIEW_NEEDED do not define orders. Other broker execution adapters remain explicitly unavailable.

Preview is read-only and bound to a completed, owner/account-scoped server job and row. Recommendations expire after ten minutes; previews after two minutes. Current native master, holding quantity/cost/product/availability, overlapping positions, current orders/Super/Forever protection and strategy state are rechecked. Existing/uncertain protection blocks duplicates, rather than modifying or loosening another stop. Mixed MTF/demat requires broker review; CNC needs verified DDPI. Cash exits require regular session.

Submission needs enabled account execution, exact typed confirmation and explicit live consent. It reacquires the account submission lock, revalidates state and whitelist, journals the attempt before transmission and consumes the preview. Uncertain responses remain UNKNOWN and block another attempt. No order is submitted by rendering a chart, analysis, preview, page reload or a saved job.

API references:
- https://dhanhq.co/docs/v2/forever/
- https://dhanhq.co/docs/v2/orders/

Validation: 35 focused tests pass, including same-rule indicator parity, stale/cross-account/quantity/protection refusal, exact confirmation, live gate, state drift, once-only submission and uncertain-outcome journaling. Broker submission tests use a fake client. No live test order is authorized or required.

Hosted verification: completed 1/1 Dhan review, 247 daily candles rendered, weekly selection rendered, and read-only PASHUPATI MTF stop preview succeeded. Live confirmation remained disabled. Zero holding action submission journals and no canonical runner state changes were recorded.
