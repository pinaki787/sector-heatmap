# Saved broker sessions, report freshness and current documentation

Released 21 November 2026. This follows the
[as-of-live source preservation checkpoint](2026-11-21-as-of-live.md).

## Result

FYERS Handoff now checks the account's current saved token before analysis and
account reads. A token change rebuilds its analysis client and history cache;
failed construction cannot mark the old client as using the new token. Dhan
retains its existing reload-on-credential-change path. No mutation is retried
because authorization changes.

The latest completed report is selectable only when its actual generation time
is no more than 15 minutes old and it belongs to the latest scan. Historical and
partial findings remain visible with their timestamp. The Manual preparation
endpoint enforces the same freshness rule independently of the browser.

The dashboard shows the last scan date. Confirmed FYERS/Dhan authorization failure
offers an account-specific login flow with daily browser-session dismissal;
successful authentication clears the warning. Timeouts do not request a new login.

## Documentation

The current hosted origin is https://utrading.pinakicloud.com.
The README, documentation index, current operations, account setup, deployment and
technical guidance were updated. Dhan setup documents API-key consent with saved
authorization. The searchable help, Markdown guide and contextual descriptions
were regenerated from the maintained help catalog, dated 21 November 2026.
The source/settings catalog was regenerated without scanning installed Python
dependencies or historical frozen source copies. Dated checkpoint evidence is
labelled historical.

## Packaging and repeatable tests

Browser tests now have their own pinned package and lockfile under tests.
Run npm --prefix tests ci --ignore-scripts, then npm --prefix tests run test:handoff.
Tests no longer depend on a particular temporary jsdom directory.

The shared V1 Pine source is a regular source file rather than a symlink into a
private directory. Its bytes and catalog checksum are unchanged. Fresh account
provisioning can extract the committed source without rejecting that private-path
link.

## Activation and evidence

- Applied targeted source and cache-version updates to all six registered account
  workspaces, retaining existing workspace-specific code.
- Reloaded only the idle notification/Handoff coordinator during a closed NSE
  session. Checked zero RUNNING slots and no unresolved/submitting receipts first.
- Dashboard process IDs, saved account policies and credential files were preserved.
  No runner was started/stopped and no order was submitted by the rollout.
- The deployed FYERS Handoff client passed a real read-only broker profile check
  using the latest saved session.
- The hosted view marks the retained November report as historical, displays the
  last scan date, and disables preparation. The real expired Dhan session produces
  the account-specific reauthentication prompt.
- Hosted help was reviewed at desktop and narrow widths; the narrow document
  width matched its viewport with no horizontal overflow.
- 99 focused Python tests and 45 JavaScript checks passed, including fresh-account
  provisioning, token replacement, failed rebind, stale/partial evidence, Manual
  guards and authentication warning behavior.
- The shared V1 catalog checksum matched across all seven maintained sources.
- Documentation links, credential-pattern checks and source catalog coverage passed.

A truly expired Dhan authorization still requires the owner's broker consent;
this release does not fabricate a valid session or bypass broker login.
No new market-hours scan is claimed while NSE is closed.
