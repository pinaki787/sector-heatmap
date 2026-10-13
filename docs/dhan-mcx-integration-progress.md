# Dhan MCX integration — deployed MCX Renko validation

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
- 76 focused MCX/execution/adapter checks passed after browser corrections.
- Full Python regression: 742 tests, one skipped, no failures.
- All 266 Node tests passed.
- Read-only current Dhan master search resolved exact CRUDEOIL futures.
- October CRUDEOIL five-minute history returned 276 candles.
- Native option MCX_COMM:580476 returned bid 129.8 / ask 129.9 with API lot 1
  and point multiplier 100. This is observation-time evidence, not a current quote.
- November candidate was rejected by the existing 3% spread guard.
- Dhan broker exposure check found zero nonzero positions and zero pending orders.
- Saved Dhan Renko instance was stopped, without position or pending intent.

## Deployment evidence

- Portal and private Dhan worker now run under systemd, preserving their prior environment.
- FYERS PID 887285 and Delta PID 1101372 were retained without restart.
- Browser verified MCX search, saved exact contract restoration, candles, indicators and fresh Dhan ticks.
- Stopped Paper instance 3654182b413310c1b6819193 was created for CRUDEOIL October chart validation; never started.
- Browser-discovered month casing and saved-contract search restoration defects were corrected.
- MCX Paper entry/exit test verifies contract multiplier, Dhan costs and quick-loss lock.
- Missing expiry evidence now blocks entries and requests a protective exit.

## Remaining before completion
1. Completion audit finished: 79 reviewed files match the deployed worker; 113 final focused checks pass. See dhan-order-routing-validation.md.
2. GitHub push remains blocked: HTTPS authentication unavailable; SSH host identity verified using GitHub metadata, but no accepted public key is available.
3. No real-order execution or real fills have been tested; simulated Live routing and broker read-only checks are separate evidence.

No claim of real fill validation is made. No order was submitted during these checks.
