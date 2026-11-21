# Shakti Prime / Red Bar V3 parity investigation

Status: in progress; exact parity not established. No trading actions or service changes authorized by this work.

## Reference observed in TradingView, 3 November 2026
- Layout TMP7, DELTAIN:BTCUSD.P, standard 5-minute candles.
- Reference: DR DEVENDRA MAHAKAAL | SHAKTI PRIME — RENKO INTELLIGENCE.
- Candidate: Red Bar v3; editable 155-line independent observed-behavior reconstruction. Its source labels intermediate target spacing and SMART/color rules as hypotheses.
- Comparison layout: reference visible left, candidate visible right; crosshair and date-range sync enabled. Different visible date extents remain possible; crosshair OHLC matched on inspected bars.
- Candidate current session 09:15–15:30 Asia/Kolkata; skip first reference candle; prior-session carry enabled.
- Candidate current EMA200 2m channel enabled, SMA200 disabled, EMA delayed one chart bar; SMA5 on >=30m enabled.
- Candidate SMART targets, 5m reference, 10 each direction, 2 forward, 1 retained session.
- Candidate reference logic: first bearish standard candle inside configured session after skipping opening candle; separate 5m and 30m request.security, lookahead_off. Reset is session/day-change driven. Targets H+n*(H-L), L-n*(H-L); bands +/-6% of reference range; revealed count uses confirmed close extremes, reached colors use tracked wick extremes.

## Reference controls read directly
- Auto reference timeframe; manual fallback 5m; Indian option reference Auto; entry confirmation 1m; Renko confirmation option text truncated, must capture full.
- Session preset Auto; manual 09:15–15:30 Asia/Kolkata.
- Global opening: Auto gap + IST fallback; Gold/FX fallback 03:30 IST; crypto reset 02:30 IST; minimum opening-detection break 45 minutes.
- Extra India 30m red zone disabled; transparency 91; 44/50/56 enabled.
- Locked reference candle highlight; internal 44/50/56; target-centered bands enabled.
- SMART display; 2 forward; band transparency 90; main H/L width 4; target width 3; target band width 2.
- Pending orange, upper reached green, lower reached bright red; exact RGB values not yet captured.
- Maximum targets 10; autoscale T15/T20 off; T11-T20 price labels on; both directions on; signal SL on; dashboard on; retain 8 historical sessions.
- Target Reaction Intelligence off; reaction dashboard on; horizon 20 confirmed bars; minimum observations 30; research through T10; reaction marks off.
- SL Midpoint; Smart Hybrid Structure-Aware; no buffer; ticks 0 and percent 0.
- IST 12:30–13:00 and 17:30–18:00 windows on; transparency 78; internal and extended 44/50/56 on; H/L extensions off; retain 8.
- Marker next red cutoff: 30m reference, session 02:30 IST, ignore first candle on.
- 200 SMA high/low band from 2m: enabled, length 200; band fill enabled. SMA5 close enabled on >=30m; length 5; line width 2, fill transparency 88.
- Order blocks enabled: confirmed swing strength 5; origin search 12; ATR14; break body >=0.8 ATR; strict prior liquidity sweep off, sweep window 20.
- OB quality >=65; historical max180; fresh per direction3; mitigated max180; nearby suppression0.35ATR; SMA directional alignment off; retention15 calendar days; fresh transparency73, touched85, invalid93; freeze on first touch; invalidate Close.
- Below5m stricter filtering on: body0.9ATR; quality65; spacing8; fresh2; suppression0.35ATR.
- Confirmed2m/5m OB synchronization on: score65; displacement0.8ATR; source spacing3.
- Renko box AUTO; FIX fallback10; original V19 Supertrend ATR14/base multiplier3; BUY/SELL labels and Supertrend line off.
- Shakti midline on; envelope off; hide anomalous plot jumps on.
- Premium dashboard Compact, Top Right. Visible rows Market Regime, Renko Trend, Shakti Direction, Trend Alignment; example Strong Bull / Bullish / Rising / 3/3.

