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

## GitHub publication completed — 2026-10-13

Ubuntu GitHub SSH authentication and repository write access now succeed. The
reviewed commits through `3a50c6472ef0c33727c611a69ae2267b216d3d13` were pushed to
`origin/main`; `git ls-remote` confirmed the identical commit on GitHub. The origin
URL now uses SSH. This supersedes the publication blockers recorded above.
No application service, runner, or broker order was changed for this publication.

## Follow-up: All Dhan markets commodity discovery — 2026-10-13

The earlier MCX validation covered explicit MCX selection and saved charts, but
missed All Dhan markets with a spaced query. Reproduced an empty selector for
CRUDEOIL in ALL; the ALL provider excluded MCX, and MCX search did not normalize
spaces. ALL now includes native MCX hosts, and crude oil matches CRUDEOIL.
Empty MCX discovery now indexes option series once instead of rescanning the
entire master per future. Real-master reads took 0.316 seconds for empty ALL and
0.291 seconds for crude oil, returning six crude-oil hosts for the latter.

After deployment and browser refresh on account b0041912d9d6f68d352814cbd24bf6da,
Renko Supertrend / All Dhan markets / crude oil visibly returned October,
November and December CRUDEOIL and CRUDEOILM contracts. The October contract was
selectable. The badge showed Dhan Connected. Dhan status no longer restarts on
unrelated form changes, suppresses concurrent checks and times out to an explicit
unknown status instead of hanging or falsely declaring disconnected.

Validation: 46 Python checks and 13 browser-code checks passed. Portal and Dhan
worker loaded the fix after confirming no positions, pending orders or active
saved runners. FYERS PID 887285 and Delta PID 1101372 stayed unchanged. No real
order was submitted and no runner was activated. Hidden-panel polling remains
an observed source of extra browser traffic; this follow-up does not claim a
complete feed-performance audit.
