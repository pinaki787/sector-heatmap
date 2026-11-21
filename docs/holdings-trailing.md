# Holding Review automatic trailing

Default off. Adding/deploying this feature does not authorize a monitor or broker order. Each holding requires a fresh completed Dhan review, read-only enablement preview, enabled account execution capability, explicit automatic-order consent and the exact typed enablement phrase.

The user selects 30 minutes or one hour. The service creates or adopts one verified application-owned Forever SINGLE protective SELL stop for the exact Dhan delivery/MTF equity holding. It periodically recalculates the same completed-daily review rules (daily EMA20/50, prior weekly EMA20, ATR14, RSI14, range/low evidence). Only a higher TRAIL candidate can raise the stop; it is never lowered. Intraday checks can leave the level unchanged because the underlying rule uses completed daily candles. No discretionary EXIT/BOOK_PROFIT order is automated. The broker retains stop-trigger protection between checks.

Each successful upward change uses the same native instrument, product and full reviewed quantity, a fixed LIMIT stop with a 0.5% trigger-to-limit buffer rounded to the native tick, and the documented SINGLE TARGET_LEG modification route. Existing/manual/ambiguous protection is never silently adopted. A retained app-owned stop can be adopted only after an explicit fresh preview and full broker reconciliation.

State, current broker stop, 30-second heartbeat, last review, next check, data, completed-candle evidence, gross P&L and request/confirmation events persist under the exact account source .private/holding-trails. The full latest review, including chart data, is retained in last-review.json; the durable Runner job preserves job-specific output and audit identity. One OS lock per account/native instrument prevents duplicate writers across dashboard processes. Account submission locking serializes trading requests.

Stop monitoring is cooperative: finish a bounded in-flight broker request, then stop further checks/modifications. It keeps the last broker protective stop and does not cancel protection or sell the holding. UI shows status, current broker trigger, protected quantity, last review, next check and heartbeat. The existing Holdings review feature permission applies to all monitor APIs. Cross-user/account requests are rejected.

Holding quantity/cost/funding changes, stale or missing evidence, foreign ownership, overlapping active strategies, externally edited or triggered/cancelled stops, account execution halt, expired authentication and uncertain broker outcomes pause the monitor for review. Broker requests are journalled before transmission; uncertain requests are never automatically replayed. Existing uncertain intents block another enablement.

Process/server interruption never automatically rearms a monitor. A surviving broker stop stays in place; explicit reviewed enablement is required again. Current monitor state participates in the dashboard restart guard. Startup/status reads do not submit orders.

Reference: https://dhanhq.co/docs/v2/forever/

Validation: 55 focused tests pass. Hosted desktop/narrow configuration and hourly read-only preview were verified. Consent remained unchecked and enablement disabled. Zero monitor states were created and all 30 pre-existing canonical runner state hashes remained unchanged. Broker modification/enablement was verified only with a fake client, not a live order.

Default checking interval is 60 minutes. Before enablement the user can select 30 or 60 minutes. For an active monitor, Update interval saves either choice without restarting the job or touching broker protection; the next check is rescheduled from the change time. Interval revisions are audited and merged so a concurrent heartbeat cannot overwrite the user choice.

Market sessions: equity monitoring sleeps outside 09:15–15:30 IST on exchange trading days. Closed-session waits are event-driven, with no periodic broker reads or analysis; Stop, shutdown and interval updates wake the worker. Scheduled sleep is distinguished from a stalled job. The calendar fails closed when its verified year expires. MCX calendar tests cover product-specific morning/evening sessions and partial holidays; live commodity trailing remains unsupported until a verified commodity protection adapter is implemented. Current live actions remain Dhan cash-equity delivery/MTF only. Default interval is 60 minutes; 30/60 can be changed while active.

25 October multi-broker extension: see multi-broker-trailing.md for the current broker/product matrix, native order validity and remaining runtime verification limits. Earlier Dhan-only statements describe the original release, not current route availability.
