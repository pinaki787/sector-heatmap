# Sector Pulse broker and workspace boundaries

The implemented trading adapters are FYERS, Dhan, Delta India and Motilal Oswal.
Indian-market sector analysis supports the selected account’s FYERS, read-only
Dhan Data API or Motilal native captured-candle provider.
Dhan selection uses Dhan candles, native security master, option-chain evidence,
quotes, account funds/positions, and order APIs throughout Sector Rotation,
Analysis Handoff, and Live Feed & Positions. FYERS selection retains its private
FYERS provider and execution path. Delta India retains its separate adapter.
There is no automatic data or execution substitution between brokers.

Dhan has account-owned manual LIMIT single/batch tickets and bought-option
adapters for Renko Supertrend, RSI based EMA, EMA Band, KAMA and the independent
Renko Engine. Unsupported instrument/product combinations fail explicitly.
KAMA retains its own completed-candle signal function; Renko Engine retains its
independent recurrence and lifecycle. Dhan EMA Band supports premium stop/target,
the existing staged profit-protection rule, and completed-candle resistance/volume
exit. KAMA supports directional underlying invalidation and a full-premium idea
cap. Selection, preview, configuration and source deployment never arm runners.

The opt-in user setup portal supports multiple users and multiple broker accounts
per user. Every account has an isolated dashboard process, source snapshot,
credential files/token cache, settings, Paper balances, journals and ownership
locks. Account dashboards verify the signed-in owner for every request and reject
mutation requests for a broker different from their registered workspace.
Administrator status permits creating users; it does not grant trading access to
another user's workspace. Setup starts no strategy and sends no order.

Each final ticket/runner retains its adapter's fresh identity, exact contract,
quotes, capital/margin, ownership, position and order reconciliation checks.
Tests use fake credentials with live gates disabled. Adding another broker
requires an explicit adapter, policy and invariant-test update.

The existing single-user dashboard is unchanged unless launched as an isolated
workspace. Authentication covers provisioned workspace dashboards, not an
independently running legacy localhost service. This local feature is not a
public Internet hosting configuration. See docs/multi-user-broker-setup.md.

Dhan credentials are saved per user/account as client ID and access token, never
read from shared environment variables. The configured client ID must match the
registered broker account reference and the authenticated Dhan profile. The
server's outgoing IP must match Dhan's registered primary/secondary IP. Account
configuration does not change IP registration, enable a strategy or submit orders.

Manual Dhan tickets require current security-master contract/lot/tick metadata,
fresh two-sided REST snapshot market depth, token/data-plan validation, funds, broker margin,
positions/pending-order checks and idea/daily risk budgets. They support NSE/BSE
equity BUY and intraday SELL entries, plus bought Call/Put entries. Futures,
short options, delivery sells and MARKET orders are unsupported by this manual
adapter. Analysis Handoff long options request Dhan Super Orders with linked
premium stop/target legs derived from underlying invalidation/target levels;
the mapping is a model estimate, not a guaranteed underlying-price exit.
Normal LIMIT tickets have planning levels only. Acknowledgement never proves
a fill or active linked protection. Batch previews aggregate risk and margin; submission stops on
any changed ticket, rejection or uncertain outcome without automatic retry.

Dhan previews are bound to one owned account, expire after two minutes and require
the displayed preview binding and an explicit Submit click. The application sends
the bound confirmation; users do not type a confirmation phrase. Live capability is off by
default. Cross-process account locks and private submission journals prevent
concurrent submission/replay. An uncertain result blocks further orders until
read-only correlation-ID reconciliation verifies the provider's result. Order
acknowledgement and confirmed fills remain distinct facts.


Dhan quote freshness follows the documented real-time REST snapshot contract.
The last executed trade's timestamp is retained separately and is not used as
the age of current bid/ask depth. Network response duration is bounded; quota
waiting is not network staleness. Slow read responses can refresh once.
Order POST requests are never automatically retried. Account-wide interprocess
throttling coordinates quote, option-chain, and history requests.

Handoff cache and analysis sizing are bound to the selected owned account.
Switching brokers clears incompatible plans, previews and account figures.
Before sending a reviewed LIMIT ticket, the adapter rechecks executable depth;
a market beyond the reviewed limit requires a new preview.


Analysis and runner jobs are durable, owned by the signed-in user and exact
broker account, and filtered by the originating section permission. Submitted
Screener pages execute on the server, with partial and final outputs retained
across navigation. Cancellation never replays work: analysis stops at bounded
checkpoints, and runner jobs invoke the existing Stop behavior only for their
activated run. Restart marks interrupted jobs without automatically rearming
trading. Restoring research does not restore order authority or bypass fresh
preview and submission checks.

Index/commodity AI Handoff uses the selected broker's current master, native
quotes, completed candles and ATM resolver. Existing positions and pending
orders exclude the underlying before evidence collection and again before
publication. Premium plans are refreshed after AI review. Incomplete evidence
produces WAIT or an explicit exclusion. Only public market evidence is sent to
OpenAI; account identifiers, positions, funds and credentials are not included
in model input. AI has no order tools. Quota failures retain broker evidence
and do not trigger an automatic retry or fabricated recommendation.

Motilal workflows use its explicit native adapter and account ownership checks.
Its captured history must warm up; missing periods remain unavailable. An
explicitly selected FYERS history source in an existing Motilal runner is a
separate, consented history setting, never an automatic execution fallback.
Broker acceptance and fill verification remain separate from implementation
and read-only validation.
