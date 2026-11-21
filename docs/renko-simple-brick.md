# Simple Brick Only — implementation and activation status

Remote implementation: 6 November 2026 IST. Authoritative root and seven hosted account source trees updated. Backups: .private/simple-brick-backup-1793905365 (including per-account originals).

New/reset dashboard settings select SIMPLE_BRICK, RENKO basis, completed observations, optional swing breakout OFF, swing display OFF, indicator strategy gates OFF, opposing completed brick exit ON. Completed green bricks qualify bullish; completed red qualify bearish. Same-color bricks hold; the first completed opposite-color brick exits. Existing session cutoffs, explicit risk controls, freshness, ownership, quota, execution preflight and range locks remain separate. Forming/provisional observations cannot exit. Supertrend / selected indicators remains selectable. Simple mode masks strategy gates without deleting saved indicator display/subordinate choices. Optional swing breakout can be enabled separately. Legacy saved configurations without a mode retain SUPERTREND and their previous swing-count semantics.

Structure features inspected: existing market-structure entry (bullish HH+HL / bearish LH+LL), opposing structure exit, swing-breakout gate, confirmed swing-level display. These are optional and default OFF. The original request named four structures while saying six; no additional unnamed swing rules were invented. Simple mode ignores indicator structure gates; use selected-indicator mode for optional HH/HL/LH/LL strategy filtering.

Lock semantics unchanged: same exit candle cannot re-enter; existing Renko loss range releases only on a fresh completed matching-direction close strictly outside its captured range and existing buffer; opposite direction inside the range remains blocked. Existing quick-close exposure lock unchanged. The Renko lock is reversal-loss/unknown-net protection, not an every-profitable-exit range lock. No new threshold was introduced.

Validation:
- 60 Python targeted tests passed across simple mode, signals, brick entry, optional swings, final qualification, exits and loss-range rules.
- 23 Node tests passed across new/reset defaults, preferences logic and qualified replay.
- Mounted parent/embedded editor sync passed with supported-backend fixture; verifies no execution mutations.
- Root and all seven account source trees passed JS syntax and color lifecycle/final-qualification probes.
- Two existing ContinuationLock tests fail on mandatory swing qualification in their old fixtures; independently reproduced against pre-change backup. New SimpleRangeLock versions pass.
- Hosted FYERS desktop and narrow inspection showed mode choices, optional swing controls, retained old saved Supertrend selection, STOPPED and no open position. Narrow check found no document horizontal overflow. No reset, mode change, runner start or order action used for hosted verification.

Deployment:
Static UI served and visually verified on utrading.pinakicloud.com.
Backend source staged but existing Python processes not reloaded. simple-brick-v1 capability gates Start/preview, server-save of new choices, and chart replay against unsupported old backends. Full hosted new-mode runtime/replay verification remains pending approved backend reload.
No runner started, no broker order submitted, no service restarted. Saved runner/order state files were not edited.

## Approved activation completed — 6 November 2026 IST

User approved the previously discussed service reload. Rechecked canonical runtime states in root and all account sources: all stopped/flat, no pending orders, no recovery/interrupt transition or broker bounce. Reloaded the shared systemd dashboard; restored its two previously serving account dashboards; completed guarded rolling bounces for FYERS, Dhan Pinaki and Delta. No runner Start or broker order action occurred.

Before/after comparison of 37 canonical state records found no changes to configurations, positions, pending orders, order/trade history, seen signals or range locks. Exact count/evidence retained in .private/simple-brick-activation-1793906435/result.json.

Authenticated hosted checks:
- Root and account-bound FYERS expose simple-brick-v1; FYERS retained its LIVE captured setup but remains STOPPED, flat, no pending order.
- Both serving Dhan dashboards and Delta expose simple-brick-v1 and remain STOPPED, flat, no pending order.
- Actual account-bound FYERS chart request for 5 November returned 75 host rows with SIMPLE_BRICK, Supertrend OFF, EMA gate OFF, swing breakout OFF and opposing completed-brick exit ON. Simulated entries and paired exits returned.
- Hosted editor retained the saved Supertrend selection, offered Simple Brick Only, and its Start button was available after capability detection. No mode/reset/save/Start action used for verification.
- Motilal connection dashboard was restored, but root trading route returns 'Motilal session expired; sign in again.' Authenticated Motilal runtime verification remains blocked; credentials/session not changed.
- Existing loss-only range-lock limitation remains unchanged.
- NSE/BSE saved allowed session start is 09:15 IST, strategy cutoff 15:10 IST. Actual entry requires post-Start fresh qualifying completed-brick evidence.
