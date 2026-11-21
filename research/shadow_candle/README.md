# Final native closing-candle Fibonacci indicator

Source: shadow_candle_final_session.pine (Pine v6). Existing root shadow-candle.pine and Sector Pulse V1 are preserved.

## Current behavior

- Primary plot ON by default: high/low and configurable 46%, 50%, 56% levels of the FINAL SHORTENED native reference candle at the selected trading-session close.
- Optional complete-reference-candle plot OFF by default: last full-duration native reference candle from the same day. Dashed, translucent lines and purple compact source markers distinguish it. Independent primary and complete toggles were tested.
- Primary range has twelve transparent color.from_gradient slices between high and low, with the strongest tint near the middle Fibonacci level. Toggle and transparency control are provided. Full range stays unfilled.
- Existing Completed sessions to retain setting is preserved (current TradingView instance: 30). Maximum 40 sessions per enabled range. No all-history refactor was retained after user clarification.
- Display rounds to at most two decimals; calculations retain precision.

## Final automatic mapping

ALL MCX, including GOLD/GOLDM: 14h (840 minutes). NSE/BSE/Nifty: 6h (360). Foreign GOLD/XAU, including recognizable Delta gold tickers: 22h (1320). Crypto: 23h (1380). MCX and NSE/BSE classification precede foreign gold. Explicit classification/manual timeframe overrides cover aliases.

## Session selection and the corrected Nifty source

Source trading session defaults to Chart and uses ticker.new with syminfo.session; explicit Regular/Extended overrides are available. It follows native TradingView bars; no custom session reconstruction or shifted candle scheme is used. Keep TradingView extended hours enabled to match the user's inspected Nifty six-hour chart.

The original ticker.standard request discarded the chart session selection. In the observed regular-session dataset, this produced the earlier 09:15–15:15 bar. After extended hours was enabled, native six-hour bars aligned at 09:00 and 15:00, and the final short bar had a scheduled end of 16:00. Earlier claims that the closing data was missing were superseded by this observed session-setting explanation. Do not equate nominal native bar end with continuous trading until that timestamp.

Direct native chart crosshair evidence: 5 Nov 2026 15:00 final short bar O24554.70 H24558.25 L24529.95 C24536.60. Indicator source: 5 Nov 15:00–16:00. Levels: 46%=24542.97, 50%=24544.10, 56%=24545.80. This replaces the earlier large-candle H24579.90/L24296.30 range, now available only through the optional complete-candle flag (extended-session 09:00–15:00).

6 Nov native final short bar crosshair: 15:00 O24873.85 H25030.35 L24872.00 C25030.35. It is not used while forming. The confirmed previous-bar request publishes at the first available reference/chart bar of the NEXT session; the 5 Nov range is therefore shown during 6 Nov. No attempt is made to backdate a signal or to simulate a future session rollover.

The candidate must be shorter than the reference duration and end exactly at the native daily session close (or explicit custom reset). Otherwise the primary range is unavailable; an earlier full candle is never silently substituted. Custom reset groups native bars and does not re-anchor them. Normal chart-session mode is recommended for the requested behavior.

## TradingView validation

Latest source was compiled/saved through TradingView Desktop, then plotted on standard Nifty six-hour and five-minute charts with ETH enabled. Current history30 was preserved. Primary-only, both-enabled, and complete-only modes were checked visually. Native source OHLC and displayed Fibonacci prices match the values above. Current chart controls preserve final ON, complete OFF, gradients ON.

Earlier mapping screenshots for MCX gold14h, foreign XAU22h, crude14h, BSE6h and BTC/ETH23h are retained. They predate the session-aware short-only correction; classification logic remains unchanged, but every corrected source/session combination has not been revalidated across all symbols, holidays, DST or special sessions. Future live rollover remains unobserved. Feed corrections and session/input changes can legitimately recalculate history.

Import into a new Pine indicator, Save and Add to chart. Use standard time-based intraday charts no higher than reference timeframe. Pin the indicator to the SAME symbol price scale, not an independent scale. Initial higher-timeframe loading can take time.

No services, runners, broker settings or orders were changed. Red-bar strategy labels were not inferred; source labels explicitly identify FINAL shortened versus OPTIONAL complete candles.

References:
https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/
https://www.tradingview.com/pine-script-docs/concepts/sessions/

## Label polish correction

