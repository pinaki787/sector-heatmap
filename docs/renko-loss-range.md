# Renko protective loss range

Available across broker workspaces. Default ON for the next Start; zero-brick buffer.
The existing host-candle quick-loss filter is separate and unchanged.

After an actual filled position closes at an after-cost loss and at least one
opposite completed brick was observed, freeze the completed-brick body high/low
from the entry signal through the exit. Count bricks, not elapsed host candles.
Only confirmed filled exposure is observed; an unfilled pending entry contributes
no exposure bricks. The original entry brick is captured at submission.

Block normal entries, trend re-entries and manual overrides while locked. Release
only on a fresh completed brick closing strictly above high + buffer * frozen box
for a buy, or below low - buffer * frozen box for a sell. That same brick can
enter if every existing indicator, ownership, freshness, quota and broker check
passes. Forming bricks, price ticks alone, old events and the exit observation
cannot release the range. Stops and protective exits bypass this entry gate.

Unknown net costs/funding produce an explicit conservative lock, not a claim of
a confirmed loss. Profitable/breakeven closes and losses without an observed
opposite brick do not create this lock. Saved locks survive worker restart;
a fresh explicit Start begins a new run without inheriting the prior run's lock.
Settings and range state are broker/account/symbol/runner scoped.

The chart shows the range high/low and the toolbar shows the active lock.
Toggle/buffer edits apply on next Start. This reduces repeated within-range
entries; it does not prevent the first loss or establish profitability.
