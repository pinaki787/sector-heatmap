# Holdings review

Open **Holdings review**, select a broker, and choose **Analyse all holdings**. The review reads the account once and processes every returned row in batches of up to five. Counts show the complete review coverage; stopping or a request failure preserves an explicitly partial result. Action cards and the Show filter narrow the queue. Export review saves the account scope, evidence, assumptions and recommendations as JSON.

The feature is advisory and read-only. It never submits, cancels or modifies orders, adopts positions, changes strategy ownership, changes saved stops or starts runners. Administrators can assign **Holdings review** through User Master. Account workspaces enforce their registered broker on the server; the owner dashboard uses its existing configured connection for the selected broker. There is no cross-account fallback.

## Supported account scope

- **FYERS:** delivery holdings returned by the holdings API, using remainingQuantity rather than beginning-of-day quantity when available. T1 and demat records remain separately visible. Zero remaining quantity is excluded. Supported exchange equity series use current quotes and up to 365 days of daily history; other holdings remain visible as Review needed. Intraday/F&O positions are not delivery holdings and remain in the existing broker positions section.
- **Delta India:** all nonzero margined derivative positions, read directly without using the account method that also reconciles local journals. Verified vanilla, non-quanto futures with matching contract/underlying units and quote/settlement currency can receive direction-aware suggestions. Options and unverified contracts remain Review needed; wallet cash is not classified as an equity holding. Price/units and currency are kept explicit. Margined position snapshots can lag recent fills.
- **Dhan:** not registered by the current local workspace account store; this feature does not pretend to have an authenticated Dhan account adapter.

## Rules and limitations

The default horizon is swing. Signals require at least 110 valid completed daily candles and 20 prior completed weeks. The week containing the most recent completed day is conservatively excluded from weekly context. FYERS daily freshness follows the existing NSE market calendar; during an open session quotes must be no older than 120 seconds. Outside the session their date must match the last completed session. Delta futures require the latest completed UTC daily candle and executable bid/ask evidence no older than 15 seconds. Quotes are evidence snapshots, not a streaming portfolio display.

Rules are deterministic technical hypotheses, without a calibrated probability or claimed backtest performance:

| Suggestion | Evidence |
| --- | --- |
| Hold | Daily close, EMA20, EMA50 and prior weekly EMA20 align with the position |
| Trail | Aligned trend, profitable movement ≥ 1 ATR and a candidate protective level beyond acquisition cost |
| Exit | Daily close and EMA20 are on the wrong side of EMA50, with an opposing prior weekly trend |
| Book profit | Gross profit, RSI ≥ 70 for longs / ≤ 30 for shorts, ≥ 2 ATR extension from EMA20, near/beyond the prior 20-session range boundary |
| Review needed | Missing/stale/malformed evidence, mixed trends, unsupported products, unverified units, futures expiry within 24h, or a quote more than 3 ATR from the completed daily close |

Long trailing candidate = max(EMA20, completed close − 2 ATR, five-session low); short candidate = min(EMA20, completed close + 2 ATR, five-session high). It must remain on the protective side of the current reference price and beyond acquisition cost. These are unrounded review levels, not exchange-valid order prices. Tighten existing stops only, and check the owning strategy and hedge relationships before acting.

Delivery gross P&L uses remaining shares × (quote − average). Verified linear futures gross P&L uses signed contracts × contract value × (exit bid/ask − entry). Futures return percentage is directional price movement, not return on margin. Brokerage, taxes, funding, dividends and corporate-action adjustment checks are outside this model. No fundamental/news model, user risk budget, existing target or stop, or portfolio suitability assessment is fabricated.

Concentration is a share of the **priced delivery subtotal**, with coverage shown. It is provisional until all holdings are processed and excludes unpriced instruments and derivatives. It is not a cross-currency or margin-exposure total. Analysis reads are paced, daily history is cached by credential identity, symbol and completed session, and a new inventory is limited to once per 60 seconds. Snapshots expire after ten minutes; analysis should be rerun before acting on old results. Exceptions retain the holding as Review needed instead of silently omitting it.

## Implementation and validation

- `sector_heatmap/holdings_analysis.py`: pure review rules, broker adapters, bounded account-scoped batching and caches.
- `/api/holdings-analysis`: authenticated dashboard route with server-side broker isolation and the holdings feature permission.
- `holdings-review.js`: section, action filters, review coverage, partial cancellation and JSON export.
- `tests/test_holdings_analysis.py`: trends, stale quotes/history, forming candles, contract units/direction, split holdings, pagination, account isolation, failure retention and permissions.

The local UI was verified with a synthetic seven-row portfolio. This is layout and interaction evidence, not live holdings validation. Deploy through the project's normal maintenance process; adding the section locally does not restart active services or strategy runners.
