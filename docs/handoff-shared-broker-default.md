# Shared broker default and merged Handoff — 30 October 2026

The explicitly selected broker account is the common default for all analysis
and execution forms and the connection pane. Switching a form's account clears
stale broker-specific URL context and reloads the interface with that account.
Unsupported sections show an unavailable choice, without choosing another broker.
Existing background schedules, broker orders, positions and grants are not moved,
enabled, disabled or rewritten by changing the displayed account.

Analysis Handoff merges owned selected Screener membership and Sector Analysis.
Native Dhan support uses its own account's master and candle provider. The selected
universe remains account-owned; another broker's saved universe is never imported.
Candidates rank by normalized high-conviction score, then source rank. The existing
allocator selects at most five unique underlyings inside the remaining allotted
pool and available selected-account funds. Tests exercise a Rs50000 pool.

Ranked read-only analysis can be retained when selected-account positions or orders
are unavailable. Such output explicitly blocks execution and carries no order
authority. Fresh positions, orders, funds, duplicate/exposure checks, complete
Screener membership, current prices and protected exits remain required before
a Live order. Unknown identity is never treated as an empty account.

Static shared-account defaults are hosted and verified. Backend activation of
analysis-independent execution checks and native Screener integration remains
pending the applicable safe service reload. No schedule policy, account grant,
order or runner was changed during this work.
