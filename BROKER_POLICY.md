# FYERS-only broker policy

Sector Heatmap has one broker boundary: FYERS.

- FYERS is the only permitted source for broker market data, option chains,
  account state, order previews, and any user-enabled execution.
- There is no broker chooser, alternative broker adapter, or fallback data feed.
- Every final ticket and every future unattended-policy evaluation must refresh
  FYERS identity, contracts, quotes, funds/margin coverage, positions, and order
  state before it can proceed.
- Tests and development must use fakes with live submission gates disabled.
- Adding another broker requires an explicit change to this policy and its
  invariant test; it must never happen incidentally through a generic adapter.
