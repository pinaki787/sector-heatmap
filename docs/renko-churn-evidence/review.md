# Renko entry churn review — 6 October 2026

Implemented in the isolated worktree; not deployed. The served process remains PID 14899 at `/Users/pinaki/trading/sector-heatmap`. Saved strategy state is STOPPED, PAPER, flat, five entries consumed. No settings, history, credentials, orders, or runner activation were changed.

## Confirmed evidence

The current run lost ₹1,728 gross and ₹2,086.41 after estimated costs. Every exit was a fresh underlying EMA10 intrabar breach. Two losing range locks were released on a downside breakout before another Call. Either-direction release is the existing specified rule, not a demonstrated coding bug. A directional lock would be a new strategy policy.

Window 2 means two gap samples, one comparison; in intrabar mode they are the latest completed gap and one provisional gap. The earlier completed contraction does not invalidate that one comparison. Intrabar qualification is a level test per new candle, rather than a completed qualification onset. Completed and intrabar execution therefore intentionally differ. Neither chart markers nor OHLC reconstruct the tick-runner trades.

Current-run entry distances from EMA10 were 19.63, 38.88, 22.85, 6.06 and 11.16 underlying points chronologically. Threshold proximity contributes to sensitivity but an arbitrary larger buffer is an unvalidated strategy change. The earlier near-instant exit can occur from a legitimate next tick crossing the EMA; the correction below cannot guarantee prevention of that.

## Correctness correction

Immediately before an entry intent, obtain a fresh underlying tick and calculate the configured exit EMA from the same confirmed history. Reject an entry already on the adverse side of its enabled exit EMA. Applies to confirmed and intrabar entries, both directions and custom exit lengths. A disabled exit stays disabled. This closes inconsistent entry/exit preflight; it does not add a buffer or promise to avoid the five historical losses. Market movement after the check remains possible.

The original Pine, signal recurrence, configuration defaults and original source_reference remain unchanged. `entry-preflight.patch` contains only the runner fix and six regression cases, relative to the served source. The strategy directory and current EMA base runner were copied from the served checkout into this older worktree to make validation representative; the base-runner copied differences are baseline dependencies, not part of this patch.

## Validation and research

100 Renko tests and 33 shared lifecycle tests pass, including stale-tick rejection, setup/last-price disagreement, bearish symmetry, confirmed-entry checks, custom exit EMA and disabled exit behavior. Tests use fake brokers and do not send real orders.

12,990 cached one-minute SENSEX bars span 17 August–6 October. Five warmup sessions excluded; five complete sessions reserved for holdout; current partial session excluded. A separate completed-candle strict-onset candidate produced identical results to the original completed-candle projection: 620 development trades, gross −1,170.92 points; 121 holdout trades, gross +1,806.06 points. Holdout net is +51.90 at 1 bp/side, −1,702.26 at 2 bp/side and −6,964.75 at 5 bp/side. These are hypothetical underlying point costs, not option brokerage estimates or historical option profit. Cached coverage is marked complete, but external exchange data quality was not independently audited. No parameter search or candidate promotion occurred.

## Deployment and remaining limits

No server restart or runner start was performed. Source changes here do not affect the served process. Rendered strategy UI verification remains pending because the correction is not deployed and no UI was edited. Historical underlying ticks plus contemporaneous option bid/ask are required to evaluate directional locks, tick qualification rearming and entry distance buffers against actual option execution. A completed-only entry setting alone still retains tick exits and is not the same as this closed-candle replay. The strategy remains unvalidated for profitability.
