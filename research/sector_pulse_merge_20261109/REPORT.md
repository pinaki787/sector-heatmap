# Sector Pulse V1 / Shadow Candle merge — 9 November 2026

Status: Shadow Candle merge implemented, compiled/saved in TradingView version 18 at 13:22:11 IST, rendered on HCLTECH 5m and 15m. Exact Shakti Prime supply/demand parity is UNMET. Rejected automatic zone detector is excluded from the active version 18 source.

Canonical source: `/home/trading/sector-heatmap/sector-pulse-v1.pine`.
Release artifact: `sector_pulse_v1_shadow_release.pine` (57,094 UTF-8 bytes; FNV1a64 43901da9e1df420a). `shadow_release_validation.json` contains SHA-256. The remote artifact and text transferred into TradingView matched byte length/FNV64 before compilation.

## Source comparison before editing

The actual HCL TradingView editor was opened and its entire 366-line V1 version 16 source extracted through text selections. An interrupted segment was re-extracted. Every captured line matched the remote baseline by FNV1a32, and the captured UTF-8 length was 25,319 bytes. `v1_editor_before.pine` preserves this verified source. `source_comparison.json` records the check. Editor search text mentioning line 897 was stale UI state; it did not establish a newer current V1 source.

All 66 existing V1 input declarations/defaults remain verbatim. Reference selection/session, India/global/MCX distinctions, extra 30m zone, 200 SMA band, 5 SMA, targets/reveal/hit tracking, independent IST windows, cutoff and inferred dashboard remain. Core calculations and V1 ratios are unchanged. Existing ratio controls do not exist in this V1 source: its actual constants are 44/50/56. Those exact values are shared by the merged range and gap features; no separate Shadow 46% override is introduced.

## Feature comparison

| Shadow feature | V1 before | Version 18 |
|---|---|---|
| Last shortened session candle, published next session | Absent | Merged |
| Market auto/manual classification; 6h equities, 14h MCX, 22h gold, 23h crypto | Absent | Merged |
| Chart/regular/extended source trading session | Absent | Merged |
| Exchange or custom daily reset/timezone | Absent | Merged |
| Shadow high/low and internal Fib levels | Absent | Merged with unchanged V1 44/50/56 |
| Optional full reference candle range | Absent | Merged; off by default |
| Source candle boxes, native blended open/close tint | Absent | Merged |
| Independent completed-close breakout regime segments/gradient | Absent | Merged |
| Historical source markers, tooltips, SC tag/leader, offsets | Absent | Merged |
| Session history | Absent | 30 completed sessions; adjustable 1–30 |
| Compact current-level panel | Absent | Merged; avoids V1 bottom-right dashboard collision |
| Previous day/week/month highs/lows and source tooltips | Absent | Merged |
| Previous close/day open gap Fib, labels and fill | Absent | Merged with V1 ratios |
| Chart-timeframe inverse RSI14/SMA14 crossing price | Absent | Merged; lengths configurable; degenerate states unavailable |
| Raw RSI/SMA and cross-side diagnostic data window | Absent | Merged |

Compatibility: unsupported/nonstandard or larger chart timeframes disable the Shadow/reference plots rather than aborting V1. Prior-period levels remain independently usable. Shared drawing limits reserve room for the modules: newest 90 target line segments, 180 target band boxes and 60 window lines; oldest rendered history is discarded first. This is a material rendering-retention limit, not a change to stored target/reveal/hit calculations. Shadow old gradients compact to a flat fill in the same historical tint under object pressure. Prices display at most two decimals; calculation precision is unchanged.

## Verification

- TradingView compiled and saved version 17 (13:09:23 IST), initially including a generic pivot detector. User rejected its zone mismatch. It is superseded.
- TradingView compiled and saved version 18 (13:22:11 IST): working Shadow merge, rejected zone detector removed. Observed rendered HCLTECH 5m and 15m, then restored HCLTECH 5m and original Shakti reference visibility. Reference settings were inspected and cancelled without modification.
- `shadow_release_validation.json`: all 66 existing input declarations, V1 calculations/ratios, merged feature presence and exclusion of rejected detector pass.
- `chart_export_validation.json`: exported 604 five-minute candles and 763 fifteen-minute candles each have zero RSI cross-side mismatch. The 5m export is from version17 (same inverse-RSI formula); 15m export is from final version18.
- Numeric inverse-RSI contract check tested 10,000 random gain/loss/target states: 9,881 had positive-price solutions; max equality residual 1.42e-14. Degenerate/nonpositive solutions are not fabricated.
- No runner, service, order or broker setting was changed. Data-only FYERS attempts failed authentication; chart OHLC was obtained through TradingView CSV exports instead. No authentication refresh was attempted.

## Exact Shakti Prime zone/label match — unresolved

The latest user direction requires exact Shakti Prime placement, bounds, rectangle extent, label appearance and lifecycle. Generic pivot and base/impulse detectors do not satisfy this. They are retained only as separate research artifacts and are NOT in version18.

