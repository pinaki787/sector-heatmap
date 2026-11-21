# Renko confirmed candles and live prices

Implementation scope: FYERS Renko workspaces. Broker/account callback identity
scopes shared caches and the Renko quote transport. Dhan, Delta and Motilal retain
their existing broker-specific transports; this change does not substitute FYERS
data for those accounts.

## Data and execution

- One account-local Renko quote hub fans out provider updates to chart and runner
  consumers. Runner Stop detaches its consumer; it does not close another
  consumer's transport. The account transport can remain connected while idle.
- One background candle request per instrument/timeframe is in flight. Completed
  1-, 5- and 15-minute strategy candles remain broker OHLC, not tick-made candles.
  A cached forming candle is never promoted merely because the clock advanced.
- Candle refresh is scheduled at the next boundary plus one second. During an
  active recent sequence, late publication retries at 1/2/4/8/16/30 seconds;
  retrieval failures use bounded backoff. Actual provider publication latency
  remains external. Readers retain the last real snapshot while refresh runs.
- The runner advances its confirmed engine only when the shared history revision
  changes. Order reconciliation, price protection and stream checks retain their
  existing independent lifecycle behavior.
- Full chronological price-history digests detect revisions older than the
  retained 1000 individual hashes. Same-anchor recovery retains owned orders,
  consumed signals and entry freshness; missing history stays blocked.
- Runner-bound chart requests identify run, symbol and timeframe, then read an
  atomic confirmed snapshot directly. They do not wait for historical replay.
  The chart shows the retained confirmed window (currently up to 500 bars).
  Select Draft preview for independent, full-range historical research.
- The yellow dashed provisional Supertrend is a clone-based live preview.
  It does not overwrite the solid confirmed series or enable intrabar execution.
  A preview is withheld when the immediately preceding confirmed bar is missing.
- Prices, broker candles, confirmed indicators and order connectivity have
  separate health text. Fresh ticks with missing OHLC show candle recovery.
  Outside verified regular-session bounds, the UI identifies the closed session
  rather than presenting that condition as a feed outage. Special sessions with
  fresh ticks continue to be treated as live.

## Validation and activation

Focused Python and browser tests cover concurrent slow readers, account
isolation, per-timeframe boundaries, late candles, preserved forming flags,
history failures, shared-consumer Stop, immutable previews, exact confirmed
snapshot ownership, and HTTP rendering when history/forming retrieval fails.

The full Renko suite has four independently reproduced pre-existing failures
(manual reference-session fixture, cross-market auto-box expectation,
Delta perpetual/sideways expectation, unknown-net sideways fallback).
Do not describe that suite as fully passing.

Changes require an explicitly authorized FYERS worker reload. Installing source
does not activate the running Python process and does not arm any runner.
Market-hour recovery and latency need prospective observation after activation;
an after-hours check cannot establish those properties.
