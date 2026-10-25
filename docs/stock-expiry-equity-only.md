# Stock-option expiry equity-only rule

For new stock-option entries, the nearest active listed stock-option expiry determines the restriction. On that expiry date and its preceding calendar day in Asia/Kolkata, new stock-option entries are blocked across the patched selection and ticket paths. Selecting a farther expiry does not bypass the rule. No premium-based fallback or next-month rollover is implemented.

Auto Handoff already collects cash-equity candidates independently from stock-option candidates. Near expiry, option candidates receive an explicit Equity only exclusion; eligible cash-equity candidates remain subject to normal conviction, fresh quotes, protection, exposure, allocation and product checks. An option-only strategy stands aside rather than silently converting option lots into an unvalidated equity share quantity. Bearish cash trades retain their existing intraday restrictions.

Existing positions, management orders and exits are not changed. The guard runs in new-entry contract selection or ticket preflight, not contract lookup for exits. Existing saved policies and authenticated Auto state are not rebound or rearmed by this implementation.

The policy uses actual broker-listed expiries rather than an assumed weekday or 30-day duration. It blocks today/tomorrow in IST, permits the nearest listed expiry at two calendar days or more, and ignores expired prior-month dates when the next month becomes the nearest active expiry.

Source updated on the authoritative Ubuntu checkout and targeted account snapshots. Runtime activation and broker acceptance must be reported separately. Tests use mocked broker responses and do not submit orders.

