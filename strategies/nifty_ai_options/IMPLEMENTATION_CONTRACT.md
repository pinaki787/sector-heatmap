# AI Renko Supertrend — current implementation contract

Latest user additions,25 November2026. This contract records requirements; it is not a completion claim.

## Activation and execution

The user must be able to start the completed strategy in PAPER or LIVE. The user selects optional exits and initially presses Start. Agents do not start runners or place real test orders. The user has approved necessary runner/dashboard/service restarts throughout this implementation; preserve settings, positions, pending intents, orders and journals and apply current-state guards.

## Automatic sizing

Automatic sizing is the default. Official TradingView native sizing is explicitly authorized, server-side, scoped to the authorizing application user. Selected broker/account supplies execution prices, source candles, contract selection and orders. Keep previous completed regular-session parent provenance, full calculation precision and the fixed30-minute conversion baseline:

- NSE/BSE indices/equities/stock derivatives:6H ATR5 /12.
- MCX, including Gold/Silver:14H ATR5 /28.
- Crypto:23H ATR7 /46.
- Forex/global commodities, including Gold/Silver:22H ATR7 /44.
- Bought-option bricks use the computed underlying brick ×0.25 for OTM and ×0.50 for ATM. Classification, never a fixed premium threshold or provider delta, selects the multiplier. This supersedes the earlier /2-for-all-options rule.

Native values are dynamic, never constants. Stale/missing sizing blocks new entries; existing owned exits retain frozen geometry. Supported execution adapters are currently FYERS and Delta India; other adapters must not silently fall back. UI values display at most2 decimals; stored calculations retain full precision.

## Automatic confirmation and reversal

Automatic entries require a fresh AI Renko Supertrend flip. Latest user confirmation is hybrid: a completed full Renko brick in the signal direction can qualify immediately, without waiting for the host candle. When the completed candle move is smaller than one brick, its completed close on the correct side of Supertrend can qualify. Candle movement is explicitly ABS(CLOSE-OPEN), not HIGH-LOW. An unfinished candle or partial brick alone never qualifies. Normal strategy exits require the opposite Supertrend direction plus the same hybrid-unit confirmation. This also applies to manual override positions; a new direction flip after manual entry is not required if the existing direction is already adverse, but the confirming unit must become available after entry. The separately enabled SMA30 exit remains independent.

On a direct opposite confirmed signal, close the exact owned position, confirm its exit fill, then enter the opposite direction immediately without waiting for another signal candle. Partial/uncertain exits never permit overlapping reverse entry. Bought options retain the separately agreed underlying-flip plus bullish premium Supertrend entry and bearish premium Supertrend exit rules; do not silently replace premium exit with underlying exit.

## Manual entry override

Provide an explicit manual-entry override in the selected broker/account/mode and already active matching AI runtime. It bypasses automatic entry qualification. The resulting position is owned by the AI strategy and its exits remain managed by the same strategy, including the chosen optional SMA30 exit. No external-position adoption, naked-option short, implicit mode switch, initial runtime start, or automatic order retry is authorized. Require explicit side selection, exact contract, valid native sizing, fresh executable quote and normal ownership/funds/market checks. Record one-shot commands and broker results durably.

## Embedded chart and form synchronization

Symbol and interval changes must synchronize bidirectionally between the strategy form and underlying embedded chart. Most recent user intent wins; delayed older responses must not overwrite newer selections. Backfill the exact selected broker symbol and matching market fields, preserve broker/account scope and saved unrelated settings. Form ETHUSD must display ETHUSD; form5minutes must display5minutes, regardless of which surface initiated the change.

When a runner is active, warn that changing symbol/timeframe can affect entry/exit behavior and obtain the user's confirmation before applying the active change. Cancel restores both surfaces. Confirmation permits changing the active timeframe; do not present a next-Start-only edit as the requested active change. Existing positions must retain their correct instrument, broker ownership and exit management; never relabel an existing position as another instrument. Instrument changes with an owned position need a queued handover while its exits continue, with clear displayed status. Do not forcibly close an owned position merely because the selected chart symbol changed.

## Optional exits and defaults

Optional one-minute underlying SMA30 exit remains OFF by default; preserve the user's existing checked choice. Bullish/Call/Long crosses below; bearish/Put/Short crosses above. Do not conflate SMA with EMA. Optional EMA/opposing-brick exits, anti-chop, calibration and manual sizing overrides remain off unless explicitly selected.

## Performance acceptance