## Required work
1. Preserve original source snapshot and reconstruct the complete Inputs/Style/Visibility specification including exact colors and plot order.
2. Calibrate session resets, reference locks and targets on matching feed/timeframe/history; compare closed historical bars across sessions and gaps.
3. Infer Renko AUTO sizing, V19 adaptive Supertrend, Shakti formula and dashboard conditions from observed outputs; do not present guesses as verified.
4. Implement a separately named candidate first; compile and compare in TradingView, preserve original.
5. Validate settings, labels, colors, tables, plots, historical timing and real-time/reload stability across instruments/timeframes. Keep all remaining uncertainty explicit.


## Verified progress — 4 November, after midnight IST
- Original 155-line Red Bar source preserved as red_bar_v3_original.pine; 8,611 characters; FNV-1a 1103780509 matched captured TradingView source.
- Raw exports retained here: BTC 5m baseline, 5m diagnostic (Supertrend and envelope enabled), 2m diagnostic, 2m paired, 5m paired, and 5m FIX10 diagnostic.
- Numerical timing correction: initial cached 5m reference export reset at 02:30 and locked at 04:30. Recalculated diagnostic resets at 02:55 and locks at 04:55. The completed 30m first bearish candle is 04:30–05:00, H76917 L76710. Recalculated historical behavior matches lookahead_off and prior-state carry until source close. Do not claim lookahead_on is the source formula. Reload/live caching remains an open issue.
- verify_reference.py: 1,290 high/low/internal-level comparisons, 200 independently computed 2m SMA values, and 238 lower-timeframe sampling comparisons, zero mismatches on supplied fixtures. Initial incomplete session excluded.
- red_bar_v3_core_candidate.pine compiled and saved separately in TradingView as Red Bar v3 — Shakti parity research; displayed title Red Bar v3 — core parity research. Candidate is present on LEFT reference chart alongside Shakti Prime. Original Red Bar remains on right and hidden on left.
- verify_paired.py: 2m 303 closed candles x7 plots =2,121 comparisons; 5m 299 closed candles x7 plots =2,093 comparisons; zero mismatches. This covers reference high/low,44/50/56 and SMA high/low only. It does not establish target, style, other instruments, Renko, Shakti, dashboard or complete settings parity.
- Longer history triggered inherited drawing time-buffer offset failure; core candidate explicitly allocates max_bars_back=5000 and max_bars_back(time,5000), then compiled and rendered. Further long-history checks remain.
- Exact input target colors read via custom-color hex editor: pending #f59722; upper reached #2ac866; lower reached #ff0000; extra India30m zone #dc2626. No custom colors were added or changed.
- Detailed dashboard additionally shows SMA STRUCTURE, VOLATILITY, PRICE EFFICIENCY, CHART TYPE and STATUS, beneath compact rows. Example BULLISH / CONTRACTING / LOW / CANDLES / OTHER / FORMING.
- Author publication is private invite-only, source disabled, description only SHAKTI PRIME INDICATOR - TMP. No formula documentation found.
- Existing downloaded Laurus 5m export38 (15,261 rows) and NIFTY5m export4 (1,651 rows) have MAHAKAAL equal to MAHAKAAL Renko Supertrend on every row. The editable Laurus observed-bands research script contains no MAHAKAAL name and does not yet supply the matching engine formula; do not imply source recovered.
- fit_shakti.py and long-lag experiments: linear autoregressions and simple ATR envelopes fail exact numeric parity. These fits remain hypotheses, not implementation-ready matches.
- Current temporary reference research settings: 5m standard candles, Supertrend ON, envelope ON, Detailed dashboard, box FIX10 (original AUTO). Restore AUTO, Supertrend OFF, envelope OFF and Compact after fixed-box diagnostics finish; preserve all other inputs.
- Native Renko hypothesis probe is saved remotely as native_renko_probe.pine and currently being compiled in the research copy. This adds data-window diagnostics only; not verified MAHAKAAL logic. Probe must not be presented as matching until paired exports prove it.
- Expanded 186-line red_bar_v3_parity_candidate.pine is an unfinished scaffold and is NOT the active TradingView candidate. Some controls lack completed behavior and engine/table/window/OB parts are missing. Do not deliver it as final.
- No runners, broker settings, services or orders touched.


