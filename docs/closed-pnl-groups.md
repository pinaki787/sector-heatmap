# Closed realised P&L groups — 24 October 2026

## Implementation

The existing Live Feed & Positions broker dashboard has one shared Closed Positions panel. It now uses `closed-pnl.js`, with Daily → day/rows, Weekly → week/days/rows, Monthly → month/weeks/days/rows, and Annual → financial year/months/weeks/days/rows. The existing selected-period limits remain current day, current Monday-based week, current month and current April-based financial year. Date groups load lazily with two concurrent read-only report requests and an account-token-isolated five-minute server cache.

The FYERS handler accepts validated `from_date` and `to_date` values within the current financial year through today. Every child date range is clipped to its parent; adjacent months never duplicate cross-month week dates. Broker report rows aggregate instruments over each requested day; they are not represented as individual executions. Same-day position fallback is explicitly gross and never assigned to historical dates.

Gross, broker report charges and net are separate. Report-level charges are never allocated to segments or rows. Segment filtering therefore shows gross totals and marks segment charges/net as not supplied. The unchanged overall footer remains explicitly all segments. Broker master instrument codes distinguish stock/index options and futures where the exact contract is still available in the master; expired or missing metadata remains visibly unclassified derivatives. Cash and commodity categories use the report exchange/segment. Only the selected account's Live INR data is included. Other brokers retain their existing report rows without invented dated reporting; crypto is not available through this FYERS account form.

No new dashboard section or permission was added. Existing broker account routing and section controls remain in force. Expansion and segment choice are retained per account/period during refresh. Account changes stop queued reads and prevent stale results repainting the previous account.

## Validation and activation status

- Remote Python unit tests: range boundaries/rejections, account cache isolation, fee non-allocation and master categories passed.
- Remote JavaScript DOM tests: contiguous/nonoverlapping periods, weekly hierarchy, filter accounting, escaping and refresh preservation passed.
- Python compile and JavaScript syntax checks passed.
- Read-only FYERS reports verified daily net totals reconcile to weekly net loss of INR 3,745.36; segment gross totals reconcile to INR 188.00.
- Root source and the owning FYERS account source were updated. Static UI files are served immediately. The FYERS-only guarded bounce completed READY after explicit user approval; the activated FYERS owner PID is 1518986.
- Hosted compatibility rendering was checked; a global 1800px table minimum width was found and overridden within the Closed Positions panel.
- Hosted Daily empty state, Weekly day groups/rows, Monthly week/day groups and Annual year/month/week/day/rows were verified. Annual showed seven months; October four clipped week groups; current week six date groups; 23 October fifteen broker realised rows. Desktop and 390-CSS-pixel layouts were inspected. Numeric column widths were adjusted; the narrow document and viewport both measured 390px, with the table fitting its panel.
- Fresh preflight confirmed nine clear stopped-state files, zero positions and empty regular, GTT and Smart order books. All nine state-file hashes were unchanged across activation; other broker owner PIDs were unchanged. Post-verification recheck again confirmed nine clear state files, no positions and no regular orders.
- Only the explicitly approved FYERS child-process bounce was performed. No main-service or other-broker reload, login, runner start/rearm, order or trading-setting mutation was performed. Segment selection and open groups were verified retained across timeframe changes. Gross/net/fee handling was verified under segment filtering; no segment fee estimates were invented.
