# Explicit multi-broker trailing protection

Shared durable scheduling, consent, exact owner/account/native instrument binding, one monitor per account/instrument, persistent intent before broker RPC, no retry on unknown outcome, Stop retaining native protection, and interrupt-without-rearming remain in force.

Broker routes:
- Dhan: existing delivery/MTF SINGLE Forever protection.
- FYERS: verified CNC cash holdings, exact native CM master, streamed fresh price, single-leg GTT create/modify; exact GTT id, client identity, side, product, quantity, trigger, limit and pending state must reconcile. Existing manual GTT/OCO and strategy ownership block this route. Current FYERS MTF/mixed funding rows are withheld unless a separate verified funding mapping is available.
- Motilal Oswal: verified unencumbered cash DP holdings, native master/profile/product/quantity and fresh native depth, SELLFROMDP STOPLOSS GTC. No DAY or AMO fallback. Modify uses exact uniqueorderid, current lastmodifiedtime and zero filled quantity; acknowledgement must reconcile exact active GTC terms in the owned order book. Broker rejection or expiry pauses for review, never recreates automatically.
- Delta India: verified vanilla linear futures, signed whole native contracts, exact product id and live bid/ask, GTC reduce-only stop-limit. Long stops rise; short stops fall. Edits preserve immutable direction/reduce-only terms, must retain the same id and reconcile pending/unfilled state. Options, inverse/quanto and expiry within 24 hours are excluded.

India cash uses verified trading-day sessions 09:15–15:30 IST, and sleeps without broker work when closed. Delta crypto uses 24/7 scheduling, independent of Indian holidays. Default 60 minutes; 30/60 editable while active. Internal and broker tick precision are preserved; display uses at most two decimals and the actual settlement/quote currency.

All existing sections retain assigned permissions and visibility. Account selection does not change another section's execution account. New support is not authorization to enable a monitor, replace another lifecycle's exits, or submit any live order.

Official contracts consulted: https://fyers.in/api-docs/v3/api/trading/order-placement/gtt-orders/ ; https://invest.motilaloswal.com/moAPI/APIDocumentation/Introduction ; https://docs.delta.exchange/#edit-order .
Broker acceptance and fills are not proven by fake-client tests or read-only hosted verification.

Hosted verification: FYERS and Delta each completed a native read-only portfolio review, returning zero delivery holdings and zero Delta positions respectively. Native monitor status endpoints returned zero monitors for all three added brokers. Motilal portfolio reading is blocked by authentication_required=true; reconnect is required for a fresh portfolio/protection preview. Saved monitor status does not require broker authentication. No live stop was submitted or modified.