## End-of-probe state, 00:24 IST
- Native FIX10 Renko ta.supertrend(3,14) model rejected: 0/301 exact, MAE58.91864, max218.20175. Raw paired fixture and native_renko_result.json retained.
- FIX10 reference line is largely quantized in10-point increments with occasional anchor-residue changes. Native Renko is not equivalent. This suggests testing custom synthetic-brick construction, but no private formula has been recovered.
- FIX10 base-multiplier1 counterfactual exported as btcusd_5m_fix10_mult1_20261104.csv. Compared with multiplier3, all302 overlapping ST values initially unchanged; this needs repeat-after-recalculation before concluding the control is ignored in FIX mode.
- Reference restored and UI verified: AUTO box, FIX fallback10, ATR14, base multiplier3, BUY/SELL labelsOFF, Supertrend lineOFF, midlineON, envelopeOFF, hide jumpsON, Compact dashboardTopRight; both chart panels standard5m. No other reference inputs intentionally changed.
- Rejected native probe removed from active research-copy source; core source still includes explicit5000-bar time buffer allocation. Verify saved/compiled status and runtime health on next inspection.
- Source in TradingView research copy is red_bar_v3_core_candidate.pine, NOT expanded scaffold. Source snapshot maintained remotely only; local project unchanged.
- Next work: implement full settings and visual controls with real behavior; independently calibrate retained SMART target rendering/labels, IST window markers, OB zones and states, and table formulas; continue fixed-box/automatic Renko and Shakti identification. Need broader instrument/timeframe/reload verification. Full goal remains incomplete.

## Full tab reload validation — 4 November, around 00:50 IST
Latest active candidate: red_bar_v3_visual_candidate.pine, 301 lines, 19501 characters, FNV1a 1750361861, compiled and saved. Adds target reveal/touch segments, retained windows with 44/50/56 levels, reference highlight, extra India zone and input/legend cleanup. These visual behaviors still require broader parity checks.
Wide pre-reload comparison: 11690 core values, 4 recent 2m SMA differences. Toggling the reference dashboard off/on did not clear them. Actual full TradingView tab reload followed by fresh left-chart CSV export: btcusd_5m_visual_paired_reload_20261104.csv, 1057 closed candles, all 7399 values across five reference plots and two SMA plots matched at 1e-8 tolerance. This supports a cached realtime-versus-recalculated historical sampling explanation; realtime parity remains unverified.
Full parity remains incomplete: private Renko/Shakti engines, order blocks, signal SL, reaction engine, dashboards and all-input behavior have not been reproduced. Preserve original Red Bar and keep candidate explicitly marked research.

### Controlled engine separation tests
AUTO diagnostic after reload saved as btcusd_5m_auto_diagnostic_reload_20261104.csv. Comparing original diagnostic with FIX10 on 297 shared closed timestamps: Renko Supertrend differs on all 297, Shakti midline and upper envelope exactly unchanged on all 297. New ATR14 versus ATR7 controlled test (btcusd_5m_atr7_diagnostic_20261104.csv), 1057 shared historical timestamps: Supertrend differs on all1057, Shakti midline/envelope unchanged exactly on all1057. Restored ATR14, AUTO, ST line OFF/envelope OFF afterwards. This independently establishes Shakti does not depend on these exposed Renko box/ATR controls for the tested sample.
Envelope is perfectly symmetric around the midline in fresh1058-row sample. Best simple TR RMA model length14 multiplier1.8237 stillRMSE13.33/max56.18: rejected. EMA inverse/cascade plateau and multivariate linear fits fail numerical tolerance; artifacts retained, no approximations added to candidate.

### Cross-timeframe and market validation — around 00:58 IST
Fresh BTC 30m paired export:1017 closed candles,8 plots including 5 SMA Close —30m+,8136 numerical comparisons,zero mismatches. Fresh NSE:NIFTY 5m export:1017 closed candles,7 core plots,7119 comparisons,zero mismatches. Canonical verify_paired.py now runs five post-calculation historical samples,total26868 numerical comparisons,zero mismatches,while separately retaining both pre-reload diagnostic exports with4 SMA differences each. This is scoped historical numerical core validation,not full indicator parity. Original source settings restored toATR14/AUTO/STlineOFF/envelopeOFF. Left BTC5m source/right BTC5m candidate restored; left candidatehidden toavoid doubleoverlay. Original RedBar remainshidden and unchanged.

