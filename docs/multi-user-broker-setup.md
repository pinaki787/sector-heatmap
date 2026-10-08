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
