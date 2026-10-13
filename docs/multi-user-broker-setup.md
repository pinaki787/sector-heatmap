# Multiple users and broker accounts

Sector Pulse now has an opt-in localhost setup portal with separate user logins
and multiple FYERS / Delta India accounts per user. Login and account setup use the same dark colours, typography, panels,
fields and buttons as the Sector Pulse dashboard. Both share a faint NSE building
photograph and decorative bull/bear artwork behind readable foreground panels. Each account gets its own
source snapshot and dashboard port, private broker credentials and token cache,
settings, strategy state, Paper balance and journal. Different accounts can run
side by side; switching accounts does not change or stop an existing strategy.

## First setup

1. Install dependencies with the normal setup-only procedure. From a reviewed
   Git checkout, commit the release before provisioning; an extracted deployable
   uses its verified `release-source-files.json` inventory and needs no Git.
2. Create the first administrator locally:
   `.venv/bin/python -m sector_heatmap.workspace_portal --bootstrap-admin admin`
   Enter and repeat a password of at least 12 characters at the terminal prompt.
   Windows uses `.venv\Scripts\python.exe` instead. No password is stored in source
   or supplied on the command line.
3. Start setup with `.venv/bin/python -m sector_heatmap.workspace_portal`. Open
   `http://127.0.0.1:8079/`. Use exactly the displayed 127.0.0.1 address; localhost
   aliases are rejected to keep host/origin checks consistent. The optional
   `--port` must be outside account ports 8100–8999.
4. Sign in. The administrator can **Add user** with a username and initial
   password. Users can change their own passwords; this revokes all their login
   sessions. There is no public self-registration or default password.
5. Under **Add broker account**, choose FYERS or Delta India, a display label and
   the actual broker account ID/reference. Repeat for another account or broker.
   Only the owning user sees or opens its accounts; administrators cannot open
   another user's workspace through the portal.
6. Open **Connection settings**. FYERS requires the application ID and secret;
   register the exact per-account callback displayed, for example
   `http://127.0.0.1:8100/callback`, with that FYERS application. Complete browser
   login/2FA inside the account dashboard after saving. Delta requires its India
   API key/secret, account permissions and allowed destination IP at Delta.
7. Leave **Enable Live capability** off for Paper/read-only setup. Enabling it
   permits explicit account execution after the existing broker checks; it does
   not start a runner or place an order. KAMA/parser/protection-specific Live
   gates stay disabled in this initial workspace release. Credentials clear from
   the form on save and are never returned by the list/status APIs.
8. **Launch dashboard** creates and opens that account's isolated process. On
   first launch, source comes from the committed release or verified deployable
   inventory. Initialization can take time; if it is still starting, wait and
   use **Open dashboard** again. It opens in a separate tab with the username,
   account label and broker in the top bar. The Renko broker choice is bound to
   the account; change broker accounts using the portal. Start a selected
   strategy only after reviewing that account's Paper/Live settings and preflight.

Opening a newly created workspace starts data services, not a trading strategy.
For existing saved workspaces, the original module's recovery semantics still
apply: held Delta monitoring intent can restore exit-only monitoring after
reconciliation. Logout/password change denies further dashboard requests and
ends streaming updates after session recheck, but does not stop background
strategies, close positions or reconcile orders. Stop/reconcile deliberately
before changing users on a shared browser if exposure needs attention.

## Isolation and persistence

Default registry: `.private/workspaces/registry.sqlite3`. Credentials live in
`.private/workspaces/accounts/<generated-id>/credentials.json`; each account's
`source/` owns its `.private/` runtime files, and its `home/` owns broker token
caches and configuration discovery. File permissions restrict registry and
credential files to the local OS user. Passwords use salted scrypt; session
tokens are stored as hashes, expire after eight hours, and cookies are HttpOnly
and SameSite=Lax to permit the top-level FYERS callback. Portal writes require
same-origin JSON and a session CSRF token; account writes require exact owner,
Host and Origin. Repeated failed logins temporarily lock that username.

The registry enforces unique broker account references and application/key
identities. These references are user-supplied, not broker-verified identity
proof. Do not register the same actual account under another ID/application or
on another machine: local ownership locks are not broker-global locks. Broker
identity still comes from fresh adapter preflight. Processes inherit an
allowlisted environment, excluding the operator's FYERS/Delta/AI/Telegram secrets
and live gates; bundled straddle scripts replace external developer-home paths.
Native WhatsApp polling is unavailable in account workspaces because it reads the
shared desktop WhatsApp session. Other unsupported-broker actions are rejected.

Credential/application identity and Live capability settings are locked while
that dashboard process is running, including after portal restart. To edit them,
first stop and reconcile its strategies/exposure, then have the operator terminate
that dashboard process (the account row shows its PID) and save the connection. Changing to a different broker
application/key requires a new account workspace; existing runtime state is not
silently reassigned. Separate same-user accounts have separate Paper capital;
there is no combined live portfolio allocation across broker accounts.

## Updates and backups

An existing workspace keeps its source snapshot; opening it again does not replace
code or restart a strategy. `source-commit.txt` identifies that snapshot. Use the
[exposure-safe deployment procedure](deployment-guide.md) for updates: back up
private registry/credentials and journals consistently, reconcile and stop the
account process with operational authority, replace reviewed source while
preserving its account-local configuration/state, and verify revision and account
identity. Do not copy an active workspace between machines or start two managers
for the same actual account. The first release does not provide an automatic
workspace migration/update or credential import tool.