### Gaussian and custom-Renko hypothesis tests
Primary author publication https://in.tradingview.com/script/izxTRSoK-Enhanced-Renko-Channel-with-Emulation-and-SMA-by-Dr-Devendra/ describes Gaussian midline and True Range boundaries for an older protected script. This is a hypothesis lead, not evidence that Shakti uses identical formulas. Standard Gaussian filters1–9 poles, periods5–500, fourOHLCsources, fast/reduced-lag modes tested. Best5m RMSE10.198/max28.545 (close,3poles,123period); 2m bestRMSE2.986/max5.163. Median prefilter variations still fail exact parity. Rejected models retained in Gaussian result files. Custom fixed10 Renko construction across path/reversal/aggregation/cap/anchor variants also fails: bestRMSE35.646,0/300 exact. No approximation incorporated into active candidate.
Current completion_audit.json explicitly records all unmet scope. Full completion remains unproven, with protected formulas and undocumented classifications the central gap.

### Extended-target and control fidelity check — around01:07IST
SourceTargetModeALL /max20/autoscaleON anchors81057 and72570 match candidate formula forH76917,L76710,range207. However sourceALL suppresses most/all target lines while candidate draws all20 per side. Repeated source check withhistory1 still suppresses lines. Source inputALL,max20,autoscaleON confirmed inAX. Do not claim ALL-mode orT11–T20label parity; underlying source bug/cache/object lifecycle remains unresolved. Candidate remains functionalALL but behavior differs. Both source/candidate restoredSMART,max10,autoscaleOFF,history8.
Source SMARTForwardTargets dropdown choices capturedexactly1,2,3. Candidate previously numeric1..5; remote candidate correctedtooptions[1,2,3] andautoscale control reorderedbeforeT11–T20labels to match source. Latest301lines/19499characters; UI upload underway. No numerical model changed.

Dropdown/order update compiled and saved in TradingView at01:07:37. Candidate UI independently verified SMARTForwardTargets combo box2, max10,autoscaleOFF,history8. Editorclosed and source-left/candidate-right visibility restored. Latest active source19499characters/301lines. Numerical formulas unchanged; no broader repeat of passed core tests needed for this input-presentation-only change.

### Source-access and blocked audit —01:09IST
Current TradingView source indicator More menu explicitly shows row(disabled) Source code. Public author/TradingView/Upsurge formula searches supplied no Shakti specification. This is the same unavailable-private-formula condition recorded across at least three consecutive goal continuations. Existing fitted/native/custom/gaussian hypotheses fail exact observable outputs. Full parity requires unavailable algorithm evidence; more guessed calculations or table values would not be an apples-to-apples match. Goal not complete. Preserve compiled research candidate and all evidence; original unchanged, normal source settings and side-by-side restored, source menuclosed. No runners/orders/services touched.

## User correction — dashboard must be part of Red Bar research copy
User rejected original-source dashboard overlay. Temporary right-source style changes were fully restored and source hiddenright. Native table appended to candidate:showdashboardON,Compact/Detailed/Off,TopRight/TopLeft/BottomRight/BottomLeft. Main four private state rows explicitlyUNVERIFIED ratherthan guessed values. DetailedSMA structure uses existing verifiedchannel; charttype andstatus are actualcurrent context. Dashboarddoesnotconsume anyoriginalsourceplots. Fullnumericalengineparity remainsblocked.

NativeRedBar dashboard compiled and saved07:36:09IST. Screenshot07:36:35 confirms independentrighttablewith MarketRegime,RenkoTrend,ShaktiDirection,TrendAlignment rows. OriginalrightShaktiPrime hidden; leftresearchcopyhidden. Privateengine rows explicitlyUNVERIFIED; fullparity remainsincomplete. No service/runners/orders touched.

