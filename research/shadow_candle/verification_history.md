# Final-session shadow candle

New standalone indicator: shadow_candle_final_session.pine. Existing root shadow-candle.pine and Sector Pulse V1 are preserved.

Usage: Create a NEW TradingView Pine indicator, paste source, Save and Add to chart. Use standard intraday candles at or below the reference timeframe; Nifty 50 five-minute is supported. Load multiple sessions.

Automatic mapping: NSE/BSE 6h (360 minutes), ALL MCX including GOLD/GOLDM 14h (840), foreign GOLD/XAU 22h (1320), crypto 23h (1380). MCX takes priority over gold; NSE/BSE listings remain in the equity group. Market classification and manual timeframe overrides are available. Unknown automatic symbols fail explicitly. GOLD/XAU substring recognition is a heuristic; override unusual tickers.

Shadow means full high-low of the FINAL native TradingView higher-timeframe candle of the previous exchange trading day, including a shortened closing candle. It is not a full-day range or a rolling window ending at close. A 6h15m session on native 6h bars can end with a 15-minute candle: that final candle is the source. Crypto has a feed-defined day reset, not a trading close.

Five lines: high, low, and low + (high-low) * percentage / 100. Three independent defaults: 46%, 50%, 56%. Display uses at most two decimals without rounding calculations. Labels show source opening/closing times in exchange timezone. Up to 40 sets retained; latest extends with chart.

Confirmation: native reference bars and time_tradingday define exchange-day alignment. Only previous-bar prices are requested using [1] with lookahead_on. The current requested day key is known calendar information, not a price. At the first reference bar of the NEXT day, the final previous bar is published. No forming-candle levels or retrospective lines at source opening. Holidays/no-tick gaps postpone publication until data resumes. Initial loaded history may lack a source.

Custom daily reset: specify an IANA timezone, hour and minute. This groups native reference bars by opening times; it does not re-anchor them or create a custom exchange session. Candidates closing after the new reset are rejected with a visible warning; prior levels remain. Reset must align with native reference boundaries. Repeats each calendar day; no custom holiday calendar. Compare source timestamps with native reference charts for each feed, including overnight, DST, and short sessions.

Feed corrections, input changes and chart session settings can legitimately recalculate results. Synthetic/Renko charts are rejected.

Validation: remote static invariants passed for all four mappings, gold priority, offset price tuple, custom-boundary rejection and publication-time line starts. This is NOT Pine compilation or TradingView chart verification. Initial checks preceded TradingView verification; see the subsequent dated verification section. Existing unrelated scripts were not replaced.

References:
https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/
https://www.tradingview.com/pine-script-docs/concepts/sessions/
https://www.tradingview.com/pine-script-docs/concepts/timeframes/

No services, runners, broker settings or orders changed.

## TradingView verification, 7 November 2026

TradingView Desktop compiled and saved the new standalone indicator. Fixed Pine v6 reserved identifier text by renaming to labelText. Changed the timeframe guard to allow an equal-reference chart after comparison on 6h triggered the original runtime guard. The Nifty 5m chart was restored and showed no runtime error. Native 6h source inspected at 5 Nov 2026 09:15: high 24579.90, low 24296.30, matching the indicator source label (close timestamp 15:15). Displayed defaults: 46%=24426.76, 50%=24438.10, 56%=24455.12. Publication began at 6 Nov opening. This verifies the final AVAILABLE native reference candle in this loaded feed; the visible native dataset showed one candle per session and no later 15:15 closing stub. No claim is made that absent feed bars can be reconstructed.

SUPERSEDED initial gold-mapping check (before user correction): MCX:GOLDM1! on 5m displayed Gold / 1320 min, source 5 Nov 09:00–23:55, high 146141, low 143282; default levels 144597.14 / 144711.50 / 144883.04. The chart instance initially inherited No scale, visibly displacing drawings. Fixed through More > Pin to scale > Pin to right scale and visually verified matching price-axis positions. If importing into another layout, ensure the indicator is pinned to the SAME price scale as the symbol. Do not select a new independent scale. Gold history took approximately one minute to finish its initial reference-data calculation.

Other MCX chart verification: MCX:CRUDEOIL1! on 5m displayed Other MCX / 840 min. Final source was the shortened 5 Nov 23:00–23:55 candle, high 8585, low 8528. Levels 8554.22 / 8556.50 / 8559.92 appeared at the 6 Nov opening. This confirms closing-stub selection on a feed where the shortened native bar exists.

Bitcoin chart verification: CRYPTO:BTCUSD on live 5m displayed Crypto / 1380 min. Source 6 Nov 23:00–7 Nov 00:00 (exchange timezone UTC), high 75874.97, low 75730.15. Levels 75796.77 / 75802.56 / 75811.25 were displayed from the next UTC day boundary (05:30 on IST chart). The ongoing current-day 23h candle was not used.

