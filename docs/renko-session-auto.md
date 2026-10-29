# Session Auto sizing

Approved policy: `session-atr-scaled-v1`.

Calculate Wilder ATR over completed full trading-session OHLC using the configured ATR length. Multiply by the configured base factor. Scale this common reference by selected timeframe minutes divided by verified session minutes. Defaults are ATR length 5 and factor 3.

Delta uses midnight-to-midnight IST (1440 minutes). Indian instruments require verified broker session boundaries; supported MCX sessions use the existing dated calendar. Incomplete coverage, unknown boundaries or conflicting source revisions withhold sizing. No future session is included.

A private account/broker/instrument/profile ledger persists the canonical source anchor, evidence hash and frozen session reference. All timeframes share that reference. Changing the displayed history window or restarting does not reseed it. At session rollover the first ordered observation rebases the price baseline without replaying the overnight move; delayed old observations cannot roll the reference backward.

The analytical box retains full precision and is bounded below by the verified native tick. It is not rounded to an order tick multiple. Order prices continue through separate executable-price validation. Displays use at most two decimals.

Existing saved runs without the explicit policy tag retain legacy sizing. The UI sends the new policy for new Auto calculations and checks backend capability before a Start request. An old worker explicitly displays legacy sizing and the pending activation notice. Private reference plans are excluded from public chart settings.

## Verification, 29 October 2026

81 scoped Python tests and 56 scoped JavaScript tests passed on the authoritative Ubuntu source. These cover formula scaling, complete-session evidence, freezing/restart, source conflict, rollover, delayed ticks, broker adapters, legacy compatibility and old-worker Start rejection.

A read-only calculation on retained BTCUSD OHLC used 77 completed sessions from an August 13 IST anchor. ATR(5) was USD 1707.665848229571; factor 3 gave reference USD 5122.997544688713. Boxes for October 29 were:

| Timeframe | Box (display USD) |
| --- | ---: |
| 1 minute | 3.56 |
| 5 minutes | 17.79 |
| 30 minutes | 106.73 |

All exceeded the verified USD 0.50 native tick. Cold full-history calculation took about 46 seconds at 1 minute; chart reads allow 120 seconds and retain six cached contexts. No fill replay or performance claim follows from calculated chart signals.

Root and applicable hosted account sources were installed with backups and a private install manifest. The loaded backend was not reloaded and does not yet advertise this revision. Activation and hosted verification of new sizing remain pending explicit reload authorization. The stopped PAPER runner, journal and saved configuration were preserved byte-for-byte; no Start or order was sent.

Final unmodified hosted-screen check: STOPPED, selected chart 5 minutes, pending-activation source disclosure visible and wrapping at 430px. The old worker currently withholds chart history with 'Completed Renko price history changed after processing before retained hashes; same-anchor recovery required.' This guard was preserved; source implementation and isolated read-only calculation do not establish successful hosted chart activation. No recovery/reload was performed.


## Hosted activation and transport correction

The user's current instruction authorizes the required routine reloads; the earlier approval-pending status is superseded. Used the normal guarded account bounce after broker reads showed zero positions and open orders. Delta worker PID 3012735 was replaced by 3130154, READY. Its three runtime files were byte-identical afterward. The loaded runner endpoint advertises session-atr-scaled-v1, while its existing saved run remains legacy-history-seed-v1, stopped PAPER, flat/no pending, same run ID and two recorded trades.

Actual hosted 5-minute and 30-minute chart responses use the new policy. The full production reference source contains 107 completed sessions with anchor 1783967400, reference ATR 1707.665856506944 and reference 5122.997569520832. All tested timeframes share input hash 23088cd43a4a94d984b7f18172225caf1c10d955f439736c7b9dde8870e34c79 and October 29 IST session opening. The small full-precision difference from the earlier isolated 77-session dry run reflects the production canonical source anchor; displayed boxes remain USD3.56/17.79/106.73.

The hosted one-minute cold request exposed the ordinary proxy's 35-second read timeout. Limited the extended 120-second timeout to read-only Renko chart GET routes; mutations and ordinary APIs retain 35 seconds. The chart client receives the same 120-second budget. A fresh hosted one-minute calculation completed HTTP200 in94.46s, 5000 displayed source rows, no history error, box3.5576372010561332, same reference hash. This verifies full history calculation without shortening its initialization or changing fills.

The normal dashboard restart guard found all shared/account runtime states inactive. Main PID2872482 was replaced successfully; all31 runtime records remained byte-identical.21 focused proxy transport checks pass, including chart/ordinary/mutation timeout isolation. The full proxy test file also has two inherited permission-check failures against unrelated working-tree auth changes; those checks were excluded from the scoped transport result and were not changed.

Actual hosted desktop charts verified selected timeframe OHLC, native USD axis and Supertrend, one calculated BUY/SELL/EXIT set, USD+INR P&L and collapsed/off Anti-chop. A narrow layout check and final120-second transport activation are recorded in the investigation ledger. The existing unsaved verification draft was preserved; a new verification tab was used. No Start/rearm, order action, audit rewrite or historical fill replay.