## Renewed formula investigation —4November07:40–07:45IST
User explicitly requested continuing formula reverse engineering after native dashboard addition. New tests:
- probe_vidya.py: CMO-adaptive VIDYA length/momentum2..100 overfourOHLCsources plus postSMA1,2,3,5,8,10,14,15,20,30,40. Best5mRMSE12.203,max37.214,0/558exact; rejected.
- Controlled current exports jumpcleanON/OFF:1098 closed timestamps, zero differences acrossShakti midline,upper/lowerenvelope,andRenkoST. Guard is not the explanation for residuals in this sample. JSONjump_cleaning_sensitivity retained.
- Earlier diagnostic versus current baseline:1015 shared historical timestamps unchanged exactly acrosssamefourengineplots. This supports historicalstability forsample; not blanketnonrepaintingproof. JSONengine_history_stability retained.
- Gaussianvolume-normalized channel model powers.25,.5,1: bestRMSE10.747,max32.904,0/598exact; rejected.
- Gaussianinverse recurrence1..6poles,period5..500,exact2androunded1.414norms: no recoveredpiecewiseconstant input undercondition-scaled tolerance; rejects testedGaussian-smoothedRenko-step hypothesis.
- GaussianTrueRange envelope1..9poles,period3..300,fast/nonfast:bestRMSE15.518,max50.763; rejected.
No fitted approximation added to research copy. Table private states remainUNVERIFIED. Reference settings restored and independentlyobserved:STlineOFF,envelopeOFF,jumpcleanON,AUTO,ATR14,multiplier3,CompactTopRight. No runners/orders/services changed. Fresh blocked-audit starts with this resumed investigation; this turn yielded useful new evidence, so do not re-markblocked merely because models failed.

## Observation-derived dashboard — user authorized
User asked whether values could be inferred and then explicitly said go ahead. Implemented four main rows as INFERRED with standalone calculations, no original dependency. Shakti Gaussian3poles period123 close: training direction98.84%, chronological holdout99.09%; 2m148/149 direction matches afterwarmup. PriceRMSE12.49 on5m, NOT line parity. Renko row uses standard candle Supertrend14factor5.7 proxy: training88.42%, chronologicalholdout95.15%. NativeFIX10 Renko direction69.10% in301rows, notused. Three-direction votes combine proxyRenko,GaussianShakti slope,SMA200channel structure; 3votesStrongBull/Bear,2Bullish/Bearish,otherwiseMixed. Mapping hypothesis not replayverified. INFERRED header/tooltip state proxy formulas; can disableinference to showUNVERIFIED. Unsupportedcharts/warmupshowUNVERIFIED. Detailedvolatility/priceefficiency stillUNVERIFIED. These calibration rates are not independent cross-instrument validation or trading performance.

InferreddashboardUI source hash3789253000 matchesremote exactly25729characters. Compiled/saved07:55:18IST; screenshot07:56:23shows actualnativeRedBartable INFERRED,STRONGBEAR,BEARISH,FALLING,3/3. Visible leftsource alsoStrongBear/Bearish/Falling; alignmenthistoricalmappingstillhypothesis. Originalrightsourcehidden,leftRedBarhidden; no externalindicator dependency. No referenceformulas orverifiedcorecalculation changed. Fullparitynotcomplete.

User requested renameSectorPulseV1 and removalofShaktiParityfield/value. Sourceupdatedindicator title andtableheader; removedbothcellsandshiftedremainingrowsup; table10rowsinstead11. Canonicalsource sector_pulse_v1.pine plusworkingcandidate same25155characters/365lines/FNV1a1042105703. Calculationsunchanged. UIcompile/renameverificationpending.

SectorPulseV1 compiled07:58:24,cloudscriptRenamed07:59:02. Screenshot07:59:13 verifieschartlegendSectorPulseV1 andtableheaderSECTORPULSEV1; ShaktiParityrow/value absent and remainingrows shiftedup. No calculationchanges. Sourcehash1042105703 matches UI25155characters.

## Native inferred order blocks — user requested
Sector Pulse V1 now includes independent confirmed swing-break/displacement order-block module. Inputs: swingstrength5, originsearch12, ATR14, breakbody0.8ATR; optionalstrictsweep20, inferredminimumscore65, spacing3, nearestfreshcenter0.35ATR, SMAalignmentoptionaloff. Below5mdefaultstricterbody0.9/spacing8/fresh2. Defaultfullorigin-candlerange; optionalbody-to-wick. Researchquality score explicitly50structure +min(30,bodyATR*20)+10recentsweep+10SMAalignment. This is NOT recoveredprivate score.
Zones created only onconfirmedstandardcandles afterpivotright-sideconfirmation. Dataoriginbackdated toopposingcandle, birthdetectionbar retainedseparately; nothistoricaltradingsignalsfromorigin. Touch/invalidatelifecycleonlysubsequentconfirmedbars; Close(default)/Wickinvalidation; freezeonfirsttouch(defaulttrue). LabelsSUPPLY/DEMAND andFresh/Touched/Invalid+Qscoreinsideboxes. Retain15calendardays/max180zones, freshlimit3perdirection andmitigated180; drawingbudgetreserves20boxesfromPine500globalcap.
Sourcebackedupsector_pulse_v1_pre_order_blocks.pine. Latestsource515lines/35132characters/FNV1a291998943 matchesCUAinmemory. UIcompilepending. Existingcore/target/dashboardformulasunchanged. No runner/order/serviceactions.

