# Manual trend filter

Optional and OFF by default, under Signal settings. Its own collapsed heading keeps the enable switch accessible. Bullish and bearish markers may be equal; otherwise bullish must be higher. Positive finite marker prices and a whole confirmation count from 1 through 100 are required when enabled. Default confirmation count is 2.

Only consecutive completed host-timeframe closes count: strictly above the bullish marker or strictly below the bearish marker. Equality, a close outside that direction, or a missing host interval resets the count. Forming candles and repeated polling do not count. The filter gates existing strategy entry events; it does not create a new reversal or entry event. Historical confirmation is permitted, while existing post-activation signal freshness rules remain enforced. Exits retain their existing rules.

The submission/authorization checks also require the fresh underlying price to retain the permitted zone, including manual entry overrides. Values persist when OFF, and edits apply on the next Start.

Deployed to main and selected FYERS account source/runtime only. Other account source trees differed and were deliberately not overwritten; Dhan/Delta runtimes were not restarted. No runner was activated and no orders were placed during verification. Tests cover equal/separate markers, strict boundaries, consecutive/reset/gap/duplicate/forming behavior, settings persistence, execution-zone revalidation, and mounted chart Start settings transfer using mocked transport.
