# Sector Pulse — current operations

Updated 21 November 2026.

## Open the hosted application

- Dashboard: [utrading.pinakicloud.com](https://utrading.pinakicloud.com).
- Saved connections: [Broker accounts](https://utrading.pinakicloud.com/accounts).
- In-app help: [Help and parameter reference](https://utrading.pinakicloud.com/user-guide.html), available after application sign-in.
- GitHub integration branch: main. The [as-of-live release record](releases/2026-11-21-as-of-live.md) explains the captured source variants.

The previous public domain is obsolete for this installation.
Addresses beginning with 127.0.0.1 in setup instructions describe a separate local
installation or server-internal port. Hosted users should use the HTTPS links above.

## Connect once per account

Choose a saved broker account in Configuration → Brokers. FYERS uses its OAuth
connection flow. Dhan uses API-key browser consent and saves the resulting
authorization privately; manual access-token entry is not the normal login flow.
Delta India uses its saved API credentials and allowed server IP. Motilal Oswal uses
its own account connection. Each account retains separate credentials and journals.

A connection made in one section is reused across that saved account’s other
sections. A refreshed FYERS token invalidates the Handoff analysis client/cache;
Dhan’s native client also reloads changed saved credentials. Never copy credentials
into individual sections or assume one account’s login authorizes another account.

The visible dashboard checks its selected account on load and periodically. A
confirmed FYERS or Dhan authentication rejection offers the account-specific login
flow once per day in that browser session until a successful connection resets the warning. Unknown network status does not request
a new login. No browser-visible prompt is possible while the dashboard is closed.
Reconnect does not start runners or retry an order.

## Read Analysis Handoff correctly

The enabled scheduler uses exchange-session slots. Outside the supported trading
session, it waits for the next session rather than inventing new market findings.
Its operating mode and saved authorization are independent of the browser login.

Current scheduled findings must belong to the latest completed scan and have an
actual generation time no more than 15 minutes old. Historical or partial reports
remain available with their date and status; they are not current trade candidates.
Manual preparation also checks freshness on the server, even if an older page is
still open. Authentication failures, partial scans and zero eligible findings are
different outcomes and must remain visible.

Saving a schedule, enabling Live capability, starting a runner, submitting an order,
accepting an order and receiving a confirmed fill are separate actions and states.
Check the selected account, current data and pending orders before any explicit
execution. Duplicate-report preferences do not authorize duplicate orders.

## Find settings and troubleshoot

The searchable [user guide](user-functional-guide.md) is generated from
dashboard-help-content.json; edit that catalog and regenerate the HTML, Markdown and
contextual help together. The [source reference](source-reference.md) is generated
from application/strategy/helper source and lists callable signatures and defaults.
The [technical guide](technical-guide.md) separates current architecture from dated
mathematical audit details.

For a delayed job, inspect heartbeat and actual status. Missing history, fees,
valuation or basis means unavailable, not zero. A saved report or old chart marker
does not establish a current signal or an accepted order.

## Release, deployment and recovery

Use short-lived feature branches and pull requests to main. A merge updates source
history; it does not reload running Python processes. Account workspaces have source
copies that require their own targeted update and verification.

Before activation, inspect runner mode, positions, pending orders, recovery state,
and the specific process that owns the changed code. Preserve account-local
credentials, settings, journals and orders. Do not restart a Live runner to verify
documentation or UI changes.

Archived checkpoint documents retain their original evidence dates and process IDs.
They are historical records, not current service-health instructions. Start with this
guide for current links and workflows, and use the [deployment guide](deployment-guide.md)
for setup and controlled source activation.
