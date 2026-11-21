# Target option premium on entry and re-entry

A specified target selects the nearest fresh executable ask across up to 61 nearby strikes in the nearest eligible expiry, keeping the required Call/Put direction. It is approximate, not an exact price or order-price cap. Blank retains ATM selection. Every entry and re-entry resolves again against current quotes; no old contract is implicitly reused and unavailable quotes do not silently fall back to ATM.

FYERS NSE/BSE index options retain their existing selection. Dhan and Motilal native option routes now use the same premium objective. Dhan fetches candidate quotes in one account-throttled batch, not a sequential REST call per strike. The usual executable quote, funds, spread, lot, ownership and entry preflight still apply. No new sleeps or retries are added to selection. Existing settings, running captures and positions are not migrated or modified; the next explicit Start captures the visible target.

The selected target, ask, bid, difference, candidate coverage and quote timestamp are retained with entry metadata and trade journal evidence. A target of 40 can select 39.80 or 40.20 according to the closest usable ask. Cash, perpetual and unsupported routes cannot accept an option-premium target.

Activation: guarded shared dashboard reload completed. All three public Dhan account routes report premium capability. Read-only affected-account evidence: target 40, selected ask 37.50, bid 37.35, 61 quoted candidates, lookup 2.78 seconds. Desktop and 390px control verified. Motilal source and mocked resolver verified; hosted live verification blocked by expired login. 117 Python and 15 JavaScript checks pass. No runner started and no broker order submitted.

Motilal reconnection follow-up: renewed login passes. Public default plus all seven saved instrument runners report premium support. Hosted premium control is visible. A non-starting Paper preview retained target 40; subsequent runner status remains stopped, with no position or pending order. No live order/fill test was performed.
