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
adapters currently support bought options; MCX Renko bought-option routes are now supported; unsupported cash strategy
routes remain explicit rather than silently substituting another broker.
Account-wide historical after-fee P&L is not fabricated where execution evidence
is unavailable. Broker outages and rate limits remain reported as errors.

## Final recovery and account-selection validation — 2026-10-13

- Renko initializes from the selected owned account record, including older URLs without a broker hint. Positions selection preserves the independent Renko account, broker and instance. Navigation registration waits for the asynchronous Renko mount.
- External-close reconciliation requires a stopped runner, exclusive state lock, unchanged recovery context, flat broker position, no pending broker order, exact owned entry fills and an unambiguous terminal external exit. Uncertain durable submission intents remain blocked. It archives evidence and stays stopped; it never sends an order.
- Browser validation reconciled the existing Dhan external closure and displayed STOPPED, no retained position/pending order, and 487.50 gross realized P&L. A zero-filled rejected row with no price no longer crashes position history.
- Final Python suite: 715 tests, one skipped, no failures. Node suite: 266 passed, including the DOM harness using the existing isolated jsdom installation. The harness now awaits account-bound mounting.
- FYERS and Delta worker processes were preserved. No real order was submitted or strategy rearmed during validation.
- GitHub publishing remains blocked by unavailable Git write credentials and connector write permission; local remote-repository commits are not a successful push.

- Final deployment parity: all 17 reviewed Dhan backend, shared UI and history files match the private worker snapshot.


## Completion audit — deployed MCX extension, 2026-10-13

| Requirement | Verified evidence |
| --- | --- |
| Broker-native contracts, candles, quotes and execution | Dhan master/history/quote checks plus native payload tests; no FYERS data fallback |
| Account isolation and existing forms | Ownership/login/handoff/form/engine/indicator tests; 113 focused checks passed in final run |
| MCX exact expiry, sizing, fees and protection | MCX discovery/valuation/calendar tests; Paper entry-exit cost-lock test; fake Live payload test |
| Served selection and chart | CRUDEOIL October selected, saved as a stopped Paper instance; reload retains MCX and exact contract; candle/indicator chart shows Dhan tick age zero |
| Deployment consistency | All 79 reviewed non-test runtime/document files match the private worker snapshot; fresh snapshot import test includes MCX, login, permissions, stream and connection UI |
| Regression | Full Python suite 742 tests, one skipped; Node suite 266 passed. Final case-normalization change additionally covered by focused tests |
| FYERS preserved | No FYERS-specific source change in MCX commits; original FYERS PID 887285 and Delta PID 1101372 retained. Shared Renko UI branches apply only to Dhan; snapshot inventory adds the Dhan module |
| No real trades or rearming | Read-only final broker check: zero positions and pending orders. Existing saved Dhan runner stopped/flat; new MCX instrument saved but never activated |
| Source commits | b398703 and 5de85af, followed by this audit/test commit; runtime files, secrets and unrelated research excluded |
| GitHub publication | Not completed: HTTPS credentials unavailable; SSH dry-run with GitHub-published verified host keys returns Permission denied (publickey). Connector write access was also unavailable |

The deployed application work and authorized non-trading validation are complete for
the supported bought-option routes, including MCX Renko. This does not assert a real
fill or guarantee broker availability. GitHub publication is the remaining external
access blocker; no live test is required or authorized to clear it.