Current reference Source code menu is disabled (observed 13:19 IST). Actual visible settings include swing strength5, origin search12, ATR14, displacement0.8ATR, score65, sweep optional off/window20, nearby0.35ATR, 3 fresh blocks/side, freeze on first touch, close invalidation, history15 days, plus ENABLED confirmed2m/5m synchronization (score65, displacement0.8, source spacing3). Exact quality scoring, synchronized stream arbitration, origin/boundary selection and label construction are not exposed by those settings.

Remote source search found `research/shakti_prime_parity/` originals/candidates explicitly identified as independent reconstructions, with no accessible protected engine. `order_block_module.pine` is inferred and its prior integration was rejected and rolled back, as documented in `evidence.md`; it is not a recovered source or a validated exact implementation. No bypass of source protection was attempted. Exact completion requires accessible original source or documented zone, scoring, sync and label rules.

The original manual rectangles were estimates from another executor, not mathematically defined inputs. Exported Nov9 supply base10:05–10:15 is1413.90–1416.90 versus manual1413.50–1416.50. The claimed Nov4 demand1397–1401 has unsupported1397 lower edge: the exported Nov4 low is1399.50. These estimates are not hardcoded or used as parity evidence. Formation confirmation is distinct from a later retest; a current lack of upward departure does not invalidate an independently evidenced historical formation.


## Version 20 behavioral reconstruction — 9 November 2026

Supersedes the earlier source-access prerequisite: no protected source is requested or required. The synchronized zone engine was reconstructed independently from visible behavior and exported TradingView OHLC. Full Shadow Candle merge and original V1 inputs and fixed 44/50/56 ratios are retained. Version 20 compiled and was saved in TradingView Chrome at 13:53 IST. The native desktop chart instance was not confirmed updated.

HCLTECH calibration: visible supply 1440.70–1443.90 and demands 1381.00–1382.40, 1393.20–1396.60 matched full source-candle ranges. Bounds are inferred from chart geometry and exact OHLC candidates; protected plots do not expose numeric rectangle bounds. Consuming the first swing break, including weak breaks, removed two spurious zones from competing hypotheses. Turning synchronization off removed the broad zones on both 2m and 5m. Raising synced displacement from 0.8 to 1.0 removed the predicted 1381.00–1382.40 demand while retaining the other two. Both reference settings were restored.

Lifecycle correction: freeze on a completed source close inside the zone; wick-only retests remain active. This distinguishes the 1393.20–1396.60 wick retest from the 1409.50–1412.00 close re-entry. Ended zones freeze rather than continue through later invalidation. Origins are drawn retrospectively; recorded born time is the actual detection time.

Held-out INFY 5m: compared reference and candidate without changing rules and exported 555 OHLC bars. The independent model found zero fresh zones inside that limited sample. Older reference zones were outside the available export; this check is inconclusive and does not certify generalization. Evidence: infy_reference_5m.csv and infy_heldout_validation.json. Remaining uncertainty: private quality filters, native Renko rules, historical lifecycle/retention, and untested symbols. This is a behavioral reconstruction, not an exact-parity certification.

Canonical remote source now matches the saved v20 candidate: 66,639 bytes, SHA256 a3cf8dc4fc704907f28fd7b2d312b6e9b777232ec52763c32d0cd9395f3a34da. Previous v18 retained as sector_pulse_v1_pre_v20.pine. No trading orders, runner or service actions were performed.


## Completion audit correction — 14:04 IST

Previous v20 completion wording was too broad. Native version20 was compiled and added at14:01:25, replacing attached18.0; editor had been displaying historical16. Frozen state1 rectangles incorrectly suppressed later nearby origins. Thus v20 itself does NOT reproduce all three calibration zones. A one-predicate correction is prepared separately as sector_pulse_v1_v21_candidate.pine; canonical remains saved v20, and candidate is not compiled or loaded. Corrected independent model restores all three inferred HCL bounds with zero residual against the calibration levels.

The initial Python lifecycle edit had not actually changed wick touch/state transitions. This audit corrected the harness to close-inside freezing, active-only suppression and15-calendar-day expiry. Evidence was regenerated in completed_close_model_audit.json. Earlier zero-fresh INFY result remains, but older-history shortage does not explain every reference discrepancy: reference supply near1175 has plausible November8 source bars inside the existing export. It must be measured directly once chart control works. Exact labels, rectangle timing, held-out lifecycle and same-bar multi-timeframe outputs remain incomplete.

Concrete UI blocker and every attempted route are recorded in completion_audit_20261109.json. Chrome existing/new tabs timed out; native control recovered long enough to compile20 then failed to reopen editor and returned invalidUIElement on exposed Raise action. No app/process restart, runner action, authentication change or order was attempted. Required next external change: restore responsive chart computer control. No source request is required.


## Version21 suppression fix applied — 14:10 IST