FirstOBbuildcompiled08:19:28 andrenderedbothSupply/Demandlabels. VisualQAfoundfarhistoricalfreshzonescompressingautoscales. Addedexplicitnearpricevisibilityfilter(defaultON,maxdistance20ATR)withdataretentionunchanged; invalidzonesdefaultOFFandnoinvalidlabelsifshown. Updated519lines/35555characters/FNV1a463623181 matchesCUA; secondcompilepending.

RefinedOBbuildcompiled/saved08:21:21IST. Screenshot08:22:02 verifiesSectorPulseV1withnativeDemandTouchedlabelandnormalpriceautoscales. FirstbuildvisuallyverifiedSupplyandDemandlabels includinginvalidstates. DefaultinvalidhistoryOFF/nearprice20ATR explicitlyconfigurable,dataretentionunchanged. Noexternalindicator dependency,privateOBscore/parityunverified. Calculationlogicrequiresconfirmedstandardcandles; nofuturepivotuseatbirth, zoneoriginshownhistoricallybutcreationrequireslaterconfirmedbreak. No orders/runners/services touched.

## User reported order-block regression — rollback
User reported lastorderblock change disturbed/broke indicator. Restored exactpre-orderblock365-lineSectorPulseV1snapshot25155characters/FNV1a1042105703 inauthoritative files anduploadedtoTradingView08:28:39. RejectedOBsource retainedsector_pulse_v1_order_blocks_reverted.pine forisolateddiagnosis. Do not re-enable/reintroduce it aspartofthisrollback. Knownfirstbuildfar-boxautoscales causedlargechartcompression; nearpricefilterhadnotestablishedbroaderregressionfreedom. Rootcauseofuser'sreportedadditionaldisturbanceisnotyetfullyisolated. Pre-existingcoreanddashboardpreserved. Currentuserlayoutissinglechart; preserveit,hideoriginalRedBarandshowrestoredSectorPulseforverification. No runner/order/serviceactions.

Rollbackcompiled/saved08:28:40IST. Screenshot08:29:21confirmspre-OBplots/targets/windows/tablevisible,OBsabsent. Usercurrentlayoutsinglepane preserved; restoredSectorPulsevisible andoriginalRedBarhidden. Layoutsaved08:29:46. Do notclaimOBregressionfixedbyfilter; modulewasremovedentirely. No orders/runners/services touched.

## GOLDM visual mismatch correction — 4 November late session
User explicitly requested fixing line/label mismatch. MCX wrongly classified with NSE/BSE equity5m0915-1530; changed MCX to global broker-aware30m reference. TradingView compiled/saved23:38:00IST. Live paired legend now high142550 low142004,44%=142244.24,50%=142277,56%=142309.76, SMA values equal at capture. Core chart overlays agree. Prior dense targets around139k were based on wrong65point equity reference; current correct span546. Further SMART pending lower line revealed minimumforward2 instead of minimum1; changed floor clamp to1, keeping configured forward offset. Verification underway. Original/other indicators preserved; no runners/orders/services touched. Full private-engine/ALL20 parity still not claimed.

SMART clamp correction compiled/saved23:39:13IST,25205characters366lines. Screenshot23:39:32 paired original/candidate confirms current reference/SMA plots and current target centers align; extra lower pending target removed. Screenshot23:39:47 candidate alone confirms unique price-scale labels and native dashboard StrongBull/Bullish/Rising3of3. Original hidden (not removed) after comparison, SectorPulse visible; layout save23:39:58. Residual historical target cutoff differs: source extends old session until next lock while candidate stops while reference uninitialized after reset; not fixed in this patch. Private engines still absent/inferred and full parity not established.
