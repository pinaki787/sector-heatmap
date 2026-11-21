# Renko live-price correction — completed 3 November 2026

Live Market Chart now confirms every full crossed brick on accepted live prices and advances Supertrend/exit EMA per brick. Only the unfinished remainder is provisional. Two-box reversals, user settings, optional indicators, re-entry selection, account isolation and risk gates are preserved. Historical Research and Runner Session Audit remain separate. Execution wakes after durable brick publication. Fills are broker events and are not guaranteed at brick prices.

Automatic bullish entries and selected same-trend re-entries require a completed green signal brick; bearish entries require a completed red signal brick. Actual open/close direction and brick-direction metadata are checked at eligibility and submission preflight, including the latest published price brick. Manual Override remains a separate explicit action. Fill timing can follow a subsequent price change.

The original test_exact_signal_formula_is_shared passes unchanged. The differing field was auto_box, not the selected box: the NSE/BSE Auto-specific warmup branch incorrectly affected diagnostics in Manual mode. That branch now applies only to Auto mode; Manual sizes and Auto sizing behavior are unchanged.

The inactive Dhan snapshot's missing spread_policy.py and required import closure were restored. Other missing runtime imports in older snapshots were also restored without replacing existing account-specific files. Workspace provisioning now carries the required runtime dependency files.

Validation: 148 targeted Python checks passed, including the original failure, signal math, live-price jumps/ordering/reversals, initial/re-entry color gates, preflight and provisioning. All seven account snapshots pass live-chart and execution-color suites (six run 21 checks and one runs 19 due to existing fixture versions). All eight source directories pass syntax validation. The earlier 24 JavaScript chart checks passed; browser source was unchanged in this completion pass.

Hosted FYERS Live Market Chart with its runner stopped confirmed a five-minute chart brick at 09:48 IST, inside the 09:45–09:50 candle. A separate read-only chart context confirmed four bricks at 09:50:38 and two at 09:50:39. Price 23626.50 versus confirmed close 23627 at 09:50:44 left a 0.50-point remainder of a 1-point box before the 09:55 candle close. Desktop and 390 CSS-pixel views were inspected; viewport overrides were restored.

Beyond FYERS, a standalone instance of the production Delta native adapter and LiveChart warmed from 30 real candles, connected to the real public WebSocket and confirmed 26 one-point bricks on one accepted observation. Supertrend and exit EMA advanced on each brick; final observed price and confirmed close were both 77050. This is native market-data/adapter evidence, separate from the hosted FYERS UI and from fills.

Dhan explicitly returned an expired/invalid saved session error. Motilal explicitly returned an expired session error. Their shared execution paths passed deterministic tests; broker-specific live checks require renewed sessions. No credentials or OTPs were changed.

Required Dhan/Delta/FYERS rolling bounces and the main dashboard restart completed successfully. Main and restarted workspaces report READY. All 35 canonical runtime states retained identical configuration, run ID, trade count, running/entry flags and position/pending presence. All runners remain stopped. No automatic recovery was needed, and no live order or manual runner action was initiated. Inactive workspaces were not started.

## Remaining native broker checks completed after renewed sign-in

The Pinaki Dhan and Motilal accounts now authenticate successfully; the earlier expired-session result is superseded for these two accounts. No additional sign-in is needed for these verified profiles.

Dhan's authenticated hosted chart endpoint returned ORDERED_LIVE_PRICE bricks from its own Data API observations. A current price of 23637.20 completed five 1-point bricks ending at 23637, with Supertrend and exit EMA progressing on each brick. A 0.20-point remainder stayed unfinished before the selected five-minute host close. This was a separate read-only chart context, not a saved setting change or order.

Motilal's authenticated hosted chart endpoint returned 518 completed 1-point bricks from one fresh native price of 23637, with per-brick Supertrend and exit EMA progression before the five-minute host close. Warmup used 72 five-minute bars aggregated from retained native captured history starting 16 October. The large brick count spans the price gap from that older native archive to the current accepted observation; it is not a claim of 518 separately observed current-day price movements. Current-day completed captured history was unavailable, so the custom read-only historical window explicitly included the retained archive. No alternate-broker data or synthetic host candles were used.

During these checks the user started the FYERS LIVE run RENKO-RUN-1d72330ff98d6f2194b4. It was observed running with POSITION_OPEN, no pending order, PRICE confirmation and trend re-entry enabled. Anti-chop, manual trend, calibration, higher-timeframe Supertrend, market structure and HTF RSI filters were off. The active recurrence and execution gate require completed matching-color Renko bricks and reject provisional/unfinished bricks. There is no selected host-candle close delay in this active path. A held position prevents another entry while that exposure remains open.

After the live-run constraint was communicated, no runner, workspace, shared service or process was restarted or reloaded. No verification order was initiated. The user's standing preference against interrupting live runs was saved to memory.