Capture source/state and measured pre-change baseline before changes, compare identical representative inputs afterward, and preserve calculation correctness. Requested candle intervals AND elapsed observation windows:30s,1m,2m,3m,5m,15m,30m,1h,4h,6h. Distinguish captured-input replay, virtual time and actual wall-clock observation. Do not claim six-hour completion early. Preserve gzip/lossless deltas, cached histories and incremental indicator state. Quotes update LTP/axis in place; they do not redownload history or replay indicators. Real context/brick-size changes may require explicit reseeding. No unmeasured competitor-speed, overall bandwidth or chart-render-latency claim.


### Active instrument handover implementation constraint
An explicitly confirmed instrument change while the user-started runner is active must queue against its exact session. Block new old-instrument entries and reversals immediately, continue normal exits for the exact owned contract, and hand over only when flat with no pending broker intent. A managed restart of that already-active run may acquire and warm the newly requested instrument under the unchanged account, route, mode, quantity, product and optional-exit choices. It must revalidate native sizing and broker readiness, never adopt external exposure, and never become initial activation of a stopped runner. A timeframe-only change preserves live Renko state and held geometry and applies between decisions after acknowledgement. These are implementation requirements, not evidence of deployment or completion.


## Start outside market hours —25 November2026
The user may Start in Paper or Live at any time. A closed regular session must
leave the user-started worker alive, with a fresh waiting heartbeat and no
off-hours orders. Owned positions remain strategy-managed when the session
reopens. Saved selected-account broker authentication is reused; no new login
is requested while the saved grant remains valid. Crypto remains continuous.
Implementation acceptance includes closed-start, open/resume, close/wait,
holiday and source reconnect coverage, without agent-started real runners.


## Optional underlying SMA / EMA High-Low bands —25 November2026
User clarified: replace the plain SMA30 UI with High/Low bands; both SMA and EMA follow the same rules. Each has an editable whole-number period (default30;1–500) and independent entry-filter and exit switches, all OFF by default. Use completed selected-broker underlying OHLC at the synchronized selected strategy timeframe, never premium or Renko wick substitutes. Above the High average permits Long/Call; below the Low average permits Short/Put. Normal fresh-flip/hybrid requirements still apply. Both enabled filters must agree. Either enabled band exit closes Long/Call below Low or Short/Put above High on a completed candle, independently of Supertrend exits; manual entries retain these exits. EMA seeds with an N-candle SMA then alpha2/(N+1). Incomplete/missing windows block filtered automatic entries but preserve ordinary owned-position exits. Timeframe changes reset band memory to the new candle basis. The embedded underlying chart shows a blue SMA cloud and purple EMA cloud using cached broker candles; active owned charts use the exact captured runtime band seed and append-only records. Band settings apply on next Start; held contract/geometry remain pinned.

## Broker-listed expiry selection and stable instrument editing —25 November2026
Fetch expiry metadata automatically from the connected selected broker/account for the exact underlying. Default to the nearest unexpired provider-listed cutoff, allowing explicit selection of another listed date. Validate that choice again against current broker metadata and the contract master on actual contract selection. Do not synthesize weekly stock-option dates where only monthlies are listed. Reset the expiry override on an underlying handover; held contracts stay pinned. Historical run expiry must not be labelled as the draft's current automatic expiry. Five-second status refreshes leave instrument controls mounted, preserving typing and selection focus.

## Native reference provenance

Keep native Renko brick time, completed parent-window time, host-data end, and calculation time distinct. An older native brick timestamp is carried-source evidence, not proof that a new brick formed in the completed parent window. A fresh calculation timestamp alone does not establish current host data. Reject stale regular-session host data as well as stale completed-session identity. Record whether the native observation predates its sampling parent; do not rewrite source timestamps. Fresh provider validation is required before claiming a specific observed box is reverified.

## Optional SMA-only signal mode —26 November2026

Supertrend remains enabled by default. When disabled, SMA High/Low band alone supplies entries and exits on completed selected-source broker candles. Both SMA entry and exit are enabled in this mode, using the configured SMA period and strategy timeframe; EMA and legacy plain-SMA rules are excluded. Underlying closes above the upper band qualify Long/Call, below the lower band Short/Put. A premium-source bought option requires its own premium close above its upper band. The existing far-edge SMA exit rules remain: Long/Call underlying below the lower band, Short/Put underlying above the upper band; premium-owned options exit below the premium lower band. No Supertrend direction, flip, ADX, warm-up, retest, confirmation or plotted-source compatibility gate applies. Forming candles and quotes cannot qualify this mode. Normal ownership, fresh executable quotes, market/session, sizing, account and order safeguards remain.

## Mandatory SMA entry retest —26 November2026