Ethereum chart verification: CRYPTO:ETHUSD on live 5m displayed Crypto / 1380 min. Source 6 Nov 23:00–7 Nov 00:00 UTC, high 2240.01, low 2232.36. Levels 2235.88 / 2236.19 / 2236.64. Both crypto symbols were observed while current-day prices were updating. A future session rollover and every exchange/calendar condition were not observed live.

## Final user correction, 7 November 2026

ALL MCX instruments, including GOLD and GOLDM, use 14h. Only foreign gold instruments (including Delta gold) use 22h. Classification checks MCX first, NSE/BSE second, foreign GOLD/XAU third, then crypto. Earlier MCX gold 22h verification is historical and explicitly superseded.

BSE chart verification: BSE:SENSEX on 5m displayed NSE/BSE / 360 min, high 79470.03, low 78520.56 from 5 Nov 09:15–15:15. Default levels 78957.32 / 78995.30 / 79052.26; three historical session sets were visible.

FINAL corrected MCX gold verification: MCX:GOLDM1! on 5m showed MCX / 840 min after final source saved at 16:05:28 IST. Final source 5 Nov 23:00–23:55, high 144394, low 143900; default levels 144127.24 / 144147.00 / 144176.64, correctly price-aligned and published at 6 Nov opening. Screenshot shadow-mcx-gold-14h-verified.png supersedes the earlier 22h check.

FINAL foreign gold verification: OANDA:XAUUSD on 5m displayed Foreign gold / 1320 min, with five price-aligned boundary/Fibonacci lines and no runtime error. Source dates/levels were visible, although part of its label overlapped the chart header in that viewport. Delta-specific gold ticker aliases were not chart-tested; use the explicit Foreign gold override for non-GOLD/non-XAU aliases.

Final screen 16:07 IST: NSE:NIFTY 5m restored; 360-min classification, three historical sets, five price-aligned lines per session and no visible runtime error. Layout saved with All changes saved visible. Screenshot shadow-nifty-final-verified.png. Latest Pine saved in TradingView at 16:05:28 IST after final mapping correction. Source SHA256: 83ebcac45d00810a386081a3e2217e69701f510ad83d3feda8d5aca6000b414c

Red-bar labels have NOT been added: source information labels currently use gray. The intended meaning of the requested red-bar labels is awaiting clarification; no all-bearish-candle labeling was inferred.


## 7 November — previous periods, source construction, gap and corrected RSI
Native NIFTY ETH daily/week/month high/low comparisons recorded in previous_periods_source_boxes_validation_20261107.json and native screenshots. Source boxes visually rendered on5m and15m, independently time anchored to shortened final source. Actual gap-up6Nov PDC24536.60/open24538.20/mid24537.40; gap-down27Oct PDC22753.20/open22708.80/46%=22732.78 verified in tooltips.
Rejected rolling RSI envelope replaced by fixed affine mapping. Bottom settings directly inspected: RSI14 close/SMA14/Chart timeframe. Same-bar adjacent samples on1m,5m,15m agree with transformed line; full values/evidence in fixed_rsi_mapping_validation_20261107.json. Positive fixed scale algebra guarantees flat signs too, though no exactly flat native pair observed. Current explicit cosmetic anchor22700, scale10 retained for replay. Script saved and applied; obsolete version19 removed, current instance retained30sessions. Red bottom RSI style preserved. No broker/order/service actions.


## 7 November17:25 IST — inverse RSI crossover semantics
Previous fixed affine mapping was rejected because candle-side placement did not encode RSI-vs-SMA. Replaced by inverse Wilder RSI threshold on chart timeframe, with prior M-1 RSI average as equality target; cosmetic mapping controls removed. Confirmed actual adjacent down-cross1m, up-cross5m, and both directions15m using candle close vs threshold and bottom RSI vs SMA simultaneously. Numerical97,400same-bar and inverse equality checks passed, including17,019side changes. Exact native samples and limitations in inverse_rsi_validation_20261107.json. TradingView version25 saved17:22. Lower red RSI settings unchanged;15m replay restored. Earlier fixed-mapping screenshots are superseded by shadow-inverse-rsi-*.png.


## 7 November23:37 IST — blended source-group colors
Version26 saved23:32:45 in TradingView. Source tuple now carries confirmed native open[1]/close[1]; source box tint uses close>open bull, close<open bear, equal existingneutral color. Transparent source boxes are frozen once created, independent of forward SC breakout regime. NIFTY4Nov15:00 native O23921.70/C23960.60 bullish;5Nov15:00 O24554.70/C24536.60 bearish; lower15m source boxes visually checked in those directions. DIVISLAB additional native directions recorded in blended_source_colors_validation_20261107.json. Neutral branch verified statically, no native equal sample observed. RSI inverse threshold, levels, settings and history retained. User changed symbol from DIVISLAB toNIFTY during verification; latestNIFTY15m retained. No runner/service/broker/order actions.
