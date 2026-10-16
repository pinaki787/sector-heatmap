# Fixed Manual Renko reference sizing

Manual mode derives a reference brick for the selected instrument, saves the
result with the draft, and keeps that number when the chart timeframe changes.
It does not update an armed runner's Start settings.

| Market | Reference | ATR length | Divisor |
| --- | --- | --- | --- |
| NSE/BSE indices, equity and option underlyings | Six hours starting 09:15 IST | 5 | 12 |
| Delta crypto | Consecutive 23-hour reference bars anchored at Unix epoch UTC | 7 | 12 |
| MCX | Selected contract's verified regular session from the broker master | 7 | Session duration in minutes / 30 |

Examples: 250 / 12 = 20.8333333333; 1500 / 12 = 125.
For a 09:00–23:30 MCX session the divisor is 29. A 23:55 close uses
895 / 30, preserving the exact duration rather than rounding it.

Reference bars aggregate completed five-minute broker OHLC. Full source-bar
coverage is required; missing candles are not synthesized. Wilder ATR uses the
first reference bar's range for the seed and then successive true ranges.
This uses broker data and an explicit reference anchor; it does not promise
numerical equivalence with a differently anchored TradingView chart.

The calculation record is saved in server preferences and scoped browser
storage. Switching instruments uses that instrument's saved fixed reference
or calculates a new one. Recalculate reference brick explicitly replaces it.
An entered Manual override is also saved. Failed reference retrieval blocks
Start until a valid calculation or explicit Manual override is available.
Auto mode's existing behavior is unchanged.

The parent strategy form refreshes its matching embedded chart after saving
a changed Manual reference. Timeframe-only edits do not recalculate the brick.
No calculation starts a runner, arms Live mode, or submits an order.