Every SMA-band-controlled entry, including the initial entry and all re-entries, needs an actual band-touch retest followed immediately by a qualifying completed directional candle. A bullish retest approaches from above on a red candle touching the previously completed band; the immediately next completed candle must be green and close above the current upper band. Bearish is mirrored. Premium-basis bought options use bullish premium semantics for either Call or Put. Above/below-band price or a fresh Supertrend flip alone cannot bypass the retest. This applies even if the SMA exit switch is off. Confirmation expires at the next candle boundary, is consumed once, and is invalidated by source/timeframe changes or entry/exit/reset. Manual override remains the separately authorized bypass. No proximity-only shortcut or EMA10 setting is substituted.


## Session-frozen native acquisition (26 November 2026)
A verified native parent value is acquired once per exact broker/account/instrument/category/acquisition session and reused by preview, Start and runtime through persistent file locks. Native parent timeframe, ATR and prior-completed provenance are unchanged. Indian equity sessions follow the exchange calendar including special hours; MCX acquisition leases use a 09:00 IST daily opening boundary and weekday rollover (broker session gates remain authoritative for holidays and special closures); continuous products use UTC calendar-day acquisition leases, not a guessed native parent anchor. No parent-boundary or hourly native refresh occurs inside that lease.
Failed or interrupted attempts are persisted and do not automatically retry that exact scope within the session. Provider daily quota additionally pauses the authorizing connection until at least next UTC day and ten minutes. A cooldown is not a valid sizing reference. Missing references continue blocking new entries; owned exits retain captured geometry. Existing still-valid exact references may be promoted to a session lease, but expired references are never extended.


## Optional manual parent override — 26 November 2026
Auto remains the default. MANUAL_PARENT explicitly accepts a user-entered positive finite native parent brick value for the selected broker/account/instrument/market/category. Apply existing parent divisors and OTM0.25/ATM0.50 factors at full precision. The value is labelled USER, MANUAL and not independently verified; it never enters the verified native cache, requires no TradingView authorization/request, and must not be relabelled on runtime updates. It is session-scoped and retained in the run configuration/audit; expiry blocks new entries while owned exits retain captured geometry. Changing instruments requires a new bound manual value. Runtime, preview and direct launch share this validation. Manual mode is optional and does not activate trading.

## Optional SMA retest — 26 November 2026
New dashboard configurations explicitly default sma_retest_required to false. Off uses the completed band-side entry filter alongside selected Supertrend rules; SMA-only mode uses completed band-side conditions without Supertrend. On preserves actual band-touch and immediate next completed directional confirmation. Exit rules are unchanged. Legacy captured configurations without the flag retain the previously mandatory retest. The optional switch is locked while running; a new Start captures it.


## Approved Motilal direct execution — 26 November 2026
Motilal direct equities/futures use FYERS for every analytical candle, price and signal; exact Motilal contract identifiers remain the execution authority.
Entry and exit use LIMIT IOC, one native tick beyond fresh ask (buy) / bid (sell), tick aligned inward. A bounded captured buffer of 1–5 ticks is supported; default 1. There is no unlimited repricing and no fill guarantee.
Intraday maps to native VALUEPLUS; futures MARGIN maps to NORMAL. Cash direct trading requires Intraday. Direct reversals retain the signal, close and confirm broker-flat before opening the opposite side.
The exact limit and original bound are persisted before submission. Partial/unknown outcomes remain retained for reconciliation, never blindly resubmitted.
Until a broker margin calculator is verified, direct entries require a conservative full economic contract value plus 1% cash reserve; this may reject trades that would qualify for leveraged margin.
MCX source mapping accepts native exchange-units-per-lot versus FYERS per-lot conventions only for the exact exchange token/expiry and explicit native LOTS metadata. Native execution quantities are unchanged; money conversion requires a current exact-contract economic multiplier.

## FYERS candle remediation
Identical duplicates are idempotent. Contradictory OHLC is quarantined before chart/strategy consumption, including conflicts against already committed closed candles. Previously committed completed candles are persisted per scope and retained across duplicates and process restarts; incoming disagreement is quarantined without replacing that verified candle. Existing validated history remains intact.
Refreshes serialize by object and durable account/symbol/session lock. An incident has at most three total fetch attempts, at least five seconds apart. A single contradictory minute triggers two independent exact-minute refetches within that three-request budget. Both must agree before the quarantined bulk response can be repaired. Other failures require two independent identical validated fixed closed windows; gaps/invalid OHLC remain blocked. No account/provider substitution or automatic budget reset.
Persistent failure displays a specific blocked state. Tests and read-only verification do not initiate orders or runners.