Bulky per-session gray information cards were removed after visual review. Historical source markers now say only Final or Full; hover reveals source timestamps, high/low and exact levels. A compact lower-right panel shows current source time and three color-coded Fibonacci values. The optional full range adds its own separate panel rows only while enabled. Input values are hidden from the chart legend (still editable in Settings), with short chart title Closing Candle Fib. Split-view overlap at the OHLC header was corrected by moving the panel below price activity.

Final label layout reserves space above TradingView event icons. Native 6h and 5m source comparison and independent toggles were observed before the text-only polish; final price/session calculations are unchanged by the label changes. The source panel is optional and exposes detailed evidence on hover.

Final visual evidence: shadow-compact-labels-split-verified.png, shadow-compact-labels-full-verified.png, shadow-source-tooltip-verified.png. The hover tooltip was inspected directly and showed FINAL shortened closing candle, 05 Nov 15:00–16:00, H24558.25 L24529.95, 46%=24542.97 / 50%=24544.10 / 56%=24545.80. Final source saved at 16:26:43 IST with no visible current compile/runtime error. Layout saved at 16:27:22 IST, full-width Nifty5m ETH restored. Source SHA256 f012cd0a0e93cddcbf2d53024d5bb70d632515df2666c980bd1839f980ac51c8.

## Latest naming and label-only correction

The exact current user-facing name is Shadow Candle (without Fib, Final, Full or support/resistance suffix). One compact label identifies only the current shadow range. Historical source circles are optional and OFF by default; detailed source data is available on hover. The compact current-price panel retains three Fibonacci percentages/prices and source time. This supersedes earlier Final/Full badge descriptions and the interim Shadow Candle Fib name. Calculations, mapping, ETH source, gradient and history control are unchanged.

## Confirmed-close dynamic colors (current behavior)

A chart candle CLOSE above Shadow Candle HIGH starts a green zone segment at that candle close. A close below LOW starts red. A close inside or exactly on the boundaries starts neutral. Forming chart ticks cannot change the state: the update uses barstate.isconfirmed in chart context, outside request.security. Current range tag and current-price accents follow this confirmed state. Earlier colored zone segments are frozen at their original transition times, so the latest green/red state is not painted backward over an entire session. Optional complete-reference lines remain visually separate.

Observed 6 Nov Nifty5m ETH: 09:15 bar C24512.80 below low24529.95 -> red from09:20; 09:30 bar C24546.20 within range -> neutral from09:35; 09:40 bar C24573.35 above high24558.25 -> green from09:45. The chart visibly retained the earlier red segment while later segments were green. Evidence: shadow-dynamic-colors-transitions.png and dynamic-color-observations.json. Live forming-tick transitions were not observed.

Dynamic fill retains per-segment historical states. To stay within TradingView's 500-box limit, oldest detailed gradients are compacted to a flat tint of THEIR OWN recorded state before adding new segments. Extremely many alternating segments can ultimately evict the oldest fills at the object cap; boundary/Fibonacci history remains governed by the existing session setting. No past segment is recolored using a newer close.

Latest visible exact name and saved script: Sector Pulse — Shadow Candle / chart label Shadow Candle. One named current label; optional historical source circles OFF. Final settings visually checked: history30, primary ON, optional complete range OFF, label ON, compact levels ON, gradients ON. Full-width and editor-split screenshots: shadow-dynamic-colors-final.png and shadow-dynamic-colors-split.png. Source saved16:36:16 IST; layout saved16:39:17 IST.

Current SHA256 aa2736cc5540a8d271903825de486223287ed0be90f24f8f3d43aa4fb6e2c731

## Current SC tag placement

The visible range tag is now exactly SC. It is centered at the shadow LOW price and anchored strictly after the latest chart candle close, using three future chart-bar intervals by default (input range1–20). label_left draws the compact tag to the right of that future anchor. A dotted horizontal leader connects the current lower-boundary endpoint to the tag at exactly the same price. The tag moves with the latest bar, is never repeated over historical candles, and retains confirmed regime coloring and source tooltip. Source/session calculations and all other settings are unchanged.

Verified in full-width and Pine-editor split views: SC is beyond all existing candles, fully visible in blank future space, at the lower-boundary price with no vertical offset. User left additional right-side chart space while reviewing; this viewport space was preserved and saved. Pine cannot enforce a viewport margin in every other layout; leave enough right-side space to display the future tag. Evidence: shadow-sc-future-split.png and shadow-sc-future-full.png. Source save observed16:44:49 IST; layout All changes saved observed16:46:13 IST.

Current source SHA256 320cebd1fa152a39a864cf8d82f596ba4d851ad87d3b23d942013b93724d79c9

