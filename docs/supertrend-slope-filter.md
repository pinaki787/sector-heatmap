# Supertrend slope entry filter

Reset Defaults disables EMA entries, exits and studies, and all other optional indicator families. Renko Supertrend and its direction/brick exits remain on. Reset Defaults enables this entry-only filter with a one-observation lookback and zero minimum ATR slope. Saved configurations which omit the switch remain off. Family OFF masks the filter without discarding the stored choice.

Slope is (current Supertrend minus Supertrend N completed observations earlier) / (current basis ATR × N). BUY needs slope strictly greater than the configured minimum; SELL needs slope strictly less than its negative. Flat readings fail even at zero minimum. Every observation in the lookback must retain the current Supertrend direction, preventing a line jump on a flip from qualifying. Missing ATR/history waits.

RENKO uses completed bricks, including multiple bricks within one host observation. CANDLESTICK uses completed host candles. The provisional drawing is excluded. Slope-enabled Supertrend-only entries wait for the first valid slope confirmation after the flip; disabling slope preserves reversal-only behavior. Existing exit rules are unchanged.

Lookback: 1–100 observations. Minimum: 0–100 ATR per observation. Values retain full internal precision; display uses two decimal places. This filter is not a profitability claim.
