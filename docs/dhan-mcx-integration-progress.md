# Dhan MCX integration — source validated, deployment pending

## Scope
Native MCX Renko discovery, exact futures-host history, bought-option execution,
contract valuation, sessions, expiry protection and costs. Preserve FYERS.
No real orders or runner activation are authorized by these checks.

## Implemented in remote source
- Exact Dhan MCX futures identities and same-expiry/strike Call-Put discovery.
- Verified contract multipliers, including mini contracts and the BULLDEX November lot revision.
- Native MCX history, market filter, option resolution and full-premium risk/funds checks.
- MCX fees, CTT, session DST, 2026 holidays and conservative pre-expiry protection.
- Fresh account snapshot dependency inventory includes the MCX module.

Specifications and source links: dhan-mcx-specifications.md.

## Validation on 2026-10-13
- 145 focused Dhan tests passed.
- Full Python regression: 739 tests, one skipped, no failures.
- All 266 Node tests passed.
- Read-only current Dhan master search resolved exact CRUDEOIL futures.
- October CRUDEOIL five-minute history returned 276 candles.
- Native option MCX_COMM:580476 returned bid 129.8 / ask 129.9 with API lot 1
  and point multiplier 100. This is observation-time evidence, not a current quote.
- November candidate was rejected by the existing 3% spread guard.
- Dhan broker exposure check found zero nonzero positions and zero pending orders.
- Saved Dhan Renko instance was stopped, without position or pending intent.

## Remaining before completion
1. Complete MCX Paper lifecycle/expiry evidence and review other strategy session boundaries.
2. Deploy source into the account worker and verify the served UI/API.
3. Resolve deployment ownership: current 8080/8100 processes are outside systemd;
   do not reuse the old orphan-process deployment helper.
4. Recheck exposure immediately before any restart; preserve FYERS/Delta processes.
5. Source-only commit and push. Prior GitHub authentication failure remains unresolved.

No claim of real fill validation is made. No order was submitted during these checks.