## Previous completed period levels

PDH/PDL use the previous completed exchange daily OHLC candle; PWH/PWL use the completed exchange week; PMH/PML use the completed exchange calendar month. The requests use the same Chart/Regular/Extended source ticker convention as Shadow Candle, with price fields high[1]/low[1] and lookahead_on. Current-period time fields are calendar metadata only. These are not rolling7/30-day windows and do not use incomplete current-period prices. Weekends/holidays naturally return the prior available trading candle. Each pair has a visibility toggle and period color; highs are dashed, lows dotted.

The six current previous-period lines are updated in place across their applicable current period; they are separate from the 30-session historical Shadow Candle ranges. Labels are exact PDH, PDL, PWH, PWL, PMH, PML, at true price, beyond the latest chart candle. Nearby labels are placed in horizontal future-time columns; no line or label price is moved. Show enough right-side chart space for these columns. Source dates and values are in label tooltips.

With both Shadow Candle and complete-reference plots disabled, the previous-period lines can also be viewed on standard higher-timeframe charts for native-candle comparison. The original intraday reference guard still applies whenever a Shadow Candle/reference plot is enabled.


### Source construction boxes (7 November 2026)
Enabled by default on chart timeframes below the configured reference. One subtle filled rectangle encloses only the confirmed shortened final native reference candle, with exact source-open/source-close timestamps and high/low. It is back-anchored over the constituent candles, separate from the projected SC zone, and is reconstructed on timeframe changes. It appears once the confirmed source is published next session; no developing source or preceding full candle is boxed. History follows Completed sessions to retain (current saved choice 30). Color and transparency are configurable. Gradient box budget reserves 40 objects for source boxes.

Native NIFTY extended-session comparisons: 5 November daily H/L 24,579.90 / 24,296.30; week starting 26 October H/L 23,118.10 / 22,387.35; October H/L 23,175.25 / 22,179.90. Period labels use future chart-bar columns to retain separation over session/weekend gaps; prices remain unchanged.

### Gap Fibonacci
Optional gap overlay (default on): PDC is previous completed exchange daily close, DO is current exchange daily open. Daily request uses the same Chart/Regular/Extended ticker convention. Endpoints are fixed for each session; equal endpoints or a difference below one minimum tick produce no gap. The existing configurable percentages and colors are reused. Orientation is explicit: 0% PDC, 100% DO, so a gap-down level descends as its ratio increases. This is independent of PDH/PDL and SC. Only the current gap is shown, with subtle fill and right-side price-anchored labels. Exchange daily OHLC may differ from the last/first extended intraday print; the gap deliberately uses native exchange daily candle endpoints.

### RSI SMA crossover price — supersedes both cosmetic mappings
The requested semantic is now candle CLOSE above/below the overlay iff RSI above/below its SMA on the SAME chart candle. The overlay inverts Wilder RSI14 with source close and SMA14 on the active chart timeframe. No cosmetic price anchor, gain, or rolling price envelope remains. This threshold is not expected to reproduce the oscillator average's shape.

For an M-point SMA including current RSI, equality requires current RSI to equal the average of the previous M-1 RSI values. Let A=(N-1)×previous Wilder gain RMA, B=(N-1)×previous loss RMA, q=target/(100-target). Required price change is q×B-A for an up move, otherwise B-A/q for a down move; add previous close. Only previous states are used, so the threshold is fixed before the current candle and has no future leakage. Close, not high/low or candle body, defines the side. A forming candle's RSI and close can cross provisionally together; confirmed closes are stable.

Warm-up, SMA length1 (RSI identically equals its own1-point SMA), target0/100, zero combined previous gain/loss, and nonpositive price solutions are withheld as unavailable, without clamping or inventing levels. Data Window exposes raw RSI, raw SMA and a same-bar side mismatch diagnostic (0=match). Source/session/gap/period behavior remains separate. Numerical evidence is in inverse_rsi_validation_20261107.json; earlier fixed-RSI screenshots are superseded.

### Blended source-group direction
Source construction boxes use the confirmed native final-small reference candle open and close: bullish close>open uses Bullish zone color, bearish close<open uses Bearish zone color, and equal uses the existing Source candle box color as neutral. The fill retains the existing90% transparency and border35% transparency. Native OHLC equals the blended constituent group (first open, maximum high, minimum low, last close), without majority voting. Each completed box is created once with its own source tint and is never recolored by later breakout regimes. The forward SC gradient/regime logic remains independent. Current source values are available in the SC hover tooltip.