Public source deployables exclude the registry, passwords, sessions, credentials,
account source copies and runtime state. Keep private backups separately. Source
publication does not activate this portal, migrate the existing single-user
session or rearm any runner. The original single-user service remains independent
and is not protected by these portal logins. Do not expose the original service
or portal publicly; remote Internet hosting requires a separate deployment design
with HTTPS and appropriate access controls. All provisioned processes bind only
to 127.0.0.1; users here are application users on the local installation, not
separate OS security principals.

## Verification scope

Automated tests use fake credentials and exercise user ownership, admin limits,
session expiry/revocation, CSRF/Host/Origin checks, broker mutation boundaries,
duplicate credential identity, private file modes, inherited-secret exclusion,
source-copy separation and credential-free deployable provisioning. Browser tests
use a temporary demo registry and create FYERS/Delta account entries without
broker authentication or orders. Real broker login/fills and Windows process
execution require destination verification.


## Dhan broker accounts

In **User Master → Broker accounts**, choose **Dhan**, use the Dhan client ID
as the broker account reference, then save **Dhan client ID** and **Dhan access
token** under Connection settings. Each user's account and token remain private.
Token renewal is performed in DhanHQ; paste the renewed token in this account's
connection settings. Live capability remains off unless explicitly enabled by
the account owner. Saving or checking a connection does not send an order.

Open **Dhan order ticket** from the account row or dashboard account menu. The
manual ticket uses Dhan's security ID and current exchange segment, quantity,
product, LIMIT price, explicit risk levels and risk budget. Existing Analysis
Handoff and Screener ticket broker selectors also list the signed-in user's
configured Dhan accounts. Changing accounts invalidates the previous preview.
A batch must use one Dhan account throughout; its combined margin and risk must
fit the declared budgets. Review every ticket and warning before confirming.

Register this server's outgoing static IP in Dhan before attempting previews.
Dhan's data plan must be active for fresh quotes. IP registration is not changed
by this application. Normal LIMIT entry tickets do not place stop/target orders;
those fields are planning/risk inputs. Check accepted orders and actual fills in
Dhan. Use **Reconcile submitted orders** for uncertain acknowledgements; the
application never retries an uncertain order automatically.

Dhan now has account-bound Renko, RSI crossover, EMA Band and KAMA V6 routes
for bought NSE/BSE options. Bullish setups buy calls; bearish setups buy puts.
EMA Band and KAMA use the existing strategy signal functions. These routes
use current contracts, executable quotes, LIMIT IOC orders, durable correlation
journals and confirmed-fill reconciliation. Selecting an account or reviewing
activation never starts a runner. Runners remain stopped after restart.

Dhan cash/futures strategies, parser automation and multi-leg straddle automation
are unsupported. The Renko after-cost quick-loss filter is unavailable for Dhan
until its fee model is verified; gross P&L is separate from unavailable net P&L.
Existing account dashboards require a controlled source update for backend
changes; the main dashboard's native Dhan APIs load with the main service.

Provider references: [orders](https://dhanhq.co/docs/v2/orders/),
[authentication and IP registration](https://dhanhq.co/docs/v2/authentication/),
[instrument master](https://dhanhq.co/docs/v2/instruments/),
[quotes](https://dhanhq.co/docs/v2/market-quote/), and
[funds and margin](https://dhanhq.co/docs/v2/funds/).

### Broker choices in forms

Forms list the signed-in user's saved FYERS, Dhan and Delta India accounts.
Incomplete accounts and unsupported broker/form combinations remain visible but
disabled with a reason. Existing strategy forms stay on the main dashboard.
Saved FYERS and Delta requests use that user's private worker through an
authenticated same-origin proxy; Dhan uses its native account-bound APIs.
Selecting Renko accounts reloads the same dashboard form to mount the selected
broker. RSI, EMA Band and KAMA switch account routing without leaving the form.
Dhan KAMA is Paper-only here until invalidation and idea-risk protection are
implemented. Dhan EMA Band disables unsupported percentage protection and
resistance/volume exits. Account switches discard late responses and clear old
history while loading the selected account. Main-dashboard server credentials remain distinct from saved private
credentials. The sidebar reports saved configuration and independently checks
Dhan authentication. Selecting an account does not start a strategy or order.

Verification: fake-client tests cover ownership, whole lots/ticks, CE/PE mapping,
funds, stale quotes, unknown submission/no duplicate retry, partial fills, exact
owned exits, restart state, original indicator math and proxy isolation. Real
Dhan profile, positions, pending orders and chart history were read successfully.
No real order or strategy activation was performed. Saved FYERS/Delta private
workspace authentication still needs destination verification.


### Live account status and chart transport

The sidebar shows only the selected broker's connection result. Delta performs
its read-only authentication check against the selected private worker. Delta
HTTPS uses the whitelisted IPv4 source address; IPv6 is not silently used for
an IPv4-only key whitelist. No authentication check submits or closes orders.

Renko REST and EventSource URLs both use the selected account's proxy. Inventory
must resolve before the stream opens, preventing main-server runner state from
overwriting private account state. The proxy streams JSON without the HTML
buffer limit, compresses it when the browser accepts gzip, and disables
intermediary buffering for SSE. Large initial chart history still takes time to
calculate and render; network reconnection cannot guarantee uninterrupted ticks.
