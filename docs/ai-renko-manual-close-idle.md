# Manual broker closure to idle

A user-started Live instrument worker now checks its managed positions through its existing selected-account broker verifier at most once per ten seconds while exposure exists. Fully flat confirmation requires a successful authoritative quantity and order-book check. Pending/uncertain application intents, partial broker positions, unresolved orders, stale or wrong-account responses, manual preparations and queued operator commands do not get cleared. Failed checks back off up to sixty seconds. Paper workers never consult a live broker through this path.

When every managed leg for this instrument is confirmed flat, the worker journals the closure, preserves an audit proof, clears its stale positions, deferred entries and capital reservation, writes a terminal Stop receipt and returns from its own loop. Its existing finally block closes the stream and releases its execution lock. Other instruments and accounts are untouched. It does not place an exit or enter again.

Where the existing broker-specific fill collector provides exact external closing fills, the journal uses that evidence. Otherwise the journal records broker-flat confirmation with unavailable exit price, fees and profit rather than inventing a fill. Existing historical trades and settings are retained. The next explicit user Start creates a new run/session; the new manager retires the prior STOPPED control state and allows normal fresh signal evaluation. Unknown retained intents still block startup.

Regression checks cover all configured broker verifiers, partial/pending/unavailable and wrong-account data, duplicate reconciliation, multiple managed legs, queued Stop precedence, no Paper broker reads, and an isolated actual ledger-lock release followed by a new worker executor accepting a simulated broker fill. No real order or Live worker is started to test this behavior.

# Dhan embedded chart binding

Dhan strategy aliases such as NSE:NIFTY are not native chart IDs. They now resolve against the selected Dhan account's instrument catalog, with exact exchange, symbol and segment matching. Requests are deduplicated per account/instrument and successful mappings are reused for the visit. Missing or ambiguous mappings show an unavailable message rather than restoring an unrelated chart.

Embedded chart initialization rejects a missing/invalid broker symbol or a different account. Native chart IDs remain display/data identities; the strategy's execution symbol is retained separately. Run-owned chart source requests that need alias mapping are validated against the same Dhan instrument master on the server; numeric OHLC and indicator values are unchanged. Markers and position overlays use the display mapping without moving execution ownership.
