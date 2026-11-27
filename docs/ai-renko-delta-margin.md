# AI Renko Delta perpetual margin

Live AI direct-perpetual entries use authenticated, selected-account configured product leverage. The software never changes broker leverage. Product initial margin, maximum-leverage notional threshold and scaling factor bound leverage for the actual size. Missing, invalid or wrong-product evidence blocks entry.

Estimated provision is the higher of configured-leverage initial margin and product size-tier initial margin, plus two taker fees including the existing 18% GST provision, plus the existing 1% notional reserve. This is a local conservative preflight, not an exchange margin acceptance guarantee. Entry depth and signed position/open-order checks remain required. Reduce-only exits and option premium rules are unchanged; legacy non-AI callers retain their existing collateral policy.

Startup obtains an authenticated flat/no-open-order check and a fresh ticker-based margin estimate. It does not require an immediate entry. Each actual entry checks fresh executable depth and current configured leverage again under the existing account admission lock. A stale book defers entry and never authorizes a trade.

A typed local funds or margin-read rejection occurs before native submission and therefore records a zero-submission outcome and clears only its own pending marker. An unknown submission/acknowledgement continues retaining its intent for broker reconciliation. Seen signal identities remain recorded, preventing replay of the rejected signal.

27 November repair evidence: selected PAXGUSD product 123006, configured 100x, base initial margin 1%, 100 contracts of 0.001 PAXG each. The prior 100-contract attempt failed the old full-notional check before creating a native intent. Fresh selected-account broker evidence confirmed flat/no open orders/no matching recent orders or fills before bookkeeping recovery. This document does not record a new order, activation or successful live-fill test.