Changed proximity duplicate suppression to consider only active state0 zones. Saved TradingView21 at14:08 (saved confirmation14:08:56), applied to native HCLTECH5m chart. Corrected native output showed both previously missing rectangles again, along with1381.00–1382.40 demand. Isolated reference comparison at the same viewport showed corresponding three broad rectangles without text labels. Canonical remote source updated to21, SHA25617aafd79bac1eb88fa081d44b90b945c0be2174e625384340951bf97e62b30fe. V20 backup retained. The entire v18 Shadow/originalV1 prefix is byte-identical.

Further symbol navigation failed: AX symbol button caused no search dialog; screenshot checked unchanged; coordinate click returned noWindowsAvailable. Thus exact held-out origin/right-edge/lifecycle and same-bar2m/5m outputs remain unverified. This does not negate the applied suppression correction and does not establish complete Shakti parity. No trading/runner/service actions.


## Neutral wording-only release — version22,18:16 IST

Canonical source and native savedTradingViewV1 updated. Branding strings/comments and two internal variable names replaced with neutralSectorPulse terminology; executable-token comparison (normalizing those two renames) is identical. No numeric constants, input defaults, calculations, conditions, function calls or drawing behavior changed. Case-insensitive brand-name scan passes; required Pine builtin chart.is_renko is intentionally retained and its display string isBRICK. Separate third-party indicators untouched. Evidence: neutral_wording.diff and neutral_wording_validation.json. Native rendered dashboard showsTREND STATE andPULSE DIRECTION.

Read-only stacked-line finding: right savedsettings enable extra30mRedBar and44/50/56lines, retain8sessions, disable targetbands, enable windowextensions and mergedSC/gap overlays. Exported5m aggregates for9Nov09:45–10:15 give30mH24965.65,L24905.25: levels24931.826,24935.45,24939.074. These explain theextra red cluster near24938 and nearcoincidence with mainlow24931.60. They are drawing objects absent fromlegend. Active main5m legend values remain24967.25/24931.60/24947.29/24949.43/24951.56. Other historical/SC lines retain their existing independent lifetimes. No behavior was changed to remove overlapping lines. See fib_line_origin_findings.json and nifty_30m_extra_levels_audit.json; aggregate30m caveat recorded.


## Shadow Candle table restoration —10November02:04IST

Compared latest standalone shadow_candle_final_session.pine table block and mergedV1: original3-column compact table was ported, but successful-source header was date-only and table maincontent depended on plot switch. Added explicitShadowCandle title and independent tablevisibility while retaining originalrenderer/source tooltip/optionalfullreference rows/collisionavoidance. No changes to ratios44/50/56, sourcecalculation, plots or otherV1features.

Authoritative source updated; nativeTradingView saved24 at02:02:43 and renderedverified TMP7NIFTY5m. Bottomrighttable:ShadowCandle08Nov14:05–16:00;44%=25049.78,50%=25058.57,56%=25067.37. Regime dashboard remainsseparate top-right. ToggledPlotShadowCandleOFF and confirmedtablepersists, thenrestoredON; otherflagsretained. Sourcevalidation/diff inshadow_table_restore_validation.json andshadow_table_restore.diff; fullscreenshotevidence shadow_table_v24_native.png. No backtest, broker, runner, service restart or order actions.


## Definitive full Shadow Candle table correction —10Nov02:16IST

Supersedes prior compact-table delivery: the requested original is the large structured table in TradingView standalone revision60, not the stale425-line remote standalone. Captured exact current958-line source read-only from its editor and retained it asshadow_standalone_revision60.pine. Namespaced andported complete SC tabledata dependencies andX/R/M/E engine, including latestred andclosedoscillator sections andconditionalSCchain-targetpagination. Removedobsoletecompacttable entirely. V1ratios44/50/56 andSCretention30 maintained; originalV1prefix/calculations (exceptforegrounddisplaydefault), inverseRSIoverlay block andzonesuffix preserved byte-for-byte. NewerSCmodule includesstandalone60 immediateconfirmed session-end publication andchainmetadata; notmisrepresented as tablecaptiononly.

Standalone60 initialized X/R/M/E tagna; added explicit completed-source tags andvisibilitycontrol. Native screenshotwithstandalonehiddenprovesV1 suppliespurpleX09:15–09:20 plusfulltable. Xvalues24987.95/24998.25/25008.55, R24947.29/24949.43/24951.56, M24901.26/24904.80/24908.34 matchindependent5mOHLCauditwithin0.01displayrounding. Eshowsunavailable onNSE/BSE; Latestred selectsM09Nov12:30–13:00Bullish. RSI5/15/30=70.90/64.00/68.63;RSISMA=63.51up/55.29up/67.11down. Previousperiodsrows andhistoryfooterpresent. Compactstripabsent; regime top-right andfulltablemiddle-right do notoverlap. Foregroundvisualorderfixprevents candlesobscuringtable.

Finalsource savedTradingView28 at02:14:28;fulltable/Xnative verificationandsavedlayoutcompleted02:15. Canonicalremoteupdated. Evidence:full_shadow_table_validation.json,full_shadow_table_expected_nifty_20261109.json(actualfilename full_table_expected_nifty_20261109.json),full_shadow_table_x_native.png. No backtest, broker, runner or service actions.
