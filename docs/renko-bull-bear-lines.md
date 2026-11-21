# Optional Renko Bull / Bear entry lines

Remote source implementation: 2 November 2026. Backend activated with explicit user approval: guarded Dhan, Delta and FYERS worker reloads and main dashboard restart completed. No strategy runner or order action performed.

Draw horizontal lines on the Renko chart and use **Set Bull line** / **Set Bear line**. Sloping time-based trend lines must be selected from Candlestick view. The selected copies are saved with instrument/timeframe settings; moving or deleting annotations does not mutate a selected or active strategy line. Select the line again to update the next Start settings.

Default OFF. When enabled, both lines, Renko strategy basis, options route, and completed bricks are required. For bullish call entries the completed Renko brick close must be strictly greater than the Bull line; bearish put entries require a close strictly less than the Bear line. Equality, a wick beyond the line, forming observations, or a host candle without a new Renko brick cannot qualify. Existing strategy event, qualification, freshness, risk, quota, session, ownership and execution checks continue to apply. Existing explicit Override Entry remains separate. No extra crossing from the other side is required. A previous qualifying brick does not authorize a later unqualified brick.

Historical chart markers retain base-strategy semantics, disclosed in the UI. Runtime assessments and submitted positions retain line-level/brick-close evidence under `line_entry_filter`.

Modified primary and all seven isolated account source copies using targeted edits; unrelated differences preserved. Account pre-edit backup: `/tmp/sector-line-entry-backup-20261102134248`. Feature capability: `drawn-renko-bull-bear-v2`; the UI blocks enabling until the owning backend advertises it.

Validation: 39 Python tests (line gate, runner integration, defaults, lifecycle and manual override), 4 JavaScript drawing/settings tests; syntax checked in eight remote source roots. Hosted UI verification is separate from backend activation; no execution test orders were submitted.


Activation verification: all three worker handoffs reported READY and main service changed PID with HTTP readiness confirmed. Before/after audit preserved account permissions, schedules and runner configurations, with every runner stopped and no retained exposure/pending orders. Audit: `output/renko-bull-bear-20261102/activation.json`.

Hosted FYERS account UI verified after reload: Bull/Bear filter control enabled (backend capability recognized), Next Start OFF and active runner filter OFF; Set Bull line and Set Bear line buttons present. Desktop and 390-pixel responsive layouts inspected. No feature enable, Start, rearm, order, or protective-range behavior change performed.
