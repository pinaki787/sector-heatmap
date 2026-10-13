# Dhan native routing validation

The Dhan path resolves instruments in Dhan's security master and uses the selected
account's historical candles, option chain, quotes, funds, positions and orders.
FYERS keeps its separate provider and execution adapter. There is no cross-broker
market-data fallback.

## Verified on 2026-10-13

- Full Python regression: 701 tests, one skipped, no failures.
- Browser-code regression: 264 tests, no failures.
- Native Dhan single and batch Analysis Handoff previews reached review in the browser.
- Dhan account selection clears the preceding broker's figures and loads Dhan funds
  and positions. Native Sector Rotation loads its sector list.
- Fake-broker tests cover protected order acknowledgement/reconciliation, unknown
  outcomes, known preflight/API rejection, partial fills and Paper entry/exit.
- Fresh account snapshots import the required execution dependencies.
- Reviewed Dhan modules match the deployed private worker snapshot.
- Existing FYERS and Delta workers were not restarted during final deployment.

No real order was submitted and no runner was rearmed by this validation.
A preview and a fake confirmed fill do not establish a real broker fill.

## Explicit limitations

Only supported instrument/product combinations are selectable. Dhan strategy
adapters currently support bought options; unsupported cash/commodity strategy
routes remain explicit rather than silently substituting another broker.
Account-wide historical after-fee P&L is not fabricated where execution evidence
is unavailable. Broker outages and rate limits remain reported as errors.

A final read-only check found a retained Live runner position and unresolved exit
in local state while Dhan reported no open positions or pending orders. That
historical record remains blocked for reconciliation; it is not proof of current
broker exposure or executable P&L. No replacement order or state deletion is
authorized by the absence of a broker position alone. This recovery discrepancy
must be resolved from broker execution evidence before reactivation.

## Final recovery and account-selection validation — 2026-10-13

- Renko initializes from the selected owned account record, including older URLs without a broker hint. Positions selection preserves the independent Renko account, broker and instance. Navigation registration waits for the asynchronous Renko mount.
- External-close reconciliation requires a stopped runner, exclusive state lock, unchanged recovery context, flat broker position, no pending broker order, exact owned entry fills and an unambiguous terminal external exit. Uncertain durable submission intents remain blocked. It archives evidence and stays stopped; it never sends an order.
- Browser validation reconciled the existing Dhan external closure and displayed STOPPED, no retained position/pending order, and 487.50 gross realized P&L. A zero-filled rejected row with no price no longer crashes position history.
- Final Python suite: 715 tests, one skipped, no failures. Node suite: 265 passed. The separate optional jsdom harness could not run because jsdom is not installed in the remote environment.
- FYERS and Delta worker processes were preserved. No real order was submitted or strategy rearmed during validation.
- GitHub publishing remains blocked by unavailable Git write credentials and connector write permission; local remote-repository commits are not a successful push.
