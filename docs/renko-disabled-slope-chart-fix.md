# Disabled Supertrend slope / Delta Simple chart repair

6 November 2026 IST.

Hosted BTCUSD screen showed Supertrend / selected indicators selected, all family masters OFF, a retained slope checkbox ON inside the disabled Supertrend family, and slope lookback 0. History requests failed with the slope-lookback validation error; the client treated it as a retryable feed delay rather than a configuration failure.

Static fix deployed in root and seven hosted source trees:
- Invalid inactive slope inputs are normalized only in request copies to the safe default lookback 1 / minimum slope 0. Active invalid slope inputs remain validation failures. Valid saved choices are retained.
- Settings saves normalize those same inactive request parameters.
- Selected slope validation failures are classified as chart settings errors, not feed outages.
- Header identifies the currently selected mode rather than calling every saved Supertrend setup Simple Brick by default.
- No captured trading configuration, runner lifecycle or order operation performed. Original user tab left unchanged to preserve pending edits.

Separate authenticated direct BTC Simple Brick chart query exposed a Delta chart_config TypeError: duplicate ema_exit_enabled keyword while combining settings and exit settings. Backend merge now uses one override mapping; final indicator-family/mode application keeps Simple mode indicator gates off. Dhan/Motilal inheritors receive the same source fix. Backend changes staged in all account sources; no reload performed under this request.

Validation:
- 12 targeted Python tests passed (Simple chart configuration, Simple Brick engine/range locks, qualified replay).
- 17 Node tests passed (Simple defaults/inactive slope, settings, replay).
- Mounted parent/child editor sync passed.
- All eight source trees passed inactive slope serialization probes.
- Hosted duplicate page loaded safe lookback 1, explicit saved Supertrend mode label, and stopped selected-runner state. Complete live chart recovery is not yet verified: direct Simple chart endpoint still runs the pre-reload duplicate-keyword code.
- Delta canonical BTCUSD and ETHUSD states inspected: stopped PAPER, no open position or pending order. A fresh state check is required immediately before any approved reload.

Backups: .private/disabled-slope-chart-fix-1793913571/
MD'
## Approved Delta activation and hosted verification

User approved the Delta-only dashboard reload. Immediate guard confirmed BTCUSD and ETHUSD were stopped PAPER, flat, no pending order or transition. Guarded rolling bounce reached READY. Before/after comparison found no captured configuration, position, pending-order, order/trade history or range-lock changes.

Authenticated direct Simple Brick Only BTCUSD one-minute Manual chart returned 5,000 rows with Supertrend OFF, slope OFF and opposing-brick exit ON. Initial cold request exceeded browser navigation timeout; identical cached follow-up succeeded.

Refreshed original user dashboard and confirmed 'Chart live · Stopped · Next Start LIVE', no chart error. Visible editor values retained: BTCUSD, one minute, Auto, manual reference 51.19, quantity 100, next mode LIVE, strategy mode SUPERTREND. Captured stopped runner remains PAPER; no Start or order occurred. Saved Supertrend mode was not silently converted to Simple Brick Only.

Other broker source trees contain the backend repair, but only Delta was reloaded under this approval.
Audit: .private/delta-chart-fix-activation-1793913967/result.json
